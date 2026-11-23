<#
.SYNOPSIS
  Prepara y monta la aplicación con Docker eligiendo dónde se ejecuta la IA.

.DESCRIPTION
  En un equipo nuevo basta con clonar el repositorio y ejecutar este script:
    1. Crea docker/.env a partir de .env.example con una SECRET_KEY y una
       DB_PASSWORD aleatorias (si ya existe, solo rellena las que falten).
    2. Descarga los pesos del modelo (InceptionV3/HE_inceptionv3.pth) del último
       release de GitHub si no están, y comprueba su SHA-256.
    3. Pregunta si ejecutar la IA en CPU, GPU NVIDIA o GPU AMD y arranca
       "docker compose ... up --build -d".

  Uso:  .\iniciar.ps1                 (pregunta la opción)
        .\iniciar.ps1 cpu | nvidia | amd
  Si PowerShell bloquea el script:
        powershell -ExecutionPolicy Bypass -File .\iniciar.ps1
#>
param(
    [ValidateSet('cpu', 'nvidia', 'amd', '')]
    [string]$Modo = ''
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$PesosRuta = Join-Path (Split-Path $PSScriptRoot -Parent) 'InceptionV3\HE_inceptionv3.pth'
$PesosSha256 = '42515436dd2de4057eba0846aaac2561b38dc88efe960ef6a471807536394a5e'
$PesosUrlPorDefecto = 'https://github.com/Xehur/TFG_MarioCastroHernandez/releases/latest/download/HE_inceptionv3.pth'
$PlaceholderDbPassword = 'cambia-esta-contrasena'

function Invocar-Silencioso([scriptblock]$bloque) {
    # En PowerShell 5.1 redirigir el stderr de un programa externo con
    # ErrorActionPreference=Stop lanza excepciones: se relaja solo aquí.
    $previo = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $salida = & $bloque 2>$null; return @{ Salida = $salida; Ok = ($LASTEXITCODE -eq 0) } }
    finally { $ErrorActionPreference = $previo }
}

function Escribir-Paso([string]$texto) { Write-Host "==> $texto" -ForegroundColor Cyan }
function Escribir-Aviso([string]$texto) { Write-Host "AVISO: $texto" -ForegroundColor Yellow }

