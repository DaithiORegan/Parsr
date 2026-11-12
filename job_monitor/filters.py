"""Configurable filtering for Irish IT-related roles."""
from __future__ import annotations

import re


def _contains_term(text: str, term: str) -> bool:
    # Whole-word boundaries avoid accidental matches such as 'IT' in 'Digital'.
    return re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", text.casefold()) is not None


def classify(title: str) -> str:
    t = title.casefold()
    if _contains_term(title, 'administrator') and not any(k in t for k in ('system','network','database','it administrator','cloud','security')):
        return 'Administration'
    # Additional sectors; avoid classifying IT systems administrators as office roles.
    if any(_contains_term(title, k) for k in ('administrative', 'receptionist', 'office assistant', 'office manager', 'executive assistant', 'personal assistant')):
        return 'Administration'
    if any(_contains_term(title, k) for k in ('accountant', 'accounting', 'finance', 'payroll', 'bookkeeper', 'accounts payable', 'accounts receivable', 'financial analyst', 'credit controller')):
        return 'Finance'
    if any(_contains_term(title, k) for k in ('human resources', 'hr advisor', 'hr manager', 'hr business', 'recruiter', 'recruitment', 'talent acquisition', 'people operations')):
        return 'HR & Recruitment'
    if any(_contains_term(title, k) for k in ('sales', 'marketing', 'account executive', 'business development', 'digital marketing', 'brand manager', 'commercial manager')):
        return 'Sales & Marketing'
    if any(_contains_term(title, k) for k in ('nurse', 'nursing', 'healthcare assistant', 'care assistant', 'social care', 'social worker', 'pharmacist', 'physiotherapist', 'occupational therapist')):
        return 'Healthcare & Care'
    if any(_contains_term(title, k) for k in ('retail', 'store manager', 'shop assistant', 'customer assistant', 'chef', 'waiter', 'waitress', 'barista', 'bartender', 'hotel', 'hospitality', 'housekeeping')):
        return 'Retail & Hospitality'
    if any(_contains_term(title, k) for k in ('warehouse', 'logistics', 'supply chain', 'production operator', 'manufacturing', 'procurement', 'delivery driver', 'forklift', 'general operative', 'quality technician')):
        return 'Operations & Logistics'
    if any(_contains_term(title, k) for k in ('electrician', 'plumber', 'carpenter', 'construction', 'quantity surveyor', 'site manager', 'civil engineer', 'maintenance technician', 'mechanic')):
        return 'Construction & Trades'
    if any(_contains_term(title, k) for k in ('teacher', 'lecturer', 'tutor', 'training coordinator', 'early years', 'childcare', 'special needs assistant')):
        return 'Education'
    if any(_contains_term(title, k) for k in ('customer service', 'customer care', 'customer support', 'call centre', 'contact centre')):
        return 'Customer Service'

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
