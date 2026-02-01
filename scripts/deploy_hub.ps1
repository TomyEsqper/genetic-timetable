Write-Host "🚀 Iniciando proceso de construcción y subida a Docker Hub..." -ForegroundColor Cyan

# 1. Verificar si el usuario está logueado
Write-Host "1. Verificando login en Docker Hub..."
docker login
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error: Debes iniciar sesión en Docker Hub primero." -ForegroundColor Red
    exit 1
}

# 2. Pedir usuario de Docker Hub si no está configurado
$env:DOCKER_HUB_USER = Read-Host "Ingresa tu usuario de Docker Hub (ej: tomyesqper)"
if (-not $env:DOCKER_HUB_USER) {
    Write-Host "❌ Error: El usuario es requerido." -ForegroundColor Red
    exit 1
}

# 3. Construir imágenes
Write-Host "2. Construyendo imágenes (esto usará la potencia de tu PC)..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml build

# 4. Subir imágenes
Write-Host "3. Subiendo imágenes a la nube..." -ForegroundColor Yellow
docker compose -f docker-compose.prod.yml push

Write-Host "✅ ¡Listo! Imágenes subidas exitosamente." -ForegroundColor Green
Write-Host "Ahora ve a tu servidor AWS y ejecuta:"
Write-Host "export DOCKER_HUB_USER=$env:DOCKER_HUB_USER" -ForegroundColor Cyan
Write-Host "docker compose -f docker-compose.prod.yml pull" -ForegroundColor Cyan
Write-Host "docker compose -f docker-compose.prod.yml up -d" -ForegroundColor Cyan
