# New Linux project state bootstrap

`ProjectRegistry.register` opts in only on actual Linux. It exclusively creates a
new private `0700` state root through a held, no-follow ancestor chain. Existing
roots, aliases, unsafe permissions and inherited extended/default ACLs are denied;
there is no repair, attach or migration. An overly restrictive umask may cause a
fail-closed creation failure; the process-wide umask is never changed.
Before creation, each ancestor must be owned by root or the effective UID;
group/other-writable namespaces require the sticky bit. Other parent namespaces
are denied without changes. On Linux, POSIX ACL write grants obey the group mask
and do not bypass sticky child ownership rules.

The ordinary state schema/bootstrap transaction first runs in owned in-memory
SQLite. After commit, a 16 MiB page-count bound precedes serialization. Complete
bytes are exclusively written through an owned `0600` descriptor, fsynced and
read back. Only then does the ordinary SQLite pathname VFS reopen the database for
WAL initialization, with private directory/file identity and ACL checks before
and after. This short reopen is **not** descriptor-bound SQLite or isolation from
a hostile same-UID process. Root/DB descriptors remain held through registry
commit. The complete state is checked before catalog commit; a failure before
that commit rolls back the catalog. Scope exit verifies the held root, database,
private permissions and namespace again before closing descriptors. An observed
change refuses success; an existing operation failure keeps its original cause.
An exit verification or close failure after catalog commit cannot roll back that
already committed registration. The private primitive also permits an empty root;
production registration separately requires the completed database before commit.

Failure cleanup only closes owned descriptors. It never removes files or roots:
an unregistered orphan, including a partially written DB, may remain. Foreign
replacements and existing unsafe objects are neither repaired nor deleted.
Orphan recovery/GC is not provided. Existing Windows/default database creation
stays on its original path. This prerequisite does not admit Linux capture or
publication, and does not widen any public capability.

`test_private_state_bootstrap.py` separates real POSIX primitive controls from
actual-Linux registry/ACL tests; macOS primitive success is not Linux acceptance.
