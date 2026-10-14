// Package sourcefacts implements only the submitted-source lexical/header profile.
// It does not bind receivers, compile BSL, resolve names, or read source files.
package sourcefacts

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"io"
	"strconv"
	"unicode/utf8"
)

const (
	Protocol              = "source_fact_scan_v1"
	MaxSourceBytes        = 524288
	MaxRequestBytes       = 1500000
	MaxResponseBytes      = 65536
	maxTokens             = 32768
	maxIdentifierRunes    = 128
	maxIdentifierBytes    = 512
	maxStringCommentBytes = 65536
	maxNumberBytes        = 128
	maxRoutines           = 256
	maxParameters         = 128
	maxDelimiterDepth     = 128
)

// Code is a closed, source-free wire error code. An empty code means success.
type Code string

const (
	InvalidRequest Code = "invalid_request"
	InputLimit     Code = "input_limit"
	HashMismatch   Code = "hash_mismatch"
	SizeMismatch   Code = "size_mismatch"
	IOError        Code = "io_error"
	InternalError  Code = "internal_error"
)

// Span uses raw UTF-8 byte offsets, including an initial BOM if present.
type Span struct {
	Start int `json:"start"`
	End   int `json:"end"`
}

type buffer struct {
	entryID int
	size    int
	hash    string
	data    []byte
}

type request struct {
	caller    buffer
	candidate buffer
	alias     bool
	selection Span
}

