"""Offline tests showing real API formats can be parsed without live credentials."""
import os
from unittest import TestCase
from unittest.mock import patch
import requests
from job_monitor.collectors import recruitee, jooble, source_availability, rss, remotive, collect


class FakeResponse:
    status_code = 200
    def __init__(self, payload=None, content=b''):
        self.payload = payload
        self.content = content
    def raise_for_status(self):
        return None
    def json(self):
        return self.payload


class AccessTests(TestCase):
    def setUp(self):
        self.src = {"provider":"recruitee","slug":"example","company":"Example"}

    def test_recruitee_xml_country_ie_and_location(self):
        xml = b'''<jobs><job><reference>abc-42</reference><title>IT Support Engineer</title>
        <locations><location><city>Cork</city><country>IE</country></location></locations>
        <url>https://example.recruitee.com/o/it-support</url><posted>2026-11-11</posted>
        </job></jobs>'''
        class Session:
            def get(self, url, timeout):
                self.url=url
                return FakeResponse(content=xml)
        ses=Session(); jobs=recruitee(ses,self.src)
        self.assertEqual(jobs[0]['location'],'Cork, Ireland')
        self.assertEqual(jobs[0]['id'],'recruitee:example:abc-42')
        self.assertTrue(ses.url.endswith('/api/feeds/offers.xml'))

    def test_jooble_api_searches_irish_endpoint_and_parses(self):
        class Session:
            def __init__(self): self.calls=[]
            def post(self,url,json,timeout):
                self.calls.append((url,json))
                return FakeResponse(payload={"jobs":[{"id":5,"title":"Helpdesk Engineer",
                  "location":"Cork, Ireland","link":"https://ie.jooble.org/job/5",
                  "company":"Irish IT Co", "salary":"€35,000"}]})
        with patch.dict(os.environ, {"JOOBLE_API_KEY":"super-secret-test-key"}):
            ses=Session(); jobs=jooble(ses,{"provider":"jooble","slug":"ireland","company":"Jooble"})
        self.assertEqual(len(ses.calls),8)
        self.assertEqual(jobs[0]['company'],'Irish IT Co')
        self.assertEqual(jobs[0]['id'],'jooble:ireland:5')
        self.assertEqual(ses.calls[0][1]['location'],'Ireland')
        self.assertTrue(ses.calls[0][0].startswith('https://ie.jooble.org/api/'))

    def test_jooble_disabled_when_no_credential(self):
        with patch.dict(os.environ, {},clear=True):
            ready,_=source_availability({"provider":"jooble","slug":"ireland"})
        self.assertFalse(ready)

    def test_rss_parser_with_location(self):
        xml=b'''<rss><channel><item><title>IT Technician</title>
        <link>https://jobs.example.ie/abc</link><guid>abc</guid><location>Dublin, Ireland</location></item></channel></rss>'''
        class Session:
            def get(self,url,timeout): return FakeResponse(content=xml)
        j=rss(Session(),{"provider":"rss","slug":"custom","company":"Example","url":"https://jobs.example.ie/rss"})
        self.assertEqual(j[0]['location'],'Dublin, Ireland')

    def test_remotive_rejects_non_europe(self):
        class Session:
            def get(self,url,params=None,timeout=None):
                return FakeResponse(payload={"jobs":[
                  {"id":1,"title":"IT Support Engineer","url":"https://remotive.com/1","candidate_required_location":"USA"},
                  {"id":2,"title":"Network Engineer","url":"https://remotive.com/2","candidate_required_location":"Europe"},
                ]})
        j=remotive(Session(),{"provider":"remotive","slug":"remote","company":"Remotive"})
        self.assertEqual(len(j),1)
        self.assertIn('Ireland-eligible',j[0]['location'])

    def test_source_exception_never_leaks_secret_key(self):
        class Session:
            def post(self,*args,**kwargs):
                raise requests.RequestException('https://ie.jooble.org/api/SENSITIVE_KEY')
        with patch.dict(os.environ, {'JOOBLE_API_KEY':'SENSITIVE_KEY'}):
            jobs,failures,success=collect(Session(),[{'provider':'jooble','slug':'ireland','company':'Jooble'}])
        self.assertNotIn('SENSITIVE_KEY',str(failures))
        self.assertEqual(success,set())