function Nuevo-Secreto([int]$bytes) {
    # Cadena aleatoria segura en base64 URL (sin '+', '/' ni '='): válida en URL de BD.
    $buffer = New-Object byte[] $bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($buffer)
    $rng.Dispose()
    return ([Convert]::ToBase64String($buffer)).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Leer-ValorEnv([string]$clave) {
    if (-not (Test-Path '.env')) { return $null }
    foreach ($linea in [IO.File]::ReadAllLines((Resolve-Path '.env'))) {
        if ($linea -match "^\s*$clave\s*=(.*)$") { return $Matches[1].Trim().Trim('"').Trim("'") }
    }
    return $null
}

function Preparar-Env {
    $nuevo = -not (Test-Path '.env')
    if ($nuevo) {
        Escribir-Paso 'Creando docker/.env a partir de .env.example'
        $lineas = [IO.File]::ReadAllLines((Resolve-Path '.env.example'))
    } else {
        $lineas = [IO.File]::ReadAllLines((Resolve-Path '.env'))
    }

    $cambios = @()
    for ($i = 0; $i -lt $lineas.Count; $i++) {
        if ($lineas[$i] -match '^\s*SECRET_KEY\s*=\s*$') {
            $lineas[$i] = 'SECRET_KEY=' + (Nuevo-Secreto 48)
            $cambios += 'SECRET_KEY'
        } elseif ($lineas[$i] -match "^\s*DB_PASSWORD\s*=\s*($PlaceholderDbPassword)?\s*$") {
            $lineas[$i] = 'DB_PASSWORD=' + (Nuevo-Secreto 24)
            $cambios += 'DB_PASSWORD'
        }
    }

    if ($nuevo -or $cambios.Count -gt 0) {
        # UTF-8 SIN BOM: Docker Compose no admite el BOM en el .env.
        $utf8SinBom = New-Object System.Text.UTF8Encoding($false)
        [IO.File]::WriteAllText((Join-Path $PSScriptRoot '.env'), ($lineas -join "`n") + "`n", $utf8SinBom)
    }
    if ($cambios.Count -gt 0) {
        Write-Host "    Generados valores aleatorios para: $($cambios -join ', ')"
        if ($cambios -contains 'DB_PASSWORD') {
            $volumen = (Invocar-Silencioso { docker volume ls -q --filter 'name=docker_db_data' }).Salida
            if ($volumen) {
                Escribir-Aviso ('Ya existe una base de datos de una instalación anterior (volumen ' +
                    'docker_db_data) creada con otra contraseña. PostgreSQL mantendrá la antigua: ' +
                    'restaura tu .env anterior o bórrala con "docker compose down -v" (se pierden los datos).')
            }
        }
    } elseif (-not $nuevo) {
        Write-Host '    docker/.env ya está configurado.'
    }
}

function Preparar-Pesos {
    if (Test-Path $PesosRuta) {
        $hash = (Get-FileHash -Algorithm SHA256 $PesosRuta).Hash.ToLower()
        if ($hash -ne $PesosSha256) {
            Escribir-Aviso 'Los pesos existentes no coinciden con el SHA-256 esperado (¿otro modelo?). Se usarán igualmente.'
        } else {
            Write-Host '    Pesos del modelo presentes y verificados.'
        }
        return
    }

    # Prioridad: variable de entorno > docker/.env > último release de GitHub.
    $url = $env:INCEPTION_WEIGHTS_URL
    if (-not $url) { $url = Leer-ValorEnv 'INCEPTION_WEIGHTS_URL' }
    if (-not $url) { $url = $PesosUrlPorDefecto }
    Escribir-Paso "Descargando los pesos del modelo (~98 MB) desde $url"
    $temporal = "$PesosRuta.part"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = 'SilentlyContinue'  # la barra de progreso ralentiza mucho la descarga
        Invoke-WebRequest -Uri $url -OutFile $temporal -UseBasicParsing
        $hash = (Get-FileHash -Algorithm SHA256 $temporal).Hash.ToLower()
        if ($hash -ne $PesosSha256) {
            Remove-Item $temporal -Force
            throw "el SHA-256 del fichero descargado no coincide ($hash)"
        }
        Move-Item $temporal $PesosRuta -Force
        Write-Host '    Pesos descargados y verificados.'
    } catch {
        if (Test-Path $temporal) { Remove-Item $temporal -Force }
        Escribir-Aviso ("No se pudieron descargar los pesos: $($_.Exception.Message). La aplicación " +
            "funcionará sin la IA (responderá 503). Copia HE_inceptionv3.pth en InceptionV3\ " +
            'o define INCEPTION_WEIGHTS_URL en docker/.env y vuelve a ejecutar el script.')
    }
}

# --- 0. Docker disponible --------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'Docker no está instalado o no está en el PATH. Instala Docker Desktop y vuelve a intentarlo.' -ForegroundColor Red
    exit 1
}
if (-not (Invocar-Silencioso { docker info }).Ok) {
    Write-Host 'Docker está instalado pero no está en marcha. Abre Docker Desktop y vuelve a intentarlo.' -ForegroundColor Red
    exit 1
}

# --- 1. Configuración y 2. pesos -------------------------------------------
Preparar-Env
Preparar-Pesos

# --- 3. CPU o GPU ----------------------------------------------------------
if (-not $Modo) {
    Write-Host ''
    Write-Host '¿Dónde quieres ejecutar la IA?'
    Write-Host '  1) CPU (funciona en cualquier equipo)'
    Write-Host '  2) GPU NVIDIA (CUDA)'
    Write-Host '  3) GPU AMD (ROCm, solo con Docker en Linux)'
    switch (Read-Host 'Opción [1]') {
        '2' { $Modo = 'nvidia' }
        '3' { $Modo = 'amd' }
        default { $Modo = 'cpu' }
    }
}

$archivos = @('-f', 'docker-compose.yml')
switch ($Modo) {
    'nvidia' { $archivos += @('-f', 'docker-compose.gpu-nvidia.yml') }
    'amd' {
        Escribir-Aviso 'Docker Desktop en Windows no expone GPU AMD; la IA usará CPU.'
        $archivos += @('-f', 'docker-compose.gpu-amd.yml')
    }
}

Escribir-Paso "Montando la aplicación con la IA en: $Modo (la primera vez tarda varios minutos)"
docker compose @archivos up --build -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host 'Aplicación:  http://localhost:5173' -ForegroundColor Green
Write-Host 'Estado IA:   http://localhost:8000/health/ai  (campo "device": cpu o cuda)'
Write-Host "Para pararla: docker compose $($archivos -join ' ') down"
