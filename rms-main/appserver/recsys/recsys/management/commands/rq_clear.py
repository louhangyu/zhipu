import os
import re
import django_rq

from django.core.management.base import CommandParser
from django.utils.timezone import now, localtime
from typing import Dict, List
from recsys.error_report_command import ErrorReportingCommand

import datetime
import logging
import gzip


logger = logging.getLogger(__name__)


class Command(ErrorReportingCommand):
    help = "Clear RQ default queue"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument('--queue',
                            type=str,
                            required=False,
                            default="default",
                            help="Queue name")

    def handle(self, *args, **options):
        queue = options['queue']
        q = django_rq.get_queue(queue)
        count = q.empty()
        print("Clear {} from {}".format(count, queue))