// parseObject rejects duplicate decoded keys, arrays, noninteger number lexemes,
// invalid Unicode strings, and excessive nesting before applying the schema.
// The standard JSON decoder supplies syntax checking, not permissive coercion.
func parseObject(raw []byte) (map[string]any, bool) {
	if len(raw) < 2 || raw[0] != '{' || raw[len(raw)-1] != '}' || !utf8.Valid(raw) || !scalarEscapes(raw) {
		return nil, false
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	v, ok := readValue(d, 0)
	if !ok {
		return nil, false
	}
	if _, err := d.Token(); err != io.EOF {
		return nil, false
	}
	obj, ok := v.(map[string]any)
	return obj, ok
}

func readValue(d *json.Decoder, depth int) (any, bool) {
	t, err := d.Token()
	if err != nil {
		return nil, false
	}
	switch v := t.(type) {
	case json.Delim:
		if v != '{' || depth >= 12 {
			return nil, false
		}
		obj := make(map[string]any)
		for d.More() {
			key, err := d.Token()
			if err != nil {
				return nil, false
			}
			k, ok := key.(string)
			if !ok {
				return nil, false
			}
			if _, exists := obj[k]; exists {
				return nil, false
			}
			value, ok := readValue(d, depth+1)
			if !ok {
				return nil, false
			}
			obj[k] = value
		}
		end, err := d.Token()
		return obj, err == nil && end == json.Delim('}')
	case json.Number:
		return v, uintLexeme(string(v))
	case string, bool, nil:
		return v, true
	default:
		return nil, false
	}
}

// encoding/json replaces unpaired UTF-16 surrogate escapes. This validation
// rejects them instead. Escaped backslashes cannot introduce a Unicode escape.
func scalarEscapes(raw []byte) bool {
	inString := false
	for i := 0; i < len(raw); i++ {
		if raw[i] == '"' {
			inString = !inString
			continue
		}
		if !inString || raw[i] != '\\' {
			continue
		}
		i++
		if i >= len(raw) {
			return false
		}
		if raw[i] != 'u' {
			continue
		}
		if i+4 >= len(raw) {
			return false
		}
		u, ok := hex4(raw[i+1 : i+5])
		if !ok {
			return false
		}
		i += 4
		if u >= 0xdc00 && u <= 0xdfff {
			return false
		}
		if u >= 0xd800 && u <= 0xdbff {
			if i+6 >= len(raw) || raw[i+1] != '\\' || raw[i+2] != 'u' {
				return false
			}
			low, ok := hex4(raw[i+3 : i+7])
			if !ok || low < 0xdc00 || low > 0xdfff {
				return false
			}
			i += 6
		}
	}
	return !inString
}

func hex4(b []byte) (uint16, bool) {
	var n uint16
	for _, c := range b {
		n <<= 4
		switch {
		case c >= '0' && c <= '9':
			n += uint16(c - '0')
		case c >= 'a' && c <= 'f':
			n += uint16(c - 'a' + 10)
		case c >= 'A' && c <= 'F':
			n += uint16(c - 'A' + 10)
		default:
			return 0, false
		}
	}
	return n, true
}

func uintLexeme(s string) bool {
	if s == "0" {
		return true
	}
	if s == "" || s[0] < '1' || s[0] > '9' {
		return false
	}
	for i := 1; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func object(v any, keys ...string) (map[string]any, bool) {
	o, ok := v.(map[string]any)
	if !ok || len(o) != len(keys) {
		return nil, false
	}
	for _, key := range keys {
		if _, ok := o[key]; !ok {
			return nil, false
		}
	}
	return o, true
}

func uintField(v any, max uint64) (int, bool) {
	n, ok := v.(json.Number)
	if !ok {
		return 0, false
	}
	u, err := strconv.ParseUint(string(n), 10, 64)
	return int(u), err == nil && u <= max
}

func shapeBuffer(v any) (buffer, Code) {
	o, ok := object(v, "entry_id", "size_bytes", "raw_sha256", "data_base64")
	if !ok {
		return buffer{}, InvalidRequest
	}
	id, ok := uintField(o["entry_id"], 4095)
	if !ok {
		return buffer{}, InvalidRequest
	}
	size, ok := uintField(o["size_bytes"], MaxSourceBytes)
	if !ok {
		return buffer{}, InvalidRequest
	}
	hash, ok := o["raw_sha256"].(string)
	if !ok || len(hash) != 64 {
		return buffer{}, InvalidRequest
	}
	for _, c := range hash {
		if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f') {
			return buffer{}, InvalidRequest
		}
	}
	encoded, ok := o["data_base64"].(string)
	if !ok {
		return buffer{}, InvalidRequest
	}
	if len(encoded) > base64.StdEncoding.EncodedLen(MaxSourceBytes) {
		return buffer{}, InputLimit
	}
	data, err := base64.StdEncoding.Strict().DecodeString(encoded)
	if err != nil || base64.StdEncoding.EncodeToString(data) != encoded {
		return buffer{}, InvalidRequest
	}
	if len(data) > MaxSourceBytes {
		return buffer{}, InputLimit
	}
	return buffer{entryID: id, size: size, hash: hash, data: data}, ""
}

func decodeRequest(raw []byte) (request, Code) {
	if len(raw) > MaxRequestBytes {
		return request{}, InputLimit
	}
	root, ok := parseObject(raw)
	if !ok {
		return request{}, InvalidRequest
	}
	o, ok := object(root, "protocol", "caller", "candidate", "selection")
	if !ok || o["protocol"] != Protocol {
		return request{}, InvalidRequest
	}
	caller, code := shapeBuffer(o["caller"])
	if code != "" {
		return request{}, code
	}
	c, ok := o["candidate"].(map[string]any)
	if !ok {
		return request{}, InvalidRequest
	}
	r := request{caller: caller}
	switch c["kind"] {
	case "same_as_caller":
		if _, ok := object(c, "kind"); !ok {
			return request{}, InvalidRequest
		}
		r.candidate, r.alias = caller, true
	case "distinct_entry":
		if _, ok := object(c, "kind", "buffer"); !ok {
			return request{}, InvalidRequest
		}
		r.candidate, code = shapeBuffer(c["buffer"])
		if code != "" {
			return request{}, code
		}
		if caller.entryID == r.candidate.entryID {
			return request{}, InvalidRequest
		}
	default:
		return request{}, InvalidRequest
	}
	s, ok := object(o["selection"], "start", "end")
	if !ok {
		return request{}, InvalidRequest
	}
	start, ok := uintField(s["start"], MaxSourceBytes)
	if !ok {
		return request{}, InvalidRequest
	}
	end, ok := uintField(s["end"], MaxSourceBytes)
	if !ok {
		return request{}, InvalidRequest
	}
	r.selection = Span{start, end}
	// Check the complete schema and all encoding shapes before byte claims.
	if code := checkBuffer(r.caller); code != "" {
		return request{}, code
	}
	if !r.alias {
		if code := checkBuffer(r.candidate); code != "" {
			return request{}, code
		}
	}
	return r, ""
}

func checkBuffer(b buffer) Code {
	if len(b.data) != b.size {
		return SizeMismatch
	}
	sum := sha256.Sum256(b.data)
	if hex.EncodeToString(sum[:]) != b.hash {
		return HashMismatch
	}
	return ""
}
