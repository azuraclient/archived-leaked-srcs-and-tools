; made by velostrap and if you dare to skid this


#SingleInstance Force

ProcessSetPriority "High"


MsgBox "dawg we make the best ahk injector for fflags join discord.gg/velostrap"








Global APP_DIR := A_AppData "\ahkinjector"
if !DirExist(APP_DIR) {
    DirCreate(APP_DIR)
}

Global USER_FLAGS_FILE := APP_DIR "\user_flags.json"
Global UserFlags := []
Global AllOffsets := Map()
Global AllPresetFlags := []
Global RobloxPID := 0
Global BaseAddress := 0
Global HProcess := 0
Global SelectedPreset := ""
Global SelectedModifiedIndex := 0

MyGui := Gui("+Resize", "discord.gg/velostrap")
MyGui.SetFont("s9", "Segoe UI")
MyGui.OnEvent("Close", (*) => ExitApp())

MyGui.Add("Text", "w300", "Available Flags:")
SearchPreset := MyGui.Add("Edit", "w300")
SearchPreset.OnEvent("Change", (ed, *) => RefreshPresetList(ed.Value))

PresetList := MyGui.Add("ListView", "r10 w600 +ReadOnly", ["Flag Name"])
PresetList.OnEvent("Click", OnPresetSelect)

MyGui.Add("Text", "vSelectedFlagText w600", "Selected Flag: None")
ValueInput := MyGui.Add("Edit", "w200 vValueInput")
SetBtn := MyGui.Add("Button", "x+10 Disabled", "Add Flag")
SetBtn.OnEvent("Click", SetValueCallback)

MyGui.Add("Text", "xm w600 h2 0x10") 

MyGui.Add("Text", "xm w300", "Modified Flags:")
SearchModified := MyGui.Add("Edit", "w300")
SearchModified.OnEvent("Change", (ed, *) => RefreshModifiedList(ed.Value))

ModifiedList := MyGui.Add("ListView", "r8 w600 +ReadOnly", ["Flag", "Value", "Type"])
ModifiedList.OnEvent("Click", OnModifiedSelect)

MyGui.Add("Text", "vSelectedModText w600", "None")
UpdateValueInput := MyGui.Add("Edit", "w200")
UpdateBtn := MyGui.Add("Button", "x+10 Disabled", "Update")
UpdateBtn.OnEvent("Click", UpdateValueCallback)

DisableBtn := MyGui.Add("Button", "x+5 Disabled", "Disable/Enable")
DisableBtn.OnEvent("Click", DisableCallback)

RemoveBtn := MyGui.Add("Button", "x+5 Disabled", "Remove")
RemoveBtn.OnEvent("Click", RemoveCallback)

ImportBtn := MyGui.Add("Button", "xm w120 h30", "Import JSON")
ImportBtn.OnEvent("Click", ImportJsonCallback)

RemoveAllBtn := MyGui.Add("Button", "x+10 w120 h30", "Remove All")
RemoveAllBtn.OnEvent("Click", RemoveAllCallback)

ApplyAllBtn := MyGui.Add("Button", "x+10 w100 h30", "Apply All")
ApplyAllBtn.OnEvent("Click", (*) => ApplyFlagsToRoblox())

MyGui.Show()

LoadUserFlags()
SetTimer(MonitorRoblox, 2000)
SetTimer(FetchOffsets, -100)


ImportJsonCallback(*) {
    Global UserFlags
    selectedFile := FileSelect(3, , "Select JSON file to import", "JSON Files (*.json)")
    if (selectedFile = "")
        return

    try {
        jsonContent := FileRead(selectedFile, "UTF-8")
        newFlags := []
        pos := 1
        while RegExMatch(jsonContent, '"([^"]+)":\s*"(.*?)"(?:,|\s*\})', &m, pos) {
            name := m[1]
            val  := m[2]
            typ  := InferType(val)
            newFlags.Push(Map("name", name, "value", val, "type", typ, "original_value", val))
            pos := m.Pos + m.Len
        }
        if (newFlags.Length = 0) {
            MsgBox "No valid key:value pairs found.`nExpected: {`"Flag`":`"Value`", ...}"
            return
        }
        UserFlags := newFlags
        SaveUserFlags()
        RefreshModifiedList()
        RefreshPresetList()
        MsgBox "Imported " newFlags.Length " flags."
    } catch as e {
        MsgBox "Import failed:`n" e.Message
    }
}

