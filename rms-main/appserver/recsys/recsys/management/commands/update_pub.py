import codecs
import json
import math
import subprocess
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures._base import TimeoutError

from django.core.management.base import CommandParser
from django.db.utils import DataError
from recsys.models import MongoConnection
from django.conf import settings
from django.utils import timezone
from django.db import close_old_connections

import logging
import datetime
import os
from tqdm import tqdm

from recsys.utils import tidy_paper_for_ann
from recsys.algorithms.aggregate import Aggregate
from recsys.error_report_command import ErrorReportingCommand
from recsys.models import HighQualityPaper

logger = logging.getLogger(__name__)


PUB_PATH = os.path.join(settings.LOCAL_CACHE_HOME, 'pub.json')
PUB_GZ_PATH = os.path.join(settings.LOCAL_CACHE_HOME, 'pub.json.gz')


class Command(ErrorReportingCommand):
    help = "Update publication pool"
    remote_host = settings.GPU_HOST
    remote_port = settings.GPU_PORT
    remote_user = settings.GPU_USER
    remote_path = "{}@{}:".format(remote_user, remote_host) + os.path.join(settings.GPU_HOME, "input_log")

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--start",
                            type=str,
                            required=False,
                            help="Start date")
        parser.add_argument("--end",
                            type=str,
                            required=False,
                            help="End date")
        parser.add_argument("--extra",
                            type=str,
                            required=False,
                            help="Extra json file")
        parser.add_argument("--mode",
                            type=str,
                            required=False,
                            default=PubExtract.MODEL_APPEND,
                            help=f"Support {PubExtract.MODEL_APPEND}|{PubExtract.MODEL_OVERWRITE}")

    def handle(self, *args, **options):
        if options['end']:
            end = timezone.now().strptime(options['end'], "%Y-%m-%d")
            end = timezone.make_aware(end)
        else:
            end = timezone.now().replace(minute=0, second=0, microsecond=0)

        if options['start']:
            start = timezone.now().strptime(options['start'], "%Y-%m-%d")
            start = timezone.make_aware(start)
        else:
            start = end - datetime.timedelta(2)

        extract = PubExtract(path=PUB_PATH, start=start, end=end, extra_path=options['extra'], mode=options['mode'])
        extract.export()

        # upload to gpu server
        if os.path.exists(PUB_GZ_PATH) and self.remote_host:
            os.system("rm -f {} && gzip -k {}".format(PUB_GZ_PATH, PUB_PATH))
            for i in range(3):
                args = ['/usr/bin/scp', '-p', '-P', str(self.remote_port), PUB_GZ_PATH, self.remote_path]
                p = subprocess.Popen(args)
                p.wait()
                if p.returncode != 0:
                    logger.error('failed, args {}'.format(args))
                    time.sleep(10 * (1 + math.exp(-i * 2)))
                else:
                    break


