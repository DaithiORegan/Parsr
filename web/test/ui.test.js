import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { localJob } from "../src/core.js";
const places = readFileSync(new URL('../src/locations.js', import.meta.url),'utf8').replace(/^import towns.*;$/m,'const towns = '+JSON.stringify(JSON.parse(readFileSync(new URL('../../config/irish_locations.json',import.meta.url),'utf8')))+';').replace(/export /g,'');
const roles = readFileSync(new URL('../src/role-types.js', import.meta.url),'utf8').replace(/export /g,'');
const formatter = readFileSync(new URL('../src/description.js', import.meta.url), 'utf8').replace('export function', 'function');
const source = readFileSync(
  new URL("../src/app.js", import.meta.url),
  "utf8",
).replace(/^import .*;\n/gm, "");
const jobs = [
  {
    id: "a",
    title: "IT Support <script>unsafe</script>",
    company: "A Ltd",
    location: "Cork",
    category: "IT Support",
    description: "Help people",
    url: "https://example.com/a",
    fit_score: 85,
  },
  {
    id: "b",
    title: "Security Analyst",
    company: "B Ltd",
    location: "Tralee",
    category: "Cybersecurity",
    description: "SOC role",
    url: "https://example.com/b",
    fit_score: 80,
  },
  {
    id: "c",
    title: "Data Analyst",
    company: "C Ltd",
    location: "Dublin",
    category: "Analyst",
    description: "Data",
    url: "https://example.com/c",
    fit_score: 75,
  },
];
jobs[0].quick_summary = {overview:'Provide employee IT support.',responsibilities:['Resolve user issues'],requirements:['Windows experience'],pay:'Not listed',experience:'2+ years',arrangement:'Hybrid',employment:'Not stated',hours:'Not stated',basis:'Highlights from the advert.'};
async function ui(hash = "#/jobs", workspace = {}, analyze = null, fixture = {}) {
  const dom = new JSDOM('<div id="app"></div><div id="toast"></div>', {
    url: "http://localhost/" + hash,
    runScripts: "outside-only",
  });
  const w = dom.window;
  if (fixture.seen) w.localStorage.setItem('parsr-seen-jobs-v1', JSON.stringify(fixture.seen));
  let calls = 0;
  w.pdfjs = { GlobalWorkerOptions: {} };
  w.localJob = localJob;
  w.scrollTo = () => {};
  w.fetch = async (url, options) => {
    if (url === "/api/session") return Response.json({owner:workspace.owner ?? true,ai_ready:workspace.ai_ready ?? false});
    if (url === "/jobs.json")
      return Response.json({ jobs: fixture.feedJobs || jobs, scanned_at: new Date().toISOString() });
    if (url === "/api/analyze") {
      calls++;
      const result = analyze ? analyze(JSON.parse(options.body)) : {};
      return result instanceof Response ? result : Response.json(result);
    }
    return Response.json({
      cvs: [],
      status: [],
      analyses: [],
      ai_ready: false,
      ...workspace,
    });
  };
  // Inject only the import dependencies; test the actual application rendering and handlers.
  await w.eval(
    `(async()=>{const pdfjs=window.pdfjs;const localJob=window.localJob;${places};${roles};${formatter};${source}})()`,
  );
  return { w, dom, calls: () => calls };
}

test('Unseen excludes every existing listing, even when seen in a fresh scan', async () => {
  const {w,dom}=await ui('#/unseen');
  assert.equal(w.document.querySelectorAll('.job').length,0);
  assert.match(w.document.querySelector('.empty').textContent,/caught up/);
  assert.match(w.document.querySelector('a[href="#/unseen"].active').textContent,/Unseen \(0\)/);
  dom.window.close();
});

