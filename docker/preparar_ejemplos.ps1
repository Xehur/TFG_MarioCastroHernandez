<#
.SYNOPSIS
  Descarga WSI de ejemplo del dataset BACH y las importa en tu cuenta.

.DESCRIPTION
  Ejecuta backend/scripts/preparar_ejemplos_bach.py dentro del contenedor del
  backend (no hace falta instalar Python). La aplicación debe estar arrancada
  (iniciar.ps1) y debes haber creado ya tu cuenta: se pedirán su email y
  contraseña.

  Uso:  .\preparar_ejemplos.ps1              (2 WSI, ~350 MB)
        .\preparar_ejemplos.ps1 -Count 4     (de 1 a 10)
        .\preparar_ejemplos.ps1 -SinAnotaciones
  Si PowerShell bloquea el script:
        powershell -ExecutionPolicy Bypass -File .\preparar_ejemplos.ps1
#>
param(
    [ValidateRange(1, 10)]
    [int]$Count = 2,
    [switch]$SinAnotaciones
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'Docker no está instalado o no está en el PATH.' -ForegroundColor Red
    exit 1
}

$argumentos = @('scripts/preparar_ejemplos_bach.py', '--count', "$Count")
if ($SinAnotaciones) { $argumentos += '--sin-anotaciones' }

docker compose exec backend python @argumentos
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host 'Si el error indica que el servicio "backend" no está en marcha, arranca antes la aplicación con .\iniciar.ps1' -ForegroundColor Yellow
    exit $LASTEXITCODE
}
