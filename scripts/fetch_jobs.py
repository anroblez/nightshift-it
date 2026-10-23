"""NightShift IT: collect remote IT jobs from trusted feeds and configured employer boards."""
import datetime
from collections import Counter
import html
import json
import pathlib
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'scripts' / 'approved_employers.json'
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
rejections = Counter()


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
        rejections['missing fields or invalid URL'] += 1
        return
    if not ROLE.search(title) or EXCLUDE_ROLE.search(title):
        rejections['title not matched or excluded'] += 1
        return
    hostname = (urlparse(url).hostname or '').lower()
    if hostname in ('bit.ly', 'tinyurl.com', 't.me', 'wa.me', ''):
        rejections['blocked shortlink'] += 1
        return
    allowed = {
        'Remotive': ('remotive.com',),
        'Arbeitnow': ('arbeitnow.com',),
        'Greenhouse': ('greenhouse.io', 'greenhouse.com'),
        'Lever': ('lever.co',),
    }
    if not any(hostname == domain or hostname.endswith('.' + domain) for domain in allowed[source]):
        rejections['unapproved link domain'] += 1
        return
    if NOT_REMOTE.search(location):
        rejections['explicitly nonremote location'] += 1
        return
    if not (REMOTE.search(location) or REMOTE.search(description[:5000])):
        rejections['no remote evidence'] += 1
        return
    if EXCLUDED_LOCATION.search(location):
        rejections['restricted international location'] += 1
        return
    if location and not US_LOCATION.search(location) and not direct and source != 'Arbeitnow':
        rejections['location not recognized as US eligible'] += 1
        return
    if url in seen:
        rejections['duplicate URL'] += 1
        return
    seen.add(url)
    schedule_text = ' '.join((title, description[:12000], str(employment)))
    schedule = [name for name, pattern in SHIFT.items() if pattern.search(schedule_text)]
    clearance = 'Mentioned' if CLEARANCE.search(schedule_text) else 'Not mentioned'
    schedule_label = ', '.join(schedule) if schedule else 'Schedule unconfirmed'
    notes = ('Employer career-board listing.' if direct else 'Third-party feed; confirm on employer career page.')
    notes += ' Verify schedule, U.S. state eligibility, employer legitimacy, and whether the opening is still active.'
    if clearance == 'Mentioned':
        notes += ' Clearance mentioned; check level and requirements.'
    items.append({
        'id': source + ':' + url, 'company': company, 'title': title, 'url': url,
        'location': location or 'Remote (eligibility unconfirmed)',
        'posted': str(posted or ''),
        'source': ('Employer-direct · ' if direct else 'Trusted feed · ') + source,
        'shift': schedule_label, 'hours': str(employment or ''),
        'evidence': schedule_label, 'clearance': clearance,
        'notes': notes, 'status': 'Saved',
    })


def remotive():
    rows = get('https://remotive.com/api/remote-jobs').get('jobs', [])
    print('Remotive listings received:', len(rows), flush=True)
    before = len(items)
    for j in rows:
        add(j.get('company_name'), j.get('title'), j.get('url'),
            j.get('candidate_required_location') or 'Remote (location unconfirmed)',
            j.get('description'), j.get('publication_date'), 'Remotive',
            employment=j.get('job_type'))
    print('Remotive matches added:', len(items) - before, flush=True)


def arbeitnow():
    before = len(items)
    for page in range(1, 4):
        payload = get(f'https://www.arbeitnow.com/api/job-board-api?page={page}')
        rows = payload.get('data', [])
        print(f'Arbeitnow page {page} listings received:', len(rows), flush=True)
        if not rows:
            break
        for j in rows:
            if not j.get('remote'):
                rejections['Arbeitnow remote flag false'] += 1
                continue
            add(j.get('company_name'), j.get('title'), j.get('url'),
                j.get('location') or 'Remote (location unconfirmed)',
                j.get('description'), j.get('created_at'), 'Arbeitnow',
                employment=' '.join(j.get('job_types') or []))
        if not payload.get('links', {}).get('next'):
            break
    print('Arbeitnow matches added:', len(items) - before, flush=True)


def configured_boards():
    if not CONFIG.exists():
        print('No approved employer config found; skipping employer boards.', flush=True)
        return
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    for source, api_template in (
        ('Greenhouse', 'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true'),
        ('Lever', 'https://api.lever.co/v0/postings/{slug}?mode=json'),
    ):
        boards = cfg.get(source.lower(), {})
        if isinstance(boards, dict):
            entries = boards.items()
        elif isinstance(boards, list):
            entries = ((slug, slug) for slug in boards)
        else:
            print(f'Skipping invalid {source} config format.', flush=True)
            continue
        for slug, company in entries:
            if not re.fullmatch(r'[A-Za-z0-9_-]+', str(slug)):
                print(f'Skipping invalid {source} board slug: {slug!r}', flush=True)
                continue
            try:
                data = get(api_template.format(slug=slug))
                rows = data.get('jobs', []) if source == 'Greenhouse' else data
                before = len(items)
                for j in rows:
                    if source == 'Greenhouse':
                        add(company, j.get('title'), j.get('absolute_url'),
                            (j.get('location') or {}).get('name', ''),
                            j.get('content', ''), j.get('updated_at', ''), source, direct=True)
                    else:
                        categories = j.get('categories') or {}
                        add(company, j.get('text'), j.get('hostedUrl'),
                            categories.get('location', ''),
                            j.get('descriptionPlain') or j.get('description') or '',
                            j.get('createdAt', ''), source, direct=True,
                            employment=categories.get('commitment', ''))
                print(f'{source} {company}: {len(rows)} received, {len(items)-before} matches', flush=True)
            except (urllib.error.URLError, ValueError, TypeError, KeyError) as e:
                print(f'{source} {company}: failed ({e})', flush=True)


def main():
    for name, fn in (('Remotive', remotive), ('Arbeitnow', arbeitnow), ('Employer boards', configured_boards)):
        try:
            fn()
        except (urllib.error.URLError, ValueError, TypeError, KeyError) as e:
            print(f'{name} failed: {e}', flush=True)
    print('Rejection breakdown:', dict(rejections), flush=True)
    items.sort(key=lambda j: str(j.get('posted', '')), reverse=True)
    if not items:
        print('No matching jobs collected; leaving existing jobs.json unchanged.', flush=True)
        return
    payload = {
        'updated_at': NOW.isoformat(),
        'jobs': items,
        'disclaimer': 'Candidate matches only; remote eligibility and schedule are not independently confirmed.',
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Total jobs written:', len(items), flush=True)


if __name__ == '__main__':
    main()
