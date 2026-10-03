/* Root-only live DLL SOURCE proposal. Synthetic pinned Node only.
 * No execution/import/compile by author. No DllMain/Editor/role grant. Private HELLO/ACK witness transport only.
 * Debug operations and held-resource queries execute only on rld_run worker.
 * Unknown state retains original handles in caller-owned storage through
 * disposable host exit. No destroy/reset API and no kernel handle export.
 */
#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0A00
#include <windows.h>
#include <bcrypt.h>
#include <stdint.h>
#include <stddef.h>
#include <wchar.h>
#include <string.h>
#include <stdio.h>
#include "root_main_receiver.h"
typedef struct RWR_PRIVATE_CONTEXT RWR_PRIVATE_CONTEXT;
typedef struct SLOT { HANDLE h; uint32_t close_attempted; } SLOT;
typedef struct HELD { SLOT process, thread; } HELD;
typedef struct THREAD_KEY { DWORD pid, tid; uint32_t live; } THREAD_KEY;
typedef struct RLD_CANDIDATE {
    uint32_t pid, initial_tid, birth_event_sequence, startup_breakpoint_seen;
    uint32_t exit_seen, exit_continued, exit_event_code, signaled;
    uint32_t process_exit_code, image_matches_pin;
    uint64_t birth_filetime;
    uint16_t image[RLD_PATH_CAP];
} RLD_CANDIDATE;
typedef struct STATE {
    SLOT job, pi_process, pi_thread, event_file, node_file, parent_file, child_file;
    HELD held[RLD_PROCESS_CAP];
    PROCESS_INFORMATION pi;
    STARTUPINFOEXW si;
    DEBUG_EVENT event;
    LPPROC_THREAD_ATTRIBUTE_LIST attrs;
    SIZE_T attr_bytes;
    HANDLE job_list[1];
    uint32_t attrs_initialized, created, blocked, terminating, kill_on_exit;
    uint32_t primary_stage, primary_error, cleanup_stage, cleanup_error;
    uint32_t creator_pid, debugger_tid, count, event_count, ledger_overflow;
    uint32_t resumed, job_empty, cleanup_complete, system_handles_pending;
    uint32_t owned_handles_remaining, pins_verified, exit_count, thread_count;
    uint32_t crypto_cleanup_unknown;
    BCRYPT_ALG_HANDLE crypto_alg;
    BCRYPT_HASH_HANDLE crypto_hash;
    uint32_t alg_close_attempted, hash_close_attempted;
    volatile LONG stop_requested;
    uint64_t start, run_end, cleanup_end, generation;
    wchar_t node_final[RLD_PATH_CAP], parent_final[RLD_PATH_CAP], child_final[RLD_PATH_CAP];
    wchar_t command[3*RLD_PATH_CAP+16], environment[2*RLD_PATH_CAP];
    RLD_CANDIDATE candidates[RLD_PROCESS_CAP];
    RLD_EVENT events[RLD_EVENT_CAP];
    THREAD_KEY threads[RLD_THREAD_CAP];
    RWR_PRIVATE_CONTEXT *receiver;
} STATE;
typedef struct COMMAND {
    RLD_COMMAND_ARGS args;
    RLD_COMMAND_OUT *out;
    uint32_t state; /* 0 unused,1 queued,2 worker-owned,3 completed */
} COMMAND;
typedef struct RLD_PRIVATE_CONTEXT {
    volatile LONG initialized, run_claimed, phase, worker_returned;
    uint32_t magic, reserved;
    SRWLOCK lock; /* short registration/phase access only; NEVER native effects */
    RLD_ARGS args;
    STATE s;
    COMMAND commands[RLD_COMMAND_SLOTS];
} RLD_PRIVATE_CONTEXT;
_Static_assert(sizeof(RLD_PRIVATE_CONTEXT)<=RLD_CONTEXT_BYTES && _Alignof(RLD_PRIVATE_CONTEXT)<=8,"private context fits");
_Static_assert(sizeof(RLD_CANDIDATE)==2096,"private candidate layout");
static uint32_t rwr_slots(const RWR_PRIVATE_CONTEXT *r);
static int rwr_retired(const RWR_PRIVATE_CONTEXT *r);
static int rwr_environment(RWR_PRIVATE_CONTEXT *r,wchar_t *env,size_t cap,size_t used);
static void rwr_cleanup(RWR_PRIVATE_CONTEXT *r);
static volatile LONG reserved_once;
static RLD_PRIVATE_CONTEXT *original_context;
static const uint8_t known_node_sha[32]={0x33,0x31,0xe1,0xff,0xe1,0x98,0x74,0x21,0x54,0x72,0x21,0x7c,0x5e,0x94,0xf5,0xa0,0xc6,0xd8,0xe1,0x8c,0x4a,0xc7,0x11,0x1d,0x39,0x37,0xaa,0x0a,0xd5,0xe9,0xb4,0xa5};
static const uint8_t known_parent_sha[32]={0x11,0x01,0x5f,0xc6,0x99,0xe6,0x45,0xf9,0x27,0xf2,0x86,0xb5,0x5d,0xb7,0x43,0xcf,0xae,0xdf,0x02,0x0e,0xff,0x60,0xa3,0x94,0x26,0xb2,0xb3,0xff,0x65,0x27,0x11,0x8f};
static const uint8_t known_child_sha[32]={0x57,0x48,0xb8,0xd4,0xf8,0xbc,0x52,0xc6,0x87,0x1c,0xcf,0x13,0x5e,0x0f,0xda,0x61,0x67,0x0a,0x8e,0x69,0xc0,0x56,0x7f,0xf9,0x41,0x9a,0xfc,0xfa,0xc3,0x47,0x64,0x11};
static DWORD nz(DWORD e) { return e ? e : ERROR_GEN_FAILURE; }
static void fail(STATE *s,uint32_t stage,DWORD e) {
    if(!s->primary_stage){s->primary_stage=stage;s->primary_error=nz(e);}
}
static void cf(STATE *s,uint32_t stage,DWORD e) {
    if(!s->cleanup_stage){s->cleanup_stage=stage;s->cleanup_error=nz(e);}
}
static int closure_fresh(STATE *s) {
    if(GetTickCount64()>=s->cleanup_end){cf(s,RLD_DEADLINE,ERROR_TIMEOUT);return 0;}
    return 1;
}
static int close_slot(STATE *s,SLOT *p) {
    DWORD e;
    if(!p->h)return 1;
    if(p->close_attempted)return 0;
    if(!closure_fresh(s))return 0;
    p->close_attempted=1;
    if(CloseHandle(p->h)){p->h=NULL;return 1;}
    e=GetLastError();cf(s,RLD_CLOSE,e);return 0;
}
static uint32_t slots(const STATE *s) {
    uint32_t n=(s->job.h!=NULL)+(s->pi_process.h!=NULL)+(s->pi_thread.h!=NULL)+
      (s->event_file.h!=NULL)+(s->node_file.h!=NULL)+(s->parent_file.h!=NULL)+(s->child_file.h!=NULL)+
      (s->crypto_alg!=NULL)+(s->crypto_hash!=NULL);
    for(uint32_t i=0;i<RLD_PROCESS_CAP;++i)n+=(s->held[i].process.h!=NULL)+(s->held[i].thread.h!=NULL);
    return n+rwr_slots(s->receiver);
}
static int path_ok(const uint16_t *p) {
    size_t i, begin;
    if (!((p[0] >= 'A' && p[0] <= 'Z') || (p[0] >= 'a' && p[0] <= 'z')) ||
        p[1] != ':' || p[2] != '\\') return 0;
    for (i = 3; i < RLD_PATH_CAP && p[i]; ++i)
        if (p[i] < 32 || p[i] == '"' || p[i] == '/' || p[i] == ':') return 0;
    if (i < 4 || i == RLD_PATH_CAP || p[i - 1] == '\\') return 0;
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
static int args_ok(const RLD_ARGS *a) {
    uint32_t zero=a->reserved0;
    if(a->magic!=RLD_MAGIC||a->version!=RLD_VERSION||a->size_bytes!=sizeof(*a)||
       !a->generation||!a->session_cookie||!path_ok(a->node_path)||
       !path_ok(a->parent_fixture)||!path_ok(a->child_fixture)||!path_ok(a->working_directory))return 0;
    for(size_t i=0;i<8;++i)zero|=a->reserved1[i];
    return !zero&&suffix((const wchar_t*)a->node_path,L"\\node.exe")&&
      suffix((const wchar_t*)a->parent_fixture,L".cjs")&&suffix((const wchar_t*)a->child_fixture,L".cjs")&&
      _wcsicmp((const wchar_t*)a->parent_fixture,(const wchar_t*)a->child_fixture)!=0;
}
static int fresh(STATE *s) {
    if(s->primary_stage||s->cleanup_stage)return 0;
    if(InterlockedCompareExchange(&s->stop_requested,0,0)){
        fail(s,RLD_REVOKED,ERROR_CANCELLED);return 0;
    }
    if(GetTickCount64()>=s->run_end){fail(s,RLD_DEADLINE,ERROR_TIMEOUT);return 0;}
    return 1;
}
/* Known BCrypt output slots remain in STATE, including failed destruction.
 * A close tombstone is irreversible; no numerical retry at cleanup. */
static void close_crypto(STATE *s) {
    if(s->crypto_hash&&!s->hash_close_attempted){
        if(!closure_fresh(s)){s->crypto_cleanup_unknown=1;return;}
        s->hash_close_attempted=1;
        if(BCryptDestroyHash(s->crypto_hash)<0){s->crypto_cleanup_unknown=1;cf(s,RLD_PIN_FILES,ERROR_INVALID_DATA);}
        else s->crypto_hash=NULL;
    }
    if(!s->crypto_hash&&s->crypto_alg&&!s->alg_close_attempted){
        if(!closure_fresh(s)){s->crypto_cleanup_unknown=1;return;}
        s->alg_close_attempted=1;
        if(BCryptCloseAlgorithmProvider(s->crypto_alg,0)<0){s->crypto_cleanup_unknown=1;cf(s,RLD_PIN_FILES,ERROR_INVALID_DATA);}
        else s->crypto_alg=NULL;
    }
}
static int pin(STATE *s,SLOT *file,const wchar_t *path,const uint8_t expected[32],
               DWORD cap,wchar_t final[RLD_PATH_CAP]) {
    LARGE_INTEGER size;
    uint8_t buffer[65536],digest[32];
    DWORD got=0,n,e=0;
    uint64_t consumed=0;
    int ok=0;
    if(!fresh(s)||file->h||s->crypto_alg||s->crypto_hash||s->crypto_cleanup_unknown)goto done;
    s->alg_close_attempted=s->hash_close_attempted=0; /* NEW cryptographic lifetimes */
    file->h=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file->h==INVALID_HANDLE_VALUE){e=GetLastError();file->h=NULL;goto done;}
    if(!GetFileSizeEx(file->h,&size)){e=GetLastError();goto done;}
    if(size.QuadPart<=0||(uint64_t)size.QuadPart>cap||
       (file==&s->node_file&&size.QuadPart!=91694408)){e=ERROR_FILE_TOO_LARGE;goto done;}
    n=GetFinalPathNameByHandleW(file->h,final,RLD_PATH_CAP,FILE_NAME_NORMALIZED|VOLUME_NAME_DOS);
    if(!n||n>=RLD_PATH_CAP){e=n?ERROR_BUFFER_OVERFLOW:GetLastError();goto done;}
    if(wcsncmp(final,L"\\\\?\\",4)!=0||_wcsicmp(final+4,path)!=0){e=ERROR_INVALID_NAME;goto done;}
    memmove(final,final+4,(wcslen(final+4)+1)*sizeof(wchar_t));
    if(BCryptOpenAlgorithmProvider(&s->crypto_alg,BCRYPT_SHA256_ALGORITHM,NULL,0)<0){e=ERROR_INVALID_DATA;goto done;}
    if(BCryptCreateHash(s->crypto_alg,&s->crypto_hash,NULL,0,NULL,0,0)<0){e=ERROR_INVALID_DATA;goto done;}
    for(;;){
        if(!fresh(s)){e=ERROR_TIMEOUT;goto done;}
        if(!ReadFile(file->h,buffer,sizeof(buffer),&got,NULL)){e=GetLastError();goto done;}
        if(!got)break;
        consumed+=got;
        if(consumed>(uint64_t)size.QuadPart){e=ERROR_INVALID_DATA;goto done;}
        if(BCryptHashData(s->crypto_hash,buffer,got,0)<0){e=ERROR_INVALID_DATA;goto done;}
    }
    if(consumed!=(uint64_t)size.QuadPart||BCryptFinishHash(s->crypto_hash,digest,sizeof(digest),0)<0||
       memcmp(digest,expected,32)!=0){e=ERROR_INVALID_DATA;goto done;}
    ok=1;
done:
    close_crypto(s);
    if(s->crypto_cleanup_unknown)ok=0;
    SecureZeroMemory(buffer,sizeof(buffer));SecureZeroMemory(digest,sizeof(digest));
    if(!ok)fail(s,RLD_PIN_FILES,e);
    return ok;
}
static int index_of(const STATE *s, DWORD pid) {
    for (uint32_t i = 0; i < s->count; ++i) if (s->candidates[i].pid == pid) return (int)i;
    return -1;
}
static int inventory(STATE *s, DWORD exact) {
    struct { DWORD assigned, listed; ULONG_PTR ids[RLD_PROCESS_CAP]; } ids;
    DWORD bytes = 0;
    memset(&ids, 0, sizeof(ids));
    if (!QueryInformationJobObject(s->job.h, JobObjectBasicProcessIdList,
                                   &ids, sizeof(ids), &bytes)) {
        fail(s, RLD_JOB, GetLastError()); return 0;
    }
    if (ids.assigned != exact || ids.listed != exact || exact > RLD_PROCESS_CAP) {
        fail(s, RLD_JOB, ERROR_INVALID_DATA); return 0;
    }
    for (DWORD i = 0; i < exact; ++i) {
        DWORD pid = (DWORD)ids.ids[i];
        if (!pid || ids.ids[i] != (ULONG_PTR)pid) {
            fail(s, RLD_JOB, ERROR_INVALID_DATA); return 0;
        }
        if (index_of(s, pid) < 0 && pid != s->pi.dwProcessId) {
            fail(s, RLD_JOB, ERROR_INVALID_DATA); return 0;
        }
        for (DWORD j = 0; j < i; ++j) if (ids.ids[j] == ids.ids[i]) {
            fail(s, RLD_JOB, ERROR_INVALID_DATA); return 0;
        }
    }
    return 1; /* never OpenProcess/OpenThread by any returned ID */
}
static int setup(STATE *s, const RLD_ARGS *a) {
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits, actual;
    SIZE_T needed = 0;
    DWORD bytes = 0, error, n;
    size_t used;
    const wchar_t env_prefix[] = L"NODE_OPTIONS=\0NODE_PATH=\0SystemRoot=";
    memset(&limits, 0, sizeof(limits)); memset(&actual, 0, sizeof(actual));
    if (!fresh(s)) return 0;
    s->job.h = CreateJobObjectW(NULL, NULL);
    if (!s->job.h) { fail(s, RLD_JOB, GetLastError()); return 0; }
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS | JOB_OBJECT_LIMIT_PROCESS_MEMORY |
        JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION;
    limits.BasicLimitInformation.ActiveProcessLimit = RLD_PROCESS_CAP;
    limits.ProcessMemoryLimit = (SIZE_T)256 * 1024 * 1024;
    if (!SetInformationJobObject(s->job.h, JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        fail(s, RLD_JOB, GetLastError()); return 0;
    }
    if (!QueryInformationJobObject(s->job.h, JobObjectExtendedLimitInformation,
                                  &actual, sizeof(actual), &bytes)) {
        fail(s, RLD_JOB, GetLastError()); return 0;
    }
    if (actual.BasicLimitInformation.LimitFlags != limits.BasicLimitInformation.LimitFlags ||
        actual.BasicLimitInformation.ActiveProcessLimit != RLD_PROCESS_CAP ||
        actual.ProcessMemoryLimit != limits.ProcessMemoryLimit || !inventory(s, 0)) {
        fail(s, RLD_JOB, ERROR_INVALID_DATA); return 0;
    }
    SetLastError(ERROR_SUCCESS);
    if (InitializeProcThreadAttributeList(NULL, 1, 0, &needed) ||
        GetLastError() != ERROR_INSUFFICIENT_BUFFER || !needed || needed > 65536) {
        fail(s, RLD_ATTRIBUTES, ERROR_INVALID_DATA); return 0;
    }
    s->attr_bytes = needed;
    s->attrs = (LPPROC_THREAD_ATTRIBUTE_LIST)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, needed);
    if (!s->attrs) { fail(s, RLD_ATTRIBUTES, ERROR_NOT_ENOUGH_MEMORY); return 0; }
    if (!InitializeProcThreadAttributeList(s->attrs, 1, 0, &s->attr_bytes)) {
        fail(s, RLD_ATTRIBUTES, GetLastError()); return 0;
    }
    s->attrs_initialized = 1; s->job_list[0] = s->job.h;
    if (!UpdateProcThreadAttribute(s->attrs, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST,
                                   s->job_list, sizeof(s->job_list), NULL, NULL)) {
        fail(s, RLD_ATTRIBUTES, GetLastError()); return 0;
    }
    s->si.StartupInfo.cb = sizeof(s->si); s->si.lpAttributeList = s->attrs;
    if (swprintf(s->command, sizeof(s->command) / sizeof(s->command[0]),
                 L"\"%ls\" \"%ls\" \"%ls\"", s->node_final, s->parent_final, s->child_final) < 0) {
        fail(s, RLD_CREATE, ERROR_BUFFER_OVERFLOW); return 0;
    }
    used = sizeof(env_prefix) / sizeof(env_prefix[0]) - 1;
    memcpy(s->environment, env_prefix, used * sizeof(wchar_t));
    n = GetWindowsDirectoryW(s->environment + used, (UINT)(2 * RLD_PATH_CAP - used - 1));
    if (!n || n >= 2 * RLD_PATH_CAP - used - 1) {
        fail(s, RLD_CREATE, n ? ERROR_BUFFER_OVERFLOW : GetLastError()); return 0;
    }
    s->environment[used + n] = 0; s->environment[used + n + 1] = 0;
    if(!rwr_environment(s->receiver,s->environment,2u*RLD_PATH_CAP,used+n+1u)){
        fail(s,RLD_CREATE,ERROR_BUFFER_OVERFLOW);return 0;
    }
    if (!fresh(s)) return 0;
    if (!CreateProcessW(s->node_final, s->command, NULL, NULL, FALSE,
            DEBUG_PROCESS | CREATE_SUSPENDED | DETACHED_PROCESS |
            CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT,
            s->environment, (const wchar_t *)a->working_directory, &s->si.StartupInfo, &s->pi)) {
        fail(s, RLD_CREATE, GetLastError()); return 0;
    }
    s->pi_process.h = s->pi.hProcess; s->pi_thread.h = s->pi.hThread; /* publish immediately */
    s->created = 1; s->system_handles_pending = 1;
    if (!DebugSetProcessKillOnExit(TRUE)) {
        error = GetLastError(); fail(s, RLD_DEBUG_KILL, error); return 0;
    }
    s->kill_on_exit = 1;              /* default is also TRUE; never set FALSE */
    if (!s->pi_process.h || !s->pi_thread.h ||
        GetProcessId(s->pi_process.h) != s->pi.dwProcessId ||
        GetThreadId(s->pi_thread.h) != s->pi.dwThreadId) {
        fail(s, RLD_BIRTH, ERROR_INVALID_DATA); return 0;
    }
    if (!inventory(s, 1) || !fresh(s)) return 0;
    /* Remove ONLY the explicit CREATE_SUSPENDED count. DEBUG_PROCESS still
     * stops the new process at its CREATE event before any user-mode execution.
     * Waiting for that event while the manual suspension remains could stall.
     * Actual event handles are duplicated before their later Continue. */
    DWORD previous = ResumeThread(s->pi.hThread);
    if (previous == (DWORD)-1) { fail(s, RLD_RESUME, GetLastError()); return 0; }
    if (previous != 1) { fail(s, RLD_RESUME, ERROR_INVALID_DATA); return 0; }
    s->resumed = 1;
    return 1;
}
static RLD_EVENT *record(STATE *s) {
    RLD_EVENT *r;
    if (s->event_count >= RLD_EVENT_CAP) {
        s->ledger_overflow = 1; fail(s, RLD_STAGE_EVENT, ERROR_BUFFER_OVERFLOW); return NULL;
    }
    r = &s->events[s->event_count++];
    r->sequence = s->event_count; r->code = s->event.dwDebugEventCode;
    r->pid = s->event.dwProcessId; r->tid = s->event.dwThreadId;
    r->elapsed_ms = GetTickCount64() - s->start;
    return r;
}
static int add_thread(STATE *s, DWORD pid, DWORD tid) {
    if (!tid || s->thread_count >= RLD_THREAD_CAP) return 0;
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
    if (s->event_file.h) { fail(s, RLD_STAGE_EVENT, ERROR_BUFFER_OVERFLOW); s->blocked = 1; return 0; }
    s->event_file.h = h;                  /* registered before CloseHandle */
    if (!close_slot(s, &s->event_file)) {
        fail(s, RLD_CLOSE, s->cleanup_error); s->blocked = 1; return 0;
    }
    s->event_file.close_attempted = 0;    /* next event has a NEW file lifetime */
    return 1;
}
static void terminate(STATE *s) {
    if(s->terminating||!s->created||!rwr_retired(s->receiver))return;
    if(!closure_fresh(s)){s->blocked=1;return;}
    s->terminating=1;
    if(!TerminateJobObject(s->job.h,RLD_STOP_EXIT_CODE))cf(s,RLD_TERMINATE,GetLastError());
}
static DWORD dispatch(STATE *s, RLD_EVENT *r) {
    DEBUG_EVENT *e = &s->event;
    DWORD disposition = DBG_CONTINUE, image_n = RLD_PATH_CAP;
    int i = index_of(s, e->dwProcessId);
    BOOL member = FALSE;
    FILETIME birth, x, k, u;
    RLD_CANDIDATE *c;
    if (e->dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT) {
        /* Numeric alias with PI would be a single OS-managed handle lifetime.
         * Do not later explicitly close a handle that EXIT/Continue will close. */
        if (e->dwProcessId == s->pi.dwProcessId) {
            if (s->pi_process.h == e->u.CreateProcessInfo.hProcess) s->pi_process.h = NULL;
            if (s->pi_thread.h == e->u.CreateProcessInfo.hThread) s->pi_thread.h = NULL;
        }
        (void)event_file(s, e->u.CreateProcessInfo.hFile);
        if (s->blocked) return disposition;
        if (i >= 0 || s->count >= RLD_PROCESS_CAP || !e->u.CreateProcessInfo.hProcess ||
            !e->u.CreateProcessInfo.hThread || (!s->count && e->dwProcessId != s->pi.dwProcessId)) {
            fail(s, RLD_STAGE_EVENT, ERROR_INVALID_DATA); s->blocked = 1; return disposition;
        }
        i = (int)s->count;
        c = &s->candidates[i]; c->pid = e->dwProcessId; c->initial_tid = e->dwThreadId;
        c->birth_event_sequence = r ? r->sequence : 0; c->process_exit_code = STILL_ACTIVE;
        ++s->count;                      /* slots/candidate registered before calls */
        if (!DuplicateHandle(GetCurrentProcess(), e->u.CreateProcessInfo.hProcess,
            GetCurrentProcess(), &s->held[i].process.h, 0, FALSE, DUPLICATE_SAME_ACCESS)) {
            fail(s, RLD_DUPLICATE, GetLastError()); s->blocked = 1; return disposition;
        }
        if (!DuplicateHandle(GetCurrentProcess(), e->u.CreateProcessInfo.hThread,
            GetCurrentProcess(), &s->held[i].thread.h, 0, FALSE, DUPLICATE_SAME_ACCESS)) {
            fail(s, RLD_DUPLICATE, GetLastError()); s->blocked = 1; return disposition;
        }
        if (GetProcessId(s->held[i].process.h) != c->pid ||
            GetThreadId(s->held[i].thread.h) != c->initial_tid ||
            GetProcessIdOfThread(s->held[i].thread.h) != c->pid) {
            fail(s, RLD_BIRTH, ERROR_INVALID_DATA); return disposition;
        }
        if (!IsProcessInJob(s->held[i].process.h, s->job.h, &member)) {
            fail(s, RLD_BIRTH, GetLastError()); return disposition;
        }
        if (!member) { fail(s, RLD_BIRTH, ERROR_INVALID_DATA); return disposition; }
        if (!GetProcessTimes(s->held[i].process.h, &birth, &x, &k, &u)) {
            fail(s, RLD_BIRTH, GetLastError()); return disposition;
        }
        c->birth_filetime = ((uint64_t)birth.dwHighDateTime << 32) | birth.dwLowDateTime;
        if (!QueryFullProcessImageNameW(s->held[i].process.h, 0, (wchar_t *)c->image, &image_n)) {
            fail(s, RLD_BIRTH, GetLastError()); return disposition;
        }
        if (image_n >= RLD_PATH_CAP || _wcsicmp((const wchar_t *)c->image, s->node_final) != 0 ||
            !add_thread(s, c->pid, c->initial_tid)) {
            fail(s, RLD_BIRTH, ERROR_INVALID_DATA); return disposition;
        }
        c->image_matches_pin = 1;
        if (e->dwProcessId != s->pi.dwProcessId && !inventory(s, RLD_PROCESS_CAP))
            return disposition;
        if (e->dwProcessId == s->pi.dwProcessId &&
            (!s->resumed || !inventory(s, 1)))
            fail(s, RLD_BIRTH, ERROR_INVALID_DATA);
        return disposition;            /* BOTH event duplicates precede Continue */
    }
    if (e->dwDebugEventCode == LOAD_DLL_DEBUG_EVENT) {
        (void)event_file(s, e->u.LoadDll.hFile);
        if (s->blocked) return disposition;
    }
    if (i < 0 || s->candidates[i].exit_continued) {
        fail(s, RLD_STAGE_EVENT, ERROR_INVALID_DATA); s->blocked = 1; return disposition;
    }
    c = &s->candidates[i];
    switch (e->dwDebugEventCode) {
    case CREATE_THREAD_DEBUG_EVENT:
        if (!e->u.CreateThread.hThread || !add_thread(s, e->dwProcessId, e->dwThreadId))
            fail(s, RLD_STAGE_EVENT, ERROR_INVALID_DATA);
        break;
    case EXIT_THREAD_DEBUG_EVENT:
        if (r) r->detail = e->u.ExitThread.dwExitCode;
        break;                         /* retirement only after checked Continue */
    case EXIT_PROCESS_DEBUG_EVENT:
        if (c->exit_seen) fail(s, RLD_STAGE_EVENT, ERROR_INVALID_DATA);
        c->exit_seen = 1; c->exit_event_code = e->u.ExitProcess.dwExitCode;
        if (r) r->detail = c->exit_event_code;
        if (!s->terminating && c->exit_event_code) fail(s, RLD_TERMINAL, ERROR_PROCESS_ABORTED);
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
            fail(s, RLD_STAGE_EVENT, ERROR_UNHANDLED_EXCEPTION);
            disposition = DBG_EXCEPTION_NOT_HANDLED; /* preserve unexpected faults */
        }
        break;
    case LOAD_DLL_DEBUG_EVENT:
    case UNLOAD_DLL_DEBUG_EVENT:
    case OUTPUT_DEBUG_STRING_EVENT:     /* don't dereference any remote pointer */
        break;
    case RIP_EVENT:
        if (r) r->detail = e->u.RipInfo.dwError;
        fail(s, RLD_STAGE_EVENT, e->u.RipInfo.dwError); break;
    default:
        fail(s, RLD_STAGE_EVENT, ERROR_INVALID_DATA); s->blocked = 1; break;
    }
    return disposition;
}

