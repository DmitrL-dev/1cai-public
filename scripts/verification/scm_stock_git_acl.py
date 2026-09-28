"""Fixed two-directory writable policy for the owned stock SCM fixture."""


def _layout(worker, root, rows):
    worker.require(root in (worker.ROOT, worker.RUNTIME), 'Stock ACL root is outside owned fixture/runtime')
    if root == worker.RUNTIME:
        return None, None
    data = root / 'localservice/data'
    scratch = root / 'localservice/diagnostics/Rentgen/diagnostic-runs'
    worker.require(root in rows and data in rows and scratch in rows
        and data.is_dir() and scratch.is_dir(), 'Fixed stock writable roots missing from inventory')
    return data, scratch


def temporary_policy(worker, root, baseline):
    data, scratch = _layout(worker, root, baseline)
    policy = worker.temporary_acl_policy(root, baseline, data)
    if scratch is not None:
        scratch_rows = {path: row for path, row in baseline.items() if path.is_relative_to(scratch)}
        policy.update(worker.temporary_acl_policy(scratch, scratch_rows, scratch))
    return policy


def verify_policy(worker, root, rows):
    data, scratch = _layout(worker, root, rows)
    if scratch is None:
        return worker.verify_temporary_acls(root, rows, None)
    scratch_rows = {path: row for path, row in rows.items() if path.is_relative_to(scratch)}
    ordinary_rows = {path: row for path, row in rows.items() if not path.is_relative_to(scratch)}
    ordinary = worker.verify_temporary_acls(root, ordinary_rows, data)
    diagnostic = worker.verify_temporary_acls(scratch, scratch_rows, scratch)
    return {'entries': len(rows), 'protected': ordinary['protected'] and diagnostic['protected'],
        'only_administrators_system_localservice': True,
        'service_modify_only_data_and_scratch': True,
        'ordinary_entries': ordinary['entries'], 'scratch_entries': diagnostic['entries']}
