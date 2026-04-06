

#Requires AutoHotkey v2.0
#SingleInstance Force


global mem := 0
global baseAddr := 0
global dataModel := 0
global workspace := 0
global camera := 0
global players := 0
global localPlayer := 0
global visualEngine := 0
global matrixAddr := 0
global camRotAddr := 0
global camPosAddr := 0
global character := 0
global humanoid := 0

global currentTarget := 0
global currentTargetPrim := 0
global aimbotKey := "e"
global aimbotToggleMode := false
global aimbotToggleState := false
global fovRadius := 300
global stickyAim := true
global predictionEnabled := true
global predictionX := 13.0
global predictionY := 13.0
global mainGui := 0
global smoothnessEnabled := false
global smoothnessValue := 50
global targetPart := "Head"
global targetPartDropdown := 0
global smoothnessCheck := 0
global smoothnessSlider := 0
global keyBg := 0
global smoothnessText := 0
global statusText := 0
global debugText := 0
global fovText := 0
global predXSlider := 0
global predYSlider := 0
global predXText := 0
global predYText := 0
global fovSlider := 0


global walkspeedEnabled := false
global walkspeedValue := 16
global jumpPowerEnabled := false
global jumpPowerValue := 50


global espSettings := Map(
    "enabled", false,
    "box", true,
    "dot", false,
    "health", false,
    "fov", false,
    "skeleton", false,
    "fovRadius", 100,
    "colBox", 0xFFFFFFFF,
    "colDot", 0xFFFF3C3C,
    "colSkel", 0xFFFFC800,
    "colFov", 0xC8FFFFFF
)
global overlayGui := 0
global overlayHwnd := 0
global gdipToken := 0
global screenWidth := 0
global screenHeight := 0
global espActive := false
global lastFrameTime := 0
global frameCount := 0
global currentFPS := 0
global fpsUpdateTime := 0
global gDC := 0
global gMemDC := 0
global gBitmap := 0
global gGraphics := 0
global gPenBox := 0
global gPenSkel := 0
global gPenFov := 0
global gBrushDot := 0
global gBrushHealthBg := 0
global gBrushClear := 0
global gBrushHealth := 0


global TTL_GEN := 300
global TTL_PLAYER := 500
global TTL_TEAM := 1000
global TTL_MAXHP := 5000
global TTL_CHAR := 150

global R15_PARTS := ["Head", "UpperTorso", "LowerTorso",
                     "LeftUpperArm", "LeftLowerArm", "LeftHand",
                     "RightUpperArm", "RightLowerArm", "RightHand",
                     "LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
                     "RightUpperLeg", "RightLowerLeg", "RightFoot"]
global R6_PARTS := ["Head", "Torso", "Left Arm", "Right Arm", "Left Leg", "Right Leg"]
global R15_MIN := ["Head", "LowerTorso", "LeftHand", "RightHand", "LeftFoot", "RightFoot"]
global R15_BONES := [
    ["Head", "UpperTorso"], ["UpperTorso", "LowerTorso"],
    ["UpperTorso", "LeftUpperArm"], ["LeftUpperArm", "LeftLowerArm"], ["LeftLowerArm", "LeftHand"],
    ["UpperTorso", "RightUpperArm"], ["RightUpperArm", "RightLowerArm"], ["RightLowerArm", "RightHand"],
    ["LowerTorso", "LeftUpperLeg"], ["LeftUpperLeg", "LeftLowerLeg"], ["LeftLowerLeg", "LeftFoot"],
    ["LowerTorso", "RightUpperLeg"], ["RightUpperLeg", "RightLowerLeg"], ["RightLowerLeg", "RightFoot"]
]
global R6_BONES := [
    ["Head", "Torso"],
    ["Torso", "Left Arm"], ["Torso", "Right Arm"],
    ["Torso", "Left Leg"], ["Torso", "Right Leg"]
]


global cacheNames := Map()
global cacheClassNames := Map()
global cacheChildren := Map()
global cacheCharacter := Map()
global cacheHumanoid := Map()
global cacheMaxHP := Map()
global cachePrimitive := Map()
global cacheTeam := Map()
global cacheCharData := Map()
global localPlayerCache := {ptr: 0, time: 0}
global playerListCache := {list: [], time: 0}


global curPosBuffer := Buffer(8, 0)


global espEnableCheck := 0
global espBoxCheck := 0
global espDotCheck := 0
global espHealthCheck := 0
global espSkelCheck := 0
global espFovCheck := 0
global espFovSlider := 0
global espFovText := 0
global espStatusText := 0
global espPreviewPic := 0


class Offsets {
    static VisualEnginePtr := 0x7EF81D8        ; VisualEngine::Pointer
    static FakeDataModelPtr := 0x834A988       ; FakeDataModel::Pointer
    static RealDataModel := 0x1C0              ; FakeDataModel::RealDataModel (was 0x448)
    static ChildrenStart := 0x78               ; Instance::ChildrenStart
    static ChildrenEnd := 0x8                  ; Instance::ChildrenEnd
    static Name := 0xB0                        ; Instance::Name (was 0x176)
    static ClassDescriptor := 0x18             ; Instance::ClassDescriptor
    static ClassName := 0x8                    ; Instance::ClassName
    static Workspace := 0x178                  ; DataModel::Workspace (was 0x1160)
    static CurrentCamera := 0x488              ; Workspace::CurrentCamera (was 0x48)
    static LocalPlayer := 0x130                ; Player::LocalPlayer
    static ModelInstance := 0x398              ; Player::ModelInstance
    static Position := 0x11C                   ; Camera::Position (was 0x228)
    static Rotation := 0xF8                    ; Camera::Rotation (was 0x192)
    static ViewMatrix := 0x130                 ; VisualEngine::ViewMatrix (was 0x304)
    static Primitive := 0x148                  ; BasePart::Primitive
    static PrimitivePosition := 0xE4           ; Primitive::Position
    static AssemblyLinearVelocity := 0xF0      ; Primitive::AssemblyLinearVelocity
    static Health := 0x194                     ; Humanoid::Health
    static MaxHealth := 0x1B4                  ; Humanoid::MaxHealth
    static Team := 0x2A0                       ; Player::Team
    static Humanoid := 0x4c0                   ; rlly useless
    static WalkSpeed := 0x1D4                  ; Humanoid::Walkspeed
    static JumpPower := 0x1B0                  ; Humanoid::JumpPower
}


class Memory {
    __New(procName) {
        this.pid := ProcessExist(procName)
        if !this.pid
            throw Error("Process not found")
        this.h := DllCall("OpenProcess", "UInt", 0x1F0FFF, "Int", 0, "UInt", this.pid, "Ptr")
        if !this.h
            throw Error("OpenProcess failed")
        this.baseAddr := this.GetModuleBase()
    }

    GetModuleBase() {
        TH32CS_SNAPMODULE := 0x00000008
        snap := DllCall("CreateToolhelp32Snapshot", "UInt", TH32CS_SNAPMODULE, "UInt", this.pid, "Ptr")
        if snap = -1
            return 0
        me32 := Buffer(1080, 0)
        NumPut("UInt", 1080, me32, 0)
        if !DllCall("Module32FirstW", "Ptr", snap, "Ptr", me32) {
            DllCall("CloseHandle", "Ptr", snap)
            return 0
        }
        base := NumGet(me32, 0x18, "Ptr")
        DllCall("CloseHandle", "Ptr", snap)
        return base
    }

    Read(addr, type := "UInt64") {
        if addr <= 0
            return 0
        size := (type = "Float" || type = "UInt" || type = "Int") ? 4 : 8
        buf := Buffer(size, 0)
        DllCall("ntdll\NtReadVirtualMemory", "Ptr", this.h, "Ptr", addr, "Ptr", buf, "UPtr", size, "UPtr*", 0, "UInt")
        return NumGet(buf, 0, type)
    }

