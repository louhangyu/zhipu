"""Statistics all user's subscribe keywords
"""
import datetime
import json
import logging
import os

from recsys.models import MongoConnection
from recsys.algorithms.redis_connection import RedisConnection
from recsys.algorithms.constants import Constants
from recsys.algorithms.text_similarity import TextSimilarity

from django.utils import timezone
from django.db import connection


logger = logging.getLogger(__file__)


word_graph = None
# with open(os.path.join(os.path.dirname(__file__), "word_table.json")) as f:
    # word_graph = json.load(f)


class SubscribeStat:
    last_days = Constants.PUSH_NEW_DAYS

    def __init__(self, uid, min_similarity=0.01, cache_time=3600*24):
        self.mongo = MongoConnection.get_aminer_client()
        self.redis = RedisConnection.get_default()
        self.uid = uid
        self.subscribe_keywords = []
        self.min_similarity = min_similarity
        self.cache_time = cache_time

    def train(self, save=True):
        self.load_user_subscribe_keywords()
        prev_keyword_newly_map = self.get_newly()
        keyword_newly_map = {}
        for keyword in self.subscribe_keywords:
            if not keyword.strip():
                continue
            last_ts = prev_keyword_newly_map.get(keyword, {}).get("ts")
            try:
                value = self.get_keyword_newly_from_db(keyword, last_ts=last_ts, n=100, min_similarity=self.min_similarity)
            except Exception as e:
                logger.warning("failed to get newly for {}: {}".format(keyword, e))
                continue
            keyword_newly_map[keyword] = value

        if save:
            if keyword_newly_map:
                self.save_to_redis(keyword_newly_map)
            else:
                self.redis.delete(self.get_cache_key())

        return keyword_newly_map

    def save_to_redis(self, data):
        """
        :param data: {keyword: {count: int, example: [str]}}
        :return:
        """
        self.redis.setex(self.get_cache_key(), self.cache_time, json.dumps(data))

    def get_newly(self):
        """ Get newly stat from redis only
        :return: {keyword: {count: int, example: [{'score': float, 'id': str}, ... ], ts: float}}
        """
        raw = self.redis.get(self.get_cache_key())
        if not raw:
            return {}

        tidy = {}
        data = json.loads(raw)
        for keyword, item in data.items():
            ts = timezone.now().fromtimestamp(item['ts'])
            if timezone.make_aware(ts) < timezone.now() - datetime.timedelta(1):
                continue
            tidy[keyword] = item

        return tidy

    def omit_keyword(self, keyword):
        """ Omit keyword stat from redis
        :param keyword: str
        :return:
        """
        data = self.get_newly()
        if keyword in data:
            del data[keyword]

        self.save_to_redis(data)

    def get_cache_key(self):
        return "subscribe_stat_{}".format(self.uid)

    def load_user_subscribe_keywords(self):
        if not self.uid:
            return []
        projection = {'experts_topic': 1}
        users = self.mongo.find_by_id("aminer", "usr", self.uid, projection)
        for user in users:
            if "experts_topic" in user:
                experts_topic = user.get("experts_topic")
                if experts_topic and isinstance(experts_topic, list):
                    for item in experts_topic:
                        if 'input_name' not in item:
                            continue
                        self.subscribe_keywords.append(item['input_name'])

        return self.subscribe_keywords

    @classmethod
    def get_keyword_newly_from_db(cls, keyword, n=20, last_ts=None, min_similarity=0.001):
        """ Get newly count and example from database
        :param keyword: str
        :param n: int, top n
        :param last_ts: last timestamp
        :param min_similarity: float
        :return: {count: int, example: [{id: str, score: float, title: str}]}
        """
        if not last_ts:
            last_ts = timezone.now() - datetime.timedelta(cls.last_days)
        else:
            if isinstance(last_ts, int) or isinstance(last_ts, float):
                last_ts = timezone.make_aware(datetime.datetime.fromtimestamp(last_ts))

        # conditions = [self.word2query(keyword)] + self.get_neighbour_words(keyword)
        conditions = [cls.word2query(keyword)]
        conditions = list(filter(lambda x: x and len(x) > 0, conditions))
        text_query = "to_tsvector(title) @@ to_tsquery('{}')".format(" | ".join(conditions))
        with connection.cursor() as c:
            sql = f"""
                select 
                  id, paper_id, title, abstract, ts
                from 
                  recsys_highqualitypaper
                where
                  {text_query} and ts > %s and year >= %s
                order by ts desc limit {n};
            """
            c.execute(sql, (last_ts, timezone.now().year))
            rows = c.fetchall()
            logger.info("rows {}, sql is {}, params {}".format(len(rows), sql, last_ts))
            result = {
                'original_count': len(rows),
                'count': 0,
                'example': [],
                'ts': last_ts.timestamp(),
            }
            texts = [row[2] for row in rows]
            if texts:
                sim_model = TextSimilarity()
                sim_model.train(texts)
            else:
                sim_model = None
            for i in range(len(rows)):
                row = rows[i]
                title = row[2]
                paper_id = row[1]
                sim = sim_model.get_similarity(keyword, title) if sim_model else min_similarity
                result['example'].append({'id': paper_id, 'score': sim, 'title': title})

            result['example'] = sorted(result['example'], key=lambda x: x['score'], reverse=True)
            result['count'] = len(result['example'])
            return result

    @classmethod
    def get_neighbour_words(cls, word):
        sub_words = []
        for token in word.split(" "):
            if not token.strip():
                continue
            sub_words.append(token)

        neighbours = word_graph.get(" ".join(sub_words))
        if not neighbours:
            return []

        queries = []
        for neighbour in neighbours:
            query = cls.word2query(neighbour['word'])
            if not query:
                continue
            queries.append(query)

        return queries

    @classmethod
    def word2query(cls, word: str) -> str:
        from recsys.algorithms.base import BaseAlgorithm
        word = BaseAlgorithm.translate_chinese(word)

        clean_words = []
        doc = word.split(" ")
        for token in doc:
            if "." in token or ":" in token:
                continue

            clean_words.append(f"\"{token}\"")

        return " <-> ".join(clean_words)
