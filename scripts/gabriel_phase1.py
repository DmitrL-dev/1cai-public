"""
Gabriel Phase 1 — Classify & Rate ALL BSL modules from ERP config.

Two-pass-in-one pipeline:
  1. Classify each module into a business domain
  2. Rate on 4 attributes (code_quality, documentation, complexity, maintainability)

Both done in a single API call per module.

File-based checkpointing to C:\1cAI\gabriel_runs\phase1\checkpoint.jsonl
Final output: phase1_results.csv (UTF-8 BOM)
"""

import asyncio
import csv
import glob
import json
import os
import re
import sys
import time
from pathlib import Path

from openai import AsyncOpenAI

# ── Config ───────────────────────────────────────────────────────────────────
BASE_DIR = r"C:\1cAI\data\configs\unpacked"
SAVE_DIR = r"C:\1cAI\gabriel_runs\phase1"
CHECKPOINT_PATH = os.path.join(SAVE_DIR, "checkpoint.jsonl")
CSV_PATH = os.path.join(SAVE_DIR, "phase1_results.csv")

MODEL = "claude-haiku-4"
MAX_CONCURRENT = 20
MAX_RETRIES = 3
BACKOFF_BASE = 3  # seconds: 3, 6, 12
TEMPERATURE = 0.1
MAX_TOKENS = 200
CODE_TRUNCATE = 4000

MIN_SIZE = 500
MAX_SIZE = 50_000

VALID_DOMAINS = {
    "Бухгалтерия",
    "Налоги",
    "Склад",
    "Продажи",
    "Закупки",
    "Кадры",
    "Производство",
    "Казначейство",
    "МСФО",
    "Администрирование",
    "Интеграция",
    "Общее",
}

SYSTEM_PROMPT = "You are a 1C:Enterprise BSL code analyst. Output ONLY valid JSON. No markdown fences."

USER_PROMPT_TEMPLATE = """Analyze this 1C BSL code. Output ONLY valid JSON:
{{
  "business_domain": "<one of: Бухгалтерия|Налоги|Склад|Продажи|Закупки|Кадры|Производство|Казначейство|МСФО|Администрирование|Интеграция|Общее>",
  "code_quality": <0-100>,
  "documentation": <0-100>,
  "complexity": <0-100>,
  "maintainability": <0-100>
}}

File: {filepath}

Code:
```
{code}
```"""


# ── Helpers ──────────────────────────────────────────────────────────────────


def collect_candidates() -> list[dict]:
    """Glob all .bsl files, filter by size 500–50000 bytes, extract metadata."""
    pattern = os.path.join(BASE_DIR, "**", "*.bsl")
    all_files = glob.glob(pattern, recursive=True)
    candidates = []
    for fp in all_files:
        try:
            size = os.path.getsize(fp)
        except OSError:
            continue
        if MIN_SIZE <= size <= MAX_SIZE:
            rel = os.path.relpath(fp, BASE_DIR)
            parts = Path(rel).parts
            top_dir = parts[0] if len(parts) > 1 else ""
            # Extract module type and object name from path
            # Typical: TopDir/ObjectName/Ext/Module.bsl
            module_type = ""
            object_name = ""
            if len(parts) >= 2:
                object_name = parts[1] if len(parts) > 2 else parts[0]
            if len(parts) >= 3:
                module_type = parts[-2] if parts[-2] != object_name else ""
            # Build a stable ID from relative path
            file_id = rel.replace("\\", "/")
            candidates.append(
                {
                    "id": file_id,
                    "filepath": fp,
                    "top_dir": top_dir,
                    "module_type": module_type,
                    "object_name": object_name,
                }
            )
    # Sort for deterministic ordering
    candidates.sort(key=lambda c: c["id"])
    return candidates


def read_bsl_file(filepath: str) -> str | None:
    """Read a BSL file trying multiple encodings. Strip BOM."""
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                text = f.read()
            # Strip BOM if still present
            if text and ord(text[0]) == 0xFEFF:
                text = text[1:]
            return text
        except (UnicodeDecodeError, UnicodeError):
            continue
        except OSError:
            return None
    return None


