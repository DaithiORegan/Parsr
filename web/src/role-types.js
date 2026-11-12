export const ROLE_TYPES = [
  {"id": "admin", "label": "Administration / Office", "terms": ["administrator", "administrative", "receptionist", "office assistant", "office manager", "executive assistant", "personal assistant"]},
  {"id": "finance", "label": "Finance / Accounting", "terms": ["accountant", "accounting", "finance", "payroll", "bookkeeper", "accounts payable", "accounts receivable", "financial analyst", "credit controller"]},
  {"id": "hr", "label": "HR / Recruitment", "terms": ["human resources", "hr advisor", "hr manager", "hr business", "recruiter", "recruitment", "talent acquisition", "people operations"]},
  {"id": "sales", "label": "Sales / Marketing", "terms": ["sales", "marketing", "account executive", "business development", "digital marketing", "brand manager", "commercial manager"]},
  {"id": "care", "label": "Healthcare / Social Care", "terms": ["nurse", "nursing", "healthcare assistant", "care assistant", "social care", "social worker", "pharmacist", "physiotherapist", "occupational therapist"]},
  {"id": "retail", "label": "Retail / Hospitality", "terms": ["retail", "store manager", "shop assistant", "customer assistant", "chef", "waiter", "waitress", "barista", "bartender", "hotel", "hospitality", "housekeeping"]},
  {"id": "operations", "label": "Operations / Manufacturing", "terms": ["warehouse", "logistics", "supply chain", "production operator", "manufacturing", "procurement", "delivery driver", "forklift", "general operative", "quality technician"]},
  {"id": "construction", "label": "Construction / Trades", "terms": ["electrician", "plumber", "carpenter", "construction", "quantity surveyor", "site manager", "civil engineer", "maintenance technician", "mechanic"]},
  {"id": "education", "label": "Education / Training", "terms": ["teacher", "lecturer", "tutor", "training coordinator", "early years", "childcare", "special needs assistant"]},
  {"id": "customer", "label": "Customer Service", "terms": ["customer service", "customer care", "customer support", "call centre", "contact centre"]},

  {id:'it-support',label:'IT Support / Helpdesk',terms:['it support','technical support','helpdesk','help desk','service desk','desktop support','deskside','it technician','support engineer']},
  {id:'soc',label:'SOC / Security Analyst',terms:['soc analyst','security analyst','security operations','incident response','threat analyst','cyber analyst']},
  {id:'cybersecurity',label:'Cybersecurity / GRC',terms:['cyber','security engineer','grc','governance risk','penetration','information security','vulnerability','iam']},
  {id:'network',label:'Network Engineer / NOC',terms:['network engineer','network administrator','network technician','noc','network support','network analyst']},
  {id:'systems',label:'Systems Administrator',terms:['systems administrator','system administrator','sysadmin','it administrator','systems engineer','infrastructure engineer']},
  {id:'cloud',label:'Cloud Engineer / DevOps',terms:['cloud','devops','site reliability','sre','platform engineer','azure engineer','aws engineer']},
  {id:'data',label:'Data / BI Analyst',terms:['data analyst','business intelligence','bi analyst','analytics','reporting analyst','data scientist','data engineer']},
  {id:'business',label:'Business / Systems Analyst',terms:['business analyst','systems analyst','system analyst','functional analyst','it analyst']},
  {id:'software',label:'Software Developer',terms:['software','developer','programmer','full stack','fullstack','frontend','backend','front end','back end']},
  {id:'qa',label:'QA / Test Engineer',terms:['qa engineer','quality assurance','test engineer','software tester','test analyst','automation tester']},
  {id:'graduate',label:'Graduate / Entry Level',terms:['graduate','junior','entry level','trainee','apprentice','intern']},
];
export function roleRelevance(job, id) {
  if(!id) return 1;
  const type=ROLE_TYPES.find(t=>t.id===id);
  if(!type) return 0;
  const title=String(job.title||'').toLowerCase().replace(/[-/]/g,' ');
  return type.terms.reduce((score,term)=>{
    const escaped=term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    return score+(new RegExp('(?:^|\\W)'+escaped+'(?:$|\\W)','i').test(title)?term.length+10:0);
  },0);
}
