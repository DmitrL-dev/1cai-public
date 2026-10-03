/* Root-only SOURCE proposal. Never compiled or executed by the author.
 * Standalone EXE: create/wait/continue/cleanup all run on its disposable main
 * thread. No DLL callbacks, PID adoption, Editor, Core, model or role grant.
 * Materialize the companion header as root_debug_birth.h beside this Source. */
#define _WIN32_WINNT 0x0A00
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stddef.h>
#include <wchar.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include "root_debug_birth.h"
_Static_assert(sizeof(void *) == 8, "Windows x64");
_Static_assert(sizeof(wchar_t) == 2, "UTF-16");

typedef struct SLOT { HANDLE h; uint32_t close_attempted; } SLOT;
typedef struct HELD { SLOT process, thread; } HELD;
typedef struct THREAD_KEY { DWORD pid, tid; uint32_t live; } THREAD_KEY;
typedef struct STATE {
    SLOT job, pi_process, pi_thread, event_file, node_file, parent_file, child_file;
    HELD held[RDBC_PROCESS_CAP];
    PROCESS_INFORMATION pi;                 /* registered BEFORE CreateProcess */
    STARTUPINFOEXW si;
    DEBUG_EVENT event;                      /* registered BEFORE Wait */
    LPPROC_THREAD_ATTRIBUTE_LIST attrs;
    SIZE_T attr_bytes;
    HANDLE job_list[1];                     /* lives until attribute destruction */
    uint32_t attrs_initialized, created, blocked, terminating, kill_on_exit;
    uint32_t primary_stage, primary_error, cleanup_stage, cleanup_error;
    uint32_t creator_pid, debugger_tid, count, event_count, ledger_overflow;
    uint32_t resumed, job_empty, cleanup_complete, system_handles_pending;
    uint32_t owned_handles_remaining, pins_verified, exit_count, thread_count;
    uint32_t crypto_cleanup_unknown;
    uint64_t start, run_end, cleanup_end, generation;
    wchar_t node_final[RDBC_PATH_CAP], parent_final[RDBC_PATH_CAP], child_final[RDBC_PATH_CAP];
    wchar_t command[3 * RDBC_PATH_CAP + 16], environment[2 * RDBC_PATH_CAP];
    RDBC_CANDIDATE candidates[RDBC_PROCESS_CAP];
    RDBC_EVENT events[RDBC_EVENT_CAP];
    THREAD_KEY threads[RDBC_THREAD_CAP];
} STATE;
static DWORD nz(DWORD e) { return e ? e : ERROR_GEN_FAILURE; }
static void fail(STATE *s, uint32_t stage, DWORD e) {
    if (!s->primary_stage) { s->primary_stage = stage; s->primary_error = nz(e); }
}
static void cf(STATE *s, uint32_t stage, DWORD e) {
    if (!s->cleanup_stage) { s->cleanup_stage = stage; s->cleanup_error = nz(e); }
}
static int close_slot(STATE *s, SLOT *p) {
    DWORD e;
    if (!p->h) return 1;
    if (p->close_attempted) return 0;
    p->close_attempted = 1;                 /* irreversible BEFORE CloseHandle */
    if (CloseHandle(p->h)) { p->h = NULL; return 1; }
    e = GetLastError(); cf(s, RDBC_CLOSE, e); return 0;
}
static uint32_t slots(const STATE *s) {
    uint32_t n = (s->job.h != NULL) + (s->pi_process.h != NULL) + (s->pi_thread.h != NULL) +
        (s->event_file.h != NULL) + (s->node_file.h != NULL) +
        (s->parent_file.h != NULL) + (s->child_file.h != NULL);
    for (uint32_t i = 0; i < RDBC_PROCESS_CAP; ++i)
        n += (s->held[i].process.h != NULL) + (s->held[i].thread.h != NULL);
    return n;
}
static int path_ok(const uint16_t *p) {
    size_t i, begin;
    if (!((p[0] >= 'A' && p[0] <= 'Z') || (p[0] >= 'a' && p[0] <= 'z')) ||
        p[1] != ':' || p[2] != '\\') return 0;
    for (i = 3; i < RDBC_PATH_CAP && p[i]; ++i)
        if (p[i] < 32 || p[i] == '"' || p[i] == '/' || p[i] == ':') return 0;
    if (i < 4 || i == RDBC_PATH_CAP || p[i - 1] == '\\') return 0;
    begin = 3;
    for (size_t j = 3; j <= i; ++j) {
        if (j == i || p[j] == '\\') {
            size_t n = j - begin;
            if (!n || (n == 1 && p[begin] == '.') ||
                (n == 2 && p[begin] == '.' && p[begin + 1] == '.') ||
                p[j - 1] == '.' || p[j - 1] == ' ') return 0;
            begin = j + 1;
        }
    }
    return 1;
}
static int suffix(const wchar_t *p, const wchar_t *end) {
    size_t n = wcslen(p), k = wcslen(end);
    return n >= k && _wcsicmp(p + n - k, end) == 0;
}
static int args_ok(const RDBC_ARGS *a) {
    uint32_t zero = a->reserved0 | a->reserved1[0] | a->reserved1[1];
    uint32_t hashes[3] = {0, 0, 0};
    if (a->magic != RDBC_MAGIC || a->version != RDBC_VERSION ||
        a->size_bytes != sizeof(*a) || !a->generation || zero ||
        !path_ok(a->node_path) || !path_ok(a->parent_fixture) ||
        !path_ok(a->child_fixture) || !path_ok(a->working_directory)) return 0;
    for (size_t i = 0; i < 8; ++i) zero |= a->reserved2[i];
    for (size_t i = 0; i < 32; ++i) {
        hashes[0] |= a->node_sha256[i]; hashes[1] |= a->parent_sha256[i];
        hashes[2] |= a->child_sha256[i];
    }
    return !zero && hashes[0] && hashes[1] && hashes[2] &&
        suffix((const wchar_t *)a->node_path, L"\\node.exe") &&
        suffix((const wchar_t *)a->parent_fixture, L".cjs") &&
        suffix((const wchar_t *)a->child_fixture, L".cjs") &&
        _wcsicmp((const wchar_t *)a->parent_fixture, (const wchar_t *)a->child_fixture) != 0;
}
static int fresh(STATE *s) {
    if (s->primary_stage || s->cleanup_stage) return 0;
    if (GetTickCount64() >= s->run_end) { fail(s, RDBC_DEADLINE, ERROR_TIMEOUT); return 0; }
    return 1;
}
/* No write/delete sharing. Root freezes private parents separately; file locks
 * do not establish directory stability. Cryptographic errors reject the run. */
