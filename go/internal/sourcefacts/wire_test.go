package sourcefacts

import (
	"bytes"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"io"
	"strings"
	"testing"
)

func basicRequest(t *testing.T) []byte {
	t.Helper()
	caller := wrapped("R.M();")
	return mustJSON(t, requestObject(caller, "Procedure M()\nEndProcedure", selectionOf(t, caller, "R.M"), false))
}

// These fixed test-owned envelopes must not call production ErrorResponse:
// Evaluate uses that same function, so sharing it would self-confirm a change.
func testErrorResponse(t *testing.T, code Code) []byte {
	t.Helper()
	goldens := map[Code]string{
		InvalidRequest: `{"protocol":"source_fact_scan_v1","status":"error","code":"invalid_request"}`,
		InputLimit:     `{"protocol":"source_fact_scan_v1","status":"error","code":"input_limit"}`,
		HashMismatch:   `{"protocol":"source_fact_scan_v1","status":"error","code":"hash_mismatch"}`,
		SizeMismatch:   `{"protocol":"source_fact_scan_v1","status":"error","code":"size_mismatch"}`,
		IOError:        `{"protocol":"source_fact_scan_v1","status":"error","code":"io_error"}`,
		InternalError:  `{"protocol":"source_fact_scan_v1","status":"error","code":"internal_error"}`,
	}
	raw, ok := goldens[code]
	if !ok {
		t.Fatal("test lacks an independent closed-error golden")
	}
	return []byte(raw)
}

func TestStrictRequestJSON(t *testing.T) {
	valid := string(basicRequest(t))
	if out, code := Evaluate([]byte(valid)); code != "" || !bytes.Contains(out, []byte(`"status":"ok"`)) {
		t.Fatal("admitted request control failed")
	}
	cases := map[string]string{
		"leading_space":         " " + valid,
		"trailing_space":        valid + "\n",
		"bom":                   "\ufeff" + valid,
		"array":                 "[" + valid + "]",
		"duplicate":             strings.Replace(valid, `"protocol":`, `"protocol":"source_fact_scan_v1","protocol":`, 1),
		"escaped_duplicate":     strings.Replace(valid, `"protocol":`, `"\u0070rotocol":"source_fact_scan_v1","protocol":`, 1),
		"unknown":               strings.Replace(valid, `"protocol":`, `"secret":"PRIVATE_WIRE_CANARY","protocol":`, 1),
		"negative_zero":         strings.Replace(valid, `"entry_id":0`, `"entry_id":-0`, 1),
		"negative":              strings.Replace(valid, `"entry_id":0`, `"entry_id":-1`, 1),
		"fraction":              strings.Replace(valid, `"entry_id":0`, `"entry_id":0.0`, 1),
		"exponent":              strings.Replace(valid, `"entry_id":0`, `"entry_id":0e0`, 1),
		"literal_1_0":           strings.Replace(valid, `"entry_id":0`, `"entry_id":1.0`, 1),
		"literal_1e0":           strings.Replace(valid, `"entry_id":0`, `"entry_id":1e0`, 1),
		"root_depth_13":         strings.Replace(valid, `"protocol":`, `"nested":`+strings.Repeat(`{"x":`, 12)+`0`+strings.Repeat(`}`, 12)+`,"protocol":`, 1),
		"boolean_id":            strings.Replace(valid, `"entry_id":0`, `"entry_id":true`, 1),
		"string_id":             strings.Replace(valid, `"entry_id":0`, `"entry_id":"0"`, 1),
		"id_overflow":           strings.Replace(valid, `"entry_id":0`, `"entry_id":18446744073709551616`, 1),
		"id_bound":              strings.Replace(valid, `"entry_id":0`, `"entry_id":4096`, 1),
		"same_ids":              strings.Replace(valid, `"entry_id":1`, `"entry_id":0`, 1),
		"null_caller":           `{"protocol":"source_fact_scan_v1","caller":null,"candidate":{"kind":"same_as_caller"},"selection":{"start":0,"end":1}}`,
		"array_candidate":       strings.Replace(valid, `"kind":"distinct_entry"`, `"kind":[]`, 1),
		"missing_protocol":      strings.Replace(valid, `"protocol":"source_fact_scan_v1",`, ``, 1),
		"protocol_case":         strings.Replace(valid, `source_fact_scan_v1`, `Source_fact_scan_v1`, 1),
		"wrong_protocol_type":   strings.Replace(valid, `"protocol":"source_fact_scan_v1"`, `"protocol":{}`, 1),
		"lone_high_surrogate":   strings.Replace(valid, `source_fact_scan_v1`, `\ud800`, 1),
		"lone_low_surrogate":    strings.Replace(valid, `source_fact_scan_v1`, `\udc00`, 1),
		"broken_surrogate_pair": strings.Replace(valid, `source_fact_scan_v1`, `\ud800\u0041`, 1),
		"invalid_utf8":          strings.Replace(valid, `source_fact_scan_v1`, "\xff", 1),
		"extra_document":        valid + valid,
		"forged_binding":        strings.Replace(valid, `"protocol":`, `"receiver_binding":"resolved","protocol":`, 1),
	}
	for name, raw := range cases {
		t.Run(name, func(t *testing.T) {
			out, code := Evaluate([]byte(raw))
			if code != InvalidRequest {
				t.Fatalf("code=%s", code)
			}
			if !bytes.Equal(out, testErrorResponse(t, InvalidRequest)) || bytes.Contains(out, []byte("PRIVATE_WIRE_CANARY")) {
				t.Fatal("nonclosed error")
			}
		})
	}
}

