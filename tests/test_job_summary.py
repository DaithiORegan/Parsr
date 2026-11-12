import unittest
from scripts.job_summary import summarize
from scripts.export_web import export
class JobSummary(unittest.TestCase):
    def test_source_grounded_quick_facts(self):
        text='''About the Job
You will provide technical support to employees. Company marketing goes here.
Responsibilities
Provide Windows and macOS support
Provision laptops and user accounts
Requirements
2+ years of experience in IT support
Knowledge of DNS and DHCP
Candidates must reside in Ireland and commute to Cork
This is a hybrid position.
Salary: €40,000–€48,000 per year.'''
        result=summarize({'title':'Support','company':'Example'}, text)
        self.assertEqual(result['overview'],'You will provide technical support to employees.')
        self.assertIn('2+', result['experience'])
        self.assertEqual(result['pay'],'€40,000–€48,000 per year')
        self.assertEqual(result['arrangement'],'Hybrid')
        self.assertIn('reside in Ireland',result['requirements'][0])
        self.assertLessEqual(len(result['responsibilities']),4)
    def test_does_not_invent_missing_pay_or_call_remote_user_support_remote_work(self):
        result=summarize({'title':'Support','company':'Example'}, 'Support remote users. Our software serves 150 countries and 2 million customers.')
        self.assertEqual(result['pay'],'Not listed')
        self.assertEqual(result['arrangement'],'Not stated')
        self.assertEqual(result['experience'],'Not stated')
    def test_every_exported_current_and_new_role_receives_a_brief(self):
        records={'old':{'url':'https://example.com/old','title':'IT Support','description':'Short source snippet'}}
        a=export({'job_index':records})['jobs']
        self.assertIn('quick_summary',a[0])
        records['new']={'url':'https://example.com/new','title':'Data Analyst','full_description':'<h3>Responsibilities</h3><ul><li>Analyse SQL datasets and report insights</li></ul><h3>Requirements</h3><p>SQL experience required</p>','salary':'€50,000 - €60,000'}
        b=export({'job_index':records})['jobs']
        self.assertTrue(all('quick_summary' in j for j in b))
        new=next(j for j in b if j['id']=='new')
        self.assertEqual(new['quick_summary']['pay'],'€50,000 - €60,000')
        self.assertIn('SQL',new['quick_summary']['responsibilities'][0])
