"""Complete byte inventories and explicitly bounded textual metadata diffs."""
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import difflib

from ._windows_source_tree import read_retained
from .edt_inventory import exported_inventory
from .edt_profiles import authorized
from .manifests import canonical_bytes, sha256
from .metadata_plans import MD, _identity, require, validate_plan
from .metadata_xml import parse_xml
from .platform_check import _pin_inputs


def _verify_identity(folder, inventory, request, check):
    counts = Counter()
    selected = "Catalogs/" + request["catalog"]["name"] + ".xml"
    found = False
    for row in inventory:
        check()
        if row["path"].lower().endswith(".xml"):
            tree = parse_xml(read_retained(folder / row["path"], 4 * 1024**2))
            for item in tree.iter():
                if item.tag.startswith(MD) and "uuid" in item.attrib:
                    counts[item.attrib["uuid"].lower()] += 1
            if row["path"] == selected:
                _identity(tree, request)
                found = True
    require(
        found
        and all(counts[request[key]["uuid"]] == 1 for key in ("catalog", "attribute")),
        "Export lost or duplicated object identity",
    )


def _diff(left, right, before, after, check):
    old = {row["path"]: row for row in before}
    new = {row["path"]: row for row in after}
    changes, used, complete = [], 0, True
    for path in sorted(old.keys() | new.keys()):
        check()
        a, b = old.get(path), new.get(path)
        if a == b:
            continue
        change = {
            "path": path,
            "before": a,
            "after": b,
            "kind": "added" if a is None else "deleted" if b is None else "modified",
        }
        if (
            max((a or {}).get("size", 0), (b or {}).get("size", 0)) > 256 * 1024
            or used >= 512 * 1024
        ):
            change["text_status"] = "omitted_limit"
            complete = False
        else:
            try:
                first = (
                    read_retained(left / path, 256 * 1024).decode("utf-8") if a else ""
                )
                second = (
                    read_retained(right / path, 256 * 1024).decode("utf-8") if b else ""
                )
                require(
                    max(len(first.splitlines()), len(second.splitlines())) <= 5000,
                    "Text diff line limit exceeded",
                )
                delta = "\n".join(
                    difflib.unified_diff(
                        first.splitlines(),
                        second.splitlines(),
                        fromfile="before/" + path,
                        tofile="after/" + path,
                        lineterm="",
                    )
                )
                size = len(delta.encode("utf-8"))
                if size + used > 512 * 1024:
                    change["text_status"] = "omitted_limit"
                    complete = False
                else:
                    change.update(
                        {
                            "text_status": "included"
                            if delta
                            else "byte_change_without_line_diff",
                            "diff": delta,
                        }
                    )
                    if not delta:
                        complete = False
                    used += size
            except UnicodeError:
                change["text_status"] = "binary_or_non_utf8"
                complete = False
        changes.append(change)
    return {"inventory_complete": True, "text_complete": complete, "changes": changes}


def build_preview(ctx, plan, run):
    with authorized(ctx) as check:
        plan = validate_plan(ctx, plan)
        folders = [run / name for name in ("input", "baseline-xml", "candidate-xml")]
        inventories = [
            exported_inventory(folder, authorize=check) for folder in folders
        ]
        require(
            sha256(canonical_bytes(inventories[0])) == plan["input_digest"],
            "Operation input differs from retained plan",
        )
        with ExitStack() as pins:
            for folder, rows in zip(folders, inventories):
                pins.enter_context(_pin_inputs(folder, rows))
            request = plan["request"]
            _verify_identity(folders[1], inventories[1], request, check)
            renamed = deepcopy(request)
            renamed["attribute"]["name"], renamed["new_name"] = (
                request["new_name"],
                request["attribute"]["name"],
            )
            _verify_identity(folders[2], inventories[2], renamed, check)
            normalization = _diff(
                folders[0], folders[1], inventories[0], inventories[1], check
            )
            edit = _diff(folders[1], folders[2], inventories[1], inventories[2], check)
            for folder, rows in zip(folders, inventories):
                require(
                    exported_inventory(folder, authorize=check) == rows,
                    "Export inventory changed during preview",
                )
        return {
            "schema": 1,
            "plan_id": plan["plan_id"],
            "snapshot": request["snapshot"],
            "layer_id": request["layer_id"],
            "inventories": dict(
                zip(("original", "baseline", "candidate"), inventories)
            ),
            "normalization": normalization,
            "edit": edit,
            "identity": {
                "catalog_uuid": request["catalog"]["uuid"],
                "attribute_uuid": request["attribute"]["uuid"],
                "new_name": request["new_name"],
            },
            "platform_check": "not_run",
            "business_data_test": "not_run",
            "apply": {
                "status": "unavailable",
                "reasons": [
                    "normalization_not_qualified",
                    "apply_undo_not_implemented",
                ],
            },
        }
