import datetime
import gzip
import hashlib
import json
import os
import random
import traceback
import numpy as np
from typing import List

import logging
import math
from urllib.parse import quote

from django.utils.timezone import now
from django.utils import timezone
from django.conf import settings
from django import db
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed, wait as wait_futures, FIRST_COMPLETED

from recsys.algorithms.recall_favorite import RecallFavorite
from recsys.models import MongoConnection, ActionLog, HighQualityPaper, ChineseEnglish
from recsys.algorithms.redis_connection import RedisConnection
from recsys.algorithms.constants import Constants
from recsys.ann import PaperIndex, PaperVectorIndex
from recsys.algorithms.subscribe_stat import SubscribeStat
from recsys.utils import is_mongo_id, is_chinese, translate_to_english
from recsys.algorithms import get_sentence_model, get_contriever_model, get_token_model, \
    sentence_model_name, contriever_model_name, get_vector_cosine


logger = logging.getLogger(__name__)


class BaseAlgorithm:
    UD_MAX_NUM_WORDS = 1000
    UD_MAX_NUM_SHOW = Constants.UD_MAX_NUM_SHOW
    ITEM_PUB = Constants.ITEM_PUB
    ITEM_PUB_TOPIC = Constants.ITEM_PUB_TOPIC
    ITEM_PERSON = Constants.ITEM_PERSON
    ITEM_AI2K = Constants.ITEM_AI2K
    ITEM_REPORT = Constants.ITEM_REPORT
    VALID_ITEM_TYPE = Constants.VALID_ITEM_TYPE   # used for download

    def __init__(self, redis_connection: RedisConnection, name: str) -> None:
        """ Algorithm have two part. Part one is online service api. Part two is model update.

        :param redis_connection: redis connection
        :param name (str): algorithm name
        """
        self.redis_connection = redis_connection
        self.mongo = MongoConnection.get_aminer_client()
        self.name = name

    def get_person_cache_key(self, person_id):
        """ Get scholar person object cache key
        :param person_id: str
        :return: str
        """
        return "person_{}".format(person_id)

    def get_person_show_history_key(self, uid: str, ud: str) -> str:
        if uid:
            return "uid_show1_{}".format(uid)
        elif ud:
            ud = self.clean_ud(ud)
            return "ud_show1_{}".format(ud)
        else:
            return ""

    def get_person_show_paper_key(self, uid: str, ud: str, paper_id: str) -> str:
        if uid:
            return "uid_show_paper_{}_{}".format(uid, paper_id)
        elif ud:
            ud = self.clean_ud(ud)
            return "ud_show_paper_{}_{}".format(ud, paper_id)
        else:
            return ""

    def get_person_click_history_key(self, uid: str, ud: str):
        if uid:
            return "uid_click_{}".format(uid)
        elif ud:
            ud = self.clean_ud(ud)
            return "ud_click_{}".format(ud)
        else:
            return ""

    def get_person_click_paper_key(self, uid: str, ud: str, paper_id: str):
        if uid:
            return "uid_click_paper_{}_{}".format(uid, paper_id)
        elif ud:
            ud = self.clean_ud(ud)
            return "ud_click_paper_{}_{}".format(ud, paper_id)
        else:
            return ""

    def get_person_keyword_key(self, uid: str, keyword: str):
        if uid:
            return "{}_keyword_{}_{}".format(self.name, uid, quote(keyword.lower()))
        else:
            return "{}_keyword_{}".format(self.name, quote(keyword.lower()))

    @classmethod
    def clean_ud(cls, ud):
        if not ud:
            return ud
        return ud.replace("-", "_")

    def get_person_show_papers(self, uid, ud) -> list:
        """
        :param uid:
        :param ud:
        :return:
            list((str, int)): return list of (paper_id, count)
        """
        if not uid and not ud:
            return []
        if uid:
            uid_key = self.get_person_show_history_key(uid, None)
            items = self.redis_connection.zrange(uid_key, 0, self.UD_MAX_NUM_SHOW, True, True)
        else:
            items = []

        if not items and ud:
            ud_key = self.get_person_show_history_key(None, ud)
            items = self.redis_connection.zrange(ud_key, 0, self.UD_MAX_NUM_SHOW, True, True)

        for i in range(len(items)):
            items[i] = (items[i][0].decode(), items[i][1])

        return items

    def get_person_click_papers(self, uid, ud) -> list:
        """
        :param uid:
        :param ud:
        :return:
            list((str, int)): return list of (paper_id, count)
        """
        if not uid and not ud:
            return []
        if uid:
            uid_key = self.get_person_click_history_key(uid, None)
            items = self.redis_connection.zrange(uid_key, 0, self.UD_MAX_NUM_SHOW, True, True)
        else:
            items = []

        if not items and ud:
            ud_key = self.get_person_click_history_key(None, ud)
            items = self.redis_connection.zrange(ud_key, 0, self.UD_MAX_NUM_SHOW, True, True)

        for i in range(len(items)):
            items[i] = (items[i][0].decode(), items[i][1])

        return items

    def get_person_keyword_last_update_key(self, uid, ud, keyword):
        """
        :param uid:
        :param ud:
        :param keyword: must have value, not null
        :return:
        """
        if not keyword:
            raise ValueError("keyword is blank")

        if uid:
            return "{}_uid_keyword_last_update_{}_{}".format(self.name, uid, quote(keyword))
        elif ud:
            return "{}_ud_keyword_last_update_{}_{}".format(self.name, ud, quote(keyword))
        else:
            return None

    def get_person_keyword_last_update_timestamp(self, uid, ud, keyword) -> float:
        key = self.get_person_keyword_last_update_key(uid, ud, keyword)
        if not key:
            return 0

        last_ts = self.redis_connection.get(key)
        if not last_ts:
            return 0

        return float(last_ts)

    def save_person_keyword_last_update_timestamp(self, uid, ud, keyword):
        key = self.get_person_keyword_last_update_key(uid, ud, keyword)
        if not key:
            return 0
        ts = int(now().timestamp())
        self.redis_connection.setex(key, 3600, "{}".format(ts))
        return ts

    @classmethod
    def transfer2abflag(cls, ud):
        """ Transfer ud to ab flag.
        :param ud: str
        :return:
            str: Returns a or b
        """
        if not ud:
            return "a"
        s = 1
        for c in ud:
            if c.isdigit():
                s += int(c)
            else:
                s += ord(c)

        if s % 2 == 0:
            return 'a'
        else:
            return 'b'

    def discount_by_show_and_click(self, uid, ud, papers):
        """
        :param uid:
        :param ud:
        :param papers: list of {item: str, type: str, score: float, recall_type: str}
        :return:
            [{}]: returns a list of paper which score is updated
        """
        showed = {k: v for (k, v) in self.get_person_show_papers(uid, ud)}
        clicked = {k: v for (k, v) in self.get_person_click_papers(uid, ud)}
        top_papers = []

        for item in papers:
            # discount by show count
            score = item['score']
            item_id = item['item']
            if item_id in showed:
                decrease_ratio = math.exp(-math.sqrt(showed[item_id] % 100))
                score *= decrease_ratio

            if item_id in clicked:
                decrease_ratio = math.exp(- (clicked[item_id] % 15))
                score *= decrease_ratio

            item.update({'score': score})
            top_papers.append(item)

        if len(top_papers) <= 0:
            logger.warning("failed to fetch recommendation for uid {}, ud {}".format(uid, ud))
            return []

        top_papers = sorted(top_papers, key=lambda x: x['score'], reverse=False)
        recall_type_pubs_map = {}
        for item in top_papers:
            recall_type = item.get('recall_type')
            if recall_type in recall_type_pubs_map:
                recall_type_pubs_map[recall_type].append(item)
            else:
                recall_type_pubs_map[recall_type] = [item]

        if len(recall_type_pubs_map) == 1:
            return top_papers

        # rearrange recommendations
        recall_type_favorite_map = RecallFavorite().predict(uid, ud)
        sorted_recall_types = sorted(list(recall_type_favorite_map.items()), key=lambda x: x[1], reverse=True)
        sorted_recall_types = list(filter(lambda x: x[0] in recall_type_pubs_map, sorted_recall_types))
        result = [None] * len(papers)
        gap = len(sorted_recall_types)
        min_prior = sorted_recall_types[-1][1]
        max_prior = sorted_recall_types[0][1]
        for i, (recall_type, prior) in enumerate(sorted_recall_types):
            for j in range(i, len(result), gap):
                prob = (prior - min_prior) / (max_prior - min_prior + 0.0001)
                # miss
                if random.random() > prob:
                    continue

                if recall_type not in recall_type_pubs_map or len(recall_type_pubs_map[recall_type]) == 0:
                    continue

                result[j] = recall_type_pubs_map[recall_type].pop()
                if len(recall_type_pubs_map[recall_type]) == 0:
                    del recall_type_pubs_map[recall_type]

        # insert left items
        for i, item in enumerate(result):
            if item is not None:
                continue

            j = i % len(recall_type_pubs_map)
            recall_type = list(recall_type_pubs_map.keys())[j]
            if recall_type not in recall_type_pubs_map or len(recall_type_pubs_map[recall_type]) == 0:
                continue
            result[i] = recall_type_pubs_map[recall_type].pop()
            if len(recall_type_pubs_map[recall_type]) == 0:
                del recall_type_pubs_map[recall_type]

        return result

    @classmethod
    def resort_recommendations(cls, items, uid, ud) :
        """ Some invalid recommendations will be removed.
        :param items: list of {item: str, type: str, score: float, recall_type: str, recall_reason: str}
        :param uid:
        :param ud:
        :return:
          [{}]: returns lists of {item: str, type: str, score: float, recall_type: str, recall_reason: str}
        """
        from recsys.algorithms.aggregate import Aggregate
        from recsys.algorithms.hybird_rank import hybird_rank

        agg = Aggregate()
        item_feature_map = {}

        for item in items:
            item_id = item['item']
            item_type = item['type']

            if item_type == cls.ITEM_PUB:
                try:
                    pub = agg.preload_pub(item_id)
                except Exception as e:
                    logger.warning("pub {} failed to preload: {}".format(item_id, e))
                    continue
                if not pub:
                    logger.info("pub {} not found".format(item_id))
                    continue
                feature = {
                    'item': item_id,
                    'type': item_type,
                    'ts': timezone.make_aware(datetime.datetime.strptime(pub.get('ts'), Constants.SQL_DATETIME_FORMAT)) if pub.get('ts') else None,
                    'citation': pub.get('n_citation', 0) or 0,
                    'num_viewed': pub.get('num_viewed', 0) or 0,
                    'district': pub.get('sciq'),
                    'title': pub['title'] or pub.get('title_zh') or "",
                    'abstract': pub.get('abstract') or pub.get('abstract_zh') or '',
                }
            elif item_type == cls.ITEM_PUB_TOPIC:
                pub_topic = agg.preload_pub_topic(item_id)
                if not pub_topic:
                    continue
                feature = {
                    'item': item_id,
                    'type': item_type,
                    'ts': timezone.make_aware(datetime.datetime.strptime(pub_topic.get('ts'), Constants.SQL_DATETIME_FORMAT)) if pub_topic.get('ts') else None,
                    'citation': pub_topic.get('num_like', 0) or 0,
                    'num_viewed': pub_topic.get('num_view', 0) or 0,
                    'district': {},
                    'title': pub_topic['title'] or pub_topic.get('title_zh'),
                    'abstract': pub_topic['content'] or pub_topic.get('content_zh'),
                }
            elif item_type == cls.ITEM_PERSON:
                person = agg.preload_person(item_id)
                if not person:
                    continue
                abstract = ""
                if 'interests' in person:
                    abstract = " ".join([x['t'] for x in person['interests'] if person['interests']])
                feature = {
                    'item': item_id,
                    'type': item_type,
                    'ts': timezone.make_aware(datetime.datetime.strptime(person.get('ts'), Constants.SQL_DATETIME_FORMAT)) if person.get('ts') else None,
                    'citation': person.get('n_citation') or 0,
                    'num_viewed': person.get('n_pubs') or 0,
                    'district': {},
                    'title': person.get('name') or '',
                    'abstract': abstract 
                }
            else:
                continue
            if not feature.get('title') and not feature.get('abstract'):
                continue
            item_feature_map[item_id] = feature

        if not item_feature_map:
            logger.warning("failed to initial item_feature_map, rec count {}".format(len(items)))
            return items

        pub_scores = hybird_rank(uid, ud, list(item_feature_map.values()))
        # update score of item
        for record in pub_scores:
            item_feature_map[record['item']]['score'] = record['score']

        new_recs = []
        for i in range(len(items)):
            item = items[i]
            pub_id = item['item']
            recall_type = item['recall_type']
            old_score = item['score']
            if pub_id not in item_feature_map:
                logger.warning("item {} not in item_feature_map".format(pub_id))
                continue
            if item_feature_map[pub_id].get('score') is None:
                logger.warning("item {} score is none".format(pub_id))
                continue

            if recall_type in [Constants.RECALL_EDITOR_HOT, Constants.RECALL_TOP]:
                old_score_ratio = 1.0
            else:
                old_score_ratio = 0.7

            item['score'] = (1 - old_score_ratio) * item_feature_map[pub_id]['score'] + old_score_ratio * old_score
            new_recs.append(item)
            logger.info("item {}, new score {}, old score {}".format(item_feature_map[pub_id], item['score'], old_score))

        new_recs = sorted(new_recs, key=lambda x: x['score'], reverse=True)
        return new_recs

    @classmethod
    def merge_duplications(cls, recs, uid=None, ud=None):
        """ Merge duplication of recommendation items.
        :param ud:
        :param uid:
        :param recs: list of {item: str, type: str, score: float, recall_type: str, recall_reason: str}
        :return:
          [{}]: returns lists of {item: str, type: str, score: float, recall_type: str, recall_reason: str}
        """
        recall_type_favorite_map = RecallFavorite().predict(uid, ud)
        paper_item_map = {}
        shrinked = []
        for item in recs:
            paper_id = item['item']

            if paper_id in paper_item_map:
                old_prior = recall_type_favorite_map.get(paper_item_map[paper_id]['recall_type'], 0.1)
                prior = recall_type_favorite_map.get(item['recall_type'], 0.1)
                if prior > old_prior:
                    paper_item_map[paper_id] = item
            else:
                paper_item_map[paper_id] = item
                shrinked.append(item)

        return shrinked

    def fetch_keyword_recommendations(self, uid, ud, keyword, num=100, ab_flag=None):
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
            for i, ex in enumerate(keyword_newly_map[keyword]['example']):
                if isinstance(ex, str):
                    paper_id = ex
                    score = 1 - 1.0 / (i + 1)
                else:
                    paper_id = ex['id']
                    score = ex['score']

                candidates.append({
                    'item': paper_id,
                    'type': self.ITEM_PUB,
                    'score': score,
                    'recall_type': Constants.RECALL_SUBSCRIBE,
                    'recall_reason': {
                        'zh': '',
                        'en': ''
                    }
                })

            return candidates

        candidates = self.get_keyword_rec_cache(keyword, uid, ud)
        # try to fetch from common cache
        if not candidates:
            candidates = self.get_keyword_rec_cache(keyword, None, None)

        # re-preload
        if not candidates:
            candidates = self.preload_keyword_recommendations(keyword, uid, ud)

        if not candidates:
            logger.warning("uid {}, ud {}, keyword '{}', don't have any recommendations".format(uid, ud, keyword))
            return []

        candidates = self.discount_by_show_and_click(uid, ud, candidates)
        result = candidates[:num]
        return result

    def preload_keyword_recommendations(self, keyword, uid, ud, paper_num=100):
        """ Preload keyword recommendations and save them to redis.
        :param keyword:
        :param ud:
        :param uid:
        :param paper_num:
        :return: [{item: str, score: float, type: str, recall_type: str}]
        """

        if not keyword:
            logger.warning("keyword {} is none, return []".format(keyword))
            return []
        keyword = self.translate_chinese(keyword)
        candidates = []
        # fetch by search engine
        paper_index = PaperIndex()
        neighbours = SubscribeStat.get_neighbour_words(keyword)
        query_limit = int(paper_num / (2 + len(neighbours)))
        pub_id_scores = paper_index.search_by_dict({"title": keyword}, k=paper_num, debug=True)
        if neighbours:
            for neighbour in neighbours:
                neighbour_pub_id_scores = paper_index.search_by_dict({'title': neighbour}, k=query_limit, debug=True)
                for i in range(len(neighbour_pub_id_scores)):
                    neighbour_pub_id_scores[i] = list(neighbour_pub_id_scores[i])
                    neighbour_pub_id_scores[i][1] = 0.7 * neighbour_pub_id_scores[i][1]
                pub_id_scores += neighbour_pub_id_scores
        for item in pub_id_scores:
            c = {
                'item': item[0],
                'type': self.ITEM_PUB,
                'score': item[1],
                'recall_type': Constants.RECALL_SUBSCRIBE,
                'recall_reason': {
                    'zh': '',
                    'en': ''
                },
                'title': item[2]['title']
            }
            candidates.append(c)

        candidates = self.merge_duplications(candidates)
        candidates = self.remove_not_found_items(candidates)
        if not candidates:
            logger.warning("uid {}, ud {}, after remove items which not found. Candidates are empty".format(uid, ud))
            return []
        # sort by properties
        candidates = self.resort_recommendations(candidates, uid, ud)
        if not candidates:
            logger.warning("uid {}, ud {}, after resort, candidates become empty".format(uid, ud))
            return []
        # sort with vector 
        sims = self.get_docs_similarity(keyword, [c['title'] for c in candidates])
        sim_ratio = 0.2
        for i in range(len(sims)):
            candidates[i]['score'] = sims[i] * sim_ratio + (1 - sim_ratio) * candidates[i]['score']
        # save to redis
        cache_key = self.get_keyword_rec_cache_key(keyword, uid, ud)
        cache_data = gzip.compress(json.dumps(candidates).encode("utf-8"))
        self.redis_connection.setex(cache_key, Constants.KEYWORD_REC_CACHE_TIME, cache_data)

        common_cache_key = self.get_keyword_rec_cache_key(keyword, None, None)
        self.redis_connection.setex(common_cache_key, Constants.KEYWORD_REC_CACHE_TIME, cache_data)
        return candidates

    @classmethod
    def translate_chinese(cls, ch):
        if is_chinese(ch) is False:
            return ch
        logger.info("ready to translate {}".format(ch))
        ch = ch.strip()
        try:
            records = ChineseEnglish.objects.filter(ch=ch)
            if len(records) > 0:
                eng = " ".join([x.eng for x in records])
            else:
                eng = None
        except Exception as e:
            logger.warning("except when query db by ch {}: {}".format(ch, e))
            eng = None

        if eng:
            return eng

        eng, supply = translate_to_english(ch)
        if eng:
            try:
                ChineseEnglish.objects.create(ch=ch, eng=eng, translator=supply)
            except Exception as e:
                logger.warning("except when save ({}, {}): {}".format(ch, eng, e))
            logger.info("translate {} to {}".format(ch, eng))
            return eng

        return ch

    def get_similar_papers_by_keyword_and_oagbert(self, keyword, timeout=0.5, limit=50, last_days=365):
        """ Search milvus
        :param keyword: str
        :param timeout: float, unit is microsecond
        :param limit:
        :param last_days:
        :return: [{item: str, score: float}]
        """
        vector_index = PaperVectorIndex()
        result = vector_index.search(keyword, timeout, limit, last_days=last_days)
        return result

    def get_non_keyword_rec_cache_key(self, uid, ud):
        if uid and uid != "":
            return "{}_non_keyword_rec_uid_{}".format(self.name, uid)
        elif ud and ud != "":
            return "{}_non_keyword_rec_ud_{}".format(self.name, ud)
        else:
            return "{}_non_keyword_rec_cold".format(self.name)

    def get_non_keyword_rec_cache(self, uid, ud):
        """
        :param uid:
        :param ud:
        :return: returns
            {
                user_type: str
                user: str,
                rec: [
                    {item_id: str, item_type: str, score: float, recall_type: str, recall_reason: str}
                ]
            }
        """
        cache_key = self.get_non_keyword_rec_cache_key(uid, ud)
        zip_data = self.redis_connection.get(cache_key)
        if not zip_data:
            return None

        return json.loads(gzip.decompress(zip_data))

    @classmethod
    def get_keyword_rec_cache_key(cls, keyword, uid, ud):
        keyword = keyword.strip().lower()
        sub_words = [x.strip() for x in keyword.split(" ") if x.strip()]
        sub_words = sorted(sub_words)
        sub_words_hash = hashlib.md5("_".join(sub_words).encode("utf-8")).hexdigest()
        if uid:
            key = "keyword_rec_uid_{}_{}".format(uid, sub_words_hash)
        elif ud:
            key = "keyword_rec_ud_{}_{}".format(ud, sub_words_hash)
        else:
            key = "keyword_rec_{}".format(sub_words_hash)

        return key

    def get_keyword_rec_cache(self, keyword, uid, ud):
        """ Get keyword recommendations from redis only
        :param keyword: str
        :return: [{item: str, score: float, type: str, recall_type: str}, ...]
        """
        cache_key = self.get_keyword_rec_cache_key(keyword, uid, ud)
        raw = self.redis_connection.get(cache_key)
        if not raw:
            return []

        unzipped = gzip.decompress(raw)
        return json.loads(unzipped)

    def fetch_non_keyword_recommendations(self, uid, ud, keyword=None, num=100, ab_flag=None):
        """
        :param uid:
        :param ud:
        :param keyword: unused
        :param num:
        :param ab_flag:
        :return: [{item: str, type: str, score: float, recall_type: str, recall_reason: str}]
        """
        cache_key = self.get_non_keyword_rec_cache_key(uid, ud)
        raw = self.redis_connection.get(cache_key)
        if not raw or not json.loads(gzip.decompress(raw)):
            cold_cache_key = self.get_non_keyword_rec_cache_key(None, None)
            raw = self.redis_connection.get(cold_cache_key)

        if not raw:
            logger.warning("can't get any recommendation for uid {}, ud {}, ab flag {}".format(uid, ud, ab_flag))
            return []

        data = json.loads(gzip.decompress(raw))
        if not data:
            logger.warning("can't get any recommendation for uid {}, ud {}, ab flag {}, because data is empty".format(uid, ud, ab_flag))
            return []

        """
        if use_cold and ab_flag:
            if ab_flag == "a":
                data['rec'] = list(filter(lambda x: x['recall_type'] in [Constants.RECALL_COLD_AI2K, Constants.RECALL_COLD_SUBSCRIBE, Constants.RECALL_COLD_SUBSCRIBE_OAG], data['rec']))
            elif ab_flag == "b":
                data['rec'] = list(filter(lambda x: x['recall_type'] in [Constants.RECALL_COLD_TOP], data['rec']))
        """

        # discount
        top_papers = self.discount_by_show_and_click(uid, ud, data['rec'])[:num]
        return top_papers

    def get_user_keywords_and_subject(self, uid):
        """
        :param uid:
        :return:
          ([], str): returns list of subscribe keyword and subject
        """
        if not uid:
            return [], ""

        subscribes = []
        subject = ""
        projection = {'experts_topic': 1, 'subject': 1}
        users = self.mongo.find_by_id("aminer", "usr", uid, projection)
        for user in users:
            if "experts_topic" in user:
                experts_topic = user.get("experts_topic")
                if experts_topic and isinstance(experts_topic, list):
                    for item in experts_topic:
                        if 'input_name' not in item:
                            continue
                        subscribes.append(item['input_name'])
            if 'subject' in user:
                subject = user['subject'] or ""

        logger.info("uid {}, keywords {}, subject {}".format(uid, subscribes, subject))
        return subscribes, subject

    @classmethod
    def get_doc_similarity(cls, text1: str, text2: str) -> float:
        """ Use transformer to get texts similarity
        :param text1: str
        :param text2: str
        :return: float, the similarity of two texts
        """
        if not text1.strip() or not text2.strip():
            return 0.0
        emb1 = PaperVectorIndex._get_text_vector(text1)
        emb2 = PaperVectorIndex._get_text_vector(text2)
        sim = get_vector_cosine(emb1, emb2)
        return sim

    @classmethod
    def get_docs_similarity(cls, text1: str, text2_list: List[str]) -> List[float]:
        """ Computer docs similarity
        :param text1: str
        :param text2_list: [str]
        :return: [], list of similarity
        """
        text1_emb = PaperVectorIndex._get_text_vector(text1)
        text2_embs = PaperVectorIndex._get_text_vector(text2_list)
        sims = []
        for i in range(len(text2_list)):
            if not text2_embs:
                sim = 0.0
            else:
                text2_emb = text2_embs[i]
                sim = get_vector_cosine(text1_emb, text2_emb)
            sims.append(sim)
        return sims

    def remove_not_found_items(self, items):
        """ Remove items which are not exists in the mongodb publication_dupl collection
        :param items: [{item: str, type: str, ...}, ...]
        :return: [{item: str, type: str, ...}, ...]
        """
        new_items = []
        pub_ids = [x['item'] for x in items if x['type'] == Constants.ITEM_PUB]
        mongo_pubs = self.mongo.find_by_ids("aminer", "publication_dupl", pub_ids)
        mongo_pub_ids = set([str(x["_id"]) for x in mongo_pubs])
        for item in items:
            if item['type'] == Constants.ITEM_PUB:
                if item['item'] not in mongo_pub_ids:
                    logger.warning("pub {} not in publication_dupl collection".format(item['item']))
                    continue
            new_items.append(item)

        return new_items


