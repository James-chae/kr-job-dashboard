import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CABIN_PATH = DATA_DIR / "cabin_jobs.json"

BROKEN_PATTERNS = [
    r"Please enable JavaScript",
    r"a:link",
    r"a:visited",
    r"cursor:",
    r"Recruitment project",
    r"jobcc-cli",
]

MOJIBAKE_RE = re.compile(r"[ÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]{2,}")
HTML_TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")

TITLE_FALLBACKS = {
    "중국동방항공": "중국동방항공 승무원 채용",
    "중국남방항공": "중국남방항공 승무원 채용",
    "Cathay Pacific": "Cathay Pacific 승무원 채용",
}

def clean_text(text: str) -> str:
    text = text or ""
    text = HTML_TAG_RE.sub(" ", text)
    for pat in BROKEN_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.I)
    text = re.sub(r"[\u200b\u2060\ufeff]", " ", text)
    text = SPACE_RE.sub(" ", text).strip()
    return text

def looks_broken(text: str) -> bool:
    if not text:
        return False
    if MOJIBAKE_RE.search(text):
        return True
    lowered = text.lower()
    return any(k.lower() in lowered for k in [
        "please enable javascript", "a:link", "a:visited", "cursor:",
        "jobcc-cli", "recruitment project"
    ])

def fallback_title(org: str, title: str) -> str:
    if org in TITLE_FALLBACKS:
        return TITLE_FALLBACKS[org]
    if title and not looks_broken(title):
        return clean_text(title)
    return f"{org} 채용"

def sanitize_job(job: dict) -> dict:
    job = dict(job)
    org = (job.get("organization") or "").strip()
    title = clean_text(job.get("title", ""))
    desc = clean_text(job.get("description", ""))
    src = clean_text(job.get("source", ""))

    if looks_broken(title) or len(title) < 2:
        title = fallback_title(org, title)

    if looks_broken(desc):
        desc = ""

    # foreign airline cards should be compact
    if org in ("중국동방항공", "중국남방항공", "Cathay Pacific"):
        desc = ""

    job["title"] = title
    job["description"] = desc[:140]
    job["source"] = src or job.get("source", "")
    if not job.get("status"):
        job["status"] = "unknown"
    return job

def main():
    if not CABIN_PATH.exists():
        print(f"[WARN] {CABIN_PATH} not found")
        return

    payload = json.loads(CABIN_PATH.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", [])
    cleaned = [sanitize_job(j) for j in jobs]
    payload["jobs"] = cleaned
    meta = payload.setdefault("meta", {})
    notes = meta.get("notes", [])
    if not isinstance(notes, list):
        notes = [str(notes)]
    notes.append("phase11c: sanitized broken foreign-airline text/mojibake")
    meta["notes"] = notes[-5:]
    CABIN_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] sanitized {len(cleaned)} cabin jobs")

if __name__ == "__main__":
    main()
