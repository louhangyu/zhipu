import datetime
import json
import os
import pprint

from django.test import TestCase
from django.utils import timezone
from recsys.ann import PaperIndex, PaperVectorIndex
from recsys.algorithms.constants import Constants


class TestPaperIndex(TestCase):

    def setUp(self) -> None:
        self.paper_index = PaperIndex()

    def test_train(self):
        self.paper_index.train()

    def test_search_by_dict(self):
        data = self.paper_index.search_by_dict({'title': "data mining"}, debug=True)
        pprint.pprint(data)
        self.assertGreater(len(data), 0)


class TestPaperVectorIndex(TestCase):

    def setUp(self) -> None:
        super(TestPaperVectorIndex, self).setUp()
        self.paper_vector_index = PaperVectorIndex()

    def test_search(self):
        keyword = "machine learning"
        res = self.paper_vector_index.search_by_dict({'title': keyword}, debug=True)
        print(res)
        self.assertGreater(len(res), 0)

    def test_get_text_vector(self):
        titles = ['hello', "how are you"]
        embs = self.paper_vector_index._get_text_vector(titles)
        self.assertGreater(len(embs), 0)
