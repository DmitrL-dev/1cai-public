//! Author-written development cases, not independent source qualification.
use rentgen_diagnostic_core::source_facts::{evaluate, Error, INPUT_LIMIT};
use serde_json::{json, Value};

const LEX_AND_SELECTOR: &[&str] = &[
    "invalid_utf8", "invalid_bom", "forbidden_control", "invalid_line_ending",
    "unsupported_code_character", "identifier_limit", "token_bytes_limit", "token_count_limit",
    "invalid_number", "unsupported_literal", "unterminated_string", "multiline_string",
    "unsupported_keyword", "unsupported_top_level", "invalid_header", "duplicate_parameter",
    "parameter_limit", "duplicate_routine", "routine_limit", "nested_routine", "mismatched_terminator",
    "missing_terminator", "stray_structural_keyword", "unbalanced_delimiter", "delimiter_depth_limit",
    "selector_span_invalid", "selector_not_qualified", "selector_outside_body", "selector_chained",
];
const EXPORT_STATES: &[&str] = &["true", "false", "selector_unavailable",
    "candidate_identity_unavailable", "candidate_name_mismatch", "candidate_not_admitted", "declaration_unavailable"];
const SERVER_STATES: &[&str] = &["true", "false", "selector_unavailable", "candidate_name_mismatch",
    "xml_missing", "xml_limit", "xml_forbidden", "xml_invalid", "xml_shape_unsupported",
    "xml_duplicate_container", "xml_name_missing", "xml_name_duplicate", "xml_name_invalid",
    "xml_server_missing", "xml_server_duplicate", "xml_server_invalid"];
fn unavailable(reason: &str) -> Value { json!({"state":"unavailable","reason":reason}) }
fn base() -> Value {
    json!({"schema_version":2,"profile":"submitted_source_facts_v1","rule_set":"source_observations_v1",
        "scope":{"case_id":1,"input_id":2,"selector_id":3,"caller_entry_id":4,"candidate_entry_id":5,"xml_entry_id":6},
        "observations":{
            "selector":{"state":"observed","value":"qualified_selector","receipt_id":10},
            "export":{"state":"observed","value":true,"receipt_id":11,"header_id":20},
            "server":{"state":"observed","value":false,"receipt_id":12,"property_id":30}},
        "receipts":{
            "selector":{"receipt_id":10,"case_id":1,"input_id":2,"selector_id":3,"entry_id":4},
            "export":{"receipt_id":11,"case_id":1,"input_id":2,"selector_id":3,"entry_id":5,"header_id":20},
            "server":{"receipt_id":12,"case_id":1,"input_id":2,"selector_id":3,"entry_id":6,"property_id":30}},
        "receiver_binding":"unknown","runtime_relation":"unknown"})
}
fn bytes(v: &Value) -> Vec<u8> { serde_json::to_vec(v).unwrap() }
fn invalid(v: &Value) { assert_eq!(evaluate(&bytes(v)), Err(Error::InvalidEnvelope), "{v}"); }
fn set_reason(v: &mut Value, role: &str, reason: &str) {
    v["observations"][role] = unavailable(reason); v["receipts"][role] = Value::Null;
}
fn dependent(v: &mut Value, role: &str, state: &str) {
    match state { "true" => v["observations"][role]["value"] = json!(true),
        "false" => v["observations"][role]["value"] = json!(false), _ => set_reason(v, role, state) }
}

