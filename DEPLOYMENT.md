# AI JobParser ATS Screening Tool — Cloudflare setup

For the ZIP upload route with a dashboard-set private password, start with [DASHBOARD_UPLOAD.md](DASHBOARD_UPLOAD.md). The original Worker/Access setup below is still supported.

This is a private personal job website copied from `DaithiORegan/JobScraper`. The original repository and its schedules remain untouched. The copied Python monitor and Discord bot still work. The new website uses Cloudflare Workers static assets, a private D1 database, Cloudflare Access and server-side Google Gemini calls.

## What is ready

- Searchable job index, categories, Cork/Kerry Best Fit, saved jobs and manual application status.
- Multiple CV versions (PDF/DOCX/TXT upload or pasted text). Files are parsed locally; only the reviewed text is stored in D1. Original files are not saved.
- Per-role AI feedback: evidence-based strengths, missing evidence, truthful improvements and limitations. Opening a job with an active CV requests analysis automatically; unchanged reviews are cached. Up to 30 new completed reviews/hour. This is advisory guidance, not a real employer ATS score.
- Separate morning/evening scans, with primary and backup attempts. Discord remains optional in this repository.
- Full source-provided descriptions retained from new scans. Historic snippets are identified and scores capped at 70 when reviewed by AI.

## 1. Connect the existing Cloudflare account

Use an API token scoped to the intended account with **Workers Scripts: Edit**, **D1: Edit**, and **Account Settings: Read**. Additional permissions may be required for any custom-domain setup you perform. Get the Account ID from the Cloudflare dashboard. Never put tokens in tracked files.

