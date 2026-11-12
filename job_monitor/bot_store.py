"""Local persistent state and parsing for the PC-hosted application tracker."""
import hashlib
import json
import re
import sqlite3
from urllib.parse import urlparse
from job_monitor.delivery import keys

def jobs_from_embeds(embeds):
    result = []
    seen = set()
    for embed in embeds:
        title = embed.get('title')
        description = embed.get('description','')
        url = embed.get('url')
        if not url:
            match = re.search(r'\*\*Apply:\*\*.*?(https?://[^\s)]+)', description)
            url = match.group(1) if match else ''
        parsed = urlparse(url)
        if not title or parsed.scheme not in ('http','https') or not parsed.netloc:
            continue
        def field(name):
            match = re.search(r'\*\*'+name+r':\*\*\s*([^\n]+)',description)
            return match.group(1).strip() if match else ''
        company, location = field('Company'), field('Location')
        if not company and ' · ' in description.split('\n')[0]:
            company,location=description.split('\n')[0].split(' · ',1)
        job={'title':title,'company':company,'location':location,'url':url}
        identities=keys(job)
        identity=next((k for k in sorted(identities) if k.startswith('job:')),next(iter(sorted(identities))))
        key=hashlib.sha256(identity.encode()).hexdigest()
        if key in seen:continue
        seen.add(key)
        result.append(dict(job,key=key,embed=embed))
    return result

class Store:
    def __init__(self, path):
        self.db=sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS companions (source_id TEXT PRIMARY KEY, companion_id TEXT NOT NULL, job_keys TEXT NOT NULL, channel_id TEXT NOT NULL DEFAULT '0');
        CREATE TABLE IF NOT EXISTS applications (user_id TEXT NOT NULL, job_key TEXT NOT NULL, message_id TEXT, PRIMARY KEY(user_id,job_key));''')
        if 'channel_id' not in {row[1] for row in self.db.execute('PRAGMA table_info(companions)')}:
            self.db.execute("ALTER TABLE companions ADD COLUMN channel_id TEXT NOT NULL DEFAULT '0'")
            self.db.commit()
    def tracked_jobs(self,channel):
        result=set()
        for row in self.db.execute('SELECT job_keys FROM companions WHERE channel_id=?',(str(channel),)):
            result.update(json.loads(row[0]))
        return result
    def job(self,key):
        row=self.db.execute('SELECT data FROM jobs WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None
    def save_jobs(self,jobs,source_url):
        with self.db:
            for job in jobs:
                self.db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)',(job['key'],json.dumps(dict(job,source_url=source_url))))
    def companion(self,source):
        return self.db.execute('SELECT companion_id FROM companions WHERE source_id=?',(str(source),)).fetchone()
    def save_companion(self,source,companion,jobs,channel=0):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO companions(source_id,companion_id,job_keys,channel_id) VALUES (?,?,?,?)',(str(source),str(companion),json.dumps([j['key'] for j in jobs]),str(channel)))
    def companions(self):
        return self.db.execute('SELECT companion_id,job_keys FROM companions').fetchall()
    def application(self,user,key):
        row=self.db.execute('SELECT message_id FROM applications WHERE user_id=? AND job_key=?',(str(user),key)).fetchone()
        return row[0] if row else None
    def mark_application(self,user,key,message):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO applications VALUES (?,?,?)',(str(user),key,str(message)))
