import gzip
import json
import pprint

from django.test import TestCase
from recsys.algorithms.aggregate import Aggregate
from recsys.algorithms.native import AlgorithmNativeUpdate
from recsys.algorithms.constants import Constants


class TestAggregateAlgorithm(TestCase):

    def setUp(self) -> None:
        self.agg = Aggregate()

    def test_preload_pub(self):
        # pub_id = "63180bf490e50fcafded73bf"
        pub_id = "53e99784b7602d9701f3e139"
        pub = self.agg.preload_pub(pub_id, use_cache=False)
        pprint.pprint(pub)
        self.assertIsNotNone(pub)
        self.assertIsNotNone(pub['venue'])

    def test_preload_ai2k(self):
        item_id = "62c6973b1a7d9722b5f2c175"
        ai2k = self.agg.preload_ai2k(item_id)
        print(ai2k)
        self.assertIsNotNone(ai2k)
        self.assertGreater(len(ai2k['persons']), 0)

    def test_fetch_pub_num_viewed(self):
        pub_id = "64951856d68f896efa1ef48b"
        num_viewed = Aggregate().fetch_pub_num_viewed(pub_id, False)
        self.assertGreaterEqual(num_viewed, 36)

    def test_fetch_person_num_viewed(self):
        person_id = "53f431badabfaee02ac9803b"
        number = self.agg.fetch_person_num_viewed(person_id)
        print("person {} num viewed {}".format(person_id, number))
        self.assertGreater(number, 13590)

    def test_fetch_pub_venue(self):
        # venue = "International Conference on Learning Representations"
        # venue = "Journal of gastroenterology and hepatology"
        # venue = "Computer Vision and Pattern Recognition"
        # venue = "Journal of Anhui Agricultural Sciences"
        # venue = "BIOSENSORS & BIOELECTRONICS"
        venue = "KDD '22: Proceedings of the 28th ACM SIGKDD Conference on Knowledge Discovery and Data Mining"
        # hbb_id = "5ea1b22bedb6e7d53c00c41b"
        hbb_id = "5eba43d8edb6e7d53c0fb8a1"
        result = Aggregate().fetch_pub_venue(venue, hbb_id)
        print(result)
        self.assertIsNotNone(result['Name'])
        self.assertIsNotNone(result['Short'])

    def test_fetch_sciq(self):
        pub_ids = [
            "5df371de3a55acfd20674ba8",
            "5e3940c73a55ace46ed436d2",
            "60b9a39ce4510cd7c8f934b8",
        ]
        for pub_id in pub_ids:
            data = Aggregate().fetch_sci_q(pub_id)
            print("pub {}, venue tag {}".format(pub_id, data))
            self.assertIsNotNone(data)

    def test_fetch_venue_ids(self):
        subjects = [
            {'id': '6257bcd85aee126c0f422ca3', 'name': '法学'},
            {'id': '6257bcd85aee126c0f422ca4', 'name': 'SOCIOLOGY 社会学'},
        ]

        for subject in subjects:
            data = self.agg.fetch_venue_ids(subject['id'], "1区")
            print("subject {}, data {}".format(subject, data))
            self.assertIsNotNone(data)
            self.assertGreater(len(data), 0)

    def test_fetch_venue_paper_ids(self):
        subjects = self.agg.fetch_subject_category("CJCR", 1)
        for subject in subjects:
            venue_ids = self.agg.fetch_venue_ids(subject['id'], '1区')
            for venue_id in venue_ids:
                data = self.agg.fetch_venue_paper_ids(venue_id, 2021, 2022)
                print(data)
                self.assertIsNotNone(data)
                break
                #self.assertGreater(len(data), 0)

    def test_fetch_person_pub_na(self):
        person_ids = self.agg.fetch_person_pub_na(100, 1000)
        print(person_ids)
        self.assertGreater(len(person_ids), 1000)

    def test_fetch_ai2k_rank(self):
        person_ids = [
            "542bd27edabfae23313f0c1d",
        ]
        agg = Aggregate()
        data = agg.fetch_ai2k_rank(person_ids)
        print(data)
        self.assertIsNotNone(data)

    def test_fetch_jconf_rank(self):
        person_id = '5485d8dddabfae8a11fb2c5b'
        agg = Aggregate()
        data = agg.fetch_jconf_rank(person_id)
        print(data)
        self.assertIsNotNone(data)
        # self.assertEqual(len(data), 1)

    def test_re_rank(self):
        data = self.agg.re_ranking(None, None, 10)
        print(data)
        self.assertIsNotNone(data)

    def test_update_non_keyword_recommendation(self):
        uid = "54365d3645ce51fb1bd14f37"
        updater = AlgorithmNativeUpdate()
        updater.update_non_keyword_recommendation(uid, None)

        key = updater.get_non_keyword_rec_cache_key(uid, None)
        zip_data = self.agg.redis_connection.get(key)
        self.assertIsNotNone(zip_data)
        rec = json.loads(gzip.decompress(zip_data))
        self.assertGreater(len(rec['rec']), 0)

        recall_types = {}
        recall_sources = {}
        for item in rec['rec']:
            if item['recall_type'] in item:
                recall_types[item['recall_type']] += 1
            else:
                recall_types[item['recall_type']] = 1

            if item['recall_source'] in item:
                recall_sources[item['recall_source']] += 1
            else:
                recall_sources[item['recall_source']] = 1

        print("recall types {}, sources {}".format(recall_types, recall_sources))
        self.assertGreater(len(recall_types), 1)
        self.assertTrue("stream" in recall_sources)

    def test_get_user_keywords_and_subject(self):
        uid = "60ee895ba22628d38b7442d4"
        keywords, subject = self.agg.get_user_keywords_and_subject(uid)
        self.assertGreater(len(keywords), 0)
        self.assertEqual(subject, "Mathmatics")

    def test_generate_cold_recommendations(self):
        updater = AlgorithmNativeUpdate()
        recommendations = updater.generate_cold_recommendations()
        self.assertIsNotNone(recommendations)

    def test_discount_by_show_and_click(self):
        pubs = [
            {'item': '1', 'type': 'pub', 'score': 1.2, 'recall_type': Constants.RECALL_SUBJECT},
            {'item': '10', 'type': 'pub', 'score': 1.01, 'recall_type': Constants.RECALL_SUBSCRIBE},
            {'item': '11', 'type': 'pub', 'score': 0.8, 'recall_type': Constants.RECALL_BEHAVIOR},
            {'item': '12', 'type': 'pub', 'score': 0.4, 'recall_type': Constants.RECALL_COLD},
            {'item': '13', 'type': 'pub', 'score': 1.2, 'recall_type': Constants.RECALL_SUBJECT},
            {'item': '14', 'type': 'pub', 'score': 1.0, 'recall_type': Constants.RECALL_SUBJECT},
            {'item': '15', 'type': 'pub', 'score': 1.1, 'recall_type': Constants.RECALL_COLD},
            {'item': '25', 'type': 'pub', 'score': 0.9, 'recall_type': Constants.RECALL_SUBJECT},
            {'item': '21', 'type': 'pub', 'score': 0.5, 'recall_type': Constants.RECALL_BEHAVIOR},
        ]
        result = self.agg.discount_by_show_and_click(None, None, pubs)
        self.assertEqual(len(pubs), len(result))

    def test_fetch_pub_summary(self):
        pub_id = "62b135585aee126c0fa06e15"
        result = self.agg.fetch_pub_summary(pub_id)
        print(result)
        self.assertIsNotNone(result)