/* Exactly one bounded debug event, on original worker only. No callbacks. */
static int pump_once(STATE *s) {
    uint64_t now=GetTickCount64(),end;
    DWORD timeout,error,disposition;
    RLD_EVENT *r;
    int i,cleanup=InterlockedCompareExchange(&s->stop_requested,0,0)||s->primary_stage||s->cleanup_stage;
    end=cleanup?s->cleanup_end:s->run_end;
    if(now>=end){
        if(cleanup){cf(s,RLD_DEADLINE,ERROR_TIMEOUT);s->blocked=1;}
        else {fail(s,RLD_DEADLINE,ERROR_TIMEOUT);InterlockedExchange(&s->stop_requested,1);}
        return 0;
    }
    timeout=(DWORD)(end-now);if(timeout>RLD_WAIT_SLICE_MS)timeout=RLD_WAIT_SLICE_MS;
    memset(&s->event,0,sizeof(s->event));
    if(!WaitForDebugEvent(&s->event,timeout)){
        error=GetLastError();
        if(error==ERROR_SEM_TIMEOUT)return 1;
        fail(s,RLD_WAIT,error);cf(s,RLD_WAIT,error);s->blocked=1;return 0;
    }
    r=record(s);disposition=dispatch(s,r);
    if(s->blocked)return 0;
    if(!s->primary_stage&&!s->cleanup_stage&&!InterlockedCompareExchange(&s->stop_requested,0,0)&&
       GetTickCount64()>=s->run_end)fail(s,RLD_DEADLINE,ERROR_TIMEOUT);
    if(s->primary_stage||s->cleanup_stage)InterlockedExchange(&s->stop_requested,1);
    if(InterlockedCompareExchange(&s->stop_requested,0,0))terminate(s);
    if(s->blocked)return 0;
    end=(InterlockedCompareExchange(&s->stop_requested,0,0)||s->primary_stage||s->cleanup_stage)?
        s->cleanup_end:s->run_end;
    if(GetTickCount64()>=end){
        if(InterlockedCompareExchange(&s->stop_requested,0,0)||s->primary_stage||s->cleanup_stage)
            cf(s,RLD_DEADLINE,ERROR_TIMEOUT);
        else fail(s,RLD_DEADLINE,ERROR_TIMEOUT);
        s->blocked=1;return 0; /* no late Continue, known slots stay retained */
    }
    if(r)r->disposition=disposition;
    if(!ContinueDebugEvent(s->event.dwProcessId,s->event.dwThreadId,disposition)){
        error=GetLastError();fail(s,RLD_CONTINUE,error);cf(s,RLD_CONTINUE,error);
        s->blocked=1;return 0;
    }
    if(r)r->continued=1;
    i=index_of(s,s->event.dwProcessId);
    if(s->event.dwDebugEventCode==EXIT_THREAD_DEBUG_EVENT&&
       !end_thread(s,s->event.dwProcessId,s->event.dwThreadId))fail(s,RLD_STAGE_EVENT,ERROR_INVALID_DATA);
    if(s->event.dwDebugEventCode==EXIT_PROCESS_DEBUG_EVENT&&i>=0){
        s->candidates[i].exit_continued=1;++s->exit_count;
        for(uint32_t j=0;j<s->thread_count;++j)
            if(s->threads[j].pid==s->event.dwProcessId)s->threads[j].live=0;
    }
    return 1;
}
static void terminal(STATE *s) {
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION accounting;
    DWORD bytes=0,wait,code;
    if(!s->count||s->exit_count!=s->count||s->blocked){cf(s,RLD_TERMINAL,ERROR_TIMEOUT);return;}
    for(uint32_t i=0;i<s->count;++i){
        for(;;){
            uint64_t now=GetTickCount64();
            DWORD timeout;
            if(now>=s->cleanup_end){cf(s,RLD_DEADLINE,ERROR_TIMEOUT);return;}
            timeout=(DWORD)(s->cleanup_end-now);
            if(timeout>RLD_WAIT_SLICE_MS)timeout=RLD_WAIT_SLICE_MS;
            wait=WaitForSingleObject(s->held[i].process.h,timeout);
            if(wait==WAIT_OBJECT_0){s->candidates[i].signaled=1;break;}
            if(wait==WAIT_FAILED){cf(s,RLD_TERMINAL,GetLastError());return;}
            if(wait!=WAIT_TIMEOUT){cf(s,RLD_TERMINAL,ERROR_INVALID_DATA);return;}
        }
        if(!closure_fresh(s))return;
        code=STILL_ACTIVE;
        if(!GetExitCodeProcess(s->held[i].process.h,&code)){cf(s,RLD_TERMINAL,GetLastError());return;}
        s->candidates[i].process_exit_code=code;
        if(code!=s->candidates[i].exit_event_code){cf(s,RLD_TERMINAL,ERROR_INVALID_DATA);return;}
    }
    for(;;){
        if(!closure_fresh(s))return;
        memset(&accounting,0,sizeof(accounting));
        if(!QueryInformationJobObject(s->job.h,JobObjectBasicAccountingInformation,
                                     &accounting,sizeof(accounting),&bytes)){
            cf(s,RLD_JOB,GetLastError());return;
        }
        if(!accounting.ActiveProcesses){
            if(!inventory(s,0))return;
            s->job_empty=1;s->system_handles_pending=0;return;
        }
        if(accounting.ActiveProcesses>RLD_PROCESS_CAP){cf(s,RLD_JOB,ERROR_INVALID_DATA);return;}
        Sleep(1); /* no alertable wait/APC */
    }
}
static void cleanup(STATE *s) {
    if(s->receiver&&!rwr_retired(s->receiver)){
        s->owned_handles_remaining=slots(s);s->cleanup_complete=0;return;
    }
    if(s->created&&!s->job_empty)terminate(s);
    (void)close_slot(s,&s->event_file);
    if(!s->created||s->job_empty){
        for(uint32_t i=0;i<RLD_PROCESS_CAP;++i){
            (void)close_slot(s,&s->held[i].thread);(void)close_slot(s,&s->held[i].process);
        }
        (void)close_slot(s,&s->pi_thread);(void)close_slot(s,&s->pi_process);
    }
    if(s->attrs_initialized){
        if(closure_fresh(s)){DeleteProcThreadAttributeList(s->attrs);s->attrs_initialized=0;}
    }
    if(s->attrs&&!s->attrs_initialized&&closure_fresh(s)){
        if(!HeapFree(GetProcessHeap(),0,s->attrs))cf(s,RLD_HEAP,ERROR_GEN_FAILURE);
        else s->attrs=NULL;
    }
    if(s->job.h&&!s->created&&closure_fresh(s)&&inventory(s,0))s->job_empty=1;
    if(!s->created||s->job_empty)(void)close_slot(s,&s->job);
    (void)close_slot(s,&s->child_file);(void)close_slot(s,&s->parent_file);
    (void)close_slot(s,&s->node_file);close_crypto(s);
    s->owned_handles_remaining=slots(s);
    s->cleanup_complete=!s->cleanup_stage&&!s->owned_handles_remaining&&!s->attrs&&
      !s->crypto_cleanup_unknown&&(!s->created||(s->job_empty&&s->count&&
      s->exit_count==s->count&&!s->system_handles_pending&&!s->blocked));
}
/* QUERY is point-in-time private data, no token factory. Checks ORIGINAL
 * held process/thread/Job slots; the PID values are internal comparisons only.
 * Both pinned births must be alive and past the declared startup breakpoint.
 */