test('new scan additions stay unseen until explicitly opened; seen status survives reload', async () => {
  const feedJobs=[jobs[0],{...jobs[1],first_indexed_at:'2026-11-12T23:00:00Z'}];
  const {w,dom}=await ui('#/unseen',{},null,{feedJobs});
  assert.equal(w.document.querySelectorAll('.job').length,1);
  // Showing the default preview does not count as the user opening the role.
  assert.equal(w.localStorage.getItem('parsr-seen-jobs-v1'),null);
  w.document.querySelector('[data-preview="b"]').click();
  await new Promise(resolve=>setTimeout(resolve,20));
  assert.equal(w.location.hash,'#/job/b');
  const seen=JSON.parse(w.localStorage.getItem('parsr-seen-jobs-v1'));
  assert.deepEqual(seen,['b']);
  w.location.hash='#/unseen';
  await new Promise(resolve=>setTimeout(resolve,20));
  assert.equal(w.document.querySelectorAll('.job').length,0);
  dom.window.close();
  const reopened=await ui('#/unseen',{},null,{feedJobs,seen});
  assert.equal(reopened.w.document.querySelectorAll('.job').length,0);
  reopened.dom.window.close();
});

test('opening a new role from All jobs or a direct link removes it from Unseen', async () => {
  const feedJobs=[{...jobs[0],first_indexed_at:'2026-11-12T23:00:00Z'},jobs[1]];
  for(const route of ['#/jobs','#/job/a']) {
    const {w,dom}=await ui(route,{},null,{feedJobs});
    if(route==='#/jobs') w.document.querySelector('[data-preview="a"]').click();
    assert.equal(JSON.parse(w.localStorage.getItem('parsr-seen-jobs-v1'))[0],'a');
    dom.window.close();
  }
});

test('Unseen updates when a role is opened in another browser tab', async () => {
  const feedJobs=[{...jobs[0],first_indexed_at:'2026-11-12T23:00:00Z'}];
  const {w,dom}=await ui('#/unseen',{},null,{feedJobs});
  w.dispatchEvent(new w.StorageEvent('storage',{key:'parsr-seen-jobs-v1',newValue:'["a"]'}));
  assert.equal(w.document.querySelectorAll('.job').length,0);
  dom.window.close();
});
test("job browser renders real rows, escapes external text, filters by category", async () => {
  const { w, dom } = await ui();
  assert.equal(w.document.querySelectorAll(".job").length, 3);
  assert.equal(w.document.querySelectorAll(".job script").length, 0);
  assert.match(w.document.body.textContent, /<script>unsafe<\/script>/);
  w.document.querySelector('[data-category="Cybersecurity"]').click();
  assert.equal(w.document.querySelectorAll(".job").length, 1);
  assert.match(
    w.document.querySelector(".job").textContent,
    /Security Analyst/,
  );
  dom.window.close();
});
test("Best Fit requires CV reviews instead of duplicating local listings", async () => {
  const { w, dom } = await ui("#/best-fit");
  assert.equal(w.document.querySelectorAll(".job").length, 0);
  assert.match(w.document.body.textContent,/No reviewed matches for these filters/);
  assert.doesNotMatch(
    w.document.querySelector(".jobs").textContent,
    /Data Analyst/,
  );
  dom.window.close();
});
test("CV page has upload, version name, reviewable text and no invented CVs", async () => {
  const { w, dom } = await ui("#/cvs");
  assert.ok(w.document.querySelector("#cv-file"));
  assert.ok(w.document.querySelector("#cv-name"));
  assert.ok(w.document.querySelector("#cv-text"));
  assert.equal(w.document.querySelectorAll(".cv-row").length, 0);
  dom.window.close();
});
test("role detail links to employer and prompts for a CV", async () => {
  const { w, dom } = await ui("#/job/a");
  assert.equal(
    w.document.querySelector(".header-actions a").href,
    "https://example.com/a",
  );
  assert.match(w.document.body.textContent, /Add your CV/);
  assert.match(w.document.body.textContent, /short snippet/);
  dom.window.close();
});

