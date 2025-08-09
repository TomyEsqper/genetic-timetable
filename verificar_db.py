#!/usr/bin/env python
"""
Script para verificar la conexión a la base de datos y diagnosticar problemas.

Este script intenta conectarse a la base de datos configurada en settings.py
y proporciona información detallada sobre cualquier error que ocurra.

Uso:
    python verificar_db.py
"""

import os
import sys
import time
import traceback

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')

def verificar_mysql_directo():
    """Intenta conectarse directamente a MySQL sin usar Django."""
    try:
        import pymysql
        from colegio.settings import DATABASES
        
        # Obtener configuración de la base de datos
        db_config = DATABASES['default']
        host = db_config.get('HOST', 'localhost')
        port = int(db_config.get('PORT', 3306))
        user = db_config.get('USER', 'root')
        password = db_config.get('PASSWORD', '')
        database = db_config.get('NAME', '')
        
        print(f"\n[1] Intentando conexión directa a MySQL...")
        print(f"   Host: {host}")
        print(f"   Puerto: {port}")
        print(f"   Usuario: {user}")
        print(f"   Base de datos: {database}")
        
        # Intentar conexión
        start_time = time.time()
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5
        )
        end_time = time.time()
        
        print(f"\n✅ Conexión exitosa a MySQL (tiempo: {end_time - start_time:.2f}s)")
        
        # Verificar si la base de datos existe
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"\n✅ Base de datos '{database}' existe y contiene {len(tables)} tablas:")
            for table in tables:
                print(f"   - {table[0]}")
        
        connection.close()
        return True
    
    except ImportError:
        print("\n❌ No se pudo importar pymysql. Asegúrate de que esté instalado:")
        print("   pip install pymysql")
        return False
    
    except Exception as e:
        print(f"\n❌ Error al conectar directamente a MySQL: {str(e)}")
        if "Access denied" in str(e):
            print("\n🔑 Problema de credenciales detectado:")
            print("   1. Verifica que el usuario y contraseña en settings.py sean correctos")
            print("   2. Asegúrate de que el usuario tenga permisos en la base de datos")
            print("   3. Prueba conectarte manualmente con: mysql -u root -p")
        elif "Can't connect" in str(e) or "Connection refused" in str(e):
            print("\n🔌 Problema de conexión detectado:")
            print("   1. Verifica que el servidor MySQL esté en ejecución")
            print("   2. Comprueba que el host y puerto sean correctos")
            print("   3. Verifica si hay un firewall bloqueando la conexión")
        elif "Unknown database" in str(e):
            print("\n📁 Base de datos no encontrada:")
            print(f"   La base de datos '{database}' no existe. Debes crearla:")
            print(f"   CREATE DATABASE {database};")
        return False

def verificar_django_db():
    """Intenta conectarse a la base de datos usando Django."""
    try:
        print("\n[2] Intentando conexión a través de Django ORM...")
        
        # Importar Django y configurar
        import django
        django.setup()
        
        # Intentar hacer una consulta simple
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        print("\n✅ Conexión exitosa a través de Django ORM")
        
        # Verificar las aplicaciones y modelos
        from django.apps import apps
        print("\n📋 Modelos disponibles en el proyecto:")
        for app_config in apps.get_app_configs():
            models = app_config.get_models()
            if models:
                print(f"\n   📦 {app_config.label}:")
                for model in models:
                    print(f"      - {model.__name__}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Error al conectar a través de Django: {str(e)}")
        traceback.print_exc()
        return False

def verificar_sqlite():
    """Verifica si SQLite es una alternativa viable."""
    try:
        import sqlite3
        print("\n[3] Verificando disponibilidad de SQLite como alternativa...")
        
        # Verificar si sqlite3 está disponible
        sqlite_version = sqlite3.sqlite_version
        print(f"\n✅ SQLite está disponible (versión {sqlite_version})")
        
        # Verificar si podemos crear una base de datos de prueba
        test_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_sqlite.db')
        conn = sqlite3.connect(test_db_path)
        conn.close()
        os.remove(test_db_path)
        
        print("\n✅ Prueba de creación de base de datos SQLite exitosa")
        print("\n💡 Puedes usar SQLite como alternativa temporal con:")
        print("   python manage.py runserver --settings=colegio.settings_sqlite")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Error al verificar SQLite: {str(e)}")
        return False

def main():
    """Función principal que ejecuta todas las verificaciones."""
    print("="*80)
    print("VERIFICADOR DE CONEXIÓN A BASE DE DATOS".center(80))
    print("="*80)
    
    # Verificar MySQL directamente
    mysql_ok = verificar_mysql_directo()
    
    # Si MySQL está bien, verificar Django
    if mysql_ok:
        django_ok = verificar_django_db()
    else:
        django_ok = False
        print("\n⚠️ No se intentará la conexión a través de Django debido a problemas con MySQL")
    
    # Verificar SQLite como alternativa
    sqlite_ok = verificar_sqlite()
    
    # Resumen
    print("\n" + "="*80)
    print("RESUMEN DE DIAGNÓSTICO".center(80))
    print("="*80)
    
    if mysql_ok and django_ok:
        print("\n✅ TODO CORRECTO: La conexión a la base de datos funciona correctamente")
    else:
        print("\n⚠️ SE DETECTARON PROBLEMAS:")
        if not mysql_ok:
            print("   ❌ No se pudo conectar directamente a MySQL")
        if not django_ok and mysql_ok:
            print("   ❌ MySQL funciona pero Django no puede conectarse")
        
        print("\n💡 RECOMENDACIONES:")
        if not mysql_ok:
            print("   1. Revisa las credenciales en colegio/settings.py")
            print("   2. Verifica que el servidor MySQL esté en ejecución")
            print("   3. Asegúrate de que la base de datos exista")
        
        if sqlite_ok:
            print("   4. Considera usar SQLite temporalmente:")
            print("      python manage.py runserver --settings=colegio.settings_sqlite")
            print("      python manage.py migrate --settings=colegio.settings_sqlite")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()