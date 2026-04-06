import sys
import os
import time
import ctypes
import pymem
from datetime import datetime
from ctypes import Structure, c_int, c_void_p, c_size_t, POINTER, byref, c_int32, c_float, c_uint64
import ctypes.wintypes

ntdll = ctypes.WinDLL('ntdll', use_last_error=True)

class IO_STATUS_BLOCK(Structure):
    _fields_ = [("Status", c_int), ("Information", c_void_p)]

NtWriteVirtualMemory = ntdll.NtWriteVirtualMemory
NtWriteVirtualMemory.argtypes = [ctypes.wintypes.HANDLE, c_void_p, c_void_p, c_size_t, POINTER(IO_STATUS_BLOCK)]
NtWriteVirtualMemory.restype = c_int

class singleton:
    def __init__(self, pm):
        self.pm = pm
        try:
            self.module = pymem.process.module_from_name(pm.process_handle, "RobloxPlayerBeta.exe")
        except:
            self.module = None
        self.cached_singleton = 0
        self.flag_cache = {}

    def get_singleton(self):
        if self.cached_singleton: return self.cached_singleton
        if not self.module: return 0
        ptrn = b"\x48\x83\xec\x38\x48\x8b\x0d"
        result = pymem.pattern.pattern_scan_module(self.pm.process_handle, self.module, ptrn)
        if not result: return 0
        try:
            relative = self.pm.read_int(result + 7)
            target = (result + 11) + relative
            self.cached_singleton = self.pm.read_ulonglong(target)
            return self.cached_singleton
        except: return 0

    def find_flag(self, name: str):
        if name in self.flag_cache: return self.flag_cache[name]
        singleton_ptr = self.get_singleton()
        if not singleton_ptr: return 0
        basis = 0xcbf29ce484222325
        for char in name:
            basis ^= ord(char)
            basis = (basis * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF 
        try:
            map_data = self.pm.read_bytes(singleton_ptr + 24, 32)
            map_list = int.from_bytes(map_data[0:8], 'little')
            map_mask = int.from_bytes(map_data[24:32], 'little')
            idx = basis & map_mask
            current_node = self.pm.read_ulonglong(map_list + (idx * 16) + 8)
            name_len = len(name)
            for _ in range(500):
                if not current_node: break
                node_data = self.pm.read_bytes(current_node, 64)
                s_size = int.from_bytes(node_data[32:40], 'little')
                if s_size == name_len:
                    s_cap = int.from_bytes(node_data[40:48], 'little')
                    s_addr = int.from_bytes(node_data[16:24], 'little') if s_cap > 15 else current_node + 16
                    try:
                        if self.pm.read_string(s_addr, s_size) == name:
                            flag_obj_ptr = int.from_bytes(node_data[48:56], 'little')
                            self.flag_cache[name] = flag_obj_ptr
                            return flag_obj_ptr
                    except: pass
                current_node = int.from_bytes(node_data[8:16], 'little')
        except: pass
        return 0

    def _nt_write(self, addr, data, size):
        try:
            status_block = IO_STATUS_BLOCK()
            return NtWriteVirtualMemory(self.pm.process_handle, addr, data, size, byref(status_block)) == 0
        except: return False

    def set_value(self, name, value, ftype):
        addr = self.find_flag(name)
        if not addr: return False
        try:
            val_ptr = self.pm.read_ulonglong(addr + 0xC0)
            if not val_ptr: return False
            if ftype == 'bool':
                v = c_int32(1 if str(value).lower() == 'true' else 0)
                return self._nt_write(val_ptr, byref(v), 4)
            elif ftype == 'int':
                v = c_int32(int(value))
                return self._nt_write(val_ptr, byref(v), 4)
            elif ftype == 'float':
                v = c_float(float(value))
                return self._nt_write(val_ptr, byref(v), 4)
            else:
                b_val = str(value).encode('utf-8')
                str_base = self.pm.read_ulonglong(val_ptr)
                self._nt_write(str_base, b_val + b'\x00', len(b_val) + 1)
                l = ctypes.c_uint64(len(b_val))
                return self._nt_write(val_ptr + 8, byref(l), 8)
        except: return False

def find_roblox_process():
    from ctypes import wintypes
    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)), ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_char * 260)
        ]
    hSnapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if hSnapshot == -1: return None
    pe32 = PROCESSENTRY32()
    pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
    target_pid = None
    if ctypes.windll.kernel32.Process32First(hSnapshot, ctypes.byref(pe32)):
        while True:
            if pe32.szExeFile == b"RobloxPlayerBeta.exe":
                target_pid = pe32.th32ProcessID
                break
            if not ctypes.windll.kernel32.Process32Next(hSnapshot, ctypes.byref(pe32)):
                break
    ctypes.windll.kernel32.CloseHandle(hSnapshot)
    return target_pid

def get_time():
    return datetime.now().strftime("%H:%M:%S")

def main():
    print(f"[{get_time()}] [+] Searching for Roblox...")
    last_pid = None
    while True:
        pid = find_roblox_process()
        if pid and pid != last_pid:
            print(f"[{get_time()}] [+] Roblox started (PID: {pid})")
            time.sleep(0.5)
            try:
                pm = pymem.Pymem(pid)
                injector = singleton(pm)
                
                flag_name = "DebugDisplayFPS"
                if injector.set_value(flag_name, "True", "bool"):
                    print(f"[{get_time()}] [*] [APPLY] Injection Finished. Success: {flag_name} -> True")
                else:
                    print(f"[{get_time()}] [-] [APPLY] FAILED: Couldnt find {flag_name}")
                
                last_pid = pid
            except Exception as e:
                print(f"[{get_time()}] [-] Error during injection: {e}")
                last_pid = None
        elif not pid:
            if last_pid:
                print(f"[{get_time()}] [-] Roblox closed")
            last_pid = None
        time.sleep(0.1)

if __name__ == "__main__":
    main()