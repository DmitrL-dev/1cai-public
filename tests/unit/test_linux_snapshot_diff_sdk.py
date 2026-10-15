"""Actual Linux source SDK/Go pair acceptance, not installed/offline evidence.

The delivery probe separately repeats the route from exact installed wheels.
These tests never spoof an OS or replace a successful production read.
"""
import asyncio
from contextlib import closing
import importlib.util
from pathlib import Path
import platform
import sqlite3
import sys
from uuid import uuid4

import pytest

from test_linux_capture import scanner
from test_linux_mcp_capture import call,local_project,read_exact,server

ROOT=Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.skipif(sys.platform!="linux" or platform.machine() not in {"x86_64","amd64"},
    reason="Actual Linux/amd64 SDK stdio and owned Go retained-pair acceptance")
spec=importlib.util.spec_from_file_location("source_pair_probe_controls",ROOT/"scripts/verification/owned_linux_sdk_probe.py")
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


def owned_administrator(project):
    from rentgen_core.authorization import OWNER_PERMISSIONS
    from rentgen_core.local_identity import current_local_principal,initialize_local_identity
    from rentgen_core.state import ProjectState
    owner=current_local_principal(identity_profile=project["profile"])
    admin_profile=project["private"]/"administrator/identity.json"
    initialize_local_identity(admin_profile)
    admin=current_local_principal(identity_profile=admin_profile)
    assert owner!=admin
    state=ProjectState(project["state"],project["project_id"])
    with state.transaction(owner,write=True) as tx:
        tx.set_membership(admin,OWNER_PERMISSIONS,operation_id=str(uuid4()),expected_revision=tx.membership_revision())
    def membership(present):
        with state.transaction(admin,write=True) as tx:
            options=dict(operation_id=str(uuid4()),expected_revision=tx.membership_revision())
            if present:tx.set_membership(owner,OWNER_PERMISSIONS,**options)
            else:tx.revoke_membership(owner,**options)
    return owner,state,membership


def test_native_sdk_explicit_pair_history_survives_unrelated_broken_head(local_project,scanner,tmp_path,monkeypatch):
    project=dict(local_project,state=local_project["private"]/"state/state.sqlite3")
    changed=project["images"][probe.CALLEE].replace(b"Return 1",b"Return 2")
    async def scenario():
        async with server(project,scanner,tmp_path/"pair-capture.stderr",monkeypatch) as (session,_):
            names={tool.name for tool in (await session.list_tools()).tools}
            assert "rentgen_snapshot_diff" in names
            assert not any(name.startswith(("rentgen_metadata_","rentgen_draft_","rentgen_proposal_")) for name in names)
            head=await call(session,"rentgen_project_head",dict(project_id=project["project_id"]))
            async def capture(head):
                return await call(session,"rentgen_capture",dict(project_id=project["project_id"],operation_id=str(uuid4()),expected_head=head))
            first=await capture(head);before=first["snapshot"]["snapshot_id"]
            (project["source"]/probe.CALLEE).write_bytes(changed)
            (project["source"]/"Configuration.xml").rename(project["source"]/"Renamed.xml")
            second=await capture(first["head"]);after=second["snapshot"]["snapshot_id"]
            (project["source"]/probe.CALLEE).write_bytes(changed.replace(b"Return 2",b"Return 3"))
            third=await capture(second["head"]);later=third["snapshot"]["snapshot_id"]
            assert len({before,after,later})==3 and third["head"]["revision"]==3
        (probe.generation(project,later)/"manifest.json").write_bytes(b"broken unrelated latest manifest")
        project["source"].rename(project["source"].with_name("live-inputs-absent"))
        principal,state,membership=owned_administrator(project)
        state_before=project["state"].read_bytes();registry_before=project["registry"].read_bytes()
        async with server(project,None,tmp_path/"pair-history.stderr",monkeypatch) as (session,_):
            pages=[];cursor=None
            while True:
                assert len(pages)<3
                page=await probe.diff_call(session,project,before,after,limit=1,**({"cursor":cursor} if cursor else {}))
                assert page["counts"]==dict(added=1,removed=1,modified=1,unchanged=2)
                pages.append(page);cursor=page["next_cursor"]
                if cursor is None:break
            changes=[change for page in pages for change in page["changes"]]
            assert len(pages)==3
            expected_forward,expected_reverse=probe.diff_expected_changes(project["images"],changed,"Configuration.xml","Renamed.xml")
            probe.check_diff_changes(changes,expected_forward)
            reverse=await probe.diff_call(session,project,after,before)
            assert reverse["counts"]==pages[0]["counts"] and reverse["next_cursor"] is None
            probe.check_diff_changes(reverse["changes"],expected_reverse)
            same=await probe.diff_call(session,project,before,before)
            assert same["counts"]==dict(added=0,removed=0,modified=0,unchanged=4)
            assert not same["changes"] and same["next_cursor"] is None
            await read_exact(session,project,before,project["images"][probe.CALLEE])
            await read_exact(session,project,after,changed)
            await probe.diff_refused(session,project,"0"*64,after,"SNAPSHOT_NOT_FOUND")
            await probe.diff_refused(session,project,after,before,"INVALID_DIFF_CURSOR",limit=1,cursor=pages[0]["next_cursor"])
            await probe.diff_refused(session,project,before,after,"INVALID_DIFF_CURSOR",limit=2,cursor=pages[0]["next_cursor"])
            for selected in (before,after):
                manifest=probe.generation(project,selected)/"manifest.json";raw=manifest.read_bytes()
                manifest.write_bytes(b"corrupt selected manifest")
                try:await probe.diff_refused(session,project,before,after,"SNAPSHOT_CORRUPT")
                finally:manifest.write_bytes(raw)
            assert await probe.diff_call(session,project,before,after)==dict(pages[0],changes=changes,next_cursor=None)
            assert await call(session,"rentgen_project_head",dict(project_id=project["project_id"]))==third["head"]
            assert project["state"].read_bytes()==state_before
            assert project["registry"].read_bytes()==registry_before
            membership(False)
            try:await probe.diff_refused(session,project,before,after,"PROJECT_FORBIDDEN")
            finally:membership(True)
        # Authorization changes are intentional audited fixture mutations;
        # the read-only SQLite byte identity was checked before those writes.
        assert project["registry"].read_bytes()==registry_before
        controls=probe.diff_library_controls(project,before,after,principal,state,membership)
        assert all(value is True for name,value in controls.items() if name!="scope")
        with closing(sqlite3.connect(project["state"].as_uri()+"?mode=ro",uri=True)) as db:
            assert db.execute("SELECT count(*) FROM snapshots").fetchone()[0]==3
            assert db.execute("SELECT count(*) FROM publication_receipts").fetchone()[0]==3
    asyncio.run(scenario())
