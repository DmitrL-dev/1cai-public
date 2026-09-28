# Registered source Git trust

## Evidence and decision

The actual f7 push/PR runs accepted a separate LocalService Git diagnostic.
Both hosted runners accepted the ordinary inherited environment, refused a
foreign-owned source under empty global/NOSYSTEM isolation, accepted only the
exact selected exception, refused the other source and refused the next child
without that exception. The public record is
`docs/product/evidence/native-git-scm-diagnostic-ci-20260928.json`.

Choose an explicit service opt-in for the already authorized registered source.
Do not infer a portable ownership boundary from the hosted runner's defaults.
Git's protected command configuration supports an empty safe.directory value
followed by one exact absolute root. It does not require writing user/system
configuration or changing a repository owner.

## Contract

- Add optional `trust_registered_source: bool = false` to Git service schema 2/3.
  JSON must contain an actual boolean. Schema 1 still rejects this field.
  Existing max_cycles, modes, scanner rules, dry-run and authorization remain.
- The service config cannot supply a trust root, wildcard, Git command or
  executable. GitAuditWorker derives the canonical root from the authorized
  project context, after verifying the existing Observer/profile binding.
- A frozen `GitRepositoryTrust(repository: Path)` records one absolute canonical
  existing directory. Reject relative paths, control characters, wildcard or
  interpolation syntax and noncanonical spelling. It is a Git exception;
  project authorization and filesystem ACL/identity obligations remain separate.
- `observe_git(..., trust=None)` and `require_ancestor(..., trust=None)` are
  additive APIs. BSL analyzer, Observer, GitWatcher and reporting composition
  accept one optional `git_trust` object and forward that same object.
- Every trusted child validates that its canonical requested root equals the
  frozen root before launching. No trust for a parent, nested repository or
  another registered project is implied. A mismatch raises `GIT_TRUST_CONTEXT`.
- Trusted command prefix:

  ```text
  git --no-pager -c core.fsmonitor=false
      -c safe.directory= -c safe.directory=<exact registered root>
      -C <the same exact root> <existing read-only command>
  ```

- Omitted opt-in adds no safe.directory entries. Existing machine/user config
  remains observable in that mode; no ownership-isolation claim is made for it.
- Remove inherited `GIT_*` environment keys case-insensitively in all three
  direct launches. Apply fixed OPTIONAL_LOCKS=0, TERMINAL_PROMPT=0 and
  NO_LAZY_FETCH=1. Set NO_REPLACE_OBJECTS=1 so exact commit analysis cannot read
  replacement objects under the original commit identity. Preserve ordinary
  non-Git environment entries such as PATH.
- Never change source/ref/index/config, owners, global Git settings or deploy a
  service as part of selecting this design. Keep default opt-in false.

## Complete call coverage

The existing inventory binds six source files and identifies three direct
subprocess launches and eleven callers. Propagation includes:

1. Git observation and ancestry helpers.
2. BSL before/after observation, ls-tree and exact commit blob reads.
3. Watcher initial/latest observation and ancestry.
4. Reporting initial/post-capture observation and ancestry.
5. Observer before/after source snapshot verification, including the verification
   reached while persisting typed evidence.

GitAuditWorker must give the same object to Observer, BslGitAnalyzer, GitWatcher
and the reporting adapter. Existing default calls and injected test seams still
receive their old positional arguments when no policy is selected.

## Verification and delivery

Use test-first cases for typed config, exact/reset argv, environment casing,
foreign/parent/nested roots rejected before any process, frozen canonical root
and unchanged default behavior. Use real current-user Git for no config/ref/index
mutation and for replacement refs with a different tree. A fake BSL adapter may
prove plumbing/blob identity; it does not establish native BSL acceptance.

Exercise the complete service composition with one explicit flag: real Git,
existing authorized project/Observer state, snapshot evidence, findings, outbox,
owner report, ancestry and revocation. Spy only on argv/environment to verify
the selected permission reaches every actual child. Do not replace Git results.

The following gates remain required for the full product result:

- Bounded production stdout while reading, timeout termination and reap. The
  existing post-read module limit alone is not the complete capture boundary.
- Installed stock schema 3 GitAuditWorker in actual LocalService with real pinned
  BSL-LS, exact commit capture/history, STOP and explicit recovery.
- Accepted source/main CI and a subsequent Core component version after dev15,
  with immutable release assets and a detailed public announcement/readback.

The measured f7 diagnostic remains a historical fact; this design does not
retroactively select production trust or qualify later runtime bytes. Root-only
review is explicit under the user's prohibition on subagents. No deployment.

## Primary references

- https://git-scm.com/docs/git-config/2.55.0#Documentation/git-config.txt-safedirectory
- https://git-scm.com/docs/git/2.55.0#Documentation/git.txt-GIT_NO_REPLACE_OBJECTS


## Owned verifier and failure diagnostics follow-up

The verifier reads the LS-bound profile through its actual fixture owner,
authorized for admin/analysis; original LS binding stays exact. Production
Observer principal policy stays unchanged. Failure metadata is limited to fixed
stage/type/known reason, public service name and PID; optional Windows event at
most512 characters cannot change result/cleanup. Raw bounded reads require SCM
PID binding. See docs/product/service-failure-events.md. Actual LS event and full
stock source qualification remain pending; original failed5b attempts unchanged.
