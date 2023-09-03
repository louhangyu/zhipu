import datetime
import math
import os

from tqdm import tqdm
import requests
import logging
import gzip
import json
import random

from recsys.algorithms.base import BaseAlgorithmApi, BaseAlgorithmUpdate, RedisConnection, BaseRecall
from recsys.algorithms.constants import Constants
from recsys.algorithms.aggregate import Aggregate
from recsys.algorithms.text_similarity import TextSimilarity
from recsys.algorithms.related_word import get_neighbours
from recsys.models import HotPaper, Subject, ActionLog
from recsys.ann import PaperIndex
from recsys.algorithms.make_top import MakeTop
from recsys.algorithms import get_vector_cosine

from django.utils.timezone import now
from django.utils import timezone
from django.conf import settings
from django import db

from recsys.utils import standard_score, is_mongo_id
from recsys.perf_collect import default_perf_collect


logger = logging.getLogger(__name__)
ALGORITHM_NATIVE_MR_NAME = "native_mr"
subject_en_keywords_map = {}


def get_subject_keywords(subject):
    """
    :param subject: str
    :return:
      []: returns list of keyword
    """
    global subject_en_keywords_map

    if not subject_en_keywords_map:
        subjects = Subject.objects.all()
        for sub in subjects:
            title = sub.title.lower().strip()
            words = sub.keywords.lower().strip()
            subject_en_keywords_map[title] = list(set([x.strip() for x in words.split(",")]))

    if not subject:
        return []

    subject = subject.lower()
    if subject not in subject_en_keywords_map:
        logger.warning("subject {} not found in {}".format(subject, subject_en_keywords_map))
        return []

    return subject_en_keywords_map[subject]


class AlgorithmNativeApi(BaseAlgorithmApi):

    def __init__(self, name=ALGORITHM_NATIVE_MR_NAME):
        super(AlgorithmNativeApi, self).__init__(RedisConnection.get_default(), name, AlgorithmNativeUpdate)

    def __str__(self):
        return "<AlgorithmNativeRecallApi>"


class AlgorithmNativeUpdate(BaseAlgorithmUpdate):
    COLD_USER = Constants.COLD_USER_ID
    COLD_USER_TYPE = Constants.COLD_USER_TYPE

    def __init__(self, name=ALGORITHM_NATIVE_MR_NAME):
        super(AlgorithmNativeUpdate, self).__init__(RedisConnection.get_default(), name)
        self.non_keyword_recall_classes = [
            AI2KRecall,
            BehaviorRecall,
            BehaviorPersonRecall,
            EditorHotRecall,
            # SubjectRecall,
            FollowRecall,
            SubscribeKGRecall,
            SubscribeRecall,
            SubscribeOAGRecall,
            # HotTopicRecall,
            SearchRecall,
            HotRecall,
        ]
        self.cold_recall_classes = [
            #EditorHotRecall,
            #HotRecall,
            #HotTopicRecall,
            #RandomPersonRecall,
            #AI2KRecall,
            #ColdAI2KRecall,
            #ColdSubscribeRecall,
            #ColdSubscribeOAGRecall,
            ColdTopRecall,
        ]

    def update_non_keyword_recommendation(self, uid, ud, recall_names=['EditorHotRecall', 'SubscribeRecall', 'SearchRecall', 'SubscribeOAGRecall', 'SubscribeKGRecall']):
        """ Run in background RQ if uid is not null
        :param uid:
        :param ud:
        :param recall_names:
        :return: int
        """
        if not uid:
            logger.warning("uid is empty, ignore")
            return 0
        logger.info("start update non keyword recommendations for {}".format(uid))
        user_type = Constants.USER_UID
        user_id = uid
        cache_key = self.get_non_keyword_rec_cache_key(uid, None)
        old_rec = self.get_non_keyword_rec_cache(uid, None)
        logger.info("get old rec for {}".format(uid))
        if not old_rec:
            old_rec = {'user_type': user_type, "user": uid, 'rec': []}

        new_items = []
        recall_classes = [
            EditorHotRecall,
            SubscribeRecall,
            SubscribeOAGRecall,
            SubscribeKGRecall,
            SearchRecall,
        ]
        valid_recall_classes = []
        for recall_class in recall_classes:
            if recall_class.__name__ in recall_names:
                valid_recall_classes.append(recall_class)

        for recall_cls in valid_recall_classes:
            recall_count = 0
            recall_obj = recall_cls()
            logger.info("initial recall obj {} for {}".format(recall_cls, uid))
            item_type_items_map = recall_obj.load_data_for_user(user_type, user_id, 100)
            logger.info("load data with recall obj {} for {}".format(recall_cls, uid))
            for _, items in item_type_items_map.items():
                new_items += items
                recall_count += len(items)

            old_rec['rec'] = list(filter(lambda x: x['recall_type'] != recall_obj.recall_type, old_rec['rec']))
            if recall_count <= 0:
                logger.warning("failed to recall any content with {} for {}".format(recall_cls, uid))
            else:
                logger.info("success recall {} content with {} for {}".format(recall_count, recall_cls, uid))

        if len(new_items) > 0:
            old_rec['rec'] += new_items
            old_rec['rec'] = self.merge_duplications(old_rec['rec'], uid, ud)
            old_rec['rec'] = self.resort_recommendations(old_rec['rec'], uid, ud)

        logger.info("ready to save to redis for {}".format(uid))
        zip_data = gzip.compress(json.dumps(old_rec, ensure_ascii=True).encode("utf-8"))
        self.redis_connection.setex(cache_key, Constants.RECOMMENDATION_CACHE_TIME, zip_data)
        logger.info("Done. Save to redis for {}".format(uid))
        return len(new_items)

    def update_keyword_recommendation(self, uid, ud, keyword, **kwargs):
        if not keyword:
            logger.warning("keyword {} from uid {} is none".format(keyword, uid))
            return 0

        current_ts = now().timestamp()
        last_update_ts = self.get_person_keyword_last_update_timestamp(uid, ud, keyword)
        if current_ts - last_update_ts < 3600:
            logger.info("You update uid {}, ud {}, keyword {} too often. The time interval is only {:.2f}. Ignore it".format(
                uid, ud, keyword, current_ts - last_update_ts
            ))
            return 0

        top_papers = self.preload_keyword_recommendations(keyword, uid, ud)
        self.save_person_keyword_last_update_timestamp(uid, ud, keyword)
        return len(top_papers)

    def fetch_non_keyword_recommendations(self, uid, ud, keyword=None, num=100, ab_flag=None):
        candidates = super(AlgorithmNativeUpdate, self).fetch_non_keyword_recommendations(uid, ud, keyword, num, ab_flag)
        tops = MakeTop().fetch()
        new_candidates = self.merge_duplications(tops + candidates)
        return new_candidates


