import json

from django.core.management.base import CommandParser

from recsys.error_report_command import ErrorReportingCommand
from recsys.algorithms.recall_favorite import RecallFavorite


class Command(ErrorReportingCommand):
    help = "Recall favorite update"

    def add_arguments(self, parser:CommandParser):
        """
        :param parser:
        :return:
        """
        parser.add_argument('--mode',
                            type=str,
                            required=False,
                            default="train",
                            help="train|eval. Default is train")

    def handle(self, *args, **options):
        recall_favorite = RecallFavorite()
        if options['mode'] == "train":
            recall_favorite.train()
        elif options['mode'] == "eval":
            recall_favorite.eval()
        else:
            raise ValueError("unknown mode {}".format(mode))

