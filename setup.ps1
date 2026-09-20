# Project bootstrap: creates .venv, installs requirements.txt, checks .env.
# Makes no AWS calls and touches no OpenSearch data. Safe to re-run.
#
#   .\setup.ps1          (Windows PowerShell)
Set-Location -LiteralPath $PSScriptRoot

# First interpreter that runs and is Python 3.10+ (`py -3` is the Windows launcher).
$python = $null
foreach ($candidate in @(@('py', '-3'), @('python'), @('python3'))) {
    $exe = $candidate[0]
    $extra = @($candidate | Select-Object -Skip 1)
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    & $exe @extra -c "import sys; sys.exit(int(sys.version_info < (3, 10)))" 2>$null
    if ($LASTEXITCODE -eq 0) { $python = @($exe) + $extra; break }
}
if (-not $python) {
    Write-Host "Python 3.10 or newer was not found. Install it and re-run: .\setup.ps1" -ForegroundColor Red
    exit 1
}
$pyExe = $python[0]
$pyArgs = @($python | Select-Object -Skip 1)

if (-not (Test-Path -LiteralPath '.venv')) {
    Write-Host "Creating virtual environment in .venv ..."
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "Could not create the virtual environment." -ForegroundColor Red; exit 1 }
}
$venvPy = if (Test-Path -LiteralPath '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { '.venv/bin/python' }

Write-Host "Installing requirements.txt ..."
& $venvPy -m pip install --disable-pip-version-check -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed; see the output above." -ForegroundColor Red; exit 1 }

if (-not (Test-Path -LiteralPath '.env')) {
    Write-Host "Dependencies are installed, but .env is missing." -ForegroundColor Yellow
    Write-Host "Create it from the template, fill in the values, then re-run this script:"
    Write-Host "  Copy-Item .env.example .env"
    exit 1
}

# config.py validates every required variable without any network call.
$problem = & $venvPy -c "import config" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Configuration is incomplete:" -ForegroundColor Yellow
    Write-Host ($problem | Select-Object -Last 1)
    Write-Host "Edit .env (see .env.example) and re-run this script."
    exit 1
}

Write-Host "Setup complete. Activate the environment before running anything:"
Write-Host "  .venv\Scripts\Activate.ps1"
