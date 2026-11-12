import { test } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import worker from "../src/worker.js";
import { localJob, validateAnalysis, cacheKey, analysisSchema } from "../src/core.js";
function database() {
  const sql = new DatabaseSync(":memory:");
  sql.exec(
    readFileSync(
      new URL("../migrations/0001_initial.sql", import.meta.url),
      "utf8",
    ),
  );
  const prepare = (query) => {
    let values = [];
    return {
      bind(...v) {
        values = v;
        return this;
      },
      async first() {
        return sql.prepare(query).get(...values);
      },
      async all() {
        return { results: sql.prepare(query).all(...values) };
      },
      async run() {
        const result=sql.prepare(query).run(...values);
        return { success: true, meta:{changes:Number(result.changes)} };
      },
    };
  };
  return {
    prepare,
    async batch(statements) {
      sql.exec("BEGIN");
      try {
        const results = await Promise.all(statements.map((s) => s.run()));
        sql.exec("COMMIT");
        return results;
      } catch (e) {
        sql.exec("ROLLBACK");
        throw e;
      }
    },
  };
}
const job = {
  id: "job1",
  title: "IT Support",
  description: "Windows and Active Directory support",
  description_complete: false,
};
const env = () => ({
  LOCAL_DEV: "true",
  DB: database(),
  ASSETS: {
    async fetch() {
      return Response.json({ jobs: [job] });
    },
  },
});
const req = (path, method = "GET", data) =>
  new Request("http://localhost" + path, {
    method,
    headers: { Origin: "http://localhost", "Content-Type": "application/json" },
    body: data ? JSON.stringify(data) : undefined,
  });
