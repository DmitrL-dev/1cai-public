/* Proposal only: Win64 output-sink shim, not a transport/Editor authority DLL.
   No Python callback and no HWND/SDK/model entrypoint.
   Each cp_call stores status/handles in caller-owned memory BEFORE returning.
   Build/pinning/loading requires separate Root admission; not performed here. */
#include "cold_owner_pipe_shim.h"
#include <sddl.h>
#include <string.h>
#include <wchar.h>

/* These predicates constrain only the admitted negative fixture grammar.
   Root separately freezes actual logon SID/GA rights, env, caps and pins. */
static BOOL negative_sddl(LPCWSTR text) {
    static const WCHAR prefix[]=L"D:P(A;;GA;;;S-1-5-5-";
    size_t n=0, at;
    if(!text) return FALSE;
    while(n<256 && text[n]!=0) ++n;
    if(n==256 || wcsncmp(text,prefix,(sizeof(prefix)/sizeof(prefix[0]))-1)!=0)
        return FALSE;
    at=(sizeof(prefix)/sizeof(prefix[0]))-1;
    if(at>=n || text[at]<L'0' || text[at]>L'9') return FALSE;
    while(at<n && text[at]>=L'0' && text[at]<=L'9') ++at;
    if(at>=n || text[at++]!=L'-' || at>=n ||
       text[at]<L'0' || text[at]>L'9') return FALSE;
    while(at<n && text[at]>=L'0' && text[at]<=L'9') ++at;
    return at+1==n && text[at]==L')';
}
static BOOL negative_pipe_name(LPCWSTR text) {
    static const WCHAR prefix[]=L"\\\\.\\pipe\\rentgen-refusal-";
    const size_t base=(sizeof(prefix)/sizeof(prefix[0]))-1;
    size_t n=0, at;
    if(!text) return FALSE;
    while(n<256 && text[n]!=0) ++n;
    if(n!=base+32 || wcsncmp(text,prefix,base)!=0) return FALSE;
    for(at=base;at<n;++at)
        if(!((text[at]>=L'0' && text[at]<=L'9') ||
             (text[at]>=L'a' && text[at]<=L'f'))) return FALSE;
    return TRUE;
}
static BOOL overlapped_args(const CP_ARGS *a) {
    const OVERLAPPED *ov=(const OVERLAPPED *)a->p;
    return a->a && a->a!=INVALID_HANDLE_VALUE && ov &&
           ov->hEvent && ov->hEvent!=INVALID_HANDLE_VALUE;
}

