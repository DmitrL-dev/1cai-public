"""Constructed receipt/wire guards only; no Linux execution is claimed here."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[2]


def module(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


probe=module("snapshot_diff_probe_controls","scripts/verification/owned_linux_sdk_probe.py")
verifier=module("snapshot_diff_verifier_controls","scripts/verification/verify_owned_linux_delivery.py")
PROJECT="11111111-1111-4111-8111-111111111111"
BEFORE,AFTER="a"*64,"b"*64


def page():
    def ref(snapshot):return dict(project_id=PROJECT,snapshot_id=snapshot,manifest_hash=snapshot)
    def entry(snapshot,digest):return dict(ref=dict(snapshot=ref(snapshot),layer_id="base",relative_path=probe.CALLEE,raw_sha256=digest),size_bytes=3,encoding="utf-8",identity_status="unresolved")
    return dict(before_snapshot=ref(BEFORE),after_snapshot=ref(AFTER),scope="source_bytes_by_layer_and_path",identity="source_path_only",
        counts=dict(added=0,removed=0,modified=1,unchanged=0),changes=[dict(kind="modified",before=entry(BEFORE,"c"*64),after=entry(AFTER,"d"*64))],next_cursor=None)


def reply(payload,*,text=None,meta=None,extra=False,is_error=False):
    content=[SimpleNamespace(type="text",text=json.dumps(payload) if text is None else text)]
    if extra:content.append(SimpleNamespace(type="text",text="private trailing data"))
    document=dict(content=[dict(type=x.type,text=x.text) for x in content],structuredContent=payload,isError=is_error)
    if meta is not None:document["_meta"]=meta
    return SimpleNamespace(content=content,structuredContent=payload,model_dump=lambda **options:document)


def test_constructed_public_page_keeps_both_exact_snapshot_bindings():
    value=page();payload={"result":{"snapshot_diff":value},"request_id":PROJECT}
    assert probe.diff_page(value,PROJECT,BEFORE,AFTER) is value
    assert probe.diff_wire(reply(payload))==payload


def test_real_typed_owner_limits_construct_before_any_native_io():
    # This catches omitted mandatory constructor arguments on every host. It
    # neither opens a generation nor pretends the host is Linux.
    from rentgen_core._posix_snapshot_session import PosixSnapshotLimits
    from rentgen_core._read_operation_budget import ReadOperationBudget
    from rentgen_core._verified_graph import VerifiedGraphLimits
    budget=ReadOperationBudget()
    try:
        source,graph=probe.diff_owner_limits(budget)
        assert type(source) is PosixSnapshotLimits and type(graph) is VerifiedGraphLimits
        assert source.copied_byte_budget<=budget.limits.copied_bytes
        assert source.resident_byte_budget<=budget.limits.image_bytes
        assert graph.image_buffer_budget>0
    finally:budget.abort()


@pytest.mark.parametrize("side,field",[("before","raw_sha256"),("after","raw_sha256"),("before","size_bytes"),("after","size_bytes")])
def test_valid_reference_shape_cannot_hide_wrong_fixture_hash_or_size(side,field):
    value=page();change=value["changes"][0]
    expected=[("modified",(probe.CALLEE,"c"*64,3),(probe.CALLEE,"d"*64,3))]
    if field=="raw_sha256":change[side]["ref"][field]="e"*64
    else:change[side][field]=4
    probe.diff_page(value,PROJECT,BEFORE,AFTER)
    with pytest.raises(probe.ProbeFailure):probe.check_diff_changes(value["changes"],expected)


@pytest.mark.parametrize("defect",["private_scope","identity_claim","before_ref","after_ref","different_path","boolean_count","boolean_size","cross_layer"])
def test_valid_looking_page_cannot_change_scope_or_source_reference_authority(defect):
    value=page()
    if defect=="private_scope":value["catalog_digest"]="private authorizer"
    elif defect=="identity_claim":value["identity"]="semantic_object_identity"
    elif defect=="before_ref":value["changes"][0]["before"]["ref"]["snapshot"]["snapshot_id"]=AFTER
    elif defect=="after_ref":value["changes"][0]["after"]["ref"]["snapshot"]["manifest_hash"]=BEFORE
    elif defect=="different_path":value["changes"][0]["after"]["ref"]["relative_path"]="renamed.bsl"
    elif defect=="boolean_count":value["counts"]["modified"]=True
    elif defect=="boolean_size":value["changes"][0]["before"]["size_bytes"]=True
    else:value["changes"][0]["before"]["ref"]["layer_id"]="other"
    with pytest.raises(probe.ProbeFailure):probe.diff_page(value,PROJECT,BEFORE,AFTER)


@pytest.mark.parametrize("defect",["private_meta","divergent_text","duplicate_text_key","extra_content","text_boolean_count","text_float_count","nonfinite_text","overflow_text"])
def test_sdk_representation_guard_rejects_private_scope_or_hidden_second_payload(defect):
    payload={"result":{"snapshot_diff":page()},"request_id":PROJECT}
    options={}
    if defect=="private_meta":options["meta"]={"catalog_digest":"private authorizer"}
    elif defect=="divergent_text":
        other=deepcopy(payload);other["result"]["snapshot_diff"]["after_snapshot"]["snapshot_id"]=BEFORE;options["text"]=json.dumps(other)
    elif defect=="duplicate_text_key":options["text"]='{"result":{"snapshot_diff":"hidden"},'+json.dumps(payload)[1:]
    elif defect in {"text_boolean_count","text_float_count","nonfinite_text","overflow_text"}:
        if defect in {"text_boolean_count","text_float_count"}:
            other=deepcopy(payload);other["result"]["snapshot_diff"]["counts"]["modified"]=True if defect=="text_boolean_count" else 1.0
            options["text"]=json.dumps(other)
        else:options["text"]=json.dumps(payload).replace('"modified": 1','"modified": '+("NaN" if defect=="nonfinite_text" else "1e999"))
    else:options["extra"]=True
    with pytest.raises(probe.ProbeFailure):probe.diff_wire(reply(payload,**options))


@pytest.mark.parametrize("location",["top_extra","block_meta","block_annotations","payload_extra","result_extra","truthy_error_flag"])
def test_equal_text_and_structured_data_cannot_hide_private_dto_metadata(location):
    payload={"result":{"snapshot_diff":page()},"request_id":PROJECT}
    if location=="payload_extra":payload["catalog_digest"]="private-authorizer"
    if location=="result_extra":payload["result"]["output_scope"]={"catalog_digest":"private-authorizer"}
    value=reply(payload);document=value.model_dump()
    if location=="top_extra":document["output_scope"]={"catalog_digest":"private-authorizer"}
    elif location=="block_meta":document["content"][0]["_meta"]={"catalog_digest":"private-authorizer"}
    elif location=="block_annotations":document["content"][0]["annotations"]={"catalog_digest":"private-authorizer"}
    elif location=="truthy_error_flag":document["isError"]=1
    with pytest.raises(probe.ProbeFailure):probe.diff_wire(value)


def error_payload():
    return {"error":dict(code="SNAPSHOT_CORRUPT",message="Controlled fixture refusal",request_id=PROJECT,details={})}


def test_exact_fixture_core_error_remains_a_public_refusal():
    payload=error_payload()
    assert probe.diff_wire(reply(payload,is_error=True))==payload


@pytest.mark.parametrize("defect",["root_extra","error_extra","missing_code","private_details","success_flag"])
def test_comparison_refusal_cannot_hide_authority_in_error_schema(defect):
    payload=error_payload()
    if defect=="root_extra":payload["catalog_digest"]="private-authorizer"
    elif defect=="error_extra":payload["error"]["output_scope"]={"catalog_digest":"private-authorizer"}
    elif defect=="missing_code":payload["error"].pop("code")
    elif defect=="private_details":payload["error"]["details"]={"catalog_digest":"private-authorizer"}
    with pytest.raises(probe.ProbeFailure):probe.diff_wire(reply(payload,is_error=defect!="success_flag"))


def receipt():
    sdk={name:True for name in ("explicit_forward","reverse_pair","self_pair","historical_bytes","broken_unrelated_head_ignored","live_inputs_removed","unknown_snapshot_refused","wrong_pair_cursor_refused","wrong_limit_cursor_refused","tampered_before_refused","tampered_after_refused","revoked_current_read_refused","output_scope_private")}
    sdk.update(pagination=dict(pages=3,changes=3,limit=1,counts=dict(added=1,removed=1,modified=1,unchanged=2)),before_snapshot_sha256=BEFORE,after_snapshot_sha256=AFTER,unrelated_head_snapshot_sha256="e"*64)
    cli={name:True for name in ("explicit_forward","reverse_pair","self_pair","pagination","historical_bytes","broken_unrelated_head_ignored","unknown_snapshot_refused","wrong_pair_cursor_refused","head_database_unchanged")}
    library={name:True for name in ("separate_owners_fit","combined_copy_budget_refused","pre_cancel_refused","descriptors_restored_after_refusals","post_success_authority_revocation_refused","output_scope_pair_mismatch_refused","expired_output_scope_refused")}
    library["scope"]=probe.DIFF_LIBRARY_SCOPE
    return dict(schema=1,scope=probe.DIFF_SCOPE,sdk=sdk,cli=cli,trusted_library_controls=library,limitations=list(probe.DIFF_LIMITATIONS))


def test_complete_constructed_receipt_is_only_a_shape_control():
    assert verifier.require_snapshot_diff_acceptance(receipt()) is None


@pytest.mark.parametrize("defect",["old_receipt","unrelated_head_reused","truthy_flag","boolean_counter","library_claims_sdk","missing_negative","broad_claim"])
def test_acceptance_wrapper_cannot_reuse_capture_only_or_broaden_constructed_claims(defect):
    value=receipt()
    if defect=="old_receipt":value=None
    elif defect=="unrelated_head_reused":value["sdk"]["unrelated_head_snapshot_sha256"]=AFTER
    elif defect=="truthy_flag":value["sdk"]["revoked_current_read_refused"]=1
    elif defect=="boolean_counter":value["sdk"]["pagination"]["counts"]["added"]=True
    elif defect=="library_claims_sdk":value["trusted_library_controls"]["scope"]="actual SDK cancellation during second copy"
    elif defect=="missing_negative":value["trusted_library_controls"].pop("combined_copy_budget_refused")
    else:value["limitations"]=[]
    with pytest.raises(verifier.base.VerificationError):verifier.require_snapshot_diff_acceptance(value)
