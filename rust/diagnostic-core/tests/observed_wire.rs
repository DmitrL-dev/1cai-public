//! Recorded-output regression only: these public fixtures are no longer heldout.
use rentgen_diagnostic_core::evaluate;
use serde_json::{json, Value};
use std::collections::BTreeSet;

const SHARDS: &[&str] = &[
    include_str!("observed-wire/wire-vectors-001.json"),
    include_str!("observed-wire/wire-vectors-002.json"),
    include_str!("observed-wire/wire-vectors-003.json"),
    include_str!("observed-wire/wire-vectors-004.json"),
    include_str!("observed-wire/wire-vectors-005.json"),
    include_str!("observed-wire/wire-vectors-006.json"),
    include_str!("observed-wire/wire-vectors-007.json"),
    include_str!("observed-wire/wire-vectors-008.json"),
    include_str!("observed-wire/wire-vectors-009.json"),
    include_str!("observed-wire/wire-vectors-010.json"),
    include_str!("observed-wire/wire-vectors-011.json"),
    include_str!("observed-wire/wire-vectors-012.json"),
    include_str!("observed-wire/wire-vectors-013.json"),
    include_str!("observed-wire/wire-vectors-014.json"),
    include_str!("observed-wire/wire-vectors-015.json"),
    include_str!("observed-wire/wire-vectors-016.json"),
    include_str!("observed-wire/wire-vectors-017.json"),
];

fn decode_hex(value: &str) -> Vec<u8> {
    fn nibble(value: u8) -> u8 {
        match value { b'0'..=b'9' => value - b'0', b'a'..=b'f' => value - b'a' + 10,
            _ => panic!("noncanonical fixture hex") }
    }
    assert_eq!(value.len() % 2, 0);
    value.as_bytes().chunks_exact(2).map(|p| nibble(p[0]) * 16 + nibble(p[1])).collect()
}

#[test]
fn replay_all_recorded_wire_vectors_without_normalizing_input() {
    let manifest: Value = serde_json::from_str(include_str!("observed-wire/manifest.json")).unwrap();
    assert_eq!(manifest["format_version"], 1);
    assert_eq!(manifest["counts"]["unique_inputs"], 156);
    assert_eq!(manifest["counts"]["covered_call_occurrences"], 249);
    assert_eq!(manifest["shards"].as_array().unwrap().len(), SHARDS.len());
    let (mut ids, mut inputs, mut occurrences) = (BTreeSet::new(), BTreeSet::new(), BTreeSet::new());
    let (mut normal, mut errors) = (0, 0);
    for (index, shard) in SHARDS.iter().enumerate() {
        let meta = &manifest["shards"][index];
        assert_eq!(meta["path"], format!("wire-vectors-{:03}.json", index + 1));
        assert_eq!(meta["bytes"].as_u64().unwrap() as usize, shard.len());
        let value: Value = serde_json::from_str(shard).unwrap();
        assert_eq!(value["format_version"], 1);
        assert_eq!(value["kind"], "recorded_wire_regression");
        let vectors = value["vectors"].as_array().unwrap();
        assert_eq!(meta["unique_vectors"].as_u64().unwrap() as usize, vectors.len());
        let mut shard_occurrences = 0;
        for vector in vectors {
            let id = vector["id"].as_str().unwrap();
            assert!(ids.insert(id.to_owned()), "duplicate vector {id}");
            let input = decode_hex(vector["input_hex"].as_str().unwrap());
            assert_eq!(input.len(), vector["input_bytes"].as_u64().unwrap() as usize, "{id}");
            assert!(inputs.insert(input.clone()), "duplicate input {id}");
            let origins = vector["origins"].as_array().unwrap();
            assert!(!origins.is_empty());
            for origin in origins {
                assert!(occurrences.insert(origin["call_index"].as_u64().unwrap()), "duplicate origin {id}");
                shard_occurrences += 1;
            }
            let expected = &vector["expected"];
            match (expected["kind"].as_str().unwrap(), evaluate(&input)) {
                ("semantic_json", Ok(result)) => {
                    assert_eq!(expected["process_exit_code"], 0);
                    assert_eq!(serde_json::to_value(result).unwrap(), expected["value"], "{id}");
                    normal += 1;
                }
                ("protocol_error", Err(error)) => {
                    assert_eq!(expected["process_exit_code"], 2);
                    let actual: Value = serde_json::from_slice(error.json()).unwrap();
                    assert_eq!(actual, json!({"error": expected["code"]}), "{id}");
                    errors += 1;
                }
                _ => panic!("unexpected result category for {id}"),
            }
        }
        assert_eq!(meta["covered_call_occurrences"].as_u64().unwrap(), shard_occurrences);
    }
    assert_eq!((ids.len(), inputs.len(), normal, errors), (156, 156, 132, 24));
    assert_eq!(occurrences, (1..=249).collect());
}
