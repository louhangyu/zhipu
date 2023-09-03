from django.test import TestCase

from recsys.algorithms.base import BaseAlgorithm
from recsys.algorithms.redis_connection import RedisConnection


class TestAlgorithmBase(TestCase):

    def setUp(self) -> None:
        super(TestAlgorithmBase, self).setUp()
        self.alg = BaseAlgorithm(RedisConnection.get_default(), "default")

    def test_get_doc_similarity(self):
        doc1 = "data mining"
        doc2 = "Deep Learning-based query-count forecasting using farmers' helpline data"
        similarity = self.alg.get_doc_similarity(doc1, doc2)
        self.assertGreater(similarity, 0)

    def test_preload_keyword_recommendations(self):
        data = self.alg.preload_keyword_recommendations("user behavior", 10, 10)
        print(data)
        self.assertGreater(len(data), 0)

