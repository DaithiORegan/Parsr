"""Configurable filtering for Irish IT-related roles."""
from __future__ import annotations

import re


def _contains_term(text: str, term: str) -> bool:
    # Whole-word boundaries avoid accidental matches such as 'IT' in 'Digital'.
    return re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", text.casefold()) is not None


def classify(title: str) -> str:
    t = title.casefold()
    if any(k in t for k in ("cyber", "soc ", "security", "grc", "penetration", "incident responder", "iam ")):
        return "Cybersecurity"
    if any(k in t for k in ("network", "noc ", "infrastructure", "cloud", "sysadmin", "system administrator", "systems administrator", "devops", "sre", "site reliability")):
        return "Networking / Infrastructure"
    if any(k in t for k in ("graduate", "intern", "apprentice")):
        return "Graduate / Junior"
    return "IT Support / Technical"


def matching_category(job: dict[str, str], filters: dict) -> str | None:
    title = job["title"]
    location = job["location"]
    if any(_contains_term(title, x) for x in filters.get("exclude_role_keywords", [])):
        return None
    if not any(_contains_term(title, x) for x in filters.get("role_keywords", [])):
        return None
    if not any(_contains_term(location, x) for x in filters.get("country_locations", [])):
        if not (filters.get("include_remote_emea_without_ireland", False)
                and any(_contains_term(location, x) for x in ("EMEA", "Europe", "European Union"))
                and "remote" in location.casefold()):
            return None
    return classify(title)
