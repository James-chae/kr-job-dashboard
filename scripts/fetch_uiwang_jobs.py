
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = DATA_DIR / "uiwang_jobs.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

LIST_URLS = [
    "https://www.uiwang.go.kr/UWKORINFO1801",
    "https://www.uiwang.go.kr/UWKORINFO1002",
    "https://www.uiwang.go.kr/UWKORINFO1001",
]

GENERIC_TITLES = {
    "채용공고",
    "지난 채용공고",
    "기타 채용공고",
    "의왕시청",
    "의왕시",
}

KEYWORDS = [
    "채용", "모집", "기간제", "공개채용", "직원", "근로자", "인턴", "상임이사",
    "센터", "공사", "사무국", "클럽", "가족센터", "장애인", "컨설턴트",
]

DATE_PATTERNS = [
    re.compile(r"(20\d{2})[.\-/년 ]\s*(\d{1,2})[.\-/월 ]\s*(\d{1,2})"),
]

RANGE_PATTERNS = [
    re.compile(
        r"(20\d{2})[.\-/년 ]\s*(\d{1,2})[.\-/월 ]\s*(\d{1,2}).{0,10}?"
        r"(20\d{2})[.\-/년 ]\s*(\d{1,2})[.\-/월 ]\s*(\d{1,2})"
    )
]


@dataclass
class Job:
    id: str
    title: str
    organization: str
    category: str
    track: str
    region: str
    employmentType: str
    postedAt: str
    deadline: str
    source: str
    sourceType: str
    url: str
    description: str


def session_with_retries() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text


def normalize_date(y: str, m: str, d: str) -> str:
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except Exception:
        return ""


def parse_single_date(text: str) -> str:
    for pat in DATE_PATTERNS:
        m = pat.search(text or "")
        if m:
            return normalize_date(*m.groups())
    return ""


def parse_date_range(text: str) -> tuple[str, str]:
    text = text or ""
    for pat in RANGE_PATTERNS:
        m = pat.search(text)
        if m:
            y1, mo1, d1, y2, mo2, d2 = m.groups()
            return normalize_date(y1, mo1, d1), normalize_date(y2, mo2, d2)
    d = parse_single_date(text)
    return d, ""


def looks_like_job_title(title: str) -> bool:
    t = clean_text(title)
    if not t or t in GENERIC_TITLES:
        return False
    if len(t) < 4:
        return False
    return any(k in t for k in KEYWORDS)


def summarize(text: str, max_len: int = 140) -> str:
    text = clean_text(text)
    # remove menu boilerplate
    text = re.sub(r"(로그인|회원가입|고객센터|사이트맵|개인정보처리방침)", "", text)
    text = clean_text(text)
    return text[:max_len].rstrip() + ("..." if len(text) > max_len else "")


def extract_links_from_list(url: str, html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[tuple[str, str]] = []

    # broad anchor scan, but keep only plausible job titles
    for a in soup.select("a[href]"):
        title = clean_text(a.get_text(" ", strip=True))
        href = a.get("href") or ""
        full = urljoin(url, href)
        if not looks_like_job_title(title):
            continue
        if urlparse(full).netloc and "uiwang.go.kr" not in full:
            continue
        items.append((title, full))

    # de-dup while preserving order
    seen = set()
    deduped = []
    for title, full in items:
        key = (title, full)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((title, full))
    return deduped[:20]


def find_title(soup: BeautifulSoup, fallback: str) -> str:
    selectors = [
        "h1", "h2", "h3",
        ".bo_v_tit", ".view_tit", ".board-view-title",
        ".title", ".subject",
    ]
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            t = clean_text(node.get_text(" ", strip=True))
            if looks_like_job_title(t):
                return t
    og = soup.select_one("meta[property='og:title']")
    if og and og.get("content"):
        t = clean_text(og["content"])
        if looks_like_job_title(t):
            return t
    return fallback


def extract_posted_deadline(text: str) -> tuple[str, str]:
    posted = ""
    deadline = ""

    # explicit labels first
    m_post = re.search(r"(게시일|등록일|작성일)\s*[:：]?\s*(20\d{2}[^ ]+)", text)
    if m_post:
        posted = parse_single_date(m_post.group(2))

    m_dead = re.search(r"(마감일|접수마감|공고기간|채용기간|접수기간)\s*[:：]?\s*(.+)", text)
    if m_dead:
        p, d = parse_date_range(m_dead.group(2))
        posted = posted or p
        deadline = deadline or d

    # generic range fallback
    if not posted and not deadline:
        p, d = parse_date_range(text)
        posted = posted or p
        deadline = deadline or d

    return posted, deadline


def extract_description(soup: BeautifulSoup) -> str:
    selectors = [
        ".bo_v_con", ".view_cont", ".board-view-content", ".content", "#content",
        ".bbs_view", ".article-body", ".board_view"
    ]
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            txt = clean_text(node.get_text(" ", strip=True))
            if len(txt) >= 12:
                return summarize(txt)
    body = clean_text(soup.get_text(" ", strip=True))
    return summarize(body)


def fetch_detail(session: requests.Session, title: str, url: str) -> Job:
    r = session.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    body_text = clean_text(soup.get_text(" ", strip=True))

    real_title = find_title(soup, title)
    posted_at, deadline = extract_posted_deadline(body_text)
    description = extract_description(soup)

    return Job(
        id=f"uiwang-{abs(hash((real_title, url)))}",
        title=real_title,
        organization="의왕시청",
        category="public",
        track="public",
        region="의왕",
        employmentType="공공/기관",
        postedAt=posted_at,
        deadline=deadline,
        source="의왕시청",
        sourceType="municipal",
        url=url,
        description=description or real_title,
    )


def main() -> None:
    session = session_with_retries()
    errors: list[str] = []
    collected: list[Job] = []
    found_links: list[tuple[str, str]] = []

    for list_url in LIST_URLS:
        try:
            r = session.get(list_url, timeout=20)
            r.raise_for_status()
            found_links.extend(extract_links_from_list(list_url, r.text))
        except Exception as e:
            errors.append(f"{list_url}: {e}")

    # de-dup links
    dedup_links = []
    seen = set()
    for t, u in found_links:
        key = (t, u)
        if key in seen:
            continue
        seen.add(key)
        dedup_links.append((t, u))

    # If we still only found generic page links, do not emit them as jobs.
    dedup_links = [(t, u) for t, u in dedup_links if looks_like_job_title(t)]

    for title, url in dedup_links[:15]:
        try:
            job = fetch_detail(session, title, url)
            # final guard against generic/non-job pages
            if not looks_like_job_title(job.title):
                continue
            collected.append(job)
        except Exception as e:
            errors.append(f"{url}: {e}")

    # de-dup jobs by title/url
    final_jobs = []
    seen_ids = set()
    for job in collected:
        key = (job.title, job.url)
        if key in seen_ids:
            continue
        seen_ids.add(key)
        final_jobs.append(job)

    payload = {
        "meta": {
            "generatedAt": datetime.now().isoformat(),
            "source": "uiwang",
            "count": len(final_jobs),
            "listUrls": LIST_URLS,
            "errors": errors,
        },
        "jobs": [asdict(j) for j in final_jobs],
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] uiwang_jobs.json saved ({len(final_jobs)} jobs)")
    if errors:
        print("[WARN] partial errors detected:")
        for e in errors[:20]:
            print(f" - {e}")


if __name__ == "__main__":
    main()
