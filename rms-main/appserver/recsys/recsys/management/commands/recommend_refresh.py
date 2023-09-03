import pprint

from django.core.management.base import CommandParser
import logging
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed, wait as wait_futures, FIRST_COMPLETED

from recsys.algorithms.native import AlgorithmNativeUpdate
from recsys.algorithms.shenzhen import AlgorithmShenzhenUpdate
from recsys.algorithms.push import AlgorithmPushUpdate
from recsys.error_report_command import ErrorReportingCommand
from recsys.algorithms.base import BaseRecall


logger = logging.getLogger(__name__)


class Command(ErrorReportingCommand):
    help = "Algorithm model update"

    def add_arguments(self, parser:CommandParser):
        parser.add_argument('--algorithm',
                            type=str,
                            required=False,
                            default="native",
                            help="You can select native|shenzhen|push. Default is native")
        parser.add_argument("--uid",
                            type=str,
                            required=False,
                            help="A uid or all")

    def handle(self, *args, **options):
        algorithm_name = options['algorithm']
        uid = options['uid']

        if algorithm_name == "native":
            alg = AlgorithmNativeUpdate()
        elif algorithm_name == "shenzhen":
            alg = AlgorithmShenzhenUpdate()
        elif algorithm_name == "push":
            alg = AlgorithmPushUpdate()
        else:
            raise ValueError("Algorithm {} unknown".format(algorithm_name))

        if uid == 'all':
            user_ids = BaseRecall().fetch_active_uids()
            with tqdm(desc="Refresh all user recommends", total=len(user_ids)) as bar:
                with ThreadPoolExecutor() as ex:
                    futures = [ex.submit(alg.update_non_keyword_recommendation, user_id, None) for user_id in user_ids]
                    for future in as_completed(futures, timeout=3600):
                        try:
                            future.result(timeout=30)
                        except Exception as e:
                            logger.warning("refresh recommend failed: {}".format(e))
                        finally:
                            bar.update()

            for _, user_id in user_ids:
                rec = alg.get_non_keyword_rec_cache(user_id, None)
                if not rec:
                    print("uid {} don't have recommends".format(user_id))
                else:
                    print("uid {} recommends {}".format(user_id, len(rec['rec'])))
        else:
            cnt = alg.update_non_keyword_recommendation(uid, None)
            rec = alg.get_non_keyword_rec_cache(uid, None)
            pprint.pprint(rec)
            self.stdout.write(
                self.style.SUCCESS('Successfully refresh {} recommends for uid {}'.format(cnt, uid))
            )

            subscribe_keywords, _ = alg.get_user_keywords_and_subject(uid)
            for keyword in subscribe_keywords:
                alg.update_keyword_recommendation(uid, None, keyword)
                rec = alg.get_keyword_rec_cache(keyword, uid, None)
                pprint.pprint(rec)
                self.stdout.write(
                    self.style.SUCCESS('Successfully refresh {} {} recommends for uid {}'.format(len(rec), keyword, uid))
                )