    Write(addr, value, type := "Float") {
        if addr <= 0
            return
        size := (type = "Float" || type = "UInt" || type = "Int") ? 4 : 8
        buf := Buffer(size, 0)
        NumPut(type, value, buf, 0)
        DllCall("ntdll\NtWriteVirtualMemory", "Ptr", this.h, "Ptr", addr, "Ptr", buf, "UPtr", size, "UPtr*", 0, "UInt")
    }

    ReadMatrix(addr) {
        m := []
        loop 16
            m.Push(this.Read(addr + (A_Index-1)*4, "Float"))
        return m
    }

    ReadString(addr) {
        len := this.Read(addr + 0x10, "Int")
        if len <= 0 || len > 10000
            return ""
        if len >= 16
            addr := this.Read(addr, "UInt64")
        if addr <= 0
            return ""
        buf := Buffer(len + 1, 0)
        DllCall("ntdll\NtReadVirtualMemory", "Ptr", this.h, "Ptr", addr, "Ptr", buf, "Ptr", len, "Ptr", 0)
        return StrGet(buf, "UTF-8")
    }

    WriteFloat(addr, value) {
        if addr <= 0
            return
        buf := Buffer(4)
        NumPut("Float", value, buf, 0)
        DllCall("ntdll\NtWriteVirtualMemory", "Ptr", this.h, "Ptr", addr, "Ptr", buf, "UPtr", 4, "UPtr*", 0, "UInt")
    }
}


class robloxfuckass {
    static GetChildren(inst) {
        global mem, cacheChildren, TTL_GEN
        if !inst
            return []
        now := A_TickCount
        if cacheChildren.Has(inst) {
            cached := cacheChildren[inst]
            if (now - cached.time) < TTL_GEN
                return cached.value
        }
        out := []
        ptr := mem.Read(inst + Offsets.ChildrenStart, "UInt64")
        if !ptr
            return out
        start := mem.Read(ptr, "UInt64")
        endPtr := mem.Read(ptr + 8, "UInt64")
        if !start || !endPtr
            return out
        cur := start
        loop 1000 {
            if cur >= endPtr
                break
            child := mem.Read(cur, "UInt64")
            if child && child != inst
                out.Push(child)
            cur += 0x10
        }
        cacheChildren[inst] := {value: out, time: now}
        return out
    }

    static FindChild(inst, name) {
        for child in this.GetChildren(inst)
            if this.GetName(child) = name
                return child
        return 0
    }

    static FindChildOfClass(inst, className) {
        for child in this.GetChildren(inst)
            if this.GetClassName(child) = className
                return child
        return 0
    }

    static GetName(inst) {
        global mem, cacheNames, TTL_GEN
        if !inst
            return ""
        now := A_TickCount
        if cacheNames.Has(inst) {
            cached := cacheNames[inst]
            if (now - cached.time) < TTL_GEN
                return cached.value
        }
        namePtr := mem.Read(inst + Offsets.Name, "UInt64")
        result := namePtr ? mem.ReadString(namePtr) : ""
        cacheNames[inst] := {value: result, time: now}
        return result
    }

    static GetClassName(inst) {
        global mem, cacheClassNames, TTL_GEN
        if !inst
            return ""
        now := A_TickCount
        if cacheClassNames.Has(inst) {
            cached := cacheClassNames[inst]
            if (now - cached.time) < TTL_GEN
                return cached.value
        }
        desc := mem.Read(inst + Offsets.ClassDescriptor, "UInt64")
        if !desc
            return ""
        classNamePtr := mem.Read(desc + Offsets.ClassName, "UInt64")
        result := classNamePtr ? mem.ReadString(classNamePtr) : ""
        cacheClassNames[inst] := {value: result, time: now}
        return result
    }
}


class Vector3 {
    __New(x := 0, y := 0, z := 0) {
        this.x := x
        this.y := y
        this.z := z
    }
    Subtract(o) => Vector3(this.x - o.x, this.y - o.y, this.z - o.z)
    Negate() => Vector3(-this.x, -this.y, -this.z)
    Magnitude() => Sqrt(this.x*this.x + this.y*this.y + this.z*this.z)
    Normalize() {
        mag := this.Magnitude()
        if mag < 0.000001
            return Vector3(0, 0, 0)
        return Vector3(this.x/mag, this.y/mag, this.z/mag)
    }
    Cross(o) => Vector3(
        this.y * o.z - this.z * o.y,
        this.z * o.x - this.x * o.z,
        this.x * o.y - this.y * o.x
    )
}

class Matrix3 {
    __New(d0:=1, d1:=0, d2:=0, d3:=0, d4:=1, d5:=0, d6:=0, d7:=0, d8:=1) {
        this.data := [d0, d1, d2, d3, d4, d5, d6, d7, d8]
    }
}

LookAtToMatrix(cameraPos, targetPos) {
    forward := targetPos.Subtract(cameraPos).Normalize()
    back := forward.Negate()
    worldUp := Vector3(0, 1, 0)
    right := worldUp.Cross(back).Normalize()
    up := back.Cross(right).Normalize()
    return Matrix3(
        right.x, up.x, back.x,
        right.y, up.y, back.y,
        right.z, up.z, back.z
    )
}

WorldToScreen(worldPos, matrix, sw, sh) {
    x := worldPos.x, y := worldPos.y, z := worldPos.z
    clipX := matrix[1]*x + matrix[2]*y + matrix[3]*z + matrix[4]
    clipY := matrix[5]*x + matrix[6]*y + matrix[7]*z + matrix[8]
    clipZ := matrix[9]*x + matrix[10]*y + matrix[11]*z + matrix[12]
    clipW := matrix[13]*x + matrix[14]*y + matrix[15]*z + matrix[16]
    if clipW <= 0.001
        return 0
    ndcX := clipX / clipW
    ndcY := clipY / clipW
    ndcZ := clipZ / clipW
    if ndcZ < 0 || ndcZ > 1
        return 0
    sx := (ndcX + 1) * 0.5 * sw
    sy := (1 - ndcY) * 0.5 * sh
    if sx < 0 || sx > sw || sy < 0 || sy > sh
        return 0
    return {x: Round(sx), y: Round(sy)}
}


GetRobloxWindowRect() {
    hwnd := WinExist("ahk_exe RobloxPlayerBeta.exe")
    if !hwnd
        return 0
    try {
        DllCall("GetClientRect", "Ptr", hwnd, "Ptr", rect := Buffer(16, 0))
        return {
            hwnd: hwnd,
            left: NumGet(rect, 0, "Int"),
            top: NumGet(rect, 4, "Int"),
            right: NumGet(rect, 8, "Int"),
            bottom: NumGet(rect, 12, "Int"),
            width: NumGet(rect, 8, "Int"),
            height: NumGet(rect, 12, "Int")
        }
    }
    return 0
}

GetCursorInWindow(hwnd) {
    pt := Buffer(8, 0)
    if !DllCall("GetCursorPos", "Ptr", pt)
        return 0
    if !DllCall("ScreenToClient", "Ptr", hwnd, "Ptr", pt)
        return 0
    return {x: NumGet(pt, 0, "Int"), y: NumGet(pt, 4, "Int")}
}


GetTargetPrimitive(player) {
    global mem, targetPart
    if !player
        return 0
    try {
        char := mem.Read(player + Offsets.ModelInstance, "UInt64")
        if !char
            return 0
        target := robloxfuckass.FindChild(char, targetPart)
        if !target
            return 0
        prim := mem.Read(target + Offsets.Primitive, "UInt64")
        return prim
    }
    return 0
}

