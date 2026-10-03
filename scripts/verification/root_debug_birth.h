/* Experimental Source proposal; standalone Windows x64 C11 EXE only. */
#ifndef ROOT_DEBUG_BIRTH_H
#define ROOT_DEBUG_BIRTH_H
#include <stdint.h>
#include <stddef.h>
#define RDBC_MAGIC 0x31424452u
#define RDBC_VERSION 1u
#define RDBC_PATH_CAP 1024u
#define RDBC_PROCESS_CAP 2u
#define RDBC_THREAD_CAP 128u
#define RDBC_EVENT_CAP 512u
#define RDBC_NODE_BYTE_CAP (128u * 1024u * 1024u)
#define RDBC_FIXTURE_BYTE_CAP 8192u
#define RDBC_RUN_MS 5000u
#define RDBC_CLEANUP_MS 3000u
#define RDBC_OUTPUT_BYTE_CAP 196608u

/* Exact native little-endian file, no raw pointers/handles.
 * Root freezes all private parent directories and independently reviews both
 * synthetic scripts before supplying their measured SHA256 and paths.
 * Reserved words must be zero. Paths are bounded local absolute UTF-16. */
typedef struct RDBC_ARGS {
    uint32_t magic, version, size_bytes, reserved0;
    uint64_t generation;
    uint32_t reserved1[2];
    uint16_t node_path[RDBC_PATH_CAP];
    uint16_t parent_fixture[RDBC_PATH_CAP];
    uint16_t child_fixture[RDBC_PATH_CAP];
    uint16_t working_directory[RDBC_PATH_CAP];
    uint8_t node_sha256[32], parent_sha256[32], child_sha256[32];
    uint32_t reserved2[8];
} RDBC_ARGS;

typedef struct RDBC_EVENT {
    uint32_t sequence, code, pid, tid;
    uint32_t disposition, continued, detail, first_chance;
    uint64_t elapsed_ms;
} RDBC_EVENT;
typedef struct RDBC_CANDIDATE {
    uint32_t pid, initial_tid, birth_event_sequence, startup_breakpoint_seen;
    uint32_t exit_seen, exit_continued, exit_event_code, signaled;
    uint32_t process_exit_code, image_matches_pin;
    uint64_t birth_filetime;
    uint16_t image[RDBC_PATH_CAP];
} RDBC_CANDIDATE;

enum RDBC_STAGE {
    RDBC_ARGUMENTS = 1, RDBC_PIN_FILES, RDBC_JOB, RDBC_ATTRIBUTES,
    RDBC_CREATE, RDBC_DEBUG_KILL, RDBC_WAIT, RDBC_STAGE_EVENT, RDBC_DUPLICATE,
    RDBC_BIRTH, RDBC_RESUME, RDBC_CONTINUE, RDBC_DEADLINE, RDBC_TERMINATE,
    RDBC_TERMINAL, RDBC_CLOSE, RDBC_HEAP, RDBC_RESULT
};
_Static_assert(sizeof(RDBC_ARGS) == 8352, "RDBC_ARGS layout");
_Static_assert(sizeof(RDBC_EVENT) == 40, "RDBC_EVENT layout");
_Static_assert(sizeof(RDBC_CANDIDATE) == 2096, "candidate layout");
_Static_assert(offsetof(RDBC_ARGS, node_path) == 32, "Args node offset");
_Static_assert(offsetof(RDBC_ARGS, node_sha256) == 8224, "Args hash offset");
#endif
