"""Bounded source checks. Print fixed categories only, never URLs, keys or bodies."""
import json
import os
import re
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
    if any(phrase in text for phrase in ('invalid api key', 'invalid key', 'key is invalid',
                                         'api key not found', 'api key is not found')):
        return 'provider_rejected_key'
    if any(phrase in text for phrase in ('key is disabled', 'key is inactive', 'key is blocked', 'key has expired')):
        return 'provider_key_not_active'
    if any(phrase in text for phrase in ('quota exceeded', 'limit exceeded', 'daily limit', 'requests limit', 'too many requests')):
        return 'provider_rate_limit'
    if 'ip' in text and ('not allowed' in text or 'blocked' in text or 'whitelist' in text):
        return 'provider_ip_restriction'
    if response.status_code == 429:
        return 'provider_rate_limit'
    if response.status_code in (401, 403):
        return 'provider_access_denied'
    if 300 <= response.status_code < 400:
        return 'redirect_not_followed'
    return 'provider_http_error'


def response_evidence(response):
    """Expose only predefined labels, even if a provider echoes a credential."""
    text = response.text[:16000].lower()
    patterns = {'mentions_api_key': r'api[ _-]?key', 'mentions_quota': r'\bquota\b',
                'mentions_limit': r'\blimit\b', 'mentions_expired': r'\bexpired\b',
                'mentions_disabled': r'\b(?:disabled|inactive)\b',
                'mentions_invalid': r'\binvalid\b', 'mentions_forbidden': r'\bforbidden\b',
                'mentions_country': r'\bcountry\b', 'mentions_ip_address': r'\bip(?: address)?\b',
                'mentions_domain': r'\bdomain\b', 'mentions_access_denied': r'access (?:is )?denied'}
    mime = response.headers.get('Content-Type', '').lower()
    return {'response_format': 'json' if 'json' in mime else 'html' if 'html' in mime else 'other',
            'signals': [label for label, pattern in patterns.items() if re.search(pattern, text)]}


def main():
    key = os.environ.get('JOOBLE_API_KEY', '').strip()
    checks = [('IrishJobs', 'https://www.irishjobs.ie/jobs/it-support/in-cork', None),
              ('Jobs.ie', 'https://www.jobs.ie/jobs/it-support/in-cork', None)]
    if key:
        checks.insert(0, ('Jooble Ireland', 'https://ie.jooble.org/api/' + quote(key, safe=''),
                          {'keywords': 'it support', 'location': 'Cork', 'page': '1', 'ResultOnPage': '1'}))
    else:
        print(json.dumps({'source': 'Jooble Ireland', 'category': 'key_not_configured'}))
    if os.environ.get('DIAGNOSTIC_SOURCE') == 'jooble':
        checks = [check for check in checks if check[0] == 'Jooble Ireland']
    for name, url, payload in checks:
        try:
            response = requests.request('POST' if payload else 'GET', url, json=payload,
                                        timeout=25, allow_redirects=False,
                                        headers={'User-Agent': 'Parsr/1.0 (job source availability check)'})
            result = {'source': name, 'http_status': response.status_code,
                      'category': response_category(response)}
            if response.status_code != 200:
                result.update(response_evidence(response))
            if name == 'Jooble Ireland' and response.status_code == 200:
                try:
                    data = response.json()
                    if not isinstance(data, dict) or not isinstance(data.get('jobs'), list):
                        raise ValueError('Unexpected job payload')
                    result['sample_jobs'] = len(data['jobs'])
                except ValueError:
                    result['category'] = 'invalid_jobs_payload'
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