RemoveAllCallback(*) {
    Global UserFlags
    if (UserFlags.Length = 0)
        return

    if MsgBox("Remove ALL modified flags? This cannot be undone.", "Confirm", "YesNo Icon?") != "Yes"
        return

    for flag in UserFlags
        ApplySingleFlag(flag["name"], "")

    UserFlags := []
    SaveUserFlags()
    RefreshModifiedList()
    RefreshPresetList()
    ToolTip("All flags removed")
    SetTimer(() => ToolTip(), -3000)
}

MonitorRoblox() {
    Global RobloxPID, BaseAddress, HProcess
    PID := ProcessExist("RobloxPlayerBeta.exe")
    
    if (PID && PID != RobloxPID) {
        if (HProcess)
            DllCall("CloseHandle", "Ptr", HProcess)
        RobloxPID := PID
        HProcess := DllCall("OpenProcess", "UInt", 0x1F0FFF, "Int", 0, "UInt", PID, "Ptr")
        BaseAddress := GetModuleBase(PID, "RobloxPlayerBeta.exe")
        
        if (BaseAddress) {
            ToolTip("Roblox Attached")
            SetTimer(() => ToolTip(), -3000)
        }
    } else if (!PID && RobloxPID) {
        RobloxPID := 0
        BaseAddress := 0
        if (HProcess) {
            DllCall("CloseHandle", "Ptr", HProcess)
            HProcess := 0
        }
        ToolTip("Roblox Disconnected")
        SetTimer(() => ToolTip(), -3000)
    }
}

GetModuleBase(PID, ModuleName) {
    hSnapshot := DllCall("CreateToolhelp32Snapshot", "UInt", 0x00000008, "UInt", PID, "Ptr")
    if (hSnapshot = -1)
        return 0
    ME32 := Buffer(A_PtrSize = 8 ? 1080 : 548, 0)
    NumPut("UInt", ME32.Size, ME32)
    if DllCall("Module32First", "Ptr", hSnapshot, "Ptr", ME32.Ptr) {
        loop {
            if (StrGet(ME32.Ptr + (A_PtrSize = 8 ? 48 : 32), "CP0") = ModuleName) {
                addr := NumGet(ME32.Ptr + (A_PtrSize = 8 ? 24 : 20), "Ptr")
                DllCall("CloseHandle", "Ptr", hSnapshot)
                return addr
            }
        } until !DllCall("Module32Next", "Ptr", hSnapshot, "Ptr", ME32.Ptr)
    }
    DllCall("CloseHandle", "Ptr", hSnapshot)
    return 0
}

FetchOffsets() {
    Global AllOffsets, AllPresetFlags
    try {
        whr := ComObject("WinHttp.WinHttpRequest.5.1")
        whr.Open("GET", "https://imtheo.lol/Offsets/FFlags.hpp", true)
        whr.Send()
        whr.WaitForResponse()
        if (whr.Status != 200)
            throw Error("HTTP " whr.Status)
        content := whr.ResponseText
        if RegExMatch(content, "s)namespace FFlags\s*\{([^}]+)\}", &match) {
            inner := match[1], pos := 1, count := 0
            while RegExMatch(inner, "uintptr_t\s+(\w+)\s*=\s*(0x[0-9A-Fa-f]+);", &m, pos) {
                AllOffsets[m[1]] := Integer(m[2])
                AllPresetFlags.Push(m[1])
                pos := m.Pos + m.Len
                count++
            }
            ToolTip("Loaded " count " flags")
            SetTimer(() => ToolTip(), -4000)
        } else {
            MsgBox("No FFlags namespace found in response.")
        }
        RefreshPresetList()
    } catch as e {
        MsgBox("Failed to load offsets:`n" e.Message)
    }
}

WriteMemory(Address, Value, Type) {
    Global HProcess
    if (!HProcess || !Address)
        return false
    try {
        if (Type = "bool") {
            buf := Buffer(1, 0)
            NumPut("Char", (StrLower(String(Value)) = "true" || Value = "1") ? 1 : 0, buf)
            sz := 1
        } else if (Type = "int") {
            buf := Buffer(4, 0), NumPut("Int", Integer(Value), buf), sz := 4
        } else if (Type = "float") {
            buf := Buffer(8, 0), NumPut("Double", Float(Value), buf), sz := 8
        } else {
            strVal := String(Value), sz := StrPut(strVal, "UTF-8"), buf := Buffer(sz, 0), StrPut(strVal, buf, "UTF-8")
        }
        return DllCall("WriteProcessMemory", "Ptr", HProcess, "Ptr", Address, "Ptr", buf.Ptr, "UInt", sz, "Ptr", 0)
    } catch {
        return false
    }
}

