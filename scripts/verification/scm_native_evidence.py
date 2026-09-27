"""Read-only Windows SCM/process evidence. No create/control/delete APIs are loaded.

Status layout and PID validity:
https://learn.microsoft.com/en-us/windows/win32/api/winsvc/nf-winsvc-queryservicestatusex
https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_status_process
"""
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import re
from rentgen_core.local_identity import _WindowsTokenAPI


class NativeEvidenceError(RuntimeError):
    def __init__(self, operation, code):
        self.operation, self.code = operation, code
        super().__init__(f'{operation} failed with Windows code {code}')


class ServiceStatus(ctypes.Structure):
    _fields_ = [(name, W.DWORD) for name in (
        'service_type', 'state', 'controls', 'win32_exit', 'service_exit',
        'checkpoint', 'wait_hint', 'pid', 'flags')]


class ServiceConfig(ctypes.Structure):
    _fields_ = [
        ('service_type', W.DWORD), ('start_type', W.DWORD), ('error_control', W.DWORD),
        ('binary_path', W.LPWSTR), ('load_group', W.LPWSTR), ('tag', W.DWORD),
        ('dependencies', W.LPWSTR), ('account', W.LPWSTR), ('display_name', W.LPWSTR),
    ]


class Luid(ctypes.Structure):
    _fields_ = [('low', W.DWORD), ('high', W.LONG)]


class LuidAttributes(ctypes.Structure):
    _fields_ = [('luid', Luid), ('attributes', W.DWORD)]


class NativeEvidence:
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('Windows required')
        self.security = ctypes.WinDLL('advapi32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = (
            (self.security.OpenSCManagerW, [W.LPCWSTR, W.LPCWSTR, W.DWORD], W.HANDLE),
            (self.security.OpenServiceW, [W.HANDLE, W.LPCWSTR, W.DWORD], W.HANDLE),
            (self.security.CloseServiceHandle, [W.HANDLE], W.BOOL),
            (self.security.QueryServiceStatusEx, [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD)], W.BOOL),
            (self.security.QueryServiceConfigW, [W.HANDLE, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD)], W.BOOL),
            (self.kernel.OpenProcess, [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            (self.kernel.QueryFullProcessImageNameW, [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)], W.BOOL),
            (self.kernel.CloseHandle, [W.HANDLE], W.BOOL),
        )
        for function, args, result in signatures:
            function.argtypes, function.restype = args, result

    @staticmethod
    def require(value, operation):
        if not value:
            raise NativeEvidenceError(operation, ctypes.get_last_error())
        return value

    def query(self, name):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,79}', name):
            raise ValueError('Invalid service name')
        manager = self.require(self.security.OpenSCManagerW(None, None, 1), 'OpenSCManager')
        try:
            service = self.security.OpenServiceW(manager, name, 0x0004 | 0x0001)
            if not service:
                code = ctypes.get_last_error()
                if code == 1060:
                    return {'name': name, 'exists': False}
                raise NativeEvidenceError('OpenService', code)
            try:
                status = ServiceStatus()
                needed = W.DWORD()
                self.require(self.security.QueryServiceStatusEx(service, 0, ctypes.byref(status), ctypes.sizeof(status), ctypes.byref(needed)), 'QueryServiceStatusEx')
                buffer = ctypes.create_string_buffer(8192)
                self.require(self.security.QueryServiceConfigW(service, buffer, len(buffer), ctypes.byref(needed)), 'QueryServiceConfig')
                config = ctypes.cast(buffer, ctypes.POINTER(ServiceConfig)).contents
                if not 1 <= status.state <= 7:
                    raise RuntimeError('Unknown SCM state')
                return {
                    'name': name, 'exists': True,
                    'status': {key: getattr(status, key) for key, _ in ServiceStatus._fields_},
                    'pid_valid': status.state in {4, 5, 6, 7} and status.pid > 0,
                    'config': {key: getattr(config, key) for key in (
                        'service_type', 'start_type', 'error_control', 'binary_path', 'account', 'display_name')},
                }
            finally:
                self.require(self.security.CloseServiceHandle(service), 'CloseServiceHandle')
        finally:
            self.require(self.security.CloseServiceHandle(manager), 'CloseSCManagerHandle')

    def process(self, pid):
        if type(pid) is not int or not 0 < pid < 2**32:
            raise ValueError('Invalid PID')
        process = self.require(self.kernel.OpenProcess(0x1000, False, pid), 'OpenProcessQuery')
        try:
            size = W.DWORD(32768)
            image = ctypes.create_unicode_buffer(size.value)
            self.require(self.kernel.QueryFullProcessImageNameW(process, 0, image, ctypes.byref(size)), 'QueryFullProcessImageName')
            api = _WindowsTokenAPI()
            token = W.HANDLE()
            self.require(api.security.OpenProcessToken(process, 0x0008, ctypes.byref(token)), 'OpenProcessToken')
            try:
                storage, sid = api.token_user(token)
                value = api.sid_string(sid)
                try:
                    identity = value.value
                    if not identity or not identity.startswith('S-1-'):
                        raise RuntimeError('Invalid token SID')
                    return {'pid': pid, 'image': str(Path(image.value)), 'token_user_sid': identity}
                finally:
                    api.free_string(value)
            finally:
                api.close_token(token)
        finally:
            self.require(self.kernel.CloseHandle(process), 'CloseProcessHandle')

    def privileges(self):
        api = _WindowsTokenAPI()
        lookup = api.security.LookupPrivilegeNameW
        lookup.argtypes = [W.LPCWSTR, ctypes.POINTER(Luid), W.LPWSTR, ctypes.POINTER(W.DWORD)]
        lookup.restype = W.BOOL
        token = api.open_token()
        try:
            needed = W.DWORD()
            first = api.security.GetTokenInformation(token, 3, None, 0, ctypes.byref(needed))
            if first or ctypes.get_last_error() != 122 or not 4 <= needed.value <= 65536:
                raise RuntimeError('Invalid TokenPrivileges size')
            storage = ctypes.create_string_buffer(needed.value)
            self.require(api.security.GetTokenInformation(token, 3, storage, len(storage), ctypes.byref(needed)), 'GetTokenPrivileges')
            count = W.DWORD.from_buffer(storage).value
            if count > 256 or 4 + count * ctypes.sizeof(LuidAttributes) > len(storage):
                raise RuntimeError('Invalid TokenPrivileges count')
            result = []
            for index in range(count):
                item = LuidAttributes.from_buffer(storage, 4 + index * ctypes.sizeof(LuidAttributes))
                size = W.DWORD(256)
                name = ctypes.create_unicode_buffer(size.value)
                self.require(lookup(None, ctypes.byref(item.luid), name, ctypes.byref(size)), 'LookupPrivilegeName')
                result.append({'name': name.value, 'enabled': bool(item.attributes & 2)})
            return result
        finally:
            api.close_token(token)
