"""
GABRIEL Phase 0 — BSL code quality rating via direct OpenAI Chat Completions API.

GABRIEL library uses OpenAI Responses API (client.responses.create) which is
incompatible with our local proxy (127.0.0.1:8045). This script replicates
GABRIEL's rate() functionality using chat.completions.create instead.

Same prompt template, same attributes, same sampling logic.
"""

import asyncio
import glob
import json
import os
import random
import time
import pandas as pd
from openai import AsyncOpenAI

# === CONFIG ===
ERP_ROOT = r"C:\1cAI\data\configs\unpacked"
SAVE_DIR = r"C:\1cAI\gabriel_runs\phase0"
SAMPLE_SIZE = 100
MIN_SIZE = 500
MAX_SIZE = 50_000
MODEL = "claude-haiku-4"  # gpt-4o-mini truncates via proxy; haiku works perfectly
MAX_CONCURRENT = 5
MAX_RETRIES = 3
RETRY_DELAY = 3.0

ATTRIBUTES = {
    "code_quality": (
        "Общее качество кода: читаемость, структурированность, "
        "отсутствие дублирования, разделение ответственности. "
        "0 = ужасный код, 100 = образцовый"
    ),
    "documentation": (
        "Степень документирования: наличие комментариев к процедурам/функциям, "
        "описание параметров и возвращаемых значений, пояснения к сложной логике. "
        "0 = нет комментариев, 100 = полностью задокументирован"
    ),
    "complexity": (
        "Цикломатическая сложность: количество ветвлений (Если/Иначе), "
        "вложенных циклов, обработок исключений. "
        "0 = очень простой линейный код, 100 = чрезвычайно запутанный"
    ),
    "maintainability": (
        "Простота сопровождения: насколько легко понять и модифицировать этот код "
        "новому разработчику. Учитывать: именование переменных, длину процедур, "
        "связанность с другими модулями. "
        "0 = невозможно поддерживать, 100 = легко поддерживать"
    ),
}

# GABRIEL-style prompt template
SYSTEM_PROMPT = """You are a code quality analysis expert specializing in 1C:Enterprise BSL language.
You will be given source code and must rate it on specific attributes.
Output ONLY valid JSON with integer ratings 0-100. No markdown, no explanation."""

RATING_PROMPT_TEMPLATE = """Rate this 1C BSL source code on these attributes:

{attributes_json}

Use integers 0-100 (inclusive). low = absent; high = extreme; mid = moderate.
Use the full range. Extremes are rare: near 0 only if truly absent, near 100 only if overwhelming.
Use moderate intermediates (e.g. 19, 67, 32) to account for nuance.
Judge each attribute independently.

Source code:
```bsl
{code}
```

Output JSON only:
{{"code_quality": <int>, "documentation": <int>, "complexity": <int>, "maintainability": <int>}}"""

PRIORITY_DIRS = [
    ("CommonModules", 25),
    ("Documents", 20),
    ("Catalogs", 15),
    ("InformationRegisters", 10),
    ("DataProcessors", 10),
    ("Reports", 5),
    ("AccumulationRegisters", 5),
    ("BusinessProcesses", 3),
    ("ExchangePlans", 2),
    ("Constants", 2),
    ("ChartsOfAccounts", 1),
    ("WebServices", 1),
    ("HTTPServices", 1),
]


def collect_candidates():
    all_files = glob.glob(os.path.join(ERP_ROOT, "**", "*.bsl"), recursive=True)
    candidates = []
    for filepath in all_files:
        size = os.path.getsize(filepath)
        if size < MIN_SIZE or size > MAX_SIZE:
            continue
        rel = os.path.relpath(filepath, ERP_ROOT)
        parts = rel.split(os.sep)
        candidates.append(
            {
                "filepath": filepath,
                "top_dir": parts[0],
                "object_name": parts[1] if len(parts) > 1 else "unknown",
                "module_type": os.path.basename(filepath).replace(".bsl", ""),
                "size_bytes": size,
            }
        )
    return candidates


def stratified_sample(candidates, size=SAMPLE_SIZE):
    by_dir = {}
    for c in candidates:
        by_dir.setdefault(c["top_dir"], []).append(c)
    sampled = []
    total_weight = sum(w for _, w in PRIORITY_DIRS)
    for dir_name, weight in PRIORITY_DIRS:
        pool = by_dir.get(dir_name, [])
        if not pool:
            continue
        n = min(max(1, round(size * weight / total_weight)), len(pool))
        sampled.extend(random.sample(pool, n))
    remaining = size - len(sampled)
    if remaining > 0:
        used = {s["filepath"] for s in sampled}
        leftover = [c for c in candidates if c["filepath"] not in used]
        if leftover:
            sampled.extend(random.sample(leftover, min(remaining, len(leftover))))
    return sampled[:size]


def read_bsl_file(filepath):
    for encoding in ["utf-8-sig", "utf-8", "cp1251"]:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def build_dataframe(sampled):
    rows = []
    for item in sampled:
        code = read_bsl_file(item["filepath"])
        if code is None or len(code.strip()) < 10:
            continue
        truncated = code[:4000] if len(code) > 4000 else code
        rows.append(
            {
                "id": f"{item['top_dir']}/{item['object_name']}/{item['module_type']}",
                "source_code": truncated,
                "full_size_bytes": item["size_bytes"],
                "line_count": code.count("\n") + 1,
                "top_dir": item["top_dir"],
                "module_type": item["module_type"],
                "object_name": item["object_name"],
                "filepath": item["filepath"],
            }
        )
    return pd.DataFrame(rows)


