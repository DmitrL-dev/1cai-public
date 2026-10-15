//go:build linux && amd64

package scanner

import (
	"crypto/sha256"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"unicode/utf8"
	"unsafe"

	"1cai/bsl-scan/internal/extractor"
	"1cai/bsl-scan/pkg/types"
)

type OwnedLimits struct {
	MaxFile, MaxBytes              int64
	MaxFiles, MaxEntries, MaxDepth int
}

func OwnedPrivate(fd int, directory bool) error {
	var info syscall.Stat_t
	if syscall.Fstat(fd, &info) != nil || info.Uid != uint32(os.Geteuid()) || info.Mode&0077 != 0 {
		return fmt.Errorf("private")
	}
	kind := uint32(syscall.S_IFREG)
	if directory {
		kind = syscall.S_IFDIR
	}
	if info.Mode&syscall.S_IFMT != kind || (!directory && info.Nlink != 1) {
		return fmt.Errorf("type")
	}
	attributes := []string{"system.posix_acl_access"}
	if directory {
		attributes = append(attributes, "system.posix_acl_default")
	}
	for _, name := range attributes {
		key, _ := syscall.BytePtrFromString(name)
		n, _, code := syscall.RawSyscall6(syscall.SYS_FGETXATTR, uintptr(fd), uintptr(unsafe.Pointer(key)), 0, 0, 0, 0)
		if code != syscall.ENODATA && code != syscall.EOPNOTSUPP && (code != 0 || n != 0) {
			return fmt.Errorf("acl")
		}
	}
	return nil
}

// Only private materialized BSL inputs, held-descriptor reads, bounded metadata
// and source accumulation. Extractor/JSON object overhead is not a hard RSS cap.
func ScanCallGraphOwned(root int, limits OwnedLimits) ([]types.BslFunction, []FileCoverage, error) {
	functions := make([]types.BslFunction, 0)
	coverage := make([]FileCoverage, 0)
	count := 0
	files := 0
	var total int64
	var walk func(int, string, int) error
	walk = func(fd int, prefix string, depth int) error {
		stream := os.NewFile(uintptr(fd), "owned-input")
		if stream == nil {
			return fmt.Errorf("directory")
		}
		defer stream.Close()
		if depth > limits.MaxDepth || OwnedPrivate(fd, true) != nil {
			return fmt.Errorf("directory")
		}
		var before syscall.Stat_t
		if syscall.Fstat(fd, &before) != nil {
			return fmt.Errorf("stat")
		}
		names := make([]string, 0)
		for {
			part, err := stream.Readdirnames(1)
			if len(part) > 0 {
				count++
				if count > limits.MaxEntries {
					return fmt.Errorf("entry_limit")
				}
				names = append(names, part[0])
			}
			if err == io.EOF {
				break
			}
			if err != nil {
				return err
			}
		}
		sort.Strings(names)
		for _, name := range names {
			path := prefix + name
			if !utf8.ValidString(path) || len(path) > 4096 {
				return fmt.Errorf("path")
			}
			child, err := syscall.Openat(fd, name, syscall.O_RDONLY|syscall.O_NONBLOCK|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
			if err != nil {
				return err
			}
			var info syscall.Stat_t
			if err := syscall.Fstat(child, &info); err != nil {
				syscall.Close(child)
				return err
			}
			if info.Mode&syscall.S_IFMT == syscall.S_IFDIR {
				if info.Dev != before.Dev {
					syscall.Close(child)
					return fmt.Errorf("device")
				}
				if err := walk(child, path+"/", depth+1); err != nil {
					return err
				}
			} else {
				if OwnedPrivate(child, false) != nil || info.Size < 0 || info.Size > limits.MaxFile || info.Dev != before.Dev {
					syscall.Close(child)
					return fmt.Errorf("input")
				}
				total += info.Size
				files++
				if total > limits.MaxBytes || files > limits.MaxFiles {
					syscall.Close(child)
					return fmt.Errorf("source_limit")
				}
				if !bslExtensions[strings.ToLower(filepath.Ext(name))] {
					if err := syscall.Close(child); err != nil {
						return err
					}
				} else {
					raw, err := ownedRead(child, info)
					if err != nil {
						return err
					}
					if !utf8.Valid(raw) {
						return fmt.Errorf("encoding")
					}
					code := strings.TrimPrefix(string(raw), "\ufeff")
					parts := strings.Split(path, "/")
					module := moduleNameFromPath(path, "")
					if len(parts) > 1 {
						module = moduleNameFromPath(path, parts[0])
					}
					found := extractor.ExtractCallGraph(code, module)
					for i := range found {
						if found[i].EndLine < found[i].Line {
							return fmt.Errorf("span")
						}
						found[i].SourcePath = path
					}
					functions = append(functions, found...)
					coverage = append(coverage, FileCoverage{SourcePath: path, RawSHA256: fmt.Sprintf("%x", sha256.Sum256(raw)), Status: "parsed", RoutineCount: len(found)})
				}
			}
			var current syscall.Stat_t
			key, _ := syscall.BytePtrFromString(name)
			_, _, failure := syscall.RawSyscall6(syscall.SYS_NEWFSTATAT, uintptr(fd), uintptr(unsafe.Pointer(key)), uintptr(unsafe.Pointer(&current)), 0x100, 0, 0)
			if failure != 0 || !ownedSame(current, info) {
				return fmt.Errorf("namespace")
			}
		}
		var after syscall.Stat_t
		if syscall.Fstat(fd, &after) != nil || !ownedSame(after, before) {
			return fmt.Errorf("directory_changed")
		}
		return nil
	}
	if err := walk(root, "", 0); err != nil {
		return nil, nil, err
	}
	return functions, coverage, nil
}

func ownedRead(fd int, before syscall.Stat_t) ([]byte, error) {
	stream := os.NewFile(uintptr(fd), "owned-source")
	if stream == nil {
		syscall.Close(fd)
		return nil, fmt.Errorf("file")
	}
	defer stream.Close()
	// Allocate exactly the observed bounded image plus one grow-detection byte.
	raw := make([]byte, before.Size+1)
	n, err := io.ReadFull(stream, raw)
	if err != io.EOF && err != io.ErrUnexpectedEOF {
		return nil, fmt.Errorf("size")
	}
	var after syscall.Stat_t
	if int64(n) != before.Size || syscall.Fstat(fd, &after) != nil || !ownedSame(after, before) {
		return nil, fmt.Errorf("changed")
	}
	return raw[:n], nil
}

func ownedSame(a, b syscall.Stat_t) bool {
	return a.Dev == b.Dev && a.Ino == b.Ino && a.Mode == b.Mode && a.Nlink == b.Nlink && a.Uid == b.Uid && a.Gid == b.Gid && a.Size == b.Size && a.Mtim == b.Mtim && a.Ctim == b.Ctim
}