class BaseAlgorithmApi(BaseAlgorithm):

    def __init__(self, redis_connection:RedisConnection, name, update_class) -> None:
        """ Used to service online http request. It will not have any operations which are too slow.

        :param redis_connection: redis connection
        :param name (str): algorithm name
        """
        super(BaseAlgorithmApi, self).__init__(redis_connection, name)
        self.update_class = update_class

    def ranking(self, uid: str, ud: str = None, num: int = 6, **kwargs) -> dict:
        """[summary]

        Args:
            uid (str): logined user id
            ud (str): JS generated id for anonymous user
            num (int, optional): item count need. Defaults to 50.
            keywords ([], optional):
            exclude_ids:
            first_reaco:
            user_agent:
            alg_flag:
            ab_flag:
        Returns:
            dict: returns recommendations, format is
            {
                data: [
                    {item:str, score:float, type: str, recall_type: str, recall_reason: str},
                    ...
                ],
            }
        """
        from recsys.background import refresh_event_handle

        keyword = " ".join(kwargs.get("keywords", [])).strip()
        exclude_ids = [str(x) for x in kwargs.get('exclude_ids', [])]
        exclude_id_fingers = set(exclude_ids)
        first_reach = kwargs.get('first_reach')
        user_agent = kwargs.get('user_agent')
        ab_flag = kwargs.get("ab_flag")

        # prefetch backend data and update redis
        if uid:
            refresh_event_handle.delay(uid, ud, keyword, first_reach=first_reach, user_agent=user_agent)

        if keyword:
            backend = self.update_class().fetch_keyword_recommendations
        else:
            backend = self.update_class().fetch_non_keyword_recommendations

        try:
            recommendations = backend(uid, ud, keyword, num=num, ab_flag=ab_flag)
        except Exception as e:
            logger.warning("exception when fetch recommendations, uid {}, ud {}, keyword {}, num {}: {}".format(uid, ud, keyword, num, e))
            logger.warning("{}".format(traceback.format_exc()))
            return {"data": [], 'ud': ud}

        data = []
        for _, item in enumerate(recommendations):
            item_id = item['item']
            if item_id in exclude_id_fingers:
                continue
            data.append(item)

        subscribe_newly = {}
        if uid:
            subscribe_newly = SubscribeStat(uid).get_newly()

        return {'data': data, 'meta': {'subscribe_newly': subscribe_newly, 'ab_flag': ab_flag}}


