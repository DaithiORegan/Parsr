"""Import public job data from Parsr; never transfer secrets, CVs or delivery history."""
import json
from datetime import datetime, timezone
import time
from pathlib import Path
from urllib.request import Request, urlopen

BASE=Path(__file__).resolve().parents[1]
URL='https://raw.githubusercontent.com/DaithiORegan/Parsr/main/web/public/jobs.json'
FIELDS=('title','company','location','url','provider','salary','posted','description','full_description','last_seen','first_indexed_at','category','experience')

def merge_feed(state, feed):
    if not isinstance(feed.get('jobs'),list) or not feed.get('scanned_at'):
        raise ValueError('Public snapshot is missing jobs or scan time')
    incoming=datetime.fromisoformat(feed['scanned_at'].replace('Z','+00:00'))
    previous=state.get('last_scan_utc')
    if previous and incoming < datetime.fromisoformat(previous.replace('Z','+00:00')):
        return state, False
    result=dict(state);index=dict(state.get('job_index',{}))
    for job in feed['jobs']:
        if not isinstance(job,dict) or not isinstance(job.get('id'),str) or not isinstance(job.get('url'),str) or not job['url'].startswith(('http://','https://')):
            raise ValueError('Invalid public job record')
        current=index.get(job['id'],{})
        if current.get('last_seen','') > job.get('last_seen',''):
            continue
        index[job['id']]={k:job[k] for k in FIELDS if k in job}
    result['job_index']=index
    result['last_scan_utc']=feed['scanned_at']
    result['scan_health']=feed.get('scan_health',{})
    result['job_feed_source']='DaithiORegan/Parsr'
    return result, result != state

def main():
    request=Request(URL+'?refresh='+str(time.time_ns()),headers={'User-Agent':'Parsr-website-feed-sync','Cache-Control':'no-cache'})
    with urlopen(request,timeout=60) as response:
        raw=response.read(24*1024*1024+1)
    if len(raw)>24*1024*1024:raise ValueError('Public feed exceeds size limit')
    feed=json.loads(raw)
    path=BASE/'data/state.json'
    state=json.loads(path.read_text()) if path.exists() else {'seen':{},'initialized':False,'baselined_sources':[]}
    merged,changed=merge_feed(state,feed)
    if changed:
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(merged,indent=2,ensure_ascii=False)+'\n');tmp.replace(path)
    print(f"Public feed checked: {feed['scanned_at']}; {len(merged.get('job_index',{}))} retained listings; changed={changed}")

if __name__=='__main__':main()
