"""Read published jobs from documented public job APIs and syndication feeds.

No logins, CAPTCHA bypass, or browser scraping are used.
"""
from __future__ import annotations

import csv
import os
from xml.etree import ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def load_sources(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(line for line in handle if not line.lstrip().startswith("#"))
        rows = []
        for row in reader:
            provider = (row.get("provider") or "").strip().lower()
            slug = (row.get("slug") or "").strip()
            company = (row.get("company") or "").strip()
            if provider and slug and company:
                if provider not in {"greenhouse", "ashby", "lever", "smartrecruiters", "recruitee", "jooble", "remotive", "rss", "jobsie", "irishjobs", "workday"}:
                    raise ValueError(f"Unsupported provider: {provider}")
                if not all(c.isalnum() or c in "-_" for c in slug):
                    raise ValueError(f"Invalid board slug: {slug}")
                url = (row.get("url") or "").strip()
                if provider == "rss" and (not url.startswith("https://") or not urlparse(url).hostname):
                    raise ValueError(f"RSS source {slug} requires an HTTPS feed URL")
                rows.append({"provider": provider, "slug": slug, "company": company, "url": url,
                             "key": f"{provider}:{slug}"})
        return rows


def session_with_retries() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "IrishITJobMonitor/2.1 (personal job search; public feeds)", "Accept": "application/json, application/xml, text/xml;q=0.9"})
    adapter = HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]))
    session.mount("https://", adapter)
    return session


def _get_json(session: requests.Session, url: str, params: dict[str, str] | None = None) -> Any:
    resp = session.get(url, params=params, timeout=25)
    resp.raise_for_status()
    return resp.json()


def _clean_job(provider: str, source: dict[str, str], raw_id: str, title: str, locations: list[str], url: str, salary: str = "", posted: str = "", description: str = "") -> dict[str, str]:
    location = "; ".join(dict.fromkeys(x.strip() for x in locations if x and x.strip())) or "Unspecified"
    return {
        "id": f"{provider}:{source['slug']}:{raw_id}",
        "provider": provider,
        "company": source["company"],
        "title": title.strip(),
        "location": location,
        "url": url,
        "salary": salary.strip(),
        "posted": str(posted or "")[:32],
        "description": str(description or "")[:6000],
    }