RefreshPresetList(Filter := "") {
    PresetList.Delete()
    PresetList.Opt("-Redraw")
    for name in AllPresetFlags {
        if (Filter != "" && !InStr(name, Filter, false))
            continue
        is_mod := false
        for f in UserFlags {
            if (f["name"] = name) {
                is_mod := true
                break
            }
        }
        if (!is_mod)
            PresetList.Add(, name)
    }
    PresetList.Opt("+Redraw")
}

RefreshModifiedList(Filter := "") {
    ModifiedList.Delete()
    for flag in UserFlags {
        if (Filter != "" && !InStr(flag["name"], Filter, false))
            continue
        ModifiedList.Add(, flag["name"], flag["value"], flag["type"])
    }
}

OnPresetSelect(LV, Row) {
    Global SelectedPreset
    if (Row) {
        SelectedPreset := LV.GetText(Row)
        MyGui["SelectedFlagText"].Value := "Selected: " SelectedPreset
        SetBtn.Enabled := true
    }
}

SetValueCallback(*) {
    val := ValueInput.Value
    if (SelectedPreset = "" || val = "")
        return
    UserFlags.Push(Map("name", SelectedPreset, "value", val, "type", InferType(val), "original_value", val))
    SaveUserFlags()
    RefreshModifiedList()
    RefreshPresetList(SearchPreset.Value)
}

OnModifiedSelect(LV, Row) {
    Global SelectedModifiedIndex
    if (Row) {
        SelectedModifiedIndex := Row
        flag := UserFlags[Row]
        MyGui["SelectedModText"].Value := flag["name"] ": " flag["value"]
        UpdateValueInput.Value := flag["value"]
        UpdateBtn.Enabled := true
        RemoveBtn.Enabled := true
        DisableBtn.Enabled := true
    }
}

UpdateValueCallback(*) {
    if (!SelectedModifiedIndex)
        return
    new_val := UpdateValueInput.Value
    UserFlags[SelectedModifiedIndex]["value"] := new_val
    UserFlags[SelectedModifiedIndex]["type"] := InferType(new_val)
    ApplySingleFlag(UserFlags[SelectedModifiedIndex]["name"], new_val)
    SaveUserFlags()
    RefreshModifiedList()
}

ApplySingleFlag(Name, Value) {
    Global BaseAddress, AllOffsets
    if (!BaseAddress || !AllOffsets.Has(Name))
        return false
    return WriteMemory(BaseAddress + AllOffsets[Name], Value, InferType(Value))
}

ApplyFlagsToRoblox() {
    success := 0
    for flag in UserFlags {
        if (ApplySingleFlag(flag["name"], flag["value"]))
            success++
    }
    ToolTip("Applied " success " flags")
    SetTimer(() => ToolTip(), -3000)
}

RemoveCallback(*) {
    if (!SelectedModifiedIndex)
        return
    ApplySingleFlag(UserFlags[SelectedModifiedIndex]["name"], "")
    UserFlags.RemoveAt(SelectedModifiedIndex)
    SaveUserFlags()
    RefreshModifiedList()
    RefreshPresetList(SearchPreset.Value)
}

DisableCallback(*) {
    if (!SelectedModifiedIndex)
        return
    flag := UserFlags[SelectedModifiedIndex]
    flag["value"] := (flag["value"] == "" ? (flag.Has("original_value") ? flag["original_value"] : "True") : "")
    ApplySingleFlag(flag["name"], flag["value"])
    SaveUserFlags()
    RefreshModifiedList()
}

InferType(Value) {
    v := StrLower(Trim(String(Value)))
    if (v = "true" || v = "false")
        return "bool"
    if IsNumber(v)
        return InStr(v, ".") ? "float" : "int"
    return "string"
}

SaveUserFlags() {
    str := "["
    for f in UserFlags {
        str .= '{"name":"' f["name"] '","value":"' f["value"] '","type":"' f["type"] '"},'
    }
    str := RTrim(str, ",") "]"
    try FileOpen(USER_FLAGS_FILE, "w", "UTF-8").Write(str)
}

LoadUserFlags() {
    if !FileExist(USER_FLAGS_FILE)
        return
    try {
        content := FileRead(USER_FLAGS_FILE, "UTF-8")
        pos := 1
        while RegExMatch(content, '\{"name":"([^"]+)","value":"([^"]*)","type":"([^"]+)"\}', &m, pos) {
            UserFlags.Push(Map("name", m[1], "value", m[2], "type", m[3], "original_value", m[2]))
            pos := m.Pos + m.Len
        }
        RefreshModifiedList()
    }
}