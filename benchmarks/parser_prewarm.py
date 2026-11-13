"""Prospective CPU-duration preparation; never included in target timings."""
from benchmarks.parser_timing import cpu, wall


def prepare_cpu(run, target_ns, max_wall_ns=100000000):
    start_wall = wall()
    start_cpu = cpu()
    calls = 0
    while cpu() - start_cpu < target_ns:
        if wall() - start_wall >= max_wall_ns:
            break
        run(200)
        calls += 200
    elapsed_cpu = cpu() - start_cpu
    return dict(calls=calls, CPU=elapsed_cpu, T=wall()-start_wall,
                target_ns=target_ns, max_wall_ns=max_wall_ns,
                ready=elapsed_cpu >= target_ns)
