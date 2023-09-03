""" Find new papers according by subscribe keywords
"""
import json
import logging
import requests
import random

from recsys.algorithms.base import BaseAlgorithmApi, BaseAlgorithmUpdate, RedisConnection, BaseRecall
from recsys.algorithms.constants import Constants
from recsys.algorithms.subscribe_stat import SubscribeStat

from django.utils import timezone
from django.conf import settings


logger = logging.getLogger(__name__)

ALGORITHM_PUSH_NAME = "push"


class AlgorithmPushApi(BaseAlgorithmApi):

    def __init__(self, name=ALGORITHM_PUSH_NAME):
        super(AlgorithmPushApi, self).__init__(RedisConnection.get_default(), name, AlgorithmPushUpdate)

    def __str__(self):
        return "<AlgorithmPushApi>"


class AlgorithmPushUpdate(BaseAlgorithmUpdate):

    def __init__(self, name=ALGORITHM_PUSH_NAME):
        super(AlgorithmPushUpdate, self).__init__(RedisConnection.get_default(), name)
        self.non_keyword_recall_classes = [
            HotPushRecall,
            WeekPushRecall,
            NewPushRecall,
            FollowPushRecall
        ]
        self.cold_cache_time = 3600*24

    def train_keyword(self, preload_item_use_cache=True):
        pass

    def fetch_keyword_recommendations(self, uid, ud, keyword, num=100):
        """
        :param uid:
        :param ud:
        :param keyword:
        :param num:
        :return: [{item: str, score: float, type: str, recall_type: str}]
        """
        if not keyword:
            logger.warning("keyword {} is none, return []".format(keyword))
            return []

        candidates = []
        subscribe_stat = SubscribeStat(uid)
        keyword_newly_map = subscribe_stat.get_newly()
        if keyword_newly_map and keyword in keyword_newly_map and keyword_newly_map[keyword]['example']:
            for i, item in enumerate(keyword_newly_map[keyword]['example']):
                if isinstance(item, str):
                    pub_id = item
                    score = 1 - 1 / i
                else:
                    pub_id = item['id']
                    score = item['score']
                candidates.append({
                    'item': pub_id,
                    'type': self.ITEM_PUB,
                    'score': score,
                    'recall_type': Constants.RECALL_SUBSCRIBE,
                    'recall_reason': {
                        'zh': '包含订阅词',
                        'en': 'Subscribed'
                    }
                })

            return candidates
        else:
            return []


class HotPushRecall(BaseRecall):

    def __init__(self):
        from recsys.algorithms.aggregate import Aggregate

        super(HotPushRecall, self).__init__(ALGORITHM_PUSH_NAME)
        self.recall_type = Constants.RECALL_PUSH_HOT
        self.keyword_papers_map = {}  # {keyword: [{pid: str, title: str, similarity: float}]}
        self.filename = self.get_filename_by_item_type(None)
        self.url = settings.RECALL_DATA_URL + "/meta/miniprogram/{}".format(self.filename)
        self.agg = Aggregate()
        self.preload()

    def preload(self):
        r = requests.get(self.url)
        if r.status_code != 200:
            logger.warning("{} status code is not 200, {}".format(self.url, r.status_code))
            return
        for line in r.text.split("\n"):
            if not line:
                continue
            item = json.loads(line)
            self.keyword_papers_map.update(item)

    def load_data_for_user(self, user_type, user_id, count=50, keyword=""):
        if user_type != Constants.USER_UID:
            return {}

        subscribe_keywords, _ = self.get_user_keywords_and_subject(user_id)
        if not subscribe_keywords:
            return {}

        candidates = []
        word_count = max(1, int(count / len(subscribe_keywords)))
        for keyword in subscribe_keywords:
            if not keyword:
                continue
            papers = self.keyword_papers_map.get(keyword.strip().lower(), [])
            if not papers:
                continue
            random.shuffle(papers)
            for paper in papers[:word_count]:
                recall_reason = self.pack_recall_reason({
                    'paper_id': paper['pid'],
                    'keywords': [keyword],
                })
                item = {
                    'type': self.ITEM_PUB,
                    'item': paper['pid'],
                    'score': paper['similarity']*0.1,
                    "recall_reason": recall_reason,
                    'recall_type': self.recall_type,
                    'recall_source': self.filename,
                    'recall_time': "{}".format(timezone.now()),
                    'recall_keyword': keyword
                }
                candidates.append(item)

        candidates = self.merge_duplications(candidates)
        result = {self.ITEM_PUB: candidates}
        return result

    def pack_recall_reason(self, paper):
        """
        :param paper: format is {paper_id: str, distance: float, keywords: []}
        :return: returns {zh: str, en: str}
        """
        keywords = paper.get('keywords')
        if keywords:
            if isinstance(keywords, list):
                keywords = list(set(keywords))
                keywords_text = list(map(lambda x: "「{}」".format(x), keywords))
                keywords_text = ", ".join(keywords_text)
        else:
            keywords_text = ""

        pub = self.agg.preload_pub(paper['paper_id'])
        labels = pub.get('labels') or []
        if 'New' in labels:
            flag_text = "New"
            flag_text_zh = "最新论文"
        elif "High Citation" in labels:
            flag_text = "High Citation"
            flag_text_zh = "高引论文"
        else:
            flag_text = ""
            flag_text_zh = "论文"

        if len(keywords) == 1:
            result = {
                "zh": "{}相关联领域的{}".format(keywords_text, flag_text_zh),
                "en": "{} Paper in related {}".format(flag_text, keywords_text),
            }
        else:
            result = {
                "zh": "{}相关联领域交叉的{}".format(keywords_text, flag_text_zh),
                "en": "{} Paper both in related {}".format(flag_text, keywords_text),
            }

        return result

    def get_filename_by_item_type(self, item_type, dt=None):
        if not dt:
            dt = timezone.now()

        return "daily-{}.json".format(dt.strftime(Constants.SQL_DATE_FORMAT))


