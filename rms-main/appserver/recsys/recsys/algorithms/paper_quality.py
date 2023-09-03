import json
import datetime

from django.db import connection
from django.utils import timezone
from django.conf import settings
import math
import os
from tqdm import tqdm
import pandas as pd

from recsys.algorithms.constants import Constants
from recsys.algorithms.redis_connection import RedisConnection
from recsys.algorithms.aggregate import Aggregate
from recsys.models import HotPaper, ActionLog


class PaperQuality:

    def __init__(self):
        self.output = os.path.join(settings.LOCAL_CACHE_HOME, "paper_quality.json")
        self.output_csv = os.path.join(settings.LOCAL_CACHE_HOME, "paper_quality.csv")
        self.redis_connection = RedisConnection.get_default()

    def train(self):
        start_time = timezone.now() - datetime.timedelta(60)
        sql = """
            SELECT
              "type",
              pub_ids,
              count(distinct ud) as UD,
              count(distinct uid) as UID,
              sum(click) as "Click",
              sum("show") as "Show"
            FROM 
              recsys_actionlog_of_all
            WHERE
              create_at > %s
            group BY
              "type", pub_ids
        """
        agg = Aggregate()
        papers = []
        with connection.cursor() as cursor:
            # cursor.execute(sql, (start_time.strftime(Constants.SQL_DATETIME_FORMAT)))
            cursor.execute(sql, [start_time.strftime(Constants.SQL_DATETIME_FORMAT)])
            for row in cursor.fetchall():
                paper = {
                    "type": int(row[0]),
                    'item': row[1].strip() if row[1] else "",
                    'ud': row[2],
                    'uid': row[3],
                    'click': int(row[4]),
                    'show': int(row[5]),
                }
                if not paper['item']:
                    continue
                paper['ctr'] = self.compute_ctr(paper)
                paper['adjust_ctr'] = self.compute_adjust_ctr(paper)
                paper['quality'] = self.compute_quality(paper)
                if paper['type'] == ActionLog.TYPE_PUB:
                    paper['item_type'] = agg.ITEM_PUB
                    pub = agg.get_cached_pub(paper['item'])
                    if pub:
                        paper['title'] = pub['title']
                elif paper['type'] == ActionLog.TYPE_PUB_TOPIC:
                    paper['item_type'] = agg.ITEM_PUB_TOPIC
                    topic = agg.get_cached_pub_topic(paper['item'])
                    if topic:
                        paper['title'] = topic['title']
                else:
                    paper['item_type'] = ''
                papers.append(paper)

        papers = sorted(papers, key=lambda x: x['quality'], reverse=True)
        top_papers = list(filter(lambda x: x['item_type'] in [agg.ITEM_PUB, agg.ITEM_PUB_TOPIC], papers))[:100]
        top_cache_key = self.get_top_cache_key()
        # self.redis_connection.setex(top_cache_key, 3600*7*24, json.dumps(top_papers))

        with open(self.output, "w") as f:
            for paper in tqdm(papers):
                self.redis_connection.setex(self.get_paper_cache_key(paper), 3600 * 24 * 7, json.dumps(paper))
                f.write(json.dumps(paper, ensure_ascii=False))
                f.write("\n")

        df = pd.read_json(self.output, lines=True)
        df.to_csv(self.output_csv)

    def get_paper_cache_key(self, paper):
        """
        :param paper: {type: str, item: str, ud: int, uid: int, click: int, show: int}
        :return:
            str: returns paper redis cache key
        """
        return "paper:quality:{}:{}".format(paper['type'], paper['item'])

    def get_top_cache_key(self):
        return "paper:quality:top"

    def get_top_items(self):
        """ Only fetch paper and topic
        :return: returns [
            {item_type: str, item: str, quality: float}
        ] if exists, else return []
        """
        key = self.get_top_cache_key()
        raw = self.redis_connection.get(key)
        if not raw:
            return []

        data = json.loads(raw)
        return data

    def get_item_quality(self, item_type, item_id):
        """
        :param item_type:
        :param item_id:
        :return:
            float: returns item quality if found, else None
        """
        paper = {
            "type": item_type,
            'item': item_id,
        }
        key = self.get_paper_cache_key(paper)
        raw = self.redis_connection.get(key)
        if not raw:
            return None

        data = json.loads(raw)
        return data['quality']

    def compute_quality(self, paper):
        """
        :param paper: {type: str, item: str, ud: int, uid: int, click: int, show: int}
        :return:
            float: returns paper quality
        """
        adjust_ctr = self.compute_adjust_ctr(paper)
        return 0.8 * adjust_ctr + 0.1 * math.log((paper['uid'] + 1)/10)

    def compute_ctr(self, paper):
        """
        :param paper: {type: str, item: str, ud: int, uid: int, click: int, show: int}
        :return:
            float: returns paper ctr
        """
        if paper['show'] == 0:
            return 0.0

        return paper['click'] / paper['show']

    def compute_adjust_ctr(self, paper):
        """
        :param paper: {type: str, item: str, ud: int, uid: int, click: int, show: int}
        :return:
            float: returns paper ctr
        """
        if paper['show'] == 0:
            return 0.0

        return paper['click'] / (paper['show'] + 1000)
