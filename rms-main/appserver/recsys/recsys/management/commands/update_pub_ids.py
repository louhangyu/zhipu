from django.core.management.base import BaseCommand
from django.core.management.base import CommandParser
from django.utils.timezone import now

import requests
import logging
from django.conf import settings
import os
import subprocess
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures._base import TimeoutError
import pandas as pd

from recsys.algorithms.aggregate import Aggregate
from recsys.algorithms.constants import Constants


logger = logging.getLogger(__name__)


SOURCE_VENUE = "venue"
SOURCE_PERSON = "person"


class Command(BaseCommand):
    help = "Update latest SCI Q1 and CCFA and ARXIV papers, person ids"
    remote_host = settings.GPU_HOST
    remote_port = settings.GPU_PORT
    remote_user = settings.GPU_USER
    remote_path = "{}@{}:".format(remote_user, remote_host) + os.path.join(settings.GPU_HOME, "input_log")

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--source",
                            type=str,
                            required=False,
                            default=SOURCE_PERSON,
                            help=f"You can select {SOURCE_PERSON}|{SOURCE_VENUE}")

    def handle(self, *args, **options):
        source = options['source']
        outputs = []
        if source == SOURCE_PERSON:
            exporter = PersonExport()
            exporter.export()
            outputs.append(exporter.output)
        elif source == SOURCE_VENUE:
            exporter = VenueExport()
            exporter.export()
            outputs.append(exporter.output)
        else:
            raise NotImplementedError(f"unknown source {source}")

        # upload to gpu server
        for src in outputs:
            if os.path.exists(src) and self.remote_host:
                args = ['/usr/bin/scp', '-p', '-P', str(self.remote_port), src, self.remote_path]
                p = subprocess.Popen(args)
                p.wait()
                if p.returncode != 0:
                    logger.error('failed, args {}'.format(args))


class SCIExport:
    SCI_SOURCE = Constants.SCI_SOURCE
    SCI_QUARTILE = Constants.SCI_QUARTILE
    CCF_SOURCE = Constants.CCF_SOURCE
    CCF_QUARTILE = Constants.CCF_QUARTILE

    def __init__(self, output=settings.HIGH_QUALITY_PAPER_ID_PATH):
        self.output = output
        self.agg = Aggregate()
        self.start_year = now().year - 1
        self.end_year = now().year + 1
        self.subject_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "subjects.csv"))
        self.subject_zh_en_map = {}

        for idx, row in self.subject_df.iterrows():
            self.subject_zh_en_map[row['zh']] = row['en']

    def export(self):
        all_papers = []  # list of (paper_id, subject_en, subject_zh)
        for (source, q) in [(self.SCI_SOURCE, self.SCI_QUARTILE), (self.CCF_SOURCE, self.CCF_QUARTILE)]:
            subject_ids = self.agg.fetch_subject_category(source, 0)
            venues = []  # list of (venue_obj, subject_en, subject_zh)
            logger.info("subject count {}, {}".format(len(subject_ids), subject_ids))
            for subject in tqdm(subject_ids, desc="{} venue load".format(source)):
                subject_zh = subject['name']
                subject_en = self.subject_zh_en_map.get(subject_zh, "")
                venues += [(x['id'], subject_en, subject_zh) for x in self.agg.fetch_venue_ids(subject['id'], q)]

            papers = []
            with tqdm(desc='{} has {} venues, load papers'.format(source, len(venues))) as bar:
                with ThreadPoolExecutor() as ex:
                    futures = [ex.submit(self.export_paper_by_venue, venue[0], self.start_year, self.end_year, venue[1], venue[2]) for venue in venues]
                    for future in as_completed(futures):
                        try:
                            r = future.result(timeout=300)
                            papers += r
                        except TimeoutError as e:
                            logger.warning("failed to fetch papers {}".format(e))
                        finally:
                            bar.update()

            print("source {} paper count {}".format(source, len(papers)))
            if not papers:
                logger.warning("source {}, quartile {}, papers count is zero".format(source, q))

            all_papers += papers

        # remove duplication and save it
        print("papers count {}".format(len(all_papers)))
        pub_ids_set = set()
        with open(self.output, "w") as f:
            f.write("pub_id,subject_en,subject_zh\n")
            for item in all_papers:
                pub_id = item[0]
                subject_en = item[1]
                subject_zh = item[2]
                if pub_id in pub_ids_set:
                    continue

                f.write("{},{},{}\n".format(pub_id, subject_en, subject_zh))
                pub_ids_set.add(pub_id)

    def export_paper_by_venue(self, venue_id, start, end, subject_en, subject_zh):
        """ Fetch paper ids by venue id
        :param venue_id:
        :param start:
        :param end:
        :param subject_en:
        :param subject_zh:
        :return: Returns list of (paper_id, subject en, subject zh)
        """
        paper_ids = self.agg.fetch_venue_paper_ids(venue_id, start, end)
        if not paper_ids:
            logger.warning("Venue {}, start {}, end {}, subject en {}, subject zh {}, don't have any papers".format(
                venue_id, start, end, subject_en, subject_zh)
            )

        return [(x['id'], subject_en, subject_zh) for x in paper_ids]


