import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import requests
from scripts.diagnose_sources import failure_category, main, response_category, response_evidence


class SourceDiagnostics(unittest.TestCase):
    def test_classifies_timeout_and_tls_separately(self):
        self.assertEqual(failure_category(requests.Timeout('secret')), 'connection_timeout')
        self.assertEqual(failure_category(requests.exceptions.SSLError('secret')), 'tls_certificate_error')

    def test_distinguishes_rate_limit_key_and_generic_forbidden(self):
        for status, body, expected in [(403, 'Invalid API key', 'provider_rejected_key'),
                                       (403, 'Forbidden', 'provider_access_denied'),
                                       (429, 'Too many requests', 'provider_rate_limit')]:
            response=Mock(status_code=status, text=body, headers={})
            self.assertEqual(response_category(response), expected)

    def test_diagnostic_never_prints_secret_exception_or_response_body(self):
        secret='SENSITIVE_TEST_KEY'
        response=Mock(status_code=403, text='Forbidden '+secret, headers={})
        output=io.StringIO()
        with patch.dict(os.environ, {'JOOBLE_API_KEY':secret}), \
             patch('scripts.diagnose_sources.requests.request', side_effect=[response, requests.ConnectionError(secret), requests.Timeout(secret)]) as request, \
             redirect_stdout(output):
            main()
        self.assertNotIn(secret, output.getvalue())
        self.assertEqual(len(output.getvalue().splitlines()),3)
        self.assertEqual(json.loads(output.getvalue().splitlines()[0])['http_status'],403)
        self.assertFalse(request.call_args_list[0].kwargs['allow_redirects'])

    def test_response_evidence_contains_only_fixed_labels(self):
        response=Mock(status_code=403, text='API key SENSITIVE_KEY is invalid. Quota limit.', headers={'Content-Type':'application/json'})
        result=response_evidence(response)
        self.assertEqual(result['response_format'],'json')
        self.assertIn('mentions_api_key',result['signals'])
        self.assertNotIn('SENSITIVE_KEY',str(result))

    def test_jooble_only_check_uses_one_request(self):
        response=Mock(status_code=403, text='Forbidden',headers={})
        output=io.StringIO()
        with patch.dict(os.environ,{'JOOBLE_API_KEY':'TEST_KEY','DIAGNOSTIC_SOURCE':'jooble'}), \
             patch('scripts.diagnose_sources.requests.request',return_value=response) as request, redirect_stdout(output):
            main()
        self.assertEqual(request.call_count,1)
        self.assertEqual(json.loads(output.getvalue())['source'],'Jooble Ireland')
