param(
    [string]$Python = $(if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }),
    [string]$VenvDir = $(if ($env:VENV_DIR) { $env:VENV_DIR } else { ".venv" }),
    [string]$EnvFile = $(if ($env:ENV_FILE) { $env:ENV_FILE } else { ".env" }),
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if (-not [System.IO.Path]::IsPathRooted($VenvDir)) {
    $VenvDir = Join-Path $Root $VenvDir
}
if (-not [System.IO.Path]::IsPathRooted($EnvFile)) {
    $EnvFile = Join-Path $Root $EnvFile
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    & $Python -m venv $VenvDir
}

& $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'Python 3.11+ is required')"

if (-not $SkipInstall) {
    & $VenvPython -m pip install -U pip
    & $VenvPython -m pip install -e ".[server]"
}

function Get-DeploymentEnv {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$Default = ""
    )

    $value = [Environment]::GetEnvironmentVariable($Name)
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        return $value
    }

    if (Test-Path $EnvFile) {
        foreach ($line in Get-Content $EnvFile) {
            if ($line -match "^\s*#") {
                continue
            }
            if ($line -match "^\s*$([regex]::Escape($Name))\s*=(.*)$") {
                $value = $Matches[1].Trim()
            }
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($value)) {
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        return $value
    }

    return $Default
}

$OpenAiApiKey = Get-DeploymentEnv -Name "OPENAI_API_KEY"
$EntryApiKey = Get-DeploymentEnv -Name "ENTRY_API_KEY"
$EntryHost = Get-DeploymentEnv -Name "ENTRY_HOST" -Default "0.0.0.0"
$EntryPort = Get-DeploymentEnv -Name "ENTRY_PORT" -Default "8769"
$Workers = Get-DeploymentEnv -Name "UVICORN_WORKERS" -Default "1"

$missing = @()
if ([string]::IsNullOrWhiteSpace($OpenAiApiKey) -or $OpenAiApiKey -eq "sk-your-api-key-here") {
    $missing += "OPENAI_API_KEY"
}
if ([string]::IsNullOrWhiteSpace($EntryApiKey) -or $EntryApiKey -eq "replace-with-app-debug-token") {
    $missing += "ENTRY_API_KEY"
}

if ($missing.Count -gt 0) {
    Write-Error "Missing required deployment settings: $($missing -join ', '). Create .env from .env.example and fill real values, or set environment variables before running this script."
}

if ($Workers -ne "1") {
    Write-Warning "UVICORN_WORKERS=$Workers. Use 1 for App debugging because sessions are in process memory."
}

$env:OPENAI_API_KEY = $OpenAiApiKey
$env:ENTRY_API_KEY = $EntryApiKey
$env:ENTRY_HOST = $EntryHost
$env:ENTRY_PORT = $EntryPort

Write-Host "Momcozy Agent API: http://$EntryHost`:$EntryPort"
Write-Host "Health check:      http://$EntryHost`:$EntryPort/healthz"
Write-Host "App WebSocket:     ws://$EntryHost`:$EntryPort/api/ag-ui-ws"

& $VenvPython -m uvicorn momcozy_agent.api_app:app --host $EntryHost --port $EntryPort --workers $Workers
exit $LASTEXITCODE

