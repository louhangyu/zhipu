import sys
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger('commands')


class ErrorReportingCommand(BaseCommand):

    def execute(self, *args, **options):
        logger.info('Running command %s' % " ".join(sys.argv))
        try:
            super(ErrorReportingCommand, self).execute(*args, **options)
        except Exception as e:
            logger.error('Management Command Error: %s', ' '.join(sys.argv), exc_info=sys.exc_info(), stack_info=True)
            raise e