static DWORD query_live(STATE *s,uint32_t slot) {
    BOOL member;
    FILETIME birth,x,k,u;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
    DWORD bytes=0,n;
    wchar_t image[RLD_PATH_CAP];
    uint64_t stamp;
    if(slot>=RLD_PROCESS_CAP||s->count!=RLD_PROCESS_CAP||s->exit_count||s->blocked||
       s->primary_stage||s->cleanup_stage||!s->pins_verified||!s->resumed||
       InterlockedCompareExchange(&s->stop_requested,0,0))return ERROR_NOT_READY;
    if(!fresh(s))return ERROR_TIMEOUT;
    for(uint32_t i=0;i<RLD_PROCESS_CAP;++i){
        RLD_CANDIDATE *c=&s->candidates[i];
        if(!s->held[i].process.h||!s->held[i].thread.h||!c->image_matches_pin||
           !c->startup_breakpoint_seen||c->exit_seen)return ERROR_NOT_READY;
        if(GetProcessId(s->held[i].process.h)!=c->pid||GetThreadId(s->held[i].thread.h)!=c->initial_tid||
           GetProcessIdOfThread(s->held[i].thread.h)!=c->pid){
            fail(s,RLD_BIRTH,ERROR_INVALID_DATA);return ERROR_INVALID_DATA;
        }
        DWORD wait=WaitForSingleObject(s->held[i].process.h,0);
        if(wait==WAIT_OBJECT_0)return ERROR_NOT_READY;
        if(wait!=WAIT_TIMEOUT){DWORD e=wait==WAIT_FAILED?GetLastError():ERROR_INVALID_DATA;fail(s,RLD_BIRTH,e);return nz(e);}
        wait=WaitForSingleObject(s->held[i].thread.h,0);
        if(wait==WAIT_OBJECT_0)return ERROR_NOT_READY;
        if(wait!=WAIT_TIMEOUT){DWORD e=wait==WAIT_FAILED?GetLastError():ERROR_INVALID_DATA;fail(s,RLD_BIRTH,e);return nz(e);}
        member=FALSE;
        if(!IsProcessInJob(s->held[i].process.h,s->job.h,&member)){DWORD e=GetLastError();fail(s,RLD_BIRTH,e);return nz(e);}
        if(!member){fail(s,RLD_BIRTH,ERROR_INVALID_DATA);return ERROR_INVALID_DATA;}
        if(!GetProcessTimes(s->held[i].process.h,&birth,&x,&k,&u)){DWORD e=GetLastError();fail(s,RLD_BIRTH,e);return nz(e);}
        stamp=((uint64_t)birth.dwHighDateTime<<32)|birth.dwLowDateTime;
        n=RLD_PATH_CAP;
        if(stamp!=c->birth_filetime||!QueryFullProcessImageNameW(s->held[i].process.h,0,image,&n)||
           n>=RLD_PATH_CAP||_wcsicmp(image,s->node_final)!=0){
            fail(s,RLD_BIRTH,ERROR_INVALID_DATA);return ERROR_INVALID_DATA;
        }
    }
    if(!inventory(s,RLD_PROCESS_CAP))return nz(s->primary_error);
    memset(&limits,0,sizeof(limits));
    if(!QueryInformationJobObject(s->job.h,JobObjectExtendedLimitInformation,&limits,sizeof(limits),&bytes)){
        DWORD e=GetLastError();fail(s,RLD_JOB,e);return nz(e);
    }
    if(limits.BasicLimitInformation.LimitFlags!=(JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|
       JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY|JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION)||
       limits.BasicLimitInformation.ActiveProcessLimit!=RLD_PROCESS_CAP||
       limits.ProcessMemoryLimit!=(SIZE_T)256*1024*1024){
        fail(s,RLD_JOB,ERROR_INVALID_DATA);return ERROR_INVALID_DATA;
    }
    if(!fresh(s))return ERROR_CANCELLED;
    return ERROR_SUCCESS;
}

