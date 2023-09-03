from django.core.management.base import CommandParser
import logging

from recsys.error_report_command import ErrorReportingCommand
from recsys.algorithms.subscribe_stat import SubscribeStat
from recsys.algorithms.base import BaseRecall
from tqdm import tqdm


logger = logging.getLogger(__name__)


class Command(ErrorReportingCommand):
    help = "Subscribe stat update"

    def add_arguments(self, parser:CommandParser):
        pass

    def handle(self, *args, **options):
        success_num = 0
        user_ids = BaseRecall().fetch_active_uids()
        for _, uid in tqdm(user_ids, desc="Train subscribe stat"):
            subscribe_stat = SubscribeStat(uid)
            newly = subscribe_stat.train()
            if newly:
                success_num += 1

        print("Success update {}".format(success_num))



