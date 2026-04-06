import webview
import requests
import re
import ctypes
from ctypes import sizeof, byref, c_void_p, c_size_t, c_bool, c_int, c_float, POINTER, Structure, wintypes, c_ulonglong
import pymem
from ctypes.wintypes import HANDLE, ULONG
import json
import threading
import random
import string
import time
import logging
import os
import urllib.request
import winreg
import tempfile
import shutil
import subprocess
import traceback
from pathlib import Path
from pypresence import Presence
from tkinter import Tk, filedialog
import sys
import keyboard
import pymem.process
import pymem.pattern
import win32gui


ntdll = ctypes.WinDLL('ntdll', use_last_error=True)

class IO_STATUS_BLOCK(Structure):
    _fields_ = [("Status", c_int),
                ("Information", c_void_p)]

NtWriteVirtualMemory = ntdll.NtWriteVirtualMemory
NtWriteVirtualMemory.argtypes = [HANDLE, c_void_p, c_void_p, c_size_t, POINTER(IO_STATUS_BLOCK)]
NtWriteVirtualMemory.restype = c_int

class GUITerminalLogger:
    def __init__(self, window):
        self.window = window
        self.buffer = []
        self.ready = False

    def mark_ready(self):
        if self.ready:
            return
        self.ready = True
        for line in self.buffer:
            self._send(line)
        self.buffer.clear()
        self._send("[SYSTEM] Terminal connected – showing backend logs")

    def _send(self, line):
        try:
            escaped = line.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
            self.window.evaluate_js(f'logToTerminal("{escaped}")')
        except Exception as e:
            print(f"[Terminal send failed] {e}: {line}")

    def write(self, text):
        if not text or text.isspace():
            return
        lines = text.rstrip().split('\n')
        for line in lines:
            if line:
                if self.ready:
                    self._send(line)
                else:
                    self.buffer.append(line)

    def flush(self):
        pass

windowed = True
rpc_enabled = True

MANUAL_OFFSETS = {
    "SimAdaptiveUseNewVelocityCriteria": 0x67BCAF0,
    "InterpolationFrameVelocityThresholdMillionth": 0x676F778,
    "FullWindowMessages": 0x67ACE90,
    "RenderLocalLightFadeInMs": 0x6783668,
    "FixWallsOcclusion": 0x67C3BC8,
    "RenderHighlightTransparency": 0x67F5E20,
    "HighlightOutlinesOnMobile": 0x67F6530,
    "RenderPerformanceOverlay": 0x67F5DC0,
    "DebugHighlightSpecificFont": 0x67C0BF0,
    "LargeJohnson": 0x6f4a128,
    "BulletContactBreakChance": 0x6f4a1b0,
    "RagdollConstraintSolverIterationCount": 0x6f4a2a8,
    "FixRagdollSolverJank": 0x6f4a3c0,
    "DebugSimIntegrationStabilityTesting": 0x6f4a1a0,
    "SimFixAssemblyRadiusCalc": 0x6b4a6a7,
    "ISRLimitSimulationRadiusToNOUCount": 0x69AC0B4
}

client_id = "1445329800095862794"
RPC = Presence(client_id)

def rpc():
    connected = False
    while True:
        try:
            if rpc_enabled:
                if not connected:
                    RPC.connect()
                    connected = True
                RPC.update(
                    details="FFlag Editor For Free | velostrap.netlify.app",
                    large_image="velostrap",
                    large_text="Velostrap",
                    buttons=[{"label": "Download Now!", "url": "https://velostrap.netlify.app"}]
                )
            else:
                if connected:
                    try:
                        RPC.close()
                    except Exception:
                        pass
                    connected = False
        except Exception as e:
            print(f"Discord RPC error: {e}")
            connected = False
        time.sleep(15)

kernel32 = ctypes.WinDLL('kernel32')
user32 = ctypes.WinDLL('user32')
SW_HIDE = 0
hWnd = kernel32.GetConsoleWindow()
if hWnd:
    user32.ShowWindow(hWnd, SW_HIDE)



kernel32.GetLastError.restype = wintypes.DWORD

APP_DIR = Path(os.path.expanduser("~")) / ".VelostrapManager"
APP_DIR.mkdir(parents=True, exist_ok=True)
USER_FLAGS_FILE = APP_DIR / "user_flags.json"
CONFIG_FILE = APP_DIR / "config.json"

DEFAULT_FLAGS = [{"name": "Vanana", "value": "False", "type": "bool"}]

DEFAULT_CONFIG = {
    "theme": "white",
    "auto_apply_on_attach": True,
    "rpc_enabled": True,
    "old_death_sound": False,
    "mouse_cursor": "default",
    "old_avatar_editor_background": False,
    "old_character_sounds": False,
    "emoji_type": "default",
    "use_custom_font": False,
    "custom_font_path": "",
    "hide_key": "insert",
    "safe_mode": True,
    "randomization": True,
    "timing_attack": True,
    "reapply": True,
    "offsetless": False
}

if not USER_FLAGS_FILE.exists():
    USER_FLAGS_FILE.write_text(json.dumps(DEFAULT_FLAGS, indent=4))
if not CONFIG_FILE.exists():
    CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=4))

try:
    existing_cfg = json.loads(CONFIG_FILE.read_text())
    rpc_enabled = bool(existing_cfg.get("rpc_enabled", True))
except Exception:
    rpc_enabled = True

threading.Thread(target=rpc, daemon=True).start()

alrprinted = False

def find_roblox_process():
    global alrprinted
    try:
        for p in pymem.process.list_processes():
            exe_name = p.szExeFile.decode('utf-8', 'ignore').lower()
            if p.th32ProcessID and "robloxplayerbeta.exe" in exe_name:
                if not alrprinted:
                    print("[+] Found Roblox!")
                    alrprinted = True
                return p.th32ProcessID
    except Exception:
        pass
    return None

