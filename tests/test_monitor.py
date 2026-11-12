import unittest

from job_monitor.filters import matching_category
from job_monitor.collectors import ashby, greenhouse, lever


BASE_FILTERS = {
    "country_locations": ["ireland", "cork", "dublin", "galway"],
    "role_keywords": ["it support", "cybersecurity", "technical support", "network", "security engineer"],
    "exclude_role_keywords": [],
    "include_remote_emea_without_ireland": False,
}


class FakeSession:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, params=None, timeout=25):
        class Response:
            def __init__(self, payload):
                self.payload = payload
            def raise_for_status(self):
                pass
            def json(self):
                return self.payload
        return Response(self.payload)


class Tests(unittest.TestCase):
    def test_irish_support_role(self):
        job = {"title": "IT Support Specialist", "location": "County Cork, Ireland"}
        self.assertEqual(matching_category(job, BASE_FILTERS), "IT Support / Technical")

    def test_exclude_unrelated(self):
        job = {"title": "Marketing Specialist", "location": "Dublin, Ireland"}
        self.assertIsNone(matching_category(job, BASE_FILTERS))

    def test_exclude_foreign_only(self):
        job = {"title": "Technical Support Engineer", "location": "Remote, US"}
        self.assertIsNone(matching_category(job, BASE_FILTERS))

    def test_greenhouse(self):
        session = FakeSession({"jobs": [{"id": 111, "title": "IT Support", "location": {"name": "Cork, Ireland"}, "absolute_url": "https://example.org/jobs/111"}]})
        jobs = greenhouse(session, {"slug": "example", "company": "Example"})
        self.assertEqual(jobs[0]["id"], "greenhouse:example:111")
        self.assertEqual(jobs[0]["location"], "Cork, Ireland")

    def test_ashby_unlisted_is_excluded(self):
        session = FakeSession({"jobs": [
            {"id": "a", "title": "IT Support", "location": "Dublin", "jobUrl": "https://x/a", "isListed": True},
            {"id": "b", "title": "IT Support", "location": "Dublin", "jobUrl": "https://x/b", "isListed": False},
        ]})
        jobs = ashby(session, {"slug": "example", "company": "Example"})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], "ashby:example:a")

    def test_lever(self):
        session = FakeSession([{"id": "xyz", "text": "Network Technician", "categories": {"location": "Dublin"}, "hostedUrl": "https://example.org/job"}])
        jobs = lever(session, {"slug": "example", "company": "Example"})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Network Technician")


if __name__ == "__main__":
    unittest.main()

# v2 provider support. Uses the same offline fake session as the original tests.
class V2Tests(unittest.TestCase):
    def test_smartrecruiters_ie_country(self):
        from job_monitor.collectors import smartrecruiters
        payload = {'content': [{'id':'99','name':'IT Support Engineer',
                    'location':{'city':'Cork','country':'IE'},
                    'releasedDate':'2026-11-11T08:00:00Z'}], 'totalFound': 1}
        jobs = smartrecruiters(FakeSession(payload), {'slug':'example','company':'Example'})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['location'], 'Cork, Ireland')
        self.assertEqual(jobs[0]['id'], 'smartrecruiters:example:99')