static LONG phase_of(RLD_PRIVATE_CONTEXT *c) { return InterlockedCompareExchange(&c->phase,0,0); }
static int begin_call(RLD_CALL_STATE *o) {
    if(!o||InterlockedCompareExchange(&o->entered,1,0)!=0)return 0;
    o->ok=0;o->error=0;InterlockedExchange(&o->done,0);return 1;
}
static void finish_call(RLD_CALL_STATE *o,int ok,DWORD error) {
    o->ok=ok?1u:0u;o->error=ok?0u:nz(error);MemoryBarrier();InterlockedExchange(&o->done,1);
}
static RLD_PRIVATE_CONTEXT *context_of(RLD_STORAGE *p) {
    RLD_PRIVATE_CONTEXT *c=(RLD_PRIVATE_CONTEXT*)p;
    if(!p||c!=original_context)return NULL;
    if(InterlockedCompareExchange(&c->initialized,0,0)!=1||c->magic!=RLD_MAGIC)return NULL;
    return c;
}
static void snapshot(RLD_PRIVATE_CONTEXT *c,RLD_SNAPSHOT *o,uint32_t slot,int live) {
    STATE *s=&c->s;
    memset(o,0,sizeof(*o));
    o->generation=c->args.generation;o->session_cookie=c->args.session_cookie;
    o->phase=(uint32_t)phase_of(c);o->primary_stage=s->primary_stage;o->primary_error=s->primary_error;
    o->cleanup_stage=s->cleanup_stage;o->cleanup_error=s->cleanup_error;
    o->candidate_count=s->count;o->event_count=s->event_count;o->exit_count=s->exit_count;
    o->owned_handles_remaining=slots(s);o->system_handles_pending=s->system_handles_pending;
    o->job_empty=s->job_empty;o->cleanup_complete=s->cleanup_complete;
    o->worker_returned=(uint32_t)InterlockedCompareExchange(&c->worker_returned,0,0);
    o->stop_requested=(uint32_t)InterlockedCompareExchange(&s->stop_requested,0,0);
    o->query_live=(live&&!o->stop_requested&&o->phase==RLD_RUNNING)?1u:0u;o->slot=slot;
    if(slot<RLD_PROCESS_CAP&&slot<s->count){
        RLD_CANDIDATE *x=&s->candidates[slot];
        o->birth_filetime=x->birth_filetime;o->birth_event_sequence=x->birth_event_sequence;
        o->image_matches_pin=x->image_matches_pin;o->signaled=x->signaled;
        o->job_member=o->query_live;
    }
    /* grants remains zero, no pointer/HANDLE/PID exported */
}
static void complete_command(RLD_PRIVATE_CONTEXT *c,uint32_t i,DWORD error,int live) {
    COMMAND *r=&c->commands[i];
    RLD_COMMAND_OUT *o=r->out;
    if(!o)return;
    snapshot(c,&o->snapshot,r->args.slot,live);
    AcquireSRWLockExclusive(&c->lock);r->state=3;ReleaseSRWLockExclusive(&c->lock);
    finish_call(&o->call,error==ERROR_SUCCESS,error);
}
static int take_query(RLD_PRIVATE_CONTEXT *c,uint32_t i) {
    int taken=0;
    AcquireSRWLockExclusive(&c->lock);
    if(c->commands[i].state==1&&c->commands[i].args.op==RLD_QUERY){
        c->commands[i].state=2;taken=1;
    }
    ReleaseSRWLockExclusive(&c->lock);
    return taken;
}
static void service_queries(RLD_PRIVATE_CONTEXT *c) {
    for(uint32_t i=0;i<RLD_QUERY_CAP;++i){
        DWORD e=ERROR_SUCCESS;
        uint32_t slot;
        if(!take_query(c,i))continue;
        slot=c->commands[i].args.slot;
        if(phase_of(c)!=RLD_RUNNING||InterlockedCompareExchange(&c->s.stop_requested,0,0))
            e=ERROR_OPERATION_ABORTED;
        else if(GetTickCount64()>=c->s.run_end){
            fail(&c->s,RLD_DEADLINE,ERROR_TIMEOUT);InterlockedExchange(&c->s.stop_requested,1);
            e=ERROR_TIMEOUT;
        }else if(slot!=RLD_SLOT_STATUS)e=query_live(&c->s,slot);
        if(GetTickCount64()>=c->s.run_end){
            fail(&c->s,RLD_DEADLINE,ERROR_TIMEOUT);InterlockedExchange(&c->s.stop_requested,1);e=ERROR_TIMEOUT;
        }
        if(InterlockedCompareExchange(&c->s.stop_requested,0,0)&&e==ERROR_SUCCESS)e=ERROR_OPERATION_ABORTED;
        complete_command(c,i,e,e==ERROR_SUCCESS&&slot<RLD_PROCESS_CAP);
    }
}
static void settle_commands(RLD_PRIVATE_CONTEXT *c) {
    for(uint32_t i=0;i<RLD_COMMAND_SLOTS;++i){
        uint32_t state,op;
        AcquireSRWLockExclusive(&c->lock);
        state=c->commands[i].state;op=c->commands[i].args.op;
        if(state==1||state==2)c->commands[i].state=2;
        ReleaseSRWLockExclusive(&c->lock);
        if(state!=1&&state!=2)continue;
        DWORD e=op==RLD_STOP&&c->s.cleanup_complete?ERROR_SUCCESS:ERROR_OPERATION_ABORTED;
        if(op==RLD_STOP&&!c->s.cleanup_complete)e=nz(c->s.cleanup_error);
        complete_command(c,i,e,0);
    }
}
/* Embedded in the unique candidate C after original private command helpers.
 * Fixed registered storage; all HANDLE/OV/buffer ownership remains private.
 */
typedef struct RWR_OP {
    OVERLAPPED ov;
    SLOT event;
    uint32_t active, terminal, producer, cancel_attempted, sequence;
    DWORD transferred, requested, error, cancel_error;
    BOOL native_result;
} RWR_OP;
typedef struct RWR_REQUEST {
    RWR_STATUS_ARGS args;
    RWR_STATUS_OUT *out;
    uint32_t state;
} RWR_REQUEST;
struct RWR_PRIVATE_CONTEXT {
    RLD_PRIVATE_CONTEXT *owner;
    RWR_ARGS args;
    SLOT pipe, token;
    RWR_OP connect, read, write;
    SECURITY_ATTRIBUTES sa;
    SECURITY_DESCRIPTOR sd;
    uint64_t acl_storage[32], token_storage[512], actual_sd_storage[512];
    uint8_t rx[RWR_BODY_CAP+4u], tx[RWR_BODY_CAP+4u], sentinel[1];
    char canonical[RWR_BODY_CAP], generation_string[21];
    wchar_t endpoint[96];
    uint32_t phase, primary_stage, primary_error, cleanup_stage, cleanup_error;
    uint32_t registered, listen_created, connected, peer_match, hello_completed;
    uint32_t ack_issued, ack_completed, authenticated, revoked, retired, unknown;
    uint32_t started, rx_used, rx_required, tx_used, tx_bytes, sentinel_issued;
    uint32_t hello_wire_bytes, ack_wire_bytes;
    DWORD peer_pid, held_pid, token_bytes, actual_sd_bytes, handle_flags;
    DWORD acl_bytes, acl_revision, ace_count;
    BOOL native_bool, dacl_present, dacl_defaulted;
    PACL actual_dacl;
    void *actual_ace;
    SECURITY_DESCRIPTOR_CONTROL actual_control;
    DWORD actual_revision;
    uint64_t birth_filetime;
    uint32_t birth_event_sequence;
    uint32_t peer_compare_attempted, peer_compare_match, peer_bracket_before, peer_bracket_after;
    RWR_REQUEST requests[RWR_STATUS_CAP];
};
_Static_assert(sizeof(RWR_PRIVATE_CONTEXT)<=RWR_CONTEXT_BYTES &&
               _Alignof(RWR_PRIVATE_CONTEXT)<=8,"receiver private storage fits");
