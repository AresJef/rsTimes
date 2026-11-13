"""The original target timing bracket, shared by the new same-thread worker."""
import gc
import time

wall = time.perf_counter_ns
cpu = time.thread_time_ns


def measure(run, n):
    if hasattr(run, "sample"):
        return run.sample(n)
    enabled = gc.isenabled()
    gc.disable()
    try:
        w0 = wall(); c0 = cpu(); w1 = wall()
        run(n)
        w2 = wall(); c1 = cpu(); w3 = wall()
    finally:
        if enabled:
            gc.enable()
    return dict(T=w2-w1, CPU=c1-c0, boundary=(w1-w0)+(w3-w2), n=n, start=w0, end=w3)


def clocks():
    observations = [measure(lambda n: None, 1) for _ in range(10000)]
    def spin(n):
        for i in range(n):
            x = i*i
    busy = [measure(spin, 200000) for _ in range(20)]
    def steps(clock):
        old = clock(); diffs = []
        for _ in range(10000):
            new = clock()
            if new > old:
                diffs.append(new-old)
            old = new
        return min(diffs)
    return dict(info={name: vars(time.get_clock_info(name)) for name in ('perf_counter', 'thread_time')},
                min_step_wall=steps(wall), min_step_cpu=steps(cpu), empty=observations, busy=busy)
