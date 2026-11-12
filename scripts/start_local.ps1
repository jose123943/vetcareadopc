param(
    [ValidateRange(1024, 65535)]
    [int] $Port = 8000,
    [switch] $NoReload
)

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Falta .venv. Crea el entorno e instala requirements.txt antes de iniciar VetCare.'
}

$previousDebug = [Environment]::GetEnvironmentVariable('DEBUG', 'Process')
$previousSettings = [Environment]::GetEnvironmentVariable('DJANGO_SETTINGS_MODULE', 'Process')
Push-Location -LiteralPath $projectDirectory
try {
    # El valor genérico DEBUG=release heredado de algunas aplicaciones desactiva
    # los estáticos de runserver. Este cambio solo afecta al proceso local.
    $env:DEBUG = 'True'
    $env:DJANGO_SETTINGS_MODULE = 'veterinaria.settings'
    & $pythonExecutable manage.py check --database default
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pythonExecutable manage.py migrate --check
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Hay migraciones pendientes. Revisa manage.py migrate --plan y aplícalas antes de arrancar.'
        exit $LASTEXITCODE
    }
    $serverArguments = @('manage.py', 'runserver', "127.0.0.1:$Port")
    if ($NoReload) { $serverArguments += '--noreload' }
    & $pythonExecutable @serverArguments
    exit $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable('DEBUG', $previousDebug, 'Process')
    [Environment]::SetEnvironmentVariable('DJANGO_SETTINGS_MODULE', $previousSettings, 'Process')
    Pop-Location
}
