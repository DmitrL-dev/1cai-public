"""Report genuine observer records; never reinterpret the old product traces."""
import hashlib
import json
from pathlib import Path
import re
import sys

PREFIX='RENTGEN_OBSERVER '

def records(text):
    result=[]
    for line_number,line in enumerate(text.splitlines(),1):
        if not line.startswith(PREFIX): continue
        words=line[len(PREFIX):].split();kind=words.pop(0)
        if kind not in {'wait','info','regs'}: raise ValueError('unknown observer event')
        row={'kind':kind,'line':line_number}
        for word in words:
            key,value=word.split('=',1)
            if key in row or not re.fullmatch('-?[0-9]+',value): raise ValueError('bad observer field')
            row[key]=int(value)
        expected={
            'wait':{'pid','status'},
            'info':{'pid','entering','ret','errno','op','retained_union_nr','a0','a1'},
            'regs':{'pid','entering','ret','errno','orig_rax','rdi','rsi','rdx'},
        }[kind]
        if set(row)-{'kind','line'}!=expected or row['pid']<=0: raise ValueError('incomplete observer record')
        result.append(row)
    return result


def inspect_ledger(text):
    rows=records(text);prior_info=None;none=[];reused=[];fallback=[];corrected=[]
    for index,row in enumerate(rows):
        if row['kind']!='info':continue
        if row['ret']==24 and row['op']==0 and row['entering']==1 and row['errno']==0:
            none.append(row)
            complete_prior = (prior_info is not None and prior_info['entering']==1 and prior_info['errno']==0
                              and ((prior_info['op']==1 and prior_info['ret']==80) or (prior_info['op']==3 and prior_info['ret']==84)))
            cross_pid = (complete_prior and prior_info['pid']!=row['pid']
                         and all(prior_info[k]==row[k] for k in ('retained_union_nr','a0','a1')))
            if cross_pid: reused.append({'prior':prior_info,'none':row})
            if index+1<len(rows):
                nxt=rows[index+1]
                if nxt['kind']=='regs' and nxt['pid']==row['pid'] and nxt['entering']==1:
                    available=nxt['ret']==0 and nxt['errno']==0
                    changed=available and nxt['orig_rax']!=row['retained_union_nr']
                    item={'none':row,'regs':nxt,'available':available,'different_number':changed}
                    fallback.append(item)
                    if cross_pid and changed: corrected.append({'prior':prior_info,**item})
        prior_info=row
    return {'records':len(rows),'none_entry_count':len(none),'cross_pid_retained_union_count':len(reused),'fallback_count':len(fallback),
            'successful_fallback_count':sum(x['available'] for x in fallback),'changed_syscall_number_count':sum(x['different_number'] for x in fallback),'corrected_cross_pid_fallback_count':len(corrected),
            'none_examples':none[:8],'cross_pid_examples':reused[:8],'fallback_examples':fallback[:8],'corrected_cross_pid_examples':corrected[:8]}


def main():
    if len(sys.argv)!=2:raise SystemExit('one evidence directory required')
    root=Path(sys.argv[1]); runs=json.loads((root/'run-results.json').read_text())
    if {x['version'] for x in runs}!={'6.8','6.12'} or len(runs)!=2:raise ValueError('both exact observers required')
    report={'scope':'synthetic zero-capability observer fidelity only; not Rentgen qualification','versions':{},'status':'inconclusive'}
    completed=True
    for run in runs:
        version=run['version'];ledger=root/f'ledger-{version}.log';trace=root/f'trace-{version}.log'
        data=inspect_ledger(ledger.read_text());data['run']=run
        data['stdout']=(root/f'probe-{version}.stdout').read_text()
        data['ledger_sha256']=hashlib.sha256(ledger.read_bytes()).hexdigest()
        data['trace_sha256']=hashlib.sha256(trace.read_bytes()).hexdigest() if trace.is_file() else None
        complete=(run['exit']==0 and not run['timeout'] and not run.get('interrupted',True) and run.get('failure') is None
                  and run['cleanup_empty'] and run.get('cleanup_errors')==[]) and data['stdout']=='completed_cycles=100\n' and trace.is_file() and trace.stat().st_size>0
        data['workload_completed']=complete;completed &= complete;report['versions'][version]=data
    old,new=(report['versions'][v] for v in ('6.8','6.12'))
    positive=old['cross_pid_retained_union_count']>0 and new['corrected_cross_pid_fallback_count']>0
    if completed and positive:report['status']='mechanism_observed_and_fixed_fallback_exercised'
    elif not completed:report['status']='workload_not_completed'
    # Even positive observer controls do not authorize a product path, explain
    # an old undecoded syscall, or waive future full-operation trace completeness.
    (root/'observer-analysis.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'versions':{v:{k:report['versions'][v][k] for k in ('workload_completed','none_entry_count','cross_pid_retained_union_count','successful_fallback_count','changed_syscall_number_count','corrected_cross_pid_fallback_count')} for v in ('6.8','6.12')}}))
    raise SystemExit(0 if completed and positive else 2)

if __name__=='__main__':main()
