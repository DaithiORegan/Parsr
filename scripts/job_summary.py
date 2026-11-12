"""Short, source-grounded role briefs for every exported vacancy. No API required."""
import re

RESP = re.compile(r'^(?:key |main |core )?(?:responsibilities|duties|what you(?:[’\']ll| will) (?:do|be doing)|your (?:role|responsibilities)|the role involves|job responsibilities)\s*[:–-]?$', re.I)
REQ = re.compile(r'^(?:minimum |essential |key )?(?:requirements|qualifications|what (?:you(?:[’\']ll| will) need|we(?:[’\']re| are) looking for)|skills(?: and experience)?|experience and qualifications|about you|your (?:skills|profile))\s*[:–-]?$', re.I)
PREFERRED = re.compile(r'^(?:preferred|desirable|nice.to.have|bonus)', re.I)
OTHER = re.compile(r'^(?:about (?:us|the company|\w+)|benefits|what we offer|our offer|equal opportunit|why (?:join|work)|compensation|salary|description|apply|application process)', re.I)
ACTION = re.compile(r'^(?:provide|support|troubleshoot|manage|maintain|develop|deliver|monitor|analyse|analyze|investigate|configure|administer|document|assist|design|implement|coordinate|resolve|work with|ensure|perform|lead|build|review|protect|respond|diagnose|provision|install|test|report|escalate|help|use)\b', re.I)
NEED = re.compile(r'\b(?:required|must|experience|qualification|degree|certification|proficien|familiarity|knowledge of|understanding of|ability to|reside|right to work|work authori[sz]ation)\b', re.I)
MONEY = re.compile(r'(?:(?:€|£|\$|EUR\s*|GBP\s*|USD\s*)\s*\d[\d,.]*(?:\s*[kK])?(?:\s*(?:-|–|—|to)\s*(?:(?:€|£|\$|EUR|GBP|USD)\s*)?\d[\d,.]*(?:\s*[kK])?)?|\d[\d,.]*(?:\s*[kK])?\s*(?:-|–|—|to)\s*\d[\d,.]*(?:\s*[kK])?\s*(?:EUR|GBP|USD))(?:\s*(?:per\s+(?:annum|year|hour|month|day)|/(?:yr|year|hr|hour|month|day)|annually|hourly))?', re.I)

def compact(text, limit=190):
    text = re.sub(r'\s+', ' ', text).strip(' •\t\n')
    if len(text) <= limit:
        return text
    # Show an explicit ellipsis rather than imply the shortened sentence is complete.
    return text[:limit-1].rsplit(' ', 1)[0].rstrip(',;:') + '…'

def unique(items, maximum):
    result, seen = [], set()
    for item in items:
        item = compact(item)
        key = re.sub(r'\W', '', item.lower())
        if len(item) > 12 and key not in seen:
            result.append(item)
            seen.add(key)
        if len(result) >= maximum:
            break
    return result

def summarize(job, text):
    lines = [re.sub(r'^[•\-*\s]+', '', line).strip() for line in text.splitlines() if line.strip()]
    sections = {'responsibilities': [], 'requirements': [], 'role': []}
    current = None
    for line in lines:
        heading = line.strip().rstrip(':')
        if RESP.match(heading):
            current = 'responsibilities'; continue
        if REQ.match(heading):
            current = 'requirements'; continue
        if re.match(r'^about (?:the )?(?:job|role|position)$', heading, re.I):
            current = 'role'; continue
        if len(heading) < 90 and (PREFERRED.match(heading) or OTHER.match(heading)):
            current = None; continue
        if current:
            sections[current].append(line)
    # Structured lists first; unstructured sources fall back to relevant sentences.
    sentences = [s.strip(' •') for s in re.split(r'(?<=[.!?])\s+|\n', text) if len(s.strip()) > 20]
    responsibilities = sections['responsibilities'] or [s for s in sentences if ACTION.match(s) and not NEED.search(s)]
    requirements = sections['requirements'] or [s for s in sentences if NEED.search(s) and not re.search(r'customers|millions|organisations globally', s, re.I)]
    # Keep eligibility restrictions visible even when long requirements lists exist.
    restrictions = [s for s in requirements if re.search(r'\b(?:must|reside|right to work|work authori[sz]ation|commute|clearance)\b', s, re.I)]
    requirements = unique(restrictions[:1] + requirements, 4)
    overview_candidates = sections['role'] or [s for s in sentences if re.search(r'\b(?:you will|you’ll|this role|this position|hiring|seeking|looking for a|responsible for)\b', s, re.I)]
    overview = compact(re.split(r'(?<=[.!?])\s+', overview_candidates[0])[0], 250) if overview_candidates else f"{job.get('title', 'IT role')} at {job.get('company', 'the listed employer')}. Read the requirements below for the available duties and experience."
    pay = compact(str(job.get('salary') or ''), 130) or 'Not listed'
    if pay == 'Not listed':
        for m in MONEY.finditer(text):
            context = text[max(0,m.start()-85):m.end()+65]
            if re.search(r'\b(?:salary|pay|compensation|remuneration|per annum|per year|per hour|annually|hourly|base range)\b|/(?:yr|hr|year|hour)\b', context, re.I):
                pay = compact(m.group(), 130); break
    exp = re.search(r'\b\d{1,2}\s*(?:(?:\+|[-–]\s*\d{1,2})\s*)?(?:years|yrs)(?:\s+of)?(?:\s+(?:relevant|professional|commercial|IT support|technical))?\s+experience\b', text, re.I)
    experience = exp.group() if exp else 'Not stated'
    arrangement = 'Not stated'
    for pattern, label in [
        (r'\bhybrid (?:role|position|working|work|opportunity|model)|\b(?:role|position) is hybrid', 'Hybrid'),
        (r'\b(?:fully|100%) remote|\bremote (?:role|position|working arrangement)|\b(?:role|position) is remote', 'Remote'),
        (r'\bon[- ]site (?:role|position|working)|\b(?:role|position) is on[- ]site', 'On-site')]:
        if re.search(pattern, text, re.I):
            arrangement = label; break
    employment = re.search(r'\b(?:full[- ]time|part[- ]time|permanent|fixed[- ]term|temporary|\d+[- ]month contract)\b', job.get('title','')+' '+text, re.I)
    hours = re.search(r'\b\d{1,2}(?:\.\d+)?\s*(?:[-–]\s*\d{1,2}(?:\.\d+)?)?\s*hours?\s*(?:per|a|/)\s*week\b', text, re.I)
    return {'overview': overview, 'responsibilities': unique(responsibilities, 4), 'requirements': requirements,
            'pay': pay, 'experience': experience, 'arrangement': arrangement,
            'employment': employment.group() if employment else 'Not stated', 'hours': hours.group() if hours else 'Not stated',
            'basis': 'Highlights extracted from the available advert. Open the full description for all conditions.'}
