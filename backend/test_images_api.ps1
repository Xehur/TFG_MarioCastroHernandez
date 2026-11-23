# Script de prueba para endpoints de imágenes
# Este script demuestra cómo usar los endpoints de upload

Write-Host "=== Test de endpoints de imágenes ===" -ForegroundColor Green

# 1. Listar imágenes (debe estar vacío inicialmente)
Write-Host "`n1. Listando imágenes actuales..." -ForegroundColor Cyan
$images = Invoke-RestMethod -Uri "http://localhost:8000/images/" -Method GET
Write-Host "Imágenes encontradas: $($images.Count)"
$images | Format-Table

# 2. Intentar subir archivo con extensión inválida
Write-Host "`n2. Probando subida con extensión inválida (.jpg)..." -ForegroundColor Cyan
try {
    $boundary = [System.Guid]::NewGuid().ToString()
    $content = @"
--$boundary
Content-Disposition: form-data; name="file"; filename="test.jpg"
Content-Type: image/jpeg

fake content
--$boundary--
"@
    $response = Invoke-RestMethod -Uri "http://localhost:8000/images/upload" -Method POST -ContentType "multipart/form-data; boundary=$boundary" -Body $content
    Write-Host "Respuesta inesperada: Debería haber fallado" -ForegroundColor Red
} catch {
    Write-Host "Validación funcionó correctamente: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 3. Obtener info de una imagen que no existe
Write-Host "`n3. Probando GET de imagen inexistente..." -ForegroundColor Cyan
try {
    $image = Invoke-RestMethod -Uri "http://localhost:8000/images/99999" -Method GET
    Write-Host "Respuesta inesperada: Debería haber fallado" -ForegroundColor Red
} catch {
    Write-Host "Validación funcionó correctamente: Imagen no encontrada" -ForegroundColor Yellow
}

Write-Host "`n=== Tests completados ===" -ForegroundColor Green
Write-Host "Nota: Para subir un archivo WSI real, necesitas un archivo .svs, .tiff o .mrxs válido"