test('opening a role automatically starts one review for an active CV', async () => {
  const dom = new JSDOM('<div id="app"></div><div id="toast"></div>', {
    url: 'http://localhost/#/job/a', runScripts: 'outside-only'
  });
  const w = dom.window;
  w.pdfjs = { GlobalWorkerOptions: {} };
  w.localJob = localJob;
  w.scrollTo = () => {};
  let calls = 0;
  w.fetch = async (url, options) => {
    if (url === '/api/session') return Response.json({owner:true});
    if (url === '/jobs.json') return Response.json({ jobs });
    if (url === '/api/analyze') { calls++; return Response.json({}); }
    return Response.json({ cvs: [{ id: 'cv1', name: 'Support CV' }], status: [], analyses: [], ai_ready: true });
  };
  await w.eval(`(async()=>{const pdfjs=window.pdfjs;const localJob=window.localJob;${places};${roles};${formatter};${source}})()`);
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(calls, 1);
  assert.equal(w.document.querySelector('#active-cv').value, 'cv1');
  dom.window.close();
});

test('selecting a job updates the adjacent description panel', async () => {
  const {w,dom}=await ui();
  w.document.querySelector('[data-preview="b"]').click();
  assert.match(w.document.querySelector('.job-preview h2').textContent,/Security Analyst/);
  assert.match(w.document.querySelector('.job-preview .description').textContent,/SOC role/);
  assert.ok(w.document.querySelector('[data-preview="b"]').closest('.job').classList.contains('selected'));
  dom.window.close();
});

test('By location allows browsing before a location is selected', async () => {
  const {w,dom}=await ui('#/local');
  assert.equal(w.document.querySelectorAll('.job').length,3);
  assert.ok(w.document.querySelector('a[href="#/local"].active'));

  dom.window.close();
});

test('role opens with concise facts and expandable full advert', async () => {
  const {w,dom}=await ui('#/job/a');
  assert.match(w.document.querySelector('.role-brief').textContent,/What you’ll do/);
  assert.match(w.document.querySelector('.brief-facts').textContent,/PayNot listed/);
  assert.match(w.document.querySelector('.brief-facts').textContent,/Experience2\+ years/);
  assert.equal(w.document.querySelector('.full-advert').open,false);
  assert.match(w.document.querySelector('.full-advert').textContent,/Help people/);
  dom.window.close();
});

function matchResult(job, score) {
  return {score,summary:'Review',strengths:[],gaps:[],suggestions:[],limitations:[],job_signature:JSON.stringify([job.title,job.description,job.description_complete])};
}
test('Best Fit uses only the selected CV and current reviewed jobs above threshold',async()=>{
  const workspace={cvs:[{id:'cv1',name:'Support'},{id:'cv2',name:'Security'}],ai_ready:true,
    analyses:[{job_id:'a',cv_id:'cv1',result:matchResult(jobs[0],90)},
      {job_id:'b',cv_id:'cv1',result:matchResult(jobs[1],40)},
      {job_id:'b',cv_id:'cv2',result:matchResult(jobs[1],95)},
      {job_id:'c',cv_id:'cv1',result:matchResult(jobs[2],99)}]};
  const {w,dom}=await ui('#/best-fit',workspace);
  assert.equal(w.document.querySelectorAll('.job').length,2);
  assert.match(w.document.querySelector('.job').textContent,/Data Analyst/);
  const select=w.document.querySelector('#active-cv');select.value='cv2';select.dispatchEvent(new w.Event('change'));
  assert.equal(w.document.querySelectorAll('.job').length,1);
  assert.match(w.document.querySelector('.job').textContent,/Security Analyst/);
  dom.window.close();
});
test('Find best matches reviews unreviewed local roles via analyze and reuses results',async()=>{
  const reviewed=[];
  const {w,dom,calls}=await ui('#/best-fit',{cvs:[{id:'cv1',name:'CV'}],ai_ready:true},body=>{
    reviewed.push(body);return matchResult(jobs.find(j=>j.id===body.job_id),body.job_id==='b'?95:80);
  });
  w.document.querySelector('#find-matches').click();
  await new Promise(resolve=>setTimeout(resolve,30));
  assert.equal(calls(),3);assert.ok(reviewed.every(b=>b.cv_id==='cv1'));
  assert.match(w.document.querySelector('.job').textContent,/Security Analyst/);
  assert.equal(w.document.querySelectorAll('.job').length,3);
  w.document.querySelector('#find-matches').click();
  await new Promise(resolve=>setTimeout(resolve,10));assert.equal(calls(),3);
  dom.window.close();
});