static int pin(STATE *s, SLOT *file, const wchar_t *path, const uint8_t expected[32],
               DWORD cap, wchar_t final[RDBC_PATH_CAP]) {
    LARGE_INTEGER size;
    BCRYPT_ALG_HANDLE alg = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    uint8_t buffer[65536], digest[32];
    DWORD got = 0, n, e = 0;
    uint64_t consumed = 0;
    int ok = 0;
    NTSTATUS status;
    file->h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                          FILE_ATTRIBUTE_NORMAL, NULL);
    if (file->h == INVALID_HANDLE_VALUE) { e = GetLastError(); file->h = NULL; goto done; }
    if (!GetFileSizeEx(file->h, &size)) { e = GetLastError(); goto done; }
    if (size.QuadPart <= 0 || (uint64_t)size.QuadPart > cap) { e = ERROR_FILE_TOO_LARGE; goto done; }
    n = GetFinalPathNameByHandleW(file->h, final, RDBC_PATH_CAP,
                                 FILE_NAME_NORMALIZED | VOLUME_NAME_DOS);
    if (!n || n >= RDBC_PATH_CAP) { e = n ? ERROR_BUFFER_OVERFLOW : GetLastError(); goto done; }
    if (wcsncmp(final, L"\\\\?\\", 4) != 0 || _wcsicmp(final + 4, path) != 0) {
        e = ERROR_INVALID_NAME; goto done;
    }
    memmove(final, final + 4, (wcslen(final + 4) + 1) * sizeof(wchar_t));
    status = BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, NULL, 0);
    if (status < 0) { e = ERROR_INVALID_DATA; goto done; }
    status = BCryptCreateHash(alg, &hash, NULL, 0, NULL, 0, 0);
    if (status < 0) { e = ERROR_INVALID_DATA; goto done; }
    for (;;) {
        if (!fresh(s)) { e = ERROR_TIMEOUT; goto done; }
        if (!ReadFile(file->h, buffer, sizeof(buffer), &got, NULL)) { e = GetLastError(); goto done; }
        if (!got) break;
        consumed += got;
        if (consumed > (uint64_t)size.QuadPart) { e = ERROR_INVALID_DATA; goto done; }
        if (BCryptHashData(hash, buffer, got, 0) < 0) { e = ERROR_INVALID_DATA; goto done; }
    }
    if (consumed != (uint64_t)size.QuadPart ||
        BCryptFinishHash(hash, digest, sizeof(digest), 0) < 0 ||
        memcmp(digest, expected, sizeof(digest)) != 0) { e = ERROR_INVALID_DATA; goto done; }
    ok = 1;
