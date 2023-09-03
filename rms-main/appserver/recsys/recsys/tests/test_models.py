import json

from django.test import TestCase
from recsys.models import MongoConnection


class TestModels(TestCase):

    def setUp(self) -> None:
        self.mongo = MongoConnection.get_aminer_client()

    def tearDown(self) -> None:
        self.mongo.close()

    def test_find_by_id(self):
        pub_id = "5390877920f70186a0d2ca83"
        items = self.mongo.find_by_id("aminer", "publication", pub_id)
        #print(items)

    def test_find_by_id1(self):
        pub_id = "5eafe7e091e01198d39865d6"
        items = self.mongo.find_by_id("aminer", "publication_dupl", pub_id)
        #print(items)
