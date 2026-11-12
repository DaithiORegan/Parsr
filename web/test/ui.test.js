import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";
import { localJob } from "../src/core.js";
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
async function ui(hash = "#/jobs", workspace = {}, analyze = null) {
  const dom = new JSDOM('<div id="app"></div><div id="toast"></div>', {
    url: "http://localhost/" + hash,
    runScripts: "outside-only",
  });
  const w = dom.window;
  let calls = 0;
  w.pdfjs = { GlobalWorkerOptions: {} };
  w.localJob = localJob;
  w.scrollTo = () => {};
  w.fetch = async (url, options) => {
    if (url === "/api/session") return Response.json({owner:workspace.owner ?? true});
    if (url === "/jobs.json")
      return Response.json({ jobs, scanned_at: new Date().toISOString() });
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
    `(async()=>{const pdfjs=window.pdfjs;const localJob=window.localJob;${roles};${formatter};${source}})()`,
  );
  return { w, dom, calls: () => calls };
}
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
  assert.match(w.document.body.textContent,/No reviewed matches yet/);
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
  await w.eval(`(async()=>{const pdfjs=window.pdfjs;const localJob=window.localJob;${roles};${formatter};${source}})()`);
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

test('Cork / Kerry is a dedicated navigation page for local roles', async () => {
  const {w,dom}=await ui('#/local');
  assert.equal(w.document.querySelectorAll('.job').length,2);
  assert.ok(w.document.querySelector('a[href="#/local"].active'));
  assert.doesNotMatch(w.document.querySelector('.jobs').textContent,/Data Analyst/);
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
  assert.equal(w.document.querySelectorAll('.job').length,1);
  assert.match(w.document.querySelector('.job').textContent,/IT Support/);
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
  assert.equal(calls(),2);assert.ok(reviewed.every(b=>b.cv_id==='cv1'&&b.job_id!=='c'));
  assert.match(w.document.querySelector('.job').textContent,/Security Analyst/);
  assert.equal(w.document.querySelectorAll('.job').length,2);
  w.document.querySelector('#find-matches').click();
  await new Promise(resolve=>setTimeout(resolve,10));assert.equal(calls(),2);
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
  assert.equal(calls(),3);assert.equal(w.document.querySelectorAll('.job').length,2);
  dom.window.close();
});

test('public job-type menu returns related titles without owner features',async()=>{
  const {w,dom}=await ui('#/jobs',{owner:false});
  assert.ok(!w.document.querySelector('.nav a[href="#/cvs"]'));
  const select=w.document.querySelector('#role-type');select.value='soc';select.dispatchEvent(new w.Event('change'));
  assert.equal(w.document.querySelectorAll('.job').length,1);
  assert.match(w.document.querySelector('.job').textContent,/Security Analyst/);
  dom.window.close();
});
test('public detail never displays CV information',async()=>{
  const {w,dom}=await ui('#/job/a',{owner:false});
  assert.equal(w.document.querySelector('.grid-two>aside'),null);
  assert.equal(w.document.querySelector('#mark-applied').hidden,true);
  dom.window.close();
});
