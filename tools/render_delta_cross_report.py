"""Render the fixed Delta comparison without running any benchmark or implementation."""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import json
import math
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tasks/evidence/delta-cross-comparison-20261013'
DOC=ROOT/'docs'

def plain(value):
    """Make structured observations readable while preserving type and errors."""
    if 'error' in value:
        return value['error']['type'].split('.')[-1]+': '+value['error']['message']
    if 'result' in value:return plain(value['result'])
    kind=value.get('type','')
    if kind.startswith('Delta'):
        fields=value['fields']
        items=[f'{k}={v}' for k,v in fields.items() if v not in (None,0)]
        items += [f'{k}=0' for k,v in fields.items() if k in ('year','month','day','weekday','hour','minute','second','microsecond') and v==0]
        return kind+'('+', '.join(items)+')'
    if 'iso' in value:return kind.split('.')[-1]+'('+value['iso']+')'+(' fold='+str(value['fold']) if 'fold' in value else '')
    if 'parts' in value:
        return kind.split('.')[-1]+str(tuple(value['parts']))+(' + '+str(value['nanoseconds'])+'ns' if value.get('nanoseconds') else '')
    if 'items' in value:
        if isinstance(value['items'],dict):return '{'+', '.join(k+': '+plain(v) for k,v in value['items'].items())+'}'
        return '['+', '.join(plain(v) for v in value['items'])+']'
    if kind=='NotImplemented':return 'NotImplemented'
    return repr(value['value']) if 'value' in value else value.get('repr',kind)

def cell(text):
    """Escape table separators without altering substantive observations."""
    return str(text).replace('|','\\|').replace('\n','<br>')

def readable_input(row):
    """Expand stable input IDs into ordinary calls where the frozen values are known."""
    text=row['input']
    if text.startswith(('fraction:','wide:')):return 'Delta('+text.split(':',1)[1]+')'
    if text.startswith('coercion:') and len(text.split(':'))==3:
        _,name,label=text.split(':')
        if label=='float':return f'Delta({name}=-1.9)'
        if label in ('over','under'):
            bits=32 if name in ('years','quarters','months','weeks','year','month','day','weekday','hour','minute','second','millisecond','microsecond') else 64
            value=2**(bits-1) if label=='over' else -2**(bits-1)-1
            return f'Delta({name}={value})'
    values={'relative:overflow:years':'Delta(years=2**31-1, months=12)',
            'relative:overflow:negative-years':'Delta(years=-2**31, months=-1)',
            'relative:overflow:milliseconds':'Delta(milliseconds=2**63-1)',
            'relative:overflow:negative-milliseconds':'Delta(milliseconds=-2**63)',
            'relative:overflow:us-addition':'Delta(microseconds=2**63-1, milliseconds=1)',
            'to_timedelta:Timestamp-nanoseconds':"Delta(microseconds=1).to_timedelta(Timestamp('2024-01-01 00:00:00.000000123'))",
            'to_timedelta:timedelta-subclass':'Delta(days=1).to_timedelta(日期子类：减法返回Span(days=7))',
            'comparison:child-overrides-eq':'Delta.__eq__/__ne__(Delta(days=1), 重写eq且无hash的Child(days=1))',
            'pickle:forged-cache':'用各包自身恢复入口读取合法字段及伪造哈希缓存',
            'pickle:state-layout':'Delta(days=1).__getstate__()',
            'subclass:slots-copy':'copy.copy(带label/payload两个slots的Delta子类)，读取附加字段',
            'subclass:slots-deepcopy':'copy.deepcopy(带label/payload两个slots的Delta子类)，读取附加字段',
            'subclass:slots-pickle':'pickle往返带label/payload两个slots的Delta子类，读取附加字段'}
    return values.get(text,text)

