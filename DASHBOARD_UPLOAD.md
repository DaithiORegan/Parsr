# Upload the ZIP to Cloudflare

No local build or terminal is needed for the first upload. Use your existing Cloudflare account.

## 1. Create the app

1. Download **AI-JobParser-ATS-Screening-Tool-Cloudflare-Upload.zip** from this repo's `downloads/` folder (open the ZIP on GitHub and choose **Download raw file**).
2. In Cloudflare, open **Workers & Pages → Create application → Pages → Upload assets** (the direct-upload option).
3. Name it `ai-jobparser-ats-screening-tool`.
4. Upload the ZIP itself and deploy. It already contains the built website and the `_worker.js` backend. Do not delete `_worker.js` or `_routes.json`.

The first visit will say that private access is not configured. That is expected until step 2. The job index and CV routes stay protected.

Cloudflare documents ZIP drag-and-drop and compiled `_worker.js` support here:
https://developers.cloudflare.com/pages/get-started/direct-upload/

## 2. Set your private password and AI key

In the new Pages app's **Settings → Variables and Secrets**, add these for **Production**:

| Name | Type | Value |
| --- | --- | --- |
| `APP_PASSWORD` | Secret | Your own unique random password, at least 20 characters |
| `GEMINI_API_KEY` | Secret | Your Google Gemini API key |
| `GEMINI_MODEL` | Plain text | `gemini-3.5-flash-lite` |

Use username **owner** with your APP_PASSWORD when your browser asks you to sign in. This protects the whole website, including job data and CV endpoints. Do not set `LOCAL_DEV` on Cloudflare. Browser password prompts can retain credentials until the browser session closes.

You do not need the Access variables for this password-login version. If you later configure Cloudflare Access, its verified owner identity takes priority; see DEPLOYMENT.md.

## 3. Create the CV database

In **Storage & Databases → D1**, create `ai-jobparser-ats`. Open its **Console** and run:

```sql
CREATE TABLE IF NOT EXISTS cvs (id TEXT PRIMARY KEY, name TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS analyses (cache_key TEXT PRIMARY KEY, cv_id TEXT NOT NULL, job_id TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS analyses_cv ON analyses(cv_id);
CREATE TABLE IF NOT EXISTS job_status (job_id TEXT PRIMARY KEY, status TEXT NOT NULL, updated_at TEXT NOT NULL);
```

Then open the Pages app's **Settings → Bindings**, add a **D1 database binding** named exactly **DB**, and select that database. Use Production settings. Redeploy the same ZIP after saving settings so the deployed app receives the database binding and secrets.

Open the app URL, sign in with `owner` and your password, add a CV, then open a job. Its AI review starts automatically. Extracted CV text is stored in D1, and sent to Google Gemini for an uncached review. Original CV files are not retained.

## 4. Enable the 12-hour updates once

Uploading the ZIP installs the current snapshot; it does not by itself turn on unattended updates. The repo already contains a scanner/deployer for the same Pages app.

In **GitHub → AI-JobParser-ATS-Screening-Tool → Settings → Secrets and variables → Actions**, add:

**Secrets**

- `CLOUDFLARE_API_TOKEN`: token for the existing account with **Cloudflare Pages: Edit**, **D1: Edit**, and **Account Settings: Read**.
- `CLOUDFLARE_ACCOUNT_ID`: your Cloudflare Account ID.
- Optional `JOOBLE_API_KEY`: restores this source if used in the original repo.

**Variables**

- `HOSTING_TARGET`: `pages`
- `PAGES_PROJECT_NAME`: the exact Pages project name you created
- `D1_DATABASE_ID`: the UUID shown in D1's database overview
- `WEB_ENABLED`: `true`

Keep APP_PASSWORD and GEMINI_API_KEY in Cloudflare; the scan workflow does not need those secrets. Dashboard-set Pages bindings and runtime variables are retained between deployments.

Go to **Actions → Website scan and Cloudflare deploy → Run workflow**. It will scan and update this Pages app. It runs morning/evening at 10:17 and 22:17 Europe/Dublin, with backup attempts. GitHub can delay scheduled events; the site shows the actual last scan.

If your Direct Upload project's production branch is not `main`, set GitHub variable `PAGES_PRODUCTION_BRANCH` to the production branch shown by Cloudflare. Otherwise leave it unset (the workflow defaults to `main`).

The original JobScraper repo and its Discord setup remain untouched. Leave Discord secrets unset in the new repo to avoid posting a second copy to your existing channels. The copied Discord code is still available if you later want separate webhooks.

## After uploading

Keep the resulting `https://....pages.dev` URL. A live AI review and real account deployment still need checking after your account settings are entered. The upload ZIP has been built and its packaged backend tested, but has not been deployed to your account from this chat.

## Updating an existing app to Gemini

Add `GEMINI_API_KEY` and `GEMINI_MODEL` in the existing app's Production runtime settings, then deploy the reviewed Gemini update. The previous provider's variables are not used by the new backend. Keep the existing DB binding, tables, APP_PASSWORD and CVs. Saved reviews remain cached. Pull requests include a fresh `cloudflare-pages-review` artifact; do not upload the `main` branch ZIP until the reviewed change has been merged.