ReadPredictedPosition(primAddr) {
    global mem, predictionEnabled, predictionX, predictionY
    if primAddr {
        posAddr := primAddr + Offsets.PrimitivePosition
        x := mem.Read(posAddr, "Float")
        y := mem.Read(posAddr + 4, "Float")
        z := mem.Read(posAddr + 8, "Float")
        if Abs(x) > 1e6
            return Vector3(0, 0, 0)
        if predictionEnabled {
            velAddr := primAddr + Offsets.AssemblyLinearVelocity
            vx := mem.Read(velAddr, "Float")
            vy := mem.Read(velAddr + 4, "Float")
            vz := mem.Read(velAddr + 8, "Float")
            x += vx * (predictionX / 100.0)
            y += vy * (predictionY / 100.0)
            z += vz * (predictionX / 100.0)
        }
        return Vector3(x, y, z)
    }
    return Vector3(0, 0, 0)
}

FindClosestTargetFromCursor() {
    global players, localPlayer, matrixAddr, currentTarget, stickyAim, fovRadius, debugText, mem, currentTargetPrim
    win := GetRobloxWindowRect()
    if !win
        return 0
    cursorPos := GetCursorInWindow(win.hwnd)
    if !cursorPos
        return 0
    matrix := mem.ReadMatrix(matrixAddr)
    if stickyAim && currentTarget != 0 {
        prim := GetTargetPrimitive(currentTarget)
        if prim {
            targetPos := ReadPredictedPosition(prim)
            if targetPos.Magnitude() > 0 {
                screen := WorldToScreen(targetPos, matrix, win.width, win.height)
                if screen {
                    dist := Sqrt((cursorPos.x - screen.x)**2 + (cursorPos.y - screen.y)**2)
                    if dist <= (fovRadius * 1.5) {
                        currentTargetPrim := prim
                        return prim
                    }
                }
            }
        }
        currentTarget := 0
        currentTargetPrim := 0
    }
    shortestDistance := 999999999
    bestPrim := 0
    bestPlayer := 0
    playerCount := 0
    validCount := 0
    fovCount := 0
    localTeam := mem.Read(localPlayer + Offsets.Team, "UInt64")
    for p in robloxfuckass.GetChildren(players) {
        playerCount++
        if robloxfuckass.GetClassName(p) != "Player"
            continue
        if p = localPlayer
            continue
        playerTeam := mem.Read(p + Offsets.Team, "UInt64")
        if playerTeam = localTeam && localTeam != 0
            continue
        prim := GetTargetPrimitive(p)
        if !prim
            continue
        validCount++
        targetPos := ReadPredictedPosition(prim)
        if targetPos.Magnitude() = 0
            continue
        screen := WorldToScreen(targetPos, matrix, win.width, win.height)
        if !screen
            continue
        cursorDist := Sqrt((screen.x - cursorPos.x)**2 + (screen.y - cursorPos.y)**2)
        if cursorDist > fovRadius
            continue
        fovCount++
        if cursorDist < shortestDistance {
            shortestDistance := cursorDist
            bestPrim := prim
            bestPlayer := p
        }
    }
    if debugText
        debugText.Value := "Players: " playerCount " | Valid: " validCount " | In FOV: " fovCount " | Dist: " Round(shortestDistance)
    if bestPrim != 0 {
        currentTarget := bestPlayer
        currentTargetPrim := bestPrim
    }
    return bestPrim
}

AimAtTarget(primAddr) {
    global camRotAddr, camPosAddr, mem, smoothnessEnabled, smoothnessValue
    if !primAddr
        return
    try {
        targetPos := ReadPredictedPosition(primAddr)
        if targetPos.Magnitude() = 0
            return
        cx := mem.Read(camPosAddr, "Float")
        cy := mem.Read(camPosAddr + 4, "Float")
        cz := mem.Read(camPosAddr + 8, "Float")
        if Abs(cx) > 1e6
            return
        cameraPos := Vector3(cx, cy, cz)

        if smoothnessEnabled {
            ; Read current rotation
            currentRot := []
            loop 9
                currentRot.Push(mem.Read(camRotAddr + (A_Index-1)*4, "Float"))

            ; Calculate target rotation
            targetMatrix := LookAtToMatrix(cameraPos, targetPos)

            ; Smooth interpolation
            smoothFactor := smoothnessValue / 100.0
            loop 9 {
                newValue := currentRot[A_Index] + (targetMatrix.data[A_Index] - currentRot[A_Index]) * smoothFactor
                mem.WriteFloat(camRotAddr + (A_Index-1)*4, newValue)
            }
        } else {
            rotationMatrix := LookAtToMatrix(cameraPos, targetPos)
            mem.WriteFloat(camRotAddr, rotationMatrix.data[1])
            mem.WriteFloat(camRotAddr + 4, rotationMatrix.data[2])
            mem.WriteFloat(camRotAddr + 8, rotationMatrix.data[3])
            mem.WriteFloat(camRotAddr + 12, rotationMatrix.data[4])
            mem.WriteFloat(camRotAddr + 16, rotationMatrix.data[5])
            mem.WriteFloat(camRotAddr + 20, rotationMatrix.data[6])
            mem.WriteFloat(camRotAddr + 24, rotationMatrix.data[7])
            mem.WriteFloat(camRotAddr + 28, rotationMatrix.data[8])
            mem.WriteFloat(camRotAddr + 32, rotationMatrix.data[9])
        }
    } catch {
        return
    }
}

AimbotLoop() {
    static lastUpdate := 0
    static lastKeyState := false
    global currentTargetPrim, currentTarget, aimbotKey, aimbotToggleMode, aimbotToggleState

    if aimbotToggleMode {
        curKeyState := GetKeyState(aimbotKey, "P")
        if curKeyState && !lastKeyState
            aimbotToggleState := !aimbotToggleState
        lastKeyState := curKeyState
        if !aimbotToggleState {
            currentTargetPrim := 0
            currentTarget := 0
            return
        }
    } else {
        if !GetKeyState(aimbotKey, "P") {
            currentTargetPrim := 0
            currentTarget := 0
            return
        }
    }
    win := GetRobloxWindowRect()
    if !win
        return
    if !WinActive("ahk_id " win.hwnd)
        return
    if A_TickCount - lastUpdate > 50 {
        currentTargetPrim := FindClosestTargetFromCursor()
        lastUpdate := A_TickCount
    }
    if currentTargetPrim
        AimAtTarget(currentTargetPrim)
}

MiscLoop() {
    global humanoid, walkspeedEnabled, walkspeedValue, jumpPowerEnabled, jumpPowerValue, mem
    if !humanoid
        return
    try {
        if walkspeedEnabled {
            wsAddr := humanoid + Offsets.WalkSpeed
            mem.Write(wsAddr, walkspeedValue, "Float")
        }
        if jumpPowerEnabled {
            jpAddr := humanoid + Offsets.JumpPower
            mem.Write(jpAddr, jumpPowerValue, "Float")
        }
    }
}


GetLocalPlayerCached() {
    global players, mem, localPlayerCache, TTL_PLAYER
    now := A_TickCount
    if (now - localPlayerCache.time) < TTL_PLAYER
        return localPlayerCache.ptr
    ptr := mem.Read(players + Offsets.LocalPlayer, "UInt64")
    localPlayerCache.ptr := ptr
    localPlayerCache.time := now
    return ptr
}

GetTeamCached(playerInst) {
    global mem, cacheTeam, TTL_TEAM
    if !playerInst
        return 0
    now := A_TickCount
    if cacheTeam.Has(playerInst) {
        cached := cacheTeam[playerInst]
        if (now - cached.time) < TTL_TEAM
            return cached.value
    }
    team := mem.Read(playerInst + Offsets.Team, "UInt64")
    cacheTeam[playerInst] := {value: team, time: now}
    return team
}

GetCharacterCached(playerInst) {
    global mem, cacheCharacter, TTL_CHAR
    if !playerInst
        return 0
    now := A_TickCount
    if cacheCharacter.Has(playerInst) {
        cached := cacheCharacter[playerInst]
        if (now - cached.time) < TTL_CHAR
            return cached.value
    }
    char := mem.Read(playerInst + Offsets.ModelInstance, "UInt64")
    cacheCharacter[playerInst] := {value: char, time: now}
    return char
}