def parse_response(raw: str) -> dict | None:
    """Parse JSON from LLM response, stripping markdown fences if needed."""
    # Strip markdown code fences
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Regex fallback — find first JSON object
    m = re.search(r"\{[^}]+\}", cleaned)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def validate_result(data: dict) -> dict | None:
    """Validate and normalise parsed result."""
    if not isinstance(data, dict):
        return None
    domain = data.get("business_domain", "")
    if domain not in VALID_DOMAINS:
        domain = "Общее"
    try:
        cq = max(0, min(100, int(data.get("code_quality", 50))))
        doc = max(0, min(100, int(data.get("documentation", 50))))
        cx = max(0, min(100, int(data.get("complexity", 50))))
        mt = max(0, min(100, int(data.get("maintainability", 50))))
    except (ValueError, TypeError):
        return None
    return {
        "business_domain": domain,
        "code_quality": cq,
        "documentation": doc,
        "complexity": cx,
        "maintainability": mt,
    }


def load_checkpoint() -> set[str]:
    """Load already-processed IDs from checkpoint file."""
    done = set()
    if not os.path.exists(CHECKPOINT_PATH):
        return done
    with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if "id" in obj:
                    done.add(obj["id"])
            except json.JSONDecodeError:
                continue
    return done


def append_checkpoint(record: dict):
    """Append a single JSON-line to checkpoint."""
    with open(CHECKPOINT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_all_checkpoint_records() -> list[dict]:
    """Load all checkpoint records for final CSV generation."""
    records = []
    if not os.path.exists(CHECKPOINT_PATH):
        return records
    with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def write_csv(records: list[dict]):
    """Write final CSV with UTF-8 BOM."""
    fields = [
        "id",
        "business_domain",
        "code_quality",
        "documentation",
        "complexity",
        "maintainability",
        "filepath",
        "top_dir",
        "module_type",
        "object_name",
        "line_count",
    ]
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def print_summary(records: list[dict]):
    """Print summary statistics."""
    n = len(records)
    if n == 0:
        print("No records to summarise.")
        return

    avg_cq = sum(r.get("code_quality", 0) for r in records) / n
    avg_doc = sum(r.get("documentation", 0) for r in records) / n
    avg_cx = sum(r.get("complexity", 0) for r in records) / n
    avg_mt = sum(r.get("maintainability", 0) for r in records) / n

    print("\n" + "=" * 70)
    print(f"PHASE 1 SUMMARY  —  {n} modules processed")
    print("=" * 70)
    print(f"  Avg code_quality:    {avg_cq:.1f}")
    print(f"  Avg documentation:   {avg_doc:.1f}")
    print(f"  Avg complexity:      {avg_cx:.1f}")
    print(f"  Avg maintainability: {avg_mt:.1f}")

    # Group by business_domain
    domain_counts: dict[str, list[dict]] = {}
    for r in records:
        d = r.get("business_domain", "Общее")
        domain_counts.setdefault(d, []).append(r)

    print(
        f"\n{'Domain':<22} {'Count':>6}  {'Quality':>7}  {'Doc':>5}  {'Cmplx':>5}  {'Maint':>5}"
    )
    print("-" * 70)
    for domain in sorted(domain_counts.keys()):
        items = domain_counts[domain]
        cnt = len(items)
        dq = sum(r.get("code_quality", 0) for r in items) / cnt
        dd = sum(r.get("documentation", 0) for r in items) / cnt
        dc = sum(r.get("complexity", 0) for r in items) / cnt
        dm = sum(r.get("maintainability", 0) for r in items) / cnt
        print(
            f"  {domain:<20} {cnt:>6}  {dq:>7.1f}  {dd:>5.1f}  {dc:>5.1f}  {dm:>5.1f}"
        )

    # Group by top_dir
    topdir_counts: dict[str, int] = {}
    for r in records:
        td = r.get("top_dir", "?")
        topdir_counts[td] = topdir_counts.get(td, 0) + 1
    print(f"\nTop dirs (top 15):")
    for td, cnt in sorted(topdir_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {td:<40} {cnt:>6}")

    print("=" * 70)


# ── Async engine ─────────────────────────────────────────────────────────────


async def process_one(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    candidate: dict,
    counters: dict,
) -> dict | None:
    """Process a single BSL module: read, call LLM, parse, checkpoint."""
    file_id = candidate["id"]
    filepath = candidate["filepath"]

    code = read_bsl_file(filepath)
    if code is None:
        counters["errors"] += 1
        return None

    line_count = code.count("\n") + 1
    # Truncate
    if len(code) > CODE_TRUNCATE:
        code = code[:CODE_TRUNCATE] + "\n... [truncated]"

    user_msg = USER_PROMPT_TEMPLATE.format(
        filepath=candidate["id"],
        code=code,
    )

    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            async with sem:
                resp = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    stream=False,
                )
            raw = resp.choices[0].message.content or ""
            parsed = parse_response(raw)
            if parsed is None:
                last_err = f"JSON parse failed: {raw[:120]}"
                raise ValueError(last_err)
            validated = validate_result(parsed)
            if validated is None:
                last_err = f"Validation failed: {parsed}"
                raise ValueError(last_err)

            record = {
                "id": file_id,
                "business_domain": validated["business_domain"],
                "code_quality": validated["code_quality"],
                "documentation": validated["documentation"],
                "complexity": validated["complexity"],
                "maintainability": validated["maintainability"],
                "filepath": filepath,
                "top_dir": candidate["top_dir"],
                "module_type": candidate["module_type"],
                "object_name": candidate["object_name"],
                "line_count": line_count,
            }
            append_checkpoint(record)
            counters["done"] += 1

            # Progress every 100
            if counters["done"] % 100 == 0:
                elapsed = time.time() - counters["t0"]
                rate = counters["done"] / elapsed if elapsed > 0 else 0
                eta_s = (counters["total"] - counters["done"]) / rate if rate > 0 else 0
                eta_m = eta_s / 60
                print(
                    f"  [{counters['done']:>6}/{counters['total']}]  "
                    f"{rate:.1f} items/s  "
                    f"ETA {eta_m:.0f}m  "
                    f"errs={counters['errors']}"
                )

            return record

        except Exception as e:
            last_err = str(e)
            if attempt < MAX_RETRIES - 1:
                wait = BACKOFF_BASE * (2**attempt)  # 3, 6, 12
                await asyncio.sleep(wait)

    # All retries exhausted
    counters["errors"] += 1
    if counters["errors"] <= 20 or counters["errors"] % 50 == 0:
        print(f"  FAIL [{file_id}]: {last_err}")
    return None


async def run_pipeline():
    """Main async pipeline."""
    os.makedirs(SAVE_DIR, exist_ok=True)

    print("Gabriel Phase 1 — Classify & Rate ALL BSL modules")
    print("=" * 60)

    # Collect candidates
    print("Collecting candidates...")
    candidates = collect_candidates()
    print(f"  Found {len(candidates)} candidates ({MIN_SIZE}–{MAX_SIZE} bytes)")

    # Load checkpoint
    done_ids = load_checkpoint()
    remaining = [c for c in candidates if c["id"] not in done_ids]
    print(f"  Already processed: {len(done_ids)}")
    print(f"  Remaining: {len(remaining)}")

    if not remaining:
        print("Nothing to do — all candidates already processed.")
        records = load_all_checkpoint_records()
        write_csv(records)
        print(f"CSV written: {CSV_PATH}")
        print_summary(records)
        return

    # Init client
    client = AsyncOpenAI(
        base_url=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8045/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", "sk-dummy"),
    )

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    counters = {
        "done": 0,
        "errors": 0,
        "total": len(remaining),
        "t0": time.time(),
    }

    print(f"\nProcessing {len(remaining)} modules (concurrency={MAX_CONCURRENT})...")
    print(f"  Model: {MODEL}")
    print(f"  Checkpoint: {CHECKPOINT_PATH}")
    print()

    # Process in batches to avoid overwhelming the event loop with 20k tasks
    BATCH_SIZE = 100
    for batch_start in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[batch_start : batch_start + BATCH_SIZE]
        tasks = [
            asyncio.create_task(process_one(client, sem, c, counters)) for c in batch
        ]
        await asyncio.gather(*tasks)

    elapsed = time.time() - counters["t0"]
    print(
        f"\nDone! {counters['done']} processed, {counters['errors']} errors in {elapsed:.1f}s"
    )

    # Write final CSV from all checkpoint records
    records = load_all_checkpoint_records()
    write_csv(records)
    print(f"CSV written: {CSV_PATH} ({len(records)} rows)")

    print_summary(records)


# ── Entry ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(run_pipeline())
