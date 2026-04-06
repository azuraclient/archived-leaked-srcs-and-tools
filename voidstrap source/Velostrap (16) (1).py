import sys
import os
import threading
import json
import webview
import pymem
import pymem.process
import pymem.pattern

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

class VelostrapEngine:
    def __init__(self):
        self.pm = None
        self.module = None
        self.cached_singleton = 0
        self.flag_cache = {}

    def attach(self):
        if self.pm:
            try:
                self.pm.read_int(self.pm.base_address)
                return True
            except:
                self.pm = None
        
        try:
            self.pm = pymem.Pymem("RobloxPlayerBeta.exe")
            self.module = pymem.process.module_from_name(self.pm.process_handle, "RobloxPlayerBeta.exe")
            self.cached_singleton = 0
            self.flag_cache = {}
            return True
        except:
            return False

    def get_singleton(self):
        if self.cached_singleton: return self.cached_singleton
        if not self.attach(): return 0
        
        res = pymem.pattern.pattern_scan_module(self.pm.process_handle, self.module, PATTERN)
        if not res: return 0
        
        try:
            rel = self.pm.read_int(res + 7)
            ptr = (res + 11) + rel
            self.cached_singleton = self.pm.read_ulonglong(ptr)
            return self.cached_singleton
        except: return 0

    def internal_scan(self, name):
        singleton = self.get_singleton()
        if not singleton: return 0

        basis = M_BASIS
        for char in name:
            basis ^= ord(char)
            basis = (basis * M_PRIME) & 0xFFFFFFFFFFFFFFFF 

        try:
            h_map = singleton + 8 
            m_bytes = self.pm.read_bytes(h_map, 56)
            m_end = int.from_bytes(m_bytes[OFF_MAP_END:OFF_MAP_END+8], 'little')
            m_list = int.from_bytes(m_bytes[OFF_MAP_LIST:OFF_MAP_LIST+8], 'little')
            m_mask = int.from_bytes(m_bytes[OFF_MAP_MASK:OFF_MAP_MASK+8], 'little')
            
            if m_mask == 0 or m_list == 0: return 0
            
            b_idx = basis & m_mask
            b_base = m_list + (b_idx * 16) 
            b_data = self.pm.read_bytes(b_base, 16)
            curr = int.from_bytes(b_data[8:16], 'little')

            if curr == m_end: return 0

            visited = set()
            limit = 0
            while True:
                if curr in visited or limit > 1500: return 0
                visited.add(curr)
                limit += 1

                e_data = self.pm.read_bytes(curr, 56)
                forward = int.from_bytes(e_data[OFF_ENTRY_FORWARD:OFF_ENTRY_FORWARD+8], 'little')
                s_size = int.from_bytes(e_data[OFF_ENTRY_STRING+OFF_STR_SIZE : OFF_ENTRY_STRING+OFF_STR_SIZE+8], 'little')
                s_alloc = int.from_bytes(e_data[OFF_ENTRY_STRING+OFF_STR_ALLOC : OFF_ENTRY_STRING+OFF_STR_ALLOC+8], 'little')
                
                f_name = ""
                if s_alloc > 0xF:
                    ptr = int.from_bytes(e_data[OFF_ENTRY_STRING : OFF_ENTRY_STRING+8], 'little')
                    try: f_name = self.pm.read_bytes(ptr, s_size).decode('utf-8', 'ignore')
                    except: pass
                else:
                    f_name = e_data[OFF_ENTRY_STRING : OFF_ENTRY_STRING+s_size].decode('utf-8', 'ignore')

                if f_name == name:
                    return int.from_bytes(e_data[OFF_ENTRY_GET_SET : OFF_ENTRY_GET_SET+8], 'little')

                if curr == forward or forward == 0: break
                curr = forward
        except: pass
        return 0

    def find_address(self, key):
        prefixes = ["FFlag", "DFFlag", "FInt", "DFInt", "FString", "DFString", "FLog", "DFLog", "FVariable"]
        clean = key
        for p in prefixes:
            if key.startswith(p):
                clean = key[len(p):]
                break
        candidates = [key, clean] + [p + clean for p in prefixes]
        checked = set()
        for c in candidates:
            if c in checked: continue
            checked.add(c)
            addr = self.internal_scan(c)
            if addr: return addr, c
        return 0, None

    def write_mem(self, addr, val, is_str):
        try:
            struct = self.pm.read_bytes(addr, 0xD0)
            v_ptr = int.from_bytes(struct[OFF_FFLAG_VALUE_PTR : OFF_FFLAG_VALUE_PTR+8], 'little')
            if not v_ptr: return False

            if is_str:
                buf = self.pm.read_ulonglong(v_ptr)
                cap = self.pm.read_ulonglong(v_ptr + 0x10)
                b_val = str(val).encode('utf-8')
                if len(b_val) > cap: return False
                self.pm.write_bytes(buf, b_val + b'\x00', len(b_val) + 1)
                self.pm.write_ulonglong(v_ptr + 0x8, len(b_val))
            else:
                self.pm.write_int(v_ptr, int(val))
            return True
        except: return False

    def execute(self, data):
        logs = []
        if not self.attach():
            return [{"msg": "Waiting for Roblox process...", "type": "err"}]
        
        for k, v in data.items():
            is_str = isinstance(v, str) and v.lower() not in ['true', 'false']
            t_val = v
            if not is_str:
                if str(v).lower() == 'true': t_val = 1
                elif str(v).lower() == 'false': t_val = 0
                else:
                    try: t_val = int(v)
                    except: 
                        logs.append({"msg": f"Invalid Value: {k}", "type": "err"})
                        continue

            addr, name = self.find_address(k)
            if addr:
                if self.write_mem(addr, t_val, is_str):
                    logs.append({"msg": f"{name} -> {t_val}", "type": "ok"})
                else:
                    logs.append({"msg": f"Write Failed: {name}", "type": "err"})
            else:
                logs.append({"msg": f"Not Found: {k}", "type": "warn"})
        return logs

