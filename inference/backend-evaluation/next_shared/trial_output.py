"""Exclusive per-run stdout/stderr logs with bounded, short terminal progress."""
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import sys
import time
import traceback

STAGES={'asset_read_plan','policy_preflight_start','policy_preflight_verified','verify_assets_start',
        'unload30b_intent','unload30b_confirmed','create_owned_intent','start_owned_intent',
        'owned_container_terminal','trial_failed','resource_threshold_exceeded','owned_cleanup_unconfirmed'}


def exclusive_text(path):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    return os.fdopen(fd,'w',encoding='utf-8',buffering=1)


class ProgressLog:
    def __init__(self,detail,terminal,run,clock=time.monotonic):
        self.detail=detail;self.terminal=terminal;self.run=Path(run);self.clock=clock
        self.pending='';self.last=clock();self.terminal_unavailable=False
    def writable(self):return True
    def flush(self):self.detail.flush()
    def write(self,text):
        self.detail.write(text);self.detail.flush()
        # Terminal parsing never truncates the saved detail file. Oversized
        # individual lines are omitted from terminal forwarding, not treated as success.
        self.pending+=text
        while '\n' in self.pending:
            line,self.pending=self.pending.split('\n',1)
            if len(line)>2*(1<<20):continue
            try:row=json.loads(line)
            except (ValueError,TypeError):continue
            if not isinstance(row,dict):continue
            now=self.clock();event=row.get('event')
            if event in STAGES:
                visible={k:row[k] for k in ('event','elapsed','reason','exit_code','oom_killed') if k in row}
            elif 'status' in row:
                visible={k:row[k] for k in ('status','backend','environment','quality','generation_requests',
                         'generation_request_intents','cleanup_confirmed','reason','elapsed_seconds') if k in row}
                restored=row.get('restoration')
                if restored is not None:visible['restoration']=restored.get('status') if isinstance(restored,dict) else restored
                visible['log_directory']=str(self.run)
            elif now-self.last>=15:
                visible={'event':'progress','elapsed':row.get('elapsed'),'log_directory':str(self.run)}
            else:continue
            self.last=now
            if not self.terminal_unavailable:
                try:self.terminal.write(json.dumps(visible,ensure_ascii=False)+'\n');self.terminal.flush()
                except (OSError,ValueError):self.terminal_unavailable=True
        if len(self.pending)>2*(1<<20):self.pending=''
        return len(text)


class RunOutput:
    def __init__(self):self.exit_code=None
    def finish(self,exit_code):
        if type(exit_code) is not int:raise TypeError('INTEGER_EXIT_CODE_REQUIRED')
        self.exit_code=exit_code


@contextmanager
def capture_run_output(run):
    run=Path(run)
    if any(p.is_symlink() for p in [run,*run.parents]):raise ValueError('SYMLINK_LOG_PATH')
    # Exclusive opens: old output is never replaced, including a partial prior setup.
    stdout=exclusive_text(run/'stdout.log')
    try:stderr=exclusive_text(run/'stderr.log')
    except BaseException:
        try:stdout.close()
        except OSError:pass
        raise
    previous_out,previous_err=sys.stdout,sys.stderr
    progress=ProgressLog(stdout,previous_out,run);result=RunOutput();log_errors=[]
    try:previous_out.write('Detailed logs: '+str(run/'stdout.log')+' ; '+str(run/'stderr.log')+'\n');previous_out.flush()
    except (OSError,ValueError):progress.terminal_unavailable=True
    sys.stdout,sys.stderr=progress,stderr
    try:
        yield result
    except BaseException as exc:
        result.exit_code=130 if isinstance(exc,KeyboardInterrupt) else exc.code if isinstance(exc,SystemExit) and type(exc.code) is int else 1
        try:traceback.print_exc(file=stderr)
        except (OSError,ValueError) as log_exc:log_errors.append(type(log_exc).__name__)
        raise
    finally:
        # Restore globals before any potentially failing I/O, even on disk full.
        sys.stdout,sys.stderr=previous_out,previous_err
        for stream in (stdout,stderr):
            for action in (stream.flush,stream.close):
                try:action()
                except (OSError,ValueError) as exc:log_errors.append(type(exc).__name__)
        try:
            # Logging errors never replace a known trial exit or its exception.
            with exclusive_text(run/'run-output.json') as meta:
                json.dump({'exit_code':result.exit_code,'stdout':'stdout.log','stderr':'stderr.log',
                           'previous_logs_overwritten':False,'log_errors':log_errors,
                           'terminal_unavailable':progress.terminal_unavailable},meta)
        except (OSError,ValueError) as exc:log_errors.append(type(exc).__name__)
        if log_errors:
            try:previous_err.write('Run log finalization incomplete; original outcome preserved. Directory: '+str(run)+'\n')
            except (OSError,ValueError):pass
