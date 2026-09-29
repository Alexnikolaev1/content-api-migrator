$ErrorActionPreference = "Stop"
$python = if (Test-Path ".\venv\Scripts\python.exe") {
    ".\venv\Scripts\python.exe"
} else {
    "python"
}

# Use $args (no param block) so flags like -o are not stolen by PowerShell.
& $python ".\run.py" @args
exit $LASTEXITCODE
