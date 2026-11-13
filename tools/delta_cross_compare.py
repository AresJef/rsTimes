"""Compare two fixed installed Delta extensions with shared dependencies.

This task-scoped tool observes existing cases and records direct paired timings.
It never builds, installs, changes either implementation, or substitutes Python.
"""
from pathlib import Path
import argparse
import copy
import csv
import gc
import hashlib
import importlib.machinery
import importlib.metadata
import importlib.util
import json
import math
import os
import pickle
import platform
import statistics
import sys
import time
import types
from datetime import date, datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
CY_ROOT = Path('/Users/jef/ResilioSync/code/cyTimes-rewrite')
CY_SITE = CY_ROOT / '.venv-delivery-R2FinalE/lib/python3.13/site-packages'
OUT = ROOT / 'tasks/evidence/delta-cross-comparison-20261013'
FIELDS = ('years','months','days','hours','minutes','seconds','microseconds',
          'year','month','day','weekday','hour','minute','second','microsecond')
EXPECTED = {
    'R': ('rstimes._native','bdadd54566d4ad41ceed5591d57a6fa789cee9d09eaff4d2e5a84345d326bb73'),
    'C': ('cytimes_rewrite.delta','3ef0ec227fe995ebb0c289f28d59ff69faa8847dcfd13b0755eaaf71fb289aba'),
}

