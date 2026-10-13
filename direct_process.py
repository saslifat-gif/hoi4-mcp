"""Read-only Windows process and power checks; no desktop/input APIs."""
import ctypes
from ctypes import wintypes
import os


def require_ac_power():
    class Power(ctypes.Structure):
        _fields_ = [('ac', ctypes.c_ubyte), ('flags', ctypes.c_ubyte),
                    ('percent', ctypes.c_ubyte), ('reserved', ctypes.c_ubyte),
                    ('remaining', ctypes.c_uint32), ('full', ctypes.c_uint32)]
    value = Power()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetSystemPowerStatus.argtypes = [ctypes.POINTER(Power)]
    kernel.GetSystemPowerStatus.restype = ctypes.c_int
    if not kernel.GetSystemPowerStatus(ctypes.byref(value)):
        raise RuntimeError('Power status unavailable')
    if value.ac != 1:
        raise RuntimeError('AC power disconnected; test stopped')
    return {'external_power': True, 'battery_percent': value.percent}


def process_identity(pid):
    if os.name != 'nt':
        raise RuntimeError('Live process verification runs on Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise RuntimeError('Bound HOI4 process is unavailable')
    try:
        exitcode = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exitcode)) or exitcode.value != 259:
            raise RuntimeError('Bound HOI4 process has stopped')
        name, length = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)):
            raise RuntimeError('Cannot identify bound process')
        if os.path.basename(name.value).lower() != 'hoi4.exe':
            raise RuntimeError('Bound process is not HOI4')
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            raise RuntimeError('Cannot verify process lifetime')
        created = times[0].dwLowDateTime | times[0].dwHighDateTime << 32
        return {'pid': pid, 'created': created, 'executable': name.value}
    finally:
        kernel.CloseHandle(handle)