class PersonExport:

    def __init__(self, output=settings.HIGH_QUALITY_PERSON_ID_PATH):
        self.output = output
        self.agg = Aggregate()

    def export(self):
        person_ids = self.agg.fetch_person_pub_na(20, 10000*100)
        with open(self.output, "w") as f:
            for p in person_ids:
                f.write(p + "\n")


class VenueExport:

    def __init__(self, output=settings.HIGH_QUALITY_PAPER_ID_PATH):
        self.output = output
        self.all_pub_ids = set()

    def export(self):
        self._load_saved()
        
        f = open(self.output, "a")
        venue_ids = self._export_venues(10)
        for venue_id in tqdm(venue_ids, desc="fetch venue pubs"):
            pub_ids = self._export_pubs_of_venue(venue_id, 30)
            for pub_id in pub_ids:
                if pub_id in self.all_pub_ids:
                    continue
                self.all_pub_ids.add(pub_id)
                f.write(f"{pub_id},,\n")
        f.close()

    def _load_saved(self):
        with open(self.output) as f:
            f.readline()
            for line in f:
                item = line.split(",")
                pub_id = item[0]
                self.all_pub_ids.add(pub_id)
        print(f"Load saved pubs {len(self.all_pub_ids)}")

    def _export_venues(self, timeout=5):
        url = "https://datacenter.aminer.cn/venue/magic"
        step = 1000
        total = 4000
        headers = {
            'Content-Type': 'application/json'
        }
        venue_ids = []

        for i in range(0, total + 1, step):
            body = [
                {
                    "action":"venuePro.Query",
                    "parameters": {
                        "offset": i,
                        "size": i + step,
                        "category": "",
                    }
                }
            ]
            try:
                r = requests.post(url, headers=headers, json=body, timeout=timeout)
            except Exception as e:
                logger.warning(f"except when post {body} to {url}: {e}")
                continue

            if r.status_code != 200:
                logger.warning(f"response status code {r.status_code} is not 200 ok when post {body} to {url}")
                continue

            resp_data = r.json()
            logger.info(f"response {resp_data} from url {url}, body {body}")
            items = resp_data['data'][0].get('items', [])
            if not items:
                break
            for item in items:
                venue_ids.append(item['id'])

        print(f"Fetch {len(venue_ids)} venues") 
        return venue_ids
    
    def _export_pubs_of_venue(self, venue_id:str, timeout:int=5):
        url = "https://datacenter.aminer.cn/venue/magic"
        step = 200
        total = 20000
        headers = {
            'Content-Type': 'application/json'
        }
        pub_ids = []

        for i in range(0, total + 1, step):
            body = [
                {
                    "action":"venuePro.GetRecentVenueAndPublication",
                    "parameters": {
                        "offset": i,
                        "size": step,
                        "venue_id": venue_id,
                    }
                }
            ]
            try:
                r = requests.post(url, headers=headers, json=body, timeout=timeout)
            except Exception as e:
                logger.warning(f"except when post {body} to {url}: {e}")
                continue

            if r.status_code != 200:
                logger.warning(f"response status code {r.status_code} is not 200 ok when post {body} to {url}")
                continue

            resp_data = r.json()
            items = resp_data['data'][0].get('items', [])
            if not items:
                break
            for item in items:
                pub_ids.append(item['publication_id'])

        return pub_ids 