done:
    if (hash && BCryptDestroyHash(hash) < 0) {
        s->crypto_cleanup_unknown = 1; cf(s, RDBC_PIN_FILES, ERROR_INVALID_DATA); ok = 0;
    }
    if (alg && BCryptCloseAlgorithmProvider(alg, 0) < 0) {
        s->crypto_cleanup_unknown = 1; cf(s, RDBC_PIN_FILES, ERROR_INVALID_DATA); ok = 0;
    }
    SecureZeroMemory(buffer, sizeof(buffer)); SecureZeroMemory(digest, sizeof(digest));
    if (!ok) fail(s, RDBC_PIN_FILES, e);
    return ok;
}
static int index_of(const STATE *s, DWORD pid) {
    for (uint32_t i = 0; i < s->count; ++i) if (s->candidates[i].pid == pid) return (int)i;
    return -1;
}
static int inventory(STATE *s, DWORD exact) {
    struct { DWORD assigned, listed; ULONG_PTR ids[RDBC_PROCESS_CAP]; } ids;
    DWORD bytes = 0;
    memset(&ids, 0, sizeof(ids));
    if (!QueryInformationJobObject(s->job.h, JobObjectBasicProcessIdList,
                                   &ids, sizeof(ids), &bytes)) {
        fail(s, RDBC_JOB, GetLastError()); return 0;
    }
    if (ids.assigned != exact || ids.listed != exact || exact > RDBC_PROCESS_CAP) {
        fail(s, RDBC_JOB, ERROR_INVALID_DATA); return 0;
    }
    for (DWORD i = 0; i < exact; ++i) {
        DWORD pid = (DWORD)ids.ids[i];
        if (!pid || ids.ids[i] != (ULONG_PTR)pid) {
            fail(s, RDBC_JOB, ERROR_INVALID_DATA); return 0;
        }
        if (index_of(s, pid) < 0 && pid != s->pi.dwProcessId) {
            fail(s, RDBC_JOB, ERROR_INVALID_DATA); return 0;
        }
        for (DWORD j = 0; j < i; ++j) if (ids.ids[j] == ids.ids[i]) {
            fail(s, RDBC_JOB, ERROR_INVALID_DATA); return 0;
        }
    }
    return 1; /* never OpenProcess/OpenThread by any returned ID */
}
static int setup(STATE *s, const RDBC_ARGS *a) {
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits, actual;
    SIZE_T needed = 0;
    DWORD bytes = 0, error, n;
    size_t used;
    const wchar_t env_prefix[] = L"NODE_OPTIONS=\0NODE_PATH=\0SystemRoot=";
    memset(&limits, 0, sizeof(limits)); memset(&actual, 0, sizeof(actual));
    s->job.h = CreateJobObjectW(NULL, NULL);
    if (!s->job.h) { fail(s, RDBC_JOB, GetLastError()); return 0; }
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS | JOB_OBJECT_LIMIT_PROCESS_MEMORY |
        JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION;
    limits.BasicLimitInformation.ActiveProcessLimit = RDBC_PROCESS_CAP;
    limits.ProcessMemoryLimit = (SIZE_T)256 * 1024 * 1024;
    if (!SetInformationJobObject(s->job.h, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        fail(s, RDBC_JOB, GetLastError()); return 0;
    }
    if (!QueryInformationJobObject(s->job.h, JobObjectExtendedLimitInformation,
                                  &actual, sizeof(actual), &bytes)) {
        fail(s, RDBC_JOB, GetLastError()); return 0;
    }
    if (actual.BasicLimitInformation.LimitFlags != limits.BasicLimitInformation.LimitFlags ||
        actual.BasicLimitInformation.ActiveProcessLimit != RDBC_PROCESS_CAP ||
        actual.ProcessMemoryLimit != limits.ProcessMemoryLimit || !inventory(s, 0)) {
        fail(s, RDBC_JOB, ERROR_INVALID_DATA); return 0;
    }
    SetLastError(ERROR_SUCCESS);
    if (InitializeProcThreadAttributeList(NULL, 1, 0, &needed) ||
        GetLastError() != ERROR_INSUFFICIENT_BUFFER || !needed || needed > 65536) {
        fail(s, RDBC_ATTRIBUTES, ERROR_INVALID_DATA); return 0;
    }
    s->attr_bytes = needed;
    s->attrs = (LPPROC_THREAD_ATTRIBUTE_LIST)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, needed);
    if (!s->attrs) { fail(s, RDBC_ATTRIBUTES, ERROR_NOT_ENOUGH_MEMORY); return 0; }
    if (!InitializeProcThreadAttributeList(s->attrs, 1, 0, &s->attr_bytes)) {
        fail(s, RDBC_ATTRIBUTES, GetLastError()); return 0;
    }
    s->attrs_initialized = 1; s->job_list[0] = s->job.h;
    if (!UpdateProcThreadAttribute(s->attrs, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST,
                                   s->job_list, sizeof(s->job_list), NULL, NULL)) {
        fail(s, RDBC_ATTRIBUTES, GetLastError()); return 0;
    }
    s->si.StartupInfo.cb = sizeof(s->si); s->si.lpAttributeList = s->attrs;
    if (swprintf(s->command, sizeof(s->command) / sizeof(s->command[0]),
                 L"\"%ls\" \"%ls\" \"%ls\"", s->node_final, s->parent_final, s->child_final) < 0) {
        fail(s, RDBC_CREATE, ERROR_BUFFER_OVERFLOW); return 0;
    }
    used = sizeof(env_prefix) / sizeof(env_prefix[0]) - 1;
    memcpy(s->environment, env_prefix, used * sizeof(wchar_t));
    n = GetWindowsDirectoryW(s->environment + used, (UINT)(2 * RDBC_PATH_CAP - used - 1));
    if (!n || n >= 2 * RDBC_PATH_CAP - used - 1) {
        fail(s, RDBC_CREATE, n ? ERROR_BUFFER_OVERFLOW : GetLastError()); return 0;
    }
    s->environment[used + n] = 0; s->environment[used + n + 1] = 0;
    if (!fresh(s)) return 0;
    if (!CreateProcessW(s->node_final, s->command, NULL, NULL, FALSE,
            DEBUG_PROCESS | CREATE_SUSPENDED | DETACHED_PROCESS |
            CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT,
            s->environment, (const wchar_t *)a->working_directory, &s->si.StartupInfo, &s->pi)) {
        fail(s, RDBC_CREATE, GetLastError()); return 0;
    }
    s->pi_process.h = s->pi.hProcess; s->pi_thread.h = s->pi.hThread; /* publish immediately */
    s->created = 1; s->system_handles_pending = 1;
    if (!DebugSetProcessKillOnExit(TRUE)) {
        error = GetLastError(); fail(s, RDBC_DEBUG_KILL, error); return 0;
    }
    s->kill_on_exit = 1;              /* default is also TRUE; never set FALSE */
    if (!s->pi_process.h || !s->pi_thread.h ||
        GetProcessId(s->pi_process.h) != s->pi.dwProcessId ||
        GetThreadId(s->pi_thread.h) != s->pi.dwThreadId) {
        fail(s, RDBC_BIRTH, ERROR_INVALID_DATA); return 0;
    }
    if (!inventory(s, 1) || !fresh(s)) return 0;
    /* Remove ONLY the explicit CREATE_SUSPENDED count. DEBUG_PROCESS still
     * stops the new process at its CREATE event before any user-mode execution.
     * Waiting for that event while the manual suspension remains could stall.
     * Actual event handles are duplicated before their later Continue. */
    DWORD previous = ResumeThread(s->pi.hThread);
    if (previous == (DWORD)-1) { fail(s, RDBC_RESUME, GetLastError()); return 0; }
    if (previous != 1) { fail(s, RDBC_RESUME, ERROR_INVALID_DATA); return 0; }
    s->resumed = 1;
    return 1;
}
static RDBC_EVENT *record(STATE *s) {
    RDBC_EVENT *r;
    if (s->event_count >= RDBC_EVENT_CAP) {
        s->ledger_overflow = 1; fail(s, RDBC_STAGE_EVENT, ERROR_BUFFER_OVERFLOW); return NULL;
    }
    r = &s->events[s->event_count++];
    r->sequence = s->event_count; r->code = s->event.dwDebugEventCode;
    r->pid = s->event.dwProcessId; r->tid = s->event.dwThreadId;
    r->elapsed_ms = GetTickCount64() - s->start;
    return r;
}
static int add_thread(STATE *s, DWORD pid, DWORD tid) {
    if (!tid || s->thread_count >= RDBC_THREAD_CAP) return 0;
    for (uint32_t i = 0; i < s->thread_count; ++i)
        if (s->threads[i].pid == pid && s->threads[i].tid == tid && s->threads[i].live) return 0;
    s->threads[s->thread_count++] = (THREAD_KEY){pid, tid, 1};
    return 1;
}
static int end_thread(STATE *s, DWORD pid, DWORD tid) {
    for (uint32_t i = 0; i < s->thread_count; ++i) {
        if (s->threads[i].pid == pid && s->threads[i].tid == tid && s->threads[i].live) {
            s->threads[i].live = 0; return 1;
        }
    }
    return 0;
}
static int event_file(STATE *s, HANDLE h) {
    if (!h) return 1;
    if (s->event_file.h) { fail(s, RDBC_STAGE_EVENT, ERROR_BUFFER_OVERFLOW); s->blocked = 1; return 0; }
    s->event_file.h = h;                  /* registered before CloseHandle */
    if (!close_slot(s, &s->event_file)) {
        fail(s, RDBC_CLOSE, s->cleanup_error); s->blocked = 1; return 0;
    }
    s->event_file.close_attempted = 0;    /* next event has a NEW file lifetime */
    return 1;
}
static void terminate(STATE *s) {
    if (s->terminating || !s->created) return;
    s->terminating = 1;                  /* only the held unnamed own Job */
    if (!TerminateJobObject(s->job.h, 125)) cf(s, RDBC_TERMINATE, GetLastError());
}
static DWORD dispatch(STATE *s, RDBC_EVENT *r) {
    DEBUG_EVENT *e = &s->event;
    DWORD disposition = DBG_CONTINUE, image_n = RDBC_PATH_CAP;
    int i = index_of(s, e->dwProcessId);
    BOOL member = FALSE;
    FILETIME birth, x, k, u;
    RDBC_CANDIDATE *c;
    if (e->dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT) {
        /* Numeric alias with PI would be a single OS-managed handle lifetime.
         * Do not later explicitly close a handle that EXIT/Continue will close. */
        if (e->dwProcessId == s->pi.dwProcessId) {
            if (s->pi_process.h == e->u.CreateProcessInfo.hProcess) s->pi_process.h = NULL;
            if (s->pi_thread.h == e->u.CreateProcessInfo.hThread) s->pi_thread.h = NULL;
        }
        (void)event_file(s, e->u.CreateProcessInfo.hFile);
        if (s->blocked) return disposition;
        if (i >= 0 || s->count >= RDBC_PROCESS_CAP || !e->u.CreateProcessInfo.hProcess ||
            !e->u.CreateProcessInfo.hThread || (!s->count && e->dwProcessId != s->pi.dwProcessId)) {
            fail(s, RDBC_STAGE_EVENT, ERROR_INVALID_DATA); s->blocked = 1; return disposition;
        }
        i = (int)s->count;
        c = &s->candidates[i]; c->pid = e->dwProcessId; c->initial_tid = e->dwThreadId;
        c->birth_event_sequence = r ? r->sequence : 0; c->process_exit_code = STILL_ACTIVE;
        ++s->count;                      /* slots/candidate registered before calls */
        if (!DuplicateHandle(GetCurrentProcess(), e->u.CreateProcessInfo.hProcess,
            GetCurrentProcess(), &s->held[i].process.h, 0, FALSE, DUPLICATE_SAME_ACCESS)) {
            fail(s, RDBC_DUPLICATE, GetLastError()); s->blocked = 1; return disposition;
        }
        if (!DuplicateHandle(GetCurrentProcess(), e->u.CreateProcessInfo.hThread,
            GetCurrentProcess(), &s->held[i].thread.h, 0, FALSE, DUPLICATE_SAME_ACCESS)) {
            fail(s, RDBC_DUPLICATE, GetLastError()); s->blocked = 1; return disposition;
        }
        if (GetProcessId(s->held[i].process.h) != c->pid ||
            GetThreadId(s->held[i].thread.h) != c->initial_tid ||
            GetProcessIdOfThread(s->held[i].thread.h) != c->pid) {
            fail(s, RDBC_BIRTH, ERROR_INVALID_DATA); return disposition;
        }
        if (!IsProcessInJob(s->held[i].process.h, s->job.h, &member)) {
            fail(s, RDBC_BIRTH, GetLastError()); return disposition;
        }
        if (!member) { fail(s, RDBC_BIRTH, ERROR_INVALID_DATA); return disposition; }
        if (!GetProcessTimes(s->held[i].process.h, &birth, &x, &k, &u)) {
            fail(s, RDBC_BIRTH, GetLastError()); return disposition;
        }
        c->birth_filetime = ((uint64_t)birth.dwHighDateTime << 32) | birth.dwLowDateTime;
        if (!QueryFullProcessImageNameW(s->held[i].process.h, 0, (wchar_t *)c->image, &image_n)) {
            fail(s, RDBC_BIRTH, GetLastError()); return disposition;
        }
        if (image_n >= RDBC_PATH_CAP || _wcsicmp((const wchar_t *)c->image, s->node_final) != 0 ||
            !add_thread(s, c->pid, c->initial_tid)) {
            fail(s, RDBC_BIRTH, ERROR_INVALID_DATA); return disposition;
        }
        c->image_matches_pin = 1;
        if (e->dwProcessId != s->pi.dwProcessId && !inventory(s, RDBC_PROCESS_CAP))
            return disposition;
        if (e->dwProcessId == s->pi.dwProcessId &&
            (!s->resumed || !inventory(s, 1)))
            fail(s, RDBC_BIRTH, ERROR_INVALID_DATA);
        return disposition;            /* BOTH event duplicates precede Continue */
    }
    if (e->dwDebugEventCode == LOAD_DLL_DEBUG_EVENT) {
        (void)event_file(s, e->u.LoadDll.hFile);
        if (s->blocked) return disposition;
    }
    if (i < 0 || s->candidates[i].exit_continued) {
        fail(s, RDBC_STAGE_EVENT, ERROR_INVALID_DATA); s->blocked = 1; return disposition;
    }
    c = &s->candidates[i];
    switch (e->dwDebugEventCode) {
    case CREATE_THREAD_DEBUG_EVENT:
        if (!e->u.CreateThread.hThread || !add_thread(s, e->dwProcessId, e->dwThreadId))
            fail(s, RDBC_STAGE_EVENT, ERROR_INVALID_DATA);
        break;
    case EXIT_THREAD_DEBUG_EVENT:
        if (r) r->detail = e->u.ExitThread.dwExitCode;
        break;                         /* retirement only after checked Continue */
    case EXIT_PROCESS_DEBUG_EVENT:
        if (c->exit_seen) fail(s, RDBC_STAGE_EVENT, ERROR_INVALID_DATA);
        c->exit_seen = 1; c->exit_event_code = e->u.ExitProcess.dwExitCode;
        if (r) r->detail = c->exit_event_code;
        if (!s->terminating && c->exit_event_code) fail(s, RDBC_TERMINAL, ERROR_PROCESS_ABORTED);
        break;
    case EXCEPTION_DEBUG_EVENT:
        if (r) {
            r->detail = e->u.Exception.ExceptionRecord.ExceptionCode;
            r->first_chance = e->u.Exception.dwFirstChance;
        }
        if (!s->primary_stage && !c->startup_breakpoint_seen &&
            e->dwThreadId == c->initial_tid && e->u.Exception.dwFirstChance == 1 &&
            e->u.Exception.ExceptionRecord.ExceptionCode == EXCEPTION_BREAKPOINT)
            c->startup_breakpoint_seen = 1; /* single declared loader-breakpoint policy */
        else {
            fail(s, RDBC_STAGE_EVENT, ERROR_UNHANDLED_EXCEPTION);
            disposition = DBG_EXCEPTION_NOT_HANDLED; /* preserve unexpected faults */
        }
        break;
    case LOAD_DLL_DEBUG_EVENT:
    case UNLOAD_DLL_DEBUG_EVENT:
    case OUTPUT_DEBUG_STRING_EVENT:     /* don't dereference any remote pointer */
        break;
    case RIP_EVENT:
        if (r) r->detail = e->u.RipInfo.dwError;
        fail(s, RDBC_STAGE_EVENT, e->u.RipInfo.dwError); break;
    default:
        fail(s, RDBC_STAGE_EVENT, ERROR_INVALID_DATA); s->blocked = 1; break;
    }
    return disposition;
}
static void pump(STATE *s) {
    while (!s->blocked) {
        uint64_t now = GetTickCount64(), end;
        DWORD timeout, error, disposition;
        int i;
        RDBC_EVENT *r;
        if (s->count && s->exit_count == s->count) break;
        if (s->primary_stage || s->cleanup_stage) {
            if (!s->cleanup_end) s->cleanup_end = now + RDBC_CLEANUP_MS;
            terminate(s); end = s->cleanup_end;
        } else end = s->run_end;
        if (now >= end) {
            if (!s->primary_stage) { fail(s, RDBC_DEADLINE, ERROR_TIMEOUT); continue; }
            cf(s, RDBC_DEADLINE, ERROR_TIMEOUT); break;
        }
        timeout = (DWORD)(end - now); if (timeout > 50) timeout = 50;
        memset(&s->event, 0, sizeof(s->event));
        if (!WaitForDebugEventEx(&s->event, timeout)) {
            error = GetLastError();
            if (error == ERROR_SEM_TIMEOUT) continue;
            fail(s, RDBC_WAIT, error); cf(s, RDBC_WAIT, error); break;
        }
        r = record(s);
        disposition = dispatch(s, r);
        if (s->blocked) break;
        if (!s->primary_stage && GetTickCount64() >= s->run_end) fail(s, RDBC_DEADLINE, ERROR_TIMEOUT);
        if (s->primary_stage || s->cleanup_stage) {
            if (!s->cleanup_end) s->cleanup_end = GetTickCount64() + RDBC_CLEANUP_MS;
            terminate(s);                /* issued release is cleanup-only now */
        }
        /* Sample the existing applicable absolute lease immediately before
         * release. Dispatch/termination calls may have crossed cleanup_end. */
        end = (s->primary_stage || s->cleanup_stage) ? s->cleanup_end : s->run_end;
        if (GetTickCount64() >= end) {
            fail(s, RDBC_DEADLINE, ERROR_TIMEOUT);
            cf(s, RDBC_DEADLINE, ERROR_TIMEOUT);
            s->blocked = 1; break;       /* unresolved stop; NEVER release late */
        }
        if (r) r->disposition = disposition;
        if (!ContinueDebugEvent(s->event.dwProcessId, s->event.dwThreadId, disposition)) {
            error = GetLastError(); fail(s, RDBC_CONTINUE, error); cf(s, RDBC_CONTINUE, error);
            s->blocked = 1; break;
        }
        if (r) r->continued = 1;
        i = index_of(s, s->event.dwProcessId);
        if (s->event.dwDebugEventCode == EXIT_THREAD_DEBUG_EVENT &&
            !end_thread(s, s->event.dwProcessId, s->event.dwThreadId))
            fail(s, RDBC_STAGE_EVENT, ERROR_INVALID_DATA);
        if (s->event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT && i >= 0) {
            s->candidates[i].exit_continued = 1; ++s->exit_count;
            for (uint32_t j = 0; j < s->thread_count; ++j)
                if (s->threads[j].pid == s->event.dwProcessId) s->threads[j].live = 0;
        }
    }
}
static void terminal(STATE *s) {
    uint64_t end = s->cleanup_end ? s->cleanup_end : GetTickCount64() + RDBC_CLEANUP_MS;
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION accounting;
    DWORD bytes = 0, wait, code;
    if (!s->count || s->exit_count != s->count || s->blocked) {
        cf(s, RDBC_TERMINAL, ERROR_TIMEOUT); return;
    }
    for (uint32_t i = 0; i < s->count; ++i) {
        for (;;) {
            uint64_t now = GetTickCount64();
            DWORD timeout = now >= end ? 0 : (DWORD)(end - now);
            if (timeout > 50) timeout = 50;
            wait = WaitForSingleObject(s->held[i].process.h, timeout);
            if (wait == WAIT_OBJECT_0) { s->candidates[i].signaled = 1; break; }
            if (wait == WAIT_FAILED) { cf(s, RDBC_TERMINAL, GetLastError()); return; }
            if (wait != WAIT_TIMEOUT || now >= end) { cf(s, RDBC_TERMINAL, ERROR_TIMEOUT); return; }
        }
        code = STILL_ACTIVE;
        if (!GetExitCodeProcess(s->held[i].process.h, &code)) { cf(s, RDBC_TERMINAL, GetLastError()); return; }
        s->candidates[i].process_exit_code = code;
        if (code != s->candidates[i].exit_event_code) { cf(s, RDBC_TERMINAL, ERROR_INVALID_DATA); return; }
    }
    for (;;) {
        memset(&accounting, 0, sizeof(accounting));
        if (!QueryInformationJobObject(s->job.h, JobObjectBasicAccountingInformation,
                                      &accounting, sizeof(accounting), &bytes)) {
            cf(s, RDBC_JOB, GetLastError()); return;
        }
        if (!accounting.ActiveProcesses) {
            if (!inventory(s, 0)) return;
            s->job_empty = 1; s->system_handles_pending = 0; return;
        }
        if (accounting.ActiveProcesses > RDBC_PROCESS_CAP || GetTickCount64() >= end) {
            cf(s, RDBC_JOB, ERROR_TIMEOUT); return;
        }
        Sleep(1);                         /* no APC and no alertable wait */
    }
}
static void collect(STATE *s, const RDBC_ARGS *a) {
    s->creator_pid = GetCurrentProcessId(); s->debugger_tid = GetCurrentThreadId();
    s->start = GetTickCount64(); s->run_end = s->start + RDBC_RUN_MS;
    if (!args_ok(a)) { fail(s, RDBC_ARGUMENTS, ERROR_INVALID_PARAMETER); goto cleanup; }
    s->generation = a->generation;
    if (!pin(s, &s->node_file, (const wchar_t *)a->node_path, a->node_sha256,
             RDBC_NODE_BYTE_CAP, s->node_final) ||
        !pin(s, &s->parent_file, (const wchar_t *)a->parent_fixture, a->parent_sha256,
             RDBC_FIXTURE_BYTE_CAP, s->parent_final) ||
        !pin(s, &s->child_file, (const wchar_t *)a->child_fixture, a->child_sha256,
             RDBC_FIXTURE_BYTE_CAP, s->child_final)) goto cleanup;
    s->pins_verified = 1;
    (void)setup(s, a);
    if (s->created) {
        pump(s);
        if (s->exit_count != s->count || s->blocked) terminate(s);
        terminal(s);
    }
cleanup:
    if (s->created && !s->job_empty) terminate(s);
    (void)close_slot(s, &s->event_file);
    /* job_empty for a created chain is set only after checked EXIT releases,
     * independent signaled/exit-code observations and an empty Job vector.
     * Unknown terminal state retains held authority through save and the
     * immediate process-exit fallback; fallback is NEVER terminal evidence. */
    if (!s->created || s->job_empty) {
        for (uint32_t i = 0; i < RDBC_PROCESS_CAP; ++i) {
            (void)close_slot(s, &s->held[i].thread); (void)close_slot(s, &s->held[i].process);
        }
        (void)close_slot(s, &s->pi_thread); (void)close_slot(s, &s->pi_process);
    }
    if (s->attrs_initialized) { DeleteProcThreadAttributeList(s->attrs); s->attrs_initialized = 0; }
    if (s->attrs && !HeapFree(GetProcessHeap(), 0, s->attrs)) cf(s, RDBC_HEAP, ERROR_GEN_FAILURE);
    else s->attrs = NULL;
    if (s->job.h && !s->created && inventory(s, 0)) s->job_empty = 1;
    if (!s->created || s->job_empty) (void)close_slot(s, &s->job);
    (void)close_slot(s, &s->child_file);
    (void)close_slot(s, &s->parent_file); (void)close_slot(s, &s->node_file);
    s->owned_handles_remaining = slots(s);
    s->cleanup_complete = !s->cleanup_stage && !s->owned_handles_remaining &&
        !s->attrs && !s->crypto_cleanup_unknown &&
        (!s->created || (s->job_empty && s->count && s->exit_count == s->count &&
                         !s->system_handles_pending && !s->blocked));
    if (!s->primary_stage && s->count != RDBC_PROCESS_CAP) fail(s, RDBC_STAGE_EVENT, ERROR_INVALID_DATA);
    for (uint32_t i = 0; i < s->count; ++i)
        if (!s->primary_stage && (!s->candidates[i].startup_breakpoint_seen ||
            !s->candidates[i].image_matches_pin || s->candidates[i].process_exit_code != 0))
            fail(s, RDBC_TERMINAL, ERROR_INVALID_DATA);
}
/* Fixed-cap streaming JSON output; only printable ASCII and escaped UTF-16.
 * The file is exclusive and already registered before collect(). Errors in
 * write/flush/close yield nonzero RC; Root must reject any partial receipt. */
