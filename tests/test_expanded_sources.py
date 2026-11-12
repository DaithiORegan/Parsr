import json
import unittest
from unittest.mock import Mock, patch
from job_monitor.boards import parse_results, search_board
from job_monitor.workday import workday


def html(items, pages=1):
    return '<script>window.__PRELOADED_STATE__["app-unifiedResultlist"] = ' + json.dumps(
        {'searchResults': {'items': items, 'pagination': {'pageCount': pages}}}) + ';</script>'


class ExpandedSources(unittest.TestCase):
    def test_board_pagination_dedup_and_correct_location(self):
        item = {'id': 1, 'title': 'IT Support', 'companyName': 'Employer',
                'location': 'Dublin', 'url': '/job/support/employer-job1', 'textSnippet': 'Support Windows'}
        second = dict(item, id=2, location='Cork', url='/job/support/employer-job2')
        session = Mock()
        session.get.side_effect = [Mock(text=html([item], 2)), Mock(text=html([item, second])),
                                   Mock(text=html([second]))]
        with patch('job_monitor.boards.TERMS', ('it-support',)):
            jobs = search_board(session, {'provider': 'irishjobs', 'slug': 'ireland', 'company': 'IrishJobs', 'search_areas':['ireland']})
        self.assertEqual(len(jobs), 2)
        self.assertIn('?page=2', session.get.call_args_list[1].args[0])
        self.assertEqual(jobs[0]['location'], 'Dublin')
        self.assertTrue(jobs[1]['url'].startswith('https://www.irishjobs.ie/job/'))
        self.assertEqual(jobs[0]['description'], 'Support Windows')

    def test_board_challenge_is_failure_not_empty_success(self):
        with self.assertRaises(ValueError):
            parse_results('<html>Please verify you are human</html>')

    def test_board_zero_results_is_valid(self):
        self.assertEqual(parse_results(html([]))['items'], [])

    def test_workday_filters_ireland_and_loads_requirements(self):
        session = Mock()
        session.post.side_effect = [
            Mock(json=lambda: {'total': 1, 'jobPostings': [], 'facets': [
                {'facetParameter': 'group', 'values': [
                    {'facetParameter': 'locationCountry', 'values': [{'descriptor': 'Ireland', 'id': 'ie'}]}]}]}),
            Mock(json=lambda: {'total': 1, 'jobPostings': [
                {'title': 'Junior IT Support', 'externalPath': '/job/Cork/Support_R1',
                 'locationsText': '2 Locations', 'bulletFields': ['R1']}]}),
        ]
        session.get.return_value = Mock(json=lambda: {'jobPostingInfo': {
            'location': 'Cork', 'additionalLocations': ['Dublin'], 'jobDescription': 'Windows support. 1 year experience.'}})
        jobs = workday(session, {'provider': 'workday', 'slug': 'example', 'company': 'Employer',
                                'url': 'https://example.wd1.myworkdayjobs.com/External'})
        self.assertEqual(session.post.call_args.kwargs['json']['appliedFacets'], {'locationCountry': ['ie']})
        self.assertIn('Cork', jobs[0]['location'])
        self.assertIn('1 year experience', jobs[0]['description'])
        self.assertEqual(jobs[0]['url'], 'https://example.wd1.myworkdayjobs.com/en-US/External/job/Cork/Support_R1')

    def test_workday_rejects_unexpected_host(self):
        with self.assertRaises(ValueError):
            workday(Mock(), {'url': 'https://example.com/External'})

    def test_board_follows_advertised_offset_pagination(self):
        item={'id':1,'title':'Information Security Analyst','companyName':'Example','location':'Carrigtohill','url':'/job/one'}
        first={'searchResults':{'items':[item],'pagination':{'pageCount':2,'links':{'next':'https://www.irishjobs.ie/jobs/cyber-security/in-cork?of=25&action=paging_next'}}}}
        page='<script>window.__PRELOADED_STATE__["app-unifiedResultlist"] = '+json.dumps(first)+';</script>'
        session=Mock();session.get.side_effect=[Mock(text=page),Mock(text=html([dict(item,id=2,url='/job/two')]))]
        with patch('job_monitor.boards.TERMS',('cyber-security',)):
            rows=search_board(session,{'provider':'irishjobs','slug':'ireland','company':'IrishJobs','search_areas':['cork']})
        self.assertEqual(len(rows),2)
        self.assertIn('of=25',session.get.call_args_list[1].args[0])

    def test_bad_query_does_not_discard_other_results(self):
        session=Mock();session.get.side_effect=[Mock(text='<html>No search state</html>'),Mock(text=html([{'id':1,'title':'Security Analyst','companyName':'Example','location':'Cork','url':'/job/one'}]))]
        source={'provider':'irishjobs','slug':'ireland','company':'IrishJobs','search_areas':['cork']}
        with patch('job_monitor.boards.TERMS',('first','second')):
            self.assertEqual(len(search_board(session,source)),1)
        self.assertEqual(source['query_status']['failed_or_truncated'],1)