def save(name, value):
    """Write task evidence outside all selected artifacts."""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def load_source(name, path):
    """Load a source-controlled case module with its own pickle namespace."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def load_targets():
    """Load exact installed packages, leaving shared dependency lookup unchanged."""
    import rstimes
    spec = importlib.machinery.PathFinder.find_spec('cytimes_rewrite', [str(CY_SITE)])
    if spec is None:
        raise RuntimeError('Selected Cython installed package missing')
    cy = importlib.util.module_from_spec(spec)
    sys.modules['cytimes_rewrite'] = cy
    spec.loader.exec_module(cy)
    targets = {'R': rstimes.Delta, 'C': cy.Delta}
    identity = {}
    for role, (module_name, expected) in EXPECTED.items():
        module = sys.modules[module_name]
        path = Path(module.__file__).resolve()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise RuntimeError(f'{role} native identity mismatch')
        identity[role] = {'native': str(path), 'sha256': digest,
                          'class': targets[role].__module__ + '.' + targets[role].__name__}
    for name, expected in [('cytimes_rewrite._calendar','a0dcc8ac79f39394e92bf95b9d069e506ab624032b48f0599182e0a848be700b'),
                           ('cytimes_rewrite.errors','a7c7e95bf7ebce1c714fb776fe4a348c70714938bb3298156f3ec2b641f4479b')]:
        module = sys.modules[name]
        assert hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() == expected
    deps = {name: importlib.metadata.version(name) for name in
            ('cytimes','numpy','pandas','python-dateutil','tzdata','pendulum')}
    identity.update(python=sys.version, executable=sys.executable, machine=platform.machine(),
                    platform=platform.platform(), dependencies=deps, pid=os.getpid())
    return targets, identity

def canonical(value, targets):
    """Describe observable values, preserving precision and corresponding types."""
    cls = type(value)
    if isinstance(value, tuple(targets.values())):
        kind = 'Delta' if cls in targets.values() else 'DeltaSubclass:' + cls.__qualname__
        return {'type': kind, 'fields': {k: getattr(value,k) for k in FIELDS}}
    kind = cls.__module__ + '.' + cls.__qualname__
    for prefix in ('cross_cases_R.', 'cross_cases_C.'):
        if kind.startswith(prefix): kind = 'shared_cases.' + kind[len(prefix):]
    if isinstance(value, datetime):
        return {'type':kind, 'iso':value.isoformat(), 'fold':value.fold,
                'tz':str(value.tzinfo), 'nanosecond':getattr(value,'nanosecond',None)}
    if isinstance(value, date): return {'type':kind,'iso':value.isoformat()}
    if isinstance(value, timedelta):
        return {'type':kind,'parts':[value.days,value.seconds,value.microseconds],
                'nanoseconds':getattr(value,'nanoseconds',None)}
    if isinstance(value, (tuple,list)):
        return {'type':kind,'items':[canonical(x,targets) for x in value]}
    if isinstance(value, dict):
        return {'type':kind,'items':{str(k):canonical(v,targets) for k,v in value.items()}}
    if value is NotImplemented: return {'type':'NotImplemented'}
    if value is None or isinstance(value,(bool,int,float,str)):
        return {'type':kind,'value':value if not isinstance(value,float) or math.isfinite(value) else repr(value)}
    return {'type':kind,'repr':repr(value)}

def error_kind(error):
    """Map corresponding package error names without erasing error messages."""
    cls = type(error)
    name = cls.__module__ + '.' + cls.__qualname__
    for prefix in ('rstimes.errors.', 'cytimes_rewrite.errors.'):
        if name.startswith(prefix): return 'DeltaErrors.' + name[len(prefix):]
    return name

def observe(call, targets):
    """Record one real call or its actual exception."""
    try: return {'result':canonical(call(),targets)}
    except Exception as error:
        return {'error':{'type':error_kind(error),'message':str(error)}}

def same_semantics(left,right):
    """Compare outputs and error categories; report error wording separately."""
    if 'error' in left and 'error' in right:
        return left['error']['type'] == right['error']['type']
    return left == right

def functional(targets, identity):
    """Reuse both projects' frozen inputs and add only uncovered direct boundaries."""
    rows = []
    role_modules = {}
    for role, package in [('R','rstimes'),('C','cytimes_rewrite')]:
        module = load_source('cross_cases_'+role, ROOT / 'tests/delta/cases.py')
        role_modules[role] = module
        _, cases = module.cases(package)
        observed = {}
        for case in cases:
            observed[case.id] = observe(case.run,targets)
        role_modules[role] = (module, observed)
    for identifier in role_modules['R'][1]:
        rows.append({'id':'rust-input:'+identifier, 'category':identifier.split(':')[0],
                     'input':identifier, 'R':role_modules['R'][1][identifier],
                     'C':role_modules['C'][1][identifier]})
    cy_cases = load_source('cross_cython_cases', CY_ROOT / 'tests/behavior_cases.py')
    for case in cy_cases.cases():
        row = {'id':'cython-input:'+case['id'],'category':case['category'],'input':case['expression']}
        for role, Delta in targets.items():
            row[role] = observe(lambda expr=case['expression'],Delta=Delta:
                                eval(expr, cy_cases.namespace(Delta)), targets)
        rows.append(row)
    for label, factory in extra_cases().items():
        row = {'id':'direct:'+label,'category':'direct','input':label}
        for role, Delta in targets.items(): row[role] = observe(lambda Delta=Delta:factory(Delta),targets)
        rows.append(row)
    for row in rows:
        row['same_semantics'] = same_semantics(row['R'],row['C'])
        row['exact_observation_equal'] = row['R'] == row['C']
    if (OUT / 'functional.json').exists() and not (OUT / 'functional-initial.json').exists():
        (OUT / 'functional.json').rename(OUT / 'functional-initial.json')
    save('functional.json',{'identity':identity,'rows':rows,
                           'same':sum(r['same_semantics'] for r in rows),
                           'different':sum(not r['same_semantics'] for r in rows)})
    save('interface.json',{role:{'fields':list(FIELDS), 'members':sorted(set(dir(Delta))-set(dir(object))),
                                 'own_members':sorted(Delta.__dict__)} for role,Delta in targets.items()})
    print(json.dumps({'functional_rows':len(rows),'differences':sum(not r['same_semantics'] for r in rows)},ensure_ascii=False))