typedef struct WRITER { HANDLE h; DWORD used; int failed; } WRITER;
static void emit(WRITER *w, const char *text, size_t n) {
    DWORD done = 0;
    if (w->failed) return;
    if (n > RDBC_OUTPUT_BYTE_CAP - w->used ||
        !WriteFile(w->h, text, (DWORD)n, &done, NULL) || done != n) { w->failed = 1; return; }
    w->used += done;
}
static void fmt(WRITER *w, const char *format, ...) {
    char text[512];
    int n;
    va_list ap; va_start(ap, format); n = vsnprintf(text, sizeof(text), format, ap); va_end(ap);
    if (n < 0 || (size_t)n >= sizeof(text)) { w->failed = 1; return; }
    emit(w, text, (size_t)n);
}
static void quoted(WRITER *w, const uint16_t *p) {
    emit(w, "\"", 1);
    for (size_t i = 0; i < RDBC_PATH_CAP && p[i]; ++i) fmt(w, "\\u%04x", (unsigned)p[i]);
    emit(w, "\"", 1);
}
static int save(HANDLE h, const STATE *s) {
    WRITER w = {h, 0, 0};
    int observed = !s->primary_stage && !s->cleanup_stage && s->cleanup_complete &&
        s->created && s->pins_verified && s->kill_on_exit && s->resumed &&
        s->count == RDBC_PROCESS_CAP && !s->ledger_overflow;
    fmt(&w, "{\"schema\":\"root-synthetic-debug-birth/1\",\"status\":\"%s\",",
        observed ? "observed_only" : "rejected");
    fmt(&w, "\"generation\":\"%llu\",\"creator_pid\":%u,\"debugger_tid\":%u,",
        (unsigned long long)s->generation, s->creator_pid, s->debugger_tid);
    fmt(&w, "\"primary_stage\":%u,\"primary_error\":%u,\"cleanup_stage\":%u,\"cleanup_error\":%u,",
        s->primary_stage, s->primary_error, s->cleanup_stage, s->cleanup_error);
    fmt(&w, "\"cleanup_complete\":%s,\"job_empty\":%s,\"owned_native_probe_handles_remaining\":%u,"
        "\"system_handles_pending\":%u,\"candidate_count\":%u,\"event_count\":%u,\"ledger_overflow\":%s,",
        s->cleanup_complete ? "true" : "false", s->job_empty ? "true" : "false",
        s->owned_handles_remaining, s->system_handles_pending, s->count, s->event_count,
        s->ledger_overflow ? "true" : "false");
    fmt(&w, "\"root_process_created\":%s,\"root_pid\":%u,\"resumed\":%s,"
        "\"fixed_process_cap\":%u,\"run_ms\":%u,\"cleanup_ms\":%u,",
        s->created ? "true" : "false", s->pi.dwProcessId, s->resumed ? "true" : "false",
        RDBC_PROCESS_CAP, RDBC_RUN_MS, RDBC_CLEANUP_MS);
    fmt(&w, "\"pins_verified\":%s,\"kill_on_exit\":%s,\"termination_requested\":%s,"
        "\"grants\":{\"EditorRole\":false,\"kernel_entry_authority\":false,\"OwnerIPC\":false,"
        "\"production_dispatch\":false,\"Core\":false,\"model\":false,\"ready\":false},",
        s->pins_verified ? "true" : "false", s->kill_on_exit ? "true" : "false",
        s->terminating ? "true" : "false");
    if (!s->cleanup_complete) {
        emit(&w, "\"candidates\":null,\"ledger\":null,\"thread_exit_fallback\":\"not_observed_cleanup\"}\n",
             sizeof("\"candidates\":null,\"ledger\":null,\"thread_exit_fallback\":\"not_observed_cleanup\"}\n") - 1);
        return !w.failed;
    }
    emit(&w, "\"candidates\":[", sizeof("\"candidates\":[") - 1);
    for (uint32_t i = 0; i < s->count; ++i) {
        const RDBC_CANDIDATE *c = &s->candidates[i];
        fmt(&w, "%s{\"pid\":%u,\"initial_tid\":%u,\"birth_event_sequence\":%u,"
            "\"birth_filetime\":\"%llu\",\"image_matches_pin\":%s,\"image\":",
            i ? "," : "", c->pid, c->initial_tid, c->birth_event_sequence,
            (unsigned long long)c->birth_filetime, c->image_matches_pin ? "true" : "false");
        quoted(&w, c->image);
        fmt(&w, ",\"startup_breakpoint_seen\":%s,\"exit_seen\":%s,\"exit_continued\":%s,"
            "\"exit_event_code\":%u,\"process_exit_code\":%u,\"signaled\":%s,"
            "\"logical_creator_role\":null}",
            c->startup_breakpoint_seen ? "true" : "false", c->exit_seen ? "true" : "false",
            c->exit_continued ? "true" : "false", c->exit_event_code, c->process_exit_code,
            c->signaled ? "true" : "false");
    }
    emit(&w, "],\"ledger\":[", sizeof("],\"ledger\":[") - 1);
    for (uint32_t i = 0; i < s->event_count; ++i) {
        const RDBC_EVENT *r = &s->events[i];
        fmt(&w, "%s{\"sequence\":%u,\"code\":%u,\"pid\":%u,\"tid\":%u,"
            "\"elapsed_ms\":%llu,\"disposition\":%u,\"continued\":%s,\"detail\":%u,\"first_chance\":%u}",
            i ? "," : "", r->sequence, r->code, r->pid, r->tid, (unsigned long long)r->elapsed_ms,
            r->disposition, r->continued ? "true" : "false", r->detail, r->first_chance);
    }
    emit(&w, "]}\n", 3);
    return !w.failed;
}
int wmain(int argc, wchar_t **argv) {
    static RDBC_ARGS args;
    static STATE state; /* registered stable output/kernel slots before all calls */
    HANDLE input = NULL, output = NULL;
    LARGE_INTEGER size;
    DWORD read = 0;
    int saved, io_ok;
    if (argc != 3 || wcslen(argv[1]) >= RDBC_PATH_CAP || wcslen(argv[2]) >= RDBC_PATH_CAP ||
        !path_ok((const uint16_t *)argv[1]) || !path_ok((const uint16_t *)argv[2])) return 2;
    input = CreateFileW(argv[1], GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                        FILE_ATTRIBUTE_NORMAL, NULL);
    if (input == INVALID_HANDLE_VALUE) return 2;
    if (!GetFileSizeEx(input, &size) || size.QuadPart != (LONGLONG)sizeof(args) ||
        !ReadFile(input, &args, sizeof(args), &read, NULL) || read != sizeof(args)) {
        (void)CloseHandle(input); return 2; /* no child effects */
    }
    if (!CloseHandle(input)) return 2;
    input = NULL;
    output = CreateFileW(argv[2], GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (output == INVALID_HANDLE_VALUE) return 2;
    collect(&state, &args);              /* this SAME main thread owns the debug connection */
    saved = save(output, &state);
    io_ok = FlushFileBuffers(output) != 0;
    if (!CloseHandle(output)) io_ok = 0;
    if (!saved || !io_ok) return 4;       /* retain incomplete file; NEVER overwrite/retry */
    return state.primary_stage || state.cleanup_stage || !state.cleanup_complete ? 1 : 0;
    /* Immediate collector/process exit: default + explicit debug kill-on-exit.
     * No ongoing controller thread, callbacks, detach, Editor or kernel grant. */
}
