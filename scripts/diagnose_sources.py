"""Bounded source checks. Print fixed categories only, never URLs, keys or bodies."""
import json
import os
from urllib.parse import quote

import requests


def failure_category(exc):
    # Inspect locally; exception strings may contain the Jooble key in its URL.
    message = str(exc).lower()
    if isinstance(exc, requests.exceptions.SSLError):
        return 'tls_certificate_error'
    if isinstance(exc, requests.exceptions.Timeout):
        return 'connection_timeout'
    if 'name resolution' in message or 'getaddrinfo' in message:
        return 'dns_resolution_failed'
    if 'connection reset' in message or 'remotedisconnected' in message:
        return 'remote_connection_closed'
    if 'connection refused' in message:
        return 'connection_refused'
    return 'connection_failed'


def response_category(response):
    if response.status_code == 200:
        return 'reachable'
    text = response.text[:16000].lower()
    if response.headers.get('cf-mitigated') == 'challenge' or 'just a moment' in text or 'captcha' in text:
        return 'provider_browser_challenge'
    if 'invalid api key' in text or 'invalid key' in text or 'key is invalid' in text:
        return 'provider_rejected_key'
    if 'ip' in text and ('not allowed' in text or 'blocked' in text or 'whitelist' in text):
        return 'provider_ip_restriction'
    if response.status_code == 429:
        return 'provider_rate_limit'
    if response.status_code in (401, 403):
        return 'provider_access_denied'
    if 300 <= response.status_code < 400:
        return 'redirect_not_followed'
    return 'provider_http_error'


def main():
    key = os.environ.get('JOOBLE_API_KEY', '').strip()
    checks = [('IrishJobs', 'https://www.irishjobs.ie/jobs/it-support/in-cork', None),
              ('Jobs.ie', 'https://www.jobs.ie/jobs/it-support/in-cork', None)]
    if key:
        checks.insert(0, ('Jooble Ireland', 'https://ie.jooble.org/api/' + quote(key, safe=''),
                          {'keywords': 'it support', 'location': 'Cork', 'page': '1', 'ResultOnPage': '1'}))
    else:
        print(json.dumps({'source': 'Jooble Ireland', 'category': 'key_not_configured'}))
    for name, url, payload in checks:
        try:
            response = requests.request('POST' if payload else 'GET', url, json=payload,
                                        timeout=25, allow_redirects=False,
                                        headers={'User-Agent': 'Parsr/1.0 (job source availability check)'})
            result = {'source': name, 'http_status': response.status_code,
                      'category': response_category(response)}
            if name != 'Jooble Ireland' and response.status_code == 200:
                from job_monitor.boards import parse_results
                try:
                    result['sample_jobs'] = len(parse_results(response.text)['items'])
                except ValueError:
                    result['category'] = 'job_search_data_missing'
            print(json.dumps(result))
        except requests.RequestException as exc:
            print(json.dumps({'source': name, 'category': failure_category(exc)}))


if __name__ == '__main__':
    main()