class BehaviorRecall(BaseRecall):

    def __init__(self):
        super(BehaviorRecall, self).__init__(ALGORITHM_NATIVE_MR_NAME)
        self.recall_type = Constants.RECALL_BEHAVIOR
        self.item_types = [self.ITEM_PUB]
        self.download_sources()

    def load_data_for_user(self, user_type, user_id, count=100, keyword=""):
        item_type_items_map = {}
        bar = tqdm(desc="{} load data".format(self.__class__.__name__))
        for item_type in self.item_types:
            # fetch recommendations from remote http uri, save it to redis
            filename = self.get_filename_by_item_type(item_type)
            tmp_path = os.path.join(settings.LOCAL_CACHE_HOME, filename)

            if item_type not in item_type_items_map:
                item_type_items_map[item_type] = []

            with gzip.open(tmp_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        logger.warning("{} is null".format(line))
                        continue
                    bar.update()
                    tmp = json.loads(line)
                    if tmp['user'] != user_id:
                        continue
                    rec = tmp['rec']
                    for i in range(len(rec)):
                        rec[i]['recall_type'] = self.recall_type
                        rec[i]['recall_reason'] = {
                            "zh": rec[i].get('reason_zh', '根据浏览兴趣为你推荐'),
                            "en": rec[i].get('reason_en', 'According to your actions'),
                        }
                        rec[i]['recall_source'] = filename
                        rec[i]['recall_time'] = "{}".format(now())
                    item_type_items_map[item_type] = standard_score(rec)

        return item_type_items_map

    def load_data(self):
        """Download data from GPU server and parse it
        :return:
           dict, set: returns item type 's user's items, the first dict format is
               {
                   item_type: {
                       (user_type, user_id): [
                           {item: str, score: float, type: str, recall_type: str, recall_reason: str}
                       ]
                   }
               }

           the second set format is (user_type, user_id)

           item_type: pub, report, pub_topic
           user_type: ud or uid
        """
        item_type_user_items_map = {}
        users = set()  # set of (user_type, user_id)

        bar = tqdm(desc="{} load data".format(self.__class__.__name__))
        for item_type in self.item_types:
            # fetch recommendations from remote http uri, save it to redis
            filename = self.get_filename_by_item_type(item_type)
            tmp_path = os.path.join(settings.LOCAL_CACHE_HOME, filename)

            item_type_user_items_map[item_type] = {}
            with gzip.open(tmp_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        logger.warning("{} is null".format(line))
                        continue
                    bar.update()
                    tmp = json.loads(line)
                    users.add((tmp['user_type'], tmp['user']))
                    rec = tmp['rec']
                    for i in range(len(rec)):
                        rec[i]['recall_type'] = self.recall_type
                        rec[i]['recall_reason'] = {
                            "zh": rec[i].get('reason_zh', '根据浏览兴趣为你推荐'),
                            "en": rec[i].get('reason_en', 'According to your actions'),
                        }
                        rec[i]['recall_source'] = filename
                        rec[i]['recall_time'] = "{}".format(now())
                    item_type_user_items_map[item_type][(tmp['user_type'], tmp['user'])] = standard_score(rec)

        return item_type_user_items_map, users

    def download_sources(self):
        for item_type in self.item_types:
            # fetch recommendations from remote http uri, save it to redis
            filename = self.get_filename_by_item_type(item_type)
            tmp_path = os.path.join(settings.LOCAL_CACHE_HOME, filename)
            if os.path.exists(tmp_path) is False or settings.DEBUG is False:
                url = "{}/{}".format(settings.GPU_NON_KEYWORD_RESULT_URL, filename)
                r = requests.get(url)
                if r.status_code != 200:
                    logger.warning("{} not found: {}".format(url, r.status_code))
                    continue

                with open(tmp_path, "wb", 0) as f:
                    f.write(r.content)
                    #print("write {}".format(tmp_path))

    def get_filename_by_item_type(self, item_type, dt=None):
        if not dt:
            dt = now()
        if item_type == self.ITEM_PUB:
            filename = "cf_{}.json.gz".format(dt.strftime("%Y_%m_%d"))
        elif item_type == self.ITEM_PUB_TOPIC:
            filename = "cf_topic_{}.json.gz".format(dt.strftime("%Y_%m_%d"))
        elif item_type == self.ITEM_REPORT:
            filename = "cf_report_{}.json.gz".format(dt.strftime("%Y_%m_%d"))
        elif item_type == self.ITEM_PERSON:
            filename = "cf_person_{}.json.gz".format(dt.strftime("%Y_%m_%d"))
        else:
            raise ValueError("unknown item type {}".format(item_type))

        return filename


class BehaviorPersonRecall(BehaviorRecall):

    def __init__(self):
        super(BehaviorPersonRecall, self).__init__()
        self.recall_type = Constants.RECALL_BEHAVIOR_PERSON
        self.item_types = [self.ITEM_PERSON]
        self.download_sources()


class RandomPersonRecall(BaseRecall):

    def __init__(self):
        super(RandomPersonRecall, self).__init__()
        self.recall_type = Constants.RECALL_RANDOM_PERSON
        self.item_types = [self.ITEM_PERSON]
        self.active_person_ids = []
        self.agg = Aggregate()
        self.fetch_active_persons()

    def load_data(self):
        return {}

    def load_data_for_user(self, user_type, user_id, count=100, keyword=""):
        """ recall data for one user
        :param user_type:
        :param user_id:
        :param count:
        :param keyword:
        :return:
            {
                item_type: [
                    {item: str, score: float, type: str, recall_type: str, recall_reason: str},
                    ...
                ]
            }
        """
        result = {
            self.ITEM_PERSON: []
        }

        random.shuffle(self.active_person_ids)
        candidates = self.active_person_ids[:count]
        for c in candidates:
            person = self.agg.preload_person(c)
            if not person:
                continue
            if not person['indices']['hindex']:
                continue
            if person['indices']['hindex'] and person['indices']['hindex'] < 10:
                continue
            result[self.ITEM_PERSON].append({
                "item": c,
                "score": person['indices']['hindex'] / 1000,
                "type": self.ITEM_PERSON,
                "recall_type": self.recall_type,
                "recall_reason": {
                    "zh": "该学者最近有新动态",
                    "en": "Maybe the scholar have new updates"
                }
            })

        return result


class SubscribeRecall(BaseRecall):

    def __init__(self):
        super(SubscribeRecall, self).__init__(ALGORITHM_NATIVE_MR_NAME)
        self.recall_type = Constants.RECALL_SUBSCRIBE
        self.agg = Aggregate()
        self.paper_index = PaperIndex()

    def load_data_for_user(self, user_type, user_id, count=50, keyword=""):
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
        if keyword:
            subscribe_keywords = [keyword]
        elif user_type == Constants.USER_UID and is_mongo_id(user_id):
            subscribe_keywords, _ = self.get_user_keywords_and_subject(user_id)
        else:
            return {}

        logger.info("get user subscribe keywords {} for {}".format(subscribe_keywords, user_id))
        if not subscribe_keywords:
            return {}

        # append neighbours
        subscribe_neighbours = []  # list of (subscribe_word, neighbours)
        for subscribe_word in subscribe_keywords:
            neighbours = get_neighbours(subscribe_word)
            subscribe_neighbours.append((subscribe_word, neighbours))
        logger.info("get subscribe neighbours {} for {}".format(subscribe_neighbours, user_id))

        candidates = []
        word_count = max(1, int(count / len(subscribe_keywords)))
        for subscribe_word, neighbours in subscribe_neighbours:
            for word in neighbours + [subscribe_word]:
                pub = {
                    "title": BaseAlgorithmApi.translate_chinese(word),
                }
                try:
                    data = self.paper_index.search_by_dict(pub, word_count, False)
                    logger.info("get {} hits by search {} for {}".format(len(data), pub, user_id))
                except Exception as e:
                    logger.warning("except when search {}: {}".format(pub, e))
                    continue
                for pub_id, score in data:
                    recall_reason = self.pack_recall_reason({
                        'paper_id': pub_id,
                        'keywords': [subscribe_word],
                    })
                    item = {
                        'type': self.ITEM_PUB,
                        'item': pub_id,
                        'score': score,
                        "recall_reason": recall_reason,
                        'recall_type': self.recall_type,
                        'recall_source': "stream",
                        'recall_time': "{}".format(now()),
                    }
                    candidates.append(item)

        candidates = self.merge_duplications(candidates)
        result = {self.ITEM_PUB: candidates}
        logger.info("done. load data for {}".format(user_id))
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
                "zh": "{}领域的{}".format(keywords_text, flag_text_zh),
                "en": "{} Paper in {}".format(flag_text, keywords_text),
            }
        else:
            result = {
                "zh": "{}领域交叉的{}".format(keywords_text, flag_text_zh),
                "en": "{} Paper both in {}".format(flag_text, keywords_text),
            }

        return result


class SubscribeKGRecall(BaseRecall):

    def __init__(self):
        super(SubscribeKGRecall, self).__init__()
        self.recall_type = Constants.RECALL_SUBSCRIBE_KG
        self.keyword_paper_ids_map = {}
        self.preload_knowledge()
        self.agg = Aggregate()

    def preload_knowledge(self):
        url = settings.RECALL_DATA_URL + "/meta/subscribe_children_kg/subscribe_children_kg.json"
        r = requests.get(url)
        if r.status_code != 200:
            logger.warning("{} is not ok".format(url))
            return
        lines = r.text.split("\n")
        for line in lines:
            if not line:
                continue
            self.keyword_paper_ids_map.update(json.loads(line))

    def load_data_for_user(self, user_type, user_id, count=50, keyword=""):
        if keyword:
            subscribe_keywords = [keyword]
        elif user_type == Constants.USER_UID and is_mongo_id(user_id):
            subscribe_keywords, _ = self.get_user_keywords_and_subject(user_id)
        else:
            return {}

        if not subscribe_keywords:
            return {}

        candidates = []
        word_count = max(1, int(count / len(subscribe_keywords)))
        for keyword in subscribe_keywords:
            keyword_en = self.translate_chinese(keyword)
            paper_ids = self.keyword_paper_ids_map.get(keyword_en, [])
            random.shuffle(paper_ids)
            for pub_id in paper_ids[:word_count]:
                recall_reason = self.pack_recall_reason({
                    'paper_id': pub_id,
                    'keywords': [keyword],
                })
                item = {
                    'type': self.ITEM_PUB,
                    'item': pub_id,
                    'score': 0.1,
                    "recall_reason": recall_reason,
                    'recall_type': self.recall_type,
                    'recall_source': "stream",
                    'recall_time': "{}".format(now()),
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


class SubscribeOAGRecall(BaseRecall):

    def __init__(self):
        super(SubscribeOAGRecall, self).__init__(ALGORITHM_NATIVE_MR_NAME)
        self.recall_type = Constants.RECALL_SUBSCRIBE_OAG
        self.agg = Aggregate()
        self.item_types = [self.ITEM_PUB]
        self.keyword_paper_ids_map = {}  # keyword is lowercase
        self.preload_data()

    def preload_data(self):
        filename = self.get_filename_by_item_type(self.ITEM_PUB)
        url = settings.RECALL_DATA_URL + "/meta/subscribe_oag/" + filename
        r = requests.get(url)
        if r.status_code != 200:
            logger.warning("{} not found: {}".format(url, r.status_code))
            return

        for line in r.text.split("\n"):
            if not line:
                continue
            self.keyword_paper_ids_map.update(json.loads(line))

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
                "zh": "{}领域的{}".format(keywords_text, flag_text_zh),
                "en": "{} Paper in {}".format(flag_text, keywords_text),
            }
        else:
            result = {
                "zh": "{}领域交叉的{}".format(keywords_text, flag_text_zh),
                "en": "{} Paper both in {}".format(flag_text, keywords_text),
            }

        return result

    def load_data_for_user(self, user_type, user_id, count=100, keyword=""):
        """ Run in background
        word = BaseAlgorithm.translate_chinese(word)
        :param count:
        :param uid:
        :return:
            dict: returns
            {
                item_type: [
                    {item: str, score: float, type: str, recall_type: str, recall_reason: str},
                    ...
                ]
            }
        """
        if user_type != Constants.USER_UID:
            return {}
        if not self.keyword_paper_ids_map:
            return {}
        subscribe_keywords, _ = self.get_user_keywords_and_subject(user_id)
        if not subscribe_keywords:
            return {}

        candidates = []
        for keyword in subscribe_keywords:
            keyword = keyword.lower()
            keyword_en = self.translate_chinese(keyword)
            papers = self.keyword_paper_ids_map.get(keyword_en)
            if not papers:
                continue

            for paper in papers:
                paper['keywords'] = [keyword]
                item = {
                    'item': paper['paper_id'],
                    'type': self.ITEM_PUB,
                    'score': paper['distance'],
                    "recall_reason": self.pack_recall_reason(paper),
                    'recall_type': self.recall_type,
                    'recall_source': "stream",
                    'recall_time': "{}".format(now())
                }
                candidates.append(item)

        return {self.ITEM_PUB: candidates}

    def get_filename_by_item_type(self, item_type, dt=None):
        if not dt:
            dt = now()
        filename = "subscribe_oag-{}.json".format(dt.strftime("%Y_%m_%d"))
        return filename


class FollowRecall(BaseRecall):

    def __init__(self):
        super(FollowRecall, self).__init__(ALGORITHM_NATIVE_MR_NAME)
        self.recall_type = Constants.RECALL_FOLLOW
        self.item_types = [self.ITEM_PUB]

    def load_data(self):
        """Download data from script server and parse it
        :return:
           dict, set: returns item type 's user's items, the first dict format is
               {
                   item_type: {
                       (user_type, user_id): {
                           {item: str, score: float, type: str, recall_type: str, recall_reason: str}
                       }
                   }
               }

           the second set format is (user_type, user_id)

           item_type: pub, report, pub_topic
           user_type: ud or uid
        """
        item_type_user_items_map = {}
        users = set()

        filename = self.get_filename_by_item_type(None)
        tmp_path = os.path.join(settings.LOCAL_CACHE_HOME, filename)
        if os.path.exists(tmp_path) is False or settings.DEBUG is False:
            url = settings.RECALL_DATA_URL + "/meta/follow_recall/" + filename
            r = requests.get(url)
            if r.status_code != 200:
                logger.warning("{} not found: {}".format(url, r.status_code))
                raise ValueError("{} 's status is not 200".format(url))

            with open(tmp_path, "w") as f:
                f.write(r.text)

            r.close()

        # read local file
        bar = tqdm(desc="FollowRecall load data")
        item_type_user_items_map[self.ITEM_PUB] = {}
        with open(tmp_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    logger.warning("{} is null".format(line))
                    continue
                bar.update()
                try:
                    tmp = json.loads(line)
                except Exception as e:
                    logger.warning("\"{}\" format is invalid, {}".format(line, e))
                    continue

                for user_id, follows in tmp.items():
                    rec = []
                    users.add(('uid', user_id))
                    for follow in follows:
                        papers = follow['papers']
                        person_name_en = follow['name_of_followed_author']
                        person_name_zh = follow['chinese_name_of_followed_author'] or person_name_en

                        for tag, recall_papers in papers.items():
                            if tag == "highly_cited_papers":
                                tag_name = "高引"
                                tag_name_en = "High Cited"
                            else:
                                tag_name = "最新"
                                tag_name_en = "New"
                            for paper in recall_papers:
                                label = paper['label']
                                if label == "cooperation_scholar":
                                    cooper_en = paper['author_name_en']
                                    cooper_zh = paper['author_name_zh'] or cooper_en
                                    recall_reason = {
                                        "zh": f"「{person_name_zh}」的合作学者「{cooper_zh}」发表的{tag_name}论文",
                                        "en": f"{tag_name_en} paper from cooperation scholar 「{person_name_en}」of your followed 「{cooper_en}」"
                                    }
                                elif label == "similar_scholar":
                                    recall_reason = {
                                        "zh": f"「{person_name_zh}」的相似学者发表的{tag_name}论文",
                                        "en": f"{tag_name_en} paper from similar scholar of your followed「{person_name_en}」"
                                    }
                                elif label == "followed_scholar":
                                    recall_reason = {
                                        "zh": f"你关注学者「{person_name_zh}」发表的{tag_name}论文",
                                        "en": f"{tag_name_en} Paper from your Followed Scholar 「{person_name_en}」"
                                    }
                                else:
                                    raise ValueError("unknown label {}".format(label))

                                rec.append({
                                    'item': paper['paper_id'],
                                    'type': Aggregate.ITEM_PUB,
                                    'score': paper['distance'],
                                    'recall_reason': recall_reason,
                                    'recall_type': self.recall_type,
                                    'recall_source': filename,
                                    'recall_time': "{}".format(now())
                                })

                    standard_score(rec)
                    item_type_user_items_map[Aggregate.ITEM_PUB][('uid', user_id)] = rec
        bar.close()
        return item_type_user_items_map, users

    def get_filename_by_item_type(self, item_type, dt=None):
        if not dt:
            dt = now()
        filename = "followed_scholar_recall-{}.json".format(dt.strftime("%Y_%m_%d"))
        return filename


class SubjectRecall(BaseRecall):
    
    def __init__(self):
        super(SubjectRecall, self).__init__(ALGORITHM_NATIVE_MR_NAME)
        self.recall_type = Constants.RECALL_SUBJECT
        self.subject_recommendations_map = {}
    
    def load_data(self):
        """Download data from script server and parse it
        :return:
           dict, set: returns item type's user's items.

           The first dict format is
               {
                   item_type: {
                       (user_type, user_id): [
                           {item: str, score: float, type: str, recall_type: str, recall_reason: str}
                       ]
                   }
               }

           The second set format is (user_type, user_id)

           - item_type: pub, report, pub_topic etc.
           - user_type: ud or uid
        """
        users = self.fetch_active_uids()

        item_type_user_items_map = {self.ITEM_PUB: {}}
        for user_type, uid in tqdm(users, desc="{} load data".format(self.__class__.__name__)):
            item_type_items_map = self.load_data_for_user(user_type, uid)
            for item_type, items in item_type_items_map.items():
                item_type_user_items_map[item_type][(user_type, uid)] = items

        return item_type_user_items_map, users

    def load_data_for_user(self, user_type, user_id, count=50, keyword=""):
        """ Run in background
        :param user_type:
        :param user_id:
        :param count:
        :param keyword: subject
        :return:
            dict: returns
            {
                item_type: [
                    {item: str, score: float, type: str, recall_type: str, recall_reason: str},
                    ...
                ]
            }
        """
        subject = keyword
        if not subject and user_type == Constants.USER_UID:
            _, subject = self.get_user_keywords_and_subject(user_id)
        if not subject:
            return {}

        if subject in self.subject_recommendations_map:
            return self.subject_recommendations_map[subject]

        paper_index = PaperIndex()
        subject_keywords = get_subject_keywords(subject)
        if not subject_keywords:
            subject_keywords.append(subject)

        items = []
        word_count = max(1, int(count / len(subject_keywords)))
        for word in subject_keywords:
            pub = {"title": word}
            try:
                data = paper_index.search_by_dict(pub, word_count, False)
            except Exception as e:
                logger.warning("failed to search {}: {}".format(pub, e))
                return {}

            for pub_id, score in data:
                items.append({
                    'type': self.ITEM_PUB,
                    'item': pub_id,
                    'item_type': self.ITEM_PUB,
                    "recall_reason": {
                        "zh": "「{}」学科优质论文".format(subject),
                        "en": "「{}」 Subject Good Paper".format(subject)
                    },
                    'recall_type': self.recall_type,
                    'recall_source': "stream",
                    'recall_time': "{}".format(now()),
                    'score': score,
                })

        result = {self.ITEM_PUB: items}
        # cache subject
        self.subject_recommendations_map[subject] = result
        return result


class EditorHotRecall(BaseRecall):
    """Run realtime
    """
    def __init__(self, prev_days=1):
        super(EditorHotRecall, self).__init__(ALGORITHM_NATIVE_MR_NAME)
        self.recall_type = Constants.RECALL_EDITOR_HOT
        end = now()
        start = end - datetime.timedelta(prev_days)
        self.hot_papers = list(HotPaper.objects.filter(create_at__range=(start, end), is_top=False).all())
        self.pub_id_paper_map = {x.pub_id: x for x in self.hot_papers}
        self.hot_pub_ids = [x.pub_id for x in self.hot_papers]
        self.agg = Aggregate()
        self.pub_id_score_map = {}
        self.pub_id_num_viewed_map = {}
        for pub_id in self.hot_pub_ids:
            num_viewed = self.agg.fetch_pub_num_viewed(pub_id, False)
            if num_viewed is not None:
                self.pub_id_num_viewed_map[pub_id] = num_viewed
            else:
                self.pub_id_num_viewed_map[pub_id] = 0
            score = 1 - 1.0 / math.exp(math.log(num_viewed + 2))
            self.pub_id_score_map[pub_id] = score
        self.hot_pub_id_scores = sorted(self.pub_id_score_map.items(), key=lambda x: x[1], reverse=True)

    def load_data_for_user(self, user_type, user_id, count=50, keyword=""):
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
        if not self.hot_pub_ids:
            return {}

        hots = self.hot_pub_id_scores[:count]
        items = []
        for hot in hots:
            pub_id = hot[0]
            score = hot[1]
            paper = self.pub_id_paper_map[pub_id]

            item = {
                'type': self.ITEM_PUB,
                'item': pub_id,
                "recall_reason": {
                    "zh": "AI预测高引论文",
                    "en": "AI predicts highly cited papers"
                },
                'recall_type': self.recall_type,
                'recall_source': "stream",
                'recall_time': "{}".format(now()),
                'score': score,
                'interpret': paper.interpret,
                'interpret_author': paper.interpret_author,
                'report_id': paper.report_id,
                'report_title': paper.report_title,
                'report_date': paper.report_date.strftime(Constants.SQL_DATE_FORMAT) if paper.report_date else "",
                'report_from': paper.report_from,
            }
            items.append(item)

        return {self.ITEM_PUB: items}


class HotRecall(BaseRecall):
    """Hot paper recall
    """
    def __init__(self):
        super(HotRecall, self).__init__(ALGORITHM_NATIVE_MR_NAME)
        self.recall_type = Constants.RECALL_HOT
        self.latest_24h = {}  # paper_id: count
        self.latest_24h_rank = {}  # paper_id: rank
        self.latest_days = 30
        self.top_pubs = []  # list of (pub_id, score)
        self.top_n = 100
        self.initial()

    def initial(self):
        sql = """
            SELECT
              pub_ids,
              sum(click)
            FROM 
              recsys_actionlog_of_all
            WHERE
              create_at > %s and "action"=2 and "type"=1
            group BY
              pub_ids
        """
        # db.connections.close_all()
        start_time = timezone.now() - datetime.timedelta(self.latest_days)
        with db.connection.cursor() as cursor:
            cursor.execute(sql, [start_time.strftime(Constants.SQL_DATETIME_FORMAT)])
            for row in cursor.fetchall():
                pub_id = row[0]
                count = int(row[1])
                self.latest_24h[pub_id] = count

        pub_counts = self.latest_24h.items()
        pub_counts = sorted(pub_counts, key=lambda x: x[1], reverse=True)
        self.top_pubs = pub_counts[:self.top_n]
        for i, item in enumerate(pub_counts):
            pub_id = item[0]
            self.latest_24h_rank[pub_id] = i + 1

    def load_data_for_user(self, user_type, user_id, count=50, keyword=""):
        """ Run in background
        :param uid:
        :param count:
        :return:
            dict: returns
            {
                item_type: [
                    {item: str, score: float, type: str, recall_type: str, recall_reason: str},
                    ...
                ]
            }
        """
        items = []
        for pub_id, i in self.top_pubs[:count]:
            item = {
                'type': self.ITEM_PUB,
                'item': pub_id,
                'recall_reason': self.pack_recall_reason(pub_id),
                'recall_type': self.recall_type,
                'recall_source': "stream",
                'recall_time': "{}".format(now()),
                'score': 1 - i / count,
            }
            items.append(item)
        standard_score(items, 'score')
        return {self.ITEM_PUB: items}

    def pack_recall_reason(self, pub_id):
        """
        :return: returns {zh: '', en: ''}
        """
        en = []
        zh = []

        if self.latest_24h_rank[pub_id] > 0:
            en.append("Top {} viewed papers in latest {} days".format(self.top_n, self.latest_days))
            zh.append("近{}天访问量Top {}".format(self.latest_days, self.top_n))

        return {'en': ", ".join(en), "zh": ", ".join(zh)}


class SearchRecall(BaseRecall):
    """Use user latest 100 search history to recall paper
    """
    def __init__(self):
        super(SearchRecall, self).__init__(ALGORITHM_NATIVE_MR_NAME)
        self.recall_type = Constants.RECALL_SEARCH
        self.paper_index = PaperIndex()
        self.history_count = 10

    def load_data_for_user(self, user_type, user_id, count=50, keyword=""):
        """ Get data for user
        :param user_type:
        :param user_id:
        :param count:
        :param keyword: default is empty
        :return:
            dict: returns
            {
                item_type: [
                    {item: str, score: float, type: str, recall_type: str, recall_reason: str},
                    ...
                ]
            }
        """
        if user_type != Constants.USER_UID or not is_mongo_id(user_id):
            return {}
        # get user latest
        queries = self.get_user_search_history(user_type, user_id)
        if not queries:
            logger.warning("uid {} don't have any search history".format(user_id))
            return {self.ITEM_PUB: []}

        result = []
        query_count = max(1, int(count / len(queries)))
        for query_item in queries:
            try:
                pubs = self.paper_index.search_by_dict({'title': BaseAlgorithmApi.translate_chinese(query_item['query'])}, query_count)
            except Exception as e:
                logger.warning("failed to search {}: {}".format(query_item['query'], e))
                continue
            for pub_id, score in pubs:
                item = {
                    'type': self.ITEM_PUB,
                    'item': pub_id,
                    'recall_reason': self.pack_recall_reason(query_item),
                    'recall_type': self.recall_type,
                    'recall_source': "stream",
                    'recall_time': "{}".format(now()),
                    'recall_query': query_item['query'],
                    'score': score * query_item['score'],
                }
                result.append(item)

        if not result:
            logger.warning("Can't recall any for uid {}, queries {}".format(user_id, queries))
            return {self.ITEM_PUB: []}

        return {self.ITEM_PUB: result}

    @classmethod
    def pack_recall_reason(cls, query_info):
        """
        :param query_info: {query: str, score: float, latest_time: datetime}
        :return: {zh: '', en: ''}
        """
        en = []
        zh = []

        time_string_en = {
            'year': '%d year',
            'month': '%d month',
            'week': '%d week',
            'day': '%d day',
            'hour': '%d hour',
            'minute': '%d minute',
        }

        time_string_zh = {
            'year': '%d 年',
            'month': '%d 月',
            'week': '%d 周',
            'day': '%d 天',
            'hour': '%d 时',
            'minute': '%d 分',
        }

        # dt = timezone.make_aware(query_info['latest_time'], timezone=pytz.timezone('Asia/Shanghai'))
        # query = cls.secret_query(query_info['query'], reserve_len=5)
        zh.append("你可能想找这篇文章")
        en.append("Papers you maybe interested in")

        return {'en': ", ".join(en), "zh": ", ".join(zh)}

    @classmethod
    def secret_query(cls, raw, reserve_len=2):
        if len(raw) < reserve_len:
            return raw
        reserve_start = int((len(raw) - reserve_len) / 2)
        reserve_end = reserve_start + reserve_len
        secret = ""
        for i, c in enumerate(raw):
            if reserve_start <= i < reserve_end:
                secret += c
            elif i == reserve_start - 1 or i == reserve_end + 1:
                secret += "*"
            else:
                pass

        return secret

    def get_user_search_history(self, user_type, user_id):
        """ Get user latest N queries
        :param user_type:
        :param user_id:
        :return: list of {query: str, score: float, latest_time: datetime}
        """
        if user_type == Constants.USER_UD:
            query_logs = self.mongo.sort("web", "user_track_log", {'ud': user_id},
                                         sort_condition1=[('tc', -1)], sort_condition2=None, limit=self.history_count)
        elif user_type == Constants.USER_UID:
            query_logs = self.mongo.sort('web', 'user_track_log', {'uid': user_id},
                                         sort_condition1=[('tc', -1)], sort_condition2=None, limit=self.history_count)
        else:
            raise ValueError('user type unknown')

        query_score_map = {}  # {query: {latest_time: datetime, score: float}}
        for query_log in query_logs:
            try:
                pl = json.loads(query_log['pl'])
                if 'query' not in pl:
                    continue
                if isinstance(pl['query'], dict):
                    query = pl['query']['query']
                elif isinstance(pl['query'], str):
                    query = pl['query']
                else:
                    query = None
            except Exception as e:
                logger.warning("'{}' is invalid: {}".format(query_log['query'], e))
                continue

            if not query:
                continue

            #query = self.tidy_query(query)
            if query not in query_score_map:
                query_score_map[query] = {'latest_time': None, 'score': 0.0}

            interval = timezone.now() - timezone.make_aware(query_log['tc'])
            score = math.exp(-math.sqrt(interval.total_seconds() / 60))
            query_score_map[query]['score'] += score
            if query_score_map[query]['latest_time'] is None:
                query_score_map[query]['latest_time'] = query_log['tc']
            elif query_score_map[query]['latest_time'] < query_log['tc']:
                query_score_map[query]['latest_time'] = query_log['tc']
            else:
                pass

        if user_type == Constants.USER_UID:
            search_logs = ActionLog.objects.filter(action=ActionLog.ACTION_SEARCH, uid=user_id).order_by("-id")[:self.history_count]
            for search_log in search_logs:
                if not search_log.query:
                    continue
                #query = self.tidy_query(search_log.query)
                query = search_log.query.strip()
                if query not in query_score_map:
                    query_score_map[query] = {'latest_time': None, 'score': 0.0}

                interval = timezone.now() - search_log.create_at
                score = math.exp(-math.sqrt(interval.total_seconds() / 60))
                query_score_map[query]['score'] += score

        result = sorted(query_score_map.items(), key=lambda x: x[1]['score'], reverse=True)
        result = [{'query': x[0], 'score': x[1]['score'], 'latest_time': x[1]['latest_time']} for x in result]
        return result


class AI2KRecall(BaseRecall):
    
    def __init__(self):
        super(AI2KRecall, self).__init__(ALGORITHM_NATIVE_MR_NAME)
        self.default_keyword = "default"
        self.word_ai2k_map = {}  # {word: [ai2k_id]}
        with open(os.path.join(os.path.dirname(__file__), "word_ai2k.json")) as f:
            self.word_ai2k_map = json.load(f)
        logger.info(f"word ai2k keys {len(self.word_ai2k_map)}")
        self.active_person_ids = set(self.fetch_active_persons())
        self.id_ai2k_map = {}
        self.ai2k_packages = self.mongo.find("aminer_rank", "recommend_record")
        for i in range(len(self.ai2k_packages)):
            p = self.ai2k_packages[i]
            self.ai2k_packages[i]['active'] = len(set(p['person_ids']) & self.active_person_ids)
            self.id_ai2k_map[str(p['_id'])] = p
        self.recall_type = Constants.RECALL_AI2K

    def load_data_for_user(self, user_type, user_id, count=20, keyword=""):
        """ Get data for user
        :param user_type:
        :param user_id:
        :param count:
        :param keyword: default is empty
        :return:
            dict: returns
            {
                item_type: [
                    {item: str, score: float, type: str, recall_type: str, recall_reason: str},
                    ...
                ]
            }
        """
        if user_type != Constants.USER_UID:
            return {}

        words, _ = self.get_user_keywords_and_subject(user_id)
        if not words:
            return {}

        result = {self.ITEM_AI2K: []}
        for word in words:
            word = word.strip().lower()
            if word in self.word_ai2k_map:
                ai2k_ids = self.word_ai2k_map[word]
            else:
                ai2k_ids = self.word_ai2k_map[self.default_keyword]
            logger.info(f"'{word}' have {len(ai2k_ids)} ai2k ids")
            if not ai2k_ids:
                continue

            for ai2k_id in ai2k_ids:
                p = self.id_ai2k_map.get(ai2k_id)
                if not p:
                    logger.info("ai2k id {} not found".format(ai2k_id))
                    continue

                if p['active'] <= 0:
                    continue
                if len(p['person_ids']) == 0:
                    continue
                person_ids = set(p['person_ids']) & self.active_person_ids

                item = {
                    'item': str(p['_id']),
                    'score': len(person_ids) / len(p['person_ids']),
                    'type': self.ITEM_AI2K,
                    'recall_type': self.recall_type,
                    'recall_reason': {
                        'zh': p['reason_zh'],
                        'en': p['reason_en'],
                    },
                    'url': p['url']
                }
                result[self.ITEM_AI2K].append(item)

        random.shuffle(result[self.ITEM_AI2K])
        result[self.ITEM_AI2K] = result[self.ITEM_AI2K][:count]
        return result


class ColdAI2KRecall(BaseRecall):

    def __init__(self):
        super(ColdAI2KRecall, self).__init__()
        self.recall_type = Constants.RECALL_COLD_AI2K
        self.filename = self.get_filename_by_item_type(None)
        self.url = settings.RECALL_DATA_URL + "/meta/cold/{}".format(self.filename)
        self.recommendations = None
        self.preload()

    def preload(self):
        r = requests.get(self.url)
        if r.status_code != 200:
            logger.warning("{} status code is not 200, {}".format(self.url, r.status_code))
            return

        self.recommendations = r.json()['rec']
        print("recommendations {}".format(len(self.recommendations)))

    def load_data_for_user(self, user_type, user_id, count=200, keyword=""):
        candidates = []
        for item in self.recommendations:
            if item['recall_type'] != self.recall_type:
                continue
            r = {
                'type': item['type'],
                'item': item['item'],
                'score': 0.1,
                "recall_reason": item.get('recall_reason', {'zh': '', 'en': ''}),
                'recall_type': self.recall_type,
                'recall_source': self.filename,
                'recall_time': "{}".format(timezone.now()),
            }
            candidates.append(r)
        print("before merge {} candidates {}, recall type {}".format(self.__class__.__name__, len(candidates), self.recall_type))
        candidates = self.merge_duplications(candidates)
        print("after merge {} candidates {}, recall type {}".format(self.__class__.__name__, len(candidates), self.recall_type))
        candidates = self.resort_recommendations(candidates)
        print("{} candidates {}, recall type {}".format(self.__class__.__name__, len(candidates), self.recall_type))
        result = {self.ITEM_PUB: candidates}
        return result

    def get_filename_by_item_type(self, item_type, dt=None):
        return "cold.json"


class ColdSubscribeRecall(ColdAI2KRecall):
    def __init__(self):
        super(ColdSubscribeRecall, self).__init__()
        self.recall_type = Constants.RECALL_COLD_SUBSCRIBE


class ColdSubscribeOAGRecall(ColdAI2KRecall):
    def __init__(self):
        super(ColdSubscribeOAGRecall, self).__init__()
        self.recall_type = Constants.RECALL_COLD_SUBSCRIBE_OAG


class ColdTopRecall(BaseRecall):

    def __init__(self):
        super(ColdTopRecall, self).__init__()
        self.recall_type = Constants.RECALL_COLD_TOP
        self.hots = []
        self.count = 200
        self.preload()

    def preload(self):
        hot_papers = HotPaper.objects.filter(is_top=True).order_by("-id")[:self.count]
        for h in hot_papers:
            self.hots.append(
                MakeTop.hot_paper_to_dict(h)
            )

    def load_data_for_user(self, user_type, user_id, count=200, keyword=""):
        candidates = []
        for h in self.hots:
            item = MakeTop.pack_recommend_item(h)
            item['recall_type'] = self.recall_type
            candidates.append(item)

        candidates = self.merge_duplications(candidates)
        candidates = self.resort_recommendations(candidates)
        result = {self.ITEM_PUB: [], self.ITEM_PUB_TOPIC: []}
        for c in candidates:
            if c['type'] == self.ITEM_PUB:
                result[self.ITEM_PUB].append(c)
            elif c['type'] == self.ITEM_PUB_TOPIC:
                result[self.ITEM_PUB_TOPIC].append(c)
        return result
