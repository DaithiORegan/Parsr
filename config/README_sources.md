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