def extra_cases():
    """Probe agreed cross-project differences absent from the legacy inputs."""
    from dateutil.relativedelta import relativedelta, MO
    import pandas as pd
    cases = {}
    for name in ('weeks','days','hours','minutes','seconds','milliseconds','microseconds'):
        for number in (1.5,-1.5,.5):
            cases[f'fraction:{name}={number}'] = lambda D,name=name,number=number:D(**{name:number})
    for name in ('years','quarters','months','weeks','year','month','day','weekday','hour','minute','second','millisecond','microsecond'):
        cases[f'wide:{name}=2**40'] = lambda D,name=name:D(**{name:2**40})
    cases['wide:years=2**53+1'] = lambda D:D(years=2**53+1)
    cases['to_timedelta:calendar-without-start'] = lambda D:D(months=1).to_timedelta()
    cases['to_timedelta:month-end'] = lambda D:D(months=1).to_timedelta(date(2024,1,31))
    cases['to_timedelta:Timestamp-nanoseconds'] = lambda D:D(microseconds=1).to_timedelta(pd.Timestamp('2024-01-01 00:00:00.000000123'))
    class Span(timedelta): pass
    class DateSpan(date):
        def __sub__(self,other):return Span(days=7)
    cases['to_timedelta:timedelta-subclass'] = lambda D:D(days=1).to_timedelta(DateSpan(2024,1,1))
    class BadDate(date):
        def __sub__(self,other):return 17
    cases['to_timedelta:non-duration-subtraction'] = lambda D:D(days=1).to_timedelta(BadDate(2024,1,1))
    def child_compare(D):
        class Child(D):
            def __eq__(self,other):return False
            __hash__ = None
        return (D.__eq__(D(days=1),Child(days=1)),D.__ne__(D(days=1),Child(days=1)))
    cases['comparison:child-overrides-eq'] = child_compare
    def child_order(D):
        class Child(D):
            def __lt__(self,other):return False
        return D.__eq__(D(days=1),Child(days=1))
    cases['comparison:child-only-orders'] = child_order
    for rdlabel,rd in [('weekday',relativedelta(weekday=MO(1))),('leapdays',relativedelta(leapdays=1))]:
        cases['relativedelta:'+rdlabel] = lambda D,rd=rd:D.from_relativedelta(rd)
    def cache_state(D):
        d = D(days=1)
        if D.__module__.startswith('cytimes_rewrite'):
            from cytimes_rewrite.delta import _restore_delta
            state = d.__reduce_ex__(4)[1][1] + (hash(d) ^ 8,)
            return _restore_delta(D,state)
        from rstimes._native import _restore_delta
        return _restore_delta(D,tuple(getattr(d,k) if getattr(d,k) is not None else -1 for k in FIELDS),hash(d)^8)
    cases['pickle:forged-cache'] = cache_state
    cases['pickle:state-layout'] = lambda D:D(days=1).__getstate__()
    def slots_copy(D,method):
        import types
        name = 'cross_slots_' + ('R' if D.__module__.startswith('rstimes') else 'C')
        module = types.ModuleType(name)
        sys.modules[name] = module
        Child = type('SlotChild',(D,),{'__slots__':('label','payload'),'__module__':name})
        module.SlotChild = Child
        value = Child(days=1)
        value.label, value.payload = 'saved', [1,2]
        result = pickle.loads(pickle.dumps(value)) if method == 'pickle' else getattr(copy,method)(value)
        return (result.days,result.label,result.payload,result is value,result.payload is value.payload)
    for method in ('copy','deepcopy','pickle'):
        cases['subclass:slots-'+method] = lambda D,method=method:slots_copy(D,method)
    cases['apply_many:mixed'] = lambda D:D(days=1).apply_many([date(2024,1,1),datetime(2024,1,1),D(hours=1),timedelta(hours=1),relativedelta(hours=1)])
    cases['apply_many:generator'] = lambda D:D(days=1).apply_many(x for x in [date(2024,1,1),date(2024,1,2)])
    cases['pickle:roundtrip'] = lambda D:pickle.loads(pickle.dumps(D(days=1,hour=9)))
    return cases

