"""Read-only, bounded1Hz host paging/PSI telemetry. Not an admission gate."""
from collections import deque
import os
from pathlib import Path


def read_paging():
    counters={k:int(v) for k,v in (line.split() for line in Path('/proc/vmstat').read_text().splitlines())}
    pressure={}
    for line in Path('/proc/pressure/memory').read_text().splitlines():
        name,*fields=line.split();row=dict(x.split('=') for x in fields)
        pressure[name]={'avg10':float(row['avg10']),'total_us':int(row['total'])}
    return {'pswpin':counters['pswpin'],'pswpout':counters['pswpout'],
        'page_size':os.sysconf('SC_PAGE_SIZE'),'memory_psi':pressure}


class PagingTelemetry:
    def __init__(self,read=read_paging):
        self.read=read;self.rows=deque(maxlen=32);self.last_time=None;self.previous=None;self.count=0
    def sample(self,now):
        if self.last_time is not None and now-self.last_time<1:return
        self.last_time=now;row={'monotonic':now,'admission_gate':False};self.count+=1
        try:
            value=self.read()
            if any(type(value.get(k)) is not int or value[k]<0 for k in ('pswpin','pswpout','page_size')) or value['page_size']==0:
                raise ValueError('INVALID_PAGING_COUNTER')
            for key in ('some','full'):
                psi=value['memory_psi'][key]
                if type(psi['total_us']) is not int or psi['total_us']<0 or not 0<=psi['avg10']<=100:
                    raise ValueError('INVALID_PSI')
            rate=None
            if self.previous is not None:
                elapsed=now-self.previous['monotonic'];old=self.previous['value']
                if elapsed<=0 or value['page_size']!=old['page_size'] or any(value[k]<old[k] for k in ('pswpin','pswpout')):
                    raise ValueError('PAGING_COUNTER_CHANGED_OR_RESET')
                rate=(value['pswpin']-old['pswpin']+value['pswpout']-old['pswpout'])*value['page_size']/elapsed
            row.update(status='OBSERVED',value=value,swap_io_bytes_per_second=rate)
            self.previous={'monotonic':now,'value':value}
        except Exception as exc:row.update(status='UNAVAILABLE',error_class=type(exc).__name__)
        self.rows.append(row)
    def snapshot(self):return {'sample_count':self.count,'max_saved_samples':32,'admission_gate':False,'samples':list(self.rows)}
