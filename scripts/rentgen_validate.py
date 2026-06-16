"""Exercise every RentgenStore method against the real DB; dump UTF-8 JSON."""
import json, sys, time
sys.path.insert(0, r"C:\1cAI\tools")
from rentgen.store import get_store

s = get_store()
out = {}
t0 = time.perf_counter()

out["meta"] = s.db_meta()
out["stats"] = s.get_stats()
out["summary"] = s.summary()
out["worst_3"] = s.worst(3)
out["hotspots_8"] = s.hotspots(8)
out["dead_code_5"] = s.dead_code(5)

# pick the most-called subroutine name for an impact demo
import sqlite3
con = sqlite3.connect(f"file:{s.db_path}?mode=ro", uri=True)
top_callee = con.execute(
    "SELECT ds.name nm, COUNT(*) c FROM call_edge e "
    "JOIN subroutine ds ON ds.id=e.callee_id GROUP BY e.callee_id "
    "ORDER BY c DESC LIMIT 1"
).fetchone()
con.close()
impact_name = top_callee[0]
out["impact_target"] = {"name": impact_name, "incoming_calls": top_callee[1]}
imp = s.get_impact_analysis(impact_name, max_depth=4)
out["impact_sample"] = {"total_edges": len(imp), "first_6": imp[:6]}

# execution flow from the most complex subroutine
flow_entry = out["stats"]["top_complex"][0]["name"]
fl = s.get_execution_flow(flow_entry, max_depth=6)
out["flow_entry"] = flow_entry
out["flow_sample"] = {"total_edges": len(fl), "first_6": fl[:6]}

# module neighbors for the top fan-in module
top_mod = out["stats"]["top_fan_in"][0]["name"]
out["neighbors_of_top_fanin"] = s.module_neighbors(top_mod, limit=8)

out["_elapsed_sec"] = round(time.perf_counter() - t0, 2)

with open(r"C:\1cAI\scripts\_rentgen_validate_out.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("OK wrote _rentgen_validate_out.json in", out["_elapsed_sec"], "s")