func TestStrictObjectAndUnicodeParser(t *testing.T) {
	for _, raw := range []string{`{"x":"\ud83e\udd8a"}`, `{"x":"\\ud800"}`, `{"\u0078":true}`, `{"x":null}`} {
		if _, ok := parseObject([]byte(raw)); !ok {
			t.Errorf("valid scalar object rejected: %s", raw)
		}
	}
	for _, raw := range []string{`{"x":[]}`, `{"x":-0}`, `{"x":1.1}`, `{"x":1e0}`, `{"x":"\ud800"}`, `{"x":"\udd8a"}`, `{"x":"\ud83eX"}`, `{"x":true,"\u0078":false}`} {
		if _, ok := parseObject([]byte(raw)); ok {
			t.Errorf("invalid object accepted: %s", raw)
		}
	}
	for depth := 1; depth <= 13; depth++ {
		raw := strings.Repeat(`{"x":`, depth) + `0` + strings.Repeat(`}`, depth)
		_, ok := parseObject([]byte(raw))
		if ok != (depth <= 12) {
			t.Fatalf("depth %d: %v", depth, ok)
		}
	}
	valid := string(basicRequest(t))
	escaped := strings.Replace(strings.Replace(valid, `"protocol":`, `"\u0070rotocol":`, 1), `source_fact_scan_v1`, `source_fact_scan_v\u0031`, 1)
	if _, code := Evaluate([]byte(escaped)); code != "" {
		t.Fatal("decoded keys/enums must compare by value")
	}
}

