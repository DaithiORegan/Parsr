"""Start a new public scanner from its public feed without losing retained listings."""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
state=BASE/'data/state.json'
if not state.exists():
    feed=json.loads((BASE/'web/public/jobs.json').read_text())
    records={j['id']:{k:v for k,v in j.items() if k not in ('id','quick_summary','availability','seen_in_latest_scan','description_complete','fit_score','matched_skills')} for j in feed.get('jobs',[])}
    state.parent.mkdir(parents=True,exist_ok=True)
    state.write_text(json.dumps({'initialized':False,'seen':{},'baselined_sources':[], 'last_scan_utc':feed.get('scanned_at'),'job_index':records},indent=2,ensure_ascii=False)+'\n')
    print(f'Preserved {len(records)} public listings before the first scan.')