engine = VelostrapEngine()

CONFIG_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'velostrap')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

DEFAULT_CONFIG = {
    "autoinject": False,
    "tray": False,
    "theme": "dark",
    "lastFlags": {}
}

def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
    except:
        pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except:
        return False

app_config = load_config()

class AppApi:
    def get_status(self):
        ok = engine.attach()
        pid = engine.pm.process_id if ok else 0
        return {"ok": ok, "pid": pid}

    def inject(self, data):
        return engine.execute(data)
    
    def minimize_window(self):
        if webview.windows:
            webview.windows[0].minimize()
    
    def maximize_window(self):
        if webview.windows:
            webview.windows[0].toggle_fullscreen()
    
    def close_window(self):
        if webview.windows:
            webview.windows[0].destroy()
    
    def move_window(self, dx, dy):
        if webview.windows:
            win = webview.windows[0]
            x, y = win.x + dx, win.y + dy
            win.move(x, y)
    
    def get_window_pos(self):
        if webview.windows:
            win = webview.windows[0]
            return {"x": win.x, "y": win.y}
        return {"x": 0, "y": 0}
    
    def get_config(self):
        return app_config
    
    def save_setting(self, key, value):
        global app_config
        app_config[key] = value
        save_config(app_config)
        return True
    
    def save_flags(self, flags):
        global app_config
        app_config["lastFlags"] = flags
        save_config(app_config)
        return True