GetHumanoidCached(charInst) {
    global cacheHumanoid, TTL_GEN
    if !charInst
        return 0
    now := A_TickCount
    if cacheHumanoid.Has(charInst) {
        cached := cacheHumanoid[charInst]
        if (now - cached.time) < TTL_GEN
            return cached.value
    }
    hum := robloxfuckass.FindChildOfClass(charInst, "Humanoid")
    cacheHumanoid[charInst] := {value: hum, time: now}
    return hum
}

GetMaxHealthCached(humInst) {
    global mem, cacheMaxHP, TTL_MAXHP
    if !humInst
        return 100
    now := A_TickCount
    if cacheMaxHP.Has(humInst) {
        cached := cacheMaxHP[humInst]
        if (now - cached.time) < TTL_MAXHP
            return cached.value
    }
    maxhp := mem.Read(humInst + Offsets.MaxHealth, "Float")
    if maxhp <= 0
        maxhp := 100
    cacheMaxHP[humInst] := {value: maxhp, time: now}
    return maxhp
}

GetPrimitiveCached(partInst) {
    global mem, cachePrimitive, TTL_GEN
    if !partInst
        return 0
    now := A_TickCount
    if cachePrimitive.Has(partInst) {
        cached := cachePrimitive[partInst]
        if (now - cached.time) < TTL_GEN
            return cached.value
    }
    prim := mem.Read(partInst + Offsets.Primitive, "UInt64")
    cachePrimitive[partInst] := {value: prim, time: now}
    return prim
}

GetPositionCached(partInst) {
    global mem
    if !partInst
        return 0
    prim := GetPrimitiveCached(partInst)
    if !prim
        return 0
    posAddr := prim + Offsets.PrimitivePosition
    x := mem.Read(posAddr, "Float")
    y := mem.Read(posAddr + 4, "Float")
    z := mem.Read(posAddr + 8, "Float")
    if Abs(x) > 1e6
        return 0
    return Vector3(x, y, z)
}

GetCharacterDataCached(charInst) {
    global mem, cacheCharData, TTL_CHAR, espSettings
    if !charInst
        return 0
    now := A_TickCount
    if cacheCharData.Has(charInst) {
        cached := cacheCharData[charInst]
        if (now - cached.time) < TTL_CHAR
            return cached.value
    }
    hum := GetHumanoidCached(charInst)
    if !hum
        return 0
    isR15 := false
    parts := Map()
    children := robloxfuckass.GetChildren(charInst)
    for child in children {
        name := robloxfuckass.GetName(child)
        if name = "UpperTorso" {
            isR15 := true
            break
        }
    }
    partsList := isR15 ? (espSettings["skeleton"] ? R15_PARTS : R15_MIN) : R6_PARTS
    for child in children {
        name := robloxfuckass.GetName(child)
        for partName in partsList {
            if name = partName {
                parts[name] := child
                break
            }
        }
    }
    if parts.Count < 2
        return 0
    maxhp := GetMaxHealthCached(hum)
    data := Map(
        "hum", hum,
        "mhp", maxhp,
        "r15", isR15,
        "parts", parts
    )
    cacheCharData[charInst] := {value: data, time: now}
    return data
}


InitGDI() {
    global gdipToken
    si := Buffer(24, 0)
    NumPut("UInt", 1, si, 0)
    DllCall("gdiplus\GdiplusStartup", "Ptr*", &gdipToken, "Ptr", si, "Ptr", 0)
}

ShutdownGDI() {
    global gdipToken, gDC, gMemDC, gBitmap, gGraphics, overlayGui, overlayHwnd
    global gPenBox, gPenSkel, gPenFov, gBrushDot, gBrushHealthBg, gBrushClear, gBrushHealth
    if gGraphics {
        DllCall("gdiplus\GdipDeleteGraphics", "Ptr", gGraphics)
        gGraphics := 0
    }
    if gPenBox
        DllCall("gdiplus\GdipDeletePen", "Ptr", gPenBox)
    if gPenSkel
        DllCall("gdiplus\GdipDeletePen", "Ptr", gPenSkel)
    if gPenFov
        DllCall("gdiplus\GdipDeletePen", "Ptr", gPenFov)
    if gBrushDot
        DllCall("gdiplus\GdipDeleteBrush", "Ptr", gBrushDot)
    if gBrushHealthBg
        DllCall("gdiplus\GdipDeleteBrush", "Ptr", gBrushHealthBg)
    if gBrushClear
        DllCall("gdiplus\GdipDeleteBrush", "Ptr", gBrushClear)
    if gBrushHealth
        DllCall("gdiplus\GdipDeleteBrush", "Ptr", gBrushHealth)
    if gBitmap {
        DllCall("DeleteObject", "Ptr", gBitmap)
        gBitmap := 0
    }
    if gMemDC {
        DllCall("DeleteDC", "Ptr", gMemDC)
        gMemDC := 0
    }
    if gDC {
        DllCall("ReleaseDC", "Ptr", overlayHwnd, "Ptr", gDC)
        gDC := 0
    }
    if gdipToken
        DllCall("gdiplus\GdiplusShutdown", "Ptr", gdipToken)
}

CreateOverlay() {
    global overlayGui, overlayHwnd, screenWidth, screenHeight
    screenWidth := A_ScreenWidth
    screenHeight := A_ScreenHeight
    overlayGui := Gui("-Caption +E0x80000 +LastFound +AlwaysOnTop +ToolWindow +OwnDialogs")
    overlayGui.BackColor := "0x000000"
    overlayGui.Show("NA x0 y0 w" screenWidth " h" screenHeight)
    overlayHwnd := overlayGui.Hwnd
    WinSetTransColor("0x000000", overlayHwnd)
    exStyle := DllCall("GetWindowLong", "Ptr", overlayHwnd, "Int", -20, "Int")
    exStyle |= 0x80000 | 0x20
    DllCall("SetWindowLong", "Ptr", overlayHwnd, "Int", -20, "Int", exStyle)
}

InitPersistentGraphics() {
    global overlayHwnd, screenWidth, screenHeight, gDC, gMemDC, gBitmap, gGraphics
    global gPenBox, gPenSkel, gPenFov, gBrushDot, gBrushHealthBg, gBrushClear
    global espSettings
    gDC := DllCall("GetDC", "Ptr", overlayHwnd, "Ptr")
    gMemDC := DllCall("CreateCompatibleDC", "Ptr", gDC, "Ptr")
    gBitmap := DllCall("CreateCompatibleBitmap", "Ptr", gDC, "Int", screenWidth, "Int", screenHeight, "Ptr")
    DllCall("SelectObject", "Ptr", gMemDC, "Ptr", gBitmap, "Ptr")
    DllCall("gdiplus\GdipCreateFromHDC", "Ptr", gMemDC, "Ptr*", &gGraphics)
    DllCall("gdiplus\GdipSetCompositingMode", "Ptr", gGraphics, "Int", 1)
    DllCall("gdiplus\GdipSetCompositingQuality", "Ptr", gGraphics, "Int", 1)
    DllCall("gdiplus\GdipSetSmoothingMode", "Ptr", gGraphics, "Int", 3)
    DllCall("gdiplus\GdipSetPixelOffsetMode", "Ptr", gGraphics, "Int", 3)
    DllCall("gdiplus\GdipSetInterpolationMode", "Ptr", gGraphics, "Int", 5)
    DllCall("gdiplus\GdipSetTextRenderingHint", "Ptr", gGraphics, "Int", 3)
    DllCall("gdiplus\GdipCreatePen1", "UInt", espSettings["colBox"], "Float", 1.2, "Int", 2, "Ptr*", &gPenBox)
    DllCall("gdiplus\GdipCreatePen1", "UInt", espSettings["colSkel"], "Float", 1.5, "Int", 2, "Ptr*", &gPenSkel)
    DllCall("gdiplus\GdipCreatePen1", "UInt", espSettings["colFov"], "Float", 1.2, "Int", 2, "Ptr*", &gPenFov)
    DllCall("gdiplus\GdipCreateSolidFill", "UInt", espSettings["colDot"], "Ptr*", &gBrushDot)
    DllCall("gdiplus\GdipCreateSolidFill", "UInt", 0xFF1a1a1a, "Ptr*", &gBrushHealthBg)
    DllCall("gdiplus\GdipCreateSolidFill", "UInt", 0x00000000, "Ptr*", &gBrushClear)
}