static uint32_t rwr_slots(const RWR_PRIVATE_CONTEXT *r) {
    if(!r)return 0;
    return (r->pipe.h!=NULL)+(r->token.h!=NULL)+(r->connect.event.h!=NULL)+
        (r->read.event.h!=NULL)+(r->write.event.h!=NULL);
}
static int rwr_retired(const RWR_PRIVATE_CONTEXT *r) { return !r||r->retired; }
static void rwr_primary(RWR_PRIVATE_CONTEXT *r,uint32_t stage,DWORD error) {
    if(!r->primary_stage){r->primary_stage=stage;r->primary_error=nz(error);}
    fail(&r->owner->s,stage,error); /* first original P survives */
}
static void rwr_cleanup_error(RWR_PRIVATE_CONTEXT *r,uint32_t stage,DWORD error) {
    if(!r->cleanup_stage){r->cleanup_stage=stage;r->cleanup_error=nz(error);}
    cf(&r->owner->s,stage,error); /* separate original F survives */
}
static int rwr_token(const char *v,size_t cap,int hex) {
    size_t n=0;
    while(n<cap&&v[n]){
        unsigned char b=(unsigned char)v[n];
        if(hex){if(!((b>='0'&&b<='9')||(b>='a'&&b<='f')))return 0;}
        else if(!((b>='A'&&b<='Z')||(b>='a'&&b<='z')||(b>='0'&&b<='9')||
                  b=='.'||b=='_'||b=='-'))return 0;
        ++n;
    }
    return n>0&&n<cap;
}
static unsigned rwr_hex(unsigned char b) { return b<='9'?(unsigned)(b-'0'):(unsigned)(b-'a')+10u; }
static int rwr_args_ok(const RLD_PRIVATE_CONTEXT *c,const RWR_ARGS *a) {
    char hello[RWR_BODY_CAP], generation[21];
    int n,k;
    uint32_t zero=a->reserved0;
    if(a->magic!=RWR_MAGIC||a->version!=RWR_VERSION||a->size_bytes!=sizeof(*a)||
       a->generation!=c->args.generation||a->session_cookie!=c->args.session_cookie||
       a->run_until_tick_ms!=c->args.run_until_tick_ms||
       a->closure_until_tick_ms!=c->args.closure_until_tick_ms||
       a->expected_slot>=RLD_PROCESS_CAP||a->pipe_access_mask!=RWR_PIPE_ACCESS_MASK||
       a->sid_bytes<8u||a->sid_bytes>RWR_SID_CAP||a->expected_current_user_sid[0]!=1u||
       a->expected_current_user_sid[1]>15u||
       a->sid_bytes!=8u+4u*a->expected_current_user_sid[1]||
       !rwr_token(a->instance,sizeof(a->instance),1)||strlen(a->instance)!=32u||
       !rwr_token(a->nonce,sizeof(a->nonce),1)||strlen(a->nonce)!=32u||
       !rwr_token(a->run,sizeof(a->run),0)||
       !rwr_token(a->source_copy_pin,sizeof(a->source_copy_pin),1)||strlen(a->source_copy_pin)!=64u)
        return 0;
    for(size_t i=a->sid_bytes;i<RWR_SID_CAP;++i)zero|=a->expected_current_user_sid[i];
    for(size_t i=0;i<3u;++i)zero|=a->reserved_bytes[i];
    for(size_t i=0;i<8u;++i)zero|=a->reserved[i];
    for(size_t i=0;i<32u;++i)
        if((rwr_hex((unsigned char)a->source_copy_pin[2*i])<<4|
            rwr_hex((unsigned char)a->source_copy_pin[2*i+1]))!=c->args.parent_sha256[i])return 0;
    k=snprintf(generation,sizeof(generation),"%llu",(unsigned long long)a->generation);
    if(k<1||(size_t)k>=sizeof(generation)||
       memcmp(a->generation_text,generation,(size_t)k+1u)!=0)return 0;
    for(size_t i=(size_t)k+1u;i<sizeof(a->generation_text);++i)zero|=(uint8_t)a->generation_text[i];
    n=snprintf(hello,sizeof(hello),
       "{\"schema\":\"root-main-witness-control/1\",\"kind\":\"hello\",\"instance\":\"%s\","
       "\"nonce\":\"%s\",\"run\":\"%s\",\"generation\":\"%s\",\"sourceCopyPin\":\"%s\"}",
       a->instance,a->nonce,a->run,a->generation_text,a->source_copy_pin);
    if(n<1||(size_t)n>=sizeof(hello)||a->hello_bytes!=(uint32_t)n||
       memcmp(a->hello,hello,(size_t)n)!=0)return 0;
    for(size_t i=a->hello_bytes;i<RWR_BODY_CAP;++i)zero|=a->hello[i];
    return zero==0;
}
/* Frozen environment is built before CreateProcess. Child fixture receives no
 * witness values because the pinned parent supplies the original child env.
 */
static int rwr_environment(RWR_PRIVATE_CONTEXT *r,wchar_t *env,size_t cap,size_t used) {
    static const char *const keys[]={"RWR_INSTANCE=","RWR_NONCE=","RWR_RUN=",
                                    "RWR_GENERATION=","RWR_SOURCE_PIN="};
    const char *values[5];
    if(!r)return 1;
    values[0]=r->args.instance;values[1]=r->args.nonce;values[2]=r->args.run;
    values[3]=r->args.generation_text;values[4]=r->args.source_copy_pin;
    for(size_t i=0;i<5u;++i){
        size_t a=strlen(keys[i]),b=strlen(values[i]);
        if(used+a+b+2u>cap)return 0;
        for(size_t j=0;j<a;++j)env[used++]=(wchar_t)(unsigned char)keys[i][j];
        for(size_t j=0;j<b;++j)env[used++]=(wchar_t)(unsigned char)values[i][j];
        env[used++]=0;
    }
    env[used]=0;return 1;
}
/* Short issuance gate: register before any possible effect, release before API.
 * STOP uses the same original lock. Once issued, completion may be cleanup-only.
 */
static int rwr_begin_effect(RWR_PRIVATE_CONTEXT *r) {
    RLD_PRIVATE_CONTEXT *c=r->owner;
    int admitted=0;
    AcquireSRWLockExclusive(&c->lock);
    if(!r->revoked&&!InterlockedCompareExchange(&c->s.stop_requested,0,0)&&
       !c->s.primary_stage&&!c->s.cleanup_stage&&GetTickCount64()<c->s.run_end)
        admitted=1;
    ReleaseSRWLockExclusive(&c->lock);return admitted;
}
static int rwr_begin_io(RWR_PRIVATE_CONTEXT *r,RWR_OP *op,DWORD size) {
    RLD_PRIVATE_CONTEXT *c=r->owner;
    int admitted=0;
    if(op->active&&(!op->terminal||op->producer))return 0;
    memset(&op->ov,0,sizeof(op->ov));op->ov.hEvent=op->event.h;
    AcquireSRWLockExclusive(&c->lock);
    if(!r->revoked&&!InterlockedCompareExchange(&c->s.stop_requested,0,0)&&
       !c->s.primary_stage&&!c->s.cleanup_stage&&GetTickCount64()<c->s.run_end){
        op->active=1;op->terminal=0;op->producer=1;op->cancel_attempted=0;
        op->transferred=0;op->requested=size;op->error=0;op->cancel_error=0;
        op->native_result=FALSE;++op->sequence;admitted=1;
    }
    ReleaseSRWLockExclusive(&c->lock);return admitted;
}
static void rwr_io_return(RWR_OP *op,BOOL result,DWORD error,int connect) {
    op->native_result=result;
    if(result||(connect&&error==ERROR_PIPE_CONNECTED)){
        op->terminal=1;op->error=ERROR_SUCCESS;
    }else if(error!=ERROR_IO_PENDING){op->terminal=1;op->error=nz(error);}
    op->producer=0;
}
static void rwr_poll(RWR_PRIVATE_CONTEXT *r,RWR_OP *op) {
    DWORD error;
    if(!op->active||op->terminal||op->producer)return;
    op->native_result=GetOverlappedResult(r->pipe.h,&op->ov,&op->transferred,FALSE);
    if(op->native_result){op->terminal=1;op->error=ERROR_SUCCESS;return;}
    error=GetLastError();
    if(error==ERROR_IO_INCOMPLETE||error==ERROR_IO_PENDING)return;
    op->terminal=1;op->error=nz(error); /* ABORTED and failed completion are terminal */
}
static int rwr_noninherit(RWR_PRIVATE_CONTEXT *r,SLOT *slot,uint32_t stage) {
    if(!rwr_begin_effect(r))return 0;
    r->handle_flags=0;
    if(!GetHandleInformation(slot->h,&r->handle_flags)){
        rwr_primary(r,stage,GetLastError());return 0;
    }
    if(r->handle_flags&HANDLE_FLAG_INHERIT){rwr_primary(r,stage,ERROR_INVALID_DATA);return 0;}
    return 1;
}
static int rwr_create_event(RWR_PRIVATE_CONTEXT *r,RWR_OP *op) {
    if(!rwr_begin_effect(r))return 0;
    op->event.h=CreateEventW(NULL,TRUE,FALSE,NULL);
    if(!op->event.h){rwr_primary(r,RWR_EVENT,GetLastError());return 0;}
    return rwr_noninherit(r,&op->event,RWR_EVENT);
}
static int rwr_create(RWR_PRIVATE_CONTEXT *r) {
    TOKEN_USER *user=(TOKEN_USER*)r->token_storage;
    ACL_SIZE_INFORMATION ai;
    ACCESS_ALLOWED_ACE *ace;
    STATE *s=&r->owner->s;
    r->started=1;
    if(!rwr_begin_effect(r))return 0;
    if(!OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&r->token.h)){
        rwr_primary(r,RWR_SECURITY,GetLastError());return 0;
    }
    if(!rwr_noninherit(r,&r->token,RWR_SECURITY)||!rwr_begin_effect(r))return 0;
    if(!GetTokenInformation(r->token.h,TokenUser,r->token_storage,sizeof(r->token_storage),&r->token_bytes)){
        rwr_primary(r,RWR_SECURITY,GetLastError());return 0;
    }
    if(!IsValidSid(user->User.Sid)||!IsValidSid(r->args.expected_current_user_sid)||
       GetLengthSid(user->User.Sid)!=r->args.sid_bytes||
       !EqualSid(user->User.Sid,r->args.expected_current_user_sid)){
        rwr_primary(r,RWR_SECURITY,ERROR_ACCESS_DENIED);return 0;
    }
    if(!close_slot(s,&r->token)){rwr_cleanup_error(r,RWR_CLOSE,s->cleanup_error);return 0;}
    if(!rwr_begin_effect(r))return 0;
    if(!InitializeSecurityDescriptor(&r->sd,SECURITY_DESCRIPTOR_REVISION)||
       !InitializeAcl((PACL)r->acl_storage,sizeof(r->acl_storage),ACL_REVISION)||
       !AddAccessAllowedAceEx((PACL)r->acl_storage,ACL_REVISION,0,r->args.pipe_access_mask,
                            r->args.expected_current_user_sid)||
       !SetSecurityDescriptorDacl(&r->sd,TRUE,(PACL)r->acl_storage,FALSE)||
       !SetSecurityDescriptorControl(&r->sd,SE_DACL_PROTECTED,SE_DACL_PROTECTED)){
        rwr_primary(r,RWR_SECURITY,GetLastError());return 0;
    }
    r->sa.nLength=sizeof(r->sa);r->sa.lpSecurityDescriptor=&r->sd;r->sa.bInheritHandle=FALSE;
    if(!rwr_create_event(r,&r->connect)||!rwr_create_event(r,&r->read)||
       !rwr_create_event(r,&r->write)||!rwr_begin_effect(r))return 0;
    r->pipe.h=CreateNamedPipeW(r->endpoint,PIPE_ACCESS_DUPLEX|FILE_FLAG_OVERLAPPED|
        FILE_FLAG_FIRST_PIPE_INSTANCE,PIPE_TYPE_BYTE|PIPE_READMODE_BYTE|PIPE_WAIT|
        PIPE_REJECT_REMOTE_CLIENTS,1,RWR_BODY_CAP+4u,RWR_BODY_CAP+4u,0,&r->sa);
    if(r->pipe.h==INVALID_HANDLE_VALUE){DWORD e=GetLastError();r->pipe.h=NULL;rwr_primary(r,RWR_PIPE,e);return 0;}
    r->listen_created=1;
    if(!rwr_noninherit(r,&r->pipe,RWR_PIPE)||!rwr_begin_effect(r))return 0;
    if(!GetKernelObjectSecurity(r->pipe.h,DACL_SECURITY_INFORMATION,
        r->actual_sd_storage,sizeof(r->actual_sd_storage),&r->actual_sd_bytes)||
       !GetSecurityDescriptorControl(r->actual_sd_storage,&r->actual_control,&r->actual_revision)||
       !GetSecurityDescriptorDacl(r->actual_sd_storage,&r->dacl_present,&r->actual_dacl,&r->dacl_defaulted)){
        rwr_primary(r,RWR_SECURITY,GetLastError());return 0;
    }
    memset(&ai,0,sizeof(ai));
    if(!r->dacl_present||!r->actual_dacl||r->dacl_defaulted||
       !(r->actual_control&SE_DACL_PROTECTED)||
       !GetAclInformation(r->actual_dacl,&ai,sizeof(ai),AclSizeInformation)||ai.AceCount!=1u||
       !GetAce(r->actual_dacl,0,&r->actual_ace)){
        rwr_primary(r,RWR_SECURITY,ERROR_INVALID_DATA);return 0;
    }
    r->ace_count=ai.AceCount;r->acl_bytes=ai.AclBytesInUse;r->acl_revision=r->actual_dacl->AclRevision;
    ace=(ACCESS_ALLOWED_ACE*)r->actual_ace;
    if(ace->Header.AceType!=ACCESS_ALLOWED_ACE_TYPE||ace->Header.AceFlags||
       ace->Mask!=r->args.pipe_access_mask||!IsValidSid(&ace->SidStart)||
       !EqualSid(&ace->SidStart,r->args.expected_current_user_sid)){
        rwr_primary(r,RWR_SECURITY,ERROR_ACCESS_DENIED);return 0;
    }
    r->phase=RWR_LISTENING;
    if(!rwr_begin_io(r,&r->connect,0))return 0;
    if(!ResetEvent(r->connect.event.h)){
        DWORD e=GetLastError();rwr_io_return(&r->connect,FALSE,e,0);
        rwr_primary(r,RWR_CONNECT,e);return 0;
    }
    r->native_bool=ConnectNamedPipe(r->pipe.h,&r->connect.ov);
    rwr_io_return(&r->connect,r->native_bool,r->native_bool?0:GetLastError(),1);
    return 1;
}
/* query_live independently brackets the original generation/cookie, exact
 * CREATE birth, held FILETIME/image/Job and process/thread WAIT_TIMEOUT facts.
 * Kernel peer PID is written to private registered storage and compared only
 * with GetProcessId(ORIGINAL held expected slot). No PID-open/adoption exists.
 */