class WeekPushRecall(HotPushRecall):

    def __init__(self):
        super(WeekPushRecall, self).__init__()
        self.recall_type = Constants.RECALL_PUSH_WEEK

    def get_filename_by_item_type(self, item_type, dt=None):
        if not dt:
            dt = timezone.now()

        return "weekly-{}.json".format(dt.strftime(Constants.SQL_DATE_FORMAT))


class NewPushRecall(BaseRecall):
    def __init__(self):
        super(NewPushRecall, self).__init__(ALGORITHM_PUSH_NAME)
        self.recall_type = Constants.RECALL_PUSH_NEW

    def load_data_for_user(self, user_type, user_id, count=100, keyword=""):
        if user_type != Constants.USER_UID:
            return {}

        candidates = []
        subscribe_stat = SubscribeStat(user_id)
        keyword_newly_map = subscribe_stat.train(False)
        if not keyword_newly_map:
            return {}

        for keyword, state in keyword_newly_map.items():
            for i, item in enumerate(state['example']):
                if isinstance(item, str):
                    pub_id = item
                    score = 1 - 1 / i
                else:
                    pub_id = item['id']
                    score = item['score']
                candidates.append({
                    'item': pub_id,
                    'type': self.ITEM_PUB,
                    'score': score*0.8,
                    'recall_type': self.recall_type,
                    'recall_reason': {
                        'zh': '',
                        'en': '',
                    },
                    'recall_keyword': keyword,
                    'recall_time': "{}".format(timezone.now()),
                })

        top_papers = self.discount_by_show_and_click(user_id, None, candidates)[:count]
        return {self.ITEM_PUB: top_papers}


class FollowPushRecall(BaseRecall):

    def __init__(self):
        from recsys.algorithms.aggregate import Aggregate

        super(FollowPushRecall, self).__init__(ALGORITHM_PUSH_NAME)
        self.recall_type = Constants.RECALL_PUSH_FOLLOW
        self.filename = self.get_filename_by_item_type(None)
        self.url = settings.RECALL_DATA_URL + "/meta/email_follow_new/{}".format(self.filename)
        self.agg = Aggregate()
        self.uid_papers_map = {}  # uid: {paper_id: str, ...}
        self.preload()

    def preload(self):
        r = requests.get(self.url)
        if r.status_code != 200:
            logger.warning("{} status code is not 200, {}".format(self.url, r.status_code))
            return
        for line in r.text.split("\n"):
            if not line:
                continue
            item = json.loads(line)
            self.uid_papers_map[item['uid']] = item['papers']

    def load_data_for_user(self, user_type, user_id, count=50, keyword=""):
        if user_type != Constants.USER_UID:
            return {}

        if user_id not in self.uid_papers_map:
            return {}

        candidates = []
        for item in self.uid_papers_map[user_id]:
            c = {
                'type': self.ITEM_PUB,
                'item': item['paper_id'],
                'score': 0.5,
                "recall_reason": "",
                'recall_type': self.recall_type,
                'recall_source': self.filename,
                'recall_time': "{}".format(timezone.now()),
                'id_of_followed_author': item.get('id_of_followed_author'),
                'name_of_followed_author': item.get('name_of_followed_author'),
                'chinese_name_of_followed_author': item.get("chinese_name_of_followed_author"),
            }
            candidates.append(c)

        return {self.ITEM_PUB: candidates}

    def pack_recall_reason(self, paper):
        """
        :param paper: format is {paper_id: str, distance: float, keywords: []}
        :return: returns {zh: str, en: str}
        """
        keywords = paper.get('keywords')
        if keywords:
            if isinstance(keywords, list):
                keywords = list(set(keywords))
                keywords_text = list(map(lambda x: "「{}」".format(x), keywords))
                keywords_text = ", ".join(keywords_text)
        else:
            keywords_text = ""

        pub = self.agg.preload_pub(paper['paper_id'])
        labels = pub.get('labels') or []
        if 'New' in labels:
            flag_text = "New"
            flag_text_zh = "最新论文"
        elif "High Citation" in labels:
            flag_text = "High Citation"
            flag_text_zh = "高引论文"
        else:
            flag_text = ""
            flag_text_zh = "论文"

        if len(keywords) == 1:
            result = {
                "zh": "{}相关联领域的{}".format(keywords_text, flag_text_zh),
                "en": "{} Paper in related {}".format(flag_text, keywords_text),
            }
        else:
            result = {
                "zh": "{}相关联领域交叉的{}".format(keywords_text, flag_text_zh),
                "en": "{} Paper both in related {}".format(flag_text, keywords_text),
            }

        return result

    def get_filename_by_item_type(self, item_type, dt=None):
        if not dt:
            dt = timezone.now()

        return "email-follow-{}.json".format(dt.strftime(Constants.SQL_DATE_FORMAT))