async def rate_single(client, semaphore, code, idx, total):
    prompt = RATING_PROMPT_TEMPLATE.format(
        attributes_json=json.dumps(ATTRIBUTES, ensure_ascii=False, indent=2),
        code=code,
    )
    for attempt in range(MAX_RETRIES):
        async with semaphore:
            try:
                resp = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                    stream=False,
                )
                content = resp.choices[0].message.content.strip()
                # Strip markdown code fences if present
                if content.startswith("```"):
                    content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                ratings = json.loads(content)
                print(f"  [{idx + 1}/{total}] OK: {ratings}")
                return ratings
            except json.JSONDecodeError as e:
                print(
                    f"  [{idx + 1}/{total}] JSON parse error (attempt {attempt + 1}): {content[:100]}"
                )
                await asyncio.sleep(RETRY_DELAY)
            except Exception as e:
                msg = str(e)[:100]
                print(f"  [{idx + 1}/{total}] API error (attempt {attempt + 1}): {msg}")
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
    print(f"  [{idx + 1}/{total}] FAILED after {MAX_RETRIES} retries")
    return None


async def rate_all(df):
    client = AsyncOpenAI()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    total = len(df)

    print(f"\nRating {total} BSL modules with {MODEL}")
    print(f"Concurrency: {MAX_CONCURRENT}, Retries: {MAX_RETRIES}")
    print(f"Attributes: {list(ATTRIBUTES.keys())}\n")

    tasks = [
        rate_single(client, semaphore, row["source_code"], i, total)
        for i, (_, row) in enumerate(df.iterrows())
    ]
    results = await asyncio.gather(*tasks)

    # Attach results to dataframe
    attr_names = list(ATTRIBUTES.keys())
    for attr in attr_names:
        df[attr] = [r.get(attr) if r else None for r in results]

    succeeded = sum(1 for r in results if r is not None)
    print(f"\nCompleted: {succeeded}/{total} successful")
    return df


def print_summary(df):
    attrs = ["code_quality", "documentation", "complexity", "maintainability"]
    valid = df.dropna(subset=attrs, how="all")

    print(f"\n{'=' * 60}")
    print(f"RESULTS SUMMARY ({len(valid)} modules rated)")
    print(f"{'=' * 60}")

    for attr in attrs:
        col = valid[attr].dropna()
        if len(col) == 0:
            continue
        print(f"\n--- {attr} ---")
        print(f"  Mean:   {col.mean():.1f}")
        print(f"  Median: {col.median():.1f}")
        print(f"  Std:    {col.std():.1f}")
        print(f"  Min:    {col.min():.0f}")
        print(f"  Max:    {col.max():.0f}")

    if "code_quality" in valid.columns and valid["code_quality"].notna().any():
        print(f"\n--- Average code_quality by metadata type ---")
        by_type = (
            valid.groupby("top_dir")["code_quality"].mean().sort_values(ascending=False)
        )
        for dir_name, score in by_type.items():
            n = len(valid[valid["top_dir"] == dir_name])
            print(f"  {dir_name}: {score:.1f} (n={n})")

        print(f"\n--- Top 5 highest quality ---")
        for _, row in valid.nlargest(5, "code_quality").iterrows():
            print(
                f"  {row['id']}: quality={row['code_quality']:.0f}, docs={row['documentation']:.0f}, "
                f"complexity={row['complexity']:.0f}, maintain={row['maintainability']:.0f}"
            )

        print(f"\n--- Top 5 lowest quality ---")
        for _, row in valid.nsmallest(5, "code_quality").iterrows():
            print(
                f"  {row['id']}: quality={row['code_quality']:.0f}, docs={row['documentation']:.0f}, "
                f"complexity={row['complexity']:.0f}, maintain={row['maintainability']:.0f}"
            )

    # Correlations
    print(f"\n--- Correlations ---")
    for a in attrs:
        for b in attrs:
            if a < b:
                corr = valid[[a, b]].dropna().corr().iloc[0, 1]
                print(f"  {a} vs {b}: {corr:.2f}")


async def main():
    random.seed(42)
    os.makedirs(SAVE_DIR, exist_ok=True)

    print("Step 1: Collecting BSL file candidates...")
    candidates = collect_candidates()
    print(f"  Found {len(candidates)} files")

    print("Step 2: Stratified sampling...")
    sampled = stratified_sample(candidates)
    print(f"  Selected {len(sampled)} modules")
    from collections import Counter

    for k, v in Counter(s["top_dir"] for s in sampled).most_common():
        print(f"    {k}: {v}")

    print("Step 3: Building DataFrame...")
    df = build_dataframe(sampled)
    print(
        f"  {len(df)} rows, avg code length: {df['source_code'].str.len().mean():.0f} chars"
    )

    print("Step 4: Rating via Chat Completions API...")
    start = time.time()
    df = await rate_all(df)
    elapsed = time.time() - start
    print(f"  Elapsed: {elapsed:.1f}s")

    print("Step 5: Saving results...")
    output_path = os.path.join(SAVE_DIR, "phase0_results.csv")
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  Saved to: {output_path}")

    # Also save raw responses as JSON for audit
    json_path = os.path.join(SAVE_DIR, "phase0_results.json")
    records = df[
        [
            "id",
            "top_dir",
            "module_type",
            "code_quality",
            "documentation",
            "complexity",
            "maintainability",
            "line_count",
            "full_size_bytes",
        ]
    ].to_dict("records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  JSON audit: {json_path}")

    print_summary(df)


if __name__ == "__main__":
    asyncio.run(main())
