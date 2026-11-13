"""The fixed 24-row E0-to-B0 cost observation, using the same paired worker."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks import pydt_refactor as m
m.ROWS=[r for r in m.ROWS if r['id'].startswith(('W','P','G'))]
# The existing Pool's worker path points here so both children use this subset.
m.__file__=__file__
if __name__=='__main__':
    if '--worker' in sys.argv:m.worker()
    else:
        p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','pilot','collect','report']);p.add_argument('--reference',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--config',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--ids',nargs='*');p.add_argument('--minutes',type=float,default=10);p.add_argument('--target-ms',type=float,default=10)
        args=p.parse_args();m.REFERENCE=args.reference;m.ALLOW_DIFFERENCES=True
        m.shared.ROWS=m.ROWS;m.shared.Pool=m.Pool;m.shared.PROGRAMS=(*m.shared.PROGRAMS,ROOT/'benchmarks/pydt_refactor.py',Path(__file__),m.INPUTS)
        if args.mode=='prepare':m.shared.prepare(args)
        elif args.mode in ('pilot','collect'):m.shared.collect(args,args.mode=='pilot')
        else:m.report(args)
