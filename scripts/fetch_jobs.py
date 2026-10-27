"""NightShift IT: collect remote IT jobs from job feeds and employer boards."""

import datetime
from collections import Counter
import html
import json
import pathlib
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse


# File locations
ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts" / "approved_employers.json"
OUTPUT = ROOT / "jobs.json"
NOW = datetime.datetime.now(datetime.timezone.utc)


# Job titles to look for
ROLE = re.compile(
    r"help[ -]?desk|service[ -]?desk|"
    r"technical support|it support|desktop support|"
    r"application support|support analyst|support engineer|"
    r"support specialist|support technician|"
    r"noc|network operations|"
    r"soc analyst|security operations|security analyst|cybersecurity|"
    r"cloud support|cloud engineer|"
    r"systems? admin|systems? engineer|network admin|"
    r"it specialist|it technician|it operations analyst|"
    r"incident (?:response|manager|coordinator)|"
    r"infrastructure support|"
    r"site security officer|security operations coordinator|"
    r"personnel security|security clearance coordinator|"
    r"clearance coordinator|"
    r"background (?:screening|investigator|investigation|check)|"
    r"record searcher|trust (?:and|&) safety|"
    r"fraud (?:analyst|investigator|specialist)|risk analyst|"
    r"identity (?:and|&) access|access control analyst|"
    r"compliance analyst|grc analyst|"
    r"technical operations coordinator|osint analyst",
    re.I,
)

# Titles to exclude
EXCLUDE_ROLE = re.compile(
    r"\b(senior|sr\.?|principal|staff|director|vice president|"
    r"head of|architect|sales|account executive|recruiter|"
    r"physician|nurse)\b",
    re.I,
)

# Remote and location keywords
REMOTE = re.compile(
    r"\bremote\b|work from home|work-from-home|telecommut|telework",
    re.I,
)

NOT_REMOTE = re.compile(
    r"\b(on[ -]?site only|in[ -]?office only|hybrid only|not remote|no remote)\b",
    re.I,
)

EXCLUDED_LOCATION = re.compile(
    r"\b(europe only|emea only|uk only|canada only|india only|"
    r"australia only|latam only|apac only)\b",
    re.I,
)

US_LOCATION = re.compile(
    r"\b(united states|usa|u\.s\.|us only|north america|"
    r"worldwide|global|anywhere|remote)\b",
    re.I,
)

CLEARANCE = re.compile(
    r"security clearance|secret clearance|top secret|"
    r"ts/sci|active clearance|clearance required|clearance preferred",
    re.I,
)

# Schedule keywords
SHIFT = {
    "overnight": re.compile(
        r"overnight|night shift|graveyard|third shift|3rd shift",
        re.I,
    ),
    "evening": re.compile(
        r"evening|late shift|second shift|2nd shift",
        re.I,
    ),
    "weekend": re.compile(
        r"weekends?|24/7|24x7|24.hour|rotating shift",
        re.I,
    ),
    "flexible": re.compile(
        r"flexible (?:hours|schedule)|asynchronous|set your own hours",
        re.I,
    ),
    "parttime": re.compile(
        r"part[ -]?time|less than 30 hours",
        re.I,
    ),
}

items = []
seen = set()
rejections = Counter()


