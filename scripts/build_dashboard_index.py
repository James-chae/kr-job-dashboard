from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_FILE = ROOT / "dashboard_index.json"

INPUTS = [
    ("public_jobs.json", "public"),
    ("uiwang_jobs.json", "public"),
    ("anyang_jobs.json", "short"),
    ("clinical_jobs.json", "clinical"),
    ("cabin_jobs.json", "cabin"),
]

def load_json(path: Path):
    if not path.exists():
        return {"meta": {"source": path.name, "count": 0, "errors": [f"{path.name} missing"]}, "jobs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"meta": {"source": path.name, "count": 0, "errors": [str(e)]}, "jobs": []}

def clean_job(job: dict, default_track: str) -> dict:
    out = dict(job)
    out["track"] = out.get("track") or default_track
    out["category"] = out.get("category") or default_track
    out["title"] = str(out.get("title", "")).strip()
    out["organization"] = str(out.get("organization", "")).strip()
    out["region"] = str(out.get("region", "")).strip()
    out["employmentType"] = str(out.get("employmentType", "")).strip()
    out["description"] = str(out.get("description", "")).strip()
    out["status"] = str(out.get("status", "unknown")).strip() or "unknown"
    return out

def should_keep(job: dict) -> bool:
    if not job.get("title"):
        return False
    if job.get("track") == "short":
        org = job.get("organization", "")
        title = job.get("title", "")
        desc = job.get("description", "")
        noisy = ["스크랩", "믿고보는", "탄탄한 중견기업"]
        if any(x in org for x in noisy):
            return False
        if title == org:
            return False
        if desc.startswith("스크랩 "):
            return False
    return True

def sort_key(job: dict):
    return (
        str(job.get("postedAt", "")),
        str(job.get("deadline", "")),
        str(job.get("title", "")),
    )

def main() -> None:
    jobs = []
    source_stats = {}
    seen = set()

    for filename, default_track in INPUTS:
        payload = load_json(DATA_DIR / filename)
        rows = payload.get("jobs", []) or []
        cleaned = []
        for row in rows:
            item = clean_job(row, default_track)
            if not should_keep(item):
                continue
            key = (item.get("title", ""), item.get("organization", ""), item.get("region", ""), item.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(item)
            jobs.append(item)

        meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
        source_stats[filename] = {
            "rawCount": len(rows),
            "keptCount": len(cleaned),
            "generatedAt": meta.get("generatedAt", ""),
            "source": meta.get("source", filename),
            "errors": meta.get("errors", []),
        }

    jobs = sorted(jobs, key=sort_key, reverse=True)

    by_region = {}
    by_track = {}
    for job in jobs:
        by_region[job.get("region", "기타")] = by_region.get(job.get("region", "기타"), 0) + 1
        by_track[job.get("track", "other")] = by_track.get(job.get("track", "other"), 0) + 1

    payload = {
        "meta": {
            "generatedAt": datetime.now().isoformat(),
            "version": 99,
            "jobCount": len(jobs),
            "byRegion": by_region,
            "byTrack": by_track,
            "sourceStats": source_stats,
        },
        "jobs": jobs,
    }

    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] dashboard_index.json saved ({len(jobs)} jobs)")
    print(f"[INFO] byRegion={by_region}")
    print(f"[INFO] byTrack={by_track}")

if __name__ == "__main__":
    main()
