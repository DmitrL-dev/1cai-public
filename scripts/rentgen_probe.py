"""One-shot schema probe for the Rentgen data join. Read-only."""
import json, itertools, os, collections

base = r"C:\1cAI"
cg = os.path.join(base, "data", "rentgen_callgraph.ndjson")
scores_p = os.path.join(base, "gabriel_runs", "scores.json")
feats_p = os.path.join(base, "gabriel_runs", "features.ndjson")
dom_p = os.path.join(base, "gabriel_runs", "domains.csv")

print("=== CALLGRAPH: 3 records ===")
modseg = collections.Counter()
cg_modules = set()
n = 0
with open(cg, encoding="utf-8") as f:
    for line in f:
        n += 1
        r = json.loads(line)
        cg_modules.add(r["module"])
        modseg[r["module"].count(".") + 1] += 1
        if n <= 3:
            print(json.dumps(r, ensure_ascii=False)[:500])
print(f"  total callgraph records: {n}")
print(f"  unique modules in callgraph: {len(cg_modules)}")
print(f"  module segment-count distribution: {dict(modseg)}")
print("  20 sample callgraph module names:")
for m in itertools.islice(sorted(cg_modules), 0, 20):
    print("   ", m)

print("\n=== SCORES.JSON ===")
with open(scores_p, encoding="utf-8") as f:
    s = json.load(f)
print("  top keys:", list(s.keys()))
print("  summary:", json.dumps(s.get("summary", {}), ensure_ascii=False)[:600])
mods = s.get("modules") or s.get("scores") or []
print("  module count:", len(mods))
if mods:
    print("  ALL fields of module[0]:", json.dumps(mods[0], ensure_ascii=False))
    print("  20 sample module_path values:")
    key = "module_path" if "module_path" in mods[0] else list(mods[0].keys())[0]
    for m in itertools.islice(mods, 0, 20):
        print("   ", m.get(key))

print("\n=== FEATURES.NDJSON: first record keys ===")
with open(feats_p, encoding="utf-8") as f:
    fr = json.loads(f.readline())
print("  keys:", list(fr.keys()))
print("  module-ish fields:", {k: v for k, v in fr.items() if "mod" in k.lower() or "path" in k.lower() or "name" in k.lower()})

print("\n=== DOMAINS.CSV: header + 3 rows ===")
with open(dom_p, encoding="utf-8") as f:
    for line in itertools.islice(f, 0, 4):
        print("  ", line.rstrip()[:240])

# Try to see if a scores module_path suffix matches a callgraph module name
print("\n=== JOIN PROBE ===")
cg_by_meta = collections.defaultdict(list)
for m in cg_modules:
    cg_by_meta[m.split(".")[0]].append(m)
sample_paths = [m.get("module_path") for m in mods[:8]] if mods and "module_path" in mods[0] else []
for p in sample_paths:
    print(f"  score path: {p}")