RenderESP() {
    global espActive, mem, players, matrixAddr, screenWidth, screenHeight
    global playerListCache, TTL_PLAYER, lastFrameTime, frameCount, currentFPS, debugText, fpsUpdateTime
    global gDC, gMemDC, gGraphics, gPenBox, gPenSkel, gPenFov, gBrushDot, gBrushHealthBg
    global curPosBuffer, espSettings, gBrushHealth

    if !espActive
        return


    currentTime := A_TickCount
    if lastFrameTime > 0 {
        deltaTime := currentTime - lastFrameTime
        if deltaTime > 0
            currentFPS := Round(1000 / deltaTime)
        frameCount++
        if currentTime - fpsUpdateTime > 500 {
            if debugText
                debugText.Value := "ESP FPS: " currentFPS
            fpsUpdateTime := currentTime
            frameCount := 0
        }
    }
    lastFrameTime := currentTime


    DllCall("gdiplus\GdipGraphicsClear", "Ptr", gGraphics, "UInt", 0x00000000)

    matrix := mem.ReadMatrix(matrixAddr)
    lp := GetLocalPlayerCached()
    lt := GetTeamCached(lp)


    DllCall("GetCursorPos", "Ptr", curPosBuffer)
    cursorX := NumGet(curPosBuffer, 0, "Int")
    cursorY := NumGet(curPosBuffer, 4, "Int")

    if espSettings["fov"] {
        rad := espSettings["fovRadius"]
        DllCall("gdiplus\GdipDrawEllipse", "Ptr", gGraphics, "Ptr", gPenFov,
                "Float", cursorX - rad, "Float", cursorY - rad,
                "Float", rad * 2, "Float", rad * 2)
    }


    now := A_TickCount
    if (now - playerListCache.time) > TTL_PLAYER {
        playerListCache.list := robloxfuckass.GetChildren(players)
        playerListCache.time := now
    }

    for player in playerListCache.list {
        if player = lp
            continue
        if lt && GetTeamCached(player) = lt
            continue

        char := GetCharacterCached(player)
        if !char
            continue

        cd := GetCharacterDataCached(char)
        if !cd
            continue

        chp := mem.Read(cd["hum"] + Offsets.Health, "Float")
        if chp <= 0
            continue

        screenParts := Map()
        minX := 1e9, maxX := -1e9
        minY := 1e9, maxY := -1e9

        for partName, partInst in cd["parts"] {
            pos3d := GetPositionCached(partInst)
            if !pos3d
                continue
            screen := WorldToScreen(pos3d, matrix, screenWidth, screenHeight)
            if !screen
                continue
            screenParts[partName] := screen
            if screen.x < minX
                minX := screen.x
            if screen.x > maxX
                maxX := screen.x
            if screen.y < minY
                minY := screen.y
            if screen.y > maxY
                maxY := screen.y
        }

        if screenParts.Count < 2 || maxX < 0
            continue

        bx := minX - 4
        by := minY - 4
        bw := (maxX - minX) + 8
        bh := (maxY - minY) + 8
        cx := bx + (bw // 2)
        cy := by + (bh // 2)

        if espSettings["box"] {
            DllCall("gdiplus\GdipDrawRectangle", "Ptr", gGraphics, "Ptr", gPenBox,
                    "Float", bx, "Float", by, "Float", bw, "Float", bh)
        }

        if espSettings["dot"] {
            DllCall("gdiplus\GdipFillEllipse", "Ptr", gGraphics, "Ptr", gBrushDot,
                    "Float", cx - 3, "Float", cy - 3, "Float", 6, "Float", 6)
        }

        if espSettings["health"] {
            ratio := chp / cd["mhp"]
            if ratio > 1
                ratio := 1
            if ratio < 0
                ratio := 0
            barX := bx - 5
            barHeight := Round(bh * ratio)
            barY := by + bh - barHeight
            DllCall("gdiplus\GdipFillRectangle", "Ptr", gGraphics, "Ptr", gBrushHealthBg,
                    "Float", barX - 1, "Float", by - 1, "Float", 5, "Float", bh + 2)
            r := Round(255 * (1.0 - ratio))
            g := Round(255 * ratio)
            colorHealth := (0xFF << 24) | (r << 16) | (g << 8) | 0
            if gBrushHealth
                DllCall("gdiplus\GdipDeleteBrush", "Ptr", gBrushHealth)
            DllCall("gdiplus\GdipCreateSolidFill", "UInt", colorHealth, "Ptr*", &gBrushHealth)
            DllCall("gdiplus\GdipFillRectangle", "Ptr", gGraphics, "Ptr", gBrushHealth,
                    "Float", barX, "Float", barY, "Float", 3, "Float", barHeight)
        }

        if espSettings["skeleton"] {
            bones := cd["r15"] ? R15_BONES : R6_BONES
            for bone in bones {
                partA := bone[1]
                partB := bone[2]
                if screenParts.Has(partA) && screenParts.Has(partB) {
                    p1 := screenParts[partA]
                    p2 := screenParts[partB]
                    DllCall("gdiplus\GdipDrawLine", "Ptr", gGraphics, "Ptr", gPenSkel,
                            "Float", p1.x, "Float", p1.y, "Float", p2.x, "Float", p2.y)
                }
            }
        }
    }


    DllCall("BitBlt", "Ptr", gDC, "Int", 0, "Int", 0, "Int", screenWidth, "Int", screenHeight,
            "Ptr", gMemDC, "Int", 0, "Int", 0, "UInt", 0x00CC0020)
}


ToggleESP(*) {
    global espEnableCheck, espActive, espSettings, overlayGui, debugText, mem
    if espEnableCheck.Value {
        if !mem {
            debugText.Value := "Attach to Roblox first!"
            espEnableCheck.Value := 0
            return
        }
        if !espActive {
            InitGDI()
            CreateOverlay()
            InitPersistentGraphics()
            espActive := true
            SetTimer(RenderESP, 1)
            debugText.Value := "ESP Enabled"
        }
    } else {
        espActive := false
        SetTimer(RenderESP, 0)
        ShutdownGDI()
        if overlayGui
            overlayGui.Destroy()
        overlayGui := 0
        debugText.Value := "ESP Disabled"
    }
    espSettings["enabled"] := espEnableCheck.Value
}

ToggleBox(*) {
    global espBoxCheck, espSettings
    espSettings["box"] := espBoxCheck.Value
}
ToggleDot(*) {
    global espDotCheck, espSettings
    espSettings["dot"] := espDotCheck.Value
}
ToggleHealth(*) {
    global espHealthCheck, espSettings
    espSettings["health"] := espHealthCheck.Value
}
ToggleSkeleton(*) {
    global espSkelCheck, espSettings
    espSettings["skeleton"] := espSkelCheck.Value
}
ToggleFOV(*) {
    global espFovCheck, espSettings
    espSettings["fov"] := espFovCheck.Value
}
UpdateFOV(*) {
    global espFovSlider, espFovText, espSettings
    espSettings["fovRadius"] := espFovSlider.Value
    espFovText.Value := "FOV Radius: " espSettings["fovRadius"] " px"
}


Global SelectedKey := "e"
Global Listening := false
Global KeyBtn := 0
Global CheckPred := 0
Global SliderX := 0
Global SliderY := 0
Global TxtX := 0
Global TxtY := 0
Global MainControls := []
Global VisualControls := []
Global MiscControls := []



C_Bg          := "0A0A0F"
C_SideBar     := "101018"
C_Accent      := "3F5EFB"
C_Text        := "CCCCCC"
C_White       := "FFFFFF"
C_Preview     := "0D0D14"


UpdateToggleMode(*) {
    global aimbotToggleMode, aimbotToggleState
    aimbotToggleMode := !aimbotToggleMode
    aimbotToggleState := false
}

DrawButton(x, y, w, h, text, callback) {
    global mainGui

    ; Background of the button
    bg := mainGui.Add("Text", Format("x{} y{} w{} h{} Background202030", x, y, w, h))
    ; Label text, white color, centered
    lbl := mainGui.Add("Text", Format("x{} y{} w{} h{} Center BackgroundTrans cFFFFFF 0x200", x, y, w, h), text)

    ; Assign the click callback
    bg.OnEvent("Click", callback)
    lbl.OnEvent("Click", callback)

    return bg  ; okay here because inside a function
}

Main() {
    global mainGui, SelectedKey, KeyBtn, keyBg, CheckPred, SliderX, SliderY, TxtX, TxtY, MainControls, VisualControls, MiscControls
    global debugText, aimbotKey, predictionEnabled, predictionX, predictionY, aimbotToggleMode
    global espEnableCheck, espBoxCheck, espDotCheck, espHealthCheck, espSkelCheck, espFovCheck, espFovSlider, espFovText
    global espPreviewPic, smoothnessCheck, smoothnessSlider, smoothnessText, targetPartDropdown

    mainGui := Gui("-Caption +AlwaysOnTop")
    mainGui.BackColor := "0A0A0F"

    ; ===== HEADER =====
    mainGui.Add("Text", "x0 y0 w720 h40 Background101018")
    mainGui.SetFont("s11 Bold cFFFFFF", "Segoe UI")
    header := mainGui.Add("Text", "x15 y0 w650 h40 BackgroundTrans 0x200", "margiela ahk external | join the discord!.gg/margielaa")
    header.OnEvent("Click", (*) => PostMessage(0xA1, 2,,, "A"))

    closeBtn := mainGui.Add("Text", "x680 y0 w40 h40 Center BackgroundTrans cFF5555", "X")
    closeBtn.SetFont("s12 Bold")
    closeBtn.OnEvent("Click", (*) => ExitApp())

    ; ===== SIDEBAR =====
    mainGui.Add("Text", "x0 y40 w140 h460 Background101018")

    mainGui.SetFont("s9 Bold c3F5EFB")
    mainGui.Add("Text", "x20 y60", "MENU")

    mainGui.SetFont("s9 cCCCCCC")
    DrawButton(15, 90, 110, 35, "Aimbot", (*) => ChangeTab("Main"))
    DrawButton(15, 135, 110, 35, "Visuals", (*) => ChangeTab("Visuals"))
    DrawButton(15, 450, 110, 35, "Attach", (*) => AttachToRoblox())

    ; =========================
    ; AIMBOT TAB
    ; =========================
    MainControls := []

    mainGui.SetFont("s12 Bold c3F5EFB")
    MainControls.Push(mainGui.Add("Text", "x170 y60", "Aimbot"))

    mainGui.SetFont("s9 c888888")
    MainControls.Push(mainGui.Add("Text", "x170 y80", "Combat settings"))

    MainControls.Push(mainGui.Add("Text", "x170 y100 w520 h1 Background252525"))

    mainGui.SetFont("s10 cCCCCCC")

    MainControls.Push(mainGui.Add("Checkbox", "x170 y115 Checked", "Enable Aimbot"))

    MainControls.Push(mainGui.Add("Text", "x170 y145", "Key"))
    keyBg := mainGui.Add("Text", "x230 y140 w100 h28 Background202030")
    KeyBtn := mainGui.Add("Text", "x230 y140 w100 h28 Center BackgroundTrans cFFFFFF 0x200", StrUpper(SelectedKey))
    keyBg.OnEvent("Click", StartListening)
    KeyBtn.OnEvent("Click", StartListening)
    MainControls.Push(keyBg)
    MainControls.Push(KeyBtn)

    toggleCheck := mainGui.Add("Checkbox", "x170 y180", "Toggle Mode")
    toggleCheck.OnEvent("Click", UpdateToggleMode)
    MainControls.Push(toggleCheck)

    MainControls.Push(mainGui.Add("Text", "x170 y210", "Target Part"))
    targetPartDropdown := mainGui.Add("DropDownList", "x250 y207 w120 Choose1", ["Head", "UpperTorso", "LowerTorso", "HumanoidRootPart"])
    targetPartDropdown.OnEvent("Change", (*) => targetPart := targetPartDropdown.Text)
    MainControls.Push(targetPartDropdown)

    CheckPred := mainGui.Add("Checkbox", "x170 y240 Checked", "Prediction")
    CheckPred.OnEvent("Click", TogglePrediction)
    MainControls.Push(CheckPred)

    TxtX := mainGui.Add("Text", "x170 y270", "Prediction X: " Round(predictionX) "%")
    MainControls.Push(TxtX)

    SliderX := mainGui.Add("Slider", "x170 y290 w350 Range0-50", predictionX)
    SliderX.OnEvent("Change", UpdatePredictionX)
    MainControls.Push(SliderX)

    TxtY := mainGui.Add("Text", "x170 y330", "Prediction Y: " Round(predictionY) "%")
    MainControls.Push(TxtY)

    SliderY := mainGui.Add("Slider", "x170 y350 w350 Range0-50", predictionY)
    SliderY.OnEvent("Change", UpdatePredictionY)
    MainControls.Push(SliderY)

    smoothnessCheck := mainGui.Add("Checkbox", "x170 y390", "Smoothness")
    smoothnessCheck.OnEvent("Click", ToggleSmoothness)
    MainControls.Push(smoothnessCheck)

    smoothnessText := mainGui.Add("Text", "x170 y420", "Smoothness: " Round(smoothnessValue) "%")
    MainControls.Push(smoothnessText)

    smoothnessSlider := mainGui.Add("Slider", "x170 y440 w350 Range0-100", smoothnessValue)
    smoothnessSlider.OnEvent("Change", UpdateSmoothness)
    MainControls.Push(smoothnessSlider)

    debugText := mainGui.Add("Text", "x170 y480 w500", "Status: waiting...")
    MainControls.Push(debugText)

    ; =========================
    ; VISUAL TAB
    ; =========================
    VisualControls := []

    mainGui.SetFont("s12 Bold c3F5EFB")
    VisualControls.Push(mainGui.Add("Text", "x170 y60 Hidden", "Visuals"))

    mainGui.SetFont("s9 c888888")
    VisualControls.Push(mainGui.Add("Text", "x170 y80 Hidden", "ESP Settings"))

    VisualControls.Push(mainGui.Add("Text", "x170 y100 w520 h1 Hidden Background252525"))

    mainGui.SetFont("s10 cCCCCCC")

    espEnableCheck := mainGui.Add("Checkbox", "x170 y120 Hidden", "Enable ESP")
    espEnableCheck.OnEvent("Click", ToggleESP)
    VisualControls.Push(espEnableCheck)

    espBoxCheck := mainGui.Add("Checkbox", "x170 y150 Hidden", "Box")
    espBoxCheck.OnEvent("Click", ToggleBox)
    VisualControls.Push(espBoxCheck)

    espDotCheck := mainGui.Add("Checkbox", "x170 y180 Hidden", "Dot")
    espDotCheck.OnEvent("Click", ToggleDot)
    VisualControls.Push(espDotCheck)

    espHealthCheck := mainGui.Add("Checkbox", "x170 y210 Hidden", "Health")
    espHealthCheck.OnEvent("Click", ToggleHealth)
    VisualControls.Push(espHealthCheck)

    espSkelCheck := mainGui.Add("Checkbox", "x170 y240 Hidden", "Skeleton")
    espSkelCheck.OnEvent("Click", ToggleSkeleton)
    VisualControls.Push(espSkelCheck)

    espFovCheck := mainGui.Add("Checkbox", "x170 y270 Hidden", "FOV")
    espFovCheck.OnEvent("Click", ToggleFOV)
    VisualControls.Push(espFovCheck)

    espFovText := mainGui.Add("Text", "x170 y300 Hidden", "FOV Radius: " espSettings["fovRadius"])
    VisualControls.Push(espFovText)

    espFovSlider := mainGui.Add("Slider", "x170 y320 w300 Range50-600 Hidden", espSettings["fovRadius"])
    espFovSlider.OnEvent("Change", UpdateFOV)
    VisualControls.Push(espFovSlider)

    ; Preview box stays same
    espPreviewPic := mainGui.Add("Picture", "x500 y120 w180 h260 Hidden")
    VisualControls.Push(espPreviewPic)

    MiscControls := []

    ChangeTab("Main")
    mainGui.Show("w720 h500")
    ApplyRoundedCorners(mainGui.Hwnd, 720, 500, 25)

    DrawESPPreview()
}

DrawESPPreview() {
    global espPreviewPic
    try {
        W := 256, H := 320

        ; Explicitly load gdiplus
        if !DllCall("LoadLibrary", "Str", "gdiplus.dll", "Ptr")
            return

        si := Buffer(24, 0)
        NumPut("UInt", 1, si)
        DllCall("gdiplus\GdiplusStartup", "UPtr*", &tok := 0, "Ptr", si, "Ptr", 0)
        if !tok
            return

        hdc := DllCall("GetDC", "Ptr", espPreviewPic.Hwnd, "Ptr")
        if !hdc {
            DllCall("gdiplus\GdiplusShutdown", "UPtr", tok)
            return
        }
        hMemDC := DllCall("CreateCompatibleDC", "Ptr", hdc, "Ptr")
        hBmp   := DllCall("CreateCompatibleBitmap", "Ptr", hdc, "Int", W, "Int", H, "Ptr")
        DllCall("SelectObject", "Ptr", hMemDC, "Ptr", hBmp)

        DllCall("gdiplus\GdipCreateFromHDC",    "Ptr", hMemDC, "UPtr*", &gfx := 0)
        DllCall("gdiplus\GdipSetSmoothingMode", "Ptr", gfx, "Int", 2)

        ; Background
        DllCall("gdiplus\GdipCreateSolidFill", "UInt", 0xFF0D0D14, "UPtr*", &brBg := 0)
        DllCall("gdiplus\GdipFillRectangleI",  "Ptr", gfx, "Ptr", brBg, "Int", 0, "Int", 0, "Int", W, "Int", H)
        DllCall("gdiplus\GdipDeleteBrush",     "Ptr", brBg)

        ; Pens / brushes
        DllCall("gdiplus\GdipCreatePen1",      "UInt", 0xFFFFFFFF, "Float", 1.5, "Int", 2, "UPtr*", &penBox  := 0)
        DllCall("gdiplus\GdipCreatePen1",      "UInt", 0xFFFFC800, "Float", 1.2, "Int", 2, "UPtr*", &penSkel := 0)
        DllCall("gdiplus\GdipCreatePen1",      "UInt", 0x55FFFFFF, "Float", 1.0, "Int", 2, "UPtr*", &penFov  := 0)
        DllCall("gdiplus\GdipCreateSolidFill", "UInt", 0xFF330000, "UPtr*", &brHpBg := 0)
        DllCall("gdiplus\GdipCreateSolidFill", "UInt", 0xFF22DD44, "UPtr*", &brHp   := 0)
        DllCall("gdiplus\GdipCreateSolidFill", "UInt", 0xFFFF3C3C, "UPtr*", &brDot  := 0)

        ; FOV circle
        fovR := 80, cx := W//2, cy := H//2
        DllCall("gdiplus\GdipDrawEllipseI", "Ptr", gfx, "Ptr", penFov,
            "Int", cx-fovR, "Int", cy-fovR, "Int", fovR*2, "Int", fovR*2)

        ; Bounding box
        bx := 100, by := 75, bw := 56, bh := 165
        DllCall("gdiplus\GdipDrawRectangleI", "Ptr", gfx, "Ptr", penBox, "Int", bx, "Int", by, "Int", bw, "Int", bh)

        ; Skeleton joints
        hx := bx + bw//2,  hy := by + 11
        tx := bx + bw//2,  ty := by + 68
        lx := bx + bw//2,  ly := by + 118

        DllCall("gdiplus\GdipDrawEllipseI", "Ptr", gfx, "Ptr", penSkel, "Int", hx-10, "Int", by,     "Int", 20, "Int", 22)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", hx, "Int", by+22,     "Int", tx, "Int", ty)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", tx, "Int", ty,        "Int", lx, "Int", ly)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", tx, "Int", ty,        "Int", bx+4,      "Int", ty+33)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", bx+4,  "Int", ty+33,  "Int", bx+2,      "Int", ly+8)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", tx,    "Int", ty,      "Int", bx+bw-4,   "Int", ty+33)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", bx+bw-4, "Int", ty+33, "Int", bx+bw-2,  "Int", ly+8)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", lx,    "Int", ly,      "Int", bx+14,     "Int", by+bh-18)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", bx+14, "Int", by+bh-18,"Int", bx+10,     "Int", by+bh)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", lx,    "Int", ly,      "Int", bx+bw-14,  "Int", by+bh-18)
        DllCall("gdiplus\GdipDrawLineI",    "Ptr", gfx, "Ptr", penSkel, "Int", bx+bw-14, "Int", by+bh-18, "Int", bx+bw-10, "Int", by+bh)

        ; Health bar
        DllCall("gdiplus\GdipFillRectangleI", "Ptr", gfx, "Ptr", brHpBg, "Int", bx-7, "Int", by,       "Int", 4, "Int", bh)
        DllCall("gdiplus\GdipFillRectangleI", "Ptr", gfx, "Ptr", brHp,   "Int", bx-7, "Int", by+bh//4, "Int", 4, "Int", (bh*3)//4)

        ; Dot
        DllCall("gdiplus\GdipFillRectangleI", "Ptr", gfx, "Ptr", brDot, "Int", bx+bw//2-3, "Int", by+bh+4, "Int", 6, "Int", 6)

        ; Cleanup
        DllCall("gdiplus\GdipDeletePen",     "Ptr", penBox)
        DllCall("gdiplus\GdipDeletePen",     "Ptr", penSkel)
        DllCall("gdiplus\GdipDeletePen",     "Ptr", penFov)
        DllCall("gdiplus\GdipDeleteBrush",   "Ptr", brHpBg)
        DllCall("gdiplus\GdipDeleteBrush",   "Ptr", brHp)
        DllCall("gdiplus\GdipDeleteBrush",   "Ptr", brDot)
        DllCall("gdiplus\GdipDeleteGraphics","Ptr", gfx)

        DllCall("BitBlt", "Ptr", hdc, "Int", 0, "Int", 0, "Int", W, "Int", H,
                "Ptr", hMemDC, "Int", 0, "Int", 0, "UInt", 0xCC0020)

        DllCall("DeleteObject", "Ptr", hBmp)
        DllCall("DeleteDC",     "Ptr", hMemDC)
        DllCall("ReleaseDC",    "Ptr", espPreviewPic.Hwnd, "Ptr", hdc)
        DllCall("gdiplus\GdiplusShutdown", "UPtr", tok)
    }
}