func TestBufferValidationAndPrecedence(t *testing.T) {
	caller := wrapped("R.M();")
	newRequest := func() map[string]any {
		return requestObject(caller, "Procedure M()\nEndProcedure", selectionOf(t, caller, "R.M"), false)
	}
	if out, code := Evaluate(mustJSON(t, newRequest())); code != "" || !bytes.Contains(out, []byte(`"status":"ok"`)) {
		t.Fatal("admitted buffer control failed")
	}
	cases := []struct {
		name   string
		mutate func(map[string]any)
		code   Code
	}{
		{"size", func(r map[string]any) { r["caller"].(map[string]any)["size_bytes"] = 0 }, SizeMismatch},
		{"hash", func(r map[string]any) { r["caller"].(map[string]any)["raw_sha256"] = strings.Repeat("0", 64) }, HashMismatch},
		{"hash_upper", func(r map[string]any) { r["caller"].(map[string]any)["raw_sha256"] = strings.Repeat("A", 64) }, InvalidRequest},
		{"hash_length", func(r map[string]any) { r["caller"].(map[string]any)["raw_sha256"] = "0" }, InvalidRequest},
		{"base64_padding", func(r map[string]any) { r["caller"].(map[string]any)["data_base64"] = "Zg" }, InvalidRequest},
		{"base64_bits", func(r map[string]any) { r["caller"].(map[string]any)["data_base64"] = "Zh==" }, InvalidRequest},
		{"base64_whitespace", func(r map[string]any) { r["caller"].(map[string]any)["data_base64"] = "Zg==\n" }, InvalidRequest},
		{"base64_url", func(r map[string]any) { r["caller"].(map[string]any)["data_base64"] = "_w==" }, InvalidRequest},
		{"alias_extra", func(r map[string]any) {
			r["candidate"] = map[string]any{"kind": "same_as_caller", "buffer": bufferObject(0, nil)}
		}, InvalidRequest},
		{"candidate_shape_before_caller_hash", func(r map[string]any) {
			r["caller"].(map[string]any)["raw_sha256"] = strings.Repeat("0", 64)
			r["candidate"] = nil
		}, InvalidRequest},
		{"caller_size_before_hash", func(r map[string]any) {
			b := r["caller"].(map[string]any)
			b["raw_sha256"] = strings.Repeat("0", 64)
			b["size_bytes"] = 0
		}, SizeMismatch},
		{"caller_before_candidate", func(r map[string]any) {
			r["caller"].(map[string]any)["raw_sha256"] = strings.Repeat("0", 64)
			r["candidate"].(map[string]any)["buffer"].(map[string]any)["size_bytes"] = 0
		}, HashMismatch},
		{"source_limit", func(r map[string]any) {
			r["caller"].(map[string]any)["data_base64"] = base64.StdEncoding.EncodeToString(make([]byte, MaxSourceBytes+1))
		}, InputLimit},
	}
	for _, tt := range cases {
		t.Run(tt.name, func(t *testing.T) {
			r := newRequest()
			tt.mutate(r)
			out, code := Evaluate(mustJSON(t, r))
			if code != tt.code {
				t.Fatalf("code=%s, want %s", code, tt.code)
			}
			if !bytes.Equal(out, testErrorResponse(t, tt.code)) {
				t.Fatal("buffer rejection released nonclosed or partial observations")
			}
		})
	}
	if _, code := Evaluate(bytes.Repeat([]byte{' '}, MaxRequestBytes+1)); code != InputLimit {
		t.Fatal("request length unchecked")
	}
	if _, code := Evaluate(mustJSON(t, requestObject("", "", Span{0, 0}, false))); code != "" {
		t.Fatal("empty buffers must be admitted with unavailable selection")
	}
}

func TestMaximumDistinctSourceBuffers(t *testing.T) {
	// Whitespace is source, but not a token. Two maximum canonical base64
	// buffers fit the deliberately larger Go request bound.
	source := strings.Repeat(" ", MaxSourceBytes)
	raw := mustJSON(t, requestObject(source, source, Span{0, 0}, false))
	if len(raw) > MaxRequestBytes {
		t.Fatal("request bound does not fit source maxima")
	}
	if _, code := Evaluate(raw); code != "" {
		t.Fatalf("maximum buffers: %s", code)
	}
}

func frame(raw []byte) []byte {
	out := make([]byte, 4+len(raw))
	binary.LittleEndian.PutUint32(out, uint32(len(raw)))
	copy(out[4:], raw)
	return out
}
func readTestFrame(t *testing.T, r io.Reader) []byte {
	t.Helper()
	var h [4]byte
	if _, err := io.ReadFull(r, h[:]); err != nil {
		t.Fatal(err)
	}
	n := binary.LittleEndian.Uint32(h[:])
	if n > MaxResponseBytes {
		t.Fatal("oversize output")
	}
	raw := make([]byte, n)
	if _, err := io.ReadFull(r, raw); err != nil {
		t.Fatal(err)
	}
	return raw
}

func TestOneShotFraming(t *testing.T) {
	valid := frame(basicRequest(t))
	tooLarge := make([]byte, 4)
	binary.LittleEndian.PutUint32(tooLarge, MaxRequestBytes+1)
	cases := []struct {
		name  string
		input []byte
		code  Code
	}{
		{"valid", valid, ""}, {"empty", nil, InvalidRequest}, {"short_prefix", valid[:3], InvalidRequest},
		{"short_body", valid[:len(valid)-1], InvalidRequest}, {"trailing_byte", append(append([]byte(nil), valid...), 0), InvalidRequest},
		{"second_frame", append(append([]byte(nil), valid...), valid...), InvalidRequest}, {"oversize", tooLarge, InputLimit}, {"zero", make([]byte, 4), InvalidRequest},
	}
	for _, tt := range cases {
		t.Run(tt.name, func(t *testing.T) {
			var out bytes.Buffer
			status := Serve(bytes.NewReader(tt.input), &out)
			if got := string(readTestFrame(t, &out)); got != Hello {
				t.Fatal("wrong hello")
			}
			response := readTestFrame(t, &out)
			if out.Len() != 0 {
				t.Fatal("trailing stdout")
			}
			if tt.code == "" {
				if status != 0 {
					t.Fatal("valid exchange failed")
				}
			} else if status != 2 || !bytes.Equal(response, testErrorResponse(t, tt.code)) {
				t.Fatalf("wrong error/status %d", status)
			}
		})
	}
}