def get_module_base(pid):
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    hProcess = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not hProcess:
        return None
    try:
        hModules = (c_void_p * 1024)()
        cbNeeded = c_size_t()
        if psapi.EnumProcessModules(hProcess, byref(hModules), sizeof(hModules), byref(cbNeeded)):
            if cbNeeded.value > sizeof(hModules):
                size_needed = cbNeeded.value
                hModules = (c_void_p * (size_needed // sizeof(c_void_p)))()
                if not psapi.EnumProcessModules(hProcess, byref(hModules), size_needed, byref(cbNeeded)):
                    return None
            return int(hModules[0]) if cbNeeded.value >= sizeof(c_void_p) else None
    finally:
        kernel32.CloseHandle(hProcess)
    return None

def fetch_fflag_offsets():
    url = "https://github.com/Jovan1-marker/Roblox-Offsets/blob/main/FFlags.hpp"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        matches = re.findall(r'uintptr_t\s+(\w+)\s*=\s*(0x[0-9A-Fa-f]+);', r.text)
        online = {name: int(offset, 16) for name, offset in matches}
        final = online.copy()
        final.update(MANUAL_OFFSETS)
        added = set(MANUAL_OFFSETS.keys()) - set(online.keys())
        print(f"[VELORIN] Loaded {len(final)} FFlags ")
        return final
    except Exception as e:
        print(f"[VELORIN] Offline mode: Using {len(MANUAL_OFFSETS)} manual offsets ({e})")
        return MANUAL_OFFSETS.copy()

PATTERN = b"\x48\x83\xec\x38\x48\x8b\x0d....\x4c\x8d\x05"

M_BASIS = 0xcbf29ce484222325
M_PRIME = 0x100000001b3

OFF_FFLAG_VALUE_PTR = 0xC0  

OFF_MAP_END = 0x00
OFF_MAP_LIST = 0x10
OFF_MAP_MASK = 0x28

OFF_ENTRY_FORWARD = 0x08
OFF_ENTRY_STRING = 0x10
OFF_ENTRY_GET_SET = 0x30  

OFF_STR_BYTES = 0x00
OFF_STR_SIZE = 0x10
OFF_STR_ALLOC = 0x18


class New_no_offset_injector:
    def __init__(self, pm):
        self.pm = pm
        self.module = pymem.process.module_from_name(pm.process_handle, "RobloxPlayerBeta.exe")
        self.cached_singleton = 0
        self.flag_cache = {}

    def get_singleton(self):
        if self.cached_singleton:
            return self.cached_singleton

        result = pymem.pattern.pattern_scan_module(self.pm.process_handle, self.module, PATTERN)
        if not result:
            print("[-] Singleton Pattern not found.")
            return 0

    
        
        rel_offset_addr = result + 7
        relative = self.pm.read_int(rel_offset_addr)
        
     
        target = (result + 11) + relative
        
        absolute = self.pm.read_ulonglong(target)
        self.cached_singleton = absolute
        return absolute

    def find_flag(self, name: str):
        if name in self.flag_cache:
            return self.flag_cache[name]

        singleton = self.get_singleton()
        if not singleton:
            return 0

        basis = M_BASIS
        for char in name:
            basis ^= ord(char)
            basis = (basis * M_PRIME) & 0xFFFFFFFFFFFFFFFF 

        hash_map_addr = singleton + 8 
        
        try:
            map_bytes = self.pm.read_bytes(hash_map_addr, 56)
        except Exception as e:
            print(f"[-] Failed to read hash map: {e}")
            return 0
            
        map_end = int.from_bytes(map_bytes[OFF_MAP_END:OFF_MAP_END+8], 'little')
        map_list = int.from_bytes(map_bytes[OFF_MAP_LIST:OFF_MAP_LIST+8], 'little')
        map_mask = int.from_bytes(map_bytes[OFF_MAP_MASK:OFF_MAP_MASK+8], 'little')

        if map_mask == 0 or map_list == 0:
            return 0

        bucket_index = basis & map_mask
        bucket_base = map_list + (bucket_index * 16) 
        
        try:
            bucket_data = self.pm.read_bytes(bucket_base, 16)
        except:
            return 0

        node_current = int.from_bytes(bucket_data[8:16], 'little')

        if node_current == map_end:
            return 0

        while True:
            try:
                entry_data = self.pm.read_bytes(node_current, 56)
            except:
                break

            forward = int.from_bytes(entry_data[OFF_ENTRY_FORWARD:OFF_ENTRY_FORWARD+8], 'little')
            
            str_data_start = OFF_ENTRY_STRING
            str_size = int.from_bytes(entry_data[str_data_start+OFF_STR_SIZE : str_data_start+OFF_STR_SIZE+8], 'little')
            str_alloc = int.from_bytes(entry_data[str_data_start+OFF_STR_ALLOC : str_data_start+OFF_STR_ALLOC+8], 'little')
            
            entry_name = ""
            
            if str_alloc > 0xF:
                ptr = int.from_bytes(entry_data[str_data_start : str_data_start+8], 'little')
                try:
                    name_bytes = self.pm.read_bytes(ptr, str_size)
                    entry_name = name_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
                except:
                    pass
            else:
                name_bytes = entry_data[str_data_start : str_data_start + str_size]
                entry_name = name_bytes.decode('utf-8', errors='ignore').rstrip('\x00')

            if str_size == len(name) and entry_name == name:
                get_set = int.from_bytes(entry_data[OFF_ENTRY_GET_SET : OFF_ENTRY_GET_SET+8], 'little')
                self.flag_cache[name] = get_set
                return get_set

            if node_current == forward or forward == 0: 
                break
            
            node_current = forward

        return 0

    def set_string(self, name: str, value: str):
        addr = self.find_flag(name)
        if not addr:
            return False
        try:
            fflag_struct = self.pm.read_bytes(addr, 0xD0)
            value_inst = int.from_bytes(fflag_struct[OFF_FFLAG_VALUE_PTR:OFF_FFLAG_VALUE_PTR + 8], 'little')
            if not value_inst:
                return False

            buffer_ptr = self.pm.read_ulonglong(value_inst)
            if buffer_ptr < 0x10000 or buffer_ptr > 0x7FFFFFFFFFFF:  # Invalid pointer check
                print(f"[-] Skipping string flag {name}: invalid buffer pointer (protected)")
                return False

            b_val = value.encode('utf-8') + b'\x00'
            if len(b_val) > 512:  # Safety limit
                print(f"[-] String too long for {name}")
                return False

            self.pm.write_bytes(buffer_ptr, b_val, len(b_val))
            self.pm.write_ulonglong(value_inst + 8, len(b_val) - 1)
            return True
        except Exception as e:
            print(f"[-] String write skipped (protected): {name} - {e}")
            return False

    def set_int(self, name: str, value: int):
        addr = self.find_flag(name)
        if not addr: 
            return False
        try:
            fflag_struct = self.pm.read_bytes(addr, 0xD0) 
            value_ptr = int.from_bytes(fflag_struct[OFF_FFLAG_VALUE_PTR : OFF_FFLAG_VALUE_PTR+8], 'little')
            if not value_ptr: 
                return False
            self.pm.write_int(value_ptr, value)
            return True
        except: 
            return False

    def set_float(self, name: str, value: float):
        addr = self.find_flag(name)
        if not addr: 
            return False
        try:
            fflag_struct = self.pm.read_bytes(addr, 0xD0) 
            value_ptr = int.from_bytes(fflag_struct[OFF_FFLAG_VALUE_PTR : OFF_FFLAG_VALUE_PTR+8], 'little')
            if not value_ptr: 
                return False
            self.pm.write_float(value_ptr, value)
            return True
        except: 
            return False

    def get_string(self, name: str):
        addr = self.find_flag(name)
        if not addr: 
            return None
        try:
            fflag_struct = self.pm.read_bytes(addr, 0xD0)
            value_inst = int.from_bytes(fflag_struct[OFF_FFLAG_VALUE_PTR : OFF_FFLAG_VALUE_PTR+8], 'little')
            if not value_inst: 
                return None
            buffer_ptr = self.pm.read_ulonglong(value_inst)
            length = self.pm.read_ulonglong(value_inst + 0x8)
            if length > 0:
                return self.pm.read_string(buffer_ptr, int(length))
            return ""
        except: 
            return None

    def get_int(self, name: str):
        addr = self.find_flag(name)
        if not addr: 
            return None
        try:
            fflag_struct = self.pm.read_bytes(addr, 0xD0)
            value_ptr = int.from_bytes(fflag_struct[OFF_FFLAG_VALUE_PTR : OFF_FFLAG_VALUE_PTR+8], 'little')
            if not value_ptr: 
                return None
            return self.pm.read_int(value_ptr)
        except: 
            return None

    def get_float(self, name: str):
        addr = self.find_flag(name)
        if not addr: 
            return None
        try:
            fflag_struct = self.pm.read_bytes(addr, 0xD0)
            value_ptr = int.from_bytes(fflag_struct[OFF_FFLAG_VALUE_PTR : OFF_FFLAG_VALUE_PTR+8], 'little')
            if not value_ptr: 
                return None
            return self.pm.read_float(value_ptr)
        except: 
            return None
class Api:
    def __init__(self):
        self._window = None
        self._pm = None
        self._base = None
        self.all_offsets = {}
        self.offsets_lock = threading.Lock()
        self.config = self.load_config()
        self._original_values = {}
        self._suppress_guard = False
        self._guard_active = False
        self._auto_reapply_thread = None
        self.monitor_sleep = 30.0
        self._auto_reapply_enabled = bool(self.config.get('reapply', False))
        self._start_roblox_monitor()
        self._cache_all_offsets()
        self._start_auto_reapply()
        self.window_visible = True
        self.current_hide_key = self.config.get('hide_key', 'insert').lower()
        self.register_hide_hotkey()

    @staticmethod
    def find_hwnd_by_title(title):
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd) and title in win32gui.GetWindowText(hwnd):
                windows.append(hwnd)
        windows = []
        win32gui.EnumWindows(enum_windows_callback, windows)
        return windows[0] if windows else None

        
    def get_settings(self):
        return self.config

    def set_offsetless(self, enabled: bool):
        self.config['offsetless'] = bool(enabled)
        self.save_config()
        status = "enabled" if enabled else "disabled"
        print(f"[+] Offsetless Injection {status}")
        return {"ok": True}

    def set_random(self, enabled: bool):
        self.config['randomization'] = bool(enabled)
        self.save_config()
        status = "enabled" if enabled else "disabled"
        print(f"[{'+' if enabled else '-'}] MWrite randomization {status}")
        return {"ok": True}

    def set_timing_attack(self, enabled: bool):
        self.config['timing_attack'] = bool(enabled)
        self.save_config()
        status = "enabled" if enabled else "disabled"
        print(f"[{'+' if enabled else '-'}] Timing injection {status}")
        return {"ok": True}

    def set_safe_mode(self, enabled: bool):
        self.config['safe_mode'] = bool(enabled)
        self.save_config()
        status = "enabled" if enabled else "disabled"
        print(f"[{'+' if enabled else '-'}] Safe Mode: Read/Write {status}")
        return {"ok": True}

    def set_reapply(self, enabled: bool):
        self.config['reapply'] = bool(enabled)
        self.save_config()
        self._auto_reapply_enabled = bool(enabled)
        status = "enabled" if enabled else "disabled"
        print(f"[{'+' if enabled else '-'}] Re-apply {status}")
        return {"ok": True}
        
    def get_offsetless_state(self):
        return {"offsetless": self.config.get('offsetless', False)}

    def register_hide_hotkey(self):
        try:
            keyboard.remove_hotkey(self.toggle_window_visibility)
        except:
            pass
        try:
            keyboard.add_hotkey(self.current_hide_key, self.toggle_window_visibility, suppress=True)
            print(f"[+] Registered key: {self.current_hide_key.upper()}")
        except Exception as e:
            print(f"[-] Failed to register '{self.current_hide_key}': {e}")

    def toggle_window_visibility(self):
        if not self._window:
            return
        if self.window_visible:
            self._window.hide()
            self.window_visible = False
            print("[-] Window HIDDEN")
        else:
            self._window.show()
            self.window_visible = True
            print("[+] Window SHOWN")

    def set_hide_key(self, key_name: str):
        key_lower = key_name.strip().lower()
        if not key_lower:
            return {"ok": False, "error": "No key provided"}

        allowed = {'insert', 'delete', 'home', 'end', 'page up', 'page down', 'esc',
                   'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12'}
        if key_lower in allowed or '+' in key_lower or len(key_lower.replace('+', '')) == 1:
            self.current_hide_key = key_lower
            self.config['hide_key'] = key_lower
            self.save_config()
            self.register_hide_hotkey()
            return {"ok": True, "message": f"keybind changed to: {key_lower.upper()}"}
        else:
            return {"ok": False, "error": "Unsupported key combination"}

    def get_official_flags(self):
        flags = self.fetch_official_flags()
        if flags is None:
            return None
        return list(flags)

    def load_json_safe(self, content):
        return self.safe_load_json(content)

    def filter_and_convert_flags(self, input_data, official_flags):
        return self.convert_and_filter_flags(input_data, official_flags)

    @staticmethod
    def clean_flag_name(name: str) -> str:
        prefixes = ["DFInt", "DFString", "DFFlag", "FInt", "FString", "FFlag"]
        for pre in prefixes:
            if name.startswith(pre):
                return name[len(pre):]
        return name

    @staticmethod
    def _parse_bool(value):
        return str(value).strip().lower() in ("true", "1")

    @staticmethod
    def _has_simsolver_conflict(flags):
        names = {"SimSolverUpdateImprovedSleepEnabled", "SimSolverImprovedPartialSleepDefaultEnabled"}
        vals = {Api.clean_flag_name(f.get("name", "")): Api._parse_bool(f.get("value", "")) for f in flags}
        return all(k in vals for k in names) and not any(vals.values())

    @staticmethod
    def _values_equal(current, desired, flag_type):
        if flag_type == "bool":
            return Api._parse_bool(current) == Api._parse_bool(desired)
        if flag_type == "int":
            try: return int(current) == int(desired)
            except: return False
        if flag_type in ("float", "double"):
            try: return abs(float(current) - float(desired)) < 1e-6
            except: return False
        return str(current) == str(desired)

    def _read_memory(self, addr, flag_type):
        try:
            if flag_type == "bool":
                return "True" if self._pm.read_bool(addr) else "False"
            elif flag_type == "int":
                try:
                    ptr = self._pm.read_ulonglong(addr)
                    if ptr > 0x10000:
                        return str(self._pm.read_int(ptr))
                except: pass
                return str(self._pm.read_int(addr))
            elif flag_type in ("float", "double"):
                return str(self._pm.read_float(addr))
            elif flag_type == "string":
                try:
                    ptr = self._pm.read_ulonglong(addr)
                    target = ptr if ptr > 0x10000 else addr
                    b = self._pm.read_bytes(target, 256)
                    return b.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
                except: return ""
        except: raise RuntimeError("Read failed")

    def _write_memory(self, addr, value, flag_type, max_retries=3):
        safe_mode = self.config.get('safe_mode', True)
        randomize = self.config.get('randomization', True)
        timing_attack = self.config.get('timing_attack', True)

        if randomize or timing_attack:
            delay = random.uniform(0.005, 0.001 if timing_attack else 0.002)
            time.sleep(delay)

        backoff = 0.05
        for attempt in range(max_retries + 1):
            try:
                value_to_write = value
                original_int = None
                if safe_mode and flag_type in ("int", "bool"):
                    try:
                        original_int = int(value)
                        value_to_write = original_int ^ 0xDEADBEEF
                    except:
                        pass

                success = False
                if safe_mode and flag_type in ("int", "bool", "float"):
                    h_process = ctypes.windll.kernel32.OpenProcess(0x001F0FFF, False, self._pm.process_id)
                    if h_process:
                        buffer = ctypes.c_byte * 8
                        data_buf = buffer()
                        if flag_type == "bool":
                            ctypes.memmove(data_buf, ctypes.byref(ctypes.c_bool(Api._parse_bool(value_to_write))), 1)
                            size = 1
                        elif flag_type == "int":
                            val = original_int if original_int is not None else int(value)
                            ctypes.memmove(data_buf, ctypes.byref(ctypes.c_int32(val)), 4)
                            size = 4
                        elif flag_type == "float":
                            ctypes.memmove(data_buf, ctypes.byref(ctypes.c_float(float(value))), 4)
                            size = 4

                        io_status = IO_STATUS_BLOCK()
                        status = NtWriteVirtualMemory(h_process, addr, data_buf, size, byref(io_status))
                        ctypes.windll.kernel32.CloseHandle(h_process)
                        success = (status == 0)
                else:
                    if flag_type == "bool":
                        self._pm.write_bool(addr, Api._parse_bool(value_to_write))
                    elif flag_type == "int":
                        ival = int(value_to_write) if safe_mode and original_int is not None else int(value)
                        try:
                            ptr = self._pm.read_ulonglong(addr)
                            self._pm.write_int(ptr if ptr > 0x10000 else addr, ival)
                        except:
                            self._pm.write_int(addr, ival)
                    elif flag_type in ("float", "double"):
                        self._pm.write_float(addr, float(value))
                    elif flag_type == "string":
                        b = str(value).encode("utf-8")[:255] + b"\x00"
                        try:
                            ptr = self._pm.read_ulonglong(addr)
                            self._pm.write_bytes(ptr if ptr > 0x10000 else addr, b, len(b))
                        except:
                            self._pm.write_bytes(addr, b, len(b))
                    success = True

                if self._values_equal(self._read_memory(addr, flag_type), value, flag_type):
                    if randomize:
                        time.sleep(random.uniform(0.001, 0.01))
                    return True, None

                raise Exception("Verification failed")

            except Exception as e:
                if attempt == max_retries:
                    return False, str(e)
                time.sleep(backoff)
                backoff *= 1.5 + random.random() * 0.5 if randomize else 2

        return False, "Max retries exceeded"

    def _start_auto_reapply(self):
        def reapply_daemon():
            while True:
                time.sleep(self.monitor_sleep)

                if not self._auto_reapply_enabled:
                    continue

                if not self._pm or not self._base:
                    continue

                if self._suppress_guard:
                    continue

                try:
                    flags = self.load_user_flags()
                    if not flags:
                        continue

                    if not self._check_if_reapply_needed(flags, threshold_ratio=0.4):
                        print("[Auto Reapply] All flags still correct – skipping")
                        continue

                    print("[Auto Reapply] Detected flag resets – reapplying...")
                    if self._window:
                        self._window.evaluate_js('showToast("Flags reset detected – reapplying...", false)')

                    result = self.apply_flags_to_roblox(
                        flags,
                        batch_size=80,
                        delay_between_batches=0.15 if not self.config.get('randomization', True) else random.uniform(0.1, 1),
                        max_retries=3 if self.config.get('timing_attack', True) else 2,
                        verbose=False
                    )

                    success = result.get('success', 0)
                    fail = result.get('fail', 0)
                    msg = result.get('message', '')

                    status_symbol = '+' if success > fail else '-'
                    total = success + fail
                    print(f"[Auto Reapply] {status_symbol} {success}/{total} flags reapplied")

                    if self._window:
                        escaped = msg.replace('\\', '\\\\').replace('"', '\\"')
                        is_error = fail > success
                        self._window.evaluate_js(f'showToast("{escaped}", {str(is_error).lower()})')

                    if self.config.get('randomization', True):
                        time.sleep(random.uniform(0.1, 0.4))

                except Exception as e:
                    print(f"[Auto Reapply] Error in daemon: {e}")
                    time.sleep(1)


        self._auto_reapply_thread = threading.Thread(target=reapply_daemon, daemon=True)
        self._auto_reapply_thread.start()
        print(f"[Auto Reapply] Daemon started | Monitor: {self.monitor_sleep}s | Reapply interval logic: {'Instant (every check)' if self._auto_reapply_enabled else 'Disabled'}")

    def open_and_clean_file(self):
        if not self._window:
            return {"error": "Window not initialized."}
        files = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=('JSON Files (*.json)', 'All Files (*.*)')
        )
        if not files:
            return {"error": "No file selected."}
        filepath = files[0]
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            content_json = self.safe_load_json(content)
            official_flags = self.fetch_official_flags()
            cleaned = self.convert_and_filter_flags(content_json, official_flags)
            return {"cleanedFlags": cleaned}
        except Exception as e:
            return {"error": f"Failed to process file: {str(e)}"}

    def cleanFlagsAndRenameFile(self):
        if not self._window:
            return {"error": "Window not initialized."}
        files = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=('JSON Files (*.json)', 'All Files (*.*)')
        )
        if not files:
            return {"error": "No file selected."}
        return self.clean_flags_from_file(files[0], save_to_disk=True)

    @staticmethod
    def safe_load_json(content):
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            idx = e.pos
            truncated = content[:idx]
            open_braces = truncated.count('{') - truncated.count('}')
            open_brackets = truncated.count('[') - truncated.count(']')
            truncated += '}' * open_braces + ']' * open_brackets
            try:
                return json.loads(truncated)
            except Exception:
                return {}

    @staticmethod
    def fetch_official_flags():
        url = "https://github.com/Jovan1-marker/Roblox-Offsets/blob/main/FFlags.hpp"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            text = response.text
            flags = re.findall(r'uintptr_t\s+(\w+)\s*=', text)
            return set(flags)
        except Exception as e:
            print(f"Warning: Failed to fetch official flags: {e}")
            return None

    @staticmethod
    def convert_and_filter_flags(input_data, valid_clean_names):
        def determine_type(val):
            val_str = str(val).lower()
            if val_str in ["true", "false"]:
                return "bool"
            try:
                int(val)
                return "int"
            except Exception:
                return "string" 

        result = []

        def process_flag(name: str, value):
            if valid_clean_names is None:
                final_name = name.strip()
            else:
                final_name = Api.clean_flag_name(name.strip())
            if valid_clean_names is not None and final_name not in valid_clean_names:
                return None

            val_str = "True" if str(value).lower() == "true" else "False" if str(value).lower() == "false" else str(value)
            val_type = determine_type(value)

            return {"name": final_name, "value": val_str, "type": val_type}

        if isinstance(input_data, dict):
            for key, value in input_data.items():
                processed = process_flag(key, value)
                if processed:
                    result.append(processed)

        elif isinstance(input_data, list):
            for item in input_data:
                if not isinstance(item, dict) or "name" not in item:
                    continue
                name = item["name"]
                value = item.get("value", "")
                processed = process_flag(name, value)
                if processed:
                    result.append(processed)

        return result

    def clean_flags_from_file(self, filepath, save_to_disk=True):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return {"error": f"Failed to load file: {e}"}
        content_json = self.safe_load_json(content)
        official_flags = self.fetch_official_flags()
        try:
            cleaned = self.convert_and_filter_flags(content_json, official_flags)
        except Exception as e:
            return {"error": f"Unsupported format: {e}"}
        if save_to_disk:
            new_filename = self.random_filename()
            new_path = os.path.join(os.path.dirname(filepath), new_filename)
            try:
                with open(new_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned, f, indent=4)
                return {"success": True, "message": f"Cleaned saved as {new_filename}", "path": new_path}
            except Exception as e:
                return {"error": f"Save failed: {e}"}
        return {"success": True, "flags": cleaned}

    @staticmethod
    def random_filename(prefix="", extension=".json", length=6):
        rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
        return f"{prefix}{rand_str}{extension}"

    def export_flags(self, flags=None):
        if not self._window:
            return {"error": "Window not initialized."}
        
        if flags is None:
            flags = self.load_user_flags()
        
        export_dict = {}
        for flag in flags:
            name = flag.get("name", "").strip()
            value = flag.get("value", "").strip()
            if name:
                export_dict[name] = value
        
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            allow_multiple=False,
            file_types=('JSON Files (*.json)', 'All Files (*.*)'),
            save_filename="my_fflags.json"
        )
        
        if not result or not result[0]:
            print("[-] Export cancelled by user")
            return {"error": "Export cancelled by user"}
        
        filepath = result[0]
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_dict, f, indent=4)
            print(f"[+] Exported {len(export_dict)} flags to {filepath} (simple dict format)")
            return {"success": True, "path": str(filepath)}
        except Exception as e:
            print(f"[-] Failed to export: {e}")
            return {"error": str(e)}

    def set_window(self, window):
        self._window = window
        
    def minimize_window(self):
        if self._window:
            self._window.minimize()
            
    def close_window(self):
        if self._window:
            self._window.destroy()
            
    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)

            migrated = DEFAULT_CONFIG.copy()
            migrated.update({k: v for k, v in loaded.items() if k in migrated})

            if migrated != loaded:
                print("[CONFIG] Migrated old config – removed obsolete keys and added missing ones")
                try:
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(migrated, f, indent=4)
                except Exception as save_err:
                    print(f"[CONFIG] Failed to save migrated config: {save_err}")

            return migrated

        except FileNotFoundError:
            print("[CONFIG] No config file found – using defaults")
            return DEFAULT_CONFIG.copy()

        except json.JSONDecodeError as e:
            print(f"[CONFIG] Corrupted config file – resetting to defaults: {e}")
            self.save_config()
            return DEFAULT_CONFIG.copy()

        except Exception as e:
            print(f"[CONFIG] Unexpected error loading config – using defaults: {e}")
            return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"[CONFIG] Failed to save: {e}")
    

        
    def get_theme(self):
        return self.config.get('theme', 'white')
    
    def save_theme(self, theme):
        self.config['theme'] = theme
        self.save_config()

        print(f"[+] Changed to: {theme.replace('_', ' ').title()}")

        return {"ok": True}
        
    def get_settings(self):
        return {
            "auto_apply_on_attach": self.config.get('auto_apply_on_attach', False),
            "rpc_enabled": self.config.get('rpc_enabled', True),
            "hide_key": self.config.get('hide_key', 'insert'),
            "safe_mode": self.config.get('safe_mode', True),
            "randomization": self.config.get('randomization', True),
            "timing_attack": self.config.get('timing_attack', True),
            "reapply": self.config.get('reapply', False),
            "offsetless": self.config.get('offsetless', False)
        }
    
    def get_preset_settings(self):
        return {
            "old_death_sound": self.config.get('old_death_sound', False),
            "mouse_cursor": self.config.get('mouse_cursor', 'default'),
            "old_avatar_editor_background": self.config.get('old_avatar_editor_background', False),
            "old_character_sounds": self.config.get('old_character_sounds', False),
            "emoji_type": self.config.get('emoji_type', 'default'),
            "use_custom_font": self.config.get('use_custom_font', False),
            "custom_font_path": self.config.get('custom_font_path', "")
        }
    
    def set_auto_apply_on_attach(self, enabled: bool):
        self.config['auto_apply_on_attach'] = bool(enabled)
        self.save_config()
        status = "enabled" if enabled else "disabled"
        print(f"[{'+' if enabled else '-'}] Auto-apply on attach {status}")
        return {"ok": True}
    
    def set_rpc_enabled(self, enabled: bool):
        self.config['rpc_enabled'] = bool(enabled)
        self.save_config()
        global rpc_enabled
        rpc_enabled = bool(enabled)
        status = "enabled" if enabled else "disabled"
        print(f"[{'+' if enabled else '-'}] Discord RPC {status}")
        return {"ok": True}
    
    def save_preset_settings(self, payload: dict):
        try:
            self.config['old_death_sound'] = bool(payload.get('old_death_sound', False))
            self.config['mouse_cursor'] = str(payload.get('mouse_cursor', 'default'))
            self.config['old_avatar_editor_background'] = bool(payload.get('old_avatar_editor_background', False))
            self.config['old_character_sounds'] = bool(payload.get('old_character_sounds', False))
            self.config['emoji_type'] = str(payload.get('emoji_type', 'default'))
            self.config['use_custom_font'] = bool(payload.get('use_custom_font', False))
            self.config['custom_font_path'] = str(payload.get('custom_font_path', ''))
            self.save_config()
            result = self.apply_nostalgia_presets()
            if "error" in result:
                print(f"[-] Failed to apply: {result['error']}")
                return {"ok": False, "error": result["error"]}
            else:
                print(f"[+] Successfully applied: {result.get('message', 'Presets applied!')}")
                return {"ok": True, "message": result.get("message", "Presets applied!")}
        except Exception as e:
            print(f"[-] Error: {str(e)}")
            return {"ok": False, "error": str(e)}
        
    def apply_custom_font(self):
        font_path = self.config.get('custom_font_path', '')
        if not font_path or not os.path.exists(font_path):
            return {"error": "No custom font selected or file not found."}
        version_folder = self.find_roblox_version_folder()
        if not version_folder:
            return {"error": "Roblox installation not found."}
        fonts_dir = os.path.join(version_folder, "content", "fonts")
        if not os.path.exists(fonts_dir):
            return {"error": "Fonts directory not found in Roblox installation."}
        target_fonts = [
            "AccanthisADFStd-Regular.ttf", "AmaticSC-Bold.ttf", "AmaticSC-Regular.ttf", "Arimo-Bold.ttf",
            "Arimo-Regular.ttf", "Balthazar-Regular.ttf", "Bangers-Regular.ttf", "BuilderExtended-Bold.ttf",
            "BuilderExtended-Regular.ttf", "BuilderExtended-SemiBold.ttf", "BuilderMono-Bold.ttf",
            "BuilderMono-Light.ttf", "BuilderMono-Regular.ttf", "BuilderSans-Bold.ttf",
            "BuilderSans-ExtraBold.ttf", "BuilderSans-Medium.ttf", "BuilderSans-Regular.ttf",
            "ComicNeue-Angular-Bold.ttf", "Creeper-Regular.ttf", "DenkOne-Regular.ttf",
            "Fondamento-Italic.ttf", "Fondamento-Regular.ttf", "FredokaOne-Regular.ttf",
            "GothamBlack.ttf", "GothamBold.ttf", "GothamBook.ttf", "GothamMedium.ttf",
            "GothamSemiBold.ttf", "GrenzeGotisch-Bold.ttf", "GrenzeGotisch-Regular.ttf",
            "Guru-Regular.ttf", "HWYGOTH.ttf", "Inconsolata-Regular.ttf", "IndieFlower-Regular.ttf",
            "JosefinSans-Regular.ttf", "Jura-Regular.ttf", "Kalam-Regular.ttf", "LuckiestGuy-Regular.ttf",
            "Merriweather-Italic.ttf", "Merriweather-Regular.ttf", "Michroma-Regular.ttf",
            "Montserrat-Black.ttf", "Montserrat-Bold.ttf", "Montserrat-Light.ttf", "Montserrat-Medium.ttf",
            "Montserrat-Regular.ttf", "Montserrat-SemiBold.ttf", "NotoNastArabicUI-Regular.ttf",
            "NotoSansBengaliUI-Regular.ttf", "NotoSansDevanagariUI-Regular.ttf", "NotoSansGeorgian-Regular.ttf",
            "NotoSansKhmerUI-Regular.ttf", "NotoSansMyanmarUI-Regular.ttf", "NotoSansSinhalaUI-Regular.ttf",
            "NotoSansThaiUI-Regular.ttf", "Nunito-Regular.ttf", "Oswald-Bold.ttf", "Oswald-Regular.ttf",
            "PatrickHand-Regular.ttf", "PermanentMarker-Regular.ttf", "PressStart2P-Regular.ttf",
            "Roboto-Bold.ttf", "Roboto-Italic.ttf", "Roboto-Mono-Regular.ttf",
            "Roboto-Regular.ttf", "RobotoCondensed-Regular.ttf", "RomanAntique.ttf", "Sarpanch-Bold.ttf",
            "Sarpanch-Regular.ttf", "SourceSans.ttf", "SourceSansBold.ttf", "SourceSansItalic.ttf",
            "SourceSansLight.ttf", "SourceSansPro-Bold.ttf", "SourceSansPro-Light.ttf",
            "SourceSansPro-Regular.ttf", "SourceSansPro-SemiBold.ttf", "SourceSansSemiBold.ttf",
            "SpecialElite-Regular.ttf", "TitilliumWeb-Bold.ttf", "TitilliumWeb-Regular.ttf",
            "Ubuntu-Italic.ttf", "Ubuntu-Regular.ttf", "zekton_rg.ttf",
        ]
        replaced = []
        skipped = []
        failed = []
        for target in target_fonts:
            dest = os.path.join(fonts_dir, target)
            if not os.path.exists(dest):
                skipped.append(target)
                continue
            try:
                shutil.copy2(font_path, dest)
                replaced.append(target)
            except PermissionError:
                failed.append(f"{target}: Permission denied – Run as Administrator!")
            except Exception as e:
                failed.append(f"{target}: {str(e)}")
        total_applied = len(replaced)
        if total_applied > 0:
            return {
                "success": True,
                "message": f"Custom font applied to {total_applied} font files! Relaunch Roblox to see full changes.",
                "applied_count": total_applied,
                "replaced": replaced[:10],
                "note": f"{len(skipped)} files skipped (not present in this version)"
            }
        else:
            return {
                "error": "No font files were replaced.",
                "details": failed or ["Run Velorin as Administrator and try again."]
            }
        
    def choose_custom_font(self):
        try:
            root = Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                title="Select Custom Font (.ttf or .otf)",
                filetypes=[("Font files", "*.ttf *.otf"), ("All files", "*.*")]
            )
            root.destroy()
            if path:
                self.config['custom_font_path'] = path
                self.save_config()
                result = self.apply_custom_font()
                if self._window:
                    if result.get("success"):
                        print(f"[FONT] Custom font applied to {result['applied_count']} files")
                        msg = result["message"]
                        self._window.evaluate_js(f'showToast("{msg}", false)')
                    else:
                        print(f"[FONT] Failed to apply custom font")
                        err = result.get("error", "Failed to apply font")
                        self._window.evaluate_js(f'showToast("{err}", true)')
                return result
            return {"path": ""}
        except Exception as e:
            return {"error": str(e)}

    def _check_if_reapply_needed(self, flags, threshold_ratio=0.5):
        """
        Check how many of the user's flags are currently different from desired values.
        Returns True if reapply seems needed.
        threshold_ratio: reapply if more than this % of flags are wrong/missing
        """
        if not self._pm or not self._base or not self.all_offsets:
            return True

        with self.offsets_lock:
            offsets = self.all_offsets.copy()

        wrong_count = 0
        total = len(flags)

        if total == 0:
            return False

        for flag in flags:
            clean_name = self.clean_flag_name(flag["name"])
            if clean_name not in offsets:
                continue

            addr = self._base + offsets[clean_name]
            desired_value = flag["value"]
            ftype = flag.get("type", "bool").lower()

            try:
                current = self._read_memory(addr, ftype)
                if not self._values_equal(current, desired_value, ftype):
                    wrong_count += 1
            except:
                wrong_count += 1

        return (wrong_count / total) >= threshold_ratio

    def _start_roblox_monitor(self):
        def monitor():
            last_running = False
            was_attached = False

            while True:
                pid = find_roblox_process()
                currently_running = pid is not None

                if currently_running:
                    if not self._pm:
                        try:
                            self._pm = pymem.Pymem(pid)
                        except Exception as e:
                            print(f"[Monitor] Failed to attach pymem: {e}")
                            self._pm = None

                    self._base = get_module_base(pid)
                    state = 'attached' if self._base else 'running'

                    if state == 'attached' and not was_attached:
                        if self._window:
                            try:
                                self._window.evaluate_js('showToast("Roblox attached successfully!", false)')
                            except:
                                pass
                        print("[+] Roblox fully attached")

                        if self.config.get('auto_apply_on_attach', False):
                            if self._window:
                                try:
                                    self._window.evaluate_js('showToast("Auto-applying your flags...", false)')
                                except:
                                    pass

                                def auto_apply_task():
                                    try:
                                        time.sleep(4)

                                        flags = self.load_user_flags()
                                        if not flags:
                                            print("[Auto Apply] No saved flags")
                                            if self._window:
                                                self._window.evaluate_js('showToast("No saved flags to auto-apply", true)')
                                            return

                                        result = self.apply_flags_to_roblox(flags)
                                        msg = result.get("message", "Auto-apply completed")
                                        success = result.get("success", 0)
                                        fail = result.get("fail", 0)
                                        is_error = fail > success or "not attached" in msg.lower()

                                        escaped_msg = msg.replace('\\', '\\\\').replace('"', '\\"')
                                        if self._window:
                                            try:
                                                self._window.evaluate_js(f'showToast("{escaped_msg}", {str(is_error).lower()})')
                                            except:
                                                pass

                                        status = "Success" if success > fail else "Partial/Failed"
                                        print(f"[Auto Apply] {status}: {msg}")
                                    except Exception as e:
                                        print(f"[Auto Apply] Error: {e}")
                                        if self._window:
                                            try:
                                                self._window.evaluate_js('showToast("Auto-apply failed", true)')
                                            except:
                                                pass

                                threading.Thread(target=auto_apply_task, daemon=True).start()
                        else:
                            if self._window:
                                try:
                                    self._window.evaluate_js('showToast("Auto-apply is disabled", false)')
                                except:
                                    pass

                        was_attached = True

                else:
                    if was_attached:
                        if self._window:
                            try:
                                self._window.evaluate_js('showToast("Roblox closed or detached", false)')
                            except:
                                pass
                        print("[-] Roblox detached")

                    self._pm = None
                    self._base = None
                    state = 'not_running'
                    was_attached = False

                if self._window:
                    try:
                        self._window.evaluate_js(f'window.updateRobloxStatus("{state}")')
                    except:
                        pass

                last_running = currently_running
                time.sleep(2)

        threading.Thread(target=monitor, daemon=True).start()

    def _cache_all_offsets(self):
        def cache_task():
            offsets = fetch_fflag_offsets()
            if offsets:
                with self.offsets_lock:
                    self.all_offsets = offsets
                if self._window:
                    try:
                        preset_list = sorted(list(offsets.keys()))
                        self._window.evaluate_js(f'window.populatePresetFlags({json.dumps(preset_list)})')
                    except Exception as e:
                        print(f"JS eval error in cache offsets: {e}")
        threading.Thread(target=cache_task, daemon=True).start()

    def load_user_flags(self):
        try:
            with open(USER_FLAGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                return DEFAULT_FLAGS[:]
            return [{**f, 'type': f.get('type', 'bool')} for f in data if isinstance(f, dict) and 'name' in f and 'value' in f] or DEFAULT_FLAGS[:]
        except Exception:
            return DEFAULT_FLAGS[:]

    def save_user_flags(self, flags):
        with self.offsets_lock:
            valid = set(self.all_offsets.keys())
        cleaned = [f for f in flags if self.clean_flag_name(f["name"]) in valid]
        try:
            with open(USER_FLAGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(cleaned, f, indent=4)
            print(f"[+] Saved {len(cleaned)} flags to disk")
            return {"status": "success"}
        except Exception as e:
            print(f"[-] Failed to save flags: {e}")
            return {"status": "error", "message": str(e)}

    def import_from_json(self):
        if not self._window:
            return {"error": "Window not initialized."}

        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=('JSON Files (*.json)', 'All Files (*.*)')
        )

        if not result or not result:
            print("[-] Import cancelled by user")
            return {"error": "Import cancelled by user"}

        use_offsetless = self.config.get('offsetless', False)
        
        if use_offsetless:
            print("[IMPORT] Offsetless mode ON → NO prefix cleaning, NO filtering")
            should_clean = False
            should_filter = False
        else:
            print("[IMPORT] Classic offset mode → prefix cleaning + filtering active")
            should_clean = True
            should_filter = True

        official_flags = self.fetch_official_flags() or set()

        with self.offsets_lock:
            known_names = official_flags.union(self.all_offsets.keys())

        all_imported_flags = []
        file_count = len(result)

        for filepath in result:
            print(f"[+] Loading flags from {filepath}")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                content_json = self.safe_load_json(content)

                if should_clean:
                    processed = self.convert_and_filter_flags(content_json, valid_clean_names=known_names)
                else:
                    processed = self.convert_and_filter_flags(content_json, valid_clean_names=None)

                all_imported_flags.extend(processed)
                print(f"[+] Loaded {len(processed)} flags from {os.path.basename(filepath)}")

            except Exception as e:
                print(f"[-] Failed to process {filepath}: {e}")
                continue

        if not all_imported_flags:
            return {"error": "No valid flags found in selected files."}

        seen = {}
        for flag in all_imported_flags:
            name = flag["name"]
            seen[name] = flag

        unique_flags = list(seen.values())

        print(f"[+] Imported and merged {len(unique_flags)} unique flags from {file_count} file(s)")
        return {"flags": unique_flags, "file_count": file_count}
    
    def kill_roblox(self):
        print("[+] Attempting to terminate Roblox process...")
        try:
            result = subprocess.run(
                ['taskkill', '/F', '/IM', 'RobloxPlayerBeta.exe'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print("[+] Roblox process terminated successfully")
                return {"success": True}
            else:
                print(f"[-] Failed to terminate Roblox: {result.stderr.strip() or 'Unknown error'}")
                return {"error": result.stderr.strip() or "Unknown error"}
        except Exception as e:
            print(f"[-] Exception: {e}")
            return {"error": str(e)}

    def apply_flags_to_roblox(self, flags, batch_size=100, delay_between_batches=0.3, max_retries=3, verbose=False):
        logger = logging.getLogger(__name__)
        total_input = len(flags)
        print(f"[APPLY] Starting injection for {total_input} flags...")

        if not self._pm or not self._base:
            print("[-] Apply failed: Roblox is not attached")
            return {"success": 0, "fail": len(flags), "removed": 0, "message": "Roblox not attached."}

        use_no_offset = self.config.get('offsetless', False)

        with self.offsets_lock:
            if not self.all_offsets and not use_no_offset:
                print("[-] Apply failed: FFlag offsets not loaded yet")
                return {"success": 0, "fail": len(flags), "removed": 0, "message": "FFlag offsets not loaded yet."}
            offsets = self.all_offsets.copy()

        print("[+] Roblox attached & offsets loaded" if not use_no_offset else "[+] Roblox attached (offsetless mode)")


        filtered_flags = []
        removed_flags = []
        for flag in flags:
            original_name = flag.get('name', '')
            if not original_name:
                continue
            if use_no_offset:
                filtered_flags.append(flag)
            else:
                clean_name = self.clean_flag_name(original_name)
                if clean_name in offsets:
                    flag['clean_name'] = clean_name
                    filtered_flags.append(flag)
                else:
                    removed_flags.append(original_name)

        if removed_flags:
            print(f"[-] Removed {len(removed_flags)} invalid/unknown flags")
        else:
            print("[+] All flags are valid")

        try:
            self.save_user_flags(filtered_flags)
            print(f"[+] Saved {len(filtered_flags)} valid flags to disk")
        except Exception as e:
            print(f"[-] Failed to save cleaned flags: {e}")
            logger.error(f"Failed to save user flags: {e}")

        success_count = 0
        fail_count = 0
        error_flags = []

        if use_no_offset:
            injector = New_no_offset_injector(self._pm)
            if not injector.get_singleton():
                return {"success": 0, "fail": len(filtered_flags), "removed": len(removed_flags),
                        "message": "Failed to find singleton in offsetless mode"}

            print(f"[+] Injecting {len(filtered_flags)} flags (offsetless, with verification, auto-skip on fail)")

            for flag in filtered_flags:
                name = flag.get('name')
                value = flag.get('value')
                flag_type = flag.get('type', 'string').lower()

                set_success = False
                try:
                    if flag_type == 'string':
                        set_success = injector.set_string(name, value)
                    elif flag_type == 'int':
                        set_success = injector.set_int(name, int(value))
                    elif flag_type == 'bool':
                        set_success = injector.set_int(name, 1 if self._parse_bool(value) else 0)
                    elif flag_type in ('float', 'double'):
                        set_success = injector.set_float(name, float(value))
                except Exception as e:
                    print(f"[-] Auto-skipped {name} (set failed): {str(e)}")
                    fail_count += 1
                    error_flags.append(f"{name} (set error: {str(e)})")
                    continue

                if not set_success:
                    print(f"[-] Auto-skipped {name} (set returned False)")
                    fail_count += 1
                    error_flags.append(f"{name} (set returned False)")
                    continue

                verified = False
                try:
                    read_val = None
                    if flag_type == 'string':
                        read_val = injector.get_string(name)
                    elif flag_type in ('int', 'bool'):
                        read_val = injector.get_int(name)
                        if flag_type == 'bool':
                            read_val = "True" if read_val != 0 else "False"
                        else:
                            read_val = str(read_val)
                    elif flag_type in ('float', 'double'):
                        read_val = str(injector.get_float(name))

                    if read_val is not None and self._values_equal(read_val, value, flag_type):
                        verified = True
                except Exception as e:
                    print(f"[-] Verification failed for {name}: {str(e)}")

                if verified:
                    success_count += 1
                    if verbose:
                        print(f"[+] Applied & verified {name} = {value}")
                else:
                    fail_count += 1
                    error_flags.append(f"{name} (verification failed)")
                    print(f"[-] Applied but verification failed for {name} (skipped)")

        else:
            print(f"[+] Injecting {len(filtered_flags)} valid flags (classic offsets)")

            def write_memory(addr, value, flag_type):
                last_error = None
                backoff = 0.1
                for attempt in range(max_retries + 1):
                    try:
                        if flag_type == "bool":
                            bool_val = str(value).lower() == "true"
                            self._pm.write_bool(addr, bool_val)
                        elif flag_type == "int":
                            ival = int(value)
                            try:
                                ptr = self._pm.read_ulonglong(addr)
                                if ptr and ptr > 0x10000:
                                    self._pm.write_int(ptr, ival)
                                else:
                                    self._pm.write_int(addr, ival)
                            except Exception:
                                self._pm.write_int(addr, ival)
                        elif flag_type in ("float", "double"):
                            self._pm.write_float(addr, float(value))
                        elif flag_type == "string":
                            s = str(value)
                            if len(s) > 255:
                                raise ValueError("String too long (>255 bytes)")
                            b = s.encode("utf-8") + b"\x00"
                            try:
                                str_ptr = self._pm.read_ulonglong(addr)
                                target_addr = str_ptr if (str_ptr and str_ptr > 0x10000) else addr
                                self._pm.write_bytes(target_addr, b, len(b))
                            except Exception:
                                self._pm.write_bytes(addr, b, len(b))
                        else:
                            raise ValueError(f"Unsupported flag type: {flag_type}")
                        return True, None
                    except Exception as e:
                        last_error = str(e)
                        if verbose:
                            logger.debug(f"Write attempt {attempt + 1}/{max_retries + 1} failed for {flag_type} at {hex(addr)}: {last_error}")
                        if attempt < max_retries:
                            time.sleep(backoff)
                            backoff = min(backoff * 3, 1.0)
                return False, last_error

            total_flags = len(filtered_flags)
            for start_idx in range(0, total_flags, batch_size):
                end_idx = min(start_idx + batch_size, total_flags)
                batch = filtered_flags[start_idx:end_idx]

                for flag in batch:
                    original_name = flag.get('name', 'unknown')
                    clean_name = flag.get('clean_name') 
                    value = flag.get('value')
                    ftype = flag.get('type', 'string').lower()

                    if ftype == "string" and isinstance(value, str) and len(value) > 255:
                        fail_count += 1
                        error_flags.append(f"{original_name} (string too long >255)")
                        continue

                    addr = self._base + offsets[clean_name]

                    if original_name not in self._original_values:
                        try:
                            current_val = None
                            if ftype == "bool":
                                current_val = "True" if self._pm.read_bool(addr) else "False"
                            elif ftype == "int":
                                try:
                                    ptr = self._pm.read_ulonglong(addr)
                                    current_val = str(self._pm.read_int(ptr if ptr > 0x10000 else addr))
                                except:
                                    current_val = str(self._pm.read_int(addr))
                            elif ftype in ("float", "double"):
                                current_val = str(self._pm.read_float(addr))
                            elif ftype == "string":
                                try:
                                    ptr = self._pm.read_ulonglong(addr)
                                    target = ptr if ptr > 0x10000 else addr
                                    b = self._pm.read_bytes(target, 256)
                                    current_val = b.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
                                except:
                                    current_val = ""
                            if current_val is not None:
                                self._original_values[original_name] = current_val
                        except Exception:
                            pass

                    success, error = write_memory(addr, value, ftype)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        error_msg = error or "unknown error"
                        error_flags.append(f"{original_name} ({error_msg})")

                progress = min(start_idx + len(batch), total_flags)
                if self._window:
                    try:
                        self._window.evaluate_js(f'window.updateInjectionProgress({progress}, {total_flags})')
                    except Exception as e:
                        if verbose:
                            logger.debug(f"Failed to update progress via JS: {e}")

                if delay_between_batches > 0:
                    time.sleep(delay_between_batches)

        total = success_count + fail_count
        parts = []
        if success_count == total and total > 0:
            print(f"[+] All {success_count} flags applied successfully!")
            parts.append(f"All {success_count} flags applied successfully!")
        elif success_count > 0:
            print(f"[+] Applied {success_count}/{total} flags | [-] Failed: {fail_count}")
            parts.append(f"Applied {success_count}/{total} flags")
        else:
            print(f"[-] No flags applied (all {fail_count} failed)")
            parts.append("No flags applied")

        if fail_count > 0:
            parts.append(f"Failed: {fail_count}")
        if removed_flags:
            parts.append(f"Removed {len(removed_flags)} invalid/unknown flags")

        result_msg = " • ".join(parts) if parts else "Injection complete – no changes."

        if success_count > 0:
            self._guard_active = True
            self._auto_reapply_enabled = True

        print(f"[APPLY] {'+' if success_count > 0 else '-'} Success: {success_count} | Failed: {fail_count} | Removed: {len(removed_flags)}")

        if self._window:
            try:
                is_error = fail_count > 0 or success_count == 0
                escaped_msg = result_msg.replace('\\', '\\\\').replace('"', '\\"')
                self._window.evaluate_js(f'showToast("{escaped_msg}", {str(is_error).lower()})')
            except Exception as e:
                print(f"[TOAST] Failed to send: {e}")

        return {
            "success": success_count,
            "fail": fail_count,
            "removed": len(removed_flags),
            "message": result_msg,
            "errors": error_flags
        }


    def uninject_flags(self, batch_size=100, delay_between_batches=0.3, max_retries=3, verbose=False):
        if not self._pm or not self._base:
            print("[-] Uninject failed: Roblox is not attached")
            return {"success": 0, "fail": 0, "message": "Roblox not attached."}
        
        with self.offsets_lock:
            if not self.all_offsets:
                print("[-] Uninject failed: FFlag offsets not loaded yet")
                return {"success": 0, "fail": 0, "message": "FFlag offsets not loaded yet."}
            offsets = self.all_offsets.copy()
        
        original_items = list(self._original_values.items())
        total_flags = len(original_items)
        
        if total_flags == 0:
            print("[+] No flags to restore – nothing injected previously")
            self._guard_active = False
            self._auto_reapply_enabled = False
            return {"success": 0, "fail": 0, "message": "No previously injected flags to restore."}
        
        print(f"[UNINJECT] Starting restoration for {total_flags} flags...")
        
        success_count = 0
        fail_count = 0
        error_flags = []
        
        self._suppress_guard = True
        
        def restore_memory(addr, original_value, inferred_type):
            last_error = None
            backoff = 0.1
            for attempt in range(max_retries + 1):
                try:
                    if inferred_type == "bool":
                        bool_val = str(original_value).lower() == "true"
                        self._pm.write_bool(addr, bool_val)
                    elif inferred_type == "int":
                        ival = int(original_value)
                        try:
                            ptr = self._pm.read_ulonglong(addr)
                            target = ptr if (ptr and ptr > 0x10000) else addr
                            self._pm.write_int(target, ival)
                        except:
                            self._pm.write_int(addr, ival)
                    elif inferred_type in ("float", "double"):
                        self._pm.write_float(addr, float(original_value))
                    elif inferred_type == "string":
                        s = str(original_value)
                        if len(s) > 255:
                            raise ValueError("Original string too long (>255 bytes)")
                        b = s.encode("utf-8") + b"\x00"
                        try:
                            ptr = self._pm.read_ulonglong(addr)
                            target = ptr if (ptr and ptr > 0x10000) else addr
                            self._pm.write_bytes(target, b, len(b))
                        except:
                            self._pm.write_bytes(addr, b, len(b))
                    else:
                        raise ValueError(f"Unsupported type: {inferred_type}")
                    
                    return True, None
                except Exception as e:
                    last_error = str(e)
                    if attempt < max_retries:
                        time.sleep(backoff)
                        backoff = min(backoff * 3, 1.0)
            return False, last_error
        
        def infer_type(value):
            if isinstance(value, str):
                val_lower = value.lower()
                if val_lower in ("true", "false"):
                    return "bool"
                try:
                    int(value)
                    return "int"
                except:
                    try:
                        float(value)
                        return "float"
                    except:
                        return "string"
            return "string" 
        
        for start_idx in range(0, total_flags, batch_size):
            end_idx = min(start_idx + batch_size, total_flags)
            batch = original_items[start_idx:end_idx]
            
            for name, original in batch:
                clean_name = self.clean_flag_name(name)
                if clean_name not in offsets:
                    fail_count += 1
                    error_flags.append(f"{name} (offset no longer valid)")
                    continue
                
                addr = self._base + offsets[clean_name]
                ftype = infer_type(original)
                
                success, error = restore_memory(addr, original, ftype)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    error_msg = error or "unknown error"
                    error_flags.append(f"{name} ({error_msg})")
            
            progress = min(start_idx + len(batch), total_flags)
            if self._window:
                try:
                    self._window.evaluate_js(f'window.updateInjectionProgress({progress}, {total_flags})')  # Reuse progress if UI supports
                except:
                    pass
            
            if delay_between_batches > 0:
                time.sleep(delay_between_batches)

        self._original_values.clear()
        self._guard_active = False
        self._auto_reapply_enabled = False
        
        parts = []
        if success_count == total_flags:
            print(f"[+] All {success_count} original values restored successfully!")
            parts.append(f"All {success_count} flags restored successfully!")
        elif success_count > 0:
            print(f"[+] Restored {success_count}/{total_flags} | [-] Failed: {fail_count}")
            parts.append(f"Restored {success_count}/{total_flags} flags")
        else:
            print(f"[-] No values restored (all {fail_count} failed)")
            parts.append("No values restored")
        
        if fail_count > 0:
            parts.append(f"Failed: {fail_count}")
        
        result_msg = " • ".join(parts) if parts else "Restoration complete – no changes."
        
        if self._window:
            try:
                is_error = fail_count > success_count
                escaped_msg = result_msg.replace('\\', '\\\\').replace('"', '\\"')
                self._window.evaluate_js(f'showToast("{escaped_msg}", {str(is_error).lower()})')
            except Exception as e:
                print(f"[TOAST] Failed to send uninject toast: {e}")
        
        print(f"[UNINJECT] {'+' if success_count > fail_count else '-'} Success: {success_count} | Failed: {fail_count}")
        
        return {
            "success": success_count,
            "fail": fail_count,
            "message": result_msg,
            "errors": error_flags
        }

    def find_roblox_version_folder(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Roblox\Environments\roblox-player")
            value, _ = winreg.QueryValueEx(key, "VersionFolder")
            winreg.CloseKey(key)
            path = os.path.join(os.getenv("LOCALAPPDATA"), "Roblox", "Versions", value)
            if os.path.exists(path):
                return path
        except Exception:
            pass
        versions_dir = os.path.join(os.getenv("LOCALAPPDATA"), "Roblox", "Versions")
        if os.path.exists(versions_dir):
            for folder in os.listdir(versions_dir):
                full = os.path.join(versions_dir, folder)
                if os.path.isdir(full) and os.path.exists(os.path.join(full, "RobloxPlayerBeta.exe")):
                    return full
        return None
    
    def apply_nostalgia_presets(self):
        presets = self.get_preset_settings()
        version_folder = self.find_roblox_version_folder()
        if not version_folder:
            return {"error": "Roblox installation not found."}
        content_root = version_folder
        replaced = 0
        restored = 0
        failed = []
        files_to_apply = []

        backup_dir = APP_DIR / "cursor_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_arrow = backup_dir / "default_ArrowCursor.png"
        backup_far = backup_dir / "default_ArrowFarCursor.png"
        cursor_path = os.path.join(content_root, "content", "textures", "Cursors", "KeyboardMouse")
        arrow_path = os.path.join(cursor_path, "ArrowCursor.png")
        far_path = os.path.join(cursor_path, "ArrowFarCursor.png")

        if not backup_arrow.exists() and os.path.exists(arrow_path):
            try:
                shutil.copy2(arrow_path, backup_arrow)
            except Exception as e:
                failed.append(f"Backup ArrowCursor: {str(e)}")
        if not backup_far.exists() and os.path.exists(far_path):
            try:
                shutil.copy2(far_path, backup_far)
            except Exception as e:
                failed.append(f"Backup ArrowFarCursor: {str(e)}")

        cursor_preset = presets["mouse_cursor"]
        cursor_name_map = {
            "default": "Default",
            "classic": "Classic",
            "blackdot": "Black Dot",
            "whitedot": "White Dot",
            "diamondsword": "Diamond Sword",
            "pink": "Pink Cross",
            "girl": "Girl"
        }
        cursor_display = cursor_name_map.get(cursor_preset.lower(), "Unknown")

        if cursor_preset.lower() != "default":
            cursor_url = {
                "classic": "https://www.rw-designer.com/cursor-view/134299.png",
                "blackdot": "https://www.rw-designer.com/cursor-view/150775.png",
                "whitedot": "https://www.rw-designer.com/cursor-view/150777.png",
                "diamondsword": "https://www.rw-designer.com/cursor-view/69125.png",
                "pink": "https://www.rw-designer.com/cursor-view/138479.png",
                "girl": "https://www.rw-designer.com/cursor-view/124576.png",
            }.get(cursor_preset.lower())

            if cursor_url:
                files_to_apply.extend([
                    ("ArrowCursor.png", cursor_url, os.path.join("content", "textures", "Cursors", "KeyboardMouse", "ArrowCursor.png")),
                    ("ArrowFarCursor.png", cursor_url, os.path.join("content", "textures", "Cursors", "KeyboardMouse", "ArrowFarCursor.png"))
                ])
                replaced += 2
                print(f"[+] Changed to: {cursor_display}")
        else:
            if backup_arrow.exists() and backup_far.exists():
                try:
                    os.makedirs(cursor_path, exist_ok=True)
                    shutil.copy2(backup_arrow, arrow_path)
                    shutil.copy2(backup_far, far_path)
                    restored += 2
                    print(f"[+] Restored to: Default")
                except Exception as e:
                    failed.append(f"Restore cursor: {str(e)}")
                    
        if presets["old_death_sound"]:
            files_to_apply.append(("ouch.ogg", "https://archive.org/download/ouch_20240329/ouch.ogg", os.path.join("content", "sounds", "ouch.ogg")))
        # DONT REMOVE TS IMMA FIX THIS SOON NIGGER
        # if presets["old_avatar_editor_background"]:
        # files_to_apply.append(("Mobile.rbxl", "https://github.com/MaximumADHD/Roblox-Old-Avatar-Editor/raw/main/Mobile.rbxl", os.path.join("ExtraContent", "places", "Mobile.rbxl")))
        # if presets["old_character_sounds"]:
        # base_url = "https://github.com/ic3w0lf22/Roblox-2014-Sounds/raw/master/"
        if files_to_apply:
            with tempfile.TemporaryDirectory() as tmpdir:
                for filename, source, rel_path in files_to_apply:
                    dest = os.path.join(content_root, rel_path)
                    try:
                        src = os.path.join(tmpdir, filename)
                        req = urllib.request.Request(source, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req) as response, open(src, 'wb') as out_file:
                            shutil.copyfileobj(response, out_file)
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        shutil.copy2(src, dest)
                        replaced += 1
                    except Exception as e:
                        failed.append(f"{filename}: {str(e)}")
        msg_parts = []
        if replaced > 0:
            msg_parts.append(f"Applied {replaced} files.")
        if restored > 0:
            msg_parts.append(f"Restored {restored} originals.")
        if not msg_parts:
            msg = "No changes needed."
        else:
            msg = " ".join(msg_parts)
        if failed:
            msg += f" Failed: {', '.join(failed[:3])}"
        return {"success": True, "message": msg.strip() + " Relaunch Roblox for changes!"}
    
        print(f"[PRESETS] Applied nostalgia settings: {msg}")

html="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FFlag Manager</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />
    <style>
        body {
            font-family: 'Inter', sans-serif;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            overflow: hidden;
            height: 100vh;
            display: flex;
            flex-direction: column;
            background: #0a0a0a;
            color: #e0e0e0;
            -webkit-app-region: no-drag;
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            transition: background-image 0.5s ease;
        }
        .material-symbols-rounded {
            font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
            font-size: 18px;
        }
        html, body { -webkit-app-region: no-drag !important; }
        body * { -webkit-app-region: no-drag !important; }
        .title-bar { -webkit-app-region: drag; }
        .title-bar-btn { -webkit-app-region: no-drag; }
        #toast, .modal-backdrop, .modal-content,
        .btn, .input-field, .material-symbols-rounded, a, input, textarea, select,
        #flag-list, #kill-roblox-btn, #roblox-status { -webkit-app-region: no-drag !important; }
        .title-bar { position: relative; z-index: 1000; }
        .title-text { pointer-events: none; }
        /* Scrollbar */
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { border-radius: 2px; background: #333333; }
        ::-webkit-scrollbar-thumb:hover { background: #555555; }
        /* Flag Row */
        .flag-row {
            transition: all 0.15s ease;
            border-bottom: 1px solid #222222;
        }
        .flag-row:hover {
            background-color: #181818;
        }
        .flag-row.selected {
            background-color: #1a2332;
            border-left: 2px solid #4285f4;
        }
        .flag-row.to-remove {
            background-color: #4a1a1a !important;
            animation: pulse-red 1.5s infinite;
        }
        @keyframes pulse-red {
            0% { background-color: #4a1a1a; }
            50% { background-color: #6a2a2a; }
            100% { background-color: #4a1a1a; }
        }
        /* Modal */
        .modal-backdrop {
            transition: opacity 0.2s ease, visibility 0.2s;
        }
        .modal-content {
            transition: transform 0.2s ease, opacity 0.2s;
        }
        /* Toast */
        #toast {
            transition: all 0.2s ease;
            border-radius: 6px;
            pointer-events: none;
        }
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        #toast.show {
            animation: slideUp 0.2s ease;
        }
        /* Input */
        .input-field {
            background: #1a1a1a;
            border: 1px solid #333333;
            color: #e0e0e0;
            transition: all 0.15s ease;
        }
        .input-field:focus {
            border-color: #4285f4;
            box-shadow: 0 0 0 2px rgba(66, 133, 244, 0.2);
        }
        /* Button */
        .btn {
            transition: all 0.15s ease;
            font-weight: 500;
        }
        .btn:hover {
            transform: translateY(-1px);
        }
        .btn:active {
            transform: translateY(0);
        }
        .btn-primary {
            background: #4285f4;
            color: white;
        }
        .btn-primary:hover {
            background: #3367d6;
        }
        .btn-secondary {
            background: #2a2a2a;
            color: #e0e0e0;
            border: 1px solid #333333;
        }
        .btn-secondary:hover {
            background: #333333;
            color: #ffffff;
        }
        .btn-danger {
            background: #2a1a1a;
            color: #ff6b6b;
            border: 1px solid #333333;
        }
        .btn-danger:hover {
            background: #3a1a1a;
        }
        .glow-red { box-shadow: 0 0 20px 8px rgba(239, 68, 68, 0.6); }
        .glow-yellow { box-shadow: 0 0 20px 8px rgba(234, 179, 8, 0.6); }
        .glow-green { box-shadow: 0 0 24px 10px rgba(34, 197, 94, 0.6); }
        #flag-list { overflow-x: hidden; }
        .row-fixed { height: 40px; }
        .animated-gradient {
            background-image: linear-gradient(90deg, #a855f7, #3b82f6, #22d3ee, #a855f7);
            background-size: 300% 300%;
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            animation: gradientShift 4s ease infinite;
        }
        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        #discordTabBtn {
            margin-top: auto;  /* Pushes it to the very bottom if the sidebar uses flex column */
            padding: 12px;     /* Match other icons' padding */
            opacity: 0.7;
            transition: opacity 0.2s;
        }

        #discordTabBtn:hover {
            opacity: 1;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px;
        }
        /* Theme */
        [data-theme="white"] body { background: #ffffff; color: #111827; }
        [data-theme="white"] .bg-black { background: #ffffff !important; }
        [data-theme="white"] .bg-gray-900 { background: #f3f4f6 !important; }
        [data-theme="white"] .border-gray-800 { border-color: #e5e7eb !important; }
        [data-theme="white"] .text-gray-400 { color: #6b7280 !important; }
        [data-theme="white"] .text-gray-200 { color: #111827 !important; }
        [data-theme="white"] .modal-content { background: #f9fafb !important; }
        [data-theme="white"] .input-field { background: #f3f4f6 !important; border-color: #d1d5db !important; color: #111827 !important; }
        [data-theme="white"] .input-field:focus { box-shadow: 0 0 0 2px rgba(59,130,246,0.25) !important; border-color: #93c5fd !important; }
        [data-theme="white"] .btn-secondary { background: #f3f4f6 !important; color: #111827 !important; border-color: #d1d5db !important; }
        [data-theme="white"] .btn-secondary:hover { background: #e5e7eb !important; }
        [data-theme="white"] .btn-danger { background: #fee2e2 !important; color: #b91c1c !important; border-color: #fecaca !important; }
        [data-theme="white"] .btn-danger:hover { background: #fecaca !important; }
        [data-theme="white"] .flag-row { border-bottom: 1px solid #e5e7eb !important; }
        [data-theme="white"] .flag-row:hover { background-color: #f9fafb !important; }
        [data-theme="white"] [data-theme="white"] .flag-row.to-remove { background-color: #fecaca !important; }
        [data-theme="white"] .modal-backdrop { background: rgba(0,0,0,0.15) !important; }
        [data-theme="white"] .table-header { background: #f9fafb !important; border-color: #e5e7eb !important; }
        [data-theme="white"] #toast { background: #e5e7eb !important; color: #111827 !important; }
        [data-theme="white"] .text-white { color: #111827 !important; }
        [data-theme="white"] .text-gray-100 { color: #1f2937 !important; }
        [data-theme="white"] .material-symbols-rounded { color: #374151 !important; }
        [data-theme="white"] .btn-primary { color: #ffffff !important; }
        [data-theme="white"] .btn-primary .material-symbols-rounded { color: #ffffff !important; }
        [data-theme="black"] body { background: #0a0a0a; color: #e0e0e0; }
        [data-theme="black"] .bg-black { background: #000000 !important; }
        [data-theme="black"] .bg-gray-900 { background: #111111 !important; }
        [data-theme="dark_purple"] body { background: #0b0a14; color: #ddd6fe; }
        [data-theme="dark_purple"] .bg-black { background: #0f0b1a !important; }
        [data-theme="dark_purple"] .bg-gray-900 { background: #120d22 !important; }
        [data-theme="dark_purple"] .border-gray-800 { border-color: #2d2249 !important; }
        [data-theme="dark_purple"] .text-gray-400 { color: #b6a7e6 !important; }
        [data-theme="dark_purple"] .modal-content { background: #1a1530 !important; }
        [data-theme="dark_blue"] body { background: #0a0f1a; color: #dbeafe; }
        [data-theme="dark_blue"] .bg-black { background: #0b1324 !important; }
        [data-theme="dark_blue"] .bg-gray-900 { background: #0e1a33 !important; }
        [data-theme="dark_blue"] .border-gray-800 { border-color: #1f2a44 !important; }
        [data-theme="dark_blue"] .text-gray-400 { color: #93c5fd !important; }
        [data-theme="dark_blue"] .modal-content { background: #162544 !important; }
     
        [data-theme="white_pink"] body { background: #ffffff; color: #111827; }
        [data-theme="white_pink"] .bg-black { background: #ffffff !important; }
        [data-theme="white_pink"] .bg-gray-900 { background: #f9fafb !important; }
        [data-theme="white_pink"] .border-gray-800 { border-color: #e5e7eb !important; }
        [data-theme="white_pink"] .text-gray-500 { color: #374151 !important; }
        [data-theme="white_pink"] .text-gray-400 { color: #374151 !important; }
        [data-theme="white_pink"] .text-gray-300 { color: #374151 !important; }
        [data-theme="white_pink"] .text-gray-200 { color: #4b5563 !important; }
        [data-theme="white_pink"] .modal-content { background: #ffffff !important; border-color: #f3f4f6 !important; }
        [data-theme="white_pink"] .input-field { background: #ffffff !important; border: 1px solid #e5e7eb !important; color: #111827 !important; }
        [data-theme="white_pink"] .input-field::placeholder { color: #9ca3af !important; }
        [data-theme="white_pink"] .input-field:focus { box-shadow: 0 0 0 2px rgba(236,72,153,0.25) !important; border-color: #f472b6 !important; }
        [data-theme="white_pink"] .btn-secondary { background: #f9fafb !important; color: #111827 !important; border-color: #e5e7eb !important; }
        [data-theme="white_pink"] .btn-secondary:hover { background: #f3f4f6 !important; }
        [data-theme="white_pink"] .btn-danger { background: #fde2e8 !important; color: #9f1239 !important; border-color: #fecdd3 !important; }
        [data-theme="white_pink"] .btn-danger:hover { background: #fcc2cf !important; }
        [data-theme="white_pink"] .flag-row { border-bottom: 1px solid #e5e7eb !important; }
        [data-theme="white_pink"] .flag-row:hover { background-color: #f9fafb !important; }
        [data-theme="white_pink"] .flag-row.to-remove { background-color: #fecdd3 !important; }
        [data-theme="white_pink"] .table-header { background: #f9fafb !important; border-color: #e5e7eb !important; color: #374151 !important; }
        [data-theme="white_pink"] #toast { background: #f9fafb !important; color: #111827 !important; border: 1px solid #e5e7eb !important; }
        [data-theme="white_pink"] .text-gray-100 { color: #1f2937 !important; }
        [data-theme="white_pink"] .material-symbols-rounded { color: #374151 !important; }
        [data-theme="white_pink"] .btn-primary { color: #ffffff !important; }
        [data-theme="white_pink"] .btn-primary .material-symbols-rounded { color: #ffffff !important; }
        [data-theme="white_pink"] .animated-gradient { background-image: linear-gradient(90deg, #f472b6, #fb7185, #f472b6, #ec4899); color: transparent; }
        [data-theme="white_pink"] .title-bar { background: #f9fafb; border-bottom: 1px solid #e5e7eb; }
        [data-theme="white_pink"] .title-text { color: #111827; }
        [data-theme="dark_pink"] body { background: #0b0a0f; color: #fdf2f8; }
        [data-theme="dark_pink"] .bg-black { background: #0d0b10 !important; }
        [data-theme="dark_pink"] .bg-gray-900 { background: #151017 !important; }
        [data-theme="dark_pink"] .border-gray-800 { border-color: #2a1a2a !important; }
        [data-theme="dark_pink"] .text-gray-400 { color: #f9a8d4 !important; }
        [data-theme="dark_pink"] .modal-content { background: #1a131a !important; }
        [data-theme="dark_pink"] .input-field { background: #1a1a1a !important; border: 1px solid #333333 !important; color: #fdf2f8 !important; }
        [data-theme="dark_pink"] .input-field::placeholder { color: #f5a3c8 !important; }
        [data-theme="dark_pink"] .input-field:focus { box-shadow: 0 0 0 2px rgba(244, 114, 182, 0.25) !important; border-color: #f472b6 !important; }
        [data-theme="dark_pink"] .btn-secondary { background: #2a1a2a !important; color: #fdf2f8 !important; border-color: #333333 !important; }
        [data-theme="dark_pink"] .btn-secondary:hover { background: #3a233a !important; }
        [data-theme="dark_pink"] .btn-danger { background: #3a1a26 !important; color: #fecdd3 !important; border-color: #4a1a2a !important; }
        [data-theme="dark_pink"] .btn-danger:hover { background: #4a2030 !important; }
        [data-theme="dark_pink"] .flag-row { border-bottom: 1px solid #2a1a2a !important; }
        [data-theme="dark_pink"] .flag-row:hover { background-color: #1f141f !important; }
        [data-theme="dark_pink"] .flag-row.to-remove { background-color: #4a2030 !important; }
        [data-theme="dark_pink"] .table-header { background: #151017 !important; border-color: #2a1a2a !important; color: #f9a8d4 !important; }
        [data-theme="dark_pink"] #toast { background: #2a1a2a !important; color: #fdf2f8 !important; border: 1px solid #4a1a2a !important; }
        [data-theme="dark_pink"] .text-white { color: #fdf2f8 !important; }
        [data-theme="dark_pink"] .text-gray-100 { color: #fde2e8 !important; }
        [data-theme="dark_pink"] .material-symbols-rounded { color: #fecdd3 !important; }
        [data-theme="dark_pink"] .animated-gradient { background-image: linear-gradient(90deg, #f472b6, #fb7185, #f472b6, #ec4899); color: transparent; }
        [data-theme="dark_pink"] .title-bar { background: #151017; border-bottom: 1px solid #2a1a2a; }
        [data-theme="dark_pink"] .title-text { color: #fdf2f8; }
        [data-theme="white"] .animated-gradient { background-image: linear-gradient(90deg, #2563eb, #06b6d4, #22d3ee, #2563eb); color: transparent; }
        [data-theme="black"] .animated-gradient { background-image: linear-gradient(90deg, #a855f7, #3b82f6, #22d3ee, #a855f7); color: transparent; }
        [data-theme="dark_purple"] .animated-gradient { background-image: linear-gradient(90deg, #c084fc, #8b5cf6, #6366f1, #c084fc); color: transparent; }
        [data-theme="dark_blue"] .animated-gradient { background-image: linear-gradient(90deg, #60a5fa, #38bdf8, #22d3ee, #60a5fa); color: transparent; }
        [data-theme="white"] .title-bar { background: #f3f4f6; border-bottom: 1px solid #e5e7eb; }
        [data-theme="white"] .title-text { color: #111827; }
        [data-theme="black"] .title-bar { background: #0b0b0b; border-bottom: 1px solid #1f2937; }
        [data-theme="black"] .title-text { color: #e5e7eb; }
        [data-theme="dark_purple"] .title-bar { background: #120d22; border-bottom: 1px solid #2d2249; }
        [data-theme="dark_purple"] .title-text { color: #ddd6fe; }
        [data-theme="dark_blue"] .title-bar { background: #0e1a33; border-bottom: 1px solid #1f2a44; }
        [data-theme="dark_blue"] .title-text { color: #dbeafe; }
        [data-theme="anime_dark"] body {
            background-image: url('https://images3.alphacoders.com/112/thumb-1920-1120789.png');
            color: #000000;
        }
        [data-theme="anime_dark"] aside {
            background: transparent !important;
            border-right: none !important;
        }
        [data-theme="anime_dark"] aside .material-symbols-rounded { color: #ffffff !important; }
        [data-theme="anime_dark"] aside button:hover { background: rgba(255, 255, 255, 0.15) !important; }
        [data-theme="anime_dark"] .bg-black { background: rgba(10, 10, 10, 0.4) !important; backdrop-filter: blur(16px); }
        [data-theme="anime_dark"] .bg-gray-900 { background: rgba(20, 20, 20, 0.5) !important; backdrop-filter: blur(16px); }
        [data-theme="anime_dark"] .modal-content { background: rgba(20, 20, 20, 0.85) !important; backdrop-filter: blur(20px); }
        [data-theme="anime_dark"] .input-field { background: rgba(40, 40, 40, 0.7) !important; color: #ffffff; border-color: rgba(255, 255, 255, 0.2); }
        [data-theme="anime_dark"] .text-gray-200, [data-theme="anime_dark"] .text-gray-100, [data-theme="anime_dark"] .text-gray-400 { color: #ffffff !important; }
        [data-theme="anime_dark"] .material-symbols-rounded { color: #ffffff !important; }
        [data-theme="anime_dark"] .btn-secondary { color: #ffffff; }
        [data-theme="anime_kawaii"] body {
            background-image: url('https://images6.alphacoders.com/135/thumb-1920-1351631.png');
            color: #000000;
        }
        [data-theme="anime_kawaii"] aside {
            background: transparent !important;
            border-right: none !important;
        }
        [data-theme="anime_kawaii"] aside .material-symbols-rounded { color: #000000 !important; }
        [data-theme="anime_kawaii"] aside button:hover { background: rgba(0, 0, 0, 0.1) !important; }
        [data-theme="anime_kawaii"] .bg-black { background: rgba(255, 255, 255, 0.5) !important; backdrop-filter: blur(16px); }
        [data-theme="anime_kawaii"] .bg-gray-900 { background: rgba(250, 250, 250, 0.6) !important; backdrop-filter: blur(16px); }
        [data-theme="anime_kawaii"] .modal-content { background: rgba(255, 255, 255, 0.9) !important; backdrop-filter: blur(20px); }
        [data-theme="anime_kawaii"] .input-field { background: rgba(255, 255, 255, 0.8) !important; color: #000000; border-color: rgba(0, 0, 0, 0.2); }
        [data-theme="anime_kawaii"] .btn-primary { background: #f472b6; }
        [data-theme="anime_kawaii"] .animated-gradient { background-image: linear-gradient(90deg, #f472b6, #fb7185, #ec4899, #f472b6); }
        [data-theme="anime_kawaii"] .text-gray-400 { color: #333333 !important; }
        [data-theme="anime_kawaii"] .material-symbols-rounded { color: #333333 !important; }
        [data-theme="anime_pink"] body {
            background-image: url('https://4kwallpapers.com/images/wallpapers/anime-girl-girly-pink-fantasy-2880x1800-5055.jpg');
            color: #000000;
        }
        [data-theme="anime_pink"] aside {
            background: transparent !important;
            border-right: none !important;
        }
        [data-theme="anime_pink"] aside .material-symbols-rounded { color: #000000 !important; }
        [data-theme="anime_pink"] aside button:hover { background: rgba(0, 0, 0, 0.1) !important; }
        [data-theme="anime_pink"] .bg-black { background: rgba(255, 255, 255, 0.5) !important; backdrop-filter: blur(16px); }
        [data-theme="anime_pink"] .bg-gray-900 { background: rgba(250, 250, 250, 0.6) !important; backdrop-filter: blur(16px); }
        [data-theme="anime_pink"] .modal-content { background: rgba(255, 255, 255, 0.9) !important; backdrop-filter: blur(20px); }
        [data-theme="anime_pink"] .input-field { background: rgba(255, 255, 255, 0.8) !important; color: #000000; border-color: rgba(0, 0, 0, 0.2); }
        [data-theme="anime_pink"] .btn-primary { background: #f472b6; }
        [data-theme="anime_pink"] .animated-gradient { background-image: linear-gradient(90deg, #f472b6, #fb7185, #ec4899, #f472b6); }
        [data-theme="anime_pink"] .text-gray-400 { color: #333333 !important; }
        [data-theme="anime_pink"] .material-symbols-rounded { color: #333333 !important; }
     
        [data-theme="dynamic-naruto-kyuubi"] body {
        background: #000 url('https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExd3E3YzFzd29hdDl0eTU2NWpramU5ZmhxNHZpMmZ2aXRseW4yZW1meCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xLBVbY3quCoWDyhQIX/giphy.gif') center/cover no-repeat fixed;
        }
        [data-theme="dynamic-naruto-kyuubi"] .bg-black { background: rgba(0, 0, 0, 0.55) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-naruto-kyuubi"] .bg-gray-900 { background: rgba(20, 20, 20, 0.65) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-naruto-kyuubi"] .modal-content { background: rgba(15, 15, 25, 0.92) !important; backdrop-filter: blur(20px); }
        [data-theme="dynamic-naruto-kyuubi"] .input-field { background: rgba(30, 30, 30, 0.85) !important; }
        [data-theme="dynamic-naruto-kyuubi"] aside { background: rgba(0, 0, 0, 0.5) !important; backdrop-filter: blur(10px); border-right: none !important; }
        [data-theme="dynamic-naruto-kyuubi"] .title-bar { background: rgba(10, 10, 10, 0.7) !important; backdrop-filter: blur(10px); }
     
        [data-theme="dynamic-samurai"] body {
        background: #000 url('https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExNm1jbjdoN2R2bTg1c2h0cXB5ZjJmZjB0ZzllMXlmYXV4bGd0NDRkMiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/HyOOyynWxMxig/giphy.gif') center/cover no-repeat fixed;
        }
        [data-theme="dynamic-samurai"] .bg-black { background: rgba(0, 0, 0, 0.55) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-samurai"] .bg-gray-900 { background: rgba(20, 20, 20, 0.65) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-samurai"] .modal-content { background: rgba(15, 15, 25, 0.92) !important; backdrop-filter: blur(20px); }
        [data-theme="dynamic-samurai"] .input-field { background: rgba(30, 30, 30, 0.85) !important; }
        [data-theme="dynamic-samurai"] aside { background: rgba(0, 0, 0, 0.5) !important; backdrop-filter: blur(10px); border-right: none !important; }
        [data-theme="dynamic-samurai"] .title-bar { background: rgba(10, 10, 10, 0.7) !important; backdrop-filter: blur(10px); }
        [data-theme="dynamic-nebula"] body {
        background: #000 url('https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExeThlbmxpbXg3ank5bDhycm1xNmpnMWoxYm05dzB6a3RpbnBucTFrbSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3og0IyRiAsl1Pczi6Y/giphy.gif') center/cover no-repeat fixed;
        }
        [data-theme="dynamic-nebula"] .bg-black { background: rgba(0, 0, 0, 0.55) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-nebula"] .bg-gray-900 { background: rgba(20, 20, 20, 0.65) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-nebula"] .modal-content { background: rgba(15, 15, 25, 0.92) !important; backdrop-filter: blur(20px); }
        [data-theme="dynamic-nebula"] .input-field { background: rgba(30, 30, 30, 0.85) !important; }
        [data-theme="dynamic-nebula"] aside { background: rgba(0, 0, 0, 0.5) !important; backdrop-filter: blur(10px); border-right: none !important; }
        [data-theme="dynamic-nebula"] .title-bar { background: rgba(10, 10, 10, 0.7) !important; backdrop-filter: blur(10px); }
        [data-theme="dynamic-aurora"] body {
        background: #000 url('https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3czbnJhYXJmcjhmdGl6c2x5ZDZzMWExZGxkaWlvYjl4Z3Jtb3h4cSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/mviluc9o1wCBy/giphy.gif') center/cover no-repeat fixed;
        }
        [data-theme="dynamic-aurora"] .bg-black { background: rgba(0, 0, 0, 0.55) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-aurora"] .bg-gray-900 { background: rgba(20, 20, 20, 0.65) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-aurora"] .modal-content { background: rgba(15, 15, 25, 0.92) !important; backdrop-filter: blur(20px); }
        [data-theme="dynamic-aurora"] .input-field { background: rgba(30, 30, 30, 0.85) !important; }
        [data-theme="dynamic-aurora"] aside { background: rgba(0, 0, 0, 0.5) !important; backdrop-filter: blur(10px); border-right: none !important; }
        [data-theme="dynamic-aurora"] .title-bar { background: rgba(10, 10, 10, 0.7) !important; backdrop-filter: blur(10px); }
        [data-theme="dynamic-particles"] body {
        background: #000 url('https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExMmc1aWQ0ZWYzNnpkMzNmbXBueDB5eGlkamxibnJ3MzRraWFsN2lzdCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/26n6G8lRMOrYC6rFS/giphy.gif') center/cover no-repeat fixed;
        }
        [data-theme="dynamic-particles"] .bg-black { background: rgba(0, 0, 0, 0.55) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-particles"] .bg-gray-900 { background: rgba(20, 20, 20, 0.65) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-particles"] .modal-content { background: rgba(15, 15, 25, 0.92) !important; backdrop-filter: blur(20px); }
        [data-theme="dynamic-particles"] .input-field { background: rgba(30, 30, 30, 0.85) !important; }
        [data-theme="dynamic-particles"] aside { background: rgba(0, 0, 0, 0.5) !important; backdrop-filter: blur(10px); border-right: none !important; }
        [data-theme="dynamic-particles"] .title-bar { background: rgba(10, 10, 10, 0.7) !important; backdrop-filter: blur(10px); }
        [data-theme="dynamic-matrix"] body {
        background: #000 url('https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExOGh1azd0bmd6dnpndW42enp1Z3R0bGVhbDZmeGU1dzh6OWNlYXcyeiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/wwg1suUiTbCY8H8vIA/giphy.gif') center/cover no-repeat fixed;
        }
        [data-theme="dynamic-matrix"] .bg-black { background: rgba(0, 0, 0, 0.55) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-matrix"] .bg-gray-900 { background: rgba(20, 20, 20, 0.65) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-matrix"] .modal-content { background: rgba(15, 15, 25, 0.92) !important; backdrop-filter: blur(20px); }
        [data-theme="dynamic-matrix"] .input-field { background: rgba(30, 30, 30, 0.85) !important; }
        [data-theme="dynamic-matrix"] aside { background: rgba(0, 0, 0, 0.5) !important; backdrop-filter: blur(10px); border-right: none !important; }
        [data-theme="dynamic-matrix"] .title-bar { background: rgba(10, 10, 10, 0.7) !important; backdrop-filter: blur(10px); }
        [data-theme="dynamic-fireflies"] body {
        background: #000 url('https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnQ0OXZrbDI3ZzNudnVvdXBoaWJnMWpoZGp0dm1nNDBiamQyamc3ZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xUPGcshrKRahaS8ef6/giphy.gif') center/cover no-repeat fixed;
        }
        [data-theme="dynamic-fireflies"] .bg-black { background: rgba(0, 0, 0, 0.55) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-fireflies"] .bg-gray-900 { background: rgba(20, 20, 20, 0.65) !important; backdrop-filter: blur(12px); }
        [data-theme="dynamic-fireflies"] .modal-content { background: rgba(15, 15, 25, 0.92) !important; backdrop-filter: blur(20px); }
        [data-theme="dynamic-fireflies"] .input-field { background: rgba(30, 30, 30, 0.85) !important; }
        [data-theme="dynamic-fireflies"] aside { background: rgba(0, 0, 0, 0.5) !important; backdrop-filter: blur(10px); border-right: none !important; }
        [data-theme="dynamic-fireflies"] .title-bar { background: rgba(10, 10, 10, 0.7) !important; backdrop-filter: blur(10px); }
        /* Bottom dock styling */
        .bottom-dock {
            position: fixed;
            bottom: 12px;
            left: 0;
            right: 0;
            display: flex;
            justify-content: center;
            pointer-events: auto;
            z-index: 1000;
        }
        .bottom-dock .dock-container {
            background: rgba(15, 15, 15, 0.85);
            border: 1px solid #222222;
            backdrop-filter: blur(12px);
            border-radius: 14px;
            padding: 6px 10px;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 6px 24px rgba(0,0,0,0.45);
            position: relative;
        }
        .dock-btn {
            height: 36px;
            min-width: 36px;
            padding: 0 10px;
            border-radius: 10px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #cbd5e1;
            transition: background 0.15s ease, color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
            position: relative;
            z-index: 1;
        }
        .dock-btn:hover { background: rgba(255,255,255,0.08); color: #ffffff; transform: translateY(-1px) scale(1.03); box-shadow: 0 4px 12px rgba(0,0,0,0.25); }
        .dock-btn .material-symbols-rounded { font-size: 20px; }
        .dock-btn .dock-label { margin-left: 8px; font-size: 13px; max-width: 0; opacity: 0; overflow: hidden; white-space: nowrap; transition: max-width 0.2s ease, opacity 0.2s ease, margin-left 0.2s ease; }
        .dock-btn-active {
            color: #ffffff;
        }
        .dock-btn-active .dock-label { max-width: 80px; opacity: 1; margin-left: 8px; font-weight: 600; }
        .dock-indicator {
            position: absolute;
            top: 6px;
            left: 0px;
            height: 36px;
            border-radius: 10px;
            background: #2563eb;
            z-index: 0;
            width: 46px;
            transition: transform 0.2s ease, width 0.2s ease, opacity 0.2s ease;
            will-change: transform, width;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .view-enter {
            animation: fadeIn 0.3s ease-out forwards;
        }
    </style>
</head>
<body>
    <script>
        window.updateRobloxStatus = function(state) {
            const robloxStatus = document.getElementById('roblox-status');
            if (!robloxStatus) return;
            robloxStatus.className = 'w-8 h-8 rounded-full transition-all duration-500';
            robloxStatus.classList.remove('bg-red-500', 'bg-yellow-500', 'bg-green-500', 'glow-red', 'glow-yellow', 'glow-green');
            if (state === 'not_running') {
                robloxStatus.classList.add('bg-red-500', 'glow-red');
                robloxStatus.title = 'Roblox not running';
            } else if (state === 'running') {
                robloxStatus.classList.add('bg-yellow-500', 'glow-yellow');
                robloxStatus.title = 'Roblox running, attaching...';
            } else if (state === 'attached') {
                robloxStatus.classList.add('bg-green-500', 'glow-green');
                robloxStatus.title = 'Roblox attached';
            }
        };
        window.populatePresetFlags = function(presets) {
            window.allPresetFlags = presets || [];
            const presetListDiv = document.getElementById('preset-list');
            const presetSearch = document.getElementById('preset-search');
            if (presetListDiv && presetSearch) {
                const searchTerm = (presetSearch.value || '').toLowerCase();
                presetListDiv.innerHTML = '';
                const filtered = window.allPresetFlags
                    .filter(flag => flag.toLowerCase().includes(searchTerm))
                    .slice(0, 100);
                if (filtered.length === 0) {
                    presetListDiv.innerHTML = '<div class="p-4 text-center text-gray-500 text-sm">No presets found</div>';
                    return;
                }
                filtered.forEach(flagName => {
                    const isPresent = (window.userFlags || []).some(f => f.name === flagName);
                    const item = document.createElement('button');
                    item.className = `w-full text-left p-3 text-sm rounded-md transition-colors ${
                        isPresent ? 'bg-gray-800 text-gray-500 cursor-not-allowed' : 'hover:bg-gray-800 text-gray-200'
                    }`;
                    item.textContent = flagName;
                    item.disabled = isPresent;
                    item.onclick = () => {
                        if (window.addFlagFromPreset) window.addFlagFromPreset(flagName);
                    };
                    presetListDiv.appendChild(item);
                });
            }
        };
        window.updateInjectionProgress = function(progress, total) {
            console.log("Injection Progress:", progress, total);
        };

        // Terminal functions
        document.addEventListener('DOMContentLoaded', () => {
                const output = document.getElementById('terminal-output');
                if (!output) return;

                output.innerHTML = '';

                function logToTerminal(message, type = 'info') {
                        const time = new Date().toLocaleTimeString('en-US', {
                                hour12: false,
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit'
                        });
                        let colorClass = '';
                        switch (type) {
                                case 'error': colorClass = 'text-red-400'; break;
                                case 'warning': colorClass = 'text-yellow-400'; break;
                                case 'success': colorClass = 'text-green-400'; break;
                                default: colorClass = 'text-gray-300';
                        }
                        const line = document.createElement('div');
                        line.className = `mb-1 ${colorClass}`;
                        line.textContent = `[${time}] ${message}`;
                        output.appendChild(line);
                        output.scrollTop = output.scrollHeight;
                }

                function clearTerminal() {
                        output.innerHTML = '<div class="text-gray-500">--- Log cleared ---</div>';
                        logToTerminal('Terminal cleared', 'success');
                        showToast('Terminal log cleared', false);
                }

                function copyTerminal() {
                        const text = output.innerText.trim();

                        if (!text || text === '--- Log cleared ---') {
                                showToast('Nothing to copy', true);
                                return;
                        }

                        if (navigator.clipboard && navigator.clipboard.writeText) {
                                navigator.clipboard.writeText(text)
                                        .then(() => showToast('Terminal log copied to clipboard!', false))
                                        .catch(() => fallbackCopy(text));
                        } else {
                                fallbackCopy(text);
                        }
                }

                function fallbackCopy(text) {
                        const textarea = document.createElement('textarea');
                        textarea.value = text;
                        textarea.style.position = 'fixed';
                        textarea.style.opacity = '0';
                        textarea.style.left = '-9999px';
                        textarea.style.top = '-9999px';
                        document.body.appendChild(textarea);

                        textarea.select();
                        textarea.setSelectionRange(0, 99999);

                        try {
                                const successful = document.execCommand('copy');
                                if (successful) {
                                        showToast('Terminal log copied to clipboard!', false);
                                } else {
                                        throw new Error();
                                }
                        } catch (err) {
                                prompt('Copy the log below (Ctrl+C / Cmd+C):', text);
                                showToast('Manual copy: select text in prompt', true);
                        } finally {
                                document.body.removeChild(textarea);
                        }
                }

                document.getElementById('clear-terminal-btn')?.addEventListener('click', clearTerminal);
                document.getElementById('copy-terminal-btn')?.addEventListener('click', copyTerminal);

                logToTerminal('Terminal ready – backend logs incoming', 'success');

                window.logToTerminal = logToTerminal;
        });

        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(() => {
                logToTerminal('Terminal ready – backend logs incoming', 'success');
                const waitingMsg = Array.from(terminalOutput.children).find(el => el.textContent.includes('Waiting for events'));
                if (waitingMsg) waitingMsg.remove();
            }, 200);
        });


        logToTerminal('Terminal initialized - watching for events...', 'info');
    </script>
    <div class="title-bar pywebview-drag-region h-8 flex justify-between items-center px-3 flex-shrink-0">
        <div class="title-text text-sm font-semibold">VELORIN-V3</div>
        <div class="flex items-center gap-2" style="-webkit-app-region: no-drag;">
            <button onclick="pywebview.api.minimize_window()" class="title-bar-btn w-8 h-8 flex items-center justify-center rounded hover:bg-gray-700">
                <span class="material-symbols-rounded !text-sm">remove</span>
            </button>
            <button onclick="pywebview.api.close_window()" class="title-bar-btn close w-8 h-8 flex items-center justify-center rounded">
                <span class="material-symbols-rounded !text-sm">close</span>
            </button>
        </div>
    </div>
    <!-- Main Content -->
    <div class="flex-1 flex flex-col overflow-hidden">
        <main class="flex-1 flex flex-col overflow-hidden pb-16">
            <section id="flags-view" class="flex-1 flex flex-col overflow-hidden">
                <!-- Header -->
                <div class="px-6 py-4 flex-shrink-0 border-b border-gray-800">
                    <div class="flex justify-between items-center">
                        <h1 class="text-3xl font-bold animated-gradient">FFlags Editor</h1>
                        <div class="flex items-center space-x-2">
                            <button id="add-new-btn" class="btn btn-secondary px-3 py-1.5 rounded-md text-sm flex items-center space-x-1">
                                <span class="material-symbols-rounded">add</span>
                                <span>Add</span>
                            </button>
                            <button id="delete-selected-btn" class="btn btn-danger px-3 py-1.5 rounded-md text-sm flex items-center space-x-1">
                                <span class="material-symbols-rounded">delete</span>
                                <span>Remove</span>
                            </button>
                            <button id="remove-all-btn" class="btn btn-danger px-3 py-1.5 rounded-md text-sm flex items-center space-x-1">
                                <span class="material-symbols-rounded">clear_all</span>
                                <span>Remove All</span>
                            </button>
                            <button id="show-preset-btn" class="btn btn-secondary px-3 py-1.5 rounded-md text-sm flex items-center space-x-1">
                                <span class="material-symbols-rounded">list</span>
                                <span>Presets</span>
                            </button>
                            <button id="import-btn" class="btn btn-secondary px-3 py-1.5 rounded-md text-sm flex items-center space-x-1">
                                <span class="material-symbols-rounded">upload</span>
                                <span>Import</span>
                            </button>
                            <button id="export-btn" class="btn btn-secondary px-3 py-1.5 rounded-md text-sm flex items-center space-x-1">
                                <span class="material-symbols-rounded">download</span>
                                <span>Export</span>
                            </button>
                        </div>
                    </div>
                </div>
                <!-- Search -->
                <div class="px-6 py-3 flex-shrink-0">
                    <div class="relative">
                        <span class="material-symbols-rounded absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">search</span>
                        <input id="search-bar" type="text" placeholder="Search flags..." class="input-field w-full pl-9 pr-3 py-2 rounded-md text-sm outline-none">
                    </div>
                </div>
                <!-- Flag List -->
                <div class="flex-1 min-h-0 px-6 pb-3">
                    <div class="h-full bg-black rounded-lg border border-gray-800 overflow-hidden flex flex-col">
                        <div class="table-header flex text-xs text-gray-400 bg-gray-900 border-b border-gray-800 px-4 py-2 sticky top-0 z-10">
                            <div class="w-12 text-center"></div>
                            <div class="flex-1 pl-2">NAME</div>
                            <div class="w-24 pl-2">TYPE</div>
                            <div class="w-32 pl-2">VALUE</div>
                        </div>
                        <div id="flag-list" class="flex-1 overflow-y-auto">
                        </div>
                    </div>
                </div>
                <!-- Actions -->
                    <div class="px-6 py-4 flex-shrink-0 border-t border-gray-800">
                    <div class="flex justify-between items-center">
                        <div class="flex items-center space-x-3">
                            <div id="roblox-status" class="w-8 h-8 rounded-full bg-red-500 glow-red"></div>
                            <button id="kill-roblox-btn" class="btn btn-danger px-3 py-1.5 rounded-md text-sm flex items-center space-x-1">
                                <span class="material-symbols-rounded">Terminal</span>
                                <span>Kill Roblox</span>
                            </button>
                        </div>
                        <div class="flex items-center space-x-3">
                            <button id="apply-btn" class="btn bg-gradient-to-r from-purple-600 to-blue-600 px-5 py-2 rounded-md text-sm text-lg font-semibold shadow-lg hover:shadow-2xl transform hover:-translate-y-1 transition-all">
                                Apply to Roblox
                            </button>
                            <button id="save-btn" class="btn btn-primary px-5 py-2 rounded-md text-sm">
                                Save Flags
                            </button>
                        </div>
                    </div>
                </div>
            </section>
            <section id="settings-view" class="flex-1 flex flex-col overflow-hidden hidden">
                    <div class="px-6 py-4 flex-shrink-0 border-b border-gray-800">
                            <h1 class="text-3xl font-bold animated-gradient">Settings</h1>
                    </div>
                    <div class="px-6 py-4 flex-1 overflow-y-auto space-y-6">
                            <!-- Main Settings Card -->
                            <div class="bg-black rounded-lg border border-gray-800 p-5 space-y-6">
                                    <label class="flex items-center justify-between cursor-pointer">
                                            <span class="text-sm text-gray-300">Auto apply flags when injected</span>
                                            <input id="auto-apply-toggle" type="checkbox" class="h-5 w-5 text-purple-500 focus:ring-purple-500">
                                    </label>
                                    <label class="flex items-center justify-between cursor-pointer">
                                            <span class="text-sm text-gray-300">Discord Rich Presence</span>
                                            <input id="discord-rpc-toggle" type="checkbox" class="h-5 w-5 text-purple-500 focus:ring-purple-500">
                                    </label>
                                    <div class="flex items-center justify-between">
                                            <span class="text-sm text-gray-300">Theme</span>
                                            <select id="theme-select" class="input-field px-3 py-2 rounded-md text-sm bg-gray-900 border border-gray-700 focus:border-purple-500 focus:outline-none">
                                                    <option value="black">Default</option>
                                                    <option value="white">White</option>
                                                    <option value="white_pink">White Pink</option>
                                                    <option value="dark_pink">Dark Pink</option>
                                                    <option value="dark_purple">Dark Purple</option>
                                                    <option value="dark_blue">Dark Blue</option>
                                                    <option value="anime_dark">Anime#1</option>
                                                    <option value="anime_kawaii">Anime#2</option>
                                                    <option value="anime_pink">Anime#3</option>
                                                    <option value="dynamic-nebula">Nebula</option>
                                                    <option value="dynamic-aurora">Aurora</option>
                                                    <option value="dynamic-particles">Particles</option>
                                                    <option value="dynamic-matrix">Matrix Cat</option>
                                                    <option value="dynamic-fireflies">Fireflies Night</option>
                                                    <option value="dynamic-naruto-kyuubi">Naruto Kyuubi</option>
                                                    <option value="dynamic-samurai">Samurai</option>
                                            </select>
                                    </div>
                                    <div class="flex items-center justify-between">
                                            <span class="text-sm text-gray-300">Hide/Show UI Keybind</span>
                                            <button id="hide-key-capture-btn"
                                                    class="px-5 py-2 rounded-md text-sm font-mono bg-gray-900 border border-gray-700 hover:border-purple-500 focus:border-purple-500 transition shadow-md min-w-[120px] text-center">
                                                    <span id="hide-key-display">INSERT</span>
                                            </button>
                                    </div>
                                    <input type="hidden" id="hide-key-input">
                            </div>
                            <div class="bg-black rounded-lg border border-gray-800 p-5">
                                    <h3 class="text-lg font-semibold text-blue-500 mb-5 animated-gradient">Protection</h3>
                                    <div class="space-y-4">
                                            <label class="flex items-center justify-between cursor-pointer">
                                                    <span class="text-sm text-gray-300">Safe Mode <span class="text-gray-400 text-xs">(NtWrite + XOR Encryption)</span></span>
                                                    <input id="safe-mode-toggle" type="checkbox" class="h-5 w-5 text-purple-500 focus:ring-purple-500">
                                            </label>
                                            <label class="flex items-center justify-between cursor-pointer">
                                                    <span class="text-sm text-gray-300">Random Re-apply <span class="text-gray-400 text-xs">(Prevent Crash)</span></span>
                                                    <input id="randomization-toggle" type="checkbox" class="h-5 w-5 text-purple-500 focus:ring-purple-500">
                                            </label>
                                            <label class="flex items-center justify-between cursor-pointer">
                                                    <span class="text-sm text-gray-300">Anti Byfron Detection</span>
                                                    <input id="timing-attack-toggle" type="checkbox" class="h-5 w-5 text-purple-500 focus:ring-purple-500">
                                            </label>
                                            <label class="flex items-center justify-between cursor-pointer">
                                                    <span class="text-sm text-gray-300">Re-apply</span>
                                                    <input id="reapply-toggle" type="checkbox" class="h-5 w-5 text-purple-500 focus:ring-purple-500">
                                            </label>
                                            <label class="flex items-center justify-between cursor-pointer">
                                                    <span class="text-sm text-gray-300">
                                                            Offsetless Injection 
                                                            <span class="text-gray-400 text-xs">(No offsets needed – more stable) </span>
                                                    </span>
                                                    <input id="offsetless-toggle" type="checkbox" class="h-5 w-5 text-purple-500 focus:ring-purple-500">
                                            </label>
                                    </div>
                            </div>
                    </div>

                    <div class="flex justify-end p-4 border-t border-gray-800">
                            <button id="save-settings-btn" class="btn btn-primary px-6 py-2 rounded-md text-sm font-medium">
                                    Save Settings
                            </button>
                    </div>
            </section>
            <section id="presets-view" class="flex-1 flex flex-col overflow-hidden hidden">
                <div class="px-6 py-4 flex-shrink-0 border-b border-gray-800">
                    <h1 class="text-3xl font-bold animated-gradient">Presets</h1>
                </div>
                <div class="px-6 py-4 flex-1 overflow-y-auto space-y-6">
                    <div class="bg-black rounded-lg border border-gray-800 p-5 space-y-4">
                        <div class="flex items-center justify-between">
                            <div>
                                <div class="text-sm text-gray-200">Use old death sound</div>
                                <div class="text-xs text-gray-500">Bring back the classic 'oof' death sound.</div>
                            </div>
                            <input id="preset-old-death" type="checkbox" class="h-4 w-4">
                        </div>
                        <div class="flex items-center justify-between">
                            <div>
                                <div class="text-sm text-gray-200">Mouse cursor</div>
                                <div class="text-xs text-gray-500">Choose between classic Roblox cursor styles.</div>
                            </div>
                            <select id="preset-mouse-cursor" class="input-field px-2 py-1 rounded text-sm w-44">
                                <option value="default">Default</option>
                                <option value="classic">Classic Style</option>
                                <option value="blackdot">Black Dot</option>
                                <option value="whitedot">White Dot</option>
                                <option value="diamondsword">Sword</option>
                                <option value="pink">Pink Cross</option>
                                <option value="girl">Girl</option>
                            </select>
                        </div>
                        <div class="flex items-center justify-between">
                            <div>
                                <div class="text-sm text-gray-200">Use old avatar editor background</div>
                                <div class="text-xs text-gray-500">Bring back the old avatar editor background used prior to 2020.</div>
                            </div>
                            <input id="preset-old-avatar-bg" type="checkbox" class="h-4 w-4">
                        </div>
                        <div class="flex items-center justify-between">
                            <div>
                                <div class="text-sm text-gray-200">Emulate old character sounds</div>
                                <div class="text-xs text-gray-500">Roughly bring back character sounds used prior to 2014.</div>
                            </div>
                            <input id="preset-old-char-sounds" type="checkbox" class="h-4 w-4">
                        </div>
                        <div class="flex items-center justify-between">
                            <div>
                                <div class="text-sm text-gray-200">Preferred emoji type</div>
                                <div class="text-xs text-gray-500">Choose which type of emoji Roblox should use.</div>
                            </div>
                            <select id="preset-emoji-type" class="input-field px-2 py-1 rounded text-sm w-52">
                                <option value="default">Default (Twitter)</option>
                                <option value="apple">Apple 🍎</option>
                                <option value="windows">Windows 🪟</option>
                                <option value="noto">Google Noto 🌈</option>
                                <option value="custom">Custom Font...</option>
                            </select>
                        </div>
                    </div>
                    <div class="bg-black rounded-lg border border-gray-800 p-5 space-y-4">
                        <div class="text-lg font-semibold text-gray-200">Miscellaneous</div>
                        <div class="flex items-center justify-between">
                            <div>
                                <div class="text-sm text-gray-200">Use custom font</div>
                                <div class="text-xs text-gray-500">Font size can be adjusted in the Engine Settings tab.</div>
                            </div>
                            <div class="flex items-center space-x-2">
                                <input id="preset-use-custom-font" type="checkbox" class="h-4 w-4">
                                <button id="preset-choose-font" class="btn btn-secondary px-3 py-1.5 rounded-md text-sm">Choose font...</button>
                            </div>
                        </div>
                        <div id="preset-font-name" class="text-xs text-gray-500"></div>
                    </div>
                    <div class="bg-black rounded-lg border border-gray-800 p-5 space-y-4">
                        <div class="text-lg font-semibold text-gray-200">Injection Control</div>
                        <div class="flex items-center justify-between">
                            <div>
                                <div class="text-sm text-gray-200">Uninject / Restore default FFlags</div>
                                <div class="text-xs text-gray-500">Restores all modified FFlags to their original default values (requires Roblox attached).</div>
                            </div>
                            <button id="uninject-btn" class="btn btn-danger px-4 py-2 rounded-md text-sm flex items-center space-x-1">
                                <span class="material-symbols-rounded">restore</span>
                                <span>Uninject</span>
                            </button>
                        </div>
                    </div>
                </div>
                <div class="flex justify-end p-4 border-t border-gray-800">
                    <button id="save-presets-btn" class="btn btn-primary px-4 py-1.5 rounded-md text-sm">Save</button>
                </div>
            </section>
            <section id="packs-view" class="flex-1 flex flex-col overflow-hidden hidden">
                <div class="px-6 py-4 flex-shrink-0 border-b border-gray-800">
                    <h1 class="text-3xl font-bold animated-gradient">Preset Packs</h1>
                    <p class="text-sm text-gray-400 mt-2">One-click optimized configurations used by the community</p>
                </div>
                <div class="px-6 py-4 flex-1 overflow-y-auto">
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                        <div class="bg-black rounded-lg border border-gray-800 p-6 hover:border-gray-500 transition-all cursor-pointer" onclick="loadPresetPack('ultra_fps')">
                            <div class="text-2xl font-bold text-white mb-2">FPS Boost</div>
                            <p class="text-sm text-gray-400">Unlock higher FPS, reduce lag, perfect for competitive play</p>
                            <div class="mt-4 text-xs text-gray-500">~118 flags • Performance focused</div>
                        </div>
                        <div class="bg-black rounded-lg border border-gray-800 p-6 hover:border-gray-500 transition-all cursor-pointer" onclick="loadPresetPack('potato')">
                            <div class="text-2xl font-bold text-white mb-2">Potato Mode</div>
                            <p class="text-sm text-gray-400">Extreme low graphics for very old/low-end PCs</p>
                            <div class="mt-4 text-xs text-gray-500">~46 flags • Maximum performance</div>
                        </div>
                        <div class="bg-black rounded-lg border border-gray-800 p-6 hover:border-gray-500 transition-all cursor-pointer" onclick="loadPresetPack('max_graphics')">
                            <div class="text-2xl font-bold text-white mb-2">Maximum Graphics</div>
                            <p class="text-sm text-gray-400">Best lighting, shadows, reflections — for high-end PCs</p>
                            <div class="mt-4 text-xs text-gray-500">~43 flags • High quality</div>
                        </div>
                        <div class="bg-black rounded-lg border border-gray-800 p-6 hover:border-gray-500 transition-all cursor-pointer" onclick="loadPresetPack('low_latency')">
                            <div class="text-2xl font-bold text-white mb-2">Zero Lag</div>
                            <p class="text-sm text-gray-400">Optimized network settings for lowest ping possible</p>
                            <div class="mt-4 text-xs text-gray-500">~79 flags • Network optimization</div>
                        </div>
                        <div class="bg-black rounded-lg border border-gray-800 p-6 hover:border-gray-500 transition-all cursor-pointer" onclick="loadPresetPack('bladeball')">
                            <div class="text-2xl font-bold text-white mb-2">BladeBall LagBall</div>
                            <p class="text-sm text-gray-400">Lagball, Black texture and good for clash</p>
                            <div class="mt-4 text-xs text-gray-500">~67 flags • Bladeball</div>
                        </div>
                        <div class="bg-black rounded-lg border border-gray-800 p-6 hover:border-gray-500 transition-all cursor-pointer" onclick="loadPresetPack('notexture')">
                            <div class="text-2xl font-bold text-white mb-2">No-Texture</div>
                            <p class="text-sm text-gray-400">Working no-texture fflag + FPS boost</p>
                            <div class="mt-4 text-xs text-gray-500">~23 flags • No Texture</div>
                        </div>
                    </div>
                </div>
            </section>

            <section id="terminal-view" class="flex-1 flex flex-col overflow-hidden hidden">
                <div class="px-6 py-4 flex-shrink-0 border-b border-gray-800">
                    <h1 class="text-3xl font-bold animated-gradient">Terminal</h1>
                    <p class="text-sm text-gray-400 mt-1">Velorin log system</p>
                </div>
                <div class="flex-1 px-6 py-4 overflow-hidden">
                    <div id="terminal-output" class="bg-black/70 backdrop-blur rounded-lg border border-gray-800 p-5 h-full overflow-y-auto font-mono text-sm whitespace-pre-wrap">
                        <div class="text-gray-500">--- Waiting for events ---</div>
                    </div>
                </div>
                <div class="px-6 py-3 flex-shrink-0 border-t border-gray-800 flex items-center justify-between">
                    <button id="clear-terminal-btn" class="btn btn-secondary px-4 py-1.5 rounded-md text-sm flex items-center gap-2">
                        <span class="material-symbols-rounded text-sm">clear_all</span>
                        Clear Log
                    </button>
                    <button id="copy-terminal-btn" class="btn btn-secondary px-4 py-1.5 rounded-md text-sm flex items-center gap-2">
                        <span class="material-symbols-rounded text-sm">content_copy</span>
                        Copy All
                    </button>
                </div>
            </section>
        </main>
        <div class="bottom-dock">
            <div id="dock-container" class="dock-container">
                <div id="dock-indicator" class="dock-indicator"></div>
                <button id="tab-flags" class="dock-btn dock-btn-active" title="Flags">
                    <span class="material-symbols-rounded">flag</span>
                    <span class="dock-label">Flags</span>
                </button>
                <button id="tab-packs" class="dock-btn" title="Packs">
                    <span class="material-symbols-rounded">package_2</span>
                    <span class="dock-label">Packs</span>
                </button>
                <button id="tab-presets" class="dock-btn" title="Presets">
                    <span class="material-symbols-rounded">tune</span>
                    <span class="dock-label">Presets</span>
                </button>
                <button id="tab-terminal" class="dock-btn" title="Terminal">
                    <span class="material-symbols-rounded">terminal</span>
                    <span class="dock-label">Terminal</span>
                </button>
                <button id="tab-settings" class="dock-btn" title="Settings">
                    <span class="material-symbols-rounded">settings</span>
                    <span class="dock-label">Settings</span>
                </button>
                <button id="discordTabBtn" class="dock-btn" title="Join Discord">
                    <svg width="20" height="20" viewBox="0 0 127.14 96.36" xmlns="http://www.w3.org/2000/svg">
                        <path fill="currentColor" d="M107.7 8.07A105.15 105.15 0 0 0 81.47 0l-3.42 6.24a97.5 97.5 0 0 0-29.1 0L45.53 0a105.15 105.15 0 0 0-26.23 8.07C1.5 26.25-2.7 46.29 1.37 65.94c4.9 19.6 20.8 35.1 39.96 40.58a107.5 107.5 0 0 0 9.24-5.38 70.5 70.5 0 0 0 28.44-1.74l.9 1.62c20.5 3.66 41.2-7.48 48.12-23.58 7.74-18.12 4.36-38.92-9.93-61.44zM53.7 69.3c-8.4 0-15.3-7.74-15.3-17.28 0-9.54 6.9-17.28 15.3-17.28 8.46 0 15.36 7.74 15.3 17.28 0 9.54-6.84 17.28-15.3 17.28zm40.32 0c-8.4 0-15.3-7.74-15.3-17.28 0-9.54 6.9-17.28 15.3-17.28 8.46 0 15.36 7.74 15.3 17.28 0 9.54-6.84 17.28-15.3 17.28z"/>
                    </svg>
                </button>
            </div>
        </div>
    </div>
    <div id="import-json-modal" class="modal-backdrop fixed inset-0 bg-black/60 flex items-center justify-center z-50 opacity-0 invisible">
        <div class="modal-content bg-[#111111] rounded-lg shadow-2xl w-full max-w-xl h-[55vh] flex flex-col scale-95 border border-[#222222]">
            <!-- Header with grey background -->
            <div class="flex items-center justify-between px-5 py-3 bg-[#1e1e1e] border-b border-[#222222]">
                <div class="flex-1"></div>
                <h3 class="text-lg font-semibold text-gray-200 text-center flex-1">Import JSON</h3>
                <div class="flex-1 flex justify-end">
                    <button id="close-import-json-modal" class="text-gray-400 hover:text-gray-200">
                        <span class="material-symbols-rounded">close</span>
                    </button>
                </div>
            </div>
            <div class="flex-1 p-4 flex flex-col">
                <div class="h-full">
                    <textarea id="json-input-area" class="w-full h-full bg-[#1e1e1e] border border-[#333333] rounded-lg p-4 text-gray-200 font-mono text-sm resize-none focus:border-blue-500 focus:outline-none" placeholder='{
  "FFlagDebugDisplayFPS": "True",
}'></textarea>
                </div>
            </div>
            <div class="flex justify-end items-center px-5 py-4 border-t border-[#222222] gap-3">
                <button id="import-from-file-btn" class="flex items-center justify-center gap-2 px-5 py-2 bg-[#1e1e1e] hover:bg-[#252525] text-white text-sm font-medium rounded-md transition-all border border-[#333333]">
                    <span class="material-symbols-rounded text-base">folder_open</span>
                    Import from file
                </button>
                <button id="clear-import-json" class="btn btn-secondary px-5 py-2 rounded-md text-sm">Clear</button>
                <button id="ok-import-json" class="btn btn-primary px-5 py-2 rounded-md text-sm">OK</button>
            </div>
        </div>
    </div>

    <!-- Preset Modal -->
    <div id="preset-modal" class="modal-backdrop fixed inset-0 bg-black/60 flex items-center justify-center z-50 opacity-0 invisible">
        <div id="modal-content-preset" class="modal-content bg-gray-900 rounded-lg shadow-lg w-full max-w-2xl h-[80vh] flex flex-col scale-95">
            <div class="flex justify-between items-center px-5 py-4 border-b border-gray-800">
                <h3 class="font-medium text-gray-100">Add Flag from Presets</h3>
                <button id="close-modal-btn-preset" class="material-symbols-rounded text-gray-400 hover:text-gray-200">close</button>
            </div>
            <div class="p-4">
                <input id="preset-search" type="text" placeholder="Search presets..." class="input-field w-full px-3 py-2 rounded-md text-sm outline-none">
            </div>
            <div id="preset-list" class="flex-1 overflow-y-auto px-4 pb-4">
            </div>
        </div>
    </div>
    <!-- Edit Modal -->
    <div id="edit-modal" class="modal-backdrop fixed inset-0 bg-black/60 flex items-center justify-center z-50 opacity-0 invisible">
        <div id="modal-content-edit" class="modal-content bg-gray-900 rounded-lg shadow-lg w-full max-w-md scale-95">
            <div class="flex justify-between items-center px-5 py-4 border-b border-gray-800">
                <h3 class="font-medium text-gray-100" id="edit-modal-title">Edit Value</h3>
                <button id="close-modal-btn-edit" class="material-symbols-rounded text-gray-400 hover:text-gray-200">close</button>
            </div>
            <div class="p-5">
                <div class="mb-3">
                    <label class="text-xs text-gray-400 mb-1 block">Value</label>
                    <input id="edit-value-input" type="text" class="input-field w-full px-3 py-2 rounded-md text-sm outline-none">
                </div>
                <p class="text-xs text-gray-500">Data type will be automatically inferred</p>
            </div>
            <div class="flex justify-end p-4 border-t border-gray-800">
                <button id="save-edit-btn" class="btn btn-primary px-4 py-1.5 rounded-md text-sm">
                    Apply
                </button>
            </div>
        </div>
    </div>
    <!-- Confirm Modal -->
    <div id="confirm-modal" class="modal-backdrop fixed inset-0 bg-black/60 flex items-center justify-center z-50 opacity-0 invisible">
        <div id="modal-content-confirm" class="modal-content bg-gray-900 rounded-lg shadow-lg w-full max-w-md scale-95">
            <div class="flex justify-between items-center px-5 py-4 border-b border-gray-800">
                <h3 class="font-medium text-gray-100" id="confirm-title">Confirm</h3>
                <button id="close-confirm-btn" class="material-symbols-rounded text-gray-400 hover:text-gray-200">close</button>
            </div>
            <div class="p-5">
                <p id="confirm-message" class="text-sm text-gray-300"></p>
            </div>
            <div class="flex justify-end space-x-2 p-4 border-t border-gray-800">
                <button id="confirm-yes" class="btn btn-primary px-4 py-1.5 rounded-md text-sm">Yes</button>
                <button id="confirm-no" class="btn btn-secondary px-4 py-1.5 rounded-md text-sm">Cancel</button>
            </div>
        </div>
    </div>
    <!-- Toast -->
    <div id="toast" class="fixed bottom-6 right-6 px-4 py-2 opacity-0 translate-y-2 z-50 rounded-md text-sm font-medium shadow-sm"></div>
    <script>
        let userFlags = [];
        let allPresetFlags = [];
        window.userFlags = userFlags;
        let editingFlagName = null;
        const flagsToRemove = new Set();
        function cleanFlagName(name) {
            const prefixes = ["DFInt", "DFString", "DFFlag", "FInt", "FString", "FFlag"];
            for (const prefix of prefixes) {
                if (name.startsWith(prefix)) {
                    return name.substring(prefix.length);
                }
            }
            return name;
        }
        // DOM Elements
        const flagList = document.getElementById('flag-list');
        const searchBar = document.getElementById('search-bar');
        const addNewBtn = document.getElementById('add-new-btn');
        const deleteSelectedBtn = document.getElementById('delete-selected-btn');
        const removeAllBtn = document.getElementById('remove-all-btn');
        const saveBtn = document.getElementById('save-btn');
        const killRobloxBtn = document.getElementById('kill-roblox-btn');
        const applyBtn = document.getElementById('apply-btn');
        const toast = document.getElementById('toast');
        const importBtn = document.getElementById('import-btn');
        const exportBtn = document.getElementById('export-btn');
        const presetModal = document.getElementById('preset-modal');
        const showPresetBtn = document.getElementById('show-preset-btn');
        const closeModalBtnPreset = document.getElementById('close-modal-btn-preset');
        const presetListDiv = document.getElementById('preset-list');
        const presetSearch = document.getElementById('preset-search');
        const flagsView = document.getElementById('flags-view');
        const settingsView = document.getElementById('settings-view');
        const presetsView = document.getElementById('presets-view');
        const packsView = document.getElementById('packs-view');
        const terminalView = document.getElementById('terminal-view');
        const flagsTabBtn = document.getElementById('tab-flags');
        const settingsTabBtn = document.getElementById('tab-settings');
        const presetsTabBtn = document.getElementById('tab-presets');
        const packsTabBtn = document.getElementById('tab-packs');
        const terminalTabBtn = document.getElementById('tab-terminal');
        const autoApplyToggle = document.getElementById('auto-apply-toggle');
        const discordRpcToggle = document.getElementById('discord-rpc-toggle');
        const saveSettingsBtn = document.getElementById('save-settings-btn');
        const themeSelect = document.getElementById('theme-select');
        const presetOldDeath = document.getElementById('preset-old-death');
        const presetMouseCursor = document.getElementById('preset-mouse-cursor');
        const presetOldAvatarBg = document.getElementById('preset-old-avatar-bg');
        const presetOldCharSounds = document.getElementById('preset-old-char-sounds');
        const presetEmojiType = document.getElementById('preset-emoji-type');
        const presetUseCustomFont = document.getElementById('preset-use-custom-font');
        const presetChooseFont = document.getElementById('preset-choose-font');
        const presetFontName = document.getElementById('preset-font-name');
        const savePresetsBtn = document.getElementById('save-presets-btn');
        const editModal = document.getElementById('edit-modal');
        const closeModalBtnEdit = document.getElementById('close-modal-btn-edit');
        const editModalTitle = document.getElementById('edit-modal-title');
        const editValueInput = document.getElementById('edit-value-input');
        const saveEditBtn = document.getElementById('save-edit-btn');
        const uninjectBtn = document.getElementById('uninject-btn');
        function withApi(fn) {
            if (window.pywebview && pywebview.api) {
                fn(pywebview.api);
            } else {
                window.addEventListener('pywebviewready', () => fn(pywebview.api));
            }
        }
        function showToast(message, isError = false) {
            toast.textContent = message;
            toast.className = `fixed bottom-6 right-6 px-4 py-2 z-50 rounded-md text-sm font-medium shadow-sm ${isError ? 'bg-red-900/80 text-red-200 border border-red-800' : 'bg-green-900/80 text-green-200 border border-green-800'}`;
            toast.classList.add('show');
            toast.classList.remove('opacity-0', 'translate-y-2');
            setTimeout(() => {
                toast.classList.add('opacity-0', 'translate-y-2');
                toast.classList.remove('show');
            }, 3000);
        }
        function inferType(value) {
            const lowerValue = value.toLowerCase().trim();
            if (lowerValue === 'true' || lowerValue === 'false') return 'bool';
            if (/^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/.test(lowerValue) && lowerValue !== '') {
                return lowerValue.indexOf('.') === -1 ? 'int' : 'float';
            }
            return 'string';
        }
        function showConfirm(message) {
            return new Promise((resolve) => {
                document.getElementById('confirm-message').innerHTML = message;
                const modal = document.getElementById('confirm-modal');
                const content = document.getElementById('modal-content-confirm');
                const yesBtn = document.getElementById('confirm-yes');
                const noBtn = document.getElementById('confirm-no');
                const closeBtn = document.getElementById('close-confirm-btn');
                modal.classList.remove('opacity-0', 'invisible');
                content.classList.remove('scale-95');
                const cleanup = () => {
                    modal.classList.add('opacity-0');
                    setTimeout(() => modal.classList.add('invisible'), 200);
                    content.classList.add('scale-95');
                    yesBtn.onclick = null;
                    noBtn.onclick = null;
                    closeBtn.onclick = null;
                    modal.onclick = null;
                };
                yesBtn.onclick = () => { resolve(true); cleanup(); };
                noBtn.onclick = () => { resolve(false); cleanup(); };
                closeBtn.onclick = () => { resolve(false); cleanup(); };
                modal.onclick = (e) => {
                    if (e.target === modal) { resolve(false); cleanup(); }
                };
            });
        }
        function updateRemoveButtonText() {
            if (!deleteSelectedBtn) return;
            const count = flagsToRemove.size;
            const textSpan = deleteSelectedBtn.querySelector('span:last-child');
            if (textSpan) {
                textSpan.textContent = count > 0 ? `Remove (${count})` : 'Remove';
            }
        }
        function showPresetModal() {
            presetModal.classList.remove('opacity-0', 'invisible');
            document.getElementById('modal-content-preset').classList.remove('scale-95');
            presetSearch.value = '';
            renderPresetList();
            setTimeout(() => presetSearch.focus(), 200);
        }
        function hidePresetModal() {
            document.getElementById('modal-content-preset').classList.add('scale-95');
            presetModal.classList.add('opacity-0');
            setTimeout(() => presetModal.classList.add('invisible'), 200);
        } 
        function switchView(activeView) {
            [flagsView, settingsView, presetsView, packsView, terminalView].forEach(v => {
                if (v === activeView) {
                    v.classList.remove('hidden');
                    v.classList.add('view-enter');
                } else {
                    v.classList.add('hidden');
                    v.classList.remove('view-enter');
                }
            });
        }
        function showSettingsView() {
            setActiveTab('settings');
            switchView(settingsView);

                // Default values (used if API fails or setting is missing)
                let autoApply = false;
                let rpcEnabled = true;
                let theme = 'black';
                let currentBossKey = 'insert';
                let safeMode = true;
                let randomization = true;
                let timingAttack = true;
                let reapply = false;
                let offsetless = false;

                withApi(async (api) => {
                    try {
                        const settings = await api.get_settings();
                        // Load all settings with fallbacks
                        autoApply = settings.auto_apply_on_attach ?? false;
                        rpcEnabled = settings.rpc_enabled ?? true;
                        safeMode = settings.safe_mode ?? true;
                        randomization = settings.randomization ?? true;
                        timingAttack = settings.timing_attack ?? true;
                        reapply = settings.reapply ?? false;
                        offsetless = settings.offsetless ?? false;

                        if (settings.hide_key) {
                            currentBossKey = settings.hide_key.trim().toLowerCase();
                        }

                        // Load theme separately
                        const t = await api.get_theme();
                        if (t) theme = t;
                    } catch (err) {
                        console.warn("Failed to load settings in showSettingsView:", err);
                        // Defaults already set above — will be used if API fails
                    }

                    // Apply all loaded values to the UI elements
                    autoApplyToggle.checked = autoApply;
                    discordRpcToggle.checked = rpcEnabled;
                    themeSelect.value = theme;
                    document.getElementById('safe-mode-toggle').checked = safeMode;
                    document.getElementById('randomization-toggle').checked = randomization;
                    document.getElementById('timing-attack-toggle').checked = timingAttack;
                    document.getElementById('reapply-toggle').checked = reapply;
                    document.getElementById('offsetless-toggle').checked = offsetless;
                    document.getElementById('hide-key-display').textContent = currentBossKey.toUpperCase();
                    document.getElementById('hide-key-input').value = '';
                });
        }
        function showFlagsView() {
            setActiveTab('flags');
            switchView(flagsView);
        }
        function showPresetsView() {
            setActiveTab('presets');
            switchView(presetsView);
            withApi(async (api) => {
                try {
                    const s = await api.get_preset_settings();
                    presetOldDeath.checked = !!s.old_death_sound;
                    presetMouseCursor.value = s.mouse_cursor || 'default';
                    presetOldAvatarBg.checked = !!s.old_avatar_editor_background;
                    presetOldCharSounds.checked = !!s.old_character_sounds;
                    presetEmojiType.value = s.emoji_type || 'default';
                    presetUseCustomFont.checked = !!s.use_custom_font;
                    presetFontName.textContent = s.custom_font_path ? s.custom_font_path : '';
                } catch {}
            });
        }
        function showPacksView() {
            setActiveTab('packs');
            switchView(packsView);
        }
        function showTerminalView() {
            setActiveTab('terminal');
            switchView(terminalView);
        }
        function setActiveTab(name) {
            const map = {
                flags: flagsTabBtn,
                settings: settingsTabBtn,
                presets: presetsTabBtn,
                packs: packsTabBtn,
                terminal: terminalTabBtn
            };
            Object.values(map).forEach(btn => {
                if (!btn) return;
                btn.classList.remove('dock-btn-active');
            });
            const active = map[name];
            if (active) {
                active.classList.add('dock-btn-active');
                measureAndUpdateIndicator(active, 320);
            }
        }
        const dockContainer = document.getElementById('dock-container');
        const dockIndicator = document.getElementById('dock-indicator');
        function updateDockIndicator(btn) {
            if (!dockContainer || !dockIndicator || !btn) return;
            const cRect = dockContainer.getBoundingClientRect();
            const bRect = btn.getBoundingClientRect();
            const left = bRect.left - cRect.left;
            const width = bRect.width;
            dockIndicator.style.width = `${Math.round(width)}px`;
            dockIndicator.style.transform = `translateX(${Math.round(left)}px)`;
        }
        function measureAndUpdateIndicator(btn, duration = 280) {
            const start = performance.now();
            function step(now) {
                updateDockIndicator(btn);
                if (now - start < duration) requestAnimationFrame(step);
            }
            requestAnimationFrame(step);
        }
        window.addEventListener('resize', () => {
            const active = document.querySelector('.dock-btn.dock-btn-active');
            if (active) updateDockIndicator(active);
        });
        const dockButtons = [flagsTabBtn, packsTabBtn, presetsTabBtn, terminalTabBtn, settingsTabBtn].filter(Boolean);
        // Indicator follows active tab only; no hover tracking
        function showEditModal(flag) {
            editingFlagName = flag.name;
            editModalTitle.textContent = flag.name;
            editValueInput.value = flag.value;
            editModal.classList.remove('opacity-0', 'invisible');
            document.getElementById('modal-content-edit').classList.remove('scale-95');
            setTimeout(() => {
                editValueInput.focus();
                editValueInput.select();
            }, 200);
        }
        function hideEditModal() {
            document.getElementById('modal-content-edit').classList.add('scale-95');
            editModal.classList.add('opacity-0');
            setTimeout(() => editModal.classList.add('invisible'), 200);
            editingFlagName = null;
        }
        function renderFlagList() {
            const searchTerm = searchBar.value.toLowerCase();
            const filteredFlags = userFlags
                .filter(flag => flag.name.toLowerCase().includes(searchTerm))
                .sort((a, b) => a.name.localeCompare(b.name));
            flagList.innerHTML = '';
            if (filteredFlags.length === 0) {
                flagList.innerHTML = '<div class="p-8 text-center text-gray-500 text-sm">No flags found</div>';
                updateRemoveButtonText();
                return;
            }
            filteredFlags.forEach((flag, index) => {
                const isMarked = flagsToRemove.has(flag.name);
                const row = document.createElement('div');
                row.className = `flag-row row-fixed flex items-center px-4 cursor-pointer ${isMarked ? 'to-remove' : ''}`;
                row.onclick = (e) => {
                    if (e.target.closest('.flag-name-cell') || e.target.closest('.flag-value-cell')) return;
                    if (e.ctrlKey || e.metaKey) {
                        flagsToRemove.has(flag.name) ? flagsToRemove.delete(flag.name) : flagsToRemove.add(flag.name);
                    } else {
                        flagsToRemove.clear();
                        flagsToRemove.add(flag.name);
                    }
                    renderFlagList();
                    updateRemoveButtonText();
                };
                row.innerHTML = `
                    <div class="w-12 text-center text-gray-500 text-sm">${index + 1}</div>
                    <div class="flag-name-cell flex-1 pl-2 pr-2">
                        <span class="text-blue-400 text-sm">${flag.name}</span>
                    </div>
                    <div class="w-24 pl-2 text-gray-400 text-xs uppercase">${flag.type}</div>
                    <div class="flag-value-cell w-32 pl-2 pr-2">
                        <span class="text-gray-200 text-sm">${flag.value}</span>
                    </div>
                `;
                row.querySelector('.flag-name-cell').ondblclick = (e) => {
                    e.stopPropagation();
                    makeNameEditable(row.querySelector('.flag-name-cell'), flag.name);
                };
                row.querySelector('.flag-value-cell').ondblclick = (e) => {
                    e.stopPropagation();
                    showEditModal(flag);
                };
                flagList.appendChild(row);
            });
            updateRemoveButtonText();
        }
        function renderPresetList() {
            const searchTerm = (presetSearch.value || '').toLowerCase();
            presetListDiv.innerHTML = '';
            if (!window.allPresetFlags || window.allPresetFlags.length === 0) {
                presetListDiv.innerHTML = '<div class="p-4 text-center text-gray-500 text-sm">Loading presets...</div>';
                return;
            }
            const filtered = window.allPresetFlags
                .filter(flag => flag.toLowerCase().includes(searchTerm))
                .slice(0, 100);
            if (filtered.length === 0) {
                presetListDiv.innerHTML = '<div class="p-4 text-center text-gray-500 text-sm">No presets found</div>';
                return;
            }
            filtered.forEach(flagName => {
                const isPresent = userFlags.some(f => f.name === flagName);
                const item = document.createElement('button');
                item.className = `w-full text-left p-3 text-sm rounded-md transition-colors ${isPresent ? 'bg-gray-800 text-gray-500 cursor-not-allowed' : 'hover:bg-gray-800 text-gray-200'}`;
                item.textContent = flagName;
                item.disabled = isPresent;
                item.onclick = () => addFlagFromPreset(flagName);
                presetListDiv.appendChild(item);
            });
        }
        presetSearch.oninput = renderPresetList;
        function makeNameEditable(element, flagName) {
            const originalTextElement = element.querySelector('span');
            const originalValue = originalTextElement.textContent;
            const input = document.createElement('input');
            input.type = 'text';
            input.value = originalValue;
            input.className = 'input-field px-2 py-1 rounded text-sm w-full outline-none';
            element.innerHTML = '';
            element.appendChild(input);
            input.focus();
            input.select();
            const save = () => {
                const newValue = input.value.trim();
                if (newValue === '') {
                    showToast('Flag name cannot be empty', true);
                    renderFlagList();
                    return;
                }
                if (newValue !== originalValue && userFlags.some(f => f.name === newValue)) {
                    showToast('Flag name already exists', true);
                    renderFlagList();
                    return;
                }
                const flag = userFlags.find(f => f.name === flagName);
                if (flag) {
                    flag.name = newValue;
                    if (flagsToRemove.has(flagName)) {
                        flagsToRemove.delete(flagName);
                        flagsToRemove.add(newValue);
                    }
                }
                renderFlagList();
                updateRemoveButtonText();
            };
            input.onblur = save;
            input.onkeydown = (e) => {
                if (e.key === 'Enter') input.blur();
                if (e.key === 'Escape') renderFlagList();
            };
        }
        function addFlagFromPreset(flagName) {
            userFlags.unshift({ name: flagName, value: 'False', type: 'bool' });
            renderFlagList();
            showToast(`Added ${flagName}`);
            hidePresetModal();
            updateRemoveButtonText();
        }
        function saveEdit() {
            const flag = userFlags.find(f => f.name === editingFlagName);
            if (!flag) return;
            const newValue = editValueInput.value.trim();
            const newType = inferType(newValue);
            flag.type = newType;
            flag.value = newType === 'bool' ? newValue.charAt(0).toUpperCase() + newValue.slice(1).toLowerCase() : newValue;
            renderFlagList();
            hideEditModal();
            showToast(`Updated ${flag.name}`);
        }
        uninjectBtn.onclick = async () => {
            uninjectBtn.disabled = true;
            uninjectBtn.textContent = 'Uninjecting...';
            try {
                const result = await pywebview.api.uninject_flags();
                if (result.message) {
                    showToast(result.message);
                }
                if (result.success > 0) {
                    showToast(`Restored ${result.success} flags to default`);
                }
                if (result.fail > 0) {
                    showToast(`Failed to restore ${result.fail} flags`, true);
                }
            } catch (e) {
                showToast(`Uninject failed: ${e.message || 'Unknown error'}`, true);
            } finally {
                uninjectBtn.disabled = false;
                uninjectBtn.textContent = 'Uninject';
            }
        };
        const PRESET_PACKS = {
            ultra_fps: [

            ],
            potato: [

            ],
            max_graphics: [

            ],
            low_latency: [

            ],
            bladeball: [
                  {name: "DebugFRMQualityLevelOverride", value: "3", type: "int"},
                  {name: "CSGLevelOfDetailSwitchingDistanceL12", value: "0", type: "int"},
                  {name: "CSGLevelOfDetailSwitchingDistanceL34", value: "0", type: "int"},
                  {name: "NewLightAttenuation3", value: "True", type: "bool"},
                  {name: "DisableFastLogTelemetry", value: "True", type: "bool"},
                  {name: "TelemetryV2Url", value: "null", type: "string"},
                  {name: "BrowserTrackerIdTelemetryEnabled", value: "False", type: "bool"},
                  {name: "DebugPerfMode", value: "False", type: "bool"},
                  {name: "TaskSchedulerLimitTargetFpsTo2402", value: "False", type: "bool"},
                  {name: "CSGLevelOfDetailSwitchingDistance", value: "0", type: "int"},
                  {name: "Network", value: "7", type: "int"},
                  {name: "TeleportClientAssetPreloadingHundredthsPercentage2", value: "100000", type: "int"},
                  {name: "TeleportClientAssetPreloadingHundredthsPercentage", value: "80000", type: "int"},
                  {name: "NumAssetsMaxToPreload", value: "False", type: "bool"},
                  {name: "AssetPreloading", value: "2147483647", type: "int"},
                  {name: "EnableTexturePreloading", value: "999999", type: "int"},
                  {name: "TextureQualityOverride", value: "3", type: "int"},
                  {name: "TextureQualityOverrideEnabled", value: "True", type: "bool"},
                  {name: "CanHideGuiGroupId", value: "32380007", type: "int"},
                  {name: "DisableDPIScale", value: "True", type: "bool"},
                  {name: "DebugGraphicsPreferD3D11", value: "True", type: "bool"},
                  {name: "DebugForceMSAASamples", value: "1", type: "int"},
                  {name: "FontSizePadding", value: "3", type: "int"},
                  {name: "HandleAltEnterFullscreenManually", value: "False", type: "bool"},
                  {name: "TerrainArraySliceSize", value: "0", type: "int"},
                  {name: "DisablePostFx", value: "True", type: "bool"},
                  {name: "TaskSchedulerTargetFps", value: "999", type: "int"},
                  {name: "RenderClampRoughnessMax", value: "-640000000", type: "int"},
                  {name: "TerrainMaterialTablePre2022", value: "False", type: "bool"},
                  {name: "TerrainMaterialTable2022", value: "False", type: "bool"},
                  {name: "LargePacketQueueSizeCutoffMB", value: "1000", type: "int"},
                  {name: "DebugDisplayFPS", value: "True", type: "bool"},
                  {name: "NumFramesToCaptureCallStack", value: "1", type: "int"},
                  {name: "InterpolationMaxDelayMSec", value: "1", type: "int"},
                  {name: "InterpolationDtLimitForLod", value: "1", type: "int"},
                  {name: "ClientPacketHealthyAllocationPercent", value: "50", type: "int"},
                  {name: "CodecMaxIncomingPackets", value: "2139999999", type: "int"},
                  {name: "CodecMaxOutgoingFrames", value: "2139999999", type: "int"},
                  {name: "InterpolationMinAssemblyCount", value: "1", type: "int"},
                  {name: "NumFramesAllowedToBeAboveError", value: "0", type: "int"},
                  {name: "InterpolationAwareTargetTimeLerpHundredth", value: "100", type: "int"},
                  {name: "PerformanceControlFrameTimeMax", value: "1", type: "int"},
                  {name: "MaxAverageFrameDelayExceedFactor", value: "0", type: "int"},
                  {name: "MaxFramesToSend", value: "1", type: "int"},
                  {name: "MaxFrameBufferSize", value: "4", type: "int"},
                  {name: "MaxProcessPacketsStepsAccumulated", value: "0", type: "int"},
                  {name: "MaxProcessPacketsJobScaling", value: "2139999999", type: "int"},
                  {name: "DebugSkyGray", value: "True", type: "bool"},
                  {name: "RakNetLoopMs", value: "1", type: "int"},
                  {name: "ClientPacketMinMicroseconds", value: "1", type: "int"},
                  {name: "ClientPacketMaxDelayMs", value: "1", type: "int"},
                  {name: "ClientPacketUnhealthyContEscMsPerSecond", value: "1", type: "int"},
                  {name: "RakNetMtuValue2InBytes", value: "1200", type: "int"},
                  {name: "RakNetNakResendDelayMs", value: "5", type: "int"},
                  {name: "RakNetApplicationFeedbackScaleUpFactorHundredthPercent", value: "200", type: "int"},
                  {name: "MaxProcessPacketsStepsPerCyclic", value: "2139999999", type: "int"},
                  {name: "PhysicsSenderMaxBandwidthBps", value: "100000", type: "int"},
                  {name: "MaxReceiveToDeserializeLatencyMilliseconds", value: "1", type: "int"},
                  {name: "RakNetResendBufferArrayLength", value: "128", type: "int"},
                  {name: "RakNetClockDriftAdjustmentPerPingMillisecond", value: "2139999999", type: "int"},
                  {name: "RakNetPingFrequencyMillisecond", value: "10", type: "int"},
                  {name: "MovePrerender", value: "True", type: "bool"},
                  {name: "MovePrerenderV2", value: "True", type: "bool"},
                  {name: "DebugTextureManagerSkipMips", value: "5", type: "int"},
                  {name: "RobloxGuiBlurIntensity", value: "0", type: "int"},
                  {name: "S2PhysicsSenderRate", value: "250", type: "int"},
                  {name: "FastGPULightCulling3", value: "True", type: "bool"}
            ],
            notexture: [
                  {name: "TextureCompositorActiveJobs", value: "0", type: "int"},
                  {name: "RenderShadowmapBias", value: "75", type: "int"},
                  {name: "CSGLevelOfDetailSwitchingDistanceL34", value: "0", type: "int"},
                  {name: "CSGLevelOfDetailSwitchingDistanceL23", value: "0", type: "int"},
                  {name: "CSGLevelOfDetailSwitchingDistanceL12", value: "0", type: "int"},
                  {name: "CSGLevelOfDetailSwitchingDistance", value: "0", type: "int"},
                  {name: "TerrainArraySliceSize", value: "0", type: "int"},
                  {name: "PerformanceControlTextureQualityBestUtility", value: "-1", type: "int"},
                  {name: "RenderUseTextureManager224", value: "False", type: "bool"},
                  {name: "IncludePowerSaverMode", value: "True", type: "bool"},
                  {name: "EnablePowerTraceModule", value: "True", type: "bool"},
                  {name: "DebugForceFSMCPULightCulling", value: "True", type: "bool"},
                  {name: "DoNotSkipMipsBasedOnSystemMemoryPS", value: "True", type: "bool"},
                  {name: "DebugLimitMinTextureResolutionWhenSkipMips", value: "9999999", type: "int"},
                  {name: "TM2SkipMipsForUnstreamable2", value: "True", type: "bool"},
                  {name: "DebugTextureManagerSkipMips", value: "10", type: "int"},
                  {name: "TextureQualityOverride", value: "0", type: "int"},
                  {name: "TextureQualityOverrideEnabled", value: "True", type: "bool"},
                  {name: "DisablePostFx", value: "True", type: "bool"},
                  {name: "TaskSchedulerTargetFps", value: "9999999", type: "int"},
                  {name: "TaskSchedulerLimitTargetFpsTo2402", value: "False", type: "bool"},
                  {name: "DebugDisplayFPS", value: "True", type: "bool"},
                  {name: "DebugSkyGray", value: "True", type: "bool"}
            ]
        };
        async function loadPresetPack(packName) {
            const pack = PRESET_PACKS[packName];
            if (!pack) return;
            const confirmed = await showConfirm(`Load "${packName.replace('_', ' ').toUpperCase()}" preset pack?<br><br>This will replace your current flags (${userFlags.length} → ${pack.length}).`);
            if (!confirmed) return;
            userFlags = pack.map(f => ({name: f.name, value: f.value, type: f.type}));
            flagsToRemove.clear();
            renderFlagList();
            updateRemoveButtonText();
            showToast(`Loaded ${pack.length} flags from ${packName.replace('_', ' ')} pack!`);
            logToTerminal(`[+] Loaded preset pack: ${packName.replace('_', ' ').toUpperCase()} (${pack.length} flags)`);
            try {
                await pywebview.api.save_user_flags(userFlags);
            } catch {}
        }
        packsTabBtn.onclick = showPacksView;
        terminalTabBtn.onclick = showTerminalView;
        
        // Button Events
        searchBar.oninput = renderFlagList;
        addNewBtn.onclick = () => {
            const newName = 'NewFlag' + Date.now().toString().slice(-4);
            userFlags.unshift({ name: newName, value: 'False', 'type': 'bool' });
            renderFlagList();
            setTimeout(() => {
                const nameCell = flagList.querySelector('.flag-row:first-child .flag-name-cell');
                if (nameCell) makeNameEditable(nameCell, newName);
            }, 50);
        };
        deleteSelectedBtn.onclick = async () => {
            if (flagsToRemove.size === 0) {
                showToast('No flags selected for removal', true);
                return;
            }
            const removedCount = flagsToRemove.size;
            const confirmed = await showConfirm(`Remove ${removedCount} selected flag(s)?`);
            if (!confirmed) return;
            userFlags = userFlags.filter(f => !flagsToRemove.has(f.name));
            flagsToRemove.clear();
            renderFlagList();
            updateRemoveButtonText();
            showToast(`Removed ${removedCount} flag${removedCount > 1 ? 's' : ''}`);
            logToTerminal(`Removed ${removedCount} selected flag${removedCount > 1 ? 's' : ''}`);
        };
        removeAllBtn.onclick = async () => {
            if (userFlags.length === 0) {
                showToast('No flags to remove', true);
                return;
            }
            const confirmed = await showConfirm(`Remove all ${userFlags.length} flags?`);
            const count = userFlags.length;
            if (confirmed) {
                userFlags = [];
                flagsToRemove.clear();
                renderFlagList();
                updateRemoveButtonText();
                showToast('All flags removed');
                logToTerminal(`Removed all ${count} flags`);
            }
        };
        saveBtn.onclick = async () => {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
            try {
                const result = await pywebview.api.save_user_flags(userFlags);
                if (result.status === "success") {
                    showToast(`Saved ${userFlags.length} flags`);
                } else {
                    showToast(`Save failed: ${result.message}`, true);
                }
            } catch (e) {
                showToast(`Error: ${e.message}`, true);
            }
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Flags';
        };
        applyBtn.onclick = async () => {
            if (applyBtn.disabled) return;
            applyBtn.disabled = true;
            applyBtn.textContent = 'Applying...';
            try {
                const timeout = new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Apply timed out after 25s')), 25000)
                );
                const result = await Promise.race([pywebview.api.apply_flags_to_roblox(userFlags), timeout]);
                if (result && result.message) {
                    const isError = result.fail > 0 || result.message.includes('Failed') || result.message.includes('not attached');
                    showToast(result.message, isError);
                } else {
                    showToast('No response from Roblox', true);
                }
                if (result.removed > 0) {
                    showToast(`Cleaned: ${result.removed} invalid/unknown flags removed`, false);
                }
            } catch (e) {
                showToast(`Apply failed: ${e.message || 'Unknown error'}`, true);
            } finally {
                applyBtn.disabled = false;
                applyBtn.textContent = 'Apply to Roblox';
            }
        };
        importBtn.onclick = () => {
            document.getElementById('json-input-area').value = '';
            document.getElementById('import-json-modal').classList.remove('opacity-0', 'invisible');
            document.getElementById('modal-content-preset').classList.remove('scale-95'); // just in case
            const modalContent = document.querySelector('#import-json-modal .modal-content');
            modalContent.classList.remove('scale-95');
            setTimeout(() => document.getElementById('json-input-area').focus(), 200);
        };
        exportBtn.onclick = async () => {
            if (userFlags.length === 0) {
                showToast('Nothing to export', true);
                return;
            }
            try {
                const result = await pywebview.api.export_flags(userFlags);
                if (result.error) {
                    showToast(result.error, true);
                } else {
                    showToast(`Exported ${userFlags.length} flags successfully!`);
                }
            } catch (err) {
                showToast('Export failed', true);
            }
        };
        killRobloxBtn.onclick = async () => {
            if (killRobloxBtn.disabled) return;
            killRobloxBtn.disabled = true;
            const confirmed = await showConfirm('Kill Roblox now?');
            if (!confirmed) {
                killRobloxBtn.disabled = false;
                return;
            }
            try {
                const res = await pywebview.api.kill_roblox();
                if (res && res.success) {
                    showToast('Terminated');
                } else {
                    showToast(res?.error || 'Failed to kill Roblox', true);
                }
            } catch (e) {
                showToast(`Error: ${e.message}`, true);
            }
            killRobloxBtn.disabled = false;
        };
        showPresetBtn.onclick = showPresetModal;
        closeModalBtnPreset.onclick = hidePresetModal;
        flagsTabBtn.onclick = showFlagsView;
        settingsTabBtn.onclick = showSettingsView;
        presetsTabBtn.onclick = showPresetsView;

        let currentBossKey = 'insert';

        settingsTabBtn.onclick = async () => {
                showSettingsView();
                let autoApply = false;
                let rpcEnabled = true;
                let theme = 'black';
                let safeMode = true;
                let randomization = true;
                let timingAttack = true;
                let reapply = false;
                let offsetless = false;

                try {
                        await withApi(async (api) => {
                                const settings = await api.get_settings();
                                autoApply = settings.auto_apply_on_attach ?? false;
                                rpcEnabled = settings.rpc_enabled ?? true;
                                safeMode = settings.safe_mode ?? true;
                                randomization = settings.randomization ?? true;
                                timingAttack = settings.timing_attack ?? true;
                                reapply = settings.reapply ?? false;
                                offsetless = settings.offsetless ?? false;
                                if (settings.hide_key) {
                                        currentBossKey = settings.hide_key.trim().toLowerCase();
                                }
                                const t = await api.get_theme();
                                if (t) theme = t;
                        });
                } catch (e) {
                        console.error("Load settings error:", e);
                        showToast("Failed to load settings", true);
                }

                autoApplyToggle.checked = autoApply;
                discordRpcToggle.checked = rpcEnabled;
                themeSelect.value = theme;
                document.getElementById('safe-mode-toggle').checked = safeMode;
                document.getElementById('randomization-toggle').checked = randomization;
                document.getElementById('timing-attack-toggle').checked = timingAttack;
                document.getElementById('reapply-toggle').checked = reapply;
                document.getElementById('offsetless-toggle').checked = offsetless;
                document.getElementById('hide-key-display').textContent = currentBossKey.toUpperCase();
                document.getElementById('hide-key-input').value = '';
        };

        saveSettingsBtn.onclick = async () => {
                const autoApply = autoApplyToggle.checked;
                const rpcEnabled = discordRpcToggle.checked;
                const theme = themeSelect.value;
                const newKey = document.getElementById('hide-key-input').value.trim().toLowerCase();
                const safeMode = document.getElementById('safe-mode-toggle').checked;
                const randomization = document.getElementById('randomization-toggle').checked;
                const timingAttack = document.getElementById('timing-attack-toggle').checked;
                const reapply = document.getElementById('reapply-toggle').checked;
                const offsetless = document.getElementById('offsetless-toggle').checked;

                try {
                        await withApi(async (api) => {
                                await api.set_auto_apply_on_attach(autoApply);
                                await api.set_rpc_enabled(rpcEnabled);
                                await api.save_theme(theme);
                                await api.set_safe_mode(safeMode);
                                await api.set_random(randomization);
                                await api.set_timing_attack(timingAttack);
                                await api.set_reapply(reapply);
                                await api.set_offsetless(offsetless);

                                const updated = await api.get_settings();

                                if (newKey) {
                                        const res = await api.set_hide_key(newKey);
                                        if (res.ok) {
                                                currentBossKey = newKey;
                                                document.getElementById('hide-key-display').textContent = newKey.toUpperCase();
                                                document.getElementById('hide-key-input').value = '';
                                                showToast(`Keybind changed to ${newKey.toUpperCase()}!`);
                                        } else {
                                                showToast(res.error || 'Invalid key', true);
                                        }
                                }
                        });

                        document.documentElement.setAttribute('data-theme', theme === 'white' ? 'white' : theme);
                        showToast('Settings saved successfully!', false);
                } catch (e) {
                        console.error("Save error:", e);
                        showToast('Save failed', true);
                }

                showFlagsView();
        };
        presetChooseFont.onclick = async () => {
            await withApi(async (api) => {
                try {
                    const res = await api.choose_custom_font();
                    if (res && res.path) {
                        presetFontName.textContent = res.path;
                    }
                } catch {}
            });
        };
        discordTabBtn.onclick = () => {
            window.open('https://discord.gg/Velostrap', '_blank');
        };
        savePresetsBtn.onclick = async () => {
            await withApi(async (api) => {
                try {
                    await api.save_preset_settings({
                        old_death_sound: presetOldDeath.checked,
                        mouse_cursor: presetMouseCursor.value,
                        old_avatar_editor_background: presetOldAvatarBg.checked,
                        old_character_sounds: presetOldCharSounds.checked,
                        emoji_type: presetEmojiType.value,
                        use_custom_font: presetUseCustomFont.checked,
                        custom_font_path: presetFontName.textContent || ''
                    });
                } catch {}
            });
            showFlagsView();
            showToast('Presets saved');
        };
        closeModalBtnEdit.onclick = hideEditModal;
        saveEditBtn.onclick = saveEdit;

        document.getElementById('close-import-json-modal').onclick = () => {
            document.getElementById('json-input-area').value = '';  // Clear text when closing
            document.getElementById('import-json-modal').classList.add('opacity-0', 'invisible');
            document.querySelector('#import-json-modal .modal-content').classList.add('scale-95');
        };

        document.getElementById('clear-import-json').onclick = () => {
            document.getElementById('json-input-area').value = '';
            showToast('JSON cleared', false);
            document.getElementById('json-input-area').focus();
        };

        document.getElementById('import-from-file-btn').onclick = async () => {
            try {
                const result = await pywebview.api.import_from_json();
                if (result.error) {
                    showToast(result.error, true);
                    return;
                }
                if (result.flags && result.flags.length > 0) {
                    const jsonStr = JSON.stringify(result.flags.map(f => ({
                        [f.name]: f.value
                    })).reduce((acc, curr) => ({...acc, ...curr}), {}), null, 2);
                    document.getElementById('json-input-area').value = jsonStr;
                    showToast(`Loaded ${result.flags.length} flags from file`, false);
                }
            } catch (e) {
                showToast('Failed to load file', true);
            }
        };

        document.getElementById('ok-import-json').onclick = async () => {
            const rawText = document.getElementById('json-input-area').value.trim();
            if (!rawText) {
                showToast('No JSON provided', true);
                return;
            }
            let parsed;
            try {
                parsed = JSON.parse(rawText);
            } catch (e) {
                showToast('Invalid JSON format', true);
                return;
            }
            withApi(async (api) => {
                try {
                    const content_json = await api.load_json_safe(rawText);
                    const official_flags = await api.get_official_flags() || null;
                    const cleaned = await api.filter_and_convert_flags(content_json, official_flags);
                    if (cleaned.length === 0) {
                        showToast('No valid flags found after cleaning', true);
                        return;
                    }
                    const confirmed = await showConfirm(`Import ${cleaned.length} cleaned flags?`);
                    if (confirmed) {
                        userFlags = cleaned;
                        flagsToRemove.clear();
                        renderFlagList();
                        updateRemoveButtonText();
                        showToast(`Imported ${cleaned.length} flags successfully!`);
                        // Close modal after successful import
                        document.getElementById('import-json-modal').classList.add('opacity-0', 'invisible');
                        document.querySelector('#import-json-modal .modal-content').classList.add('scale-95');
                    }
                } catch (err) {
                    showToast('Import failed: ' + (err.message || 'Unknown error'), true);
                }
            });
        };

        // Initialize
        withApi(async (api) => {
            try {
                userFlags = await api.load_user_flags();
                window.userFlags = userFlags;
                renderFlagList();
                updateRemoveButtonText();
                const t = await api.get_theme();
                document.documentElement.setAttribute('data-theme', (t === 'light') ? 'white' : t);
                const initialActive = document.querySelector('.dock-btn.dock-btn-active');
                if (initialActive) measureAndUpdateIndicator(initialActive, 300);
            } catch (e) {
                showToast(`Failed to load flags: ${e.message}`, true);
                userFlags = [];
                renderFlagList();
            }
        });
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                e.preventDefault();
                const visibleRows = flagList.querySelectorAll('.flag-row');
                if (visibleRows.length === 0) return;
                const allMarked = Array.from(visibleRows).every(row => {
                    const name = row.querySelector('.flag-name-cell span').textContent;
                    return flagsToRemove.has(name);
                });
                visibleRows.forEach(row => {
                    const name = row.querySelector('.flag-name-cell span').textContent;
                    if (allMarked) {
                        flagsToRemove.delete(name);
                    } else {
                        flagsToRemove.add(name);
                    }
                });
                renderFlagList();
                updateRemoveButtonText();
            }
        });
    </script>
</body>
</html>
"""
if __name__ == '__main__':
    api = Api()
    window = webview.create_window(
        title='VELORIN-V3',
        html=html,
        js_api=api,
        resizable=False,
        width=1000,
        height=720,
        background_color="#0a0a0a",
        text_select=False,
        frameless=True,
        easy_drag=False,
    )
    api.set_window(window)

    terminal_logger = GUITerminalLogger(window)
    sys.stdout = terminal_logger
    sys.stderr = terminal_logger

    def on_loaded():
        print("[GUI] Webview page fully loaded")
        terminal_logger.mark_ready()
        try:
            window.evaluate_js("""
                const output = document.getElementById('terminal-output');
                output.innerHTML = '';
                logToTerminal('VELOSTRAP Terminal Active', 'success');
            """)
        except:
            pass

    window.events.loaded += on_loaded

    webview.start(
        debug=False,
        gui='edgechromium',
        http_server=False
    )
