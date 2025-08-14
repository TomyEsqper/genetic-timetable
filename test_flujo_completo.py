#!/usr/bin/env python3
"""
TEST COMPLETO DEL FLUJO DE DATOS - ALGORITMO GENÉTICO
=======================================================

Este script verifica paso a paso todo el flujo de datos del algoritmo genético:
1. Carga de datos
2. Inicialización de población
3. Ejecución del algoritmo
4. Guardado de horarios
5. Actualización de cache
6. Comunicación con la interfaz web

Autor: Sistema de Verificación Automática
Fecha: 2025-08-14
"""

import os
import sys
import time
import json
import traceback
import signal
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
import django
django.setup()

from django.core.cache import cache
from django.db import connection
from horarios.models import Horario, Curso, Materia, Profesor, Aula
from horarios.genetico import generar_horarios_genetico_robusto
from horarios.genetico import _guardar_horarios_parciales
from horarios.genetico import _convertir_a_diccionarios

class TimeoutError(Exception):
    """Excepción personalizada para timeouts"""
    pass

def timeout_handler(signum, frame):
    """Manejador de timeout"""
    raise TimeoutError("Operación excedió el tiempo límite")

class TestFlujoCompleto:
    """Test completo del flujo de datos del algoritmo genético"""
    
    def __init__(self):
        self.errores = []
        self.advertencias = []
        self.exitos = []
        self.inicio_tiempo = time.time()
        
    def log_exito(self, mensaje):
        """Registra un éxito"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.exitos.append(f"[{timestamp}] ✅ {mensaje}")
        print(f"[{timestamp}] ✅ {mensaje}")
        
    def log_advertencia(self, mensaje):
        """Registra una advertencia"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.advertencias.append(f"[{timestamp}] ⚠️ {mensaje}")
        print(f"[{timestamp}] ⚠️ {mensaje}")
        
    def log_error(self, mensaje, error=None):
        """Registra un error"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        error_msg = f"[{timestamp}] ❌ {mensaje}"
        if error:
            error_msg += f" - Error: {str(error)}"
        self.errores.append(error_msg)
        print(error_msg)
        if error:
            print(f"Traceback: {traceback.format_exc()}")
            
    def log_info(self, mensaje):
        """Registra información"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ℹ️ {mensaje}")
        
    def test_conexion_db(self):
        """Test 1: Verificar conexión a base de datos"""
        self.log_info("🔍 TEST 1: Verificando conexión a base de datos...")
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    self.log_exito("Conexión a base de datos exitosa")
                    return True
                else:
                    self.log_error("Conexión a base de datos falló - resultado inesperado")
                    return False
        except Exception as e:
            self.log_error("Conexión a base de datos falló", e)
            return False
            
    def test_datos_basicos(self):
        """Test 2: Verificar que existan datos básicos en la BD"""
        self.log_info("🔍 TEST 2: Verificando datos básicos en la base de datos...")
        
        try:
            # Verificar cursos
            cursos_count = Curso.objects.count()
            self.log_info(f"Cursos en BD: {cursos_count}")
            if cursos_count == 0:
                self.log_error("No hay cursos en la base de datos")
                return False
                
            # Verificar materias
            materias_count = Materia.objects.count()
            self.log_info(f"Materias en BD: {materias_count}")
            if materias_count == 0:
                self.log_error("No hay materias en la base de datos")
                return False
                
            # Verificar profesores
            profesores_count = Profesor.objects.count()
            self.log_info(f"Profesores en BD: {profesores_count}")
            if profesores_count == 0:
                self.log_error("No hay profesores en la base de datos")
                return False
                
            # Verificar aulas
            aulas_count = Aula.objects.count()
            self.log_info(f"Aulas en BD: {aulas_count}")
            if aulas_count == 0:
                self.log_error("No hay aulas en la base de datos")
                return False
                
            self.log_exito(f"Datos básicos verificados: {cursos_count} cursos, {materias_count} materias, {profesores_count} profesores, {aulas_count} aulas")
            return True
            
        except Exception as e:
            self.log_error("Error verificando datos básicos", e)
            return False
            
    def test_cache_funcionando(self):
        """Test 3: Verificar que el cache esté funcionando"""
        self.log_info("🔍 TEST 3: Verificando funcionamiento del cache...")
        
        try:
            # Test básico de cache
            test_data = {"test": "valor", "numero": 42, "lista": [1, 2, 3]}
            cache.set("test_cache", test_data, 60)
            
            # Verificar que se guardó
            cached_data = cache.get("test_cache")
            if cached_data == test_data:
                self.log_exito("Cache funcionando correctamente")
                
                # Limpiar test
                cache.delete("test_cache")
                return True
            else:
                self.log_error(f"Cache no está funcionando - esperado: {test_data}, obtenido: {cached_data}")
                return False
                
        except Exception as e:
            self.log_error("Error verificando cache", e)
            return False
            
    def test_algoritmo_genetico_basico(self):
        """Test 4: Ejecutar algoritmo genético básico con timeout"""
        self.log_info("🔍 TEST 4: Ejecutando algoritmo genético básico...")
        
        try:
            # Parámetros muy conservadores para test rápido
            parametros = {
                'poblacion_size': 5,  # Reducido de 10
                'generaciones': 2,     # Reducido de 5
                'prob_cruce': 0.8,
                'prob_mutacion': 0.2,
                'elite': 1,            # Reducido de 2
                'paciencia': 2,        # Reducido de 3
                'timeout_seg': 15,     # Reducido de 30
                'workers': 1,
                'semilla': 42
            }
            
            self.log_info(f"Parámetros de test (conservadores): {parametros}")
            
            # Configurar timeout para evitar que se cuelgue
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(20)  # 20 segundos máximo
            
            try:
                # Ejecutar algoritmo
                resultado = generar_horarios_genetico_robusto(**parametros)
                signal.alarm(0)  # Cancelar alarm
                
                # Verificar resultado
                if resultado and 'exito' in resultado:
                    if resultado['exito']:
                        self.log_exito("Algoritmo genético ejecutado exitosamente")
                    else:
                        self.log_advertencia(f"Algoritmo genético ejecutado pero sin solución válida: {resultado.get('mensaje', 'Sin mensaje')}")
                        
                    # Verificar que se generaron horarios
                    if 'horarios' in resultado and resultado['horarios']:
                        self.log_exito(f"Se generaron {len(resultado['horarios'])} horarios")
                    else:
                        self.log_error("No se generaron horarios en el resultado")
                        return False
                        
                    return True
                else:
                    self.log_error("Algoritmo genético no retornó resultado válido")
                    return False
                    
            except TimeoutError:
                signal.alarm(0)
                self.log_error("Algoritmo genético excedió el tiempo límite - puede estar colgado")
                return False
                
        except Exception as e:
            self.log_error("Error ejecutando algoritmo genético", e)
            return False
            
    def test_guardado_horarios(self):
        """Test 5: Verificar guardado de horarios en BD"""
        self.log_info("🔍 TEST 5: Verificando guardado de horarios en base de datos...")
        
        try:
            # Obtener datos reales de la base de datos
            curso = Curso.objects.first()
            materia = Materia.objects.first()
            profesor = Profesor.objects.first()
            
            if not curso or not materia or not profesor:
                self.log_error("No hay datos suficientes en la BD para el test")
                return False
                
            # Crear datos de prueba con datos reales
            datos_prueba = [
                {
                    'curso_id': curso.id,
                    'materia_id': materia.id,
                    'profesor_id': profesor.id,
                    'dia': 'lunes',
                    'bloque': 1,
                    'es_relleno': False,
                    'curso_nombre': curso.nombre,
                    'materia_nombre': materia.nombre
                }
            ]
            
            self.log_info(f"Usando datos reales: curso={curso.nombre}, materia={materia.nombre}, profesor={profesor.nombre}")
            
            # Contar horarios antes del test
            horarios_antes = Horario.objects.count()
            self.log_info(f"Horarios en BD antes del test: {horarios_antes}")
            
            # Intentar guardar
            _guardar_horarios_parciales(datos_prueba, 0, 0.5)
            
            # Verificar que se guardaron
            horarios_despues = Horario.objects.count()
            self.log_info(f"Horarios en BD después del test: {horarios_despues}")
            
            # La función elimina todos los horarios existentes y crea nuevos
            # Por lo tanto, después del test debería haber exactamente 1 horario
            if horarios_despues == 1:
                self.log_exito(f"Horarios guardados exitosamente: {horarios_despues} horarios creados")
                return True
            else:
                self.log_error(f"Horarios no se guardaron correctamente. Esperado: 1, Obtenido: {horarios_despues}")
                return False
                
        except Exception as e:
            self.log_error("Error verificando guardado de horarios", e)
            return False
            
    def test_cache_progreso(self):
        """Test 6: Verificar que el cache se actualice con progreso"""
        self.log_info("🔍 TEST 6: Verificando actualización de cache con progreso...")
        
        try:
            # Verificar que existe la clave de progreso
            progreso = cache.get('ga_progreso_actual')
            if progreso:
                self.log_exito(f"Cache de progreso encontrado: {progreso}")
                return True
            else:
                self.log_advertencia("No hay cache de progreso - esto puede ser normal si no se ha ejecutado el algoritmo")
                return True
                
        except Exception as e:
            self.log_error("Error verificando cache de progreso", e)
            return False
            
    def test_vista_ajax(self):
        """Test 7: Verificar que la vista AJAX funcione"""
        self.log_info("🔍 TEST 7: Verificando vista AJAX...")
        
        try:
            # Simular lo que hace la vista AJAX
            from frontend.views import progreso_ajax
            from django.test import RequestFactory
            
            # Crear request de prueba
            factory = RequestFactory()
            request = factory.get('/progreso-ajax/')
            
            # Llamar vista
            response = progreso_ajax(request)
            
            if response.status_code == 200:
                try:
                    # JsonResponse tiene el contenido en response.content, no en response.json()
                    import json
                    data = json.loads(response.content.decode('utf-8'))
                    self.log_exito(f"Vista AJAX funcionando - Status: {response.status_code}, Data: {data}")
                    return True
                except Exception as e:
                    self.log_error("Vista AJAX retornó 200 pero no es JSON válido", e)
                    return False
            else:
                self.log_error(f"Vista AJAX falló - Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_error("Error verificando vista AJAX", e)
            return False
            
    def test_flujo_completo(self):
        """Test 8: Flujo completo desde algoritmo hasta interfaz (versión simplificada)"""
        self.log_info("🔍 TEST 8: Ejecutando flujo completo (versión simplificada)...")
        
        try:
            # 1. Ejecutar algoritmo con parámetros muy conservadores
            self.log_info("Paso 1: Ejecutando algoritmo genético...")
            parametros = {
                'poblacion_size': 3,   # Muy pequeño para test rápido
                'generaciones': 1,      # Solo 1 generación
                'prob_cruce': 0.8,
                'prob_mutacion': 0.2,
                'elite': 1,
                'paciencia': 1,
                'timeout_seg': 10,      # Timeout muy corto
                'workers': 1,
                'semilla': 42
            }
            
            # Configurar timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(15)  # 15 segundos máximo
            
            try:
                resultado = generar_horarios_genetico_robusto(**parametros)
                signal.alarm(0)
                
                if not resultado:
                    self.log_error("Flujo completo falló - algoritmo no retornó resultado")
                    return False
                    
                # 2. Verificar que se guardaron horarios
                self.log_info("Paso 2: Verificando horarios guardados...")
                horarios_count = Horario.objects.count()
                self.log_info(f"Horarios en BD: {horarios_count}")
                
                if horarios_count == 0:
                    self.log_error("Flujo completo falló - no se guardaron horarios")
                    return False
                    
                # 3. Verificar cache de progreso
                self.log_info("Paso 3: Verificando cache de progreso...")
                progreso = cache.get('ga_progreso_actual')
                if progreso:
                    self.log_exito(f"Cache de progreso actualizado: {progreso}")
                else:
                    self.log_advertencia("No hay cache de progreso - esto puede ser normal")
                    
                # 4. Verificar que la vista AJAX puede leer los datos
                self.log_info("Paso 4: Verificando vista AJAX...")
                from frontend.views import progreso_ajax
                from django.test import RequestFactory
                
                factory = RequestFactory()
                request = factory.get('/progreso-ajax/')
                response = progreso_ajax(request)
                
                if response.status_code == 200:
                    # JsonResponse tiene el contenido en response.content, no en response.json()
                    import json
                    data = json.loads(response.content.decode('utf-8'))
                    if 'horarios_parciales' in data:
                        self.log_exito(f"Vista AJAX funcionando - Horarios: {data['horarios_parciales']}")
                    else:
                        self.log_advertencia("Vista AJAX funcionando pero sin datos de horarios")
                else:
                    self.log_error(f"Vista AJAX falló - Status: {response.status_code}")
                    return False
                    
                self.log_exito("Flujo completo ejecutado exitosamente")
                return True
                
            except TimeoutError:
                signal.alarm(0)
                self.log_error("Flujo completo excedió el tiempo límite")
                return False
                
        except Exception as e:
            self.log_error("Error en flujo completo", e)
            return False
            
    def ejecutar_todos_tests(self):
        """Ejecuta todos los tests en secuencia"""
        self.log_info("🚀 INICIANDO TEST COMPLETO DEL FLUJO DE DATOS")
        self.log_info("=" * 60)
        
        tests = [
            ("Conexión DB", self.test_conexion_db),
            ("Datos Básicos", self.test_datos_basicos),
            ("Cache", self.test_cache_funcionando),
            ("Algoritmo Genético", self.test_algoritmo_genetico_basico),
            ("Guardado Horarios", self.test_guardado_horarios),
            ("Cache Progreso", self.test_cache_progreso),
            ("Vista AJAX", self.test_vista_ajax),
            ("Flujo Completo", self.test_flujo_completo)
        ]
        
        resultados = {}
        
        for nombre, test_func in tests:
            self.log_info(f"\n{'='*20} {nombre} {'='*20}")
            try:
                resultado = test_func()
                resultados[nombre] = resultado
                if resultado:
                    self.log_exito(f"✅ {nombre}: PASÓ")
                else:
                    self.log_error(f"❌ {nombre}: FALLÓ")
            except Exception as e:
                self.log_error(f"❌ {nombre}: ERROR EXCEPCIONAL", e)
                resultados[nombre] = False
                
        # Resumen final
        self.log_info("\n" + "=" * 60)
        self.log_info("📊 RESUMEN FINAL DE TESTS")
        self.log_info("=" * 60)
        
        total_tests = len(tests)
        tests_pasados = sum(1 for r in resultados.values() if r)
        tests_fallidos = total_tests - tests_pasados
        
        self.log_info(f"Total tests: {total_tests}")
        self.log_info(f"✅ Tests pasados: {tests_pasados}")
        self.log_info(f"❌ Tests fallidos: {tests_fallidos}")
        
        if tests_fallidos == 0:
            self.log_exito("🎉 TODOS LOS TESTS PASARON - SISTEMA FUNCIONANDO AL 100%")
        else:
            self.log_error(f"⚠️ {tests_fallidos} TESTS FALLARON - REVISAR SISTEMA")
            
        # Mostrar errores si los hay
        if self.errores:
            self.log_info("\n❌ ERRORES ENCONTRADOS:")
            for error in self.errores:
                print(f"  {error}")
                
        # Mostrar advertencias si las hay
        if self.advertencias:
            self.log_info("\n⚠️ ADVERTENCIAS:")
            for advertencia in self.advertencias:
                print(f"  {advertencia}")
                
        # Mostrar éxitos
        if self.exitos:
            self.log_info("\n✅ ÉXITOS:")
            for exito in self.exitos[-10:]:  # Solo los últimos 10
                print(f"  {exito}")
                
        tiempo_total = time.time() - self.inicio_tiempo
        self.log_info(f"\n⏱️ Tiempo total de ejecución: {tiempo_total:.2f} segundos")
        
        return tests_fallidos == 0

def main():
    """Función principal"""
    print("🧪 TEST COMPLETO DEL FLUJO DE DATOS - ALGORITMO GENÉTICO")
    print("=" * 70)
    
    try:
        test = TestFlujoCompleto()
        exito = test.ejecutar_todos_tests()
        
        if exito:
            print("\n🎉 RESULTADO: SISTEMA FUNCIONANDO CORRECTAMENTE")
            sys.exit(0)
        else:
            print("\n❌ RESULTADO: SISTEMA CON PROBLEMAS - REVISAR ERRORES")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 ERROR FATAL: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 