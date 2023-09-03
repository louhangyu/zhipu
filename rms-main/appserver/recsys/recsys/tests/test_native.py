import gzip
import json
import pprint

from django.test import TestCase
from recsys.algorithms.native import AlgorithmNativeUpdate, AlgorithmNativeApi, SearchRecall, RandomPersonRecall, \
    AI2KRecall, EditorHotRecall
from recsys.algorithms.constants import Constants
from recsys.models import HotPaper


class TestNative(TestCase):

    def setUp(self) -> None:
        super(TestNative, self).setUp()
        self.api = AlgorithmNativeApi()
        self.update = AlgorithmNativeUpdate()

    def test_fetch_keyword_recommendation(self):
        keyword = "machine learning"
        result = self.api.fetch_keyword_recommendations(None, None, keyword)
        self.assertGreater(len(result), 0)

    def test_train(self):
        self.update.train()


class TestSearchRecall(TestCase):

    def setUp(self) -> None:
        super(TestSearchRecall, self).setUp()
        self.recall_obj = SearchRecall()

    def test_load_data_for_user(self):
        uid = "61910b9ab3a197f775722e8b"
        data = self.recall_obj.load_data_for_user(Constants.USER_UID, uid)
        print(data)
        self.assertGreater(len(data), 0)
        self.assertGreater(len(data[self.recall_obj.ITEM_PUB]), 0)

    def test_get_user_search_history(self):
        uid = "61910b9ab3a197f775722e8b"
        data = self.recall_obj.get_user_search_history(Constants.USER_UID, uid)
        print(data)
        self.assertGreater(len(data), 0)

    def test_secret_query(self):
        raw = "machine learning"
        reserve_len = 2
        secret = self.recall_obj.secret_query(raw, reserve_len)
        print("secret is {}".format(secret))
        star_count = list(secret).count("*")
        self.assertEqual(star_count, 2)


class TestRandomPersonRecall(TestCase):
    def setUp(self) -> None:
        super(TestRandomPersonRecall, self).setUp()
        self.recall_obj = RandomPersonRecall()

    def test_load_data_for_user(self):
        data = self.recall_obj.load_data_for_user(None, None)
        print(data)
        self.assertGreater(len(data), 0)
        self.assertGreater(len(data[Constants.ITEM_PERSON]), 0)


class TestAI2KRecall(TestCase):
    def setUp(self) -> None:
        super(TestAI2KRecall, self).setUp()
        self.recall_obj = AI2KRecall()

    def test_load_data_for_user(self):
        data = self.recall_obj.load_data_for_user(Constants.USER_UID, "62909e0a3248c45650126ce5")
        print(data)
        self.assertGreater(len(data), 0)
        #self.assertGreater(len(data[Constants.ITEM_AI2K]), 0)


class TestEditorHotRecall(TestCase):
    def setUp(self) -> None:
        super(TestEditorHotRecall, self).setUp()
        HotPaper.objects.create(pub_id='64990cd0d68f896efaf85cb2')
        HotPaper.objects.create(pub_id='64990cd0d68f896efaf85d0a')

    def tearDown(self) -> None:
        HotPaper.objects.all().delete()
        return super().tearDown()

    def test_load_data_for_user(self):
        recall_obj = EditorHotRecall()
        print(recall_obj.pub_id_num_viewed_map)
        self.assertGreater(len(recall_obj.hot_pub_id_scores), 0)
        pub_id_num_viewed_list = sorted(recall_obj.pub_id_num_viewed_map.items(), key=lambda x: x[1], reverse=True)
        self.assertGreater(
            recall_obj.pub_id_score_map[pub_id_num_viewed_list[0][0]],
            recall_obj.pub_id_score_map[pub_id_num_viewed_list[1][0]]
        )

        data = recall_obj.load_data_for_user(Constants.USER_UID, "62909e0a3248c45650126ce5")
        print(data)
        self.assertGreater(len(data), 0)