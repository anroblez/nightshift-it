"""NightShift IT: collect remote IT jobs from trusted feeds and configured employer boards."""
import datetime
import html
import json
import pathlib
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts" / "approved_employers.json"
OUTPUT = ROOT / 'jobs.json'
NOW = datetime.datetime.now(datetime.timezone.utc)

ROLE = re.compile(r'help[ -]?desk|service[ -]?desk|technical support|it support|desktop support|application support|support analyst|support engineer|noc|network operations|soc analyst|security operations|security analyst|cybersecurity|cloud support|cloud engineer|systems? admin|network admin|it specialist|incident (?:response|manager)|infrastructure support', re.I)
EXCLUDE_ROLE = re.compile(r'\b(senior|sr\.?|principal|staff|director|vice president|head of|architect|sales|account executive|recruiter|physician|nurse)\b', re.I)
REMOTE = re.compile(r'\bremote\b|work from home|work-from-home|telecommut', re.I)
NOT_REMOTE = re.compile(r'\b(on[ -]?site only|in[ -]?office only|hybrid only|not remote|no remote)\b', re.I)
EXCLUDED_LOCATION = re.compile(r'\b(europe only|emea only|uk only|canada only|india only|australia only|latam only|apac only)\b', re.I)
US_LOCATION = re.compile(r'\b(united states|usa|u\.s\.|us only|north america|worldwide|global|anywhere|remote)\b', re.I)
CLEARANCE = re.compile(r'security clearance|secret clearance|top secret|ts/sci|active clearance|clearance required|clearance preferred', re.I)
SHIFT = {
    'overnight': re.compile(r'overnight|night shift|graveyard|third shift|3rd shift', re.I),
    'evening': re.compile(r'evening|late shift|second shift|2nd shift', re.I),
    'weekend': re.compile(r'weekends?|24/7|24x7|24.hour|rotating shift', re.I),
    'flexible': re.compile(r'flexible (?:hours|schedule)|asynchronous|set your own hours', re.I),
    'parttime': re.compile(r'part[ -]?time|less than 30 hours', re.I),
}
items = []
seen = set()

def get(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'NightShiftIT/3.0 (personal job discovery)',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.load(response)

def plain(value):
    return html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))

def add(company, title, url, location, description, posted, source, direct=False, employment=''):
    company, title, url, location = (str(v or '').strip() for v in (company, title, url, location))
    description = plain(description)
    if not company or not title or not url.startswith('https://'):
        return
    if not ROLE.search(title) or EXCLUDE_ROLE.search(title):
        return
    hostname = (urlparse(url).hostname or '').lower()
    if hostname in ('bit.ly', 'tinyurl.com', 't.me', 'wa.me', ''):
        return
    allowed = {
        'Remotive': ('remotive.com',),
        'Arbeitnow': ('arbeitnow.com',),
        'Greenhouse': ('greenhouse.io', 'greenhouse.com'),
        'Lever': ('lever.co',),
    }
    if not any(hostname == domain or hostname.endswith('.' + domain) for domain in allowed[source]):
        return
    if NOT_REMOTE.search(location):
        return
    # Location must indicate remote; descriptions can establish remote status when location is broad.
    if not (REMOTE.search(location) or REMOTE.search(description[:5000])):
        return
    if EXCLUDED_LOCATION.search(location):
        return
    # A location such as 'London, UK' is not evidence of US remote eligibility.
    # Allow remote + city/state labels for employer-direct listings, flagged for verification.
    if location and not US_LOCATION.search(location) and not direct and source != 'Arbeitnow':
        return
    if url in seen:
        return
    seen.add(url)
    schedule_text = ' '.join((title, description[:12000], str(employment)))
    schedule = [name for name, pattern in SHIFT.items() if pattern.search(schedule_text)]
    clearance = 'Mentioned' if CLEARANCE.search(schedule_text) else 'Not mentioned'
    schedule_label = ', '.join(schedule) if schedule else 'Schedule unconfirmed'
    source_label = ('Employer-direct · ' if direct else 'Trusted feed · ') + source
    notes = ('Employer career-board listing.' if direct else 'Third-party feed; confirm on employer career page.')
    notes += ' Verify schedule, U.S. state eligibility, employer legitimacy, and whether the opening is still active.'
    if clearance == 'Mentioned':
        notes += ' Clearance mentioned; check level and requirements.'
    items.append({
        'id': source + ':' + url, 'company': company, 'title': title, 'url': url,
        'location': location or 'Remote (eligibility unconfirmed)',
        'posted': str(posted or ''), 'source': source_label,
        'shift': schedule_label, 'hours': str(employment or ''),
        'evidence': schedule_label, 'clearance': clearance,
        'notes': notes, 'status': 'Saved',
    })

def remotive():
    rows = get('https://remotive.com/api/remote-jobs').get('jobs', [])
    print('Remotive listings received:', len(rows), flush=True)
