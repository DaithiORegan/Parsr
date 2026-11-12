# Parsr — Irish Job Discovery & CV Matching

[Live job browser](https://ai-jobparser-ats-screening-tool.pages.dev)

Parsr collects Irish vacancies across technology and other sectors and presents them as searchable, concise role briefs. Visitors choose a job family to find related titles, filter by location, inspect responsibilities and requirements, and open the original employer advert.

## Features

- Public browsing by role family: IT support/helpdesk, SOC/security analysis, cybersecurity/GRC, networking, systems administration, cloud/DevOps, data/BI, business analysis, development, QA and graduate roles.
- Selectable counties and advertised locations across Ireland, search, category filters and title-based relevance ranking.
- Non-tech families include administration, finance, HR, sales, marketing, healthcare, retail, hospitality, operations, logistics, construction, education and customer service.
- Automatically generated, source-grounded briefs with pay only when listed. Full descriptions remain expandable.
- Private owner workspace for multiple CV versions, application tracking and Gemini-assisted role reviews.
- Scheduled scan/deploy workflow with primary and backup attempts in Europe/Dublin time.
- Existing Discord alert and bot tooling retained.

## Architecture

A Python scanner gathers source-provided vacancies and exports a job snapshot. A vanilla JavaScript frontend is bundled with esbuild. A Cloudflare Pages advanced-mode Worker serves the public interface, while authenticating owner-only API routes. Cloudflare D1 stores private CV text, review results and application status. Google Gemini returns schema-validated advisory reviews; the key stays in server runtime settings.

Job-family suggestions use transparent title matching, not AI. CV reviews use Gemini and are advisory estimates rather than an employer ATS result. Source coverage, source errors and GitHub scheduling affect freshness; the UI shows the actual last scan time.

## Privacy and public deployment

Public browsing exposes vacancies and job summaries. Visitor assessment accepts only that visitor’s supplied CV text and a public job ID; it cannot retrieve owner CVs. They do not expose owner CVs, application history, AI reviews or personal profile scores. `/owner` requires the existing owner credentials; CV/AI/diagnostic APIs remain authenticated. Public visitors can upload PDF/DOCX/TXT CVs and request Gemini role reviews without accounts. Visitor CV text and results remain in sessionStorage in the current browser tab, and are not written to D1. Closing the tab or deleting the CV removes that tab’s saved copy. Text is sent to Gemini only for assessment.

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

## Visitor CV assessment

Add a CV in **My CV / AI review**, review the extracted text, and acknowledge Gemini processing before using it. Opening a role automatically assesses the selected CV; Best Fit can review jobs within your selected location and role family. Results are advisory, not a real employer ATS result. Visitor CV text and assessment output are not saved in the server database. Owner CVs remain in the protected owner workspace.

Public review attempts are limited to 5/hour and 20/day per network address, with a site-wide budget of 100/day. These limits include failed provider attempts. D1 stores only expiring counters with HMAC-hashed network identifiers; it stores no visitor CV or review output. Owner reviews retain their separate limits. Initial public rollout uses browser-tab storage; it does not provide cross-device accounts or saved visitor CVs.

The expanded scanner includes national searches and direct employer feeds across sectors. Coverage depends on configured sources; this is not a complete national jobs database. Jooble's expanded 16-term search can use up to 64 requests/day for two scans, excluding manual runs. Scheduled scans generate summaries for every new exported role.

## Scan coverage and retained listings

Browsing defaults to all known listings. Jobs missed by a scan stay searchable with an **Availability unconfirmed** label, rather than disappearing. Choose **Seen in latest scan only** for the narrower latest snapshot. A source outage or partial query does not prove a vacancy closed. Coverage metadata identifies failed, partial and key-dependent sources; confirm availability on the employer's advert.

Board pagination follows the advertised next link, and regional tech searches supplement national searches. The county/town registry includes Cork towns such as Carrigtohill and Ringaskiddy. The production private repo commits snapshots for automatic Pages Git deployment; public mirrors are opt-in for scheduled scans. Jooble needs its own Actions secret for fresh results.