For deployment from Codex, configure `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in the environment settings. For GitHub Actions, add them as repository **Actions secrets**. Repository secrets are not inherited from the original JobScraper repo.

## 2. Create D1

From `web/`, with Node 22+:

```sh
npm ci
npx wrangler d1 create ai-jobparser-ats
```

Copy the returned database UUID into the GitHub Actions **variable** `D1_DATABASE_ID` and into a local environment variable of that name. Do not rename the binding `DB`.

## 3. Restrict the website to you

In Cloudflare Zero Trust → Access → Applications, add a self-hosted application for the Worker URL (`ai-jobparser-ats-screening-tool.<your-subdomain>.workers.dev`) or your custom domain. Add an Allow policy for **your exact email only**. Turn on Cloudflare Access protection for the workers.dev route in Workers → Settings → Domains & Routes as appropriate for your account; protect preview URLs too if enabled.

Get the Access application's **AUD tag**, your team domain (e.g. `yourteam.cloudflareaccess.com`), and your email. Set these three GitHub Actions **variables**, also used as Worker runtime variables:

- `ACCESS_TEAM_DOMAIN`
- `ACCESS_AUD`
- `OWNER_EMAIL`

The Worker verifies Access JWT signatures, issuer, audience and owner email on every route including assets and the job index. Without this configuration it returns 503; without a valid owner JWT it refuses access. No public fallback is enabled.

## 4. Deploy

With the four nonsecret variables above exported in your shell:

```sh
cd web
node configure.mjs
npm run build
npx wrangler d1 migrations apply DB --remote
npx wrangler deploy
```

`configure.mjs` writes the deployment values into `wrangler.jsonc`. The committed template deliberately contains a placeholder D1 UUID. The workflow replaces it before deploying. Never add `LOCAL_DEV=true` to production.

For AI reviews, configure the Worker secret using the secure prompt:

```sh
npx wrangler secret put GEMINI_API_KEY
```

The model defaults to `gemini-3.5-flash-lite`; change `GEMINI_MODEL` if needed. Google Gemini usage is billed to that API account. CV and job text go to Google Gemini when an uncached role review runs. Without a key, the rest of the website works and displays a setup notice. Create a Gemini API key in Google AI Studio and save it as a Cloudflare server secret; never commit it or put it in frontend variables.

## 5. Enable updates every 12 hours

Set the GitHub Actions **variable** `WEB_ENABLED` to `true`, then run **Website scan and Cloudflare deploy** once manually. Morning/evening attempts are 10:17 and 22:17 Europe/Dublin with backups at 10:47 and 22:47. A successful slot suppresses its backup. GitHub may delay cron events; the UI shows the actual last scan and warns after 18 hours.

Each enabled run scans, runs Python and Worker tests, exports jobs, migrates D1, redeploys, and saves scan/delivery history in this repo. Scheduled scans cannot run until Cloudflare and Access configuration is supplied. Actions must have read/write contents permissions.

Optional secrets:

- `JOOBLE_API_KEY`: enables that source, otherwise accessible sources still scan.
- `DISCORD_WEBHOOK_URL`, `DISCORD_WEBHOOK_LOCAL`, `DISCORD_WEBHOOK_ATS`: preserve original Discord behavior **for this repository**. Use separate destinations if the original is still active, or leave unset for a website-only scanner. The original repo's webhooks and PC-hosted bot continue independently. No duplicate original-channel messages are sent by default.

The copied `Manual Discord Monitor (optional)` workflow is manual only. All original alert/report/backfill and bot commands remain available. The original repo is not modified.

## Data and scoring limits

The initial copy has been refreshed by a live scan. All Jobs and Best Fit show roles returned by the latest scan. Historic jobs remain accessible through saved links, with an availability warning. A source failure can temporarily remove a role from the latest-scan view without proving that it has closed. New scans retain full source-provided descriptions, but some sources only supply snippets. An old vacancy is not automatically proven active or closed. Check its last-seen date and original advert. Baseline scores use the existing candidate profile; changing the active uploaded CV affects AI reviews, not the legacy profile heuristic. Best Fit includes Cork and Kerry locations only (including listed towns); generic remote Ireland is not automatically treated as local.

Saved/applied status is personal website data, independent of the PC-hosted Discord bot's SQLite records. Clicking the employer link does not submit or record an application. The explicit Mark as applied button records only your status.

D1 stores CV text, AI results and job status. Deleting a CV removes its text and cached reviews from the live database; provider backups follow Cloudflare retention settings. Job data is packaged privately with the Worker, not put in public storage.

## Local development and checks

Copy `web/.dev.vars.example` to `web/.dev.vars`, and use `LOCAL_DEV=true` only on localhost. Build assets, apply local migrations, then use `npx wrangler dev` if you want to preview. Local development needs a valid local D1 configuration in wrangler.jsonc. Production access stays closed by default.

```sh
python -m pip install -r requirements-bot.txt
python -m unittest discover -s tests -q
PYTHONPATH=. python scripts/export_web.py
cd web
npm ci
npm test
npm run build
npx wrangler deploy --dry-run --outdir ../work/worker-build
```

The Worker tests use a real in-memory SQLite database through a D1-compatible test adapter. AI calls are mocked for repeatable tests; a live provider review must be verified after key setup. Browser QA depends on the execution environment's available browser tools.

## Gemini migration and review artifacts

Set `GEMINI_API_KEY` as a server secret and `GEMINI_MODEL=gemini-3.5-flash-lite` as a runtime variable in the target Cloudflare app. For Pages, use Settings → Variables and Secrets in Production; the model in `wrangler.jsonc` is for Worker deployments, not Pages runtime settings. Redeploy after changing bindings/secrets. Existing OpenAI credentials are ignored by this backend and can be removed after migration. Do not put provider keys in GitHub build variables or browser code.

The backend uses Google's official [`generateContent` REST API](https://ai.google.dev/api/generate-content) with `responseMimeType: application/json` and `responseJsonSchema: analysisSchema`. The response keeps score, summary, strengths, gaps, suggestions and limitations. Existing cached reviews remain usable, including reviews generated before the provider change; changing provider or model does not invalidate the content-based cache. No D1 schema migration is needed.

Authentication/configuration or model-access failures return a safe 502 message; quota exhaustion returns 429; request timeouts return 504; network failures and invalid/blocked/truncated results return 502. Failed reviews are not cached. Provider bodies and exceptions are not logged or relayed to the browser. An 8,192-token generation budget accommodates Gemini's thinking and structured output; requests retain the 45-second timeout. Local completed-review limits remain 30/hour.

From `web/`, run `npm test` and `npm run build:pages`. Then from the repository root run `python scripts/package_pages.py` to regenerate the upload ZIP. The packager rejects builds that lack the Gemini backend. Pull-request checks test/build/package and attach a `cloudflare-pages-review` ZIP artifact without running the production scan/deploy job. Scheduled deployments also package a fresh backend and attach `cloudflare-pages-upload`. Provider keys are runtime-only and are not needed in either build job.

## Best Fit and local browsing

Cork / Kerry lists all latest-scan local roles. Best Fit shows only roles with a saved, current review for the selected CV scoring **60 or higher**, ordered by AI fit by default. It never substitutes the candidate-profile estimate for a missing CV review. Changing CV switches the reviewed results; changed listing text requires a new review.

Select a CV and click **Find my best matches** to review unreviewed local roles sequentially through `/api/analyze` (Gemini after this migration). Saved reviews are reused. Progress and partial results remain visible; quota/network errors stop the batch and allow resuming later. Switching CV or leaving Best Fit stops additional requests after the current request completes. This does not run a bulk paid analysis automatically when scanning jobs or opening the page. New scan results become eligible for review on the next button click. The existing 30-completed-reviews/hour limit and provider quota still apply.

The default is `gemini-3.5-flash-lite`, the replacement Google explicitly recommended when this deployment's key was denied access to `gemini-2.5-flash-lite`. Model listing is discovery, not proof of generation access. Change the existing Cloudflare `GEMINI_MODEL` runtime variable too, since it overrides the code default.

## Public browsing / private owner workspace

The homepage, compiled assets and sanitized `/jobs.json` feed are public. Job-type selection ranks related titles without an API call. Personal profile scores are omitted from the public feed. `/api/session` returns only whether the current browser has owner credentials; anonymous visitors never load the CV workspace.

Use `/owner` to sign in with the existing owner credentials. All other `/api/*` routes (including CVs, reviews, application state and Gemini diagnostics) remain protected. This is public job discovery, not multiuser CV hosting. Do not remove APP_PASSWORD merely to open public browsing. If Cloudflare Access protects the entire domain, its policy must allow public routes while retaining owner protection; the Worker still authenticates owner APIs.

For a public portfolio repository, use a clean source history with a generic candidate profile. Keep any previous repository containing a real profile private: deleting the file at HEAD or force-pushing branches alone may leave historical PR references accessible. A clean public source copy should omit scanner delivery history and generated private/local data. Keep the currently deployed private repository as the production build source until a deliberate Git integration migration.