def loop_for(call):
    """Use the same public-call loop and immediate result release for both roles."""
    def run(n):
        for _ in range(n):
            result = call()
            del result
    return run

def workloads(targets):
    """Reuse both real workload sets; reject non-equivalent outcomes before timing."""
    package = types.ModuleType('benchmarks')
    package.__path__ = [str(CY_ROOT / 'benchmarks')]
    sys.modules['benchmarks'] = package
    import benchmarks.round2_scenarios as cy_work
    pairs, metadata = {}, {}
    for role,D in targets.items():
        for ident,(run,one) in cy_work.workloads(D).items():
            key='C:'+ident
            pairs.setdefault(key,{})[role]=(run,one)
            group = ('批量' if ident.startswith('batch-') else '构造' if ident.startswith('construct-')
                     else '日期' if ident.startswith('calendar-') else 'Delta与时长运算' if ident.startswith('arithmetic-')
                     else '第三方' if ident.startswith('interop-') else '属性与协议')
            metadata[key]={'group':group,'input':next((expr for name,expr,_ in cy_work.SCENARIOS if name==ident),ident),'source':'Cython共享输入'}
        source = load_source('cross_perf_'+role,ROOT / 'tests/delta/cases.py')
        _, records = source.benchmark_cases('rstimes' if role=='R' else 'cytimes_rewrite')
        _, extra = source.revision_benchmark_cases('rstimes' if role=='R' else 'cytimes_rewrite','revision-candidate')
        records += [case for case in extra if not case.id.startswith('float:')]
        for case in records:
            key='R:'+case.id
            pairs.setdefault(key,{})[role]=(loop_for(case.run),case.run)
            metadata[key]={'group':case.group,'input':case.id,'source':'Rust共享输入'}
        for label in ('repr-first-fresh','repr-alternating','repr-subclass'):
            class Child(D):pass
            values=[D(days=1),D(days=2)]
            state=[0]
            if label=='repr-first-fresh': call=lambda D=D:repr(D(days=1))
            elif label=='repr-subclass':
                child=Child(days=1)
                call=lambda child=child:repr(child)
            else:
                def call(values=values,state=state):
                    state[0] ^= 1
                    return repr(values[state[0]])
            key='direct:'+label
            pairs.setdefault(key,{})[role]=(loop_for(call),call)
            metadata[key]={'group':'表示与缓存','input':label,'source':'区分热缓存、交替和首次构造'}
    selected,excluded={},{}
    for key,roles in pairs.items():
        seen={}
        for role,(_,one) in roles.items():
            if key.startswith('R:save:') and key.endswith(':write'):
                seen[role]=observe(lambda one=one:pickle.loads(one()),targets)
            else: seen[role]=observe(one,targets)
        if all('result' in item for item in seen.values()) and same_semantics(seen['R'],seen['C']):
            selected[key]=roles
        else: excluded[key]={'input':metadata[key],'observations':seen,'reason':'结果/返回类型不同或调用报错，不参加性能排名'}
    return selected,metadata,excluded

def measure(run,n):
    """Keep GC enabled; bracket full public work using wall and thread CPU clocks."""
    w0=time.perf_counter_ns(); c0=time.thread_time_ns(); w1=time.perf_counter_ns()
    run(n)
    w2=time.perf_counter_ns(); c1=time.thread_time_ns(); w3=time.perf_counter_ns()
    return {'T':w2-w1,'CPU':c1-c0,'boundary':(w1-w0)+(w3-w2),'n':n,'start':w0,'end':w3}

def good(member,clock,min_ns=5_000_000):
    """Apply frozen quality tests without choosing by performance outcome."""
    T=member['T']
    return (T>=min_ns and member['CPU']>0 and abs(T-member['CPU'])/T<=.10
            and member['boundary']/T<=.01 and clock['max_read_ns']/T<=.005)

