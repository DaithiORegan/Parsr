
import * as pdfjs from "pdfjs-dist/build/pdf.mjs";
import mammoth from "mammoth/mammoth.browser.js";
import { localJob } from "./core.js";
import { ROLE_TYPES, roleRelevance } from "./role-types.js";
import { COUNTIES, locationMatches } from "./locations.js";
import { descriptionHTML } from "./description.js";

pdfjs.GlobalWorkerOptions.workerSrc = "/vendor/pdf.worker.min.mjs";

const $ = (s) => document.querySelector(s),
  esc = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );

const date = (s) =>
  s
    ? new Date(s).toLocaleString("en-IE", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Not recorded";

const autoAttempted = new Set();

let state = { jobs: [], cvs: [], status: [], analyses: [], ai_ready: false, owner:false },
  category = "All roles",
  query = "",
  location = "All locations",
  sort = window.location.hash.startsWith("#/unseen") ? "newest" : "fit",
  page = 1,
  error = "",
  activeCV = localStorage.getItem("activeCV") || "",
  busy = false,
  matchingCV = "",
  matchingProgress = "",
  selectedJobID = "",
  selectedRoleType = "",
  listingScope = "all";

const categories = [
  "All roles",
  "Cybersecurity",
  "IT Support",
  "Analyst",
  "Cloud & Infrastructure",
  "Graduate & Junior",
  "Administration", "Finance", "HR & Recruitment", "Sales & Marketing", "Healthcare & Care", "Retail & Hospitality", "Operations & Logistics", "Construction & Trades", "Education", "Customer Service",
];

const app = $("#app");

const seenStorageKey = 'parsr-seen-jobs-v1';
const seenJobs = new Set();
try {
  const saved = JSON.parse(localStorage.getItem(seenStorageKey) || '[]');
  if (Array.isArray(saved)) saved.filter(id => typeof id === 'string').forEach(id => seenJobs.add(id));
} catch {}
const isUnseen = j => Boolean(j.first_indexed_at && Number.isFinite(Date.parse(j.first_indexed_at)) && !seenJobs.has(j.id));
function markSeen(id) {
  if (!state.jobs.some(j => j.id === id && j.first_indexed_at)) return;
  try {
    const saved = JSON.parse(localStorage.getItem(seenStorageKey) || '[]');
    if (Array.isArray(saved)) saved.filter(value => typeof value === 'string').forEach(value => seenJobs.add(value));
  } catch {}
  seenJobs.add(id);
  try {localStorage.setItem(seenStorageKey, JSON.stringify([...seenJobs]));} catch {}
}

window.addEventListener('storage', event => {
  if (event.key !== seenStorageKey) return;
  try {
    const saved = JSON.parse(event.newValue || '[]');
    if (!Array.isArray(saved)) return;
    seenJobs.clear();
    saved.filter(id => typeof id === 'string').forEach(id => seenJobs.add(id));
    if (locationHash()[0] === 'unseen') render();
  } catch {}
});

function toast(message) {
  $("#toast").textContent = message;
  $("#toast").style.display = "block";
  setTimeout(() => ($("#toast").style.display = "none"), 6500);
}

async function api(path, options = {}) {
  const response = await fetch("/api/" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error("The server returned an unreadable response.");
  }
  if (!response.ok) throw Error(data.error || "Request failed");
  return data;
}

async function refresh() {
  const session = await api("session");
  state.owner = !!session.owner;
  if(!state.owner) {
    let saved={};try{saved=JSON.parse(sessionStorage.getItem('parsr-visitor')||'{}');}catch{}
    state.cvs=Array.isArray(saved.cvs)?saved.cvs:[];state.analyses=Array.isArray(saved.analyses)?saved.analyses:[];
    state.status=[];state.ai_ready=!!session.ai_ready;activeCV=state.cvs.some(c=>c.id===activeCV)?activeCV:state.cvs[0]?.id||'';return;
  }
  const w = await api("workspace");
  Object.assign(state, w);
  if (!state.cvs.some((c) => c.id === activeCV))
    activeCV = state.cvs[0]?.id || "";
  localStorage.setItem("activeCV", activeCV);
}

function saveVisitor() {
  if(!state.owner) sessionStorage.setItem('parsr-visitor',JSON.stringify({cvs:state.cvs,analyses:state.analyses}));
}
async function analyzeRole(jobID,cvID) {
  if(state.owner) return api('analyze',{method:'POST',body:JSON.stringify({cv_id:cvID,job_id:jobID})});
  const cv=state.cvs.find(c=>c.id===cvID);
  if(!cv)throw Error('Add a CV in this browser tab first.');
  const result=await api('visitor/analyze',{method:'POST',body:JSON.stringify({cv_text:cv.text,cv_name:cv.name,job_id:jobID})});
  state.analyses.push({job_id:jobID,cv_id:cvID,result});saveVisitor();return result;
}
const review = (j) =>
  state.analyses.findLast(
    (a) =>
      a.job_id === j.id &&
      a.cv_id === activeCV &&
      a.result.job_signature ===
        JSON.stringify([j.title, j.description, j.description_complete]),
  )?.result;

const status = (j) =>
  state.status.find((a) => a.job_id === j.id)?.status || "none";

function cvSelect() {
  return `<select id="active-cv" aria-label="Active CV" ${state.cvs.length ? "" : "disabled"}><option value="">Select a CV</option>${state.cvs.map((c) => `<option value="${esc(c.id)}" ${c.id === activeCV ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>`;
}

function shell(content, nav) {
  const ownerLinks = state.owner ? [["best-fit", "✧", "Best Fit"],["saved", "♡", "Saved jobs"],["cvs", "▤", "My CVs"]] : [["best-fit","✧","Best Fit"],["cvs","▤","My CV / AI review"]];
  app.innerHTML = `<div class="shell"><aside class="sidebar"><a href="#/jobs" class="brand">
  <img
    src="/parsr-logo.png"
    alt="Parsr Logo"
    class="parsr-logo"
  />
  <span>
    Parsr
    <small>JOBS · CV MATCHING</small>
  </span>
</a><div class="navlabel">YOUR WORKSPACE</div><nav class="nav" aria-label="Main navigation">${[
    ["jobs", "▦", "All jobs"],
    ["unseen", "◉", `Unseen (${state.jobs.filter(isUnseen).length})`],
    ["local", "⌖", "By location"],
    ...ownerLinks,
  ]
    .map(
      ([id, icon, title]) =>
        `<a href="#/${id}" class="${nav === id ? "active" : ""}"><span>${icon}</span>${title}</a>`,
    )
    .join(
      "",
    )}</nav><div class="side-note"><span class="dot"></span><strong>Always looking ahead</strong><br>Fresh scans twice a day.<br>Your next opportunity could be one scan away.</div><div class="profile"><div class="avatar">Y</div><div>Parsr<small>Irish tech opportunities</small></div></div></aside><div><header class="topbar"><span>Workspace <span class="muted">/ ${esc(nav === "cvs" ? "CV library" : nav === "best-fit" ? "Best Fit" : nav === "unseen" ? "Unseen roles" : "Opportunities")}</span></span><span class="workspace-tag">◉ Public job browser</span></header><main>${!state.owner ? '<div class="public-note">Explore Irish tech roles · <a href="/owner">Owner sign in</a></div>' : ""}${error ? `<div class="banner">${esc(error)}</div>` : ""}${content}</main></div></div>`;
  $("#active-cv")?.addEventListener("change", (e) => {
    activeCV = e.target.value;
    localStorage.setItem("activeCV", activeCV);
    render();
  });
}

function jobCard(j) {
  const r = review(j),
    saved = status(j) === "saved";
  return `<article class="job ${j.id === selectedJobID ? "selected" : ""}"><div class="company-logo">${esc(j.company?.slice(0, 2).toUpperCase() || "IT")}</div><div><h3><button class="job-title" data-preview="${esc(j.id)}">${esc(j.title)}</button></h3><div class="company">${esc(j.company)} <span aria-hidden="true">·</span> ${esc(j.location)}</div><div class="job-meta">${isUnseen(j)?'<span class="badge">Unseen</span>':''}${j.seen_in_latest_scan === false?'<span class="stale-badge">Availability unconfirmed</span>':'<span class="badge">Seen in latest scan</span>'}<span class="chip">${esc(j.category)}</span>${localJob(j) ? '<span class="badge">Cork & Kerry</span>' : ""}<span>${esc(j.experience || "Experience not stated")}</span>${status(j) === "applied" ? '<span class="badge">Applied</span>' : ""}</div><div class="job-actions"><a class="text-link" href="#/job/${encodeURIComponent(j.id)}">View role details ↗</a><button data-save="${esc(j.id)}" aria-label="${saved ? "Unsave" : "Save"} ${esc(j.title)}">${saved ? "♥ Saved" : "♡ Save"}</button></div></div>${r ? `<div class="score">${r.score}<small>AI CV fit / 100</small></div>` : ""}</article>`;
}

function bindCards() {
  $$("[data-role-open]").forEach(a => a.addEventListener("click", () => markSeen(a.dataset.roleOpen)));
  $$("[data-preview]").forEach(b => b.onclick = () => {
    selectedJobID = b.dataset.preview;
    markSeen(selectedJobID);
    if (locationHash()[0] === 'unseen') {
      window.location.hash = '#/job/' + encodeURIComponent(selectedJobID);
      return;
    }
    render();
    if (window.innerWidth < 900)
      document.querySelector(".job-preview")?.scrollIntoView({
        behavior: "smooth"
      });
  });

  if(!state.owner) $$("[data-save]").forEach(b=>b.hidden=true);
  $$("[data-save]").forEach(
    (b) =>
      (b.onclick = () =>
        setStatus(
          b.dataset.save,
          status({ id: b.dataset.save }) === "saved" ? "none" : "saved",
        )),
  );
}

function $$(s) {
  return [...document.querySelectorAll(s)];
}

async function setStatus(id, value) {
  try {
    await api("status", {
      method: "POST",
      body: JSON.stringify({ job_id: id, status: value }),
    });
    await refresh();
    render();
    toast(
      value === "applied"
        ? "Marked as applied. No application was submitted."
        : "Job updated.",
    );
  } catch (e) {
    toast(e.message);
  }
}

function scanHealthNotice() {
  const h=state.scan_health||{};
  const failed=[...(h.failed_sources||[]),...(h.partial_sources||[])].map(s=>s.company||s.provider);
  const locked=(h.locked_sources||[]).map(s=>s.company||s.provider);
  const missing=state.jobs.filter(j=>j.seen_in_latest_scan===false).length;
  if(!failed.length&&!locked.length&&!missing)return '';
  return `<div class="banner"><strong>Scan coverage & availability</strong><br>${failed.length?`Unavailable or partial sources: ${esc([...new Set(failed)].join(', '))}. `:''}${locked.length?`Sources needing configuration: ${esc(locked.join(', '))}. `:''}${missing} previously indexed listings were not confirmed in the latest scan. They remain searchable and are labelled unconfirmed; a missed scan does not prove a job has closed. Open the original advert to check.</div>`;
}
function bestFitControls(jobs) {
  const reviewed = jobs.filter(j => review(j)).length;
  return `<section class="panel match-controls"><h3>Match these roles to your CV</h3><p>Gemini reviews roles in the selected location and job family against your CV. ${reviewed} of ${jobs.length} roles reviewed. Unchanged reviews are reused.</p><button id="find-matches" class="primary" ${!activeCV||!state.ai_ready||matchingCV||busy?'disabled':''}>${matchingCV?'Reviewing selected roles…':'Find my best matches'}</button><p class="note" role="status">${esc(matchingProgress || (!activeCV?'Add or select a CV to start.':!state.ai_ready?'Configure the Gemini API key to start matching.':(state.owner?'This sends CV and role text to Gemini. Up to 30 new reviews per hour.':'CV text goes to Gemini. Visitor limits: 5 attempts/hour and 20/day per network, subject to the site-wide budget.')))}</p></section>`;
}

async function findBestMatches() {
  if(matchingCV || !activeCV || !state.ai_ready) return;
  const cvID = activeCV;
  const pending = state.jobs.filter(
    j => (listingScope === "all" || j.seen_in_latest_scan !== false) && locationMatches(j,location) && roleRelevance(j,selectedRoleType)>0 && !review(j)
  );

  matchingCV = cvID;
  matchingProgress = pending.length
    ? 'Starting CV reviews…'
    : 'All selected roles already reviewed.';
  render();

  let completed = 0;
  try {
    for(const job of pending) {
      if(activeCV !== cvID || locationHash()[0] !== "best-fit") break;

      matchingProgress = `Reviewing role ${completed+1} of ${pending.length}…`;
      render();

      const result = await analyzeRole(job.id,cvID);

      if(state.owner)state.analyses.push({job_id:job.id,cv_id:cvID,result});
      completed++;
    }
    matchingProgress = `${completed} reviews completed. Matching roles appear below; other roles remain in All jobs.`;
  } catch(e) {
    matchingProgress = `${completed} reviews completed. ${e.message} Saved results are retained; click again later to continue.`;
  } finally {
    matchingCV = "";
    render();
  }
}

function listPage(nav) {
  let jobs = state.jobs
    .filter(j => nav !== 'unseen' || isUnseen(j))
    .filter((j) => listingScope === "all" || j.seen_in_latest_scan !== false)

    .filter((j) => nav !== "saved" || ["saved", "applied"].includes(status(j)));

  jobs = jobs.filter(j => roleRelevance(j, selectedRoleType) > 0);
  const base = jobs;

  if(nav === "best-fit")
    jobs = jobs.filter(j => (review(j)?.score ?? -1) >= 60);

  jobs = jobs
    .filter((j) => category === "All roles" || j.category === category)
    .filter((j) =>
      (j.title + " " + j.company + " " + j.location + " " + j.description)
        .toLowerCase()
        .includes(query.toLowerCase()),
    )
    .filter(
      (j) =>
        location === "All locations" ||
        locationMatches(j, location),
    );

  jobs.sort((a, b) =>
    sort === "company"
      ? a.company.localeCompare(b.company)
      : sort === "newest"
        ? String((nav === "unseen" ? b.first_indexed_at : b.last_seen) || b.posted || "").localeCompare(
            String((nav === "unseen" ? a.first_indexed_at : a.last_seen) || a.posted || ""),
          )
        : (review(b)?.score ?? b.fit_score ?? 0) -
          (review(a)?.score ?? a.fit_score ?? 0),
  );

  if(selectedRoleType && sort === "fit" && nav !== "best-fit")
    jobs.sort((a,b)=>roleRelevance(b,selectedRoleType)-roleRelevance(a,selectedRoleType));
  const pages = Math.max(1, Math.ceil(jobs.length / 15));
  page = Math.min(page, pages);
  const visible = jobs.slice((page - 1) * 15, page * 15);
  const selected = visible.find(j => j.id === selectedJobID) || visible[0];
  selectedJobID = selected?.id || "";

  shell(
    `<div class="intro"><div><div class="eyebrow">YOUR JOB SEARCH, IN FOCUS</div><h1>${nav === "unseen" ? "New roles you haven’t opened." : nav === "local" ? "Explore roles by location." : nav === "best-fit" ? "Your best matches." : nav === "saved" ? "Your saved opportunities." : "Find your next opportunity."}</h1><p>${nav === "unseen" ? "Only roles added by scans after Unseen launched appear here. Existing listings stay out. Opening a role marks it as seen in this browser." : nav === "local" ? "Choose any county, town or advertised location below." : nav === "best-fit" ? "Roles scoring 60+ against your selected CV, within your chosen location and job type." : nav === "saved" ? "Keep promising roles and track where you’ve applied." : "Explore roles across Ireland, across industries. Find your next step."}</p></div><a class="primary" href="#/cvs">Manage CVs ↗</a></div><div class="stats"><div class="stat"><div><small>${nav === "unseen" ? "Unseen opportunities" : nav === "best-fit" ? "Local opportunities" : "Known opportunities"}</small><strong>${base.length}</strong></div><div class="stat-icon">▦</div></div><div class="stat"><div><small>In selected location</small><strong>${state.jobs.filter(j => (listingScope === "all" || j.seen_in_latest_scan !== false) && locationMatches(j,location)).length}</strong></div><div class="stat-icon">⌖</div></div><div class="stat"><div><small>CVs in your library</small><strong>${state.cvs.length}</strong></div><div class="stat-icon">▤</div></div></div>${nav === "best-fit" ? bestFitControls(base) : ""}${scanHealthNotice()}${state.scanned_at && Date.now() - new Date(state.scanned_at) > 18 * 3600000 ? '<div class="banner">The latest snapshot is over 18 hours old. Check the scan workflow; listings may have changed.</div>' : ""}<div class="tabs" role="group" aria-label="Role categories">${categories.map((c) => `<button data-category="${esc(c)}" class="${category === c ? "active" : ""}">${c}</button>`).join("")}</div><div class="role-menu"><label for="role-type">What kind of role are you looking for?</label><select id="role-type"><option value="">Browse all job types</option>${ROLE_TYPES.map(t=>`<option value="${t.id}" ${selectedRoleType===t.id?'selected':''}>${t.label}</option>`).join('')}</select><p class="note">Includes similar job titles within your selected role family. Use search and location to narrow the results.</p></div><div class="filters"><input id="search" class="search" type="search" placeholder="Search job titles, companies or skills…" aria-label="Search jobs" value="${esc(query)}"><select id="listing-scope" aria-label="Listing freshness"><option value="all" ${listingScope==='all'?'selected':''}>All known listings</option><option value="latest" ${listingScope==='latest'?'selected':''}>Seen in latest scan only</option></select><select id="location" aria-label="Location">${["All locations", ...COUNTIES, "Remote", ...new Set(state.jobs.map(j=>j.location).filter(Boolean))].map((l) => `<option ${location === l ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>${cvSelect()}</div><div class="result-heading"><span><strong>${jobs.length} opportunities</strong> <span class="muted">· Last scan ${date(state.scanned_at)}</span></span><select id="sort" aria-label="Sort jobs">${[
      ["fit", "Best match"],
      ["newest", nav === "unseen" ? "Newest added" : "Latest seen"],
      ["company", "Company A–Z"],
    ]
      .map(
        ([v, n]) =>
          `<option value="${v}" ${sort === v ? "selected" : ""}>${n}</option>`,
      )
      .join("")}</select></div><div class="job-browser"><div class="job-results"><div class="jobs">${
      jobs
        .slice((page - 1) * 15, page * 15)
        .map(jobCard)
        .join("") ||
      (nav === "unseen" ? '<div class="empty"><h2>You’re all caught up</h2><p>New roles will appear here after future scans. Existing listings are available in All jobs.</p></div>' : nav === "best-fit" ? '<div class="empty"><h2>No reviewed matches for these filters</h2><p>Choose your CV below the filters, then use Find my best matches. This page shows reviewed roles scoring 60+; unreviewed roles remain in All jobs.</p></div>' : '<div class="empty"><h2>No roles here yet</h2><p>Try another category or clear your filters. Save jobs from All jobs to build your shortlist.</p></div>')
    }</div><div class="pagination"><button id="previous" ${page === 1 ? "disabled" : ""}>← Previous</button><span>${page} / ${pages}</span><button id="next" ${page === pages ? "disabled" : ""}>Next →</button></div></div>${selected ? jobPreview(selected) : ""}</div><p class="note">Role suggestions match job-title families. Availability and requirements should be confirmed in the original advert. Add your CV for a personal AI review. Visitor CVs and results stay in this tab.</p>`,
    nav,
  );
  if(!state.owner) {
    document.querySelector('.intro a[href="#/cvs"]')?.remove();


    document.querySelector('.job-preview > .text-link')?.remove();
  }

  $("#listing-scope").onchange = e => {listingScope=e.target.value;page=1;render();};
  $("#role-type").onchange = e => {selectedRoleType=e.target.value;category="All roles";page=1;render();};
  $("#find-matches")?.addEventListener("click", findBestMatches);

  $$("[data-category]").forEach(
    (b) =>
      (b.onclick = () => {
        category = b.dataset.category;
        page = 1;
        render();
      }),
  );

  let timer;
  $("#search").oninput = (e) => {
    query = e.target.value;
    clearTimeout(timer);
    timer = setTimeout(() => {
      const pos = e.target.selectionStart;
      render();
      $("#search").focus();
      $("#search").setSelectionRange(pos, pos);
    }, 250);
  };

  $("#location").onchange = (e) => {
    location = e.target.value;
    page = 1;
    render();
  };

  $("#sort").onchange = (e) => {
    sort = e.target.value;
    render();
  };

  $("#previous").onclick = () => {
    page--;
    render();
    window.scrollTo(0, 0);
  };

  $("#next").onclick = () => {
    page++;
    render();
    window.scrollTo(0, 0);
  };

  bindCards();
}

function quickSummary(j) {
  const s = j.quick_summary;
  if (!s)
    return '<p class="note">Summary unavailable in this snapshot. Open the full advert below.</p>';

  const facts = [
    ["Pay", s.pay],
    ["Location", j.location],
    ["Working pattern", s.arrangement],
    ["Experience", s.experience]
  ];

  if(s.employment !== "Not stated") facts.push(["Contract",s.employment]);
  if(s.hours !== "Not stated") facts.push(["Hours",s.hours]);

  return `<section class="role-brief"><div class="eyebrow">THE ROLE AT A GLANCE</div><h3>Quick read</h3><p class="brief-overview">${esc(s.overview)}</p><dl class="brief-facts">${facts.map(([label,value])=>`<div><dt>${esc(label)}</dt><dd>${esc(value||"Not stated")}</dd></div>`).join('')}</dl><div class="brief-section"><h3>What you’ll do</h3>${s.responsibilities.length?`<ul>${s.responsibilities.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`:'<p class="note">Duties are not clearly separated in the available advert. Check the full description.</p>'}</div><div class="brief-section"><h3>What they need from you</h3>${s.requirements.length?`<ul>${s.requirements.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`:'<p class="note">Specific requirements are not stated in the available listing.</p>'}</div>${!j.description_complete?'<p class="brief-warning">Limited listing data — confirm the full requirements in the original advert.</p>':''}<p class="note">${esc(s.basis)}</p></section>`;
}

function jobPreview(j) {
  return `<aside class="job-preview panel" aria-label="Selected job details"><div class="preview-top"><span class="chip">${esc(j.category)}</span><span class="muted">${localJob(j)?"Cork & Kerry":"Ireland"}</span></div><div class="company-logo">${esc(j.company?.slice(0,2).toUpperCase()||"IT")}</div><h2>${esc(j.title)}</h2><p class="preview-company">${esc(j.company)} · ${esc(j.location)}</p><div class="header-actions"><a class="primary" href="#/job/${encodeURIComponent(j.id)}">View role details</a><a class="preview-apply" data-role-open="${esc(j.id)}" href="${esc(j.url)}" target="_blank" rel="noopener noreferrer">Apply on company site ↗</a></div><div class="preview-facts"><span>${esc(j.experience||"Experience not specified")}</span><span>Last seen ${date(j.last_seen)}</span></div>${quickSummary(j)}<details class="full-advert"><summary>Read full job description</summary><div class="description">${descriptionHTML(j.full_description || j.description||"Open the original advert for the full job description.")}</div></details><a class="text-link" href="#/job/${encodeURIComponent(j.id)}">See your CV strengths and gaps →</a></aside>`;
}

function detail(id) {
  const j = state.jobs.find((j) => j.id === id);
  if (!j) {
    shell(
      '<div class="empty"><h1>Role not found</h1><a href="#/jobs">Back to jobs</a></div>',
      "jobs",
    );
    return;
  }

  markSeen(id);
  const r = review(j);

  shell(
    `<a class="back" href="#/jobs">← Back to opportunities</a><div class="detail-header"><div class="eyebrow">${esc(j.category)}</div><h1>${esc(j.title)}</h1><p class="muted">${esc(j.company)} · ${esc(j.location)}</p><div class="header-actions"><a class="primary" href="${esc(j.url)}" target="_blank" rel="noopener noreferrer">Open original advert ↗</a><button id="mark-applied">${status(j) === "applied" ? "✓ Marked as applied" : "Mark as applied"}</button><button data-save="${esc(j.id)}">${status(j) === "saved" ? "♥ Saved" : "♡ Save role"}</button></div></div><div class="grid-two"><div><section class="panel"><h2>Role summary</h2><p class="note">Source: ${esc(j.provider)} · Last seen: ${date(j.last_seen)} · Posted: ${esc(j.posted || "Not supplied")}</p>${!j.description_complete ? '<div class="banner">This listing contains only a short snippet. Open the original advert for full duties and requirements. AI feedback will be limited.</div>' : ""}${j.seen_in_latest_scan === false ? '<div class="banner">Not returned in the latest scan. Availability is unverified; check the original advert.</div>' : ""}${quickSummary(j)}<details class="full-advert"><summary>Read full job description</summary><div class="description">${descriptionHTML(j.full_description || j.description || "No description supplied. Open the original advert for details.")}</div></details></section><section class="panel"><h3>Experience requirement</h3><p>${esc(j.experience || "Not stated in available data.")}</p><p class="note">Opening an advert does not record or submit an application. Use “Mark as applied” after you apply yourself.</p></section></div><aside><section class="panel"><div class="eyebrow">PERSONAL CV REVIEW</div><h2>How does your CV fit?</h2>${cvSelect()}${!state.ai_ready ? '<div class="banner">AI reviews need the server API key configured. You can upload and manage CVs now.</div>' : ""}${state.cvs.length ? `<p class="note">Opening a role with a CV selected automatically sends that CV’s text and the available job description to Google Gemini for review. Unchanged reviews are reused.</p><button id="analyze" class="primary full" ${busy ? "disabled" : ""}>${busy ? "Reviewing your CV…" : r ? "Load saved review" : "Analyze this role"}</button>` : '<p class="muted">Add your CV to see strengths, gaps and suggestions for this role.</p><a class="text-link" href="#/cvs">Add your first CV →</a>'}${
      r
        ? `<div class="review-score">${r.score}<span> / 100</span></div><p class="note">Advisory AI fit · ${esc(r.cv_name)} · ${date(r.analyzed_at)}</p><p>${esc(r.summary)}</p>${[
            ["strengths", "What works well", "good"],
            ["gaps", "Gaps & missing evidence", "bad"],
            ["suggestions", "Ways to improve", ""],
            ["limitations", "Limits of this review", ""],
          ]
            .map(
              ([key, title, cls]) =>
                `<div class="review-block ${cls}"><h3>${title}</h3><ul>${r[key].map((v) => `<li>${esc(v)}</li>`).join("") || "<li>None identified.</li>"}</ul></div>`,
            )
            .join("")}`
        : ""
    }<p class="note">This is guidance based on the supplied text, not an employer’s ATS result or a guarantee of eligibility.</p></section></aside></div>`,
    "jobs",
  );

  if(!state.owner) {


    document.querySelector('#mark-applied')?.setAttribute('hidden','');
  }
  $("#mark-applied").onclick = () =>
    setStatus(id, status(j) === "applied" ? "none" : "applied");

  $("#analyze")?.addEventListener("click", async () => {
    if (!activeCV) {
      toast("Choose a CV first.");
      return;
    }
    const cv = activeCV;
    busy = true;
    render();
    try {
      await analyzeRole(id,cv);
      await refresh();
      toast("Your CV review is ready.");
    } catch (e) {
      toast(e.message);
    } finally {
      busy = false;
      matchingCV = "";
      matchingProgress = "";
      selectedJobID = "",
  selectedRoleType = "",
  listingScope = "all";
      render();
    }
  });

  bindCards();

  const attemptKey = JSON.stringify([activeCV, id, j.description]);
  if (
    state.ai_ready &&
    activeCV &&
    !r &&
    !busy &&
    !autoAttempted.has(attemptKey)
  ) {
    autoAttempted.add(attemptKey);
    queueMicrotask(() => {
      if (
        locationHash()[0] === "job" &&
        decodeURIComponent(locationHash().slice(1).join("/")) === id
      )
        $("#analyze")?.click();
    });
  }
}

function cvsPage() {
  shell(
    `<div class="intro"><div><div class="eyebrow">MAKE YOUR EXPERIENCE COUNT</div><h1>A CV for every next step.</h1><p>Keep your versions together. Choose the right one for each role.</p></div></div><div class="grid-two"><section class="panel"><h2>Your CV library</h2><p class="note">${state.owner?"Up to 20 versions in your private library.":"CV text and reviews stay in this browser tab until you delete them or close the tab. No account is needed."} Original files are not retained.</p>${state.cvs.map((c) => `<article class="cv-row"><h3>▤ ${esc(c.name)}</h3><small>Added ${date(c.created_at)}</small><div class="job-actions"><button data-use="${esc(c.id)}" ${activeCV === c.id ? "disabled" : ""}>${activeCV === c.id ? "✓ Active CV" : "Use this CV"}</button><button data-delete="${esc(c.id)}">Delete</button></div></article>`).join("") || '<div class="empty"><h3>Your next chapter starts with your CV</h3><p>Upload a PDF or Word document, or paste your CV text.</p></div>'}<p class="note">Reviews compare your selected CV with each role. For visitors, CV text is sent to Gemini for assessment but is not saved in the server database.</p></section><section class="panel"><h2>Add a CV version</h2><form id="cv-form"><label for="cv-name">Version name</label><input id="cv-name" class="full" required maxlength="120" placeholder="e.g. IT Support · November 2026"><label for="cv-file">Upload PDF or DOCX</label><input id="cv-file" class="full" type="file" accept=".pdf,.docx,.txt"><p class="note">Maximum 10 MB. Text is extracted in your browser. For scanned PDFs, paste readable text below.</p><label for="cv-text">Review or paste your CV text</label><textarea id="cv-text" required minlength="100" maxlength="80000" placeholder="Your experience, education, skills and achievements…"></textarea><p class="note">Check the extracted text before saving. Delete a version any time to remove its text and saved AI reviews.</p><label><input type="checkbox" required> I understand my selected CV text is sent to Google Gemini when I open a role or request Best Fit matching.</label><button class="primary full" type="submit">Use this CV</button></form></section></div>`,
    "cvs",
  );

  $$("[data-use]").forEach(
    (b) =>
      (b.onclick = () => {
        activeCV = b.dataset.use;
        localStorage.setItem("activeCV", activeCV);
        render();
      }),
  );

  $$("[data-delete]").forEach(
    (b) =>
      (b.onclick = async () => {
        if (!confirm("Delete this CV and its saved AI reviews?")) return;
        try {
          if(state.owner) await api("cvs/" + encodeURIComponent(b.dataset.delete), {method:"DELETE"});
          else {state.cvs=state.cvs.filter(c=>c.id!==b.dataset.delete);state.analyses=state.analyses.filter(a=>a.cv_id!==b.dataset.delete);saveVisitor();}
          await refresh();
          render();
          toast("CV deleted.");
        } catch (e) {
          toast(e.message);
        }
      }),
  );

  $("#cv-file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;

    if (f.size > 10 * 1024 * 1024) {
      toast("Choose a file smaller than 10 MB.");
      return;
    }

    try {
      toast("Extracting CV text…");
      let text = "";

      if (f.name.toLowerCase().endsWith(".pdf")) {
        const pdf = await pdfjs.getDocument({
          data: await f.arrayBuffer(),
          isEvalSupported: false,
        }).promise;

        if (pdf.numPages > 30)
          throw Error("Please use a CV with 30 pages or fewer.");

        for (let i = 1; i <= pdf.numPages; i++) {
          const p = await pdf.getPage(i);
          text +=
            (await p.getTextContent()).items
              .map((t) => t.str + (t.hasEOL ? "\n" : " "))
              .join("") + "\n";
        }
        await pdf.destroy();
      } else if (f.name.toLowerCase().endsWith(".docx"))
        text = (
          await mammoth.extractRawText({ arrayBuffer: await f.arrayBuffer() })
        ).value;
      else if (f.name.toLowerCase().endsWith(".txt"))
        text = await f.text();
      else throw Error("Please choose PDF, DOCX or TXT.");

      if (text.length > 80000)
        throw Error("CV text exceeds 80,000 characters.");

      $("#cv-text").value = text;

      if (!$("#cv-name").value)
        $("#cv-name").value = f.name.replace(/\.[^.]+$/, "");

      toast(
        text.trim().length < 100
          ? "No readable CV found. Paste the text manually."
          : "Text extracted. Review it, then save your CV.",
      );
    } catch (e) {
      toast(
        e.message || "Could not read the document. Paste the text instead.",
      );
    }
  };

  $("#cv-form").onsubmit = async (e) => {
    e.preventDefault();
    const b = e.target.querySelector("button[type=submit]");
    b.disabled = true;
    try {
      let result;
      if(state.owner) result=await api("cvs",{method:"POST",body:JSON.stringify({name:$("#cv-name").value,text:$("#cv-text").value})});
      else {
        if(state.cvs.length>=20)throw Error('Remove an old CV first; maximum 20 per tab.');
        result={id:crypto.randomUUID(),name:$("#cv-name").value,text:$("#cv-text").value,created_at:new Date().toISOString()};
        state.cvs.push(result);saveVisitor();
      }
      activeCV = result.id;
      await refresh();
      render();
      toast("CV saved to your library.");
    } catch (e) {
      toast(e.message);
      b.disabled = false;
    }
  };
}

function render() {
  const [route = "jobs", ...rest] = locationHash();
  if(!state.owner && ["saved"].includes(route)) {
    shell('<section class="panel"><h1>Private owner workspace</h1><p>CVs, AI reviews and application history require owner sign-in.</p><a class="primary" href="/owner">Owner sign in</a></section>', 'jobs');return;
  }
  if (route === "cvs") cvsPage();
  else if (route === "job") detail(decodeURIComponent(rest.join("/")));
  else listPage(
    ["jobs", "unseen", "local", "best-fit", "saved"].includes(route)
      ? route
      : "jobs"
  );
}

function locationHash() {
  return window.location.hash.replace(/^#\/?/, "").split("/");
}

window.addEventListener("hashchange", () => {
  if (["unseen", "local", "best-fit"].includes(locationHash()[0])) {
    location = "All locations";
    category = "All roles";
    query = "";
    sort = locationHash()[0] === "unseen" ? "newest" : "fit";
  }
  selectedJobID = '';
  page = 1;
  render();
  window.scrollTo(0, 0);
});

try {
  const response = await fetch("/jobs.json");
  if (!response.ok) throw Error("Could not load the job index.");
  Object.assign(state, await response.json());

  try {
    await refresh();
  } catch (e) {
    error = e.message;
  }

  render();
} catch (e) {
  app.innerHTML = `<div class="empty"><h1>Workspace unavailable</h1><p>${esc(e.message)}</p><button id="retry">Try again</button></div>`;
  $("#retry").onclick = () => window.location.reload();
}
