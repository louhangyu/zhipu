from django.core.management.base import CommandParser
import logging

from recsys.algorithms.native import AlgorithmNativeUpdate
from recsys.algorithms.shenzhen import AlgorithmShenzhenUpdate
from recsys.algorithms.push import AlgorithmPushUpdate
from recsys.error_report_command import ErrorReportingCommand


logger = logging.getLogger(__name__)


class Command(ErrorReportingCommand):
    help = "Algorithm model update"

    def add_arguments(self, parser:CommandParser):
        parser.add_argument('--algorithm',
                            type=str,
                            required=False,
                            default="native",
                            help="You can select native or shenzhen. Default is native")
        parser.add_argument("--mode",
                            type=str,
                            required=False,
                            default="predict",
                            help="You can select train|predict|pipeline")
        parser.add_argument("--without-cache",
                            type=bool,
                            required=False,
                            help="Whether preload items with use cache")

    def handle(self, *args, **options):
        print(options)
        algorithm_name = options['algorithm']
        mode = options['mode']
        not_use_cache = options['without_cache']
        if not_use_cache is None:
            use_cache = True
        else:
            use_cache = False

        print("Use cache {}".format(use_cache))
        if algorithm_name == "native":
            alg = AlgorithmNativeUpdate()
        elif algorithm_name == "shenzhen":
            alg = AlgorithmShenzhenUpdate()
        elif algorithm_name == "push":
            alg = AlgorithmPushUpdate()
        else:
            raise ValueError("Algorithm {} unknown".format(algorithm_name))

        if mode == "train":
            alg.train(use_cache)
        else:
            raise NotImplementedError()

        self.stdout.write(
            self.style.SUCCESS('Successfully update algorithm {} mode {}, use cache {}'.format(algorithm_name, mode, use_cache))
        )