type failingReader struct{}

func (failingReader) Read([]byte) (int, error) { return 0, errors.New("PRIVATE_IO_CANARY") }

type shortWriter struct{ bytes.Buffer }

func (w *shortWriter) Write(p []byte) (int, error) {
	if len(p) > 1 {
		p = p[:1]
	}
	return w.Buffer.Write(p)
}

type zeroWriter struct{}

func (zeroWriter) Write([]byte) (int, error) { return 0, nil }

type panickingReader struct{}

func (panickingReader) Read([]byte) (int, error) { panic("PRIVATE_PANIC_CANARY") }

func TestIOAndPanicPrivacy(t *testing.T) {
	for _, tt := range []struct {
		reader io.Reader
		code   Code
	}{{failingReader{}, IOError}, {panickingReader{}, InternalError}} {
		var out bytes.Buffer
		if Serve(tt.reader, &out) != 2 {
			t.Fatal("expected status 2")
		}
		if bytes.Contains(out.Bytes(), []byte("PRIVATE_")) {
			t.Fatal("dynamic diagnostic leaked")
		}
		readTestFrame(t, &out)
		if !bytes.Equal(readTestFrame(t, &out), testErrorResponse(t, tt.code)) {
			t.Fatal("wrong closed error")
		}
	}
	var out shortWriter
	if Serve(bytes.NewReader(frame(basicRequest(t))), &out) != 0 {
		t.Fatal("partial writes not completed")
	}
	if Serve(bytes.NewReader(frame(basicRequest(t))), zeroWriter{}) != 2 {
		t.Fatal("zero write accepted")
	}
}

// Finite public completion variants from the independent W audit. Selection
// at the inclusive raw endpoint is a wire success with unavailable selection.
func TestInclusiveWireRequestBounds(t *testing.T) {
	caller := wrapped("R.M();")
	valid := requestObject(caller, "Procedure M()\nEndProcedure", selectionOf(t, caller, "R.M"), false)
	baseline := evaluateObject(t, valid)
	if baseline["status"] != "ok" {
		t.Fatal("admitted control failed")
	}
	t.Run("entry_4095", func(t *testing.T) {
		r := requestObject(caller, "Procedure M()\nEndProcedure", selectionOf(t, caller, "R.M"), false)
		r["caller"].(map[string]any)["entry_id"] = 4095
		out := evaluateObject(t, r)
		observedState(t, out["selector"], "observed")
	})
	for _, edge := range []struct {
		name      string
		selection Span
		code      Code
	}{
		{"start_524288", Span{524288, 524288}, ""},
		{"start_524289", Span{524289, 524288}, InvalidRequest},
		{"end_524289", Span{0, 524289}, InvalidRequest},
	} {
		t.Run(edge.name, func(t *testing.T) {
			r := requestObject(caller, "Procedure M()\nEndProcedure", edge.selection, false)
			out, code := Evaluate(mustJSON(t, r))
			if code != edge.code {
				t.Fatalf("code=%s, want %s", code, edge.code)
			}
			if edge.code != "" {
				if !bytes.Equal(out, testErrorResponse(t, edge.code)) {
					t.Fatal("nonclosed error")
				}
			} else {
				v, ok := parseObject(out)
				if !ok {
					t.Fatal("invalid success")
				}
				expectReason(t, v["selector"], "selector_span_invalid")
				expectReason(t, v["header"], "selector_unavailable")
			}
		})
	}
	t.Run("framed_request_1500000", func(t *testing.T) {
		raw := mustJSON(t, valid)
		padded := append([]byte{'{'}, bytes.Repeat([]byte{' '}, MaxRequestBytes-len(raw))...)
		padded = append(padded, raw[1:]...)
		if len(padded) != 1500000 {
			t.Fatal("wrong exact bound")
		}
		var out bytes.Buffer
		if Serve(bytes.NewReader(frame(padded)), &out) != 0 {
			t.Fatal("exact request cap rejected")
		}
		if !bytes.Equal(readTestFrame(t, &out), []byte(Hello)) {
			t.Fatal("hello changed")
		}
		want, code := Evaluate(raw)
		if code != "" || !bytes.Equal(readTestFrame(t, &out), want) || out.Len() != 0 {
			t.Fatal("padding changed response")
		}
	})
}
