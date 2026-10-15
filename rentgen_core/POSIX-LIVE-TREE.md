# Internal POSIX live-tree reader

`_posix_live_tree.PosixLiveTree(source_root, state_root, limits=PosixLiveLimits(),
authorize_read=...)` is an explicit internal adapter for the future capture owner.
It supplies `configure(configuration)`, `inventory(configuration, exclusions)` and
`read(item)` only. There is no current capture-factory dispatch, candidate write,
scanner process, publication, identity or public capability change. Windows source
code, native handles and its read/delete sharing contract are unchanged.

## Data and namespace contract

The adapter has separate frozen `PosixStamp` and `PosixTreeItem` values. Stamps
contain device/inode, POSIX mode/owner/link/size/time/flags, with natural `directory`
and `size` data used by the narrow capture loops. They have no Win32 attributes or
native-handle facade. Exact items are retained by their producing owner; equal
items forged or returned by another tree are not read capabilities.

Source/state absolute ancestors are opened no-follow through the existing POSIX
`Directory` primitives. Source and layer descendants must remain on the source
device and an admitted local filesystem. Known duplicate directory identities,
state-root aliases and known state-ancestor aliases outside their expected path
are refused. State may live on another admitted local
filesystem because it is excluded, not read as source content. Linux same-device
mount semantics still need actual runtime qualification; no universal mount or
network-filesystem support is implied. In particular, a bind mount of an arbitrary
state descendant cannot generally be identified from known device/inode chains
alone; no universal same-device bind-mount exclusion is claimed.

Live project directories use `private=False`: ordinary readable 0755/0644 projects
and readable ACLs are allowed by the OS. The private retained-state UID/0700/0600
and extended-ACL refusal policy is not imposed on live source trees. Links,
multiple-link files, devices, sockets, FIFOs and nonregular leaves are refused.

`configure` accepts one exact versioned `SourceConfiguration`. Containment and
layer overlap checks include held descriptor-chain identities. A source root
inside state, a layer inside state, or overlapping/aliased layers is invalid.
Configured layer components and computed exclusion components must occur with
their exact spelling in descriptor enumeration: case/Unicode aliases are refused
instead of silently missing the state exclusion. Exclusions returned by configure
must be passed unchanged to inventory. State linkage is rechecked throughout.

The first inventory includes layer roots and empty directories, validates portable
names and NFC/casefold collision rules before exclusions, sorts by layer ordinal
and UTF-8 bytes, and pins all selected directories and regular leaves. It records
directory name sets and POSIX stamps, then rechecks them and every held leaf before
return. Stamps start at first inventory, so future capture may create excluded
state staging between configure and that inventory. Later inventories refuse
observed membership, stamp or linkage changes; they do not repin replacement files.

## Copied reads and caller responsibility

`with tree.read(item) as chunks:` copies the entire bounded file from its already
held descriptor with one bounded `os.pread(fd, size + 1, 0)` per pass, and verifies descriptor plus named
entry stamps before/after the copy. It yields one immutable `bytes` chunk. There
is no original pathname content reopen and no list-of-chunks/join inside the
adapter. Python buffered-stream replay cannot replace the second content read;
short native reads fail rather than being silently retried through a path. Name
attachment and stamps are checked again before iterator disclosure
and read-context exit. Returned bytes are independent of later source mutations.

The caller still owns two content passes, comparison of their bytes/hashes and a
final inventory. The current capture `_inventory`/`_pass` pure data loops are used
in tests without changing their Windows dispatch. No complete POSIX capture or
candidate-publication claim follows from that source-only compatibility check.

POSIX descriptors are not writer/delete leases or an atomic filesystem snapshot.
Only observed changes are refused; temporary changes between observations may be
missed. `temporal_atomicity=not_proven` remains the future capture contract. Hostile
same-UID/root processes and arbitrary trusted Python code are outside this local
boundary.

## Bounded synchronous lifetime

Typed limits are required. Configurable maxima preserve 64 MiB per file, 1 GiB
total inventory file bytes and 100,000 inventory items. Relative source depth is
at most 256 components (default 128). Every directory/leaf is held until tree exit;
the default limit is 1024 retained descriptors, configurable to 65,536. Accounting
includes both independent absolute ancestor chains, child/leaf descriptors and
one transient `scandir` duplicate, and refuses before opening another descriptor.
This is the adapter's retained FD count, not unrelated caller/process descriptors.

Defaults permit three inventory calls and two reads per file, with at most 2 GiB
cumulative copied content. Attempts are charged before copying; a failed owner
operation closes the tree. At most one read context owns an image at a time, up to
`max_file_bytes + 1` bytes during grow detection. Buffered streams, metadata/Python
objects, allocator overhead and caller-retained results are additional memory;
these limits are not a hard process RSS cap. Callers must budget returned copies
and concurrent owners separately.

One entry PID/thread owns the explicit non-generator tree and read contexts.
Foreign/forked/reentrant operations and exits refuse before changing ownership or
advancing private generator finalizers. An idle abandoned read is closed by its
owner's outer tree exit; executing/reentrant read exit cannot tear down an active
operation. Copied image references are cleared on close. Cleanup receives the body
exception triple, preserving its original denial/cause; failed success cleanup
cannot become success. Explicit owner context exit is mandatory; there is no TTL
reaper or automatic background cleanup.

The trusted callback and a monotonic deadline are checked before/after entry,
configuration, inventory, copy and iterator disclosure, and on successful exit.
The deadline starts before filesystem entry and is at most 30 seconds. It is
cooperative: C reads, filesystem calls and a blocking callback cannot be forcibly
interrupted mid-call. Successful exit also rechecks the observed inventory.

## Verification scope

Tests use real owned POSIX directories, held streams, actual mutations and process
fork/thread boundaries, plus the existing capture data loops. No POSIX-as-Windows
handles, fake OS platform, live publication or scanner lifecycle is used. Local
macOS results are source evidence only. Actual Linux and Windows regression were
separately qualified for the bounded [PR #102 capture integration](../docs/product/evidence/development-ci-366db69-20261016.json),
including installed CLI. Subsequent source/bytes and the future offline installed
SDK need their own acceptance; larger device/workload claims remain unqualified.