static void finish(CP_OUT *o, BOOL ok, DWORD err) {
    o->ok = ok ? 1u : 0u;
    o->error = ok ? 0u : err;
    MemoryBarrier();
    InterlockedExchange((volatile LONG *)&o->done, 1);
}
CP_EXPORT void WINAPI cp_abi(uint32_t o[CP_ABI_WORDS]) {
    if(!o) return;
    o[0]=CP_ABI_VERSION; o[1]=(uint32_t)sizeof(void *);
    o[2]=(uint32_t)sizeof(CP_ARGS); o[3]=(uint32_t)sizeof(CP_OUT);
    o[4]=(uint32_t)sizeof(OVERLAPPED); o[5]=(uint32_t)sizeof(WCHAR);
}
CP_EXPORT void WINAPI cp_call(uint32_t op, CP_ARGS *a, CP_OUT *o) {
    CP_ARGS captured;
    BOOL ok=FALSE;
    DWORD err=ERROR_INVALID_PARAMETER;
    if (!a || !o || sizeof(void *)!=8) return;
    /* A slot is never dispatched twice; even failure keeps its first outputs. */
    if (InterlockedCompareExchange((volatile LONG *)&o->entered,1,0)!=0) return;
    captured=*a; a=&captured; /* Snapshot values before the first native effect. */
    switch(op) {
    case 1: /* unnamed, noninherited Job */
        o->h1=CreateJobObjectW(NULL,NULL);
        ok=o->h1!=NULL; err=ok?0:GetLastError(); break;
    case 2: { /* fixed one-process, no-breakaway, aggregate Job commit */
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION v;
        ZeroMemory(&v,sizeof(v));
        if (!a->number || a->number>512ull*1024*1024) break;
        v.BasicLimitInformation.LimitFlags=
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|
            JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_JOB_MEMORY;
        v.BasicLimitInformation.ActiveProcessLimit=1;
        v.JobMemoryLimit=(SIZE_T)a->number;
        ok=SetInformationJobObject(a->a,JobObjectExtendedLimitInformation,&v,sizeof(v));
        err=ok?0:GetLastError(); break;
    }
    case 3: {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION v;
        ZeroMemory(&v,sizeof(v));
        ok=QueryInformationJobObject(a->a,JobObjectExtendedLimitInformation,&v,sizeof(v),NULL);
        err=ok?0:GetLastError();
        if(ok) {
            o->value=v.BasicLimitInformation.LimitFlags;
            o->extra=v.BasicLimitInformation.ActiveProcessLimit;
            o->birth=(uint64_t)v.JobMemoryLimit;
            if(v.ProcessMemoryLimit!=0) {ok=FALSE;err=ERROR_INVALID_DATA;}
        }
        break;
    }
    case 4: {
        struct {DWORD assigned,returned;ULONG_PTR ids[2];} p;
        ZeroMemory(&p,sizeof(p));
        ok=QueryInformationJobObject(a->a,JobObjectBasicProcessIdList,&p,sizeof(p),NULL);
        err=ok?0:GetLastError();
        if(ok) {
            o->value=p.assigned;o->extra=p.returned;
            if(p.returned>1 || p.assigned!=p.returned) {ok=FALSE;err=ERROR_MORE_DATA;}
            else o->birth=p.returned ? (uint64_t)p.ids[0] : 0;
        }
        break;
    }
    case 5: {
        BOOL member=FALSE;
        ok=IsProcessInJob(a->b,a->a,&member);
        err=ok?0:GetLastError();o->value=member?1u:0u;break;
    }
    case 6: {
        PSECURITY_DESCRIPTOR sd=NULL;
        if(!negative_sddl(a->path)) break;
        ok=ConvertStringSecurityDescriptorToSecurityDescriptorW(a->path,SDDL_REVISION_1,&sd,NULL);
        err=ok?0:GetLastError();o->h1=(HANDLE)sd;break;
    }
    case 7: {
        HLOCAL remainder;
        if(!a->a) break;
        remainder=LocalFree((HLOCAL)a->a);
        ok=remainder==NULL;err=ok?0:GetLastError();break;
    }
    case 8: {
        SECURITY_ATTRIBUTES sa;
        sa.nLength=sizeof(sa);sa.lpSecurityDescriptor=a->a;sa.bInheritHandle=FALSE;
        {
            BOOL present=FALSE, defaulted=FALSE;
            PACL dacl=NULL;
            SECURITY_DESCRIPTOR_CONTROL control=0;
            DWORD revision=0;
            if(!a->a || !negative_pipe_name(a->path) ||
               a->count<1 || a->count>4096 ||
               !IsValidSecurityDescriptor(a->a)) break;
            ok=GetSecurityDescriptorDacl(a->a,&present,&dacl,&defaulted);
            err=ok?0:GetLastError();
            if(!ok) break;
            ok=GetSecurityDescriptorControl(a->a,&control,&revision);
            err=ok?0:GetLastError();
            if(!ok) break;
            if(!present || !dacl || defaulted || !(control&SE_DACL_PROTECTED)) {
                ok=FALSE;err=ERROR_INVALID_SECURITY_DESCR;break;
            }
        }
        o->h1=CreateNamedPipeW(a->path,
            PIPE_ACCESS_DUPLEX|FILE_FLAG_FIRST_PIPE_INSTANCE|FILE_FLAG_OVERLAPPED,
            PIPE_TYPE_BYTE|PIPE_READMODE_BYTE|PIPE_WAIT|PIPE_REJECT_REMOTE_CLIENTS,
            1,a->count,a->count,0,&sa);
        ok=o->h1!=INVALID_HANDLE_VALUE;err=ok?0:GetLastError();break;
    }
    case 9:
        o->h1=CreateEventW(NULL,TRUE,FALSE,NULL);
        ok=o->h1!=NULL;err=ok?0:GetLastError();break;
    case 10: {
        STARTUPINFOEXW si;
        PROCESS_INFORMATION pi;
        SIZE_T required=0;
        HANDLE jobs[1]={a->a};
        _Alignas(16) BYTE attributes[1024];
        LPPROC_THREAD_ATTRIBUTE_LIST list=(LPPROC_THREAD_ATTRIBUTE_LIST)attributes;
        BOOL initialized=FALSE;
        ZeroMemory(&si,sizeof(si));ZeroMemory(&pi,sizeof(pi));
        if(!a->a||!a->path||!a->command||!a->environment||!a->cwd) break;
        ok=InitializeProcThreadAttributeList(NULL,1,0,&required);
        err=ok?0:GetLastError();
        if(ok || err!=ERROR_INSUFFICIENT_BUFFER ||
           !required || required>sizeof(attributes)) {
            ok=FALSE;
            if(err==0 || err==ERROR_INSUFFICIENT_BUFFER) err=ERROR_INVALID_PARAMETER;
            break;
        }
        ok=InitializeProcThreadAttributeList(list,1,0,&required);
        err=ok?0:GetLastError();
        if(!ok) break;
        initialized=TRUE;
        ok=UpdateProcThreadAttribute(list,0,PROC_THREAD_ATTRIBUTE_JOB_LIST,
                                    jobs,sizeof(jobs),NULL,NULL);
        err=ok?0:GetLastError();
        if(ok) {
            si.StartupInfo.cb=sizeof(si);si.lpAttributeList=list;
            /* Job association AT BIRTH, so owner death cannot orphan an
               unassigned suspended fixture. No inherited pipe/event/Job handle. */
            ok=CreateProcessW(a->path,a->command,NULL,NULL,FALSE,
                CREATE_SUSPENDED|CREATE_UNICODE_ENVIRONMENT|DETACHED_PROCESS|
                EXTENDED_STARTUPINFO_PRESENT,(LPVOID)a->environment,a->cwd,
                &si.StartupInfo,&pi);
            err=ok?0:GetLastError();
        }
        /* Store every output, including a nonzero partial output on failure. */
        o->h1=pi.hProcess;o->h2=pi.hThread;o->value=pi.dwProcessId;o->extra=pi.dwThreadId;
        if(initialized) DeleteProcThreadAttributeList(list);
        break;
    }
    case 11:
        o->value=ResumeThread(a->a);
        ok=o->value!=0xffffffffu;err=ok?0:GetLastError();break;
    case 12: {
        FILETIME birth,exited,kernel,user;
        DWORD length=1024;
        o->value=GetProcessId(a->a);
        if(!o->value){err=GetLastError();break;}
        ok=GetProcessTimes(a->a,&birth,&exited,&kernel,&user);
        err=ok?0:GetLastError();if(!ok)break;
        o->birth=((uint64_t)birth.dwHighDateTime<<32)|birth.dwLowDateTime;
        ok=QueryFullProcessImageNameW(a->a,0,o->image,&length);
        err=ok?0:GetLastError();if(!ok)break;
        if(length>=1024){ok=FALSE;err=ERROR_INSUFFICIENT_BUFFER;break;}
        o->image[length]=0;
        o->extra=WaitForSingleObject(a->a,0);
        ok=o->extra==WAIT_OBJECT_0||o->extra==WAIT_TIMEOUT;
        err=ok?0:GetLastError();break;
    }
    case 13: {
        ULONG pid=0;
        ok=GetNamedPipeClientProcessId(a->a,&pid);
        err=ok?0:GetLastError();o->value=(uint32_t)pid;break;
    }
    case 14:
        if(!overlapped_args(a)) break;
        ok=ConnectNamedPipe(a->a,(LPOVERLAPPED)a->p);
        err=ok?0:GetLastError();break;
    case 15:
        if(!overlapped_args(a)||!a->q||a->count<1||a->count>4096)break;
        ok=ReadFile(a->a,a->q,a->count,NULL,(LPOVERLAPPED)a->p);
        err=ok?0:GetLastError();break;
    case 16:
        if(!overlapped_args(a)||!a->q||a->count<1||a->count>4096)break;
        ok=WriteFile(a->a,a->q,a->count,NULL,(LPOVERLAPPED)a->p);
        err=ok?0:GetLastError();break;
    case 17: {
        DWORD transferred=0;
        if(!overlapped_args(a))break;
        ok=GetOverlappedResult(a->a,(LPOVERLAPPED)a->p,&transferred,FALSE);
        err=ok?0:GetLastError();o->value=(uint32_t)transferred;break;
    }
    case 18:
        if(!overlapped_args(a))break;
        ok=CancelIoEx(a->a,(LPOVERLAPPED)a->p);
        err=ok?0:GetLastError();break;
    case 19:
        ok=CloseHandle(a->a);err=ok?0:GetLastError();break;
    case 20:
        ok=TerminateJobObject(a->a,125);err=ok?0:GetLastError();break;
    case 21:
        ok=TerminateProcess(a->a,125);err=ok?0:GetLastError();break;
    case 22:
        o->value=WaitForSingleObject(a->a,0);
        ok=o->value==WAIT_OBJECT_0||o->value==WAIT_TIMEOUT;
        err=ok?0:GetLastError();
        if(ok&&o->value==WAIT_OBJECT_0) {
            DWORD exit_code=0;
            ok=GetExitCodeProcess(a->a,&exit_code);
            err=ok?0:GetLastError();o->extra=(uint32_t)exit_code;
        }
        break;
    case 23:
        ok=DuplicateHandle(GetCurrentProcess(),a->a,GetCurrentProcess(),
                           &o->h1,0,FALSE,DUPLICATE_SAME_ACCESS);
        err=ok?0:GetLastError();break;
    default:
        break;
    }
    finish(o,ok,err);
}