class BaseAlgorithmUpdate(BaseAlgorithm):
    def __init__(self, redis_connection: RedisConnection, name: str) -> None:
        """Used to update model and write predictions to redis. Always run in background.

        :param redis_connection: redis connection
        :param name (str): algorithm name
        """
        super(BaseAlgorithmUpdate, self).__init__(redis_connection, name)
        self.mongo = MongoConnection.get_aminer_client()
        self.non_keyword_recall_classes = []
        self.cold_recall_classes = []
        self.cache_time = 3600*24
        self.cold_cache_time = 3600*24*7

    def predict(self):
        pass

    def train(self, preload_item_use_cache=True):
        """Download data from GPU server, then save them to redis
        :return:
        """
        self.train_non_keyword(preload_item_use_cache)
        self.train_keyword(preload_item_use_cache)

    def train_non_keyword(self, preload_item_use_cache=True):
        from recsys.algorithms.aggregate import Aggregate

        agg = Aggregate()
        recall_classes = self.non_keyword_recall_classes

        cold_rec = self.generate_cold_recommendations()
        print("cold rec {}".format(len(cold_rec)))
        to_preload_items_set = set()
        item_type_user_items_maps = []
        users = set([(Constants.COLD_USER_TYPE, Constants.COLD_USER_ID)])

        def recall_class_train(recall_class):
            return recall_class().train()

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = pool.map(recall_class_train, recall_classes, timeout=3600*8)
            for i, future_result in enumerate(futures):
                (recall_item_type_user_items_map, recall_users) = future_result

                if not recall_item_type_user_items_map:
                    logger.warning("{} do not have result".format(recall_classes[i].__class__.__name__))
                    continue
                item_type_user_items_maps.append(recall_item_type_user_items_map)
                for _, user_items_map in recall_item_type_user_items_map.items():
                    for _, items in user_items_map.items():
                        to_preload_items_set |= set([(x.get('item'), 0, x.get('type'), '') for x in items])
                users |= recall_users

        to_preload_items_set |= set([(x.get('item'), 0, x.get('type'), "") for x in cold_rec])
        self.preload_recommend_items(agg, to_preload_items_set, preload_item_use_cache, False)

        for (user_type, user_id) in tqdm(users, desc="{} update user recommendation".format(self.__class__.__name__)):
            rec = []
            for item_type_user_items_map in item_type_user_items_maps:
                for item_type in self.VALID_ITEM_TYPE:
                    if item_type not in item_type_user_items_map:
                        continue
                    item_type_rec = item_type_user_items_map[item_type].get((user_type, user_id))
                    if not item_type_rec:
                        continue
                    rec += item_type_rec

            if user_type == Constants.COLD_USER_TYPE:
                rec = cold_rec

            uid, ud = None, None
            if user_type == Constants.USER_UD:
                ud = user_id
            elif user_type == Constants.USER_UID:
                uid = user_id

            rec = self.merge_duplications(rec, uid, ud)
            rec = self.resort_recommendations(rec)

            # prepare to save redis
            cache_time = self.cache_time
            uid, ud = None, None
            if user_type == Constants.USER_UD:
                ud = user_id
            elif user_type == Constants.USER_UID:
                uid = user_id
            elif user_type == Constants.COLD_USER_TYPE:
                uid, ud = None, None
                cache_time = self.cold_cache_time
            else:
                raise ValueError("unknown user type {}".format(user_type))
            cache_key = self.get_non_keyword_rec_cache_key(uid, ud)
            # data format is {'user': str, 'user_type': str, 'rec': [{item: str, type: str, score: float}]}
            data = {
                "user": user_id,
                "user_type": user_type,
                "rec": rec,
            }
            zip_data = gzip.compress(json.dumps(data, ensure_ascii=True).encode("utf-8"))
            self.redis_connection.setex(cache_key, cache_time, zip_data)
            logger.info("update cache {}, recommendations {}".format(cache_key, len(rec)))

    def train_keyword(self, preload_item_use_cache=True):
        from recsys.algorithms.aggregate import Aggregate

        agg = Aggregate()
        to_preload_items_set = set()
        active_users = BaseRecall().fetch_active_uids()
        
        def preload_for_uid(item:tuple[str, str]):
            return self.preload_keyword_recommendations(item[0], item[1], None)
       
        with tqdm(desc="Preload keyword recommendations", total=len(active_users)) as bar:
            with ThreadPoolExecutor(max_workers=8) as pool:
                args = []
                for _, uid in active_users:
                    keywords, _ = self.get_user_keywords_and_subject(uid)
                    for keyword in keywords:
                        args.append((keyword, uid))
                
                for candidates in pool.map(preload_for_uid, args, timeout=3600*8):
                    bar.update()
                    to_preload_items_set |= set([(c['item'], 0, c['type'], '') for c in candidates])

        self.preload_recommend_items(agg, to_preload_items_set, preload_item_use_cache, False)

    @classmethod
    def preload_recommend_items(cls, agg, to_preload_items_set, preload_item_use_cache, preload_summary=True):
        if settings.DEBUG:
            return

        to_preload_items_list = list(to_preload_items_set)
        with tqdm(desc="Preload recommend items", total=len(to_preload_items_list)) as bar:
            with ThreadPoolExecutor() as ex:
                futures = [ex.submit(agg.preload_items, [item], preload_item_use_cache) for item in to_preload_items_list]
                for future in as_completed(futures, timeout=3600*4):
                    try:
                        future.result(timeout=15)
                    except Exception as e:
                        logger.warning("load item failed: {}".format(e))
                    finally:
                        bar.update()

        # preload summary
        if preload_summary:
            to_preload_pubs = list(filter(lambda x: x[2] == Constants.ITEM_PUB, to_preload_items_list))
            with tqdm(desc="Preload pub summary {}".format(len(to_preload_pubs))) as bar:
                with ThreadPoolExecutor() as ex:
                    futures = [ex.submit(agg.fetch_pub_summary, item[0]) for item in to_preload_pubs]
                    for future in as_completed(futures, timeout=3600):
                        try:
                            future.result(timeout=30)
                        except Exception as e:
                            logger.warning("load item failed: {}".format(e))
                        finally:
                            bar.update()

    def generate_cold_recommendations(self):
        """ For all cold user
        :return:  returns list of  {item: str, type: str, score: float, recall_type: str, recall_reason: str}
        """
        new_items = []

        for recall_cls in self.cold_recall_classes:
            recall_obj = recall_cls()
            item_type_items_map = recall_obj.load_data_for_user(None, None)
            for _, items in item_type_items_map.items():
                new_items += items

        return new_items