def greenhouse(session: requests.Session, source: dict[str, str]) -> list[dict[str, str]]:
    board = quote(source["slug"], safe="")
    data = _get_json(session, f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", {"content":"true"})
    result = []
    for j in data.get("jobs", []):
        if not j.get("id") or not j.get("title"):
            continue
        loc = j.get("location") or {}
        loc_name = loc.get("name", "") if isinstance(loc, dict) else str(loc)
        url = j.get("absolute_url") or f"https://job-boards.greenhouse.io/{board}/jobs/{j['id']}"
        result.append(_clean_job("greenhouse", source, str(j["id"]), j["title"], [loc_name], url, posted=j.get("updated_at", ""), description=j.get("content", "")))
    return result


def ashby(session: requests.Session, source: dict[str, str]) -> list[dict[str, str]]:
    board = quote(source["slug"], safe="")
    data = _get_json(session, f"https://api.ashbyhq.com/posting-api/job-board/{board}", {"includeCompensation": "true"})
    result = []
    for j in data.get("jobs", []):
        if not j.get("title") or j.get("isListed") is False:
            continue
        locations = [j.get("location", "")]
        locations.extend(x.get("location", "") for x in j.get("secondaryLocations", []) if isinstance(x, dict))
        salary_data = j.get("compensation") or {}
        salary = salary_data.get("scrapeableCompensationSalarySummary") or salary_data.get("compensationTierSummary") or ""
        url = j.get("jobUrl") or j.get("applyUrl") or ""
        if not url:
            continue
        raw_id = str(j.get("id") or url.rsplit("/", 1)[-1])
        result.append(_clean_job("ashby", source, raw_id, j["title"], locations, url, salary=salary, description=j.get("descriptionPlain", "") or j.get("descriptionHtml", "")))
    return result


def lever(session: requests.Session, source: dict[str, str]) -> list[dict[str, str]]:
    site = quote(source["slug"], safe="")
    result = []
    # Public Lever postings API returns at most 100 jobs per request.
    for skip in range(0, 1000, 100):
        jobs = _get_json(session, f"https://api.lever.co/v0/postings/{site}", {"mode": "json", "skip": str(skip), "limit": "100"})
        if not isinstance(jobs, list):
            raise ValueError(f"Lever API returned unexpected data for {site}")
        for j in jobs:
            if not j.get("id") or not j.get("text"):
                continue
            categories = j.get("categories") or {}
            locations = [categories.get("location", "")]
            locations.extend(j.get("allLocations") or [])
            url = j.get("hostedUrl") or j.get("applyUrl") or ""
            if not url:
                continue
            result.append(_clean_job("lever", source, str(j["id"]), j["text"], locations, url, posted=j.get("createdAt", ""), description=j.get("descriptionPlain", "")))
        if len(jobs) < 100:
            break
    return result


def smartrecruiters(session: requests.Session, source: dict[str, str]) -> list[dict[str, str]]:
    """SmartRecruiters public Posting API, paginated with limit and offset.

    Not every SmartRecruiters customer permits external reuse; only add verified,
    permitted company boards to config/sources.csv.
    """
    slug = quote(source["slug"], safe="")
    base_url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    result = []
    for offset in range(0, 5000, 100):
        payload = _get_json(session, base_url, {"limit": "100", "offset": str(offset)})
        jobs = payload.get("content", [])
        if not isinstance(jobs, list):
            raise ValueError(f"SmartRecruiters API returned unexpected data for {slug}")
        for j in jobs:
            if not j.get("id") or not j.get("name"):
                continue
            loc = j.get("location") or {}
            parts = [str(loc.get(k) or "") for k in ("city", "region", "country")]
            if parts[-1].upper() == "IE":
                parts[-1] = "Ireland"
            location = ", ".join(x for x in parts if x)
            url = j.get("applyUrl") or f"https://jobs.smartrecruiters.com/{slug}/{j['id']}"
            result.append(_clean_job("smartrecruiters", source, str(j["id"]), j["name"], [location], url, posted=j.get("releasedDate", "")))
        if len(jobs) < 100 or len(result) >= int(payload.get("totalFound", 5000)):
            break
    return result




def source_availability(source: dict[str, str]) -> tuple[bool, str]:
    """Credentials are optional. Do not record unconfigured sources as failures/baselined."""
    if source["provider"] == "jooble" and not os.getenv("JOOBLE_API_KEY", "").strip():
        return False, "requires JOOBLE_API_KEY (free Irish Jooble API key)"
    return True, "ready"


def recruitee(session: requests.Session, source: dict[str, str]) -> list[dict[str, str]]:
    """Published-only Recruitee XML vacancy feed; no Recruitee Careers API token needed."""
    slug = source["slug"]
    resp = session.get(f"https://{slug}.recruitee.com/api/feeds/offers.xml", timeout=25)
    resp.raise_for_status()
    if len(resp.content) > 8_000_000:
        raise ValueError("Recruitee XML feed larger than 8 MB")
    root = ET.fromstring(resp.content)
    result = []
    for j in root.findall(".//job"):
        raw_id = (j.findtext("reference") or "").strip()
        title = (j.findtext("title") or "").strip()
        url = (j.findtext("url") or j.findtext("apply_url") or "").strip()
        if not (raw_id and title and url.startswith("https://")):
            continue
        locations = []
        for loc in j.findall("./locations/location"):
            city = (loc.findtext("city") or "").strip()
            country = (loc.findtext("country") or "").strip()
            if country.upper() == "IE":
                country = "Ireland"
            locations.append(", ".join(x for x in (city, country) if x))
        if not locations:
            country = (j.findtext("country") or "").strip()
            if country.upper() == "IE":
                country = "Ireland"
            locations = [", ".join(x for x in ((j.findtext("city") or "").strip(), country) if x)]
        salary_node = j.find("salary")
        salary = ""
        if salary_node is not None:
            lo, hi = salary_node.findtext("min_salary"), salary_node.findtext("max_salary")
            curr, period = salary_node.findtext("currency"), salary_node.findtext("period")
            if lo or hi:
                salary = f"{curr or ''} {(lo or '').strip()} - {(hi or '').strip()} / {(period or '').strip()}".strip()
        result.append(_clean_job("recruitee", source, raw_id, title, locations, url,
                                 salary=salary, posted=j.findtext("posted") or "", description=j.findtext("description") or ""))
    return result


# Fewer than 100 daily Jooble requests: 8 terms x 2 pages x 2 scheduled scans = 32.
JOOBLE_TERMS = (
    "IT support", "technical support", "helpdesk", "cybersecurity",
    "network engineer", "systems administrator", "IT technician", "SOC analyst",
)


def jooble(session: requests.Session, source: dict[str, str]) -> list[dict[str, str]]:
    """Jooble Ireland official REST API; requires country-specific key from ie.jooble.org."""
    key = os.environ["JOOBLE_API_KEY"].strip()
    # Only official Irish endpoint; no browser scraping / session cookie handling.
    api_url = f"https://ie.jooble.org/api/{quote(key, safe='')}"
    result: list[dict[str, str]] = []
    for term in JOOBLE_TERMS:
        for page in (1, 2):
            payload = {"keywords": term, "location": "Ireland", "page": str(page), "ResultOnPage": "50"}
            r = session.post(api_url, json=payload, timeout=25)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data.get("jobs"), list):
                raise ValueError("Jooble API returned unexpected jobs payload")
            for j in data["jobs"]:
                jid, title, url = j.get("id"), j.get("title"), j.get("link")
                if not jid or not title or not url:
                    continue
                # Jooble search may return locations outside the specified country.
                result.append(_clean_job("jooble", source, str(jid), str(title),
                          [str(j.get("location") or "")], str(url),
                          salary=str(j.get("salary") or ""), posted=str(j.get("updated") or ""), description=str(j.get("snippet") or "")))
                result[-1]["company"] = str(j.get("company") or "Unknown company")
            if len(data["jobs"]) < 50:
                break
    return result


