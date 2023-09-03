import gzip
import json
import pprint

from django.test import TestCase
from recsys.models import ActionLog
from recsys.algorithms.constants import Constants
from recsys.algorithms.interest import Interest
from recsys.algorithms.user_vector import UserVectorTrain


class TestInterest(TestCase):

    def setUp(self) -> None:
        super(TestInterest, self).setUp()
        self.uid = "620db182757ab5a1ba7ccb7f"
        self.interest = Interest(Constants.USER_UID, self.uid)
        user_vector_trainer = UserVectorTrain(prev_days=7)
        user_vector_trainer.train_for_uids([self.uid])

    def tearDown(self) -> None:
        super(TestInterest, self).tearDown()

    def test_train(self):
        title = "joint cue let"
        sim = self.interest.get_similarity(title)
        print("sim is {}".format(sim))
        self.assertGreater(sim, 0)

