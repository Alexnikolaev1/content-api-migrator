param([string]$Target = "all")

$ErrorActionPreference = "Stop"
$python = if (Test-Path ".\venv\Scripts\python.exe") {
    ".\venv\Scripts\python.exe"
} else {
    "python"
}

switch ($Target) {
    "all" { & $python martin_guard.py all }
    "length" { & $python martin_guard.py length }
    "complexity" { & $python martin_guard.py complexity }
    "shape" { & $python martin_guard.py shape }
    "structure" { & $python martin_guard.py structure }
    "mutate" { & $python -m mutmut run }
    default { throw "Неизвестная цель: $Target" }
}

exit $LASTEXITCODE
