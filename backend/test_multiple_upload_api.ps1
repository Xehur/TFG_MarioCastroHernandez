# Script de prueba para upload múltiple de imágenes (drag & drop)
# Este script demuestra cómo usar el endpoint de upload múltiple

Write-Host "=== Test de upload múltiple de imágenes ===" -ForegroundColor Green

# URL del endpoint
$uri = "http://localhost:8000/images/upload-multiple"

# Ejemplo 1: Subir múltiples archivos (ajusta las rutas según tus archivos)
Write-Host "`n1. Probando upload múltiple con archivos reales..." -ForegroundColor Cyan
Write-Host "NOTA: Necesitas archivos WSI reales (.svs, .tiff, .mrxs) para este test" -ForegroundColor Yellow

# Si tienes archivos WSI, descomenta y ajusta estas líneas:
# $files = @(
#     @{name='files'; filename='imagen1.svs'; filepath='C:\ruta\a\imagen1.svs'},
#     @{name='files'; filename='imagen2.svs'; filepath='C:\ruta\a\imagen2.svs'},
#     @{name='files'; filename='imagen3.tiff'; filepath='C:\ruta\a\imagen3.tiff'}
# )
#
# $form = @{}
# foreach ($file in $files) {
#     $form[$file.name] = Get-Item -Path $file.filepath
# }
#
# $response = Invoke-RestMethod -Uri $uri -Method Post -Form $form
# $response | ConvertTo-Json -Depth 5

# Ejemplo 2: Ver la respuesta esperada del endpoint
Write-Host "`n2. Estructura de respuesta esperada:" -ForegroundColor Cyan
$expectedResponse = @{
    total = 3
    successful = 2
    failed = 1
    results = @(
        @{
            filename = "imagen1.svs"
            success = $true
            message = "Archivo procesado exitosamente"
            image = @{
                id = 1
                filename = "imagen1.svs"
                width = 35868
                height = 16704
                level_count = 3
                file_size_mb = 83.4
            }
        },
        @{
            filename = "imagen2.jpg"
            success = $false
            message = "Formato no soportado"
            error = "Formato no soportado. Permitidos: .svs, .tiff, .tif, .mrxs"
        },
        @{
            filename = "imagen3.tiff"
            success = $true
            message = "Archivo procesado exitosamente"
            image = @{
                id = 2
                filename = "imagen3.tiff"
                width = 24000
                height = 18000
                level_count = 4
                file_size_mb = 120.5
            }
        }
    )
}

$expectedResponse | ConvertTo-Json -Depth 5

# Ejemplo 3: Beneficios del endpoint múltiple
Write-Host "`n3. Beneficios del endpoint de upload múltiple:" -ForegroundColor Cyan
Write-Host "  - Soporta drag & drop de múltiples archivos desde el frontend" -ForegroundColor White
Write-Host "  - Procesa cada archivo independientemente" -ForegroundColor White
Write-Host "  - Retorna resultado detallado para cada archivo" -ForegroundColor White
Write-Host "  - HTTP 207 Multi-Status: algunos archivos pueden tener éxito y otros fallar" -ForegroundColor White
Write-Host "  - Validación individual: extensión, tamaño, duplicados, metadatos WSI" -ForegroundColor White
Write-Host "  - Los archivos exitosos se guardan aunque otros fallen" -ForegroundColor White

# Ejemplo 4: Uso desde interfaz web
Write-Host "`n4. Probar desde la interfaz Swagger:" -ForegroundColor Cyan
Write-Host "  1. Abrir: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  2. Buscar endpoint: POST /images/upload-multiple" -ForegroundColor White
Write-Host "  3. Clic en 'Try it out'" -ForegroundColor White
Write-Host "  4. Clic en 'Add string item' para cada archivo" -ForegroundColor White
Write-Host "  5. Seleccionar múltiples archivos WSI" -ForegroundColor White
Write-Host "  6. Clic en 'Execute'" -ForegroundColor White
Write-Host "  7. Ver respuesta detallada con status de cada archivo" -ForegroundColor White

Write-Host "`n=== Guía completa ===" -ForegroundColor Green
