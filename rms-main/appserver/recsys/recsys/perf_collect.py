"""Collect program performance and output to local disk.
"""
import timeit
from django.conf import settings
from django.utils import timezone



class PerfCollect:
    def __init__(self, output):
        self.output = output

    @classmethod
    def default(cls):
        return cls(settings.PERF_COLLECT_OUTPUT)

    def collect(self, file, line_no, fun, *args, **kwargs):
        with open(self.output, "a") as f:
            start = timeit.default_timer()
            ret = fun(*args, **kwargs)
            end = timeit.default_timer()
            spend = end - start
            f.write(f"time:{timezone.now()},file:{file},lineno:{line_no},func:{fun.__qualname__},spends:{spend}\n")

        return ret


default_perf_collect = PerfCollect.default()