HTML_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>velostrap</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;500;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg: #030305;
            --glass: rgba(20, 20, 25, 0.75);
            --sidebar-bg: #0a0a0c;
            --border: rgba(255, 255, 255, 0.08);
            --primary: #6366f1;
            --primary-glow: rgba(99, 102, 241, 0.4);
            --text: #e0e0e0;
            --success: #10b981;
            --danger: #ef4444;
            --warn: #f59e0b;
        }

        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Space Grotesk', sans-serif;
            height: 100vh;
            margin: 0;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .app-container {
            display: flex;
            flex-direction: column;
            height: 100%;
            background: radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.05), transparent 40%);
        }

        .titlebar {
            height: 35px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 15px;
            background: linear-gradient(90deg, #111 0%, #08080a 100%);
            -webkit-app-region: drag;
            user-select: none;
            z-index: 100;
        }

        .window-title {
            font-size: 0.75rem;
            color: #666;
            letter-spacing: 1px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .titlebar-right {
            display: flex;
            align-items: center;
            gap: 15px;
            -webkit-app-region: no-drag;
        }
        
        .status-badge {
            background: rgba(255,255,255,0.03);
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.65rem;
            display: flex;
            align-items: center;
            gap: 6px;
            border: 1px solid rgba(255,255,255,0.05);
            font-family: 'JetBrains Mono', monospace;
        }
        .dot { width: 5px; height: 5px; border-radius: 50%; background: #555; transition: 0.3s; }
        .dot.on { background: var(--success); box-shadow: 0 0 6px var(--success); }
        .dot.off { background: var(--danger); }
        
        .window-controls {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .win-btn {
            width: 22px;
            height: 22px;
            border: none;
            border-radius: 4px;
            background: transparent;
            color: #555;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s;
            font-size: 0.7rem;
        }
        .win-btn:hover { background: rgba(255,255,255,0.1); color: #fff; }
        .win-btn.close:hover { background: var(--danger); color: #fff; }

        .main-body {
            display: flex;
            flex: 1;
            overflow: hidden;
        }

        .nav-sidebar {
            width: 200px;
            background: var(--sidebar-bg);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            padding: 20px 15px;
            gap: 30px;
            flex-shrink: 0;
        }

        .app-logo {
            font-size: 1.1rem;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
            padding-left: 10px;
        }
        .app-logo i { color: var(--primary); font-size: 1rem; }

        .nav-menu {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .nav-btn {
            background: transparent;
            border: none;
            color: #777;
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 12px;
            text-align: left;
        }
        .nav-btn:hover {
            background: rgba(255,255,255,0.03);
            color: #bbb;
        }
        .nav-btn.active {
            background: rgba(99, 102, 241, 0.1);
            color: #fff;
            border: 1px solid rgba(99, 102, 241, 0.2);
        }
        .nav-btn.active i { color: var(--primary); }
        .nav-btn i { width: 20px; text-align: center; }

        .content-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background: rgba(0,0,0,0.1);
        }

        .workspace {
            flex: 1;
            display: flex;
            overflow: hidden;
        }

        #tab-editor {
            width: 100%;
            height: 100%;
        }

        .editor-pane {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 25px;
        }
        
        .pane-header { 
            font-size: 0.8rem; 
            text-transform: uppercase; 
            color: #666; 
            margin-bottom: 12px; 
            font-weight: 700; 
            letter-spacing: 1px; 
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        textarea {
            flex: 1;
            background: #0e0e11;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            color: #d4d4d8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
            resize: none;
            outline: none;
            line-height: 1.6;
            transition: 0.2s;
        }
        textarea:focus { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1); }

        .action-sidebar {
            width: 200px;
            padding: 25px;
            background: rgba(0,0,0,0.15);
            border-left: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .action-btn {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 6px;
            font-weight: 700;
            font-family: 'Space Grotesk', sans-serif;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            text-transform: uppercase;
            font-size: 0.8rem;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), #4f46e5);
            color: white;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2);
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3); }
        .btn-primary:active { transform: scale(0.98); }

        .btn-secondary {
            background: transparent;
            border: 1px solid var(--border);
            color: #aaa;
        }
        .btn-secondary:hover { background: rgba(255,255,255,0.05); color: #fff; border-color: #555; }

        .tab-panel { display: none; flex: 1; overflow: hidden; }
        .tab-panel.active { display: flex; }
        
        .presets-panel {
            flex-direction: column;
            padding: 30px;
            gap: 15px;
            overflow-y: auto;
        }
        .preset-card {
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .preset-card:hover {
            background: rgba(255,255,255,0.04);
            border-color: var(--primary);
            transform: translateX(5px);
        }
        .preset-info h3 { margin: 0 0 6px 0; font-size: 1rem; color: #fff; }
        .preset-info p { margin: 0; font-size: 0.8rem; color: #777; }
        .preset-icon {
            width: 45px; height: 45px;
            border-radius: 10px;
            background: linear-gradient(135deg, var(--primary), #4f46e5);
            display: flex; align-items: center; justify-content: center;
            color: #fff; font-size: 1.1rem;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
        
        .settings-panel {
            flex-direction: column;
            padding: 30px;
            gap: 20px;
            overflow-y: auto;
        }
        .settings-section {
            background: rgba(255,255,255,0.015);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 25px;
        }
        .settings-section h3 {
            margin: 0 0 20px 0;
            font-size: 0.8rem;
            text-transform: uppercase;
            color: #888;
            letter-spacing: 1px;
            display: flex; align-items: center; gap: 8px;
        }
        .setting-row {
            display: flex; align-items: center; justify-content: space-between;
            padding: 15px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .setting-row:last-child { border-bottom: none; }
        .setting-label { display: flex; flex-direction: column; gap: 4px; }
        .setting-label span { font-size: 0.95rem; color: #e0e0e0; }
        .setting-label small { font-size: 0.75rem; color: #666; }
        
        .toggle {
            width: 46px; height: 26px;
            background: #2a2a2e;
            border-radius: 13px;
            position: relative;
            cursor: pointer;
            transition: 0.2s;
            border: 1px solid var(--border);
        }
        .toggle.on { background: var(--primary); border-color: var(--primary); }
        .toggle::after {
            content: ''; position: absolute;
            width: 18px; height: 18px;
            background: #fff; border-radius: 50%;
            top: 3px; left: 3px;
            transition: 0.2s cubic-bezier(0.4, 0.0, 0.2, 1);
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        .toggle.on::after { left: 23px; }
        
        .setting-select {
            background: #111;
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 8px 12px;
            color: #fff;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.85rem;
            cursor: pointer;
            outline: none;
        }
        .setting-select:focus { border-color: var(--primary); }

        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #555; }

    </style>
</head>
<body>

    <div class="app-container">
        
        <div class="titlebar">
            <div class="window-title">velostrap v2</div>
            
            <div class="titlebar-right">
                <div class="status-badge">
                    <div id="dot" class="dot"></div>
                    <span id="stat-txt">CONNECTING...</span>
                </div>
                
                <div class="window-controls">
                    <button class="win-btn" onclick="minimizeWindow()" title="Minimize">
                        <i class="fa-solid fa-minus"></i>
                    </button>
                    <button class="win-btn" onclick="maximizeWindow()" title="Maximize">
                        <i class="fa-regular fa-square"></i>
                    </button>
                    <button class="win-btn close" onclick="closeWindow()" title="Close">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
            </div>
        </div>

        <div class="main-body">
            
            <div class="nav-sidebar">
                <div class="app-logo">
                    <i class="fa-solid fa-cube"></i> VELOSTRAP
                </div>

                <div class="nav-menu">
                    <button class="nav-btn active" onclick="switchTab('editor')">
                        <i class="fa-solid fa-code"></i> Editor
                    </button>
                    <button class="nav-btn" onclick="switchTab('presets')">
                        <i class="fa-solid fa-bookmark"></i> Presets
                    </button>
                    <button class="nav-btn" onclick="switchTab('settings')">
                        <i class="fa-solid fa-gear"></i> Settings
                    </button>
                </div>
            </div>

            <div class="content-area">
                
                <div class="workspace">
                    <div id="tab-editor" class="tab-panel active">
                        <div class="editor-pane">
                            <div class="pane-header">Fast Flag Configuration</div>
                            <textarea id="jsonIn" spellcheck="false">{
  "TaskSchedulerTargetFps": 999,
  "FFlagTaskSchedulerLimitTargetFpsTo2402": false,
  "DebugDisplayFPS": true
}</textarea>
                        </div>

                        <div class="action-sidebar">
                            <div class="pane-header">Actions</div>
                            <button class="action-btn btn-primary" onclick="inject()">
                                <i class="fa-solid fa-bolt"></i> INJECT
                            </button>
                            <button class="action-btn btn-secondary" onclick="format()">
                                <i class="fa-solid fa-code"></i> BEAUTIFY
                            </button>
                        </div>
                    </div>
                    
                    <div id="tab-presets" class="tab-panel presets-panel">
                        <div class="pane-header">Available Presets</div>
                        
                        <div class="preset-card" onclick="loadPreset('fps')">
                            <div class="preset-info">
                                <h3><i class="fa-solid fa-rocket"></i> FPS Boost</h3>
                                <p>Unlock higher framerates and reduce input lag significantly.</p>
                            </div>
                            <div class="preset-icon"><i class="fa-solid fa-gauge-high"></i></div>
                        </div>
                        
                        <div class="preset-card" onclick="loadPreset('graphics')">
                            <div class="preset-info">
                                <h3><i class="fa-solid fa-microchip"></i> Potato Mode</h3>
                                <p>Extremely low graphics for low-end hardware optimization.</p>
                            </div>
                            <div class="preset-icon"><i class="fa-solid fa-display"></i></div>
                        </div>
                        
                        <div class="preset-card" onclick="loadPreset('rendering')">
                            <div class="preset-info">
                                <h3><i class="fa-solid fa-ghost"></i> Physics & Hitbox</h3>
                                <p>Optimized interpolation for tracking players (phantom settings).</p>
                            </div>
                            <div class="preset-icon"><i class="fa-solid fa-crosshairs"></i></div>
                        </div>
                    </div>
                    
                    <div id="tab-settings" class="tab-panel settings-panel">
                        <div class="settings-section">
                            <h3><i class="fa-solid fa-sliders"></i> General</h3>
                            
                                                    <div class="settings-section">
                            <h3><i class="fa-solid fa-palette"></i> Interface</h3>
                            
                            <div class="setting-row">
                                <div class="setting-label">
                                    <span>Accent Color</span>
                                    <small>Customize the application color theme.</small>
                                </div>
                                <select class="setting-select" id="theme-select" onchange="changeTheme()">
                                    <option value="dark">Indigo (Default)</option>
                                    <option value="midnight">Ocean Blue</option>
                                    <option value="purple">Neon Purple</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>

<script>
    function format() {
        const el = document.getElementById('jsonIn');
        try {
            const o = JSON.parse(el.value);
            el.value = JSON.stringify(o, null, 2);
        } catch {}
    }

    async function inject() {
        const el = document.getElementById('jsonIn');
        let data;
        try { data = JSON.parse(el.value); } 
        catch { return; }

        try {
            const logs = await window.pywebview.api.inject(data);
        } catch(e) {}
    }

    setInterval(async () => {
        try {
            if(!window.pywebview) return;
            
            const d = await window.pywebview.api.get_status();
            const dot = document.getElementById('dot');
            const txt = document.getElementById('stat-txt');
            
            if(d.ok) {
                dot.className = 'dot on';
                txt.innerText = "ATTACHED (" + d.pid + ")";
                txt.style.color = "#fff";
            } else {
                dot.className = 'dot off';
                txt.innerText = "SEARCHING...";
                txt.style.color = "#666";
            }
        } catch {}
    }, 1500);

    function minimizeWindow() {
        if(window.pywebview && window.pywebview.api) {
            window.pywebview.api.minimize_window();
        }
    }
    
    function maximizeWindow() {
        if(window.pywebview && window.pywebview.api) {
            window.pywebview.api.maximize_window();
        }
    }
    
    function closeWindow() {
        if(window.pywebview && window.pywebview.api) {
            window.pywebview.api.close_window();
        }
    }
    
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    
    document.addEventListener('DOMContentLoaded', () => {
        const titlebar = document.querySelector('.titlebar');
        
        if(titlebar) {
            titlebar.addEventListener('mousedown', (e) => {
                if(e.target.closest('.win-btn') || e.target.closest('.status-badge')) return;
                
                isDragging = true;
                dragStartX = e.screenX;
                dragStartY = e.screenY;
                e.preventDefault();
            });
        }
        
        document.addEventListener('mousemove', async (e) => {
            if(!isDragging) return;
            if(!window.pywebview || !window.pywebview.api) return;
            
            const dx = e.screenX - dragStartX;
            const dy = e.screenY - dragStartY;
            
            if(dx !== 0 || dy !== 0) {
                await window.pywebview.api.move_window(dx, dy);
                dragStartX = e.screenX;
                dragStartY = e.screenY;
            }
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
        
        document.addEventListener('selectstart', (e) => {
            if(isDragging) e.preventDefault();
        });
    });
    
    function switchTab(tab) {
        const btns = document.querySelectorAll('.nav-btn');
        btns.forEach(btn => btn.classList.remove('active'));
        if(event && event.target) {
            const btn = event.target.closest('.nav-btn');
            if(btn) btn.classList.add('active');
        }
        
        document.querySelectorAll('.tab-panel').forEach(p => {
            p.classList.remove('active');
            p.style.display = 'none';
        });
        
        const panel = document.getElementById('tab-' + tab);
        if(panel) {
            panel.classList.add('active');
            panel.style.display = 'flex';
        }
    }
    
    const PRESETS = {
        fps: {
    "TaskSchedulerTargetFps": "2222",
    "HandleAltEnterFullscreenManually": "False",
    "DebugPauseVoxelizer": "True",
    "DebugSkyGray": "True",
    "DebugPerfMode": "False",
    "FastGPULightCulling3": "True",
    "S2PhysicsSenderRate": "38000",
    // ... (rest of fps preset remains unchanged)
    "EnablePowerTraceModule": "True",
    "IncludePowerSaverMode": "True"
},
        graphics: {
    "TextureCompositorActiveJobs": "0",
    "RenderShadowmapBias": "75",
    // ... (rest unchanged)
    "DebugSkyGray": "True"
},
        rendering: {
  "DFFlagDebugMechanismInterpolationWorldSpace": true,
  "DFFlagSimLocalBallSocketInterpolation": true,     
  // ... (rest unchanged)
  "DFIntMaxFrameBufferSize": 1
}
    };
    
    function loadPreset(name) {
        const preset = PRESETS[name];
        if(preset) {
            document.getElementById('jsonIn').value = JSON.stringify(preset, null, 2);
            switchTabByName('editor');
        }
    }
    
    function switchTabByName(tab) {
        const btns = document.querySelectorAll('.nav-btn');
        btns.forEach((btn, i) => {
            btn.classList.remove('active');
            if(tab === 'editor' && i === 0) btn.classList.add('active');
            if(tab === 'presets' && i === 1) btn.classList.add('active');
            if(tab === 'settings' && i === 2) btn.classList.add('active');
        });
        
        document.querySelectorAll('.tab-panel').forEach(p => {
            p.classList.remove('active');
            p.style.display = 'none';
        });
        
        const panel = document.getElementById('tab-' + tab);
        if(panel) {
            panel.classList.add('active');
            panel.style.display = 'flex';
        }
    }
    
    async function toggleSetting(setting) {
        const toggle = document.getElementById('toggle-' + setting);
        if(toggle) {
            toggle.classList.toggle('on');
            const isOn = toggle.classList.contains('on');
            
            if(window.pywebview && window.pywebview.api) {
                await window.pywebview.api.save_setting(setting, isOn);
            }
        }
    }
    
    async function changeTheme() {
        const theme = document.getElementById('theme-select').value;
        const root = document.documentElement;
        
        if(theme === 'midnight') {
            root.style.setProperty('--primary', '#3b82f6');
            root.style.setProperty('--primary-glow', 'rgba(59, 130, 246, 0.4)');
        } else if(theme === 'purple') {
            root.style.setProperty('--primary', '#a855f7');
            root.style.setProperty('--primary-glow', 'rgba(168, 85, 247, 0.4)');
        } else {
            root.style.setProperty('--primary', '#6366f1');
            root.style.setProperty('--primary-glow', 'rgba(99, 102, 241, 0.4)');
        }
        
        if(window.pywebview && window.pywebview.api) {
            await window.pywebview.api.save_setting('theme', theme);
        }
    }
    
    async function loadConfig() {
        try {
            if(!window.pywebview || !window.pywebview.api) return;
            
            const config = await window.pywebview.api.get_config();
            
            if(config.autoinject) document.getElementById('toggle-autoinject')?.classList.add('on');
            if(config.tray) document.getElementById('toggle-tray')?.classList.add('on');
            
            if(config.theme) {
                document.getElementById('theme-select').value = config.theme;
                changeTheme();
            }
            
            if(config.lastFlags && Object.keys(config.lastFlags).length > 0) {
                document.getElementById('jsonIn').value = JSON.stringify(config.lastFlags, null, 2);
            }
        } catch(e) {}
    }
    
    window.addEventListener('pywebviewready', loadConfig);
    
    const originalInject = inject;
    inject = async function() {
        const el = document.getElementById('jsonIn');
        let data;
        try { data = JSON.parse(el.value); }
        catch { return; }
        
        if(window.pywebview && window.pywebview.api) {
            await window.pywebview.api.save_flags(data);
        }
        
        try {
            await window.pywebview.api.inject(data);
        } catch(e) {}
    }
</script>
</body>
</html>
"""

if __name__ == '__main__':
    api = AppApi()
    
    window = webview.create_window(
        'velostrap',
        html=HTML_UI,
        js_api=api,
        width=1000,
        height=720,
        resizable=True,
        frameless=True,
        easy_drag=False,
        background_color='#030305'
    )
    
    webview.start(debug=False)