from django.test import TestCase
import datetime
from django.utils import timezone

from recsys.algorithms.subscribe_stat import SubscribeStat
from recsys.models import HighQualityPaper


class TestSubscribeStat(TestCase):

    def setUp(self) -> None:
        super(TestSubscribeStat, self).setUp()
        self.subscribe_stat = SubscribeStat("5d380271530c7086034c4c58")
        HighQualityPaper.objects.create(
            title="learning machine",
            abstract="lll",
            paper_id="xxss",
            venue="China",
            ts=timezone.now() - datetime.timedelta(hours=4)
        )

    def tearDown(self) -> None:
        super(TestSubscribeStat, self).tearDown()

    def test_get_keyword_newly_from_db(self):
        keyword = "learning"
        last_ts = timezone.now() - datetime.timedelta(7)
        result = self.subscribe_stat.get_keyword_newly_from_db(keyword, last_ts=last_ts.timestamp())
        print(result)
        self.assertIsNotNone(result)
        self.assertGreater(result['count'], 0)
