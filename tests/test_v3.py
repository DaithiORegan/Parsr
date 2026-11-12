import unittest
from job_monitor.evaluate import evaluate
P={'preferred_titles':['IT Support','SOC Analyst'],'skills':['Windows','Active Directory','Microsoft 365'], 'max_stated_experience_years_for_high_fit':2}
class V3(unittest.TestCase):
    def test_senior_not_strong_with_known_keywords(self):
        j={'title':'Senior IT Support Engineer','location':'Cork, Ireland','description':'Windows Active Directory Microsoft 365'}
        self.assertLess(evaluate(j,'IT Support / Technical',P)['score'],58)
    def test_stated_experience_read_from_text(self):
        j={'title':'IT Support Specialist','location':'Cork','description':'Minimum 5 years experience in IT support required.'}
        a=evaluate(j,'IT Support / Technical',P)
        self.assertIn('5+',a['experience'])
        self.assertLess(a['score'],58)
    def test_no_invented_requirement(self):
        j={'title':'Junior IT Support','location':'Cork','description':''}
        a=evaluate(j,'IT Support / Technical',P)
        self.assertEqual(a['experience'],'Not stated in available listing data')
        self.assertIn('Full duties',a['description'])
    def test_entry_level_preferred(self):
        j={'title':'Junior IT Support','location':'Cork','description':'Windows Active Directory Microsoft 365 helpdesk'}
        self.assertGreater(evaluate(j,'IT Support / Technical',P)['score'],78)
if __name__=='__main__':unittest.main()
