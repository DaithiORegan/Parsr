"""Transparent rule-based ranking against candidate_profile.json, not an ATS or LLM score."""
from __future__ import annotations
import html
import re

SENIOR = re.compile(r"\b(senior|sr\.?|principal|staff|lead|director|head of|manager|architect|vp|chief)\b",re.I)
JUNIOR = re.compile(r"\b(junior|graduate|entry.level|associate|trainee|apprentice|intern|level 1|1st line|first.line|l1)\b",re.I)
YEARS = re.compile(r"\b(?:at least|minimum of|minimum|over|more than)?\s*(\d{1,2})\s*(?:\+|to\s*\d+|[-–]\s*\d+)?\s*(?:years|yrs)\s+(?:of\s+)?(?:relevant\s+)?(?:experience|exp)\b", re.I)
YEARS_ALT = re.compile(r"\b(\d{1,2})\s*(?:\+|[-–]\s*\d+)?\s*(?:years|yrs)\s+(?:in|working with|of)\b",re.I)
COMMON = ["active directory", "microsoft 365", "office 365", "windows server", "windows", "powershell", "group policy", "network", "dns", "dhcp", "siem", "soc", "python", "linux", "cybersecurity", "customer service", "technical support", "hardware", "security monitoring", "vulnerability"]

def plain(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]*>", " ", text or ""))
    return " ".join(text.split())

def evaluate(job: dict, category: str, profile: dict) -> dict:
    title = plain(job.get('title',''))
    description = plain(job.get('description',''))
    location = plain(job.get('location',''))
    t = title.casefold(); d = description.casefold(); l = location.casefold()
    years_match = YEARS.search(description) or YEARS_ALT.search(description)
    years = int(years_match.group(1)) if years_match else None
    level = 'Senior / leadership' if SENIOR.search(title) else ('Junior / graduate' if JUNIOR.search(title) else 'Not specified')
    score = 33
    if any(x.casefold() in t for x in profile.get('preferred_titles', [])): score += 21
    if any(x in l for x in ['cork','kerry','tralee','killarney']): score += 13
    elif 'remote' in l and 'ireland' in l: score += 13
    elif 'ireland' in l or any(x in l for x in ['dublin','limerick','galway']): score += 5
    if JUNIOR.search(title): score += 16
    if SENIOR.search(title): score -= 45
    matched = [s for s in profile.get('skills', COMMON) if s.casefold() in (t+' '+d)]
    score += min(21, 3*len(matched))
    if years is not None:
        if years >= 5: score -= 28
        elif years >= 3: score -= 15
        elif years <= profile.get('max_stated_experience_years_for_high_fit',2): score += 6
    if level == 'Senior / leadership': score = min(score, 42)
    if years is not None and years >= 5: score = min(score, 45)
    if not description: score = min(score, 73)
    score = max(0, min(100, score))
    if years is not None: exp = f'{years}+ years mentioned (check advert)'
    else: exp = 'Not stated in available listing data'
    if description:
        desc = description[:240].rsplit(' ',1)[0].strip() if len(description)>240 else description
        desc += '…' if len(description)>len(desc) else ''
    else:
        desc = f'{category} vacancy. Full duties and requirements: open original advert.'
    return {'experience_years':years,'score':score,'level':level,'experience':exp,'description':desc,
            'matched_skills':matched[:6], 'rating':'Strong' if score>=78 else 'Possible' if score>=58 else 'Low',
            'basis':'Heuristic estimate using title, location and any supplied description; not a verified CV match.'}

