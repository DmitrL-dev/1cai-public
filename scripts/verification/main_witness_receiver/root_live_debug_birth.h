/* Root-private SOURCE proposal, Windows x64 C11. Synthetic pinned Node only.
 * Caller-owned, aligned zeroed storage; no constructor, DllMain effects or
 * destruction API. Root keeps storage/DLL/worker/requests/outputs until worker
 * return AND join AND known terminal cleanup. Unknown retains all authority
 * until the disposable Root host exits; thread-exit kill is NOT cleanup proof.
 */
#ifndef ROOT_LIVE_DEBUG_BIRTH_SYNTHETIC_H
#define ROOT_LIVE_DEBUG_BIRTH_SYNTHETIC_H
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#define RLD_EXPORT __declspec(dllexport)
#define RLD_VERSION 1u
#define RLD_MAGIC 0x314c4452u
#define RLD_CONTEXT_BYTES 65536u
#define RLD_PATH_CAP 1024u
#define RLD_PROCESS_CAP 2u
#define RLD_THREAD_CAP 128u
#define RLD_EVENT_CAP 512u
#define RLD_QUERY_CAP 16u
#define RLD_STOP_SLOT 16u
#define RLD_COMMAND_SLOTS 17u
#define RLD_NODE_BYTE_CAP (128u*1024u*1024u)
#define RLD_FIXTURE_BYTE_CAP 8192u
#define RLD_MAX_RUN_MS 5000u
#define RLD_MAX_CLEANUP_MS 3000u
#define RLD_WAIT_SLICE_MS 50u
#define RLD_STOP_EXIT_CODE 125u
#define RLD_SLOT_STATUS UINT32_MAX
#define RLD_ABI_WORDS 12u
typedef struct RLD_STORAGE { uint64_t opaque[RLD_CONTEXT_BYTES/8u]; } RLD_STORAGE;
typedef struct RLD_CALL_STATE {
    volatile LONG entered, done;
    uint32_t ok, error;
} RLD_CALL_STATE;
typedef struct RLD_CLOCK_OUT { RLD_CALL_STATE call; uint64_t tick_ms; } RLD_CLOCK_OUT;
typedef struct RLD_ARGS {
    uint32_t magic, version, size_bytes, reserved0;
    uint64_t generation, session_cookie;
    uint64_t run_until_tick_ms, closure_until_tick_ms;
    uint16_t node_path[RLD_PATH_CAP], parent_fixture[RLD_PATH_CAP];
    uint16_t child_fixture[RLD_PATH_CAP], working_directory[RLD_PATH_CAP];
    uint8_t node_sha256[32], parent_sha256[32], child_sha256[32];
    uint32_t reserved1[8];
} RLD_ARGS;
typedef struct RLD_EVENT {
    uint32_t sequence, code, pid, tid;
    uint32_t disposition, continued, detail, first_chance;
    uint64_t elapsed_ms;
} RLD_EVENT;
/* No HANDLE, pointer, PID or arbitrary reopen/adoption field in QUERY output.
 * generation/cookie/slot are correlation under the original private storage
 * binding; neither this structure nor its JSON copy is kernel authority.
 */
