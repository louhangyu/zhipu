import pprint

from django.core.management.base import BaseCommand
from django.core.management.base import CommandParser
import logging

from recsys.algorithms.aggregate import Aggregate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Get pub venue"

    def add_arguments(self, parser:CommandParser):
        parser.add_argument('--pub',
                            type=str,
                            required=True,
                            help="Publication id")

    def handle(self, *args, **options):
        pub_id = options['pub']
        agg = Aggregate()
        pub = agg.mongo.find_by_id("aminer", "publication_dupl", pub_id)[0]
        venue_raw = pub.get('venue', {}).get('raw', None)
        hbb_id = pub.get("venue_hhb_id")
        venue_info = agg.fetch_pub_venue(venue_raw, hbb_id)
        pprint.pprint(pub)
        print(f"Send: \"{venue_raw}\", \"{hbb_id}\"")
        print(f"Remote response: {venue_info}")
        print(f"Final info: {agg.get_venue_info(pub)}")

