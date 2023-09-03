import gzip
import json
import pprint

from django.test import TestCase
from recsys.algorithms.redis_connection import RedisConnection
from recsys.algorithms.aggregate import Aggregate


class TestRedisConnection(TestCase):
    def setUp(self) -> None:
        super(TestRedisConnection, self).setUp()
        self.redis_conn = RedisConnection.get_default()
        self.agg = Aggregate()

    def test_zadd(self):
        pub_id = "123456"
        uid = "111"
        person_show_history_cache_key = self.agg.get_person_show_history_key(uid, None)
        self.redis_conn.delete(person_show_history_cache_key)

        self.agg.redis_connection.zadd(person_show_history_cache_key, {pub_id: 1}, incr=True)
        showed = dict(self.agg.get_person_show_papers(uid, None))
        self.assertEqual(showed[pub_id], 1)

        self.agg.redis_connection.zadd(person_show_history_cache_key, {pub_id: 1}, incr=True)
        showed = dict(self.agg.get_person_show_papers(uid, None))
        self.assertEqual(showed[pub_id], 2)