def get(url):
    """Retrieve JSON data from a job source."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NightShiftIT/3.0 (personal job discovery)",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=35) as response:
        return json.load(response)


def plain(value):
    """Remove HTML tags from a job description."""
    return html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))


def add(
    company,
    title,
    url,
    location,
    description,
    posted,
    source,
    direct=False,
    employment="",
):
    """Check a job against the filters and add it if it matches."""

    company, title, url, location = (
        str(value or "").strip()
        for value in (company, title, url, location)
    )
    description = plain(description)

    if not company or not title or not url.startswith("https://"):
        rejections["missing fields or invalid URL"] += 1
        return

    if not ROLE.search(title) or EXCLUDE_ROLE.search(title):
        rejections["title not matched or excluded"] += 1
        return

    hostname = (urlparse(url).hostname or "").lower()

    if hostname in ("bit.ly", "tinyurl.com", "t.me", "wa.me", ""):
        rejections["blocked shortlink"] += 1
        return

    allowed = {
        "Remotive": ("remotive.com",),
        "Arbeitnow": ("arbeitnow.com",),
        "Greenhouse": ("greenhouse.io", "greenhouse.com"),
        "Lever": ("lever.co",),
    }

    if not any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in allowed[source]
    ):
        rejections["unapproved link domain"] += 1
        return

    if NOT_REMOTE.search(location):
        rejections["explicitly nonremote location"] += 1
        return

    if not (REMOTE.search(location) or REMOTE.search(description[:5000])):
        rejections["no remote evidence"] += 1
        return

    if EXCLUDED_LOCATION.search(location):
        rejections["restricted international location"] += 1
        return

    if (
        location
        and not US_LOCATION.search(location)
        and not direct
        and source != "Arbeitnow"
    ):
        rejections["location not recognized as US eligible"] += 1
        return

    if url in seen:
        rejections["duplicate URL"] += 1
        return

    seen.add(url)

    schedule_text = " ".join((title, description[:12000], str(employment)))

    schedule = [
        name
        for name, pattern in SHIFT.items()
        if pattern.search(schedule_text)
    ]

    clearance = "Mentioned" if CLEARANCE.search(schedule_text) else "Not mentioned"
    schedule_label = ", ".join(schedule) if schedule else "Schedule unconfirmed"

    if direct:
        notes = "Employer career-board listing."
    else:
        notes = "Third-party feed; confirm on employer career page."

    notes += (
        " Verify schedule, U.S. state eligibility, employer legitimacy, "
        "and whether the opening is still active."
    )

    if clearance == "Mentioned":
        notes += " Clearance mentioned; check level and requirements."

    items.append(
        {
            "id": source + ":" + url,
            "company": company,
            "title": title,
            "url": url,
            "location": location or "Remote (eligibility unconfirmed)",
            "posted": str(posted or ""),
            "source": (
                "Employer-direct · " if direct else "Trusted feed · "
            ) + source,
            "shift": schedule_label,
            "hours": str(employment or ""),
            "evidence": schedule_label,
            "clearance": clearance,
            "notes": notes,
            "status": "Saved",
        }
    )


def remotive():
    """Search the Remotive job feed."""
    rows = get("https://remotive.com/api/remote-jobs").get("jobs", [])
    print("Remotive listings received:", len(rows), flush=True)

    before = len(items)

    for job in rows:
        add(
            job.get("company_name"),
            job.get("title"),
            job.get("url"),
            job.get("candidate_required_location")
            or "Remote (location unconfirmed)",
            job.get("description"),
            job.get("publication_date"),
            "Remotive",
            employment=job.get("job_type"),
        )

    print("Remotive matches added:", len(items) - before, flush=True)


def arbeitnow():
    """Search up to three pages of the Arbeitnow job feed."""
    before = len(items)

    for page in range(1, 4):
        payload = get(
            f"https://www.arbeitnow.com/api/job-board-api?page={page}"
        )
        rows = payload.get("data", [])

        print(
            f"Arbeitnow page {page} listings received: {len(rows)}",
            flush=True,
        )

        if not rows:
            break

        for job in rows:
            if not job.get("remote"):
                rejections["Arbeitnow remote flag false"] += 1
                continue

            add(
                job.get("company_name"),
                job.get("title"),
                job.get("url"),
                job.get("location") or "Remote (location unconfirmed)",
                job.get("description"),
                job.get("created_at"),
                "Arbeitnow",
                employment=" ".join(job.get("job_types") or []),
            )

        if not payload.get("links", {}).get("next"):
            break

    print("Arbeitnow matches added:", len(items) - before, flush=True)


def configured_boards():
    """Search the approved Greenhouse and Lever employer boards."""

    if not CONFIG.exists():
        print("No approved employer config found; skipping employer boards.")
        return

    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    sources = (
        (
            "Greenhouse",
            "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
        ),
        (
            "Lever",
            "https://api.lever.co/v0/postings/{slug}?mode=json",
        ),
    )

    for source, api_template in sources:
        boards = config.get(source.lower(), {})

        if isinstance(boards, dict):
            entries = boards.items()
        elif isinstance(boards, list):
            entries = ((slug, slug) for slug in boards)
        else:
            print(f"Skipping invalid {source} config format.", flush=True)
            continue

        for slug, company in entries:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", str(slug)):
                print(f"Skipping invalid {source} board slug: {slug!r}")
                continue

            try:
                data = get(api_template.format(slug=slug))
                rows = data.get("jobs", []) if source == "Greenhouse" else data
                before = len(items)

                for job in rows:
                    if source == "Greenhouse":
                        add(
                            company,
                            job.get("title"),
                            job.get("absolute_url"),
                            (job.get("location") or {}).get("name", ""),
                            job.get("content", ""),
                            job.get("updated_at", ""),
                            source,
                            direct=True,
                        )
                    else:
                        categories = job.get("categories") or {}

                        add(
                            company,
                            job.get("text"),
                            job.get("hostedUrl"),
                            categories.get("location", ""),
                            job.get("descriptionPlain")
                            or job.get("description")
                            or "",
                            job.get("createdAt", ""),
                            source,
                            direct=True,
                            employment=categories.get("commitment", ""),
                        )

                print(
                    f"{source} {company}: {len(rows)} received, "
                    f"{len(items) - before} matches",
                    flush=True,
                )

            except (urllib.error.URLError, ValueError, TypeError, KeyError) as error:
                print(f"{source} {company}: failed ({error})", flush=True)


def main():
    """Run each source and save the matching jobs."""

    sources = (
        ("Remotive", remotive),
        ("Arbeitnow", arbeitnow),
        ("Employer boards", configured_boards),
    )

    for name, function in sources:
        try:
            function()
        except (urllib.error.URLError, ValueError, TypeError, KeyError) as error:
            print(f"{name} failed: {error}", flush=True)

    print("Rejection breakdown:", dict(rejections), flush=True)

    items.sort(key=lambda job: str(job.get("posted", "")), reverse=True)

    if not items:
        print("No matching jobs collected; leaving existing jobs.json unchanged.")
        return

    payload = {
        "updated_at": NOW.isoformat(),
        "jobs": items,
        "disclaimer": (
            "Candidate matches only; remote eligibility and schedule "
            "are not independently confirmed."
        ),
    }

    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Total jobs written:", len(items), flush=True)


if __name__ == "__main__":
    main()
