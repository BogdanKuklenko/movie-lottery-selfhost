# Movie Lottery Notification Client - Keep Alive Script
# Checks if client is running and starts if needed

# Use script's own directory (automatically handles any path)
$ScriptDir = $PSScriptRoot
$PythonExe = "pythonw.exe"
$ClientScript = "notification_client.py"
$ServerUrl = "http://localhost:8888"
$LogFile = Join-Path $ScriptDir "keep_alive.log"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $Message" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

# Check if Docker container is running
function Test-DockerRunning {
    try {
        $result = docker inspect -f '{{.State.Running}}' movie_lottery_app 2>$null
        return $result -eq "true"
    } catch {
        return $false
    }
}

# Check if notification_client is running
function Test-ClientRunning {
    $processes = Get-Process -Name "python*" -ErrorAction SilentlyContinue
    foreach ($proc in $processes) {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
            if ($cmdLine -like "*notification_client*") {
                return $true
            }
        } catch {}
    }
    return $false
}

# Start the client
function Start-NotificationClient {
    Write-Log "Starting notification_client.py..."
    Set-Location $ScriptDir
    Start-Process -FilePath $PythonExe -ArgumentList "$ClientScript --server $ServerUrl" -WorkingDirectory $ScriptDir -WindowStyle Hidden
    Write-Log "Client started"
}

# Main logic
if (-not (Test-DockerRunning)) {
    Write-Log "Docker container not running, skip"
    exit 0
}

if (Test-ClientRunning) {
    # Client is running, all ok
    exit 0
}

# Client not running, Docker is running - start client
Write-Log "Client not running, Docker is running"
Start-NotificationClient