static DWORD rwr_peer(RWR_PRIVATE_CONTEXT *r) {
    RLD_PRIVATE_CONTEXT *c=r->owner;
    STATE *s=&c->s;
    RLD_CANDIDATE *birth;
    DWORD e;
    if(!r->connected||!r->pipe.h||r->revoked||r->args.generation!=c->args.generation||
       r->args.session_cookie!=c->args.session_cookie||GetTickCount64()>=s->run_end)
        return ERROR_OPERATION_ABORTED;
    e=query_live(s,r->args.expected_slot);if(e)return e;
    birth=&s->candidates[r->args.expected_slot];
    if(r->birth_filetime&&(r->birth_filetime!=birth->birth_filetime||
       r->birth_event_sequence!=birth->birth_event_sequence))return ERROR_INVALID_DATA;
    r->birth_filetime=birth->birth_filetime;r->birth_event_sequence=birth->birth_event_sequence;
    r->peer_bracket_before=1;r->peer_bracket_after=0;
    if(!rwr_begin_effect(r))return ERROR_OPERATION_ABORTED;
    r->peer_pid=0;r->held_pid=0;
    if(!GetNamedPipeClientProcessId(r->pipe.h,&r->peer_pid))return nz(GetLastError());
    r->held_pid=GetProcessId(s->held[r->args.expected_slot].process.h);
    if(!r->held_pid)return nz(GetLastError());
    e=query_live(s,r->args.expected_slot);if(e)return e;
    r->peer_bracket_after=1;r->peer_compare_attempted=1;
    r->peer_compare_match=r->peer_pid==r->held_pid&&r->held_pid==birth->pid;
    if(r->args.generation!=c->args.generation||r->args.session_cookie!=c->args.session_cookie||
       r->birth_filetime!=s->candidates[r->args.expected_slot].birth_filetime||
       r->birth_event_sequence!=s->candidates[r->args.expected_slot].birth_event_sequence)
        return ERROR_INVALID_DATA;
    if(!r->peer_compare_match)return ERROR_ACCESS_DENIED;
    r->peer_match=1;return ERROR_SUCCESS;
}
static int rwr_read_issue(RWR_PRIVATE_CONTEXT *r,uint8_t *buffer,DWORD size) {
    if(!size||size>RWR_CHUNK_CAP||!rwr_begin_io(r,&r->read,size))return 0;
    if(!ResetEvent(r->read.event.h)){
        rwr_io_return(&r->read,FALSE,GetLastError(),0);return 0;
    }
    r->native_bool=ReadFile(r->pipe.h,buffer,size,&r->read.transferred,&r->read.ov);
    rwr_io_return(&r->read,r->native_bool,r->native_bool?0:GetLastError(),0);return 1;
}
static int rwr_write_issue(RWR_PRIVATE_CONTEXT *r) {
    DWORD size=r->tx_bytes-r->tx_used;
    if(!size||size>RWR_CHUNK_CAP||!rwr_begin_io(r,&r->write,size))return 0;
    r->ack_issued=1;
    if(!ResetEvent(r->write.event.h)){
        rwr_io_return(&r->write,FALSE,GetLastError(),0);return 0;
    }
    r->native_bool=WriteFile(r->pipe.h,r->tx+r->tx_used,size,&r->write.transferred,&r->write.ov);
    rwr_io_return(&r->write,r->native_bool,r->native_bool?0:GetLastError(),0);return 1;
}
static int rwr_ack_build(RWR_PRIVATE_CONTEXT *r) {
    uint64_t now=GetTickCount64(),remaining;
    int n;
    if(now>=r->owner->s.run_end)return 0;
    remaining=r->owner->s.run_end-now;
    if(!remaining||remaining>RLD_MAX_RUN_MS)return 0;
    n=snprintf((char*)r->tx+4,RWR_BODY_CAP,
       "{\"schema\":\"root-main-witness-control/1\",\"kind\":\"ack\",\"instance\":\"%s\","
       "\"nonce\":\"%s\",\"run\":\"%s\",\"generation\":\"%s\",\"sourceCopyPin\":\"%s\",\"remainingMs\":%u}",
       r->args.instance,r->args.nonce,r->args.run,r->args.generation_text,r->args.source_copy_pin,
       (unsigned)remaining);
    if(n<1||(uint32_t)n>=RWR_BODY_CAP)return 0;
    r->tx[0]=(uint8_t)n;r->tx[1]=(uint8_t)((uint32_t)n>>8);
    r->tx[2]=(uint8_t)((uint32_t)n>>16);r->tx[3]=(uint8_t)((uint32_t)n>>24);
    r->tx_bytes=(uint32_t)n+4u;r->tx_used=0;return 1;
}
static void rwr_revoke(RWR_PRIVATE_CONTEXT *r) {
    RLD_PRIVATE_CONTEXT *c=r->owner;
    AcquireSRWLockExclusive(&c->lock);
    r->revoked=1;r->authenticated=0;
    if(!r->retired&&!r->unknown)r->phase=RWR_REVOKED;
    InterlockedExchange(&c->s.stop_requested,1);
    ReleaseSRWLockExclusive(&c->lock);
}
static void rwr_cancel(RWR_PRIVATE_CONTEXT *r,RWR_OP *op) {
    if(!op->active||op->terminal||op->producer||op->cancel_attempted)return;
    op->cancel_attempted=1;
    op->native_result=CancelIoEx(r->pipe.h,&op->ov);
    op->cancel_error=op->native_result?0:GetLastError();
    if(!op->native_result&&op->cancel_error!=ERROR_NOT_FOUND)
        rwr_cleanup_error(r,RWR_CANCEL,op->cancel_error);
    /* Success/NOT_FOUND is NOT terminal. rwr_poll alone observes completion. */
}
static int rwr_io_ended(const RWR_OP *op) {
    return !op->active||(op->terminal&&!op->producer);
}
static int rwr_close(RWR_PRIVATE_CONTEXT *r,SLOT *slot) {
    DWORD e;
    if(!slot->h)return 1;
    if(slot->close_attempted)return 0;
    if(GetTickCount64()>=r->owner->s.cleanup_end){rwr_cleanup_error(r,RWR_DEADLINE,ERROR_TIMEOUT);return 0;}
    slot->close_attempted=1;
    if(CloseHandle(slot->h)){slot->h=NULL;return 1;}
    e=GetLastError();rwr_cleanup_error(r,RWR_CLOSE,e);return 0;
}
static void rwr_cleanup(RWR_PRIVATE_CONTEXT *r) {
    if(!r||r->retired)return;
    if(!r->revoked)rwr_revoke(r); /* tombstone precedes Cancel/Close */
    if(GetTickCount64()>=r->owner->s.cleanup_end){
        r->unknown=1;r->phase=RWR_UNKNOWN;rwr_cleanup_error(r,RWR_DEADLINE,ERROR_TIMEOUT);return;
    }
    rwr_cancel(r,&r->connect);rwr_cancel(r,&r->read);rwr_cancel(r,&r->write);
    rwr_poll(r,&r->connect);rwr_poll(r,&r->read);rwr_poll(r,&r->write);
    if(!rwr_io_ended(&r->connect)||!rwr_io_ended(&r->read)||!rwr_io_ended(&r->write))return;
    if(r->cleanup_stage){r->unknown=1;r->phase=RWR_UNKNOWN;return;}
    if(!rwr_close(r,&r->pipe)||!rwr_close(r,&r->connect.event)||
       !rwr_close(r,&r->read.event)||!rwr_close(r,&r->write.event)||!rwr_close(r,&r->token)){
        r->unknown=1;r->phase=RWR_UNKNOWN;return;
    }
    r->retired=1;r->phase=RWR_RETIRED;
    /* Buffers stay in registered storage until Root externally joins worker.
     * No storage free/unload/scrub is attempted in this native worker. */
}
static void rwr_service(RWR_PRIVATE_CONTEXT *r) {
    STATE *s;
    DWORD e;
    if(!r||r->retired)return;
    s=&r->owner->s;
    if(r->revoked||InterlockedCompareExchange(&s->stop_requested,0,0)||s->primary_stage||s->cleanup_stage){
        rwr_cleanup(r);return;
    }
    if(GetTickCount64()>=s->run_end){rwr_primary(r,RWR_DEADLINE,ERROR_TIMEOUT);rwr_cleanup(r);return;}
    if(!r->started)return;
    rwr_poll(r,&r->connect);
    if(!r->connect.terminal)return;
    if(r->connect.error){rwr_primary(r,RWR_CONNECT,r->connect.error);rwr_cleanup(r);return;}
    if(!r->connected){r->connected=1;r->phase=RWR_CONNECTED;r->rx_required=4;}
    e=rwr_peer(r);
    if(e==ERROR_NOT_READY&&!r->peer_match)return; /* no HELLO read before both exact births are live */
    if(e){rwr_primary(r,RWR_PEER,e);rwr_cleanup(r);return;}
    if(!r->hello_completed){
        rwr_poll(r,&r->read);
        if(r->read.active&&!r->read.terminal)return;
        if(r->read.active){
            if(r->read.error||!r->read.transferred||r->read.transferred>r->read.requested){
                rwr_primary(r,RWR_READ,r->read.error?r->read.error:ERROR_BROKEN_PIPE);rwr_cleanup(r);return;
            }
            r->rx_used+=r->read.transferred;r->hello_wire_bytes+=r->read.transferred;
            r->read.active=0;
            e=rwr_peer(r);if(e){rwr_primary(r,RWR_PEER,e);rwr_cleanup(r);return;}
        }
        if(r->rx_used==4u&&r->rx_required==4u){
            uint32_t size=(uint32_t)r->rx[0]|((uint32_t)r->rx[1]<<8)|
                         ((uint32_t)r->rx[2]<<16)|((uint32_t)r->rx[3]<<24);
            if(!size||size>RWR_BODY_CAP||size!=r->args.hello_bytes){
                rwr_primary(r,RWR_HELLO_BYTES,ERROR_INVALID_DATA);rwr_cleanup(r);return;
            }
            r->rx_required=size+4u;
        }
        if(r->rx_used<r->rx_required){
            (void)rwr_read_issue(r,r->rx+r->rx_used,r->rx_required-r->rx_used);return;
        }
        if(r->rx_used!=r->rx_required||memcmp(r->rx+4,r->args.hello,r->args.hello_bytes)){
            rwr_primary(r,RWR_HELLO_BYTES,ERROR_INVALID_DATA);rwr_cleanup(r);return;
        }
        e=rwr_peer(r);if(e){rwr_primary(r,RWR_PEER,e);rwr_cleanup(r);return;}
        r->hello_completed=1;r->phase=RWR_HELLO;
        if(!rwr_ack_build(r)){rwr_primary(r,RWR_DEADLINE,ERROR_TIMEOUT);rwr_cleanup(r);return;}
        r->phase=RWR_ACK;
        (void)rwr_write_issue(r);return;
    }
    if(!r->ack_completed){
        rwr_poll(r,&r->write);
        if(!r->write.active||!r->write.terminal)return;
        if(r->write.error||!r->write.transferred||r->write.transferred>r->write.requested){
            rwr_primary(r,RWR_WRITE,r->write.error?r->write.error:ERROR_INVALID_DATA);rwr_cleanup(r);return;
        }
        r->tx_used+=r->write.transferred;r->ack_wire_bytes+=r->write.transferred;r->write.active=0;
        e=rwr_peer(r);if(e){rwr_primary(r,RWR_PEER,e);rwr_cleanup(r);return;}
        if(r->tx_used<r->tx_bytes){(void)rwr_write_issue(r);return;}
        if(r->tx_used!=r->tx_bytes){rwr_primary(r,RWR_WRITE,ERROR_INVALID_DATA);rwr_cleanup(r);return;}
        r->ack_completed=1;
        AcquireSRWLockExclusive(&r->owner->lock);
        if(!r->revoked&&!InterlockedCompareExchange(&s->stop_requested,0,0)&&
           !s->primary_stage&&!s->cleanup_stage&&GetTickCount64()<s->run_end){
            r->authenticated=1;r->phase=RWR_AUTHENTICATED;
        }
        ReleaseSRWLockExclusive(&r->owner->lock);
        if(!r->authenticated){rwr_cleanup(r);return;}
    }
    /* HELLO+ACK is the entire contract. A one-byte sentinel observes EOF or any
     * trailing/causal frame; it cannot admit a third frame or selection data. */
    if(!r->sentinel_issued){
        if(rwr_read_issue(r,r->sentinel,1))r->sentinel_issued=1;
        return;
    }
    rwr_poll(r,&r->read);
    if(r->read.terminal){
        rwr_primary(r,r->read.error?RWR_READ:RWR_EXTRA_DATA,
                    r->read.error?r->read.error:ERROR_INVALID_DATA);rwr_cleanup(r);
    }
}
static void rwr_status_copy(RWR_PRIVATE_CONTEXT *r,RWR_STATUS *o,uint32_t index) {
    STATE *s=&r->owner->s;
    memset(o,0,sizeof(*o));
    o->generation=r->args.generation;o->session_cookie=r->args.session_cookie;o->phase=r->phase;
    o->primary_stage=r->primary_stage;o->primary_error=r->primary_error;
    o->cleanup_stage=r->cleanup_stage;o->cleanup_error=r->cleanup_error;
    o->expected_slot=r->args.expected_slot;o->registered=r->registered;o->listen_created=r->listen_created;
    o->connected=r->connected;o->peer_match=r->peer_match;o->hello_completed=r->hello_completed;
    o->ack_issued=r->ack_issued;o->ack_completed=r->ack_completed;
    o->revoked=r->revoked||(uint32_t)InterlockedCompareExchange(&s->stop_requested,0,0);
    o->authenticated=r->authenticated&&!o->revoked&&GetTickCount64()<s->run_end;
    o->io_pending=(r->connect.active&&!r->connect.terminal)+(r->read.active&&!r->read.terminal)+
                  (r->write.active&&!r->write.terminal);
    o->producer_pending=r->connect.producer+r->read.producer+r->write.producer;
    o->io_terminal=rwr_io_ended(&r->connect)&&rwr_io_ended(&r->read)&&rwr_io_ended(&r->write);
    o->retired=r->retired;o->owned_handles_remaining=rwr_slots(r);o->unknown=r->unknown;
    o->hello_wire_bytes=r->hello_wire_bytes;o->ack_wire_bytes=r->ack_wire_bytes;o->status_index=index;
    o->birth_filetime=r->birth_filetime;o->birth_event_sequence=r->birth_event_sequence;
    o->client_pid=r->peer_pid;o->expected_held_pid=r->held_pid;
    o->peer_compare_attempted=r->peer_compare_attempted;o->peer_compare_match=r->peer_compare_match;
    o->peer_bracket_before=r->peer_bracket_before;o->peer_bracket_after=r->peer_bracket_after;
}
static void rwr_status_service(RWR_PRIVATE_CONTEXT *r,int final) {
    if(!r)return;
    for(uint32_t i=0;i<RWR_STATUS_CAP;++i){
        RWR_REQUEST *request=&r->requests[i];RWR_STATUS_OUT *out;
        int taken=0;
        AcquireSRWLockExclusive(&r->owner->lock);
        if(request->state==1){request->state=2;taken=1;}
        ReleaseSRWLockExclusive(&r->owner->lock);
        if(!taken)continue;
        out=request->out;rwr_status_copy(r,&out->status,i);
        AcquireSRWLockExclusive(&r->owner->lock);request->state=3;ReleaseSRWLockExclusive(&r->owner->lock);
        finish_call(&out->call,!final,final?ERROR_OPERATION_ABORTED:0);
    }
}
RLD_EXPORT void WINAPI rwr_abi(uint32_t out[RWR_ABI_WORDS]) {
    static const uint32_t words[RWR_ABI_WORDS]={1,8,RWR_CONTEXT_BYTES,8,sizeof(RWR_ARGS),
        sizeof(RWR_STATUS_ARGS),sizeof(RWR_STATUS_OUT),sizeof(RWR_STATUS),sizeof(RLD_CALL_STATE),
        RWR_BODY_CAP,RWR_CHUNK_CAP,RWR_FRAME_CAP,RWR_STATUS_CAP};
    if(out)memcpy(out,words,sizeof(words));
}
RLD_EXPORT void WINAPI rwr_register(RLD_STORAGE *original,RWR_STORAGE *receiver,
                                  const RWR_ARGS *args,RLD_CALL_STATE *out) {
    RLD_PRIVATE_CONTEXT *c;
    RWR_PRIVATE_CONTEXT *r=(RWR_PRIVATE_CONTEXT*)receiver;
    RWR_ARGS copied;
    DWORD error=ERROR_INVALID_PARAMETER;
    if(!begin_call(out))return;
    c=context_of(original);
    if(!c||!receiver||((uintptr_t)receiver&7u)||!args||receiver==(RWR_STORAGE*)original)goto rejected;
    copied=*args;
    if(!rwr_args_ok(c,&copied))goto rejected;
    AcquireSRWLockExclusive(&c->lock);
    if(c->s.receiver||phase_of(c)!=RLD_REGISTERED||InterlockedCompareExchange(&c->run_claimed,0,0)){
        error=ERROR_INVALID_STATE;goto unlock_rejected;
    }
    if(InterlockedCompareExchange(&c->s.stop_requested,0,0)||GetTickCount64()>=c->s.run_end){
        error=ERROR_OPERATION_ABORTED;goto unlock_rejected;
    }
    memset(receiver,0,sizeof(*receiver));r->owner=c;r->args=copied;
    r->registered=1;r->phase=RWR_REGISTERED;
    {
        const wchar_t prefix[]=L"\\\\.\\pipe\\rentgen-main-witness-";
        size_t n=sizeof(prefix)/sizeof(prefix[0])-1u;
        memcpy(r->endpoint,prefix,n*sizeof(wchar_t));
        for(size_t i=0;i<32u;++i)r->endpoint[n+i]=(wchar_t)(unsigned char)copied.instance[i];
        r->endpoint[n+32u]=0;
    }
    c->s.receiver=r; /* original pair + all output/buffer/OV slots published before effects */
    ReleaseSRWLockExclusive(&c->lock);finish_call(out,1,0);return;
unlock_rejected:
    ReleaseSRWLockExclusive(&c->lock);
rejected:
    finish_call(out,0,error);
}
RLD_EXPORT void WINAPI rwr_submit_status(RLD_STORAGE *original,RWR_STORAGE *receiver,
                                       const RWR_STATUS_ARGS *args,RWR_STATUS_OUT *out) {
    RLD_PRIVATE_CONTEXT *c;
    RWR_PRIVATE_CONTEXT *r=(RWR_PRIVATE_CONTEXT*)receiver;
    RWR_STATUS_ARGS request;
    DWORD error=ERROR_INVALID_PARAMETER;
    LONG phase;
    if(!out||!begin_call(&out->call))return;
    memset(&out->status,0,sizeof(out->status));out->command_index=UINT64_MAX;
    InterlockedExchange(&out->submit_done,0);InterlockedExchange(&out->accepted,0);
    c=context_of(original);
    if(!c||!r||c->s.receiver!=r||!args)goto rejected;
    request=*args;
    if(request.reserved||request.index>=RWR_STATUS_CAP||request.generation!=c->args.generation||
       request.session_cookie!=c->args.session_cookie)goto rejected;
    AcquireSRWLockExclusive(&c->lock);phase=phase_of(c);
    if(r->requests[request.index].state){error=ERROR_ALREADY_EXISTS;goto unlock_rejected;}
    if(phase<RLD_STARTING||phase>RLD_STOPPING||InterlockedCompareExchange(&c->worker_returned,0,0)){
        error=ERROR_INVALID_STATE;goto unlock_rejected;
    }
    if(GetTickCount64()>=c->s.cleanup_end){error=ERROR_TIMEOUT;goto unlock_rejected;}
    r->requests[request.index].args=request;r->requests[request.index].out=out;
    out->command_index=request.index;InterlockedExchange(&out->accepted,1);
    InterlockedExchange(&out->submit_done,1);MemoryBarrier();r->requests[request.index].state=1;
    ReleaseSRWLockExclusive(&c->lock);return;
unlock_rejected:
    ReleaseSRWLockExclusive(&c->lock);
rejected:
    InterlockedExchange(&out->submit_done,1);finish_call(&out->call,0,error);
}

