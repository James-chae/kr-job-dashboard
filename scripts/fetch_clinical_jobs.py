
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
OUTPUT_PATH = DATA_DIR / 'clinical_jobs.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
}

KEYWORDS = [
    '임상병리', '임상병리사', '진단검사', '진단검사의학', '검체', '병리사', '의료기사'
]
REGION_KEYWORDS = ['서울', '경기', '성남', '분당', '수원', '안양', '용인', '부천', '고양', '의정부']

SOURCES = [
    {
        'name': '사람인 임상병리',
        'url': 'https://m.saramin.co.kr/job-industry/job-list?cat_kewd=559&is_detail_search=y',
        'source_type': 'job-board',
    },
    {
        'name': '서울의료원 채용',
        'url': 'https://www.seoulmc.or.kr/site/recruit/recruitList.do',
        'source_type': 'hospital',
    },
    {
        'name': '국립암센터 채용',
        'url': 'https://ncc.recruiter.co.kr/app/jobnotice/list',
        'source_type': 'hospital',
    },
    {
        'name': '분당서울대병원 채용',
        'url': 'https://recruit.snubh.org/main/recruit/recruit_list.do',
        'source_type': 'hospital',
    },
]

DATE_PATTERNS = [
    re.compile(r'(20\d{2})[./-](\d{1,2})[./-](\d{1,2})'),
    re.compile(r'(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일'),
]

SPACE_RE = re.compile(r'\s+')
TAG_RE = re.compile(r'<[^>]+>')

@dataclass
class Job:
    id: str
    title: str
    organization: str
    category: str = 'clinical'
    track: str = 'clinical'
    region: str = '서울/경기'
    employmentType: str = '임상병리'
    postedAt: str = ''
    deadline: str = ''
    status: str = 'unknown'
    source: str = ''
    sourceType: str = 'hospital'
    url: str = ''
    description: str = ''

    def to_dict(self):
        return self.__dict__


def session_with_retries() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def norm_text(text: str) -> str:
    text = text or ''
    text = TAG_RE.sub(' ', text)
    text = SPACE_RE.sub(' ', text).strip()
    return text


def extract_date(text: str) -> str:
    for pat in DATE_PATTERNS:
        m = pat.search(text or '')
        if m:
            y, mo, d = m.groups()
            return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
    return ''


def keyword_match(text: str) -> bool:
    t = norm_text(text)
    return any(k in t for k in KEYWORDS)


def region_from_text(text: str) -> str:
    t = norm_text(text)
    for k in REGION_KEYWORDS:
        if k in t:
            return '서울' if k == '서울' else '경기'
    return '서울/경기'


def make_id(prefix: str, title: str, org: str, url: str) -> str:
    seed = f'{prefix}|{title}|{org}|{url}'
    return f'clinical-{abs(hash(seed))}'


def add_job(jobs, seen, title, org, source_name, source_type, url, snippet=''):
    title = norm_text(title)
    org = norm_text(org) or source_name
    snippet = norm_text(snippet)
    blob = ' '.join([title, org, snippet])
    if not title or not keyword_match(blob):
        return
    region = region_from_text(blob)
    posted = extract_date(blob)
    deadline = ''
    status = 'unknown'
    key = (title, org, url)
    if key in seen:
        return
    seen.add(key)
    jobs.append(Job(
        id=make_id(source_name, title, org, url),
        title=title,
        organization=org,
        region=region,
        postedAt=posted,
        deadline=deadline,
        status=status,
        source=source_name,
        sourceType=source_type,
        url=url,
        description=snippet[:140],
    ).to_dict())


def parse_saramin(html: str, base_url: str, jobs, seen):
    soup = BeautifulSoup(html, 'html.parser')
    # generic anchors + text fallback
    for a in soup.select('a'):
        text = norm_text(a.get_text(' ', strip=True))
        href = urljoin(base_url, a.get('href') or '')
        if not href:
            continue
        parent_text = norm_text(a.parent.get_text(' ', strip=True)) if a.parent else text
        add_job(jobs, seen, text, '사람인', '사람인 임상병리', 'job-board', href, parent_text)


def parse_generic_list(html: str, base_url: str, source_name: str, source_type: str, jobs, seen):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a'):
        text = norm_text(a.get_text(' ', strip=True))
        if len(text) < 4:
            continue
        href = urljoin(base_url, a.get('href') or '')
        ctx = norm_text(a.parent.get_text(' ', strip=True)) if a.parent else text
        add_job(jobs, seen, text, source_name, source_name, source_type, href, ctx)


def text_fallback(html: str, source_name: str, source_type: str, base_url: str, jobs, seen):
    # Pull keyword-centered windows from full text when anchors fail.
    text = norm_text(BeautifulSoup(html, 'html.parser').get_text(' ', strip=True))
    for kw in KEYWORDS:
        for m in re.finditer(re.escape(kw), text):
            start = max(0, m.start() - 35)
            end = min(len(text), m.end() + 85)
            snippet = text[start:end]
            title = snippet[:80]
            add_job(jobs, seen, title, source_name, source_name, source_type, base_url, snippet)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sess = session_with_retries()
    jobs = []
    seen = set()
    errors = []

    for src in SOURCES:
        try:
            r = sess.get(src['url'], timeout=20)
            r.encoding = r.apparent_encoding or r.encoding or 'utf-8'
            html = r.text
            if src['name'].startswith('사람인'):
                parse_saramin(html, src['url'], jobs, seen)
            else:
                parse_generic_list(html, src['url'], src['name'], src['source_type'], jobs, seen)
            if not jobs:
                text_fallback(html, src['name'], src['source_type'], src['url'], jobs, seen)
        except Exception as e:
            errors.append(f"{src['url']}: {e}")

    payload = {
        'meta': {
            'generatedAt': __import__('datetime').datetime.now().isoformat(),
            'source': 'clinical',
            'count': len(jobs),
            'sources': [s['url'] for s in SOURCES],
            'errors': errors,
        },
        'jobs': jobs,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[OK] clinical_jobs.json saved ({len(jobs)} jobs)")
    if errors:
        print('[WARN] partial errors detected:')
        for err in errors:
            print(' -', err)


if __name__ == '__main__':
    main()
