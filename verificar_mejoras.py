#!/usr/bin/env python3
"""
Script de verificación rápida de las mejoras implementadas.
Ejecutar: python verificar_mejoras.py
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def verificar_archivos():
    """Verifica que los archivos principales existan."""
    print("🔍 Verificando archivos principales...")
    
    archivos_requeridos = [
        "requirements.txt",
        "horarios/models.py",
        "horarios/genetico.py",
        "api/views.py",
        "horarios/management/commands/cargar_dataset.py",
        "horarios/tests/test_genetico.py",
        "horarios/exportador.py",
        "pytest.ini",
        "README_MEJORAS.md"
    ]
    
    faltantes = []
    for archivo in archivos_requeridos:
        if not os.path.exists(archivo):
            faltantes.append(archivo)
        else:
            print(f"  ✅ {archivo}")
    
    if faltantes:
        print(f"  ❌ Archivos faltantes: {faltantes}")
        return False
    
    print("  ✅ Todos los archivos principales existen")
    return True

def verificar_dependencias():
    """Verifica que las dependencias estén en requirements.txt."""
    print("\n🔍 Verificando dependencias...")
    
    dependencias_requeridas = [
        "numba",
        "django-redis",
        "pytest-django",
        "numpy",
        "djangorestframework"
    ]
    
    try:
        with open("requirements.txt", "r") as f:
            contenido = f.read()
        
        faltantes = []
        for dep in dependencias_requeridas:
            if dep not in contenido:
                faltantes.append(dep)
            else:
                print(f"  ✅ {dep}")
        
        if faltantes:
            print(f"  ❌ Dependencias faltantes: {faltantes}")
            return False
        
        print("  ✅ Todas las dependencias están presentes")
        return True
        
    except FileNotFoundError:
        print("  ❌ No se encontró requirements.txt")
        return False

def verificar_modelos():
    """Verifica que los modelos tengan las restricciones correctas."""
    print("\n🔍 Verificando modelos...")
    
    try:
        with open("horarios/models.py", "r") as f:
            contenido = f.read()
        
        verificaciones = [
            ("unique_together en Horario", "unique_together"),
            ("aula_fija en Curso", "aula_fija"),
            ("unique_together en BloqueHorario", "unique_together"),
            ("Meta class en Horario", "class Meta:"),
            ("Meta class en BloqueHorario", "class Meta:")
        ]
        
        faltantes = []
        for desc, patron in verificaciones:
            if patron in contenido:
                print(f"  ✅ {desc}")
            else:
                faltantes.append(desc)
        
        if faltantes:
            print(f"  ❌ Elementos faltantes: {faltantes}")
            return False
        
        print("  ✅ Todas las restricciones de modelo están presentes")
        return True
        
    except FileNotFoundError:
        print("  ❌ No se encontró horarios/models.py")
        return False

def verificar_genetico():
    """Verifica que el algoritmo genético tenga las optimizaciones."""
    print("\n🔍 Verificando algoritmo genético...")
    
    try:
        with open("horarios/genetico.py", "r") as f:
            contenido = f.read()
        
        verificaciones = [
            ("ProcessPoolExecutor", "ProcessPoolExecutor"),
            ("@njit", "@njit"),
            ("nopython=True", "nopython=True"),
            ("fastmath=True", "fastmath=True"),
            ("timeout_seg", "timeout_seg"),
            ("logs JSON", "logs_generacion"),
            ("return log_final", "return log_final")
        ]
        
        faltantes = []
        for desc, patron in verificaciones:
            if patron in contenido:
                print(f"  ✅ {desc}")
            else:
                faltantes.append(desc)
        
        if faltantes:
            print(f"  ❌ Optimizaciones faltantes: {faltantes}")
            return False
        
        print("  ✅ Todas las optimizaciones del GA están presentes")
        return True
        
    except FileNotFoundError:
        print("  ❌ No se encontró horarios/genetico.py")
        return False

def verificar_api():
    """Verifica que la API tenga las mejoras."""
    print("\n🔍 Verificando API...")
    
    try:
        with open("api/views.py", "r") as f:
            contenido = f.read()
        
        verificaciones = [
            ("validar_prerrequisitos", "_validar_prerrequisitos"),
            ("status.HTTP_409_CONFLICT", "HTTP_409_CONFLICT"),
            ("metricas", "metricas"),
            ("timeout_seg", "timeout_seg"),
            ("semilla", "semilla"),
            ("workers", "workers")
        ]
        
        faltantes = []
        for desc, patron in verificaciones:
            if patron in contenido:
                print(f"  ✅ {desc}")
            else:
                faltantes.append(desc)
        
        if faltantes:
            print(f"  ❌ Mejoras de API faltantes: {faltantes}")
            return False
        
        print("  ✅ Todas las mejoras de API están presentes")
        return True
        
    except FileNotFoundError:
        print("  ❌ No se encontró api/views.py")
        return False

def verificar_tests():
    """Verifica que los tests estén completos."""
    print("\n🔍 Verificando tests...")
    
    try:
        with open("horarios/tests/test_genetico.py", "r") as f:
            contenido = f.read()
        
        verificaciones = [
            ("TestAlgoritmoGenetico", "class TestAlgoritmoGenetico"),
            ("TestRendimiento", "class TestRendimiento"),
            ("TestValidaciones", "class TestValidaciones"),
            ("test_restricciones_sin_solapes", "test_restricciones_sin_solapes"),
            ("test_rendimiento_dataset_pequeno", "test_rendimiento_dataset_pequeno"),
            ("test_paralelismo", "test_paralelismo")
        ]
        
        faltantes = []
        for desc, patron in verificaciones:
            if patron in contenido:
                print(f"  ✅ {desc}")
            else:
                faltantes.append(desc)
        
        if faltantes:
            print(f"  ❌ Tests faltantes: {faltantes}")
            return False
        
        print("  ✅ Todos los tests están presentes")
        return True
        
    except FileNotFoundError:
        print("  ❌ No se encontró horarios/tests/test_genetico.py")
        return False

def verificar_management():
    """Verifica que el comando de management esté presente."""
    print("\n🔍 Verificando comando de management...")
    
    try:
        with open("horarios/management/commands/cargar_dataset.py", "r") as f:
            contenido = f.read()
        
        verificaciones = [
            ("class Command", "class Command"),
            ("--size", "--size"),
            ("--seed", "--seed"),
            ("--force", "--force"),
            ("S, M, L, XL", "choices=['S', 'M', 'L', 'XL']"),
            ("cargar_dataset", "cargar_dataset")
        ]
        
        faltantes = []
        for desc, patron in verificaciones:
            if patron in contenido:
                print(f"  ✅ {desc}")
            else:
                faltantes.append(desc)
        
        if faltantes:
            print(f"  ❌ Elementos del comando faltantes: {faltantes}")
            return False
        
        print("  ✅ Comando de management está completo")
        return True
        
    except FileNotFoundError:
        print("  ❌ No se encontró el comando de management")
        return False

def verificar_exportador():
    """Verifica que el exportador esté presente."""
    print("\n🔍 Verificando exportador...")
    
    try:
        with open("horarios/exportador.py", "r") as f:
            contenido = f.read()
        
        verificaciones = [
            ("exportar_horario_csv", "exportar_horario_csv"),
            ("exportar_horario_por_curso_csv", "exportar_horario_por_curso_csv"),
            ("exportar_horario_por_profesor_csv", "exportar_horario_por_profesor_csv"),
            ("generar_resumen_horario", "generar_resumen_horario"),
            ("HttpResponse", "HttpResponse"),
            ("Content-Disposition", "Content-Disposition")
        ]
        
        faltantes = []
        for desc, patron in verificaciones:
            if patron in contenido:
                print(f"  ✅ {desc}")
            else:
                faltantes.append(desc)
        
        if faltantes:
            print(f"  ❌ Funciones de exportación faltantes: {faltantes}")
            return False
        
        print("  ✅ Exportador está completo")
        return True
        
    except FileNotFoundError:
        print("  ❌ No se encontró horarios/exportador.py")
        return False

def main():
    """Función principal de verificación."""
    print("🚀 Verificación de Mejoras Implementadas")
    print("=" * 50)
    
    verificaciones = [
        verificar_archivos,
        verificar_dependencias,
        verificar_modelos,
        verificar_genetico,
        verificar_api,
        verificar_tests,
        verificar_management,
        verificar_exportador
    ]
    
    resultados = []
    for verificacion in verificaciones:
        try:
            resultado = verificacion()
            resultados.append(resultado)
        except Exception as e:
            print(f"  ❌ Error en verificación: {e}")
            resultados.append(False)
    
    print("\n" + "=" * 50)
    print("📊 RESUMEN DE VERIFICACIÓN")
    print("=" * 50)
    
    total = len(resultados)
    exitosos = sum(resultados)
    
    print(f"✅ Verificaciones exitosas: {exitosos}/{total}")
    print(f"❌ Verificaciones fallidas: {total - exitosos}/{total}")
    
    if exitosos == total:
        print("\n🎉 ¡TODAS LAS MEJORAS HAN SIDO IMPLEMENTADAS CORRECTAMENTE!")
        print("\n📋 Próximos pasos:")
        print("1. Instalar dependencias: pip install -r requirements.txt")
        print("2. Crear migraciones: python manage.py makemigrations")
        print("3. Aplicar migraciones: python manage.py migrate")
        print("4. Cargar dataset: python manage.py cargar_dataset --size M")
        print("5. Ejecutar tests: pytest -v")
        print("6. Generar horarios: curl -X POST http://localhost:8000/api/generar-horarios/")
        return 0
    else:
        print("\n⚠️  Algunas verificaciones fallaron. Revisar los errores arriba.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 