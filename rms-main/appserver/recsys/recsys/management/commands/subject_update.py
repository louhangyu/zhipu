from django.core.management.base import CommandParser
import logging

from recsys.error_report_command import ErrorReportingCommand
from recsys.algorithms.native import subject_en_keywords
from recsys.models import Subject


logger = logging.getLogger(__name__)


class Command(ErrorReportingCommand):
    help = "Subject update"

    def add_arguments(self, parser:CommandParser):
        pass

    def handle(self, *args, **options):
        cols = list(subject_en_keywords.columns)
        for col in cols:
            keywords = list(subject_en_keywords[col])
            keywords = list(set(keywords))
            keywords = list(filter(lambda x: isinstance(x, str) and x, keywords))
            keywords = list(map(lambda x: x.strip(), keywords))
            Subject.objects.create(
                title=str(col),
                keywords=",".join(keywords)
            )
