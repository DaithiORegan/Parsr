"""Union remote and local job history on GitHub Actions push collisions."""
import json
import subprocess
from pathlib import Path

path=Path('data/state.json')
local=json.loads(path.read_text(encoding='utf-8'))
subprocess.run(['git','fetch','origin','main'],check=True)
try:
    remote=json.loads(subprocess.check_output(['git','show','origin/main:data/state.json'],text=True))
except subprocess.CalledProcessError:
    remote={'seen':{},'baselined_sources':[],'backfill_sent':[]}
seen=dict(remote.get('seen',{}))
seen.update(local.get('seen',{}))
result=dict(remote)
result.update(local)
# Never replace the entire remote index with an older scanner snapshot.
index=dict(remote.get('job_index',{}))
for jid, record in local.get('job_index',{}).items():
    previous=index.get(jid)
    if previous is None or record.get('last_seen','') >= previous.get('last_seen',''):
        index[jid]=record
result['job_index']=index
result['seen']=seen
result['baselined_sources']=sorted(set(local.get('baselined_sources',[]))|set(remote.get('baselined_sources',[])))
result['backfill_sent']=sorted(set(local.get('backfill_sent',[]))|set(remote.get('backfill_sent',[])))
for key in ('backfill_by_channel','alert_sent_by_channel','delivered_by_channel'):
    merged={}
    for name in set(remote.get(key,{}))|set(local.get(key,{})):
        merged[name]=sorted(set(remote.get(key,{}).get(name,[]))|set(local.get(key,{}).get(name,[])))
    result[key]=merged
result['initialized']=bool(local.get('initialized') or remote.get('initialized'))
subprocess.run(['git','reset','--hard','origin/main'],check=True)
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
