"""Extract user event log by day
"""
from django.core.management.base import CommandParser
from django.utils import timezone
from django.conf import settings

from recsys.models import MongoConnection, ActionLog, UserEventLog
from recsys.error_report_command import ErrorReportingCommand

from urllib.parse import unquote
import logging
import datetime
import json
import re
import os
import subprocess
import time
import math
import pytz


logger = logging.getLogger(__name__)


class Command(ErrorReportingCommand):
    help = "Export user event log"
    remote_host = settings.GPU_HOST
    remote_port = settings.GPU_PORT
    remote_user = settings.GPU_USER
    remote_directory = os.path.join(settings.GPU_HOME, "input_log")

    def add_arguments(self, parser: CommandParser):
        parser.add_argument('--start',
                            type=str,
                            required=False,
                            default='',
                            help="Start date to extract")

    def handle(self, *args, **options):
        mongo_client = MongoConnection.get_aminer_client()
        end = (timezone.now() + datetime.timedelta(1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if options['start']:
            start = timezone.now().strptime(options['start'], "%Y-%m-%d")
            start = timezone.make_aware(start)
        else:
            start = end - datetime.timedelta(days=1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)

        offset = start
        while offset < end:
            offset_end = offset.replace(hour=23, minute=59, second=59, microsecond=59)
            sql = {
                'tc': {'$gte': offset, "$lt": offset_end}
            }
            event_logs = mongo_client.find('web', 'user_event_log', sql)
            if len(event_logs) == 0:
                event_logs = mongo_client.find("web", "user_event_log_2021_12_18_22_40", sql)

            action_logs = ActionLog.objects.filter(
                create_at__range=(offset, offset_end),
                action=ActionLog.ACTION_CLICK
            ).all()

            sh_tz = pytz.timezone("Asia/Shanghai")
            offset_native = timezone.make_naive(offset, timezone=sh_tz)
            remote_path = '{}@{}:{}/{}-log.json'.format(
                self.remote_user, self.remote_host, self.remote_directory, offset_native.strftime('%Y-%m-%d'))
            local_path = '/data/cache/aminer/user_event_log_{}.json'.format(offset_native.strftime("%Y_%m_%d"))

            extract = ActionLogExport(output=local_path, event_logs=event_logs, action_logs=action_logs, day=offset.date())
            extract.save()

            if os.path.exists(local_path):
                for i in range(3):
                    args = ['/usr/bin/scp', '-p', '-P', str(self.remote_port), local_path, remote_path]
                    p = subprocess.Popen(args)
                    p.wait()
                    if p.returncode != 0:
                        logger.error('failed, args {}'.format(args))
                        time.sleep(10 * (1 + math.exp(-i * 2)))
                    else:
                        break
            print("{} Done. Event log {}, action log {} in ({}, {})".format(datetime.datetime.now(), len(event_logs), len(action_logs), offset, offset_end))

            offset += datetime.timedelta(1)
            os.remove(local_path)


class ActionLogExport:
    def __init__(self, output, event_logs, action_logs, day):
        self.output = output
        self.event_logs = event_logs
        self.action_logs = action_logs
        self.day = day

        self.data = []
        self.hash = {}
        self.time_format = "%Y-%m-%d %H:%M:%S"

    @classmethod
    def is_mongod_bid(cls, item):
        if len(item) != 24:
            return False
        for c in item:
            if c.isalnum() is False:
                return False
        return True

    def parse_url(self, url):
        """ Parse url and extract visit type, visit content
        :param url: str
        :return:
          (str, str): returns tag name and tag content
        """
        tag = re.split('/|\?|&', url)

        # 'https(s):'
        if tag[0] not in ['https:', 'http:']:
            #print("Mismatch 'http(s):", url)
            return None, None

        # 'https(s)://'
        if tag[1] != '':
            #print("Mismatch https(s)://", url)
            return None, None

        # ['www.aminer.cn', 'https?://(((www-)?beta.aminer.cn)|(www-\d+.aminer.cn)|(\d+\.\d+\.\d+\.\d+)|(localhost))']
        if tag[2] != 'www.aminer.cn':
            pattern = re.compile(
                'https?://(((www-)?beta.aminer.cn)|(www-\d+.aminer.cn)|(\d+\.\d+\.\d+\.\d+)|(localhost)|(www.aminer.org)|(.*aminer.cn:7001))')
            if pattern.match(url):
                return None, None
            else:
                # print("Mismatch www.aminer.cn", url)
                pass

        # homepage, ['www.aminer.cn']
        if len(tag) == 3 or (len(tag) == 4 and tag[3] == ''):
            # return 'homepage', None
            return None, None

        # 'www.aminer.cn/pub or profile or search'
        if tag[3] == 'pub':
            if len(tag) >= 5 and self.is_mongod_bid(tag[4]):
                return 'pub', tag[4]
            # print ("Mismatch www.aminer.cn/pub/", url)
        elif tag[3] == 'profile':
            if len(tag) >= 5 and self.is_mongod_bid(tag[4]):
                return 'person', tag[4]
            if len(tag) >= 6 and self.is_mongod_bid(tag[5]):
                return 'person', tag[5]
            # print ("Mismatch www.aminer.cn/profile/", url)
        elif tag[3] == 'search' and len(tag) >= 6 and tag[4] == 'pub':
            query = None
            for q in tag[5:]:
                if q.startswith('q='):
                    query = unquote(q[2:])
                    break
            if query:
                return 'search_pub', query
            # print ("Mismatch www.aminer.cn/search/pub/", url)
        elif tag[3] == 'search' and len(tag) >= 6 and tag[4] == 'person':
            query = None
            for q in tag[5:]:
                if q.startswith('q='):
                    query = unquote(q[2:])
                    break
            if query:
                return 'search_person', query
            # print ("Mismatch www.aminer.cn/search/person/", url)
        elif tag[3] == 'topic':
            if len(tag) >= 5 and self.is_mongod_bid(tag[4]):
                return 'topic', tag[4]
            if len(tag) < 5:
                return None, None
            for label in ['page', 'channel', 'sort', 'f=cs']:
                if label in tag[4]:
                    return None, None
            # print ("Mismatch www.aminer.cn/topic/", url)
        elif tag[3] == 'conf':
            return None, None
        elif tag[3] == 'research_report':
            if len(tag) >= 5 and self.is_mongod_bid(tag[4]):
                return 'research_report', tag[4]
            if len(tag) >= 6 and self.is_mongod_bid(tag[5]):
                return 'research_report', tag[5]
            if len(tag) < 5:
                return None, None

        return None, None

    def tidy_user_event_log(self, record):
        """ Tidy record
        :param record: document of mongodb database web.user_event_log, format is
            {
                "_id" : ObjectId("621c4185d9bcc380058fffb1"),
                "tc" : ISODate("2022-02-28T03:28:59.391Z"),
                "ip" : "125.41.244.185",
                "agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
                "cd" : 24,
                "ck" : 1,
                "ds" : "1280x720",
                "du" : "www.aminer.cn",
                "es" : 1,
                "isnew" : 1,
                "isp" : "0",
                "ja" : 0,
                "ln" : "zh-CN",
                "os" : "Windows 10",
                "ou" : "https://www.aminer.cn/profile/renata-petrillo/5630efad45ceb49c5de1638e",
                "pt" : "Petrillo Renata - AI Profile | 人才画像",
                "re" : "",
                "sb" : "Chrome",
                "sn" : 0,
                "u" : "https://www.aminer.cn/profile/renata-petrillo/5630efad45ceb49c5de1638e",
                "ud" : "Qdsxkb481Zzal8rbFuOmQ",
                "up" : "qwoSZaIzmAkMwKe48AIEh"
            }

        :return:
          dict: returns tidy dict, format is
            {
              _id: str,
              ip: str,
              user: str,
              tc: datetime,
              type: str,
              query: str,
              uid: str,
              ud: str,
              item: str
            }
        """
        if 'ud' not in record or 'u' not in record or 'ip' not in record:
            return
        item_type, item = self.parse_url(record['u'])
        if item_type is None:
            return
        result = {
            '_id': record['_id'],
            'ip': record['ip'],
            'user': record['ud'],
            'tc': record['tc'],
            'type': item_type,
            "ud": record['ud']
        }
        if item_type.startswith('search_'):
            result['query'] = item[:250]
        else:
            result['item'] = item

        if 'uid' in record:
            # the log from log in user
            result['uid'] = record['uid']
            result['user'] = record['uid']

        self.data.append(result)
        return result

    def tidy_action_log(self, record: ActionLog) -> dict:
        """
        :param record: ActionLog Object
        :return:
          dict: returns tidy dict, format is
            {
              _id: str,
              ip: str,
              user: str,
              tc: datetime,
              type: str,
              query: str,
              uid: str,
              ud: str,
              item: str
            }
        """
        if record.action not in [ActionLog.ACTION_CLICK, ActionLog.ACTION_SEARCH]:
            return {}

        uid_is_none = False
        if record.uid is None or record.uid == "None" or record.uid.strip() == "":
            uid_is_none = True

        ud_is_none = False
        if record.ud is None or record.ud == "None" or record.ud.strip() == "":
            ud_is_none = True

        if uid_is_none and ud_is_none:
            logger.warning("action log {} do not contain any ud or uid".format(record))
            return {}

        result = {
            "_id": record.id,
            "ip": record.ip or "",
            "user": record.uid if record.uid else record.ud,
            "tc": record.create_at,
            "query": record.query,
            'uid': record.uid or "",
            'ud': record.ud or "",
            'type': "",
            'item': '',
        }

        if record.type == ActionLog.TYPE_PUB:
            result['type'] = 'pub'
            result['item'] = record.pub_ids
        elif record.type == ActionLog.TYPE_PUB_TOPIC:
            result['type'] = 'topic'
            result['item'] = record.pub_ids
        elif record.type == ActionLog.TYPE_REPORT:
            result['type'] = 'research_report'
            result['item'] = record.pub_ids
        elif record.type == ActionLog.TYPE_PROFILE:
            result['type'] = 'person'
            result['item'] = record.pub_ids

        self.data.append(result)

    def save(self):
        for record in self.event_logs:
            record['_id'] = str(record['_id'])
            self.tidy_user_event_log(record)

        for record in self.action_logs:
            self.tidy_action_log(record)

        # save to db
        UserEventLog.objects.filter(tc_day=self.day).delete()
        step = 1000
        for i in range(0, len(self.data) + 1, step):
            bulk = self.data[i:i+step]
            records = []
            for r in bulk:
                records.append(UserEventLog(
                    ip=r['ip'],
                    user=r['user'],
                    tc=r['tc'],
                    tc_day=self.day,
                    type=r.get('type'),
                    query=r.get('query'),
                    uid=r.get('uid'),
                    ud=r.get('ud'),
                    item=r.get('item')
                ))
            try:
                UserEventLog.objects.bulk_create(records)
            except Exception as e:
                logger.warning("expect when bulk create: {}".format(e))

        with open(self.output, 'w') as file:
            data = []
            for r in self.data:
                r['tc'] = r['tc'].strftime(self.time_format)
                data.append(r)
            json.dump(data, file, indent=4, ensure_ascii=False)
