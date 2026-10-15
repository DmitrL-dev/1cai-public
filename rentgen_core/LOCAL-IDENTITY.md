# Trusted local identity profile lifetime

The Linux local CLI/stdio identity adapter accepts a separate private profile,
not a protocol-supplied identity. Its canonical document remains schema 1 with
exactly `schema`, `kind`, `namespace` and `uid`; the principal remains
`linux-local:<namespace>:uid:<effective uid>`. The namespace is a UUID4 local
ownership label, not a bearer credential. Deliberately copying an otherwise
valid profile preserves the same principal. No project membership is migrated.
Windows continues to use its process-token SID adapter.

Profile reads and explicit Linux bootstrap hold a descriptor for every absolute
ancestor. Each component is opened relative to its held parent with no symlink
following; bootstrap creates missing directories through those descriptors.
Parent traversal and oversized paths are refused. Ancestor inode identities and
their directory entries are checked before and after work. Ancestors such as
the account home and system temporary directory need not be private; the final
profile directory must be owned by the effective account with mode `0700` and
no extended access or default ACL. The regular profile file must have one link,
the same owner, mode `0600`, no extended access ACL, and the existing 1024-byte
maximum. Existing permissions and ACLs are never repaired.

Reads copy at most 1025 bytes from the held file, finish short reads, and compare
exact inode metadata stamps, the named entry, parent privacy and all ancestor
bindings before interpreting and returning the canonical identity. Bootstrap
uses an exclusive private temporary file, checks the written bytes, synchronizes
the file, and publishes through Linux `renameat2(RENAME_NOREPLACE)`. It retains
the original file descriptor through final namespace synchronization and exact
byte verification. It does not reopen a potentially changed absolute pathname.
The newly and exclusively created temporary inode receives mode `0600` through
its held descriptor, including when the caller's umask removed owner bits.
This does not change an existing profile or directory; newly created directories
whose resulting permissions are not private are refused without repair.

A failed final directory synchronization leaves the complete published file in
place. Retrying bootstrap synchronizes the directory chain but still refuses an
existing final identity; it never replaces the winning namespace. Temporary
cleanup removes only the entry that still identifies this operation's held
temporary inode. A foreign collision or replacement survives. Cleanup and close
failures cannot replace an exception already raised by the operation.

These are operation-scoped observations, not filesystem leases or an atomic
snapshot of all ancestors. Malicious same-UID processes, root and modified
project databases remain outside the trusted-local boundary. This change adds
no capture, retained-session, live-apply, remote-authentication or macOS product
capability. Real Darwin descriptor/ACL tests exercise private implementation
primitives only. Actual Linux bootstrap/CLI history and scoped installed CLI
were separately qualified at [PR #102, HEAD `366db69`](../docs/product/evidence/development-ci-366db69-20261016.json).
Local tests remain distinct from CI; this does not qualify native 1C/EDT, the
future offline installed SDK or later source/bytes.
