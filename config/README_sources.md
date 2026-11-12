# How actual source access works

Each row in `sources.csv` is configured to make a real API/feed request. This is not a site-name directory; however, live success is only established by a successful scan, and providers can stop responding at any time.

- `greenhouse`, `ashby`, `lever`, `smartrecruiters`: published public job APIs, no API key required for public listings.
- `recruitee`: public XML job feed. Recruitee's separate JSON Careers API is shifting to token authentication; this integration deliberately uses its documented XML publishing feed.
- `remotive`: public remote jobs API. Must link to Remotive and include attribution; four checks/day maximum. Only explicit Worldwide/Europe/Ireland location eligibility is included, but confirm eligibility before applying.
- `jooble`: Irish regional API, requires a **Jooble Ireland** API key. Requests are limited to eight search terms across at most two pages every six hours: maximum 64 scheduled requests/day, below their 100 requests/day free allowance. Manual scans also consume quota.
- `rss`: RSS/Atom feed reader exists, but no unverified RSS URL has been turned on. Add documented public feed rows only, with `provider,slug,company,url`.

A feed can return zero current jobs; that does not mean its collector failed. If a company closes its account, the scan reports an ERROR, not a false success.

**Do not add ordinary web URLs to an API collector.** A career page using Workday, Taleo, iCIMS or a bespoke vendor needs its own permitted integration, a usable official feed or an email alert ingestion route.


## Expanded coverage (November 2026)

The configuration now includes direct public Jobs.ie and IrishJobs searches,
Workday Ireland career sites, and substantially more employer ATS feeds.
Each newly enabled employer endpoint was checked live before addition; feeds
may have zero Irish IT matches today and still advertise relevant roles later.

Jobs.ie and IrishJobs search 12 role families nationally and explicitly in Cork,
follow all result pages (up to 20 per search, with an explicit failure if exceeded),
and deduplicate posting IDs across searches. Public search-page data supplies
employer, actual location, description snippet, salary, posted date and application
URL. A Cork search can include surrounding locations: channel routing always uses
the listing's location, not the search query. HTML/schema or access failures are
reported as source failures, never as successful empty results.

Workday uses the public career site's country facets to select Ireland, paginates
the matching postings, and loads full job descriptions and additional locations
for relevant IT roles. It requires a career-site URL in the CSV's url column.
It does not use applicant accounts.

Indeed and LinkedIn are not directly integrated. Jooble may supply overlapping
listings, but this is not complete coverage of either board. No login, paid
third-party scraping subscription or API credential has been added.

Existing quiet baselines still apply to newly added sources; complete Discord
reports include their current matching vacancies even on their first scan.

## Troubleshooting unavailable sources

Run **Actions → Diagnose job source access → Run workflow** in Parsr. This makes
one bounded request per source on the same GitHub-hosted network as scheduled
scans. It reports fixed status categories, without printing the key, request URL,
response body, or any CV data. Repeated full scans consume API quota and are not
a useful way to diagnose access denial.

On 12 November 2026, Jooble returned HTTP 403 from GitHub with its secret present;
the Irish endpoint matches Jooble's published API examples. This establishes an
access refusal, not a missing secret or a proven invalid key. Ask Jooble API
support to confirm the key is active for **Ireland (ie.jooble.org)** and whether
account, website, quota or IP restrictions apply to the Parsr site and GitHub
Actions requests. Do not paste the key into issues, chat, or logs. A specific
restriction must be resolved through the provider, not worked around.

Later on the same day, replacing Parsr's `JOOBLE_API_KEY` secret restored HTTP 200
from the unchanged Irish API endpoint. The Discord repository's key had already
returned real listings there. Repository secrets are independent: saving a key in
the Discord repository does not update Parsr. To verify a replacement, select
`jooble` in the diagnostic workflow; it checks for an actual `jobs` array as well
as HTTP 200. GitHub does not allow a saved secret's plaintext value to be read.

Both IrishJobs and Jobs.ie timed out from GitHub during the same diagnostic,
while their public search data returned HTTP 200 from the development workspace.
The exact network-side cause remains unconfirmed. If that difference persists,
scheduled collection requires a permitted host with working access or an
approved provider feed/API. A successful manual check here does not repair the
GitHub scheduler. Do not disable TLS verification or bypass browser challenges.

A board connection/access error stops further requests to that board. Pages
already collected are retained and the scan is marked partial; an initial
failure remains a failure, never a successful empty scan. Older records remain
searchable with their original last-seen timestamps.