RLD_EXPORT void WINAPI rld_abi(uint32_t out[RLD_ABI_WORDS]) {
    static const uint32_t words[RLD_ABI_WORDS]={
        1,8,65536,8,sizeof(RLD_ARGS),sizeof(RLD_CLOCK_OUT),sizeof(RLD_CALL_STATE),
        sizeof(RLD_COMMAND_ARGS),sizeof(RLD_COMMAND_OUT),sizeof(RLD_SNAPSHOT),sizeof(RLD_RUN_OUT),sizeof(RLD_EVENT)
    };
    if(out)memcpy(out,words,sizeof(words));
}
RLD_EXPORT void WINAPI rld_clock(RLD_CLOCK_OUT *out) {
    if(!out||!begin_call(&out->call))return;
    out->tick_ms=GetTickCount64();finish_call(&out->call,1,0);
}
RLD_EXPORT void WINAPI rld_init(RLD_STORAGE *storage,const RLD_ARGS *args,RLD_CALL_STATE *out) {
    RLD_PRIVATE_CONTEXT *c=(RLD_PRIVATE_CONTEXT*)storage;
    RLD_ARGS copied;
    uint64_t now;
    if(!begin_call(out))return;
    if(!storage||((uintptr_t)storage&7u)||!args){finish_call(out,0,ERROR_INVALID_PARAMETER);return;}
    copied=*args;now=GetTickCount64();
    if(!args_ok(&copied)||now>=copied.run_until_tick_ms||
       copied.run_until_tick_ms-now>RLD_MAX_RUN_MS||
       copied.closure_until_tick_ms<=copied.run_until_tick_ms||
       copied.closure_until_tick_ms-copied.run_until_tick_ms>RLD_MAX_CLEANUP_MS){
        finish_call(out,0,ERROR_INVALID_PARAMETER);return;
    }
    if(InterlockedCompareExchange(&reserved_once,1,0)!=0){finish_call(out,0,ERROR_ALREADY_EXISTS);return;}
    /* Root owns whole aligned storage beforehand, never aliases args/outputs. */
    memset(storage,0,sizeof(*storage));InitializeSRWLock(&c->lock);
    c->args=copied;c->magic=RLD_MAGIC;c->s.generation=copied.generation;
    c->s.run_end=copied.run_until_tick_ms;c->s.cleanup_end=copied.closure_until_tick_ms;
    InterlockedExchange(&c->phase,RLD_REGISTERED);
    original_context=c;MemoryBarrier();InterlockedExchange(&c->initialized,1);
    finish_call(out,1,0);
}
RLD_EXPORT void WINAPI rld_submit(RLD_STORAGE *storage,const RLD_COMMAND_ARGS *args,RLD_COMMAND_OUT *out) {
    RLD_PRIVATE_CONTEXT *c;
    RLD_COMMAND_ARGS request;
    DWORD error=ERROR_INVALID_PARAMETER;
    uint64_t now;
    LONG phase;
    if(!out||!begin_call(&out->call))return;
    memset(&out->snapshot,0,sizeof(out->snapshot));
    out->command_index=UINT64_MAX;InterlockedExchange(&out->submit_done,0);InterlockedExchange(&out->accepted,0);
    c=context_of(storage);
    if(!c||!args)goto rejected;
    request=*args;
    if(request.reserved||request.generation!=c->args.generation||request.session_cookie!=c->args.session_cookie||
       !((request.op==RLD_QUERY&&request.index<RLD_QUERY_CAP&&
           (request.slot<RLD_PROCESS_CAP||request.slot==RLD_SLOT_STATUS))||
         (request.op==RLD_STOP&&request.index==RLD_STOP_SLOT&&request.slot==RLD_SLOT_STATUS)))goto rejected;
    AcquireSRWLockExclusive(&c->lock);
    phase=phase_of(c);now=GetTickCount64();
    if(c->commands[request.index].state!=0){error=ERROR_ALREADY_EXISTS;goto unlock_rejected;}
    if(phase<RLD_REGISTERED||phase>RLD_RUNNING){error=ERROR_INVALID_STATE;goto unlock_rejected;}
    if(request.op==RLD_QUERY&&(phase!=RLD_RUNNING||InterlockedCompareExchange(&c->s.stop_requested,0,0))){
        error=ERROR_OPERATION_ABORTED;goto unlock_rejected;
    }
    if(now>=(request.op==RLD_STOP?c->s.cleanup_end:c->s.run_end)){
        error=ERROR_TIMEOUT;goto unlock_rejected;
    }
    c->commands[request.index].args=request;c->commands[request.index].out=out;
    out->command_index=request.index;
    if(request.op==RLD_STOP)InterlockedExchange(&c->s.stop_requested,1); /* revoke before observer/worker effects */
    InterlockedExchange(&out->accepted,1);InterlockedExchange(&out->submit_done,1);
    MemoryBarrier();c->commands[request.index].state=1; /* retained output registered before worker effect */
    ReleaseSRWLockExclusive(&c->lock);return;
unlock_rejected:
    ReleaseSRWLockExclusive(&c->lock);
rejected:
    InterlockedExchange(&out->submit_done,1);finish_call(&out->call,0,error);
}
RLD_EXPORT void WINAPI rld_run(RLD_STORAGE *storage,RLD_RUN_OUT *out) {
    RLD_PRIVATE_CONTEXT *c;
    STATE *s;
    if(!out||!begin_call(&out->call))return;
    memset(&out->snapshot,0,sizeof(out->snapshot));out->ledger_count=0;out->reserved=0;
    memset(out->ledger,0,sizeof(out->ledger));
    c=context_of(storage);
    if(!c){finish_call(&out->call,0,ERROR_INVALID_STATE);return;}
    if(InterlockedCompareExchange(&c->run_claimed,1,0)!=0){finish_call(&out->call,0,ERROR_ALREADY_EXISTS);return;}
    s=&c->s;s->creator_pid=GetCurrentProcessId();s->debugger_tid=GetCurrentThreadId();s->start=GetTickCount64();
    InterlockedExchange(&c->phase,RLD_STARTING);
    if(GetTickCount64()>=s->run_end){fail(s,RLD_DEADLINE,ERROR_TIMEOUT);goto cleanup_worker;}
    if(InterlockedCompareExchange(&s->stop_requested,0,0))goto cleanup_worker;
    /* Exact known synthetic code, not an arbitrary caller-provided Node script. */
    if(memcmp(c->args.node_sha256,known_node_sha,32)||memcmp(c->args.parent_sha256,known_parent_sha,32)||
       memcmp(c->args.child_sha256,known_child_sha,32)){fail(s,RLD_PIN_FILES,ERROR_INVALID_DATA);goto cleanup_worker;}
    if(!pin(s,&s->node_file,(const wchar_t*)c->args.node_path,known_node_sha,RLD_NODE_BYTE_CAP,s->node_final)||
       !pin(s,&s->parent_file,(const wchar_t*)c->args.parent_fixture,known_parent_sha,RLD_FIXTURE_BYTE_CAP,s->parent_final)||
       !pin(s,&s->child_file,(const wchar_t*)c->args.child_fixture,known_child_sha,RLD_FIXTURE_BYTE_CAP,s->child_final))
        goto cleanup_worker;
    s->pins_verified=1;
    if(!s->receiver){fail(s,RWR_ARGUMENTS,ERROR_INVALID_STATE);goto cleanup_worker;}
    if(!rwr_create(s->receiver))goto cleanup_worker;
    if(InterlockedCompareExchange(&s->stop_requested,0,0)||s->primary_stage||s->cleanup_stage)goto cleanup_worker;
    (void)setup(s,&c->args);
    if(!s->created)goto cleanup_worker;
    InterlockedExchange(&c->phase,RLD_RUNNING);
    for(;;){
        if(s->primary_stage||s->cleanup_stage)InterlockedExchange(&s->stop_requested,1);
        if(!InterlockedCompareExchange(&s->stop_requested,0,0)&&GetTickCount64()>=s->run_end){
            fail(s,RLD_DEADLINE,ERROR_TIMEOUT);InterlockedExchange(&s->stop_requested,1);
        }
        if(InterlockedCompareExchange(&s->stop_requested,0,0)){
            InterlockedExchange(&c->phase,RLD_STOPPING);terminate(s);
        }
        rwr_service(s->receiver);rwr_status_service(s->receiver,0);
        service_queries(c);
        if(s->blocked)break;
        if(InterlockedCompareExchange(&s->stop_requested,0,0)&&s->count&&s->exit_count==s->count&&rwr_retired(s->receiver))break;
        if(s->count&&s->exit_count==s->count){
            /* Natural exits do NOT close original held slots before stop/end. */
            if(GetTickCount64()>=s->cleanup_end){cf(s,RLD_DEADLINE,ERROR_TIMEOUT);break;}
            Sleep(1);continue;
        }
        (void)pump_once(s);
    }
    if(s->count&&s->exit_count==s->count&&!s->blocked)terminal(s);
    else cf(s,RLD_TERMINAL,ERROR_TIMEOUT);
cleanup_worker:
    InterlockedExchange(&c->phase,RLD_STOPPING);
    if(s->receiver){
        rwr_revoke(s->receiver);
        while(!rwr_retired(s->receiver)&&!s->receiver->unknown&&GetTickCount64()<s->cleanup_end){
            rwr_cleanup(s->receiver);
            if(!rwr_retired(s->receiver)&&!s->receiver->unknown)Sleep(1);
        }
        if(!rwr_retired(s->receiver)){
            s->receiver->unknown=1;s->receiver->phase=RWR_UNKNOWN;
            rwr_cleanup_error(s->receiver,RWR_IO_TERMINAL,ERROR_TIMEOUT);
        }
    }
    cleanup(s);
    InterlockedExchange(&c->phase,s->cleanup_complete?RLD_CLOSED:RLD_UNKNOWN);
    /* Return publication != Python producer-ended/thread-join proof. */
    InterlockedExchange(&c->worker_returned,1);settle_commands(c);rwr_status_service(s->receiver,1);
    snapshot(c,&out->snapshot,RLD_SLOT_STATUS,0);
    if(s->cleanup_complete&&!s->ledger_overflow){
        out->ledger_count=s->event_count;
        memcpy(out->ledger,s->events,s->event_count*sizeof(RLD_EVENT));
    }
    finish_call(&out->call,s->cleanup_complete&&!s->primary_stage&&!s->cleanup_stage,
                s->primary_stage?s->primary_error:s->cleanup_error);
    /* No reset/destroy/unload. Unknown keeps ctx/Job/dups/crypto/file/attrs slots;
     * debug-worker exit fallback kills but does NOT prove terminal observation. */
}

