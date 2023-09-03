import datetime
import os
from tqdm import tqdm
import logging
import random

from recsys.algorithms.base import BaseAlgorithmApi, BaseAlgorithmUpdate, RedisConnection, BaseRecall
from recsys.algorithms.constants import Constants
from recsys.ann import PaperIndex

from django.utils.timezone import now
from django.utils import timezone
from django import db

from recsys.utils import standard_score


logger = logging.getLogger(__name__)

ALGORITHM_SHENZHEN_NAME = "shenzhen"


class AlgorithmShenzhenApi(BaseAlgorithmApi):

    def __init__(self, name=ALGORITHM_SHENZHEN_NAME):
        super(AlgorithmShenzhenApi, self).__init__(RedisConnection.get_default(), name, AlgorithmShenzhenUpdate)

    def __str__(self):
        return "<AlgorithmShenzhenApi>"


class AlgorithmShenzhenUpdate(BaseAlgorithmUpdate):

    def __init__(self, name=ALGORITHM_SHENZHEN_NAME):
        super(AlgorithmShenzhenUpdate, self).__init__(RedisConnection.get_default(), name)
        self.non_keyword_recall_classes = [
            NewlyRecall,
        ]
        self.cold_recall_classes = [
            NewlyRecall
        ]


class NewlyRecall(BaseRecall):
    """Only fetch papers in our keywords
    """
    def __init__(self):
        super(NewlyRecall, self).__init__()
        self.recall_type = Constants.RECALL_SHENZHEN_NEWLY
        self.latest_24h = {}  # paper_id: count
        self.latest_24h_rank = {}  # paper_id: rank
        self.domain_keywords = set()
        self.domain_pub_ids = []  # list of {domain: str, pub_id: str}
        self.last_days = 21
        self.initial()

    def initial(self):
        sql = """
            SELECT
              pub_ids,
              sum(click) as "Click"
            FROM 
              recsys_actionlog_of_all
            WHERE
              day >= %s and type=1 and pub_ids is not null
            group BY
              pub_ids
        """
        start_time = timezone.now() - datetime.timedelta(self.last_days)
        with db.connection.cursor() as cursor:
            cursor.execute(sql, [start_time.strftime(Constants.SQL_DATETIME_FORMAT)])
            for row in cursor.fetchall():
                pub_id = row[0]
                count = int(row[1])
                self.latest_24h[pub_id] = count

        pub_counts = self.latest_24h.items()
        pub_counts = sorted(pub_counts, key=lambda x: x[1], reverse=True)
        for i, item in enumerate(pub_counts):
            pub_id = item[0]
            self.latest_24h_rank[pub_id] = i + 1

        self.initial_domain_keywords()
        self.load_domain_pub_ids()

    def initial_domain_keywords(self):
        path = os.path.join(os.path.dirname(__file__), "shenzhen.txt")
        with open(path) as f:
            for line in f:
                self.domain_keywords.add(line.strip())

        return self.domain_keywords

    def load_domain_pub_ids(self):
        pub_ids = set()
        paper_index = PaperIndex()
        for domain in self.domain_keywords:
            candidates = paper_index.search_by_dict({'title': domain}, 50)
            for pub_id, _ in candidates:
                if pub_id in pub_ids:
                    continue
                self.domain_pub_ids.append({'domain': domain, 'pub_id': pub_id})
                pub_ids.add(pub_id)

        self.domain_pub_ids = self.domain_pub_ids[:1000]

        logger.info("Found {} domain pubs".format(len(self.domain_pub_ids)))
        return self.domain_pub_ids

    def load_data(self):
        users = self.fetch_active_uids()

        item_type_user_items_map = {self.ITEM_PUB: {}, self.ITEM_PUB_TOPIC: {}}
        for user_type, user_id in tqdm(users, desc="{} load data".format(self.__class__.__name__)):
            item_type_items_map = self.load_data_for_user(user_type, user_id)
            for item_type, items in item_type_items_map.items():
                item_type_user_items_map[item_type][(user_type, user_id)] = items

        return item_type_user_items_map, users

    def load_data_for_user(self, user_type, user_id, count=100, keyword=""):
        """ Run in background
        :param user_type:
        :param user_id:
        :param count:
        :param keyword:
        :return:
            dict: returns
            {
                item_type: [
                    {item: str, score: float, type: str, recall_type: str, recall_reason: str},
                    ...
                ]
            }
        """
        random.shuffle(self.domain_pub_ids)
        top_pubs = self.domain_pub_ids[:count]
        items = []
        for i, domain_pub_id_map in enumerate(top_pubs):
            item = {
                'type': self.ITEM_PUB,
                'item': domain_pub_id_map['pub_id'],
                # 'recall_reason': self.pack_recall_reason(domain_pub_id_map['pub_id'], domain_pub_id_map['domain']),
                'recall_reason': "",
                'recall_type': self.recall_type,
                'recall_source': "stream",
                'recall_time': "{}".format(now()),
                'score': 1.0 - i / count,
            }
            items.append(item)
        standard_score(items, 'score')
        return {self.ITEM_PUB: items}

    def pack_recall_reason(self, pub_id, domain):
        """
        :return: returns {zh: '', en: ''}
        """
        en = [domain]
        zh = [domain]
        rank = self.latest_24h_rank.get(pub_id, -1)
        click = self.latest_24h.get(pub_id, 0)

        if 0 < rank < 10:
            en.append("Latest 24h view rank at {}".format(rank))
            zh.append("最近24小时访问量第{}".format(rank))
        elif click > 10:
            en.append("{} views in last 24 hours".format(click))
            zh.append("最近24小时有{}次浏览".format(click))

        return {'en': ", ".join(en), "zh": ", ".join(zh)}

