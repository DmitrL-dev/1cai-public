# Editor native compilation

Use companion 0.1.5 development with core dev8. Existing accepted 0.1.4
artifacts remain unchanged. Native VS Code controls, no webview or dependencies.

1. Validate the exact selected draft revision, retrieve its stored proposal, and
   save an operation UUID and proposal in the profile before invoking the core.
2. Use a separate bounded process runner for native compilation. The core checks
   the executable hash and retained snapshot. Cancellation kills the owned tree;
   abrupt editor termination has no process-death guarantee.
3. Provide a draft context command and result lookup by persisted UUID. Reopening
   results never initiates compilation. Incomplete is not a process-liveness claim.
4. Test wrong revisions, foreign results, lost responses, cancelled selection,
   duplicate starts, and read-only recovery. Exercise the service against installed
   dev8 and real 1C using the synthetic fixture, then build the development VSIX.
5. Keep dev7 repair support unchanged. Document dev8 setup and development status;
   verify the published companion separately from the changing development build.