#[test]
fn exact_ordered_output_keeps_only_assertions_and_unknown_relations() {
    let result = evaluate(&bytes(&base())).unwrap();
    let actual = serde_json::to_string(&result).unwrap();
    assert_eq!(actual, concat!(
        "{\"schema_version\":2,\"profile\":\"submitted_source_facts_v1\",\"rule_set\":\"source_observations_v1\",",
        "\"assurance\":\"source_facts_host_asserted_no_binding_no_runtime\",",
        "\"scope\":{\"case_id\":1,\"input_id\":2,\"selector_id\":3,\"caller_entry_id\":4,\"candidate_entry_id\":5,\"xml_entry_id\":6},",
        "\"observations\":{\"selector\":{\"state\":\"observed\",\"value\":\"qualified_selector\",\"receipt_id\":10},",
        "\"export\":{\"state\":\"observed\",\"value\":true,\"receipt_id\":11,\"header_id\":20},",
        "\"server\":{\"state\":\"observed\",\"value\":false,\"receipt_id\":12,\"property_id\":30}},",
        "\"receiver_binding\":\"unknown\",\"runtime_relation\":\"unknown\"}"));
    assert!(!actual.contains("receipts"));
    assert!(rentgen_diagnostic_core::evaluate(&bytes(&base())).is_err());
    let mut v = base(); v["profile"] = json!("synthetic_v1"); invalid(&v);
}
#[test]
fn exhaustive_dependency_matrix_with_both_values_xml_presence_and_same_file() {
    // Oracle spells out the frozen table independently of Rust enum patterns.
    let identity = ["xml_limit", "xml_forbidden", "xml_invalid", "xml_shape_unsupported",
        "xml_duplicate_container", "xml_name_missing", "xml_name_duplicate", "xml_name_invalid"];
    let usable_export = ["true", "false", "candidate_not_admitted", "declaration_unavailable"];
    let usable_server = ["true", "false", "xml_server_missing", "xml_server_duplicate", "xml_server_invalid"];
    let (mut accepted, mut rejected) = (0, 0);
    for selector in [false, true] { for e in EXPORT_STATES { for s in SERVER_STATES {
        for has_xml in [false, true] { for alias in [false, true] {
            let mut v = base();
            if !selector { set_reason(&mut v, "selector", "selector_not_qualified"); }
            dependent(&mut v, "export", e); dependent(&mut v, "server", s);
            if !has_xml { v["scope"]["xml_entry_id"] = Value::Null; }
            if alias {
                v["scope"]["candidate_entry_id"] = json!(4);
                if v["receipts"]["export"].is_object() { v["receipts"]["export"]["entry_id"] = json!(4); }
            }
            let expected = if !selector { *e == "selector_unavailable" && *s == "selector_unavailable" }
                else if !has_xml { *e == "candidate_identity_unavailable" && *s == "xml_missing" }
                else { (*e == "candidate_identity_unavailable" && identity.contains(s))
                    || (*e == "candidate_name_mismatch" && *s == "candidate_name_mismatch")
                    || (usable_export.contains(e) && usable_server.contains(s)
                        && !(alias && *e == "candidate_not_admitted")) };
            let outcome = evaluate(&bytes(&v));
            if expected {
                let result = serde_json::to_value(outcome.unwrap()).unwrap();
                let mut wanted = v.clone();
                wanted.as_object_mut().unwrap().remove("receipts");
                wanted["assurance"] = json!("source_facts_host_asserted_no_binding_no_runtime");
                assert_eq!(result, wanted,
                    "unchanged assertions: selector={selector} export={e} server={s} xml={has_xml} alias={alias}");
                assert_eq!(result["receiver_binding"], "unknown");
                assert_eq!(result["runtime_relation"], "unknown");
                accepted += 1;
            } else {
                assert_eq!(outcome, Err(Error::InvalidEnvelope),
                    "closed rejection: selector={selector} export={e} server={s} xml={has_xml} alias={alias}");
                rejected += 1;
            }
        }}
    }}}
    assert_eq!((accepted, rejected), (59, 837));
}
#[test]
fn all_selector_reasons_are_closed_and_abstention_is_success() {
    for reason in LEX_AND_SELECTOR {
        let mut v = base(); set_reason(&mut v, "selector", reason);
        set_reason(&mut v, "export", "selector_unavailable");
        set_reason(&mut v, "server", "selector_unavailable");
        assert!(evaluate(&bytes(&v)).is_ok());
        v["scope"]["xml_entry_id"] = Value::Null;
        assert!(evaluate(&bytes(&v)).is_ok());
    }
    for reason in ["caller_not_admitted", "absent", "CANARY_SECRET", "", "INVALID_UTF8"] {
        let mut v = base(); set_reason(&mut v, "selector", reason); invalid(&v);
    }
}
#[test]
fn every_receipt_role_and_scope_is_checked() {
    for role in ["selector", "export", "server"] {
        for field in ["receipt_id", "case_id", "input_id", "selector_id", "entry_id"] {
            let mut v = base(); v["receipts"][role][field] = json!(99); invalid(&v);
        }
        let mut v = base(); v["receipts"][role] = Value::Null; invalid(&v);
    }
    for (role, field) in [("export", "header_id"), ("server", "property_id")] {
        let mut v = base(); v["receipts"][role][field] = json!(99); invalid(&v);
        let mut v = base(); v["observations"][role][field] = json!(99); invalid(&v);
    }
    for (left, right) in [("selector", "export"), ("selector", "server"), ("export", "server")] {
        let mut v = base(); let id = v["receipts"][left]["receipt_id"].clone();
        v["receipts"][right]["receipt_id"] = id.clone(); v["observations"][right]["receipt_id"] = id; invalid(&v);
    }
    for id in [4,5] { let mut v = base(); v["scope"]["xml_entry_id"] = json!(id); invalid(&v); }
    assert!(evaluate(&bytes(&base())).is_ok());
    for id in [4,5] {
        let mut v = base();
        v["scope"]["xml_entry_id"] = json!(id);
        // Keep the receipt coherent so this isolates XML-vs-BSL collision.
        v["receipts"]["server"]["entry_id"] = json!(id);
        invalid(&v);
    }
    // Typed namespaces may share IDs; this does not turn references into assurance.
    let mut v = base();
    for field in ["case_id", "input_id", "selector_id"] {
        v["scope"][field] = json!(10);
        for role in ["selector", "export", "server"] { v["receipts"][role][field] = json!(10); }
    }
    assert!(evaluate(&bytes(&v)).is_ok());
}
fn object_paths(value: &Value, prefix: &str, out: &mut Vec<String>) {
    if let Some(object) = value.as_object() {
        out.push(prefix.to_owned());
        for (key, child) in object { object_paths(child, &format!("{prefix}/{key}"), out); }
    }
}
#[test]
fn every_record_rejects_unknown_missing_fields_positional_arrays_and_wrong_types() {
    let mut abstention = base();
    set_reason(&mut abstention, "selector", "invalid_utf8");
    set_reason(&mut abstention, "export", "selector_unavailable");
    set_reason(&mut abstention, "server", "selector_unavailable");
    abstention["scope"]["xml_entry_id"] = Value::Null;
    for original in [base(), abstention] {
        let mut paths = vec![]; object_paths(&original, "", &mut paths);
        for path in paths {
            let record = original.pointer(&path).unwrap().as_object().unwrap();
            let mut v = original.clone(); v.pointer_mut(&path).unwrap()["CANARY_SECRET"] = json!(1); invalid(&v);
            for key in record.keys() {
                let mut v = original.clone(); v.pointer_mut(&path).unwrap().as_object_mut().unwrap().remove(key); invalid(&v);
            }
            for substitute in [json!([]), json!(record.values().collect::<Vec<_>>()), json!(null), json!(true), json!(0), json!("object")] {
                let mut v = original.clone(); *v.pointer_mut(&path).unwrap() = substitute; invalid(&v);
            }
        }
    }
}
#[test]
fn raw_integer_lexemes_bounds_duplicate_decoded_keys_and_unicode_are_strict() {
    let raw = String::from_utf8(bytes(&base())).unwrap();
    for token in ["-0", "-1", "+1", "01", "1.0", "1e0", "1E+0", "true", "false", "null", "\"1\"", "0", "2147483648", "18446744073709551616"] {
        let mutated = raw.replacen("\"case_id\":1", &format!("\"case_id\":{token}"), 1);
        assert_eq!(evaluate(mutated.as_bytes()), Err(Error::InvalidEnvelope), "{token}");
    }
    for slot in ["/scope/case_id", "/scope/input_id", "/scope/selector_id", "/scope/caller_entry_id",
        "/scope/candidate_entry_id", "/scope/xml_entry_id", "/observations/selector/receipt_id",
        "/observations/export/receipt_id", "/observations/export/header_id", "/observations/server/receipt_id",
        "/observations/server/property_id", "/receipts/selector/receipt_id", "/receipts/export/header_id", "/receipts/server/property_id"] {
        for wrong in [json!(0), json!(2_147_483_648u64), json!(true), json!("1")] {
            let mut v = base(); *v.pointer_mut(slot).unwrap() = wrong; invalid(&v);
        }
    }
    assert!(evaluate(raw.as_bytes()).is_ok());
    let ordinary = raw.replacen("\"case_id\":1", "\"case_id\":1,\"case_id\":1", 1);
    assert_eq!(evaluate(ordinary.as_bytes()), Err(Error::InvalidEnvelope));
    let duplicate = raw.replacen("\"case_id\":1", "\"case_id\":1,\"case\\u005fid\":1", 1);
    assert_eq!(evaluate(duplicate.as_bytes()), Err(Error::InvalidEnvelope));
    let duplicate_tag = raw.replacen("\"state\":\"observed\"", "\"state\":\"observed\",\"st\\u0061te\":\"observed\"", 1);
    assert_eq!(evaluate(duplicate_tag.as_bytes()), Err(Error::InvalidEnvelope));
    let escaped = raw.replace("\"profile\"", "\"pro\\u0066ile\"").replace("submitted_source_facts_v1", "submitted_source_facts_\\u00761");
    assert!(evaluate(escaped.as_bytes()).is_ok());
    for malformed in [raw.replace("unknown", "\\ud800"), raw.replace("unknown", "\\udfff")] {
        assert_eq!(evaluate(malformed.as_bytes()), Err(Error::InvalidEnvelope));
    }
    let mut invalid_utf8 = bytes(&base()); invalid_utf8[2] = 0xff;
    assert_eq!(evaluate(&invalid_utf8), Err(Error::InvalidEnvelope));
}
#[test]
fn forged_verified_states_relations_receipts_and_ordinary_canary_fields_are_rejected() {
    for field in ["receiver_binding", "runtime_relation"] {
        for state in ["present", "supported", "refuted", "resolved", "static_external_resolved", "verified", "CANARY_SECRET"] {
            let mut v = base(); v[field] = json!(state); invalid(&v);
        }
    }
    for field in ["assurance", "workflow", "permission", "capabilities", "source", "path", "hash", "confidence"] {
        let mut v = base(); v[field] = json!("verified_CANARY_SECRET"); invalid(&v);
    }
    for role in ["selector", "export", "server"] {
        for state in ["present", "supported", "refuted", "verified"] {
            let mut v = base(); v["observations"][role]["state"] = json!(state); invalid(&v);
        }
        let mut v = base(); v["receipts"][role]["verified"] = json!(true); invalid(&v);
        let mut v = base(); v["observations"][role]["reason"] = json!("declaration_unavailable"); invalid(&v);
    }
}
#[test]
fn exact_root_framing_and_payload_cap_allow_only_interior_whitespace() {
    let raw = bytes(&base());
    for (prefix,suffix) in [(b" ".as_slice(),b"".as_slice()), (b"",b"\n"), (b"\xef\xbb\xbf",b""), (b"",b"{}"), (b"",b"x")] {
        assert_eq!(evaluate(&[prefix,&raw,suffix].concat()), Err(Error::InvalidEnvelope));
    }
    let mut padded = raw.clone(); padded.splice(1..1, std::iter::repeat_n(b' ', INPUT_LIMIT-raw.len()));
    assert_eq!(padded.len(), INPUT_LIMIT); assert!(evaluate(&padded).is_ok());
    padded.insert(1,b' '); assert_eq!(evaluate(&padded), Err(Error::InputLimit));
    for input in [b"".as_slice(), b"[]", b"null", b"true", b"{}", b"{\"scope\":{", b"{\"n\":NaN}", b"{\"n\":Infinity}"] {
        assert_eq!(evaluate(input), Err(Error::InvalidEnvelope));
    }
}

#[test]
fn booleans_enums_nullability_and_maximum_ids_are_exact() {
    for role in ["export", "server"] {
        for value in [json!(0), json!(1), json!("true"), json!(null), json!({})] {
            let mut v = base(); v["observations"][role]["value"] = value; invalid(&v);
        }
    }
    for value in [json!(true), json!("call"), json!("supported"), json!(null)] {
        let mut v = base(); v["observations"]["selector"]["value"] = value; invalid(&v);
    }
    for (field, value) in [("schema_version", json!(1)), ("schema_version", json!(true)),
        ("rule_set", json!("source_observations_v2")), ("profile", json!(null))] {
        let mut v = base(); v[field] = value; invalid(&v);
    }
    let mut v = base();
    for field in ["case_id", "input_id", "selector_id"] {
        v["scope"][field] = json!(2_147_483_647u32);
        for role in ["selector", "export", "server"] { v["receipts"][role][field] = json!(2_147_483_647u32); }
    }
    assert!(evaluate(&bytes(&v)).is_ok());
    let receipt = v["receipts"]["export"].clone();
    set_reason(&mut v,"export","declaration_unavailable");
    assert!(evaluate(&bytes(&v)).is_ok());
    v["receipts"]["export"] = receipt; invalid(&v);
}
