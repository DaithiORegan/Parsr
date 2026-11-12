export const ROLE_TYPES = [
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