const review = {
  score: 92,
  summary: "Good evidence",
  strengths: ["Windows coursework"],
  gaps: ["No production experience stated"],
  suggestions: ["Describe the coursework lab"],
  limitations: ["Short description"],
};
test("Cork and Kerry both qualify, remote Ireland does not", () => {
  for (const location of ["Cork", "Tralee", "Kerry", "Killarney"])
    assert.ok(localJob({ location }));
  assert.equal(localJob({ location: "Remote Ireland" }), false);
  assert.equal(
    localJob({ location: "Dublin", description: "Cork office" }),
    false,
  );
});
test("private routes fail closed without Access configuration", async () => {
  const response = await worker.fetch(
    new Request("https://site.workers.dev/api/workspace"),
    env(),
  );
  assert.equal(response.status, 503);
  const r = await worker.fetch(
    new Request("https://site.workers.dev/api/workspace"),
    {
      ...env(),
      ACCESS_TEAM_DOMAIN: "mine.cloudflareaccess.com",
      ACCESS_AUD: "abc",
      OWNER_EMAIL: "owner@example.com",
    },
  );
  assert.equal(r.status, 401);
});
test("CV lifecycle, validation, origin checks and analysis deletion", async () => {
  const e = env();
  assert.equal(
    (
      await worker.fetch(
        req("/api/cvs", "POST", { name: "Empty", text: "short" }),
        e,
      )
    ).status,
    400,
  );
  const wrong = new Request("http://localhost/api/cvs", {
    method: "POST",
    headers: { Origin: "https://evil.example" },
    body: "{}",
  });
  assert.equal((await worker.fetch(wrong, e)).status, 403);
  const saved = await (
    await worker.fetch(
      req("/api/cvs", "POST", {
        name: "Support",
        text: "Windows coursework and technical support. ".repeat(12),
      }),
      e,
    )
  ).json();
  assert.ok(saved.id);
  let data = await (await worker.fetch(req("/api/workspace"), e)).json();
  assert.equal(data.cvs.length, 1);
  assert.equal(data.cvs[0].text, undefined);
  await e.DB.prepare("INSERT INTO analyses VALUES (?,?,?,?,?)")
    .bind("key", saved.id, "job1", JSON.stringify(review), "2026-11-12")
    .run();
  assert.equal(
    (await worker.fetch(req("/api/cvs/" + saved.id, "DELETE"), e)).status,
    200,
  );
  data = await (await worker.fetch(req("/api/workspace"), e)).json();
  assert.equal(data.cvs.length, 0);
  assert.equal(data.analyses.length, 0);
});
test("AI reviews are validated, capped for snippets and cached by content", async () => {
  const e = env();
  e.GEMINI_API_KEY = "test";
  const saved = await (
    await worker.fetch(
      req("/api/cvs", "POST", {
        name: "CV",
        text: "Windows coursework ".repeat(20),
      }),
      e,
    )
  ).json();
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async (url, options) => {
    calls++;
    assert.equal(url, 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent');
    assert.equal(options.headers['x-goog-api-key'], 'test');
    assert.equal(options.redirect, 'manual');
    const body = JSON.parse(options.body);
    assert.equal(body.generationConfig.responseMimeType, 'application/json');
    assert.deepEqual(body.generationConfig.responseJsonSchema, analysisSchema);
    assert.match(body.systemInstruction.parts[0].text, /untrusted DATA/);
    assert.equal(JSON.parse(body.contents[0].parts[0].text).cv, 'Windows coursework '.repeat(20).trim());
    return Response.json({ candidates: [{finishReason:'STOP', content:{parts:[{text:JSON.stringify(review)}]}}] });
  };
  try {
    let r = await worker.fetch(
      req("/api/analyze", "POST", { job_id: job.id, cv_id: saved.id }),
      e,
    );
    assert.equal(r.status, 200);
    const result = await r.json();
    assert.equal(result.score, 70);
    for (const field of ["summary", "strengths", "gaps", "suggestions", "limitations"])
      assert.deepEqual(result[field], review[field]);
    r = await worker.fetch(
      req("/api/analyze", "POST", { job_id: job.id, cv_id: saved.id }),
      e,
    );
    assert.equal(r.status, 200);
    assert.equal(calls, 1);
    assert.equal(
      result.job_signature,
      JSON.stringify([job.title, job.description, job.description_complete]),
    );
  } finally {
    globalThis.fetch = original;
  }
});
test("missing provider key returns actionable error", async () => {
  const e = env();
  const saved = await (
    await worker.fetch(
      req("/api/cvs", "POST", {
        name: "CV",
        text: "Windows experience ".repeat(20),
      }),
      e,
    )
  ).json();
  assert.equal(
    (
      await worker.fetch(
        req("/api/analyze", "POST", { job_id: job.id, cv_id: saved.id }),
        e,
      )
    ).status,
    503,
  );
});
test("review schema rejects malformed provider output and cache changes with evidence", async () => {
  assert.equal(validateAnalysis(review), true);
  assert.equal(validateAnalysis({ ...review, score: 150 }), false);
  assert.equal(validateAnalysis({ ...review, gaps: [{}] }), false);
  assert.notEqual(
    await cacheKey({ id: "1", text: "a" }, job),
    await cacheKey({ id: "1", text: "b" }, job),
  );
});

test('dashboard password prompts for owner login', async () => {
  const e = { APP_PASSWORD: 'a-long-private-test-password', ASSETS: { async fetch() { return new Response('private asset'); } } };
  const request = headers => new Request('https://example.pages.dev/owner', {headers});
  let r = await worker.fetch(request({}), e);
  assert.equal(r.status, 401);
  assert.match(r.headers.get('www-authenticate'), /Basic/);
  r = await worker.fetch(request({Authorization:'Basic '+btoa('owner:wrong')}), e);
  assert.equal(r.status, 401);
  r = await worker.fetch(request({Authorization:'Basic '+btoa('owner:'+e.APP_PASSWORD)}), e);
  assert.equal(r.status, 200);
  assert.equal(await r.text(), 'private asset');
  r = await worker.fetch(request({}), {...e, APP_PASSWORD:'short'});
  assert.equal(r.status, 503);
});

test('workspace readiness depends on Gemini and never includes secrets', async () => {
  const e=env();e.OPENAI_API_KEY='unused-old-key';
  let r=await worker.fetch(req('/api/workspace'),e);
  assert.equal((await r.json()).ai_ready,false);
  e.GEMINI_API_KEY='private-gemini-key';
  r=await worker.fetch(req('/api/workspace'),e);
  const text=await r.text();assert.equal(JSON.parse(text).ai_ready,true);
  assert.ok(!text.includes(e.GEMINI_API_KEY));assert.ok(!text.includes(e.OPENAI_API_KEY));
});
async function analysisEnvironment() {
  const e=env();e.GEMINI_API_KEY='secret-test-gemini-key';
  const cvText='Private CV experience with Windows. '.repeat(8);
  const cv=await (await worker.fetch(req('/api/cvs','POST',{name:'CV',text:cvText}),e)).json();
  return {e,request:()=>req('/api/analyze','POST',{job_id:job.id,cv_id:cv.id}),cvText};
}
test('Gemini provider failures and malformed outputs are safe and never cached', async t => {
  const envelope=text=>Response.json({candidates:[{finishReason:'STOP',content:{parts:[{text}]}}]});
  const failures=[
    ['redirect refused',()=>new Response(null,{status:302,headers:{Location:'https://example.com'}}),502,/retry/],
    ['invalid key',()=>Response.json({error:{message:'secret-test-gemini-key private CV'}},{status:400}),502,/key/i],
    ['unauthorized',()=>new Response('sensitive provider body',{status:401}),502,/key/i],
    ['forbidden',()=>new Response('sensitive provider body',{status:403}),502,/access/],
    ['model missing',()=>new Response('sensitive provider body',{status:404}),502,/model/],
    ['quota',()=>new Response('sensitive provider body',{status:429}),429,/quota/],
    ['unavailable',()=>new Response('sensitive provider body',{status:503}),502,/retry/],
    ['network',()=>{throw Error('secret-test-gemini-key private CV');},502,/reach/],
    ['timeout',()=>{throw new DOMException('secret-test-gemini-key private CV','TimeoutError');},504,/too long/],
    ['bad envelope',()=>new Response('not JSON'),502,/unreadable/],
    ['missing candidate',()=>Response.json({}),502,/incomplete/],
    ['blocked',()=>Response.json({promptFeedback:{blockReason:'SAFETY'}}),502,/incomplete/],
    ['truncated',()=>Response.json({candidates:[{finishReason:'MAX_TOKENS',content:{parts:[{text:JSON.stringify(review)}]}}]}),502,/incomplete/],
    ['bad JSON',()=>envelope('not JSON'),502,/unreadable/],
    ['bad schema',()=>envelope(JSON.stringify({...review,score:200})),502,/invalid review/],
  ];
  for(const [name,reply,status,pattern] of failures) await t.test(name,async()=>{
    const {e,request,cvText}=await analysisEnvironment();
    const original=globalThis.fetch;const log=console.error;let logs='';
    globalThis.fetch=async()=>reply();console.error=(...args)=>{logs+=args.join(' ');};
    try {
      const r=await worker.fetch(request(),e);assert.equal(r.status,status);
      const text=await r.text();assert.match(text,pattern);
      for(const secret of [e.GEMINI_API_KEY,cvText,'sensitive provider body'])assert.ok(!(text+logs).includes(secret));
      assert.equal((await e.DB.prepare('SELECT COUNT(*) AS n FROM analyses').first()).n,0);
    } finally {globalThis.fetch=original;console.error=log;}
  });
});
test('custom Gemini model, split text parts and unchanged local rate limit',async()=>{
  const {e,request}=await analysisEnvironment();e.GEMINI_MODEL='gemini-3.1-flash-lite';
  const original=globalThis.fetch;let calls=0;
  globalThis.fetch=async url=>{calls++;assert.match(url,/gemini-3\.1-flash-lite:generateContent$/);const text=JSON.stringify(review);return Response.json({candidates:[{finishReason:'STOP',content:{parts:[{thought:true,text:'ignore reasoning'},{text:text.slice(0,25)},{text:text.slice(25)}]}}]});};
  try {
    for(let i=0;i<30;i++)await e.DB.prepare('INSERT INTO analyses VALUES (?,?,?,?,?)').bind('recent'+i,'other','other',JSON.stringify(review),new Date().toISOString()).run();
    assert.equal((await worker.fetch(request(),e)).status,429);assert.equal(calls,0);
    await e.DB.prepare('DELETE FROM analyses').run();
    assert.equal((await worker.fetch(request(),e)).status,200);assert.equal(calls,1);
  } finally {globalThis.fetch=original;}
});

test('private Gemini diagnostics return only public configuration and available models',async()=>{
  const e=env();e.GEMINI_API_KEY='sensitive-test-key';
  const original=globalThis.fetch;let calls=0;
  globalThis.fetch=async(url,options)=>{
    calls++;assert.equal(url,'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000');
    assert.equal(options.headers['x-goog-api-key'],e.GEMINI_API_KEY);
    assert.equal(options.redirect,'manual');assert.equal(options.body,undefined);
    return Response.json({models:[
      {name:'models/gemini-3.5-flash-lite',supportedGenerationMethods:['generateContent'],description:e.GEMINI_API_KEY},
      {name:'models/embedding-only',supportedGenerationMethods:['embedContent']},
      {name:'sensitive-test-key',supportedGenerationMethods:['generateContent']}
    ]});
  };
  try {
    let r=await worker.fetch(new Request('https://app.pages.dev/api/ai-status'),e);
    assert.equal(r.status,503);assert.equal(calls,0);
    r=await worker.fetch(req('/api/ai-status'),e);
    const text=await r.text(),data=JSON.parse(text);
    assert.equal(data.configured_model_available,true);
    assert.deepEqual(data.available_models,['gemini-3.5-flash-lite']);
    assert.ok(!text.includes(e.GEMINI_API_KEY));
    e.GEMINI_MODEL='gemini-2.5-flash';
    assert.equal((await (await worker.fetch(req('/api/ai-status'),e)).json()).configured_model_available,false);
    globalThis.fetch=async()=>new Response('sensitive-test-key',{status:403});
    const rejected=await (await worker.fetch(req('/api/ai-status'),e)).json();
    assert.equal(rejected.provider_http_status,403);assert.ok(!JSON.stringify(rejected).includes(e.GEMINI_API_KEY));
  } finally {globalThis.fetch=original;}
});

test('generation diagnostics isolate basic and schema requests without CV or key disclosure',async()=>{
  const e=env();e.GEMINI_API_KEY='sensitive-key';
  const original=globalThis.fetch;let calls=0;
  globalThis.fetch=async(url,options)=>{
    calls++;
    if(options.method==='GET')return Response.json({models:[{name:'models/gemini-3.5-flash-lite',supportedGenerationMethods:['generateContent']}]});
    assert.equal(options.redirect,'manual');assert.ok(!options.body.includes('cv_id'));
    const body=JSON.parse(options.body);
    if(body.generationConfig.responseJsonSchema){assert.deepEqual(body.generationConfig.responseJsonSchema,analysisSchema);return Response.json({error:{status:'NOT_FOUND',message:'model not found sensitive-key projects/private-project AIzaSecretTest',details:[{reason:'MODEL_ACCESS_DENIED'}]}},{status:404});}
    return Response.json({candidates:[{content:{parts:[{text:'OK'}]}}]});
  };
  try {
    const r=await worker.fetch(req('/api/ai-status?test=1'),e);const text=await r.text(),data=JSON.parse(text);
    assert.equal(calls,2);assert.equal(data.cv_data_sent,false);
    assert.equal(data.generation_tests[0].http_status,200);
    assert.equal(data.generation_tests[1].google_status,'NOT_FOUND');
    assert.equal(data.generation_tests[1].error_category,'model_or_method_not_found');
    assert.ok(!text.includes(e.GEMINI_API_KEY));
    assert.ok(!text.includes('private-project'));assert.ok(!text.includes('AIzaSecretTest'));
    assert.deepEqual(data.generation_tests[1].provider_reasons,['MODEL_ACCESS_DENIED']);
    assert.match(data.generation_tests[1].provider_message,/redacted/);
  } finally {globalThis.fetch=original;}
});

test('direct generation probes do not depend on model-list availability',async()=>{
  const e=env();e.GEMINI_API_KEY='private-key';const original=globalThis.fetch;
  let calls=0;
  globalThis.fetch=async(url)=>{calls++;assert.ok(url.includes(':generateContent'));throw new TypeError('Invalid header private-key');};
  try {
    const text=await (await worker.fetch(req('/api/ai-status?test=1'),e)).text();const data=JSON.parse(text);
    assert.equal(data.diagnostic_version,'gemini-status-v3');assert.equal(calls,2);
    assert.equal(data.generation_tests[0].failure_class,'invalid_header_value');
    assert.ok(!text.includes(e.GEMINI_API_KEY));
  }finally{globalThis.fetch=original;}
});

test('public browsing leaves CVs, AI calls and diagnostics owner-only',async()=>{
  const e={...env(),APP_PASSWORD:'a-long-private-test-password'};
  const request=path=>new Request('https://example.pages.dev'+path);
  for(const path of ['/','/jobs.json','/parsr-logo.png'])assert.equal((await worker.fetch(request(path),e)).status,200);
  const session=await (await worker.fetch(request('/api/session'),e)).json();assert.equal(session.owner,false);
  for(const path of ['/api/workspace','/api/ai-status','/owner'])assert.equal((await worker.fetch(request(path),e)).status,401);
  const write=new Request('https://example.pages.dev/api/analyze',{method:'POST',headers:{Origin:'https://example.pages.dev'},body:'{}'});
  assert.equal((await worker.fetch(write,e)).status,401);
  e.ASSETS.fetch=async()=>Response.json({jobs:[{id:'j',title:'Support',fit_score:95,matched_skills:['personal']} ]});
  const feed=await (await worker.fetch(request('/jobs.json'),e)).json();
  assert.equal(feed.jobs[0].fit_score,undefined);assert.equal(feed.jobs[0].matched_skills,undefined);
});

test('visitor analysis is stateless, isolated from owner CVs, and usage-limited',async()=>{
  const e=env();e.GEMINI_API_KEY='test';e.APP_PASSWORD='long-private-owner-password';
  await e.DB.prepare('INSERT INTO cvs VALUES (?,?,?,?)').bind('owner-cv','Owner','OWNER PRIVATE TEXT','now').run();
  const original=globalThis.fetch;let calls=0;
  globalThis.fetch=async(url,options)=>{
    calls++;const b=JSON.parse(options.body);
    assert.ok(b.contents[0].parts[0].text.includes('Visitor work experience'));
    assert.ok(!options.body.includes('OWNER PRIVATE TEXT'));
    return Response.json({candidates:[{finishReason:'STOP',content:{parts:[{text:JSON.stringify(review)}]}}]});
  };
  try {
    const data={job_id:job.id,cv_id:'owner-cv',cv_text:'Visitor work experience with Windows. '.repeat(6),cv_name:'Visitor CV'};
    for(let i=0;i<5;i++)assert.equal((await worker.fetch(req('/api/visitor/analyze','POST',data),e)).status,200);
    assert.equal((await worker.fetch(req('/api/visitor/analyze','POST',data),e)).status,429);
    assert.equal(calls,5);
    assert.equal((await e.DB.prepare('SELECT COUNT(*) AS n FROM cvs').first()).n,1);
    assert.equal((await e.DB.prepare('SELECT COUNT(*) AS n FROM analyses').first()).n,0);
    const records=await e.DB.prepare('SELECT * FROM visitor_limits').all();
    const stored=JSON.stringify(records);assert.ok(!stored.includes('Visitor work experience'));assert.ok(!stored.includes('localhost'));
  } finally {globalThis.fetch=original;}
});