class PubExtract:
    MODEL_APPEND = "append"
    MODEL_OVERWRITE = "overwrite"

    def __init__(self, path, start, end, extra_path=None, mode=MODEL_APPEND):
        self.path = path
        self.sci_path = settings.HIGH_QUALITY_PAPER_ID_PATH
        self.pub_id_subject_map = {}  # {pub_id: {en: str, zh: str}}
        self.start = start
        self.end = end
        self.extra_path = extra_path
        self.mode = mode
        self.agg = Aggregate()

        self.ai2000_person_ids = set()
        self.exported_pub_ids = set()
        self.exported_hours = set()
        self.hour_format = "%Y-%m-%d %H"
        self.paper_id_map = {}  # {paper_id: id}

        self._initial_pub_id_subject_map()
        self._initial_paper_id_map()

        if os.path.exists(path) and self.mode == self.MODEL_APPEND:
            with tqdm(desc="load {}".format(self.path)) as bar:
                with codecs.open(path, encoding="utf-8") as f:
                    for line in f:
                        try:
                            pub = json.loads(line)
                        except Exception as e:
                            logger.warning("failed to load json {}: {}".format(line, e))
                            continue
                        if not pub:
                            continue
                        self.exported_pub_ids.add(pub["_id"])
                        if pub.get("ts"):
                            hour = timezone.now().strptime(pub['ts'], "%Y-%m-%d %H:%M:%S")
                            hour = timezone.make_aware(hour)
                            self.exported_hours.add(hour.strftime(self.hour_format))
                        bar.update()
        elif self.mode == self.MODEL_OVERWRITE:
            if os.path.exists(path):
                os.remove(path)

    def _initial_pub_id_subject_map(self):
        df = pd.read_csv(self.sci_path)
        for idx, row in tqdm(df.iterrows(), desc="Initial pub id subject map"):
            self.pub_id_subject_map[row['pub_id']] = {
                'zh': row['subject_zh'] if not pd.isna(row['subject_zh']) else "",
                'en': row['subject_en'] if not pd.isna(row['subject_en']) else "",
            }

        return self.pub_id_subject_map

    def _initial_paper_id_map(self):
        """ Get paper mysql id from mysql db
        :return: {paper_id: mysql_id}
        """
        step = 1000
        total = HighQualityPaper.objects.count()
        with tqdm(desc="Initial paper id map", total=total) as bar:
            for i in range(0, total + 1, step):
                rows = HighQualityPaper.objects.order_by("id")[i:i+step]
                for row in rows:
                    self.paper_id_map[row.paper_id] = row.id
                    bar.update()

        return self.paper_id_map

    def export(self):
        if HighQualityPaper.objects.count() < len(self.exported_pub_ids):
            self._sync_high_quality_table()

        # export from mongodb
        hours = (self.end - self.start).total_seconds() // 3600
        hours = int(hours)
        offset = self.start
        for i in range(hours):
            if offset.strftime(self.hour_format) in self.exported_hours:
                offset += datetime.timedelta(hours=1)
                continue
            offset_end = offset + datetime.timedelta(hours=1)
            items = get_mongo_data('aminer', 'publication_dupl', offset, offset_end)
            valid_num = self._export_pubs(items)
            print("{} ~ {}. Valid {}.".format(offset, offset_end, valid_num))
            offset += datetime.timedelta(hours=1)

        to_process_pub_ids = []
        # export form extra_path
        if self.extra_path and os.path.exists(self.extra_path):
            with open(self.extra_path) as f:
                pub_ids = json.load(f)
                for pub_id in pub_ids:
                    if pub_id in self.exported_pub_ids:
                        continue
                    to_process_pub_ids.append(pub_id)

        # export from SCI
        for paper_id in tqdm(self.pub_id_subject_map.keys(), desc="Process pubs from datacenter api"):
            if paper_id in self.exported_pub_ids:
                continue
            to_process_pub_ids.append(paper_id)

        step = 1000
        for i in range(0, len(to_process_pub_ids) + 1, step):
            items = MongoConnection.get_aminer_client().find_by_ids("aminer", "publication_dupl", to_process_pub_ids[i:i+step])
            self._export_pubs(items)

    def _sync_high_quality_table(self):
        with tqdm(desc="initial high quality table from db") as bar:
            with codecs.open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        pub = json.loads(line)
                    except Exception as e:
                        logger.warning("failed to load json {}: {}".format(line, e))
                        continue
                    if not pub:
                        continue
                    try:
                        self._save_pub_to_db(pub)
                    except Exception as e:
                        logger.warning("failed to save pub {} to db: {}".format(pub, e))
                        continue
                    bar.update()

    def _save_pub_to_db(self, pub:dict) -> int:
        """ Save pub to db table.
        :param pub: from preload_pub() method
        :return: Id of object 
        """
        if 'ts' not in pub:
            return -1
        if not pub['ts']:
            return -1

        try:
            ts = datetime.datetime.strptime(pub['ts'], "%Y-%m-%d %H:%M:%S")
            ts = timezone.make_aware(ts)
        except Exception as e:
            logger.warning("failed to parse ts: {}".format(e))
            return -1

        year = int(pub['year']) if pub.get('year') else None
        if pub['_id'] not in self.paper_id_map:
            obj = HighQualityPaper.objects.create(
                paper_id=pub['_id'],
                title=pub['title'],
                abstract=pub['abstract'],
                tags=",".join(pub['tags']),
                authors=",".join(pub['authors']),
                venue=pub['venue'],
                affiliations="|".join(pub['affiliations']),
                ts=ts,
                subject_zh=pub['subject_zh'],
                subject_en=pub['subject_en'],
                category=pub.get('category'),
                year=year
            )
            return obj.id
        else:
            old_obj = HighQualityPaper.objects.get(id=self.paper_id_map[pub['_id']])
            old_obj.tags = ",".join(pub['tags'])
            old_obj.ts = ts
            old_obj.affiliations = "|".join(pub['affiliations'])
            old_obj.subject_zh = pub['subject_zh']
            old_obj.subject_en = pub['subject_en']
            old_obj.year = pub['year']
            old_obj.save()
            return old_obj.id

    def _pack_record(self, record: dict) -> dict:
        """
        :param record: Mongodb publication_dupl
        :return:
            dict: returns record if valid, else None
        """

        if str(record['_id']) in self.exported_pub_ids:
            return {} 

        pid = str(record['_id'])
        pub = self.agg.preload_pub(pid)

        if self.is_too_old(pub):
            return {}

        if not self.agg.is_ccf_a(pub) and \
                not self.agg.is_sci_q1(pub) and \
                not self.is_valid_arxiv(pub):
            return {}

        category = pub.get('category') or ''
        if isinstance(category, list):
            category = ",".join(category)

        result = {
            'tags': [],
            "ts": record.get('ts').strftime("%Y-%m-%d %H:%M:%S") if record.get('ts') else "",
            'year': int(record['year']) if record.get('year') else None,
            'subject_zh': self.pub_id_subject_map.get(pid, {}).get('zh', ""),
            'subject_en': self.pub_id_subject_map.get(pid, {}).get('en') or "",
            'id_of_mysql': self.paper_id_map.get(pid, -1),
            'category': category,
        }

        citation = int(record.get('n_citation', '0'))
        year = int(record.get('year', '0'))
        if (citation > 100 and year > 2010) or (citation > 500 and year < 2010):
            result['tags'].append('High citation')

        num_viewed = pub.get('num_viewed') or 0
        if (num_viewed > 500 and year > 2010) or (num_viewed > 1000 and year < 2010):
            result['tags'].append('High viewed')

        if self.agg.is_sci_q1(pub):
            result['tags'].append("SCI")

        if self.agg.is_ccf_a(pub):
            result['tags'].append('CCFA')

        if self.is_valid_arxiv(pub):
            result['tags'].append("Arxiv")

        pub = tidy_paper_for_ann(pub)
        if not pub:
            return {}
        result.update(pub)
        return result

    def _export_pubs(self, pubs: list[dict]):
        """
        :param items:  list of mongodb publication_dupl object
        :return:
        """
        close_old_connections()
        n_valid = 0
        valid_pubs = list(filter(lambda x: x['_id'] not in self.exported_pub_ids, pubs))

        with tqdm(total=len(valid_pubs), desc="Export pubs") as bar:
            with ThreadPoolExecutor() as ex:
                with codecs.open(self.path, 'a', 'utf-8') as f:
                    futures = ex.map(self._pack_record, valid_pubs)
                    for r in futures:
                        try:
                            if not r:
                                continue
                            n_valid += 1
                            line = json.dumps(r)
                            f.write(line)
                            f.write("\n")

                            self.exported_pub_ids.add(r['_id'])
                            self._save_pub_to_db(r)
                        except TimeoutError as e:
                            logger.warning("timeout {}".format(e))
                        except DataError as e:
                            logger.warning("data error {}".format(e))
                        finally:
                            bar.update()

        return n_valid

    @classmethod
    def is_too_old(cls, pub, year_gap=5):
        if 'year' not in pub or pub['year'] is None:
            return True
        if isinstance(pub['year'], str):
            year = int(pub['year'])
        else:
            year = pub['year']

        if timezone.now().year - year > year_gap:
            return True

        return False

    def is_valid_arxiv(self, pub):
        if self.agg.is_arxiv(pub) is False:
            return False

        return True


def get_mongo_data(db, doc, start_time, end_time):
    mongo_client = MongoConnection.get_aminer_client()
    sql = {
        'ts': {'$gt': start_time, '$lte': end_time, '$exists': True}
    }

    return mongo_client.find(db, doc, sql)