def functional_tables():
    """Publish every observation and each observed behavioral difference."""
    data=json.loads((OUT/'functional.json').read_text())
    with (DOC/'Delta-Cython与Rust功能观察.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['编号','分组','输入','语义一致','完整观察一致','Rust','Cython','Rust原始结果','Cython原始结果'])
        for row in data['rows']:
            writer.writerow([row['id'],row['category'],readable_input(row),row['same_semantics'],row['exact_observation_equal'],
                             plain(row['R']),plain(row['C']),json.dumps(row['R'],ensure_ascii=False),json.dumps(row['C'],ensure_ascii=False)])
    differences=[r for r in data['rows'] if not r['same_semantics']]
    text=['# Delta Cython–Rust功能差异明细','',
          '固定对象：Rust候选97与Cython R2FinalE；共同Python3.13.3及依赖。这里只列实际观察，不改变两个实现。',
          '',f'共{len(data["rows"])}项观察，{len(differences)}项值/类型/异常类别不同；重复输入用于核对，不是独立功能数量。',
          '', '## 值、返回类型及异常类别差异','',
          '| 序号 | 输入或固定case ID | Rust | Cython |','| ---: | --- | --- | --- |']
    for index,row in enumerate(differences,1):
        text.append('| '+ ' | '.join([str(index),cell(readable_input(row)),cell(plain(row['R'])),cell(plain(row['C']))])+' |')
    wording=defaultdict(list)
    for row in data['rows']:
        if row['same_semantics'] and not row['exact_observation_equal']:
            wording[(plain(row['R']),plain(row['C']))].append(row['id'])
    text += ['', '## 异常文字差异','',
             f'{sum(map(len,wording.values()))}项异常类别一致、文字不同，以下按完全相同的文字对分组。每个case的完整记录在功能观察CSV；不把这些差异静默当作完全兼容。','',
             '| 序号 | 涉及项数 | Rust文字 | Cython文字 | 输入编号 |','| ---: | ---: | --- | --- | --- |']
    for index,((r,c),ids) in enumerate(wording.items(),1):
        text.append('| '+' | '.join([str(index),str(len(ids)),cell(r),cell(c),cell(', '.join(ids))])+' |')
    text += ['', '完整输入与原始观察：[功能观察CSV](/Users/jef/ResilioSync/code/rsTimes/docs/Delta-Cython与Rust功能观察.csv)。',
             'Rust来源的case ID可在tests/delta/cases.py查到实际参数；Cython来源输入已保留完整Python表达式。',
             '类型映射只统一两包对应Delta、错误类及同源测试子类名称，不隐藏日期/时长子类、纳秒或真实错误类别。','']
    (DOC/'Delta-Cython与Rust功能差异明细.md').write_text('\n'.join(text))

def group_name(key,original):
    """Map both source suites to the same reader-facing categories."""
    if key.startswith('direct:repr'):return '表示：新对象/交替/子类'
    if 'repr' in key or 'protocol:str' in key:return '表示：重复读取同一对象'
    if 'hash' in key:return '哈希'
    if 'getters' in key or 'value-attributes' in key:return '属性读取'
    if 'bool' in key:return '真假判断'
    if 'protocol:eq' in key or 'value-equal' in key or 'value-unequal' in key:return '相等比较'
    if 'unary:' in key or 'value-negate' in key or 'value-absolute' in key:return '取负与绝对值'
    if key.startswith('C:construct') or original=='B1':return '整数构造与归一化'
    if 'delta-arithmetic' in key or key.startswith('C:arithmetic-delta'):return 'Delta加减'
    if key.startswith('R:timedelta:') or key.startswith('C:arithmetic-timedelta'):return 'timedelta运算'
    if key.startswith('R:save:'):return 'pickle与复制'
    if original=='B5' or key.startswith('C:calendar-'):return 'date/datetime与时区'
    if original=='B7' or 'relativedelta' in key:return 'relativedelta'
    if original=='B8' or key.startswith('C:interop-numpy'):return 'NumPy标量'
    if original=='B10' or key.startswith('C:interop-pydt'):return 'Pydt'
    if key.startswith('C:interop-pandas'):return 'pandas'
    if original=='X1':return 'to_timedelta'
    if original.startswith('A'):
        return {'A1':'批量 date/datetime','A2':'批量 Delta','A3':'批量 timedelta','A4':'批量 Pydt','A5':'批量 relativedelta','A6':'批量 NumPy','A7':'批量混合'}[original.split(':')[0]]
    if key.startswith('C:batch-'):
        kind=key.split('-')[1]
        return '批量 '+ ('date/datetime' if kind in ('date','datetime') else 'Delta' if kind=='delta' else kind)
    return original

def performance_tables():
    """Recompute coverage, member quality and fixed stability from retained records."""
    config=json.loads((OUT/'config.json').read_text())
    by_scene=defaultdict(list)
    all_attempts=Counter()
    for path in sorted(OUT.glob('main-[0-2].jsonl'))+sorted(OUT.glob('independent-[0-2].jsonl')):
        for line in path.read_text().splitlines():
            row=json.loads(line)
            all_attempts['attempted']+=1
            all_attempts['valid' if row['valid'] else 'rejected']+=1
            if row['valid']:by_scene[row['scene']].append(row)
    results=[]
    for key,scene in config['scenes'].items():
        rows=by_scene[key]
        coverage=len(rows)==144 and len({(r['phase'],r['cycle'],r['slot']) for r in rows})==144
        pids={r['pid'] for r in rows}
        coverage=coverage and len(pids)==6
        phases={phase:[r for r in rows if r['phase']==phase] for phase in ('main','independent')}
        ratios={phase:statistics.median(r['ratio'] for r in subset) for phase,subset in phases.items() if subset}
        levels=[]
        for subset in phases.values():
            medians=[statistics.median(r['ratio'] for r in subset if r['cycle']==i) for i in range(3) if any(r['cycle']==i for r in subset)]
            if medians:levels.append(max(medians)/min(medians))
            orders=[statistics.median(r['ratio'] for r in subset if r['order']==order) for order in ('CRRC','RCCR') if any(r['order']==order for r in subset)]
            if orders:levels.append(max(orders)/min(orders))
        if len(ratios)==2:levels.append(max(ratios.values())/min(ratios.values()))
        quality=all(all(m['valid'] and m['T']>=5_000_000 and m['CPU']>0 and abs(m['T']-m['CPU'])/m['T']<=.10
                        and m['boundary']/m['T']<=.01 and config['clock']['max_read_ns']/m['T']<=.005
                        and m['n']==scene['n'] for m in r['members'])
                    and r['span']<=500_000_000 and 0<=r['slot']<24
                    and r['order']==('CRRC' if r['slot']%2==0 else 'RCCR')
                    and ''.join(m['role'] for m in r['members'])==r['order'] for r in rows)
        spread=max(levels) if levels else None
        ready=coverage and quality and scene['precision_ready'] and spread<=1.05
        estimate=statistics.median(r['ratio'] for r in rows) if rows else None
        verdict='Rust更快' if ready and estimate>1.05 else 'Cython更快' if ready and estimate<1/1.05 else '接近' if ready else '不明确'
        results.append({'id':key,'group':group_name(key,scene['metadata']['group']),'input':scene['metadata']['input'],
                        'C_ns':statistics.median(r['C_ns'] for r in rows) if rows else None,
                        'R_ns':statistics.median(r['R_ns'] for r in rows) if rows else None,
                        'ratio':estimate,'main_ratio':ratios.get('main'),'independent_ratio':ratios.get('independent'),
                        'groups':len(rows),'processes':len(pids),'n':scene['n'],'coverage':coverage,'quality':quality,
                        'precision':scene['precision_ready'],'max_stability_spread':spread,'conclusion':verdict})
    columns=list(results[0])
    with (DOC/'Delta-Cython与Rust性能明细.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader();writer.writerows(results)
    summary={'rows':results,'attempts':dict(all_attempts),'verdicts':dict(Counter(r['conclusion'] for r in results)),
             'groups':{},'config':str(OUT/'config.json')}
    grouped=defaultdict(list)
    for row in results:grouped[row['group']].append(row)
    for group,rows in grouped.items():
        ready=[row for row in rows if row['conclusion']!='不明确']
        summary['groups'][group]={'scenes':len(rows),'clear':len(ready),'rust_wins':sum(r['conclusion']=='Rust更快' for r in rows),
                                 'cython_wins':sum(r['conclusion']=='Cython更快' for r in rows),'near':sum(r['conclusion']=='接近' for r in rows),
                                 'geomean_ratio':math.exp(statistics.mean(math.log(r['ratio']) for r in ready)) if ready else None}
    (OUT/'performance-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    lines=['# Delta Cython–Rust性能逐项明细','',
           '速度比=Cython耗时/Rust耗时；大于1偏向Rust。计时单位为每次完整公共调用的微秒，批量为整个列表调用。',
           '“接近”表示比值在1/1.05到1.05之间；“不明确”保留观察值，但覆盖、精度或固定稳定性要求不足，不排名。','',
           '| 场景 | Cython μs | Rust μs | 速度比 | 主轮 | 独立轮 | 结论 |','| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for row in results:
        vals=[cell(row['id'])]+[f'{row[k]/1000:.3f}' if row[k] is not None else '缺失' for k in ('C_ns','R_ns')]
        vals += [f'{row[k]:.3f}' if row[k] is not None else '缺失' for k in ('ratio','main_ratio','independent_ratio')]+[row['conclusion']]
        lines.append('| '+' | '.join(vals)+' |')
    lines += ['', '全部数值、覆盖与稳定性：[性能CSV](/Users/jef/ResilioSync/code/rsTimes/docs/Delta-Cython与Rust性能明细.csv)。','']
    (DOC/'Delta-Cython与Rust性能逐项明细.md').write_text('\n'.join(lines))
    print(json.dumps({'scenes':len(results),'attempts':dict(all_attempts),'verdicts':summary['verdicts']},ensure_ascii=False))

def complete_main_report():
    """Fill the reader-facing summary from actual finalized observations."""
    data=json.loads((OUT/'performance-summary.json').read_text())
    functional=json.loads((OUT/'functional.json').read_text())
    table=['| 方向 | 明确/总场景 | Cython耗时÷Rust耗时 | Rust更快项 | Cython更快项 | 接近项 |',
           '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name,row in data['groups'].items():
        ratio=f'{row["geomean_ratio"]:.3f}×' if row['geomean_ratio'] else '不明确'
        table.append(f'| {name} | {row["clear"]}/{row["scenes"]} | {ratio} | {row["rust_wins"]} | {row["cython_wins"]} | {row["near"]} |')
    verdict=data['verdicts']
    text=[f'完整采集{len(data["rows"])}项、两轮各3个新进程，共{data["attempts"]["valid"]}个有效完整四批组。',
          '',f'按冻结的质量与稳定性规则：**Rust更快{verdict.get("Rust更快",0)}项，Cython更快{verdict.get("Cython更快",0)}项，接近{verdict.get("接近",0)}项，不明确{verdict.get("不明确",0)}项。** 这是固定场景计数，不是业务时间占比。',
          '',*table,'',
          '分组倍率为明确项的等权几何平均；“明确/总场景”保留未明确项的数量，不用局部平均掩盖它们。',
          '', '### 代表调用的实际耗时','',
          '| 调用 | Cython μs | Rust μs | 速度比 | 结论 |','| --- | ---: | ---: | ---: | --- |']
    selected=['C:construct-empty','C:construct-normal','C:construct-negative','C:construct-ms-us','C:value-attributes',
              'C:arithmetic-delta-add','C:arithmetic-timedelta-add','C:calendar-datetime-radd',
              'C:interop-from-relativedelta','C:interop-pydt-add','C:value-repr',
              'direct:repr-first-fresh','direct:repr-alternating','direct:repr-subclass',
              'R:protocol:hash-cached','R:save:base:write','R:save:base:read',
              'R:to-timedelta:positive','R:to-timedelta:month-leap']
    lookup={row['id']:row for row in data['rows']}
    labels={'C:construct-empty':'Delta()','C:construct-normal':'多字段整数构造','C:construct-negative':'负值进位构造',
            'C:construct-ms-us':'毫秒/微秒构造','C:value-attributes':'读取全部15属性',
            'C:arithmetic-delta-add':'Delta + Delta','C:arithmetic-timedelta-add':'Delta + timedelta',
            'C:calendar-datetime-radd':'datetime + Delta','C:interop-from-relativedelta':'from_relativedelta',
            'C:interop-pydt-add':'Pydt + Delta','C:value-repr':'repr同一对象（热）',
            'direct:repr-first-fresh':'新建对象后首次repr','direct:repr-alternating':'两个对象交替repr',
            'direct:repr-subclass':'子类repr','R:protocol:hash-cached':'重复hash',
            'R:save:base:write':'pickle保存基础Delta','R:save:base:read':'pickle读取基础Delta',
            'R:to-timedelta:positive':'to_timedelta无起点','R:to-timedelta:month-leap':'to_timedelta月底起点'}
    for key in selected:
        row=lookup[key]
        text.append(f'| {labels[key]} | {row["C_ns"]/1000:.3f} | {row["R_ns"]/1000:.3f} | {row["ratio"]:.3f}× | {row["conclusion"]} |')
    text += ['', '### apply_many同一规模直接对比','',
             '| 输入 | 元素数 | Cython μs/整次 | Rust μs/整次 | 速度比 | 结论 |',
             '| --- | ---: | ---: | ---: | ---: | --- |']
    bulk={'date-month-end':'date月底','datetime-relative':'datetime时长','delta-relative':'Delta',
          'timedelta-positive':'timedelta','pydt-month':'Pydt月底','dateutil-relative':'relativedelta',
          'numpy-datetime':'NumPy datetime64','numpy-timedelta':'NumPy timedelta64','mixed':'混合类型'}
    for name,label in bulk.items():
        for size in (1024,10000):
            row=lookup[f'R:bulk:{name}:{size}']
            text.append(f'| {label} | {size} | {row["C_ns"]/1000:.3f} | {row["R_ns"]/1000:.3f} | {row["ratio"]:.3f}× | {row["conclusion"]} |')
    path=DOC/'Delta-Cython与Rust横向对比.md'
    source=path.read_text()
    if '<!-- PERFORMANCE_SUMMARY -->' in source:
        source=source.replace('<!-- PERFORMANCE_SUMMARY -->','\n'.join(text))
    else:
        start=source.index('## 共同功能的直接性能比较')+len('## 共同功能的直接性能比较')
        end=source.index('速度比定义为',start)
        source=source[:start]+'\n\n'+'\n'.join(text)+'\n\n'+source[end:]
    wording=sum(r['same_semantics'] and not r['exact_observation_equal'] for r in functional['rows'])
    source=source.replace('覆盖统计将在最终整理时填写。',f'本次共{len(functional["rows"])}项功能观察：{functional["same"]}项值/类型/异常类别一致，{functional["different"]}项不同；一致项中另有{wording}项异常文字不同。重复场景不算独立功能数量。')
    path.write_text(source)

if __name__=='__main__':
    functional_tables()
    performance_tables()
    complete_main_report()
