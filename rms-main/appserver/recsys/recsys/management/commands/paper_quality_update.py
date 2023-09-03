from django.core.management.base import CommandParser
import logging

from recsys.error_report_command import ErrorReportingCommand
from recsys.algorithms.paper_quality import PaperQuality


logger = logging.getLogger(__name__)


class Command(ErrorReportingCommand):
    help = "Paper quality update"

    def add_arguments(self, parser:CommandParser):
        pass

    def handle(self, *args, **options):
        paper_quality = PaperQuality()
        paper_quality.train()