/* Data-only final observation, after Root's actual rld_run producer return
 * AND external worker join. Native worker_returned is a necessary local guard,
 * never a replacement for that external join. No request queue or native effect.
 */
RLD_EXPORT void WINAPI rwr_final_status(RLD_STORAGE *original,RWR_STORAGE *receiver,
                                      RWR_STATUS_OUT *out) {
    RLD_PRIVATE_CONTEXT *c;
    RWR_PRIVATE_CONTEXT *r=(RWR_PRIVATE_CONTEXT*)receiver;
    LONG phase;
    DWORD error=ERROR_INVALID_STATE;
    int known=0;
    if(!out||!begin_call(&out->call))return;
    memset(&out->status,0,sizeof(out->status));out->command_index=UINT64_MAX;
    InterlockedExchange(&out->submit_done,0);InterlockedExchange(&out->accepted,0);
    c=context_of(original);
    if(!c||!r||c->s.receiver!=r)goto rejected;
    AcquireSRWLockExclusive(&c->lock);
    phase=phase_of(c);
    if(r->owner!=c||!r->registered||r->args.generation!=c->args.generation||
       r->args.session_cookie!=c->args.session_cookie||
       !InterlockedCompareExchange(&c->worker_returned,0,0)||
       (phase!=RLD_CLOSED&&phase!=RLD_UNKNOWN)||!r->revoked||r->authenticated){
        ReleaseSRWLockExclusive(&c->lock);goto rejected;
    }
    /* Final revocation/authentication guards make rwr_status_copy's clock
     * branch unreachable. Every copied receiver field is preserved native data.
     * Only the sentinel index identifies this nonqueued terminal observation.
     */
    rwr_status_copy(r,&out->status,UINT32_MAX);
    known=phase==RLD_CLOSED&&c->s.cleanup_complete&&r->retired&&!r->unknown&&
          !r->cleanup_stage&&rwr_io_ended(&r->connect)&&rwr_io_ended(&r->read)&&
          rwr_io_ended(&r->write)&&!rwr_slots(r);
    if(!known)error=ERROR_OPERATION_ABORTED;
    ReleaseSRWLockExclusive(&c->lock);
    InterlockedExchange(&out->accepted,known?1:0);
    InterlockedExchange(&out->submit_done,1);finish_call(&out->call,known,error);return;
rejected:
    InterlockedExchange(&out->submit_done,1);finish_call(&out->call,0,error);
}
