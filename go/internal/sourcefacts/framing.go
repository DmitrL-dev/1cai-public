package sourcefacts

import (
	"encoding/binary"
	"io"
)

const Hello = `{"protocol":"source_fact_scan_v1","kind":"hello","ownership":"linux_parent_death_v1"}`

// Serve is the one-shot stdio exchange, called only after native ownership setup
// by the executable. It requires EOF before evaluation or any response. A caller
// must also enforce an external deadline: an open input is never valid EOF.
func Serve(in io.Reader, out io.Writer) (status int) {
	helloWritten, responseStarted := false, false
	defer func() {
		if recover() != nil {
			status = 2
			if helloWritten && !responseStarted {
				_ = writeFrame(out, ErrorResponse(InternalError))
			}
		}
	}()
	if err := writeFrame(out, []byte(Hello)); err != nil {
		return 2
	}
	helloWritten = true
	raw, code := readRequest(in)
	var result []byte
	if code != "" {
		result = ErrorResponse(code)
	} else {
		result, code = Evaluate(raw)
	}
	responseStarted = true
	if err := writeFrame(out, result); err != nil {
		return 2
	}
	if code != "" {
		return 2
	}
	return 0
}

func readRequest(in io.Reader) ([]byte, Code) {
	var prefix [4]byte
	if _, err := io.ReadFull(in, prefix[:]); err != nil {
		return nil, readCode(err)
	}
	n := binary.LittleEndian.Uint32(prefix[:])
	if n > MaxRequestBytes {
		return nil, InputLimit
	}
	if n == 0 {
		return nil, InvalidRequest
	}
	raw := make([]byte, int(n))
	if _, err := io.ReadFull(in, raw); err != nil {
		return nil, readCode(err)
	}
	// Even one trailing byte prevents success; do not read an unbounded tail.
	var tail [1]byte
	if n, err := io.ReadFull(in, tail[:]); n != 0 || err != io.EOF {
		if n != 0 {
			return nil, InvalidRequest
		}
		return nil, readCode(err)
	}
	return raw, ""
}

func readCode(err error) Code {
	if err == io.EOF || err == io.ErrUnexpectedEOF {
		return InvalidRequest
	}
	return IOError
}

func writeFrame(out io.Writer, payload []byte) error {
	if len(payload) > MaxResponseBytes {
		return io.ErrShortWrite
	}
	var prefix [4]byte
	binary.LittleEndian.PutUint32(prefix[:], uint32(len(payload)))
	if err := writeAll(out, prefix[:]); err != nil {
		return err
	}
	return writeAll(out, payload)
}

func writeAll(out io.Writer, data []byte) error {
	for len(data) != 0 {
		n, err := out.Write(data)
		if n < 0 || n > len(data) {
			return io.ErrShortWrite
		}
		if err != nil {
			return err
		}
		if n == 0 {
			return io.ErrShortWrite
		}
		data = data[n:]
	}
	return nil
}
