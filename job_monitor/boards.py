"""Public Jobs.ie and IrishJobs search pages; no login or challenge bypass."""
import json
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

TERMS = ('it-support', 'technical-support', 'service-desk', 'desktop-support',
         'systems-administrator', 'network-engineer', 'cyber-security',
         'soc-analyst', 'it-graduate', 'cloud-engineer', 'it-technician', 'qa-engineer', 'administration', 'accountant', 'human-resources', 'sales', 'marketing', 'nursing', 'retail', 'hospitality', 'warehouse', 'construction', 'teacher', 'customer-service')


class SearchState(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.parts = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.in_script = True
            self.parts = []

    def handle_data(self, data):
        if self.in_script:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.in_script:
            self.scripts.append(''.join(self.parts))
            self.in_script = False


def parse_results(html):
    parser = SearchState()
    parser.feed(html)
    marker = 'window.__PRELOADED_STATE__["app-unifiedResultlist"] ='
    for script in parser.scripts:
        if marker in script:
            # Decode data only, never execute website JavaScript.
            state = json.JSONDecoder().raw_decode(script.split(marker, 1)[1].lstrip())[0]
            results = state.get('searchResults')
            if not isinstance(results, dict) or not isinstance(results.get('items'), list):
                raise ValueError('Job board search schema changed')
            return results
    raise ValueError('Job board search data missing; source may be blocked or changed')


def search_board(session, source):
    from job_monitor.collectors import _clean_job
    host = {'irishjobs': 'www.irishjobs.ie', 'jobsie': 'www.jobs.ie'}[source['provider']]
    base = 'https://' + host
    jobs = {}
    failed_queries = 0
    succeeded_queries = 0
    source["query_status"] = {}
    for term in TERMS:
        # National queries support visitor-selected locations across Ireland.
        for area in (source.get('search_areas') or (('ireland','cork','dublin','galway','limerick','kerry') if term in ('cyber-security','soc-analyst','it-support','network-engineer') else ('ireland',))):
            try:
                url = f'{base}/jobs/{term}/in-{area}'
                visited = set()
                for page in range(20):
                    if url in visited:
                        raise ValueError('Job board pagination loop')
                    visited.add(url)
                    response = session.get(url, timeout=25)
                    response.raise_for_status()
                    results = parse_results(response.text)
                    for item in results['items']:
                        if not item.get('id') or not item.get('title') or not item.get('url'):
                            continue
                        link = urljoin(base, item['url'])
                        if urlparse(link).hostname != host:
                            continue
                        job = _clean_job(source['provider'], source, str(item['id']), item['title'],
                                         [item.get('location') or 'Unspecified'], link,
                                         salary=item.get('salary') or '', posted=item.get('datePosted') or '',
                                         description=item.get('textSnippet') or '')
                        job['company'] = item.get('companyName') or 'Unknown company'
                        jobs[job['id']] = job
                    pagination = results.get('pagination') or {}
                    if page + 1 >= int(pagination.get('pageCount', 1)):
                        break
                    next_link = pagination.get('links', {}).get('next')
                    if isinstance(next_link, str) and next_link:
                        next_url = urljoin(base, next_link)
                        parsed = urlparse(next_url)
                        if parsed.scheme != 'https' or parsed.hostname != host:
                            raise ValueError('Unexpected pagination host')
                        url = next_url
                    else:
                        url = f'{base}/jobs/{term}/in-{area}?page={page + 2}'
                else:
                    raise ValueError('Job board search exceeds pagination budget')
                succeeded_queries += 1
            except ValueError:
                failed_queries += 1
                print(f"[PARTIAL] {source['provider']}: skipped search with unavailable result data")
    source['query_status'] = {'succeeded':succeeded_queries,'failed_or_truncated':failed_queries}
    if failed_queries and not jobs:
        raise ValueError('No usable job-board result data')
    return list(jobs.values())