typedef struct RLD_SNAPSHOT {
    uint64_t generation, session_cookie;
    uint32_t phase, primary_stage, primary_error, cleanup_stage, cleanup_error;
    uint32_t candidate_count, event_count, exit_count, owned_handles_remaining;
    uint32_t system_handles_pending, job_empty, cleanup_complete;
    uint32_t worker_returned, stop_requested, query_live, slot;
    uint64_t birth_filetime;
    uint32_t birth_event_sequence, image_matches_pin, job_member, signaled;
    uint32_t grants; /* ALWAYS zero: Editor/OwnerIPC/Core/model/ready/etc. */
    uint32_t reserved[3];
} RLD_SNAPSHOT;
enum RLD_PHASE {
    RLD_REGISTERED=1, RLD_STARTING=2, RLD_RUNNING=3, RLD_STOPPING=4,
    RLD_CLOSED=5, RLD_UNKNOWN=6
};
enum RLD_COMMAND_OP { RLD_QUERY=1, RLD_STOP=2 };
typedef struct RLD_COMMAND_ARGS {
    uint32_t op, index, slot, reserved;
    uint64_t generation, session_cookie;
} RLD_COMMAND_ARGS;
typedef struct RLD_COMMAND_OUT {
    RLD_CALL_STATE call;
    volatile LONG submit_done, accepted;
    uint64_t command_index;
    RLD_SNAPSHOT snapshot;
} RLD_COMMAND_OUT;
/* Terminal-only diagnostic ledger may contain PID join keys. NEVER authority. */
typedef struct RLD_RUN_OUT {
    RLD_CALL_STATE call;
    RLD_SNAPSHOT snapshot;
    uint32_t ledger_count, reserved;
    RLD_EVENT ledger[RLD_EVENT_CAP];
} RLD_RUN_OUT;
enum RLD_STAGE {
    RLD_ARGUMENTS=1, RLD_PIN_FILES, RLD_JOB, RLD_ATTRIBUTES,
    RLD_CREATE, RLD_DEBUG_KILL, RLD_WAIT, RLD_STAGE_EVENT, RLD_DUPLICATE,
    RLD_BIRTH, RLD_RESUME, RLD_CONTINUE, RLD_DEADLINE, RLD_TERMINATE,
    RLD_TERMINAL, RLD_CLOSE, RLD_HEAP, RLD_RESULT, RLD_REVOKED
};
_Static_assert(sizeof(void*)==8 && sizeof(WCHAR)==2, "Windows x64");
_Static_assert(sizeof(RLD_STORAGE)==65536 && _Alignof(RLD_STORAGE)==8, "storage ABI");
_Static_assert(sizeof(RLD_CALL_STATE)==16 && sizeof(RLD_CLOCK_OUT)==24, "call ABI");
_Static_assert(sizeof(RLD_ARGS)==8368 && offsetof(RLD_ARGS,node_path)==48, "args ABI");
_Static_assert(offsetof(RLD_ARGS,node_sha256)==8240, "args hashes");
_Static_assert(sizeof(RLD_EVENT)==40, "event ABI");
_Static_assert(sizeof(RLD_SNAPSHOT)==120 && offsetof(RLD_SNAPSHOT,birth_filetime)==80, "snapshot ABI");
_Static_assert(sizeof(RLD_COMMAND_ARGS)==32 && offsetof(RLD_COMMAND_ARGS,generation)==16, "command args ABI");
_Static_assert(sizeof(RLD_COMMAND_OUT)==152 && offsetof(RLD_COMMAND_OUT,snapshot)==32, "command output ABI");
_Static_assert(sizeof(RLD_RUN_OUT)==20624 && offsetof(RLD_RUN_OUT,ledger)==144, "run output ABI");
/* Data ABI words:
 * 1,8,65536,8,8368,24,16,32,152,120,20624,40.
 * Every call/output is fresh zeroed single-use. rld_init reserves one context
 * per DLL lifetime; no reuse/reset, even after CLOSED. Args are copied at init.
 * Root obtains rld_clock once and fixes actual absolute run/closure ends;
 * init refuses expired/run>5000/cleanup>3000; no API renews either deadline.
 * rld_run is invoked once by the dedicated debug worker and may block.
 * rld_submit only copies/registers a bounded command: submit_done!=completion.
 * QUERY slots0/1 require both original birth slots alive; STATUS yields facts
 * only. QUERY indices0..15, reserved STOP index16/slotSTATUS, each once.
 * accepted QUERY may finish as cleanup-only if revoke/expiry crossed issuance.
 * STOP done=1 only after worker cleanup result; all command storage remains
 * retained through run return/join. CANCEL/kill/worker exit are not terminal.
 */
RLD_EXPORT void WINAPI rld_abi(uint32_t out[RLD_ABI_WORDS]);
RLD_EXPORT void WINAPI rld_clock(RLD_CLOCK_OUT *out);
RLD_EXPORT void WINAPI rld_init(RLD_STORAGE *storage, const RLD_ARGS *args, RLD_CALL_STATE *out);
RLD_EXPORT void WINAPI rld_run(RLD_STORAGE *storage, RLD_RUN_OUT *out);
RLD_EXPORT void WINAPI rld_submit(RLD_STORAGE *storage, const RLD_COMMAND_ARGS *args, RLD_COMMAND_OUT *out);
#endif