ApplyRoundedCorners(hwnd, w := 720, h := 500, r := 20) {
    region := DllCall("gdi32\CreateRoundRectRgn"
        , "Int", 0, "Int", 0
        , "Int", w, "Int", h
        , "Int", r, "Int", r
        , "Ptr")

    DllCall("user32\SetWindowRgn", "Ptr", hwnd, "Ptr", region, "Int", true)
}

ChangeTab(TabName) {
    global MainControls, VisualControls, MiscControls, KeyBtn, keyBg

    for ctrl in MainControls
        ctrl.Visible := false
    for ctrl in VisualControls
        ctrl.Visible := false

    if (TabName = "Main") {
        for ctrl in MainControls
            ctrl.Visible := true
        TogglePrediction()
        ToggleSmoothness()
    } else if (TabName = "Visuals") {
        for ctrl in VisualControls
            ctrl.Visible := true
        KeyBtn.Visible := false
        keyBg.Visible := false
    }
}

TogglePrediction(*) {
    global CheckPred, TxtX, SliderX, TxtY, SliderY, MainControls, predictionEnabled
    state := CheckPred.Value
    predictionEnabled := state
    isVisible := (MainControls[1].Visible && state)
    TxtX.Visible := isVisible
    SliderX.Visible := isVisible
    TxtY.Visible := isVisible
    SliderY.Visible := isVisible
}

