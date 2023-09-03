import datetime

from django.core.management.base import BaseCommand
from django.core.management.base import CommandParser
import logging

from recsys.utils import Report
from recsys.error_report_command import ErrorReportingCommand


logger = logging.getLogger(__name__)


class Command(ErrorReportingCommand):
    help = "Push CTR report"

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

        report = Report()
        report.send()
