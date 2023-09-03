from django.test import TestCase
from django.test.client import Client
from django.urls import reverse
import json

from recsys.algorithms.aggregate import Aggregate


class TestViews(TestCase):

    def setUp(self) -> None:
        super(TestViews, self).setUp()
        self.client = Client()
        self.agg = Aggregate()

    def test_recommend_v3(self):
        url = reverse("recommend_v3")
        data = json.dumps([{
            "parameters": {
                "num": 6,
                "exclude_ids": [],
                'keywords': [],
                'uid': '54365d3645ce51fb1bd14f37',
            }
        }])
        resp = self.client.post(url, data, content_type="application/json")

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content.decode())
        print("data {}".format(data))

        self.assertGreater(len(data['data'][0]['data']), 0)

        # whether have ad_human?
        epubs = []
        for item in data['data'][0]['data']:
            # print(item)
            epubs.append(item['e_pub'][0])
        self.assertGreater(len(epubs), 0)

        has_ad_human_type = False
        for item in epubs:
            if item['type'] == self.agg.ITEM_AD_HUMAN:
                has_ad_human_type = True
        self.assertTrue(has_ad_human_type)

    def test_recommend_v3_stream(self):
        url = reverse("recommend_v3")
        body = json.dumps([{
            "parameters": {
                "num": 6,
                "exclude_ids": [],
                'keywords': [],
                'uid': '54365d3645ce51fb1bd14f37',
            }
        }])
        data = {'body': body}
        resp = self.client.get(url, data, content_type="application/json")
        self.assertEqual(resp.status_code, 200)

