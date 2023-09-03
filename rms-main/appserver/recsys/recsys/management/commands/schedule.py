from django.core.management.base import CommandParser
from recsys.error_report_command import ErrorReportingCommand
from recsys.schedule import Schedule
from recsys.algorithms.make_top import MakeTop


class Command(ErrorReportingCommand):
    help = "Run task chain"

    def add_arguments(self, parser: CommandParser):
        pass

    def handle(self, *args, **options):
        scheduler = Schedule()
        # todo: register job
        topper = MakeTop()
        scheduler.register("MakeTop", "train", topper.train)

        scheduler.run()