UpdatePredictionX(*) {
    global SliderX, TxtX, predictionX
    predictionX := SliderX.Value
    TxtX.Value := "Prediction X: " Round(predictionX) "%"
}

UpdatePredictionY(*) {
    global SliderY, TxtY, predictionY
    predictionY := SliderY.Value
    TxtY.Value := "Prediction Y: " Round(predictionY) "%"
}

StartListening(*) {
    Global SelectedKey, Listening, KeyBtn, aimbotKey
    Listening := true
    KeyBtn.Text := "..."
    Hotkey("XButton1", Caught, "On")
    Hotkey("XButton2", Caught, "On")
    ih := InputHook("L1 M")
    ih.Start()
    while (Listening && ih.InProgress)
        Sleep(10)
    if (ih.Input != "")
        SelectedKey := ih.Input
    ih.Stop()
    Hotkey("XButton1", "Off")
    Hotkey("XButton2", "Off")
    aimbotKey := SelectedKey
    KeyBtn.Text := StrUpper(SelectedKey)
    Listening := false
}

ToggleSmoothness(*) {
    global smoothnessCheck, smoothnessEnabled, smoothnessSlider, smoothnessText, MainControls
    state := smoothnessCheck.Value
    smoothnessEnabled := state
    isVisible := (MainControls[1].Visible && state)
    smoothnessSlider.Visible := isVisible
    smoothnessText.Visible := isVisible
}

