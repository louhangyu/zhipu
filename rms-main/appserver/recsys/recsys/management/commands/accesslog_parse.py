import datetime
import os
import re

from django.core.mail import send_mail

from recsys.models import AccessLogSnapshot

from django.core.management.base import BaseCommand
from django.core.management.base import CommandParser
from django.utils.timezone import now, localtime
from typing import Dict, List
from recsys.error_report_command import ErrorReportingCommand

import datetime
import logging
import gzip


logger = logging.getLogger(__name__)
regex = "([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+) (\-) (\-) \[(.*)\] \"([A-Z]+) (.*) HTTP/([0-9]\.[0-9])\" ([0-9]+) ([0-9]+) \"(.*)\" \"(.*)\" \"(.*)\" ([0-9]+\.[0-9]+)[,]?.*"
pattern = re.compile(regex)

owners = [
    "xiaotao.peng@aminer.cn",
    "yifan.zhu@aminer.cn",
    "huihui.yuan@aminer.cn"
]


class Command(ErrorReportingCommand):
    BUSINESS_ALL = "all"
    BUSINESS_TOPIC_EMBEDDING = "topic_embedding"
    help = "Access Log Parse"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument('--access-log-dir',
                            type=str,
                            required=False,
                            default="",
                            help="Access log dir")
        parser.add_argument('--access-log',
                            type=str,
                            required=False,
                            default="",
                            help="Access log file")

    def handle(self, *args, **options):
        if options['access_log']:
            access_log = options['access_log']
        else:
            access_log_dir = options['access_log_dir']
            local_last_hour = localtime().now() - datetime.timedelta(hours=1)
            date_dir = "{:02d}/{:02d}/{:02d}/{:02d}.log.gz".format(local_last_hour.year, local_last_hour.month, local_last_hour.day, local_last_hour.hour)
            access_log = os.path.join(access_log_dir, date_dir)

        dj_last_hour = now() - datetime.timedelta(hours=1)
        dj_last_hour = dj_last_hour.replace(minute=0, second=0, microsecond=0)
        all_snapshot = AccessLogSnapshot(
            happen_time=dj_last_hour,
            business=self.BUSINESS_ALL
        )
        topic_embedding_snapshot = AccessLogSnapshot(
            happen_time=dj_last_hour,
            business=self.BUSINESS_TOPIC_EMBEDDING
        )
        samples = {}  # use status code as key, line list as value
        n_success = 0
        n_fail = 0
        line_no = 0
        with gzip.open(access_log, "rb") as f:
            for line in f:
                line_no += 1
                line = line.decode()
                obj = self.extract_accesslog_line(line)
                if not obj:
                    logger.warning("line {} at {} is not recognized.".format(line_no, line))
                    n_fail += 1
                    continue

                n_success += 1
                if obj['status'] != 200:
                    if obj['status'] in samples:
                        samples[obj['status']].append(line)
                    else:
                        samples[obj['status']] = [line]

                # update all
                self.update_snapshot(all_snapshot, obj)

                if obj['path'].find("/get_topic_embedding") > -1:
                    self.update_snapshot(topic_embedding_snapshot, obj)

        self.save_snapshot(all_snapshot)
        self.save_snapshot(topic_embedding_snapshot)

        self.alert_owner([all_snapshot, topic_embedding_snapshot], samples)

        self.stdout.write(
            "Parse {}, success {}, fail {}".format(access_log, self.style.SUCCESS(n_success), self.style.WARNING(n_fail))
        )

    @classmethod
    def extract_accesslog_line(cls, line):
        """
        :param line:
        :return:
        """
        matches = pattern.match(line)
        if not matches:
            return {}

        result = {'ip': matches[1], 'path': matches[6], 'status': int(matches[8]), 'resp_body_bytes': int(matches[9]),
                  'resp_seconds': float(matches[13])}
        return result

    def update_snapshot(self, snapshot: AccessLogSnapshot, obj: Dict):
        """
        :param snapshot: the AccessLogSnapshot object
        :param obj: dict of access log stats
        :return:
        """

        snapshot.total += 1
        if obj['status'] == 200:
            snapshot.status_200_number += 1
        elif obj['status'] >= 500:
            snapshot.status_5xx_number += 1

        snapshot.resp_body_bytes_sum += obj['resp_body_bytes']
        snapshot.resp_seconds_sum += obj['resp_seconds']

    def save_snapshot(self, snapshot):
        AccessLogSnapshot.objects.filter(happen_time=snapshot.happen_time, business=snapshot.business).delete()
        snapshot.save()

    def alert_owner(self, snapshots:List[AccessLogSnapshot], samples:Dict):
        all_5xx = sum([s.status_5xx_number for s in snapshots if s.business == self.BUSINESS_ALL])
        if all_5xx < 10:
            return

        hour_format = "%Y-%m-%d %H"
        title = "RecSys found {} 5xx in {}".format(all_5xx, snapshots[0].happen_time.strftime(hour_format))
        headers = ['Hour', "Total", "200", "5xx", "avgRespByte", "avgRespSecond", "5xxPercentage"]
        content = ""
        for snapshot in snapshots:
            content += "{}\n\n".format(snapshot.business)
            content += "{:20s} {:10s} {:10s} {:10s} {:10s} {:10s} {:10s}\n".format(
                headers[0], headers[1], headers[2], headers[3], headers[4], headers[5], headers[6]
            )

            history = AccessLogSnapshot.objects.filter(business=snapshot.business, happen_time__gt=snapshot.happen_time - datetime.timedelta(hours=24))
            for h in history:
                content += "{:10s} {:10d} {:10d} {:10d} {:>15.4f} {:10.4f} {:10.2f}%\n".format(
                    h.happen_time.strftime(hour_format),
                    h.total,
                    h.status_200_number,
                    h.status_5xx_number,
                    h.avg_resp_byte(),
                    h.avg_resp_second(),
                    h.status_5xx_number * 100 / h.total
                )

            content += "------\n"

        content += "Samples\n\n"
        for status in sorted(list(samples.keys())):
            content += "Status {}: {}\n".format(status, len(samples[status]))
            for line in samples[status][:3]:
                content += line

            content += "---\n"

        send_mail(title, content, from_email=None, recipient_list=owners)
        print(title)
        print(content)


