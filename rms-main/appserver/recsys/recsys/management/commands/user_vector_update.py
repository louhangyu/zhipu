import json

from django.core.management.base import CommandParser

from recsys.error_report_command import ErrorReportingCommand
from recsys.algorithms.user_vector import UserVectorTrain


class Command(ErrorReportingCommand):
    help = "User vector update"

    def add_arguments(self, parser:CommandParser):
        """
        :param parser:
        :return:
        """
        parser.add_argument('--n-cluster',
                            type=int,
                            required=False,
                            default=16,
                            help="")
        parser.add_argument('--max-iter',
                            type=int,
                            required=False,
                            default=500,
                            help="")
        parser.add_argument('--random-state',
                            type=int,
                            required=False,
                            default=0,
                            help="")
        parser.add_argument('--mode',
                            type=str,
                            required=False,
                            default="train",
                            help="train|rebuild")

    def handle(self, *args, **options):
        mode = options['mode']
        if mode == 'train':
            model = UserVectorTrain(n_cluster=options["n_cluster"], max_iter=options['max_iter'], random_state=options['random_state'])
            model.train()
        elif mode == 'rebuild':
            model = UserVectorTrain(n_cluster=options["n_cluster"], max_iter=options['max_iter'], random_state=options['random_state'])
            model.rebuild()
        else:
            raise ValueError(f"unknown mode '{mode}'")


