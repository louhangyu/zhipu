from recsys.perf_collect import default_perf_collect
import timeit


class ScheduleJob:

    def __init__(self, module, section, func, *args, **kwargs):
        self.module = module
        self.section = section
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        ret = self.func(*self.args, **self.kwargs)
        return ret


class Schedule:

    def __init__(self):
        self.jobs = []

    def register(self, module, section, func, *args, **kwargs):
        job = ScheduleJob(module, section, func, *args, **kwargs)
        self.jobs.append(job)

    def run(self):
        for i, job in enumerate(self.jobs):
            print(f"{i}th job start {job.module}.{job.section}")
            start = timeit.default_timer()
            job.run()
            end = timeit.default_timer()
            spend = end - start
            print(f"{i}th job done  {job.module}.{job.section}, spend {spend}s")

