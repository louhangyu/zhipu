import gzip
import json
import pprint
import datetime

from django.core.management.base import BaseCommand
from django.core.management.base import CommandParser
import logging

from recsys.algorithms.aggregate import RedisConnection, Aggregate
from recsys.models import MongoConnection

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Push mail preload"

    def add_arguments(self, parser:CommandParser):
        parser.add_argument('--date',
                            type=str,
                            required=False,
                            help="Push date, format yyyy-mm-dd")

    def handle(self, *args, **options):
        date_str = options['date']
        if date_str:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        else:
            date = datetime.datetime.now()

        agg = Aggregate()

        mongo_client = MongoConnection.get_aminer_client()
        sql = {
            "send_time": date.strftime("%Y-%m-%d")
        }
        items = mongo_client.find("tracking", "send_mail_data", sql)
        for item in items:
            print("preload item {}".format(item))
            pub_id = item['_id']
            agg.preload_pub(pub_id, False)

        print("Preload items {}".format(len(items)))
