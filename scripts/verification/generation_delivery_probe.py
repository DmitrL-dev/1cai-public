"""Installed CLI oracle over owned synthetic generations; no product imports."""
from contextlib import closing
import hashlib
import json
import sqlite3
from uuid import UUID, uuid4


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def state_image(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        return digest("\n".join(connection.iterdump()).encode())


def catalog_entry(state, snapshot):
    with closing(sqlite3.connect(state.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute(
            "SELECT manifest_hash,source_digest,graph_hash,generation_relpath,manifest_version,published_at "
            "FROM snapshots WHERE project_id=? AND snapshot_id=?",
            (snapshot["project_id"], snapshot["snapshot_id"])).fetchone()
    require(row is not None and row[0] == snapshot["manifest_hash"], "Independent catalog binding differs")
    locator = row[3]
    require(locator.startswith("generations/") and str(UUID(locator[12:])) == locator[12:],
            "Expected an owned UUID generation")
    return dict(snapshot=snapshot, source_digest=row[1], graph_hash=row[2],
                generation_relpath=locator, manifest_version=row[4], published_at=row[5])


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "Owned generation contains an alias")
        result[path.relative_to(root).as_posix()] = digest(path.read_bytes()) if path.is_file() else "directory"
    return result


def validate_verification(result, catalog, document):
    require(result["catalog"] == catalog and result["physical_state"] == "verified_at_read"
            and result["removal_permitted"] is False, "Generation verification binding or safety claim differs")
    summary = result["validation"]
    expected = dict(catalog["snapshot"], source_digest=catalog["source_digest"], graph_hash=catalog["graph_hash"],
                    verified_source_files=len(document["source"]["entries"]),
                    verified_derived_files=len(document["derived_inputs"]))
    require(all(summary.get(key) == value for key, value in expected.items())
            and type(summary.get("verified_total_bytes")) is int and summary["verified_total_bytes"] > 0,
            "Generation validation summary differs from independently read manifest/catalog")


def verify(command, state_root, source_root, first, second):
    """command runs a fresh installed CLI process, already scoped to this project."""
    require(not source_root.exists(), "Live source must be absent during generation diagnostics")
    require(first["snapshot"] != second["snapshot"], "Expected historical and current generations")
    state = state_root / "state.sqlite3"
    before = state_image(state)
    head = second["head"]
    records, original, checks = {}, {}, []

    def call(name, locator, *, error=None):
        options = dict(expected=2, error_code=error) if error else {}
        result = command(name, "--generation-relpath", locator, **options)
        checks.append(dict(command=name, generation_relpath=locator, exit=2 if error else 0, error_code=error))
        return result

    def attributed(catalog, publication):
        value = call("generation-attribution", catalog["generation_relpath"])
        require(value == dict(generation_relpath=catalog["generation_relpath"], status="catalog_referenced",
            observed_head=head, catalog=catalog, latest_publication=publication,
            physical_state="not_inspected", removal_permitted=False), "Generation attribution differs from durable state")
        return value

    for label, publication in (("first", first), ("second", second)):
        catalog = catalog_entry(state, publication["snapshot"])
        root = state_root / catalog["generation_relpath"]
        original[label] = inventory(root)
        document = json.loads((root / "manifest.json").read_bytes())
        require(digest((root / "manifest.json").read_bytes()) == catalog["snapshot"]["manifest_hash"],
                "Independent manifest hash differs")
        attribution = attributed(catalog, publication)
        result = call("generation-verify", catalog["generation_relpath"])
        validate_verification(result, catalog, document)
        records[label] = dict(catalog=catalog, verification=result, attribution=attribution)

    unknown = []
    for present in (False, True):
        locator = "generations/" + str(uuid4())
        root = state_root / locator
        if present:
            root.mkdir(mode=0o700)
            (root / "unregistered-marker").write_bytes(b"owned unregistered attempt\n")
        contents = inventory(root)
        value = call("generation-attribution", locator)
        require(value == dict(generation_relpath=locator, status="unreferenced_at_read", observed_head=head,
            catalog=None, latest_publication=None, physical_state="not_inspected", removal_permitted=False),
            "Unregistered locator attribution differs")
        call("generation-verify", locator, error="GENERATION_UNREFERENCED")
        require(root.exists() == present and inventory(root) == contents, "Unregistered attempt was changed")
        unknown.append(dict(generation_relpath=locator, directory_present=present, contents_unchanged=True))

    catalog = records["first"]["catalog"]
    root = state_root / catalog["generation_relpath"]
    document = json.loads((root / "manifest.json").read_bytes())
    entry = document["source"]["entries"][0]
    names = dict(source="sources/" + entry["layer_id"] + "/" + entry["relative_path"],
                 derived=document["derived_inputs"][0]["relative_path"], graph="graph.sqlite3",
                 manifest="manifest.json", extra="unlisted-file", sidecar="graph.sqlite3-wal", missing="manifest.json")
    for damage, name in names.items():
        path = root / name
        require(path.resolve().is_relative_to(root.resolve()), "Damage target escapes owned generation")
        raw = path.read_bytes() if path.exists() else None
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
        try:
            if damage == "missing":
                path.unlink()
            else:
                # Existing files keep their length so a size-only check cannot pass.
                require(raw is None or len(raw) > 0, "Expected nonempty captured input")
                path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:] if raw is not None else b"owned corrupt fixture\n")
                path.chmod(mode)
            # Attribution is state-only even when the physical generation is broken.
            attributed(catalog, first)
            call("generation-verify", catalog["generation_relpath"], error="SNAPSHOT_CORRUPT")
        finally:
            if raw is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(raw)
                path.chmod(mode)
        validate_verification(call("generation-verify", catalog["generation_relpath"]), catalog, document)

    require(command("project-head") == head, "Diagnostics changed project head")
    for publication in (first, second):
        require(command("publication-receipt", "--operation-id", publication["operation_id"]) == publication,
                "Diagnostics changed publication receipt")
    require(state_image(state) == before, "Diagnostics changed logical SQLite state")
    for label, record in records.items():
        require(inventory(state_root / record["catalog"]["generation_relpath"]) == original[label],
                "Diagnostics changed retained generation inventory/bytes")
    return dict(schema=1, scope="installed CLI owned two-generation fixture; no cleanup or full product qualification",
        **records, checks=checks, unreferenced=unknown, damage_cases=list(names), state_sha256=before,
        outcomes=dict(historical_verified=True, current_verified=True, unreferenced_refused=True,
            damaged_refused=True, state_unchanged=True, retained_bytes_restored=True, live_source_absent=True))
