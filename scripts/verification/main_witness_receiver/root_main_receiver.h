/* Root-private SOURCE candidate. Original RLD ABI is unchanged.
 * This extension carries data only. No HANDLE/pointer leaves native status.
 * Diagnostic PID comparisons below are join keys, never reopen/adoption input.
 * Keep both original storages, DLL, requests and outputs until actual worker
 * return AND external join AND known terminal receiver/birth/Job cleanup.
 * No execute, import or compile performed by the Source author.
 */
#ifndef ROOT_MAIN_WITNESS_RECEIVER_SOURCE_H
#define ROOT_MAIN_WITNESS_RECEIVER_SOURCE_H
#include "root_live_debug_birth.h"
#define RWR_VERSION 1u
#define RWR_MAGIC 0x31525752u
#define RWR_CONTEXT_BYTES 32768u
#define RWR_BODY_CAP 1024u
#define RWR_CHUNK_CAP 4096u
#define RWR_FRAME_CAP 2u
#define RWR_STATUS_CAP 16u
#define RWR_SID_CAP 68u
#define RWR_PIPE_ACCESS_MASK 0x0012019fu
#define RWR_ABI_WORDS 13u
typedef struct RWR_STORAGE { uint64_t opaque[RWR_CONTEXT_BYTES/8u]; } RWR_STORAGE;
typedef struct RWR_ARGS {
    uint32_t magic, version, size_bytes, reserved0;
    uint64_t generation, session_cookie, run_until_tick_ms, closure_until_tick_ms;
    uint32_t expected_slot, hello_bytes, sid_bytes, pipe_access_mask;
    uint8_t expected_current_user_sid[RWR_SID_CAP];
    char instance[33], nonce[33], run[129], generation_text[21], source_copy_pin[65];
    uint8_t reserved_bytes[3];
    uint8_t hello[RWR_BODY_CAP];
    uint32_t reserved[8];
} RWR_ARGS;
enum RWR_PHASE {
    RWR_REGISTERED=1, RWR_LISTENING=2, RWR_CONNECTED=3, RWR_HELLO=4,
    RWR_ACK=5, RWR_AUTHENTICATED=6, RWR_REVOKED=7, RWR_RETIRED=8, RWR_UNKNOWN=9
};
enum RWR_STAGE {
    RWR_ARGUMENTS=100, RWR_SECURITY, RWR_EVENT, RWR_PIPE, RWR_CONNECT,
    RWR_PEER, RWR_READ, RWR_HELLO_BYTES, RWR_WRITE, RWR_EXTRA_DATA,
    RWR_CANCEL, RWR_IO_TERMINAL, RWR_CLOSE, RWR_DEADLINE, RWR_STOPPED
};
typedef struct RWR_STATUS {
    uint64_t generation, session_cookie;
    uint32_t phase, primary_stage, primary_error, cleanup_stage, cleanup_error;
    uint32_t expected_slot, registered, listen_created, connected, peer_match;
    uint32_t hello_completed, ack_issued, ack_completed, authenticated, revoked;
    uint32_t io_pending, producer_pending, io_terminal, retired, owned_handles_remaining;
    uint32_t unknown, hello_wire_bytes, ack_wire_bytes, status_index;
    uint64_t birth_filetime;
    uint32_t birth_event_sequence, grants; /* grants is ALWAYS zero */
    uint32_t client_pid, expected_held_pid, peer_compare_attempted, peer_compare_match;
    uint32_t peer_bracket_before, peer_bracket_after;
} RWR_STATUS;
typedef struct RWR_STATUS_ARGS {
    uint32_t index, reserved;
    uint64_t generation, session_cookie;
} RWR_STATUS_ARGS;
typedef struct RWR_STATUS_OUT {
    RLD_CALL_STATE call;
    volatile LONG submit_done, accepted;
    uint64_t command_index;
    RWR_STATUS status;
} RWR_STATUS_OUT;
_Static_assert(sizeof(RWR_STORAGE)==32768 && _Alignof(RWR_STORAGE)==8,"receiver storage ABI");
_Static_assert(sizeof(RWR_ARGS)==1472 && offsetof(RWR_ARGS,hello)==416,"receiver args ABI");
_Static_assert(sizeof(RWR_STATUS)==152 && offsetof(RWR_STATUS,birth_filetime)==112,"receiver status ABI");
_Static_assert(sizeof(RWR_STATUS_ARGS)==24 && sizeof(RWR_STATUS_OUT)==184,"receiver call ABI");
/* Additive data ABI words: 1,8,32768,8,1472,24,184,152,16,1024,4096,2,16.
 * register is once, after original rld_init and before rld_run. It copies only
 * frozen data and attaches the exact original pair; it creates no native object.
 * expected_slot=0 for the positive; slot=1 is the isolated wrong-peer control.
 * SID is actual current-user binary SID; explicit duplex rights include the
 * FILE_CREATE_PIPE_INSTANCE bit required by Node GENERIC_WRITE. FIRST/max1
 * and the fresh namespace guard the original server instance while it lives.
 * Root supplies exact canonical seven-field HELLO.
 * original run/closure ends must match exactly; neither API renews deadlines.
 * status indices0..15 are fresh, single-use asynchronous observations. All
 * native receiver effects run on the original rld_run debug worker. STOP16
 * revokes both domains; cancellation is not IO terminal proof. Unknown retains
 * storage/OV/buffers/handles/context; no destruction or reset API exists.
 */
RLD_EXPORT void WINAPI rwr_abi(uint32_t out[RWR_ABI_WORDS]);
RLD_EXPORT void WINAPI rwr_register(RLD_STORAGE *original, RWR_STORAGE *receiver,
                                  const RWR_ARGS *args, RLD_CALL_STATE *out);
RLD_EXPORT void WINAPI rwr_submit_status(RLD_STORAGE *original, RWR_STORAGE *receiver,
                                       const RWR_STATUS_ARGS *args, RWR_STATUS_OUT *out);
/* Final data observation only. Root MUST first establish actual rld_run native
 * producer return AND external worker join. Native guards additionally require
 * the exact original pair, worker_returned and CLOSED/UNKNOWN final phase.
 * Original/RWR data ABI arrays and all structure layouts remain unchanged.
 * One fresh zeroed disjoint RWR_STATUS_OUT: command_index=UINT64_MAX and copied
 * status_index=UINT32_MAX distinguish this nonqueued final read. Known CLOSED
 * copies preserved raw terminal fields and returns accepted=1, call.ok=1 even
 * when preserved primary error is the expected peer rejection105/5. UNKNOWN
 * copies preserved raw fields but returns accepted=0, call.error=995; never PASS.
 * Premature/wrong-pair calls fail with ERROR_INVALID_STATE and zero status.
 * No native IO/query/close/revival/lease renewal or authority transfer occurs.
 */
RLD_EXPORT void WINAPI rwr_final_status(RLD_STORAGE *original, RWR_STORAGE *receiver,
                                      RWR_STATUS_OUT *out);
#endif
