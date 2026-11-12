param(
    [string[]] $TestLabels = @()
)

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Falta .venv. Crea el entorno e instala requirements.txt antes de ejecutar las pruebas.'
}

Push-Location -LiteralPath $projectDirectory
try {
    & $pythonExecutable manage.py check --settings=veterinaria.test_settings
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pythonExecutable manage.py makemigrations --check --dry-run --settings=veterinaria.test_settings
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pythonExecutable manage.py test @TestLabels --settings=veterinaria.test_settings --verbosity 2
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
