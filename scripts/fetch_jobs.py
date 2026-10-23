
import datetime, html, json, os, pathlib, re, urllib.request
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = datetime.datetime.now(datetime.timezone.utc)
# Add confirmed employer board identifiers to scripts/approved_employers.json.
CONFIG = pathlib.Path(__file__).with_name('approved_employers.json')
DEFAULT = {'greenhouse': {}, 'lever': {}}
config = json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.exists() else DEFAULT

ROLE = re.compile(r'help\s*desk|service\s*desk|technical support|it support|desktop support|application support|support analyst|support engineer|technical support engineer|noc|network operations|soc|security operations|security analyst|cybersecurity analyst|cloud support|cloud engineer|systems? administrator|network administrator|it specialist|incident (?:response|manager)|infrastructure support', re.I)
BAD_ROLE = re.compile(r'\b(senior|sr\.?|principal|staff|director|vice president|vp|head of|architect|sales|account executive|recruiter|physician|nurse)\b', re.I)
SHIFT = {'overnight': re.compile(r'overnight|night shift|graveyard|third shift|3rd shift', re.I), 'evening': re.compile(r'evening|late shift|second shift|2nd shift', re.I), 'weekend': re.compile(r'weekends?|24/7|24x7|24.hour|rotating shift', re.I), 'flexible': re.compile(r'flexible (?:hours|schedule)|asynchronous|set your own hours', re.I), 'parttime': re.compile(r'part.time|part time|less than 30 hours', re.I)}
REMOTE = re.compile(r'\bremote\b|work from home|work-from-home|telecommut', re.I)
NOT_REMOTE = re.compile(r'\b(on.?site only|onsite only|in.office only|hybrid only|not remote|no remote)\b', re.I)
US = re.compile(r'\b(united states|u\.?s\.?a?\.?|us only|usa only|north america|anywhere in the us|anywhere in the united states)\b', re.I)
EXCLUDED = re.compile(r'\b(europe only|emea only|uk only|canada only|india only|australia only|latam only|apac only)\b', re.I)
CLEARANCE = re.compile(r'\b(secret clearance|top secret|ts/sci|security clearance|active clearance|clearance required|clearance preferred)\b', re.I)
items = []
stats = {}

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'NightShiftIT/2.0 (personal job discovery)', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def plain(s):
    return html.unescape(re.sub(r'<[^>]*>', ' ', str(s or '')))

def add(company, title, url, location, description, date, source, direct=False, employment=''):
    company, title, location, url = (str(v or '').strip() for v in (company, title, location, url))
    description = plain(description)
    if not company or not title or not url.startswith('https://'):
        return
    if not ROLE.search(title) or BAD_ROLE.search(title):
        return
    host = (urlparse(url).hostname or '').lower()
    if not host or host in {'bit.ly', 'tinyurl.com', 't.me', 'wa.me'}:
        return
    if source == 'Remotive' and host not in {'remotive.com', 'www.remotive.com'}:
        return
    if source == 'Arbeitnow' and not host.endswith('arbeitnow.com'):
        return
    if source == 'Greenhouse' and not (host.endswith('greenhouse.io') or host.endswith('greenhouse.com')):
        return
    if source == 'Lever' and not host.endswith('lever.co'):
        return
    # Require explicit remote wording. Employer board location is the strongest signal.
    if NOT_REMOTE.search(location) or not (REMOTE.search(location) or REMOTE.search(description[:4500])):
        return
    if EXCLUDED.search(location) or (location and not US.search(location) and not REMOTE.fullmatch(location) and not re.search(r'worldwide|global|anywhere', location, re.I) and source != 'Arbeitnow'):
        # Unknown location is not proof of U.S. eligibility. Only accept US/remote/global location labels.
        return
    if re.search(r'worldwide|global|anywhere', location, re.I) and not US.search(location):
        # Worldwide may include US, but label as unconfirmed.
        pass
    schedule_text = ' '.join((title, description[:12000], employment))
    matches = [name for name, rx in SHIFT.items() if rx.search(schedule_text)]
    clearance = 'Mentioned' if CLEARANCE.search(schedule_text) else 'Not mentioned'
    label = ', '.join(matches) if matches else 'Schedule unconfirmed'
    notes = ('Employer-direct listing' if direct else 'Trusted job feed; verify on employer site') + '; confirm schedule, U.S. state eligibility, and whether the position remains open.'
    if clearance == 'Mentioned':
        notes += ' Clearance mentioned; verify required level.'
    items.append({'id': source + ':' + url, 'company': company, 'title': title, 'url': url,
                  'location': location or 'Remote (eligibility unconfirmed)', 'posted': str(date or ''),
                  'source': ('Employer-direct · ' + source) if direct else ('Trusted feed · ' + source),
                  'shift': label, 'hours': employment, 'evidence': label, 'clearance': clearance,
                  'notes': notes, 'status': 'Saved'})

def fetch_remotive():
    data = get('https://remotive.com/api/remote-jobs')
    rows = data.get('jobs', [])
    print('Remotive received:', len(rows))
    for x in rows:
        add(x.get('company_name'), x.get('title'), x.get('url'), x.get('candidate_required_location', ''), x.get('description'), x.get('publication_date'), 'Remotive', employment=x.get('job_type', ''))

def fetch_arbeitnow():
    data = get('https://www.arbeitnow.com/api/job-board-api')
    rows = data.get('data', [])
    print('Arbeitnow received:', len(rows))
    for x in rows:
        if x.get('remote'):
            add(x.get('company_name'), x.get('title'), x.get('url'), 'Remote', x.get('description'), x.get('created_at'), 'Arbeitnow')

def fetch_greenhouse(company, token):
    data = get('https://boards-api.greenhouse.io/v1/boards/' + token + '/jobs?content=true')
    rows = data.get('jobs', [])
    print('Greenhouse', company, 'received:', len(rows))
    for x in rows:
        if x.get('internal_job_id', 1) is None:
            continue
        add(company, x.get('title'), x.get('absolute_url'), (x.get('location') or {}).get('name', ''), x.get('content'), x.get('updated_at'), 'Greenhouse', True)

def fetch_lever(company, token):
    rows = get('https://api.lever.co/v0/postings/' + token + '?mode=json&limit=100')
    print('Lever', company, 'received:', len(rows))