def quad(roles,n,slot,clock,min_ns=5_000_000,max_span=500_000_000):
    """Measure complete ABBA/BAAB groups; preserve every valid slow group."""
    order='CRRC' if slot%2==0 else 'RCCR'
    members=[]
    for role in order:
        row=measure(roles[role][0],n)
        row['role']=role
        row['valid']=good(row,clock,min_ns)
        members.append(row)
    span=members[-1]['end']-members[0]['start']
    valid=all(row['valid'] for row in members) and span<=max_span
    C=sum(row['T'] for row in members if row['role']=='C')
    R=sum(row['T'] for row in members if row['role']=='R')
    return {'order':order,'members':members,'span':span,'valid':valid,'ratio':C/R,'C_ns':C/(2*n),'R_ns':R/(2*n)}

def clocks():
    """Measure available clock resolution and actual read overhead once."""
    overhead=[]
    for _ in range(2000):
        t0=time.perf_counter_ns(); time.thread_time_ns(); overhead.append(time.perf_counter_ns()-t0)
    return {'max_read_ns':max(statistics.median(overhead),time.get_clock_info('perf_counter').resolution*1e9,
                              time.get_clock_info('thread_time').resolution*1e9),'wall':'perf_counter_ns','cpu':'thread_time_ns'}

def prepare(targets,identity):
    """Calibrate common counts, short/long controls and bounded feasibility before freezing."""
    pairs,metadata,excluded=workloads(targets)
    clock=clocks()
    config={'protocol':'cross-delta-v1','identity':identity,'clock':clock,'scenes':{},'excluded':excluded,
            'cycles_per_phase':3,'groups_per_cycle':24,'order_quota':{'CRRC':12,'RCCR':12},
            'gc':'enabled','minimum_batch_ns':5_000_000,'off_cpu_limit':.10,'boundary_limit':.01,
            'group_span_ns':500_000_000,'short_long_ratio_limit':1.03,'stability_limit':1.05,
            'estimator':'median of complete quad C-total/R-total; groups and cycles predetermined',
            'near_equal_ratio':[1/1.05,1.05],'collect_seconds_limit':2100,'finite_retest':'none; unstable results remain inconclusive'}
    started=time.perf_counter()
    for index,(key,roles) in enumerate(pairs.items()):
        n=1
        for _ in range(5):
            samples=[measure(roles[r][0],n) for r in ('C','R')]
            fastest=min(s['T'] for s in samples)
            if fastest>=6_000_000:break
            n=max(n+1,math.ceil(n*7_000_000/max(1,fastest)))
        controls=[]
        for slot in range(8):
            kinds=(1,2) if slot%4 in (0,3) else (2,1)
            for factor in kinds:
                row=quad(roles,n*factor,slot,clock,max_span=500_000_000*factor)
                row.update(slot=slot,factor=factor)
                controls.append(row)
        short=[r['ratio'] for r in controls if r['factor']==1 and r['valid']]
        long=[r['ratio'] for r in controls if r['factor']==2 and r['valid']]
        spread=(max(statistics.median(short),statistics.median(long))/min(statistics.median(short),statistics.median(long))) if short and long else None
        config['scenes'][key]={'n':n,'metadata':metadata[key],'control':controls,
                              'short_long_spread':spread,'precision_ready':len(short)>=4 and len(long)>=4 and spread<=1.03}
        if (index+1)%25==0: print(json.dumps({'prepared':index+1,'total':len(pairs)},ensure_ascii=False),flush=True)
    config['prepare_elapsed_seconds']=time.perf_counter()-started
    config['estimated_valid_collection_seconds']=sum(statistics.median([r['span'] for r in s['control'] if r['factor']==1])*144/1e9 for s in config['scenes'].values())
    config['program_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save('config.json',config)
    print(json.dumps({'prepared':len(pairs),'excluded':len(excluded),'elapsed':config['prepare_elapsed_seconds'],
                      'estimated_collection_seconds':config['estimated_valid_collection_seconds'],
                      'precision_unready':sum(not s['precision_ready'] for s in config['scenes'].values())},ensure_ascii=False),flush=True)

def refine_controls(targets):
    """Fix the demonstrated long-control span allowance before formal freezing."""
    config=json.loads((OUT/'config.json').read_text())
    pairs,_,_=workloads(targets)
    config['long_control_span_ns']=1_000_000_000
    for key,scene in config['scenes'].items():
        if scene['precision_ready']:continue
        controls=[]
        for slot in range(8):
            for factor in ((1,2) if slot%4 in (0,3) else (2,1)):
                row=quad(pairs[key],scene['n']*factor,slot,config['clock'],max_span=500_000_000*factor)
                row.update(slot=slot,factor=factor)
                controls.append(row)
        short=[r['ratio'] for r in controls if r['factor']==1 and r['valid']]
        long=[r['ratio'] for r in controls if r['factor']==2 and r['valid']]
        spread=max(statistics.median(short),statistics.median(long))/min(statistics.median(short),statistics.median(long)) if short and long else None
        scene['initial_control']=scene['control']
        scene.update(control=controls,short_long_spread=spread,precision_ready=len(short)>=4 and len(long)>=4 and spread<=1.03)
        print(json.dumps({'refined':key,'short_long_spread':spread,'ready':scene['precision_ready']}),flush=True)
    config['program_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    config['refinement_reason']='Initial short groups valid; 2x controls alone exceeded the mistakenly reused short span. Independently rechecked affected controls with 2x span; member quality and formal span unchanged.'
    config['input_sha256']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in
        (ROOT/'tests/delta/cases.py', CY_ROOT/'benchmarks/round2_scenarios.py',CY_ROOT/'benchmarks/scenarios.py')}
    save('config.json',config)

def collect(targets,identity,phase,cycle):
    """Collect predetermined slots in one new process without refreshing the campaign budget."""
    config=json.loads((OUT/'config.json').read_text())
    assert config['program_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    pairs,_,_=workloads(targets)
    campaign=json.loads((OUT/'campaign.json').read_text())
    log=OUT/f'{phase}-{cycle}.jsonl'
    if log.exists():raise FileExistsError(log)
    counts={}
    with log.open('w') as stream:
        for index,(key,scene) in enumerate(config['scenes'].items()):
            roles=pairs[key]; n=scene['n']
            for role in ('C','R'):roles[role][0](n)
            for slot in range(24):
                attempts=0
                while True:
                    if time.time()>=campaign['deadline_epoch']:
                        print('CAMPAIGN_BUDGET_STOP',flush=True);return
                    row=quad(roles,n,slot,config['clock'])
                    row.update(scene=key,phase=phase,cycle=cycle,slot=slot,pid=os.getpid(),attempt=attempts)
                    stream.write(json.dumps(row,separators=(',',':'))+'\n')
                    counts['valid' if row['valid'] else 'rejected']=counts.get('valid' if row['valid'] else 'rejected',0)+1
                    if row['valid']:break
                    attempts+=1
                    if attempts%5==0:time.sleep(.05)
                    if attempts>=120:
                        print(json.dumps({'scene':key,'slot':slot,'status':'INCOMPLETE_RETRY_LIMIT'}),flush=True);break
            stream.flush()
            if (index+1)%25==0:print(json.dumps({'phase':phase,'cycle':cycle,'scenes':index+1,'counts':counts}),flush=True)
    save(f'{phase}-{cycle}-identity.json',identity)
    print(json.dumps({'phase':phase,'cycle':cycle,'complete_scenes':len(config['scenes']),'counts':counts}),flush=True)

def main():
    """Dispatch bounded comparison phases using fixed installed targets."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['functional','prepare','refine','collect'])
    parser.add_argument('--phase',choices=['main','independent'])
    parser.add_argument('--cycle',type=int)
    args=parser.parse_args()
    targets,identity=load_targets()
    if args.mode=='functional':
        save('identity.json',identity)
        functional(targets,identity)
    elif args.mode=='prepare':prepare(targets,identity)
    elif args.mode=='refine':refine_controls(targets)
    else:collect(targets,identity,args.phase,args.cycle)

if __name__ == '__main__':main()