class BaseRecall(BaseAlgorithm):

    def __init__(self, name="base_recall"):
        super(BaseRecall, self).__init__(RedisConnection.get_default(), name)
        self.recall_type = None
        self.item_types = []

    def train(self):
        """Download data from GPU server, preload items
        :return: (dict, set): item type 's user's items, the first dict format is
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
        try:
            item_type_user_items_map, users = self.load_data()
        except Exception as e:
            logger.warning("{} failed to train: {}\n{}".format(self.__class__.__name__, e, traceback.format_exc()))
            return {}, set()

        self.remove_yesterday_files()
        return item_type_user_items_map, users

    def fetch_active_uids(self):
        """ Include uid
        :return: returns set of (user_type, user_id), user_type is uid
        """
        db.connections.close_all()
        end = now()
        start = end - datetime.timedelta(10)
        uids = ActionLog.objects.filter(create_at__range=(start, end)).values_list('uid').distinct()
        result = set()
        for x in uids:
            uid = x[0]
            if is_mongo_id(uid):
                result.add(("uid", uid))
        return result

    def fetch_active_uds(self):
        """ Query users who have not login and visit site at least twice
        :return: returns set of (user_type, user_id), user_type is ud
        """
        db.connections.close_all()
        end = now()
        start = end - datetime.timedelta(7)
        sql = """
        select *
        from
        (
            select 
              ud, 
              count(distinct(DATE(create_at))) as cnt
            from recsys_actionlog
            where 
              create_at > %s and 
              uid is null and
              ud is not null and
              length(ud) > 0
            group by ud
        ) a
        where 
          a.cnt > 3
        """
        result = set()
        with db.connection.cursor() as c:
            c.execute(sql, [start.strftime(Constants.SQL_DATETIME_FORMAT)])
            for row in c.fetchall():
                result.add((Constants.USER_UD, row[0]))
        return result

    def fetch_active_persons(self):
        """Only fetch persons who have action
        :return: [str], list of person_id string
        """
        last_time = timezone.now() - datetime.timedelta(7)
        person_ids = self.mongo.distinct("web", "scholar_paper_pool", "person_id", {"event_date": {"$gt": last_time}})
        if len(person_ids) == 0:
            logger.warning("active persons are empty")
            return []

        return person_ids

    def fetch_users(self):
        """ Include uid and ud
        :return: returns set of (user_type, user_id), user_type is uid or ud
        """
        users = self.fetch_active_uds() | self.fetch_active_uids()
        return users

    def load_data(self):
        item_count = 0
        user_count = 0
        example_uids = []
        users = self.fetch_users()

        item_type_user_items_map = {}
        for user_type, user_id in tqdm(users, desc="{} load data".format(self.__class__.__name__)):
            item_type_items_map = self.load_data_for_user(user_type, user_id)
            if not item_type_items_map:
                continue
            if len(item_type_items_map) == 1:
                _, items = list(item_type_items_map.items())[0]
                if not items:
                    continue
            if len(example_uids) < 2:
                if user_type == Constants.USER_UID:
                    example_uids.append(user_id)
            user_count += 1
            for item_type, items in item_type_items_map.items():
                if item_type not in item_type_user_items_map:
                    item_type_user_items_map[item_type] = {}
                clean_items = self.remove_not_found_items(items)
                item_type_user_items_map[item_type][(user_type, user_id)] = clean_items
                item_count += len(clean_items)

        print("{} load {} items, {} users, example user ids {}".format(self.__class__.__name__, item_count, user_count, example_uids))
        return item_type_user_items_map, users

    def remove_yesterday_files(self):
        for item_type in self.item_types:
            yesterday = now() - datetime.timedelta(1)
            filename = self.get_filename_by_item_type(item_type, yesterday)
            if not filename:
                continue
            yesterday_path = os.path.join(settings.LOCAL_CACHE_HOME, filename)
            if os.path.exists(yesterday_path):
                os.remove(yesterday_path)

    def get_filename_by_item_type(self, item_type, dt=None):
        return ""

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
        return {}