UpdateSmoothness(*) {
    global smoothnessSlider, smoothnessText, smoothnessValue
    smoothnessValue := smoothnessSlider.Value
    smoothnessText.Value := "Smoothness: " Round(smoothnessValue) "%"
}

Caught(K) {
    Global SelectedKey, Listening, aimbotKey
    SelectedKey := K
    aimbotKey := K
    Listening := false
}

AttachToRoblox() {
    global mem, baseAddr, debugText, humanoid
    try {
        debugText.Value := "Searching for RobloxPlayerBeta.exe..."
        mem := Memory("RobloxPlayerBeta.exe")
        baseAddr := mem.baseAddr
        debugText.Value := "Process found. Base: 0x" Format("{:X}", baseAddr) " - Attaching..."

        result := aimbotshit()
        if !result {
            debugText.Value := "Attach failed - check offsets (see MsgBox)"
            return
        }
        debugText.Value := "Attached successfully!"
        SetTimer(AimbotLoop, 10)
        SetTimer(MiscLoop, 100)

        if espEnableCheck && espEnableCheck.Value {
            ToggleESP()
        }
    } catch as err {
        debugText.Value := "Error: " err.Message
        MsgBox("Exception during attach:`n" err.Message "`n`nLine: " err.Line, "Attach Error", 0x10)
    }
}

Insert::
{
    global mainGui

    if !mainGui
        return

    if DllCall("IsWindowVisible", "Ptr", mainGui.Hwnd)
        mainGui.Hide()
    else
        mainGui.Show()
}

Delete::
{
    ExitApp()
}

aimbotshit() {
    global mem, baseAddr, dataModel, workspace, camera, players, localPlayer, visualEngine, matrixAddr, camRotAddr, camPosAddr, character, humanoid, debugText
    try {
        debugText.Value := "[1/7] Reading VisualEngine..."
        visualEngine := mem.Read(baseAddr + Offsets.VisualEnginePtr, "UInt64")
        if !visualEngine {
            MsgBox("Step 1 FAILED: VisualEngine = 0`nOffset: 0x" Format("{:X}", Offsets.VisualEnginePtr) "`nThis offset is likely outdated.", "Offset Debug", 0x30)
            return false
        }

        debugText.Value := "[2/7] Reading FakeDataModel..."
        fakeDataModel := mem.Read(baseAddr + Offsets.FakeDataModelPtr, "UInt64")
        if !fakeDataModel {
            MsgBox("Step 2 FAILED: FakeDataModel = 0`nOffset: 0x" Format("{:X}", Offsets.FakeDataModelPtr) "`nThis offset is likely outdated.", "Offset Debug", 0x30)
            return false
        }

        debugText.Value := "[3/7] Reading RealDataModel..."
        dataModel := mem.Read(fakeDataModel + Offsets.RealDataModel, "UInt64")
        if !dataModel {
            MsgBox("Step 3 FAILED: RealDataModel = 0`nfakeDataModel: 0x" Format("{:X}", fakeDataModel) "`nOffset: 0x" Format("{:X}", Offsets.RealDataModel), "Offset Debug", 0x30)
            return false
        }

        debugText.Value := "[4/7] Reading Workspace..."
        workspace := mem.Read(dataModel + Offsets.Workspace, "UInt64")
        if !workspace {
            MsgBox("Step 4 FAILED: Workspace = 0`ndataModel: 0x" Format("{:X}", dataModel) "`nOffset: 0x" Format("{:X}", Offsets.Workspace), "Offset Debug", 0x30)
            return false
        }

        debugText.Value := "[5/7] Reading Camera..."
        camera := mem.Read(workspace + Offsets.CurrentCamera, "UInt64")
        if !camera {
            ; Fallback: find Camera as a named child of Workspace
            camera := robloxfuckass.FindChild(workspace, "Camera")
        }
        if !camera {
            MsgBox("Step 5 FAILED: Camera = 0`nworkspace: 0x" Format("{:X}", workspace) "`nOffset: 0x" Format("{:X}", Offsets.CurrentCamera) "`n`nBoth direct offset and FindChild('Camera') failed.", "Offset Debug", 0x30)
            return false
        }

        debugText.Value := "[6/7] Finding Players service..."
        players := robloxfuckass.FindChild(dataModel, "Players")
        if !players {
            MsgBox("Step 6 FAILED: Could not find 'Players' child in DataModel`ndataModel: 0x" Format("{:X}", dataModel) "`n`nThe Name/Children offsets may be wrong.", "Offset Debug", 0x30)
            return false
        }

        debugText.Value := "[7/7] Reading LocalPlayer..."
        localPlayer := mem.Read(players + Offsets.LocalPlayer, "UInt64")
        if !localPlayer {
            MsgBox("Step 7 FAILED: LocalPlayer = 0`nplayers: 0x" Format("{:X}", players) "`nOffset: 0x" Format("{:X}", Offsets.LocalPlayer) "`n`nMake sure you are in a game (not the menu).", "Offset Debug", 0x30)
            return false
        }

        character := mem.Read(localPlayer + Offsets.ModelInstance, "UInt64")
        if character {
            humanoid := robloxfuckass.FindChildOfClass(character, "Humanoid")
        }
        matrixAddr := visualEngine + Offsets.ViewMatrix
        camRotAddr := camera + Offsets.Rotation
        camPosAddr := camera + Offsets.Position
        return true
    } catch as err {
        MsgBox("Exception in aimbotshit():`n" err.Message "`nLine: " err.Line, "Attach Exception", 0x10)
        return false
    }
}

OnExit((*) => ShutdownGDI())

Main()

F2::
{
    global mainGui
    if DllCall("IsWindowVisible", "Ptr", mainGui.Hwnd)
        mainGui.Hide()
    else
        mainGui.Show()
}

F4::ExitApp()
