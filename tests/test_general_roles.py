import json, unittest
from pathlib import Path
from job_monitor.filters import matching_category
class GeneralRoles(unittest.TestCase):
    def test_non_tech_roles_are_collected_and_categorized(self):
        filters=json.loads((Path(__file__).resolve().parents[1]/'config/filters.json').read_text())
        for title,category in [('Accountant','Finance'),('Registered Nurse','Healthcare & Care'),('Office Administrator','Administration'),('Warehouse Operative','Operations & Logistics'),('Retail Store Manager','Retail & Hospitality'),('HR Manager','HR & Recruitment')]:
            with self.subTest(title=title):self.assertEqual(matching_category({'title':title,'location':'Dublin, Ireland'},filters),category)
        self.assertEqual(matching_category({'title':'Systems Administrator','location':'Galway, Ireland'},filters),'Networking / Infrastructure')
