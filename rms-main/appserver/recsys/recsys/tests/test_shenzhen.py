import gzip
import json
import pprint

from django.test import TestCase
from recsys.algorithms.shenzhen import AlgorithmShenzhenUpdate


class TestShenzhenUpdate(TestCase):

    def setUp(self) -> None:
        super(TestShenzhenUpdate, self).setUp()
        self.updator = AlgorithmShenzhenUpdate()

    def test_train(self):
        self.updator.train()

