//! Independent strict admission; does not alter the synthetic-v1 parser.
use super::{model::Envelope, Error, INPUT_LIMIT};
use serde::de::{self, DeserializeSeed, MapAccess, Visitor};
use serde::Deserializer;
use serde_json::{Map, Value};
use std::fmt;

// Check raw integer lexemes before serde can convert them. Track only JSON
// structural bytes outside quoted strings; serde subsequently validates every
// escape, Unicode scalar, keyword and punctuation. Arrays never occur here.
fn preflight(input: &[u8]) -> Result<(), Error> {
    if input.first() != Some(&b'{') || input.last() != Some(&b'}') {
        return Err(Error::InvalidEnvelope);
    }
    let mut i = 0;
    let mut depth = 0u8;
    let mut quoted = false;
    while i < input.len() {
        let b = input[i];
        if quoted {
            match b {
                b'\\' => { i += 1; }
                b'"' => quoted = false,
                _ => (),
            }
        } else {
            match b {
                b'"' => quoted = true,
                b'{' => {
                    depth += 1;
                    if depth > 12 { return Err(Error::InvalidEnvelope); }
                }
                b'}' => { depth = depth.checked_sub(1).ok_or(Error::InvalidEnvelope)?; }
                b'[' | b']' | b'-' | b'+' => return Err(Error::InvalidEnvelope),
                b'0'..=b'9' => {
                    let start = i;
                    while i < input.len() && !matches!(input[i], b',' | b'}' | b':' | b'{' | b'[' | b']' | b' ' | b'\t' | b'\r' | b'\n') {
                        i += 1;
                    }
                    let raw = &input[start..i];
                    if (raw.len() > 1 && raw[0] == b'0') || !raw.iter().all(u8::is_ascii_digit) {
                        return Err(Error::InvalidEnvelope);
                    }
                    continue;
                }
                _ => (),
            }
        }
        i += 1;
    }
    if quoted || depth != 0 { return Err(Error::InvalidEnvelope); }
    Ok(())
}
struct StrictJson;
impl<'de> DeserializeSeed<'de> for StrictJson {
    type Value = Value;
    fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Value, D::Error> {
        d.deserialize_any(self)
    }
}
impl<'de> Visitor<'de> for StrictJson {
    type Value = Value;
    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { f.write_str("closed JSON") }
    fn visit_bool<E: de::Error>(self, v: bool) -> Result<Value, E> { Ok(Value::Bool(v)) }
    fn visit_u64<E: de::Error>(self, v: u64) -> Result<Value, E> { Ok(Value::Number(v.into())) }
    fn visit_str<E: de::Error>(self, v: &str) -> Result<Value, E> { Ok(Value::String(v.to_owned())) }
    fn visit_string<E: de::Error>(self, v: String) -> Result<Value, E> { Ok(Value::String(v)) }
    fn visit_unit<E: de::Error>(self) -> Result<Value, E> { Ok(Value::Null) }
    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Value, A::Error> {
        let mut object = Map::new();
        while let Some(key) = map.next_key::<String>()? {
            if object.contains_key(&key) { return Err(de::Error::custom("invalid")); }
            object.insert(key, map.next_value_seed(StrictJson)?);
        }
        Ok(Value::Object(object))
    }
    // No sequence, signed or float visitor. No coercion or positional records.
}
pub(super) fn parse(input: &[u8]) -> Result<Envelope, Error> {
    if input.len() > INPUT_LIMIT { return Err(Error::InputLimit); }
    preflight(input)?;
    let mut d = serde_json::Deserializer::from_slice(input);
    let value = StrictJson.deserialize(&mut d).map_err(|_| Error::InvalidEnvelope)?;
    d.end().map_err(|_| Error::InvalidEnvelope)?;
    serde_json::from_value(value).map_err(|_| Error::InvalidEnvelope)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn raw_depth_counts_root_and_ignores_quoted_braces() {
        for n in [1, 12] {
            let text = format!("{}0{}", "{\"k\":".repeat(n), "}".repeat(n));
            assert_eq!(preflight(text.as_bytes()), Ok(()));
        }
        let text = format!("{}0{}", "{\"k\":".repeat(13), "}".repeat(13));
        assert_eq!(preflight(text.as_bytes()), Err(Error::InvalidEnvelope));
        assert_eq!(preflight(br#"{"k":"{[0e2]}\\\""}"#), Ok(()));
    }
}
