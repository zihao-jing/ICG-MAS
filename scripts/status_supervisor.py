"""Keeps STATUS.md alive: whenever a tracked job process is running and the status loop is not, start scripts/status_loop.sh. Polls every 60 seconds.
Tracked jobs: any process whose command line matches `scripts.run_*` or `scripts.pilot_*`. Run once in the background: nohup python -u -m scripts.status_supervisor &
Stop it with: pkill -f scripts.status_supervisor"""
import re,subprocess,sys,time
TRACKED=re.compile(r'scripts\.(run_|pilot_)[a-z0-9_]+')
def should_start(job_running,loop_running):return bool(job_running and not loop_running)
def _ps():
    out=subprocess.run(['ps','-axo','command'],capture_output=True,text=True).stdout.splitlines();return out
def jobs_running(lines):return any(TRACKED.search(l) and 'status_supervisor' not in l and 'pgrep' not in l and 'ps -ax' not in l and 'make_status' not in l for l in lines)
def loop_running(lines):return any('scripts/status_loop.sh' in l and 'pgrep' not in l for l in lines)
def main(poll=60,once=False):
    while True:
        lines=_ps();j,l=jobs_running(lines),loop_running(lines)
        if should_start(j,l):
            subprocess.Popen(['nohup','bash','./scripts/status_loop.sh'],stdout=open('rebuttal/results/batch1/status_loop.log','a'),stderr=subprocess.STDOUT,start_new_session=True)
            print(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'started status loop (a tracked job is running)',flush=True)
        if once:return (j,l)
        time.sleep(poll)
if __name__=='__main__':main(once='--once' in sys.argv)
