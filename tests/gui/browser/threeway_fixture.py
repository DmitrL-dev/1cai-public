"""Owned three-ZIP byte matrix for genuine browser/HTTP/Rust acceptance.

Expected actions are explicit fixture facts, not produced by the implementation
under test. The archives have no common-history claim and are never extracted.
"""
import hashlib
import zipfile


SIDES = ("base", "current", "upstream")
ACTIONS = ("unchanged", "same_change", "keep_current", "take_upstream", "conflict")


def build_threeway_archives(root):
    owner = (b'<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
             b'<Catalog uuid="11111111-1111-4111-8111-111111111111">'
             b'<Properties><Name>ThreeVersions</Name></Properties>'
             b'<ChildObjects/></Catalog></MetaDataObject>')
    cases = [
        ("Catalogs/ThreeVersions.xml", "unchanged", owner, owner, owner),
        ("Cases/Unchanged.bsl", "unchanged", b"same", b"same", b"same"),
        ("Cases/SameChanged.bsl", "same_change", b"old", b"new", b"new"),
        ("Cases/SameAdded.bsl", "same_change", None, b"new", b"new"),
        ("Cases/DeletedBoth.bsl", "same_change", b"old", None, None),
        ("Cases/ModifiedCurrent.bsl", "keep_current", b"old", b"current", b"old"),
        ("Cases/AddedCurrent.bsl", "keep_current", None, b"current", None),
        ("Cases/DeletedCurrent.bsl", "keep_current", b"old", None, b"old"),
        ("Cases/ModifiedUpstream.bsl", "take_upstream", b"old", b"old", b"upstream"),
        ("Cases/AddedUpstream.bsl", "take_upstream", None, None, b"upstream"),
        ("Cases/DeletedUpstream.bsl", "take_upstream", b"old", b"old", None),
        ("Cases/DifferentChanges.bsl", "conflict", b"old", b"current", b"upstream"),
        ("Cases/DifferentAdditions.bsl", "conflict", None, b"current", b"upstream"),
        ("Cases/DeleteCurrentModifyUpstream.bsl", "conflict", b"old", None, b"upstream"),
        ("Cases/ModifyCurrentDeleteUpstream.bsl", "conflict", b"old", b"current", None),
    ]
    # Literal angle brackets are rejected by portable path validation. Entities,
    # quotes that are legal in a path, Cyrillic, and an emoji remain untrusted.
    untrusted_path = ("Cases/Кириллица😀 '&lt;img src=x "
                      "onerror=globalThis.ownedThreewayInjected=true&gt;' "
                      + "LongOwnedSegment" * 12 + ".bsl")
    cases.append((untrusted_path, "conflict", b"base", b"current", b"upstream"))
    for index in range(401):
        cases.append((f"Paged/Current{index:03d}.bsl", "keep_current",
                      f"// base {index:03d}\n".encode(),
                      f"// current {index:03d}\n".encode(),
                      f"// base {index:03d}\n".encode()))
    cases.sort(key=lambda case: case[0].encode("utf-8"))
    archives, entries, sizes = {}, {}, {}
    for side_index, side in enumerate(SIDES, start=2):
        archive = root / f"threeway-{side}.zip"
        present = [(case[0], case[side_index]) for case in cases if case[side_index] is not None]
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for path, data in present:
                info = zipfile.ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                output.writestr(info, data)
        archives[side] = {"path": str(archive), "filename": archive.name,
                          "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
        entries[side] = len(present)
        sizes[side] = sum(len(data) for _, data in present)
    rows = []
    counts = dict.fromkeys(ACTIONS, 0)
    for path, action, *values in cases:
        counts[action] += 1
        rows.append({"path": path, "action": action, **{
            side: None if data is None else {
                "raw_sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
            for side, data in zip(SIDES, values)}})
    counts.update(total=len(cases), files=len(cases), changes=len(cases) - counts["unchanged"])
    coverage = {"scope": "exact_path_inventory", "comparison": "raw_sha256_and_size",
                "complete": True, "entry_records": sum(entries.values()),
                "decoded_bytes": sum(sizes.values()), "union_paths": len(cases),
                "side_entries": entries, "side_decoded_bytes": sizes}
    return {"archives": archives, "rows": rows, "counts": counts,
            "coverage": coverage, "untrusted_path": untrusted_path,
            "current_modules": entries["current"] - 1}
