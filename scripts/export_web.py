"""Export the saved scanner index; keep full text for evidence-based analysis."""
import json
import html
from scripts.job_summary import summarize
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parents[1]

def readable_text(value):
    # Decode before parsing: feeds sometimes HTML-encode the entire description.
    value = str(value or '')
    for _ in range(4):
        decoded = html.unescape(value)
        if decoded == value:
            break
        value = decoded
    class DescriptionParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
            self.hidden = 0
        def handle_starttag(self, tag, attrs):
            if tag in ('script', 'style'):
                self.hidden += 1
            if not self.hidden and tag in ('p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'br'):
                self.parts.append('\n\n')
            if not self.hidden and tag == 'li':
                self.parts.append('\n• ')
        def handle_endtag(self, tag):
            if tag in ('script', 'style'):
                self.hidden = max(0, self.hidden - 1)
            if not self.hidden and tag in ('p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol'):
                self.parts.append('\n\n')
        def handle_data(self, data):
            if not self.hidden:
                self.parts.append(data)
    parser = DescriptionParser()
    parser.feed(value)
    import re
    return re.sub(r'\n{3,}', '\n\n', ''.join(parser.parts)).strip()

def seen_in_scan(record, state):
    if not record.get('last_seen') or not state.get('last_scan_utc'):
        return False
    try:
        seen = datetime.fromisoformat(record['last_seen'])
        scanned = datetime.fromisoformat(state['last_scan_utc'])
        return abs((scanned - seen).total_seconds()) < 600
    except (ValueError, TypeError):
        return False

def export(state):
    jobs = []
    for jid, j in state.get('job_index', {}).items():
        if not str(j.get('url', '')).startswith(('https://', 'http://')):
            continue
        text = readable_text(j.get('full_description') or j.get('description', ''))
        title = j.get('title', '')
        category = j.get('category', 'Other IT')
        if category in ('IT Support / Technical','Graduate / Junior') and 'analyst' in title.lower():
            category = 'Analyst'
        elif category == 'Graduate / Junior':
            category = 'Graduate & Junior'
        elif category == 'IT Support / Technical':
            category = 'IT Support'
        elif category == 'Networking / Infrastructure':
            category = 'Cloud & Infrastructure'
        jobs.append(dict(j, id=jid, category=category, description=text,
                         description_complete=bool(j.get('full_description')),
                         seen_in_latest_scan=seen_in_scan(j, state),
                         quick_summary=summarize(j, text)))
    jobs.sort(key=lambda j: -j.get('fit_score', 0))
    return {'scanned_at':state.get('last_scan_utc'), 'exported_at':datetime.now(timezone.utc).isoformat(), 'jobs':jobs}

if __name__ == '__main__':
    out = BASE / 'web/public/jobs.json'
    out.write_text(json.dumps(export(json.loads((BASE/'data/state.json').read_text())), ensure_ascii=False))
    print(f'Exported scanner index to {out.name}')
