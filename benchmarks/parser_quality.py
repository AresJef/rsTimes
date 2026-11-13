"""Reuse the frozen clock-quality rules without importing unrelated collectors."""
POLICY = dict(min_batch_ns=5_000_000, max_boundary_fraction=0.001, q_limit=0.02)

def quality(value,config):
    if config.get('warmup_policy')=='cpu20ms':
        proof=value.get('warmup_cpu')
        if (not isinstance(proof,dict) or proof.get('target_ns')!=20000000
                or proof.get('max_wall_ns')!=100000000):
            return dict(status='ERROR',reason='CPU-duration preparation identity missing')
        if proof.get('ready') is True and proof.get('CPU',0)<20000000:
            return dict(status='ERROR',reason='CPU-duration preparation counter mismatch')
    if value.get('warmup_ready') is False:
        return dict(status='INSUFFICIENT',reason='CPU-duration preparation incomplete')
    T,CPU,boundary=value['T'],value['CPU'],value['boundary']
    if T<=0 or CPU<=0 or boundary<0:return dict(status='ERROR',reason='clock counters invalid')
    e=(boundary+config['clock_uncertainty_ns'])/T
    q=(T-CPU)/T
    result=dict(q=q,e=e)
    if q < -e:return dict(result,status='ERROR',reason='negative difference outside calibrated clock bound')
    if T<POLICY['min_batch_ns'] or boundary/T>POLICY['max_boundary_fraction']:
        return dict(result,status='INSUFFICIENT',reason='duration or boundary resolution')
    if q-e>POLICY['q_limit']:return dict(result,status='REJECTED',reason='off-CPU bound exceeded')
    if q+e>POLICY['q_limit']:return dict(result,status='INSUFFICIENT',reason='off-CPU bound overlaps limit')
    return dict(result,status='VALID',reason='all batch checks passed')


def clock_bound(proof):
    # CPU observations bracket the inner wall interval. Boundary measures that
    # mismatch; the additional term is an empirical residual/quantization bound.
    empty=proof['empty'];busy=proof['busy']
    residual=max(max(0,r['CPU']-r['T']-r['boundary']) for r in empty+busy)
    granularity=max(proof['min_step_wall'],proof['min_step_cpu'],
        int(1e9*proof['info']['perf_counter']['resolution']),int(1e9*proof['info']['thread_time']['resolution']))
    return 2*(residual+granularity)