test('Best Fit retains partial reviews on quota failure and resumes missing jobs',async()=>{
  let requests=0;
  const {w,dom,calls}=await ui('#/best-fit',{cvs:[{id:'cv1',name:'CV'}],ai_ready:true},body=>{
    requests++;
    if(requests===2)return Response.json({error:'Gemini quota reached.'},{status:429});
    return matchResult(jobs.find(j=>j.id===body.job_id),85);
  });
  w.document.querySelector('#find-matches').click();
  await new Promise(resolve=>setTimeout(resolve,30));
  assert.equal(calls(),2);assert.equal(w.document.querySelectorAll('.job').length,1);
  assert.match(w.document.querySelector('.match-controls').textContent,/Gemini quota reached/);
  w.document.querySelector('#find-matches').click();
  await new Promise(resolve=>setTimeout(resolve,30));
  assert.equal(calls(),4);assert.equal(w.document.querySelectorAll('.job').length,3);
  dom.window.close();
});

test('public job-type menu returns related titles without owner features',async()=>{
  const {w,dom}=await ui('#/jobs',{owner:false});
  assert.ok(w.document.querySelector('.nav a[href="#/cvs"]'));
  const select=w.document.querySelector('#role-type');select.value='soc';select.dispatchEvent(new w.Event('change'));
  assert.equal(w.document.querySelectorAll('.job').length,1);
  assert.match(w.document.querySelector('.job').textContent,/Security Analyst/);
  dom.window.close();
});
test('public detail never displays CV information',async()=>{
  const {w,dom}=await ui('#/job/a',{owner:false});
  assert.ok(w.document.querySelector('.grid-two>aside'));
  assert.equal(w.document.querySelector('#mark-applied').hidden,true);
  dom.window.close();
});

test('location menu selects Dublin independently of Cork and Kerry',async()=>{
  const {w,dom}=await ui('#/jobs');const select=w.document.querySelector('#location');
  select.value='Dublin';select.dispatchEvent(new w.Event('change'));
  assert.equal(w.document.querySelectorAll('.job').length,1);
  assert.match(w.document.querySelector('.job').textContent,/Data Analyst/);
  dom.window.close();
});
test('visitor saves their CV only in the current tab',async()=>{
  const {w,dom}=await ui('#/cvs',{owner:false});
  w.document.querySelector('#cv-name').value='Visitor version';
  w.document.querySelector('#cv-text').value='Visitor work experience. '.repeat(12);
  w.document.querySelector('#cv-form input[type=checkbox]').checked=true;
  w.document.querySelector('#cv-form').dispatchEvent(new w.Event('submit',{cancelable:true,bubbles:true}));
  await new Promise(resolve=>setTimeout(resolve,20));
  const stored=JSON.parse(w.sessionStorage.getItem('parsr-visitor'));
  assert.equal(stored.cvs.length,1);assert.equal(stored.cvs[0].name,'Visitor version');
  assert.match(w.document.querySelector('.cv-row').textContent,/Visitor version/);
  dom.window.close();
});

test('missing latest-scan Cork security roles remain discoverable with warnings',async()=>{
  jobs.push({id:'historic',title:'Cyber Security Awareness Analyst',company:'Example',location:'Carrigtohill',category:'Cybersecurity',description:'Security awareness',url:'https://example.com/role',seen_in_latest_scan:false});
  try {
    const {w,dom}=await ui('#/jobs');
    let location=w.document.querySelector('#location');location.value='Cork';location.dispatchEvent(new w.Event('change'));
    let role=w.document.querySelector('#role-type');role.value='cybersecurity';role.dispatchEvent(new w.Event('change'));
    assert.equal(w.document.querySelectorAll('.job').length,1);
    assert.match(w.document.querySelector('.job').textContent,/Availability unconfirmed/);
    const scope=w.document.querySelector('#listing-scope');scope.value='latest';scope.dispatchEvent(new w.Event('change'));
    assert.equal(w.document.querySelectorAll('.job').length,0);
    dom.window.close();
  }finally{jobs.pop();}
});
