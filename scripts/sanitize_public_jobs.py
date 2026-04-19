from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PUBLIC_FILE = DATA_DIR / "public_jobs.json"

def main() -> None:
    if not PUBLIC_FILE.exists():
        print("[WARN] public_jobs.json not found")
        return

    payload = json.loads(PUBLIC_FILE.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", [])
    cleaned = []
    seen = set()

    for job in jobs:
        job["category"] = "public"
        job["track"] = "public"
        job["employmentType"] = job.get("employmentType") or "공공/기관"
        job["status"] = job.get("status") or "unknown"
        job["title"] = str(job.get("title", "")).strip()
        job["organization"] = str(job.get("organization", "")).strip()
        job["region"] = str(job.get("region", "")).strip()
        job["description"] = str(job.get("description", "")).strip()[:140]
        key = (job["title"], job["organization"], job["region"], job.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(job)

    payload["jobs"] = cleaned
    meta = payload.setdefault("meta", {})
    meta["count"] = len(cleaned)
    notes = meta.get("notes", [])
    if not isinstance(notes, list):
        notes = [str(notes)]
    notes.append("phase-fix: normalized public jobs for dashboard build")
    meta["notes"] = notes[-5:]

    PUBLIC_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] public_jobs.json sanitized ({len(cleaned)} jobs)")

if __name__ == "__main__":
    main()