def remotive(session: requests.Session, source: dict[str, str]) -> list[dict[str, str]]:
    """Remote jobs with explicit Ireland/Europe/Worldwide location eligibility.

    The provider requires attribution and permits up to four daily API checks.
    """
    data = _get_json(session, "https://remotive.com/api/remote-jobs")
    result = []
    for j in data.get("jobs", []):
        eligible = str(j.get("candidate_required_location") or "").strip()
        v = eligible.casefold()
        if not any(t in v for t in ("ireland", "worldwide", "anywhere", "europe", "global")):
            continue
        if not (j.get("id") and j.get("title") and j.get("url")):
            continue
        result.append(_clean_job("remotive", source, str(j["id"]), str(j["title"]),
                    [f"Ireland-eligible remote ({eligible})"], str(j["url"]),
                    salary=str(j.get("salary") or ""), posted=str(j.get("publication_date") or ""), description=str(j.get("description") or "")))
        result[-1]["company"] = str(j.get("company_name") or "Unknown company")
    return result


def rss(session: requests.Session, source: dict[str, str]) -> list[dict[str, str]]:
    """Generic RSS 2.0 / Atom feeds, enabled only for actual documented public feeds.

    Nonstandard feeds without a location are ignored by the downstream Ireland filter.
    """
    url = source["url"]
    resp = session.get(url, timeout=25)
    resp.raise_for_status()
    if len(resp.content) > 8_000_000:
        raise ValueError("RSS/Atom feed larger than 8 MB")
    root = ET.fromstring(resp.content)
    result = []
    for j in root.findall(".//item"):
        title = j.findtext("title") or ""
        link = j.findtext("link") or ""
        raw_id = j.findtext("guid") or link
        location = j.findtext("location") or j.findtext("{http://purl.org/dc/elements/1.1/}coverage") or ""
        if title and link.startswith("https://"):
            result.append(_clean_job("rss", source, str(raw_id), title, [location], link,
                                     posted=j.findtext("pubDate") or ""))
    atom = "{http://www.w3.org/2005/Atom}"
    for j in root.findall(f".//{atom}entry"):
        title = j.findtext(f"{atom}title") or ""
        links = [node.get("href", "") for node in j.findall(f"{atom}link")]
        link = next((link for link in links if link.startswith("https://")), "")
        raw_id = j.findtext(f"{atom}id") or link
        location = j.findtext("location") or ""
        if title and link:
            result.append(_clean_job("rss", source, str(raw_id), title, [location], link,
                                     posted=j.findtext(f"{atom}published") or ""))
    return result

from job_monitor.boards import search_board
from job_monitor.workday import workday

COLLECTORS = {"workday": workday, "jobsie": search_board, "irishjobs": search_board, "greenhouse": greenhouse, "ashby": ashby, "lever": lever, "smartrecruiters": smartrecruiters, "recruitee": recruitee, "jooble": jooble, "remotive": remotive, "rss": rss}


def collect(session: requests.Session, sources: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[str], set[str]]:
    all_jobs = []
    failures = []
    successful_sources: set[str] = set()
    for source in sources:
        name = f"{source['company']} ({source['provider']})"
        try:
            jobs = COLLECTORS[source["provider"]](session, source)
            successful_sources.add(source.get("key") or f"{source['provider']}:{source['slug']}")
            all_jobs.extend(jobs)
            print(f"[OK] {name}: {len(jobs)} published jobs")
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            # Never log exception URLs: Jooble embeds an API key in its endpoint path.
            # GitHub masks configured secrets, but avoiding URLs here is safer.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            detail = f"HTTP {status}" if status else type(exc).__name__
            failures.append(f"{name}: {detail}")
            print(f"[ERROR] {name}: {detail}")
    return all_jobs, failures, successful_sources

