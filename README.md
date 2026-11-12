# Parsr — Irish Tech Job Discovery

[Live job browser](https://ai-jobparser-ats-screening-tool.pages.dev)

Parsr collects Irish technology vacancies and presents them as searchable, concise role briefs. Visitors choose a job family to find related titles, filter by location, inspect responsibilities and requirements, and open the original employer advert.

## Features

- Public browsing by role family: IT support/helpdesk, SOC/security analysis, cybersecurity/GRC, networking, systems administration, cloud/DevOps, data/BI, business analysis, development, QA and graduate roles.
- Cork/Kerry browsing, search, category filters and title-based relevance ranking.
- Automatically generated, source-grounded briefs with pay only when listed. Full descriptions remain expandable.
- Private owner workspace for multiple CV versions, application tracking and Gemini-assisted role reviews.
- Scheduled scan/deploy workflow with primary and backup attempts in Europe/Dublin time.
- Existing Discord alert and bot tooling retained.

## Architecture

A Python scanner gathers source-provided vacancies and exports a job snapshot. A vanilla JavaScript frontend is bundled with esbuild. A Cloudflare Pages advanced-mode Worker serves the public interface, while authenticating owner-only API routes. Cloudflare D1 stores private CV text, review results and application status. Google Gemini returns schema-validated advisory reviews; the key stays in server runtime settings.

Job-family suggestions use transparent title matching, not AI. CV reviews use Gemini and are advisory estimates rather than an employer ATS result. Source coverage, source errors and GitHub scheduling affect freshness; the UI shows the actual last scan time.

## Privacy and public deployment

Public routes expose vacancies and job summaries only. They do not expose owner CVs, application history, AI reviews or personal profile scores. `/owner` requires the existing owner credentials; CV/AI/diagnostic APIs remain authenticated. Public visitors do not get accounts or CV-upload features in this version.

The candidate profile in `config/candidate_profile.json` is a generic example. Never commit real CVs, `.env`, `.dev.vars`, database exports, API keys or webhook URLs. See [DEPLOYMENT.md](DEPLOYMENT.md) and [DASHBOARD_UPLOAD.md](DASHBOARD_UPLOAD.md) for setup. The production site's stored CVs stay in its private D1 database and are not part of the source repository.

## Development

Requirements: Python 3.12+ and Node.js 22+.

```sh
python -m pip install -r requirements-bot.txt
python -m unittest discover -s tests -q
PYTHONPATH=. python scripts/export_web.py
cd web
npm ci
npm test
npm run build:pages
```

For localhost only, copy `web/.dev.vars.example` to `web/.dev.vars`. Set Gemini credentials only through an ignored local secret file or Cloudflare runtime secrets. `LOCAL_DEV=true` is accepted only on localhost and must never be enabled in production.

From the repository root, `python scripts/package_pages.py` packages the compiled Pages application into the upload ZIP. The GitHub Actions workflow also builds and verifies review/deployment artifacts. Production updates require the hosting configuration described in the deployment guide.

## Project scope

This is a portfolio project demonstrating data collection, filtering, accessible web UI, private backend routes, structured AI integration, caching and automated deployment. It does not submit job applications or verify that every indexed listing is still open. Always confirm details with the original employer.
