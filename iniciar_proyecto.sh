#!/bin/bash

echo "🚀 Iniciando Generador de Horarios - Sistema Robusto"
echo "=================================================="

# Verificar si el entorno virtual existe
if [ ! -d "venv" ]; then
    echo "❌ Error: No se encontró el entorno virtual 'venv'"
    echo "   Ejecuta: python -m venv venv"
    exit 1
fi

# Activar entorno virtual
echo "📦 Activando entorno virtual..."
source venv/bin/activate

# Verificar dependencias
echo "🔍 Verificando dependencias..."
if ! python -c "import django" 2>/dev/null; then
    echo "📥 Instalando dependencias..."
    pip install -r requirements.txt
fi

# Verificar base de datos
echo "🗄️ Verificando base de datos..."
python manage.py check

# Aplicar migraciones si es necesario
echo "🔄 Aplicando migraciones..."
python manage.py migrate

# Verificar si hay datos
echo "📊 Verificando datos..."
if [ $(python manage.py shell -c "from horarios.models import Curso; print(Curso.objects.count())" 2>/dev/null) -eq 0 ]; then
    echo "📝 Cargando datos de ejemplo..."
    python cargar_datos_ejemplo.py
fi

echo ""
echo "✅ Sistema listo!"
echo ""
echo "🌐 Servidor iniciándose en: http://localhost:8000"
echo "📋 Dashboard: http://localhost:8000/horarios/"
echo "🔧 Admin: http://localhost:8000/admin/ (usuario: admin, contraseña: admin)"
echo ""
echo "⏹️ Para detener el servidor: Ctrl+C"
echo ""

# Iniciar servidor
echo "🚀 Iniciando servidor..."
python manage.py runserver 0.0.0.0:8000 