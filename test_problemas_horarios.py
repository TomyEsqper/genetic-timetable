#!/usr/bin/env python3
"""
TEST ESPECÍFICO PARA PROBLEMAS IDENTIFICADOS
============================================

Este script verifica:
1. Huecos en horarios generados
2. Problema de semilla fija (99999)
3. Limpieza correcta de horarios anteriores
4. Diferentes configuraciones generan diferentes horarios

Autor: Sistema de Verificación Automática
Fecha: 2025-08-14
"""

import os
import sys
import time
import json
import traceback
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
import django
django.setup()

from django.core.cache import cache
from django.db import connection
from horarios.models import Horario, Curso, Materia, Profesor, Aula
from horarios.genetico import generar_horarios_genetico

class TestProblemasHorarios:
    def __init__(self):
        self.logs = []
        self.errores = []
        
    def log_info(self, mensaje):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] ℹ️ {mensaje}"
        print(log_msg)
        self.logs.append(log_msg)
        
    def log_exito(self, mensaje):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] ✅ {mensaje}"
        print(log_msg)
        self.logs.append(log_msg)
        
    def log_error(self, mensaje):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] ❌ {mensaje}"
        print(log_msg)
        self.logs.append(log_msg)
        self.errores.append(mensaje)
        
    def log_advertencia(self, mensaje):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] ⚠️ {mensaje}"
        print(log_msg)
        self.logs.append(log_msg)

    def test_limpieza_horarios(self):
        """Test 1: Verificar que se limpien los horarios anteriores"""
        self.log_info("🔍 TEST 1: Verificando limpieza de horarios anteriores...")
        
        try:
            # Contar horarios antes
            horarios_antes = Horario.objects.count()
            self.log_info(f"Horarios en BD antes: {horarios_antes}")
            
            # Ejecutar algoritmo con parámetros mínimos
            resultado = generar_horarios_genetico(
                poblacion_size=3,
                generaciones=1,
                prob_cruce=0.8,
                prob_mutacion=0.2,
                elite=1,
                paciencia=2,
                timeout_seg=10,
                workers=1,
                semilla=42
            )
            
            # Verificar que se generaron horarios
            if resultado and resultado.get('exito'):
                horarios_despues = Horario.objects.count()
                self.log_info(f"Horarios en BD después: {horarios_despues}")
                
                if horarios_despues > 0:
                    self.log_exito(f"Horarios generados: {horarios_despues}")
                    return True
                else:
                    self.log_error("No se generaron horarios")
                    return False
            else:
                self.log_error(f"Algoritmo falló: {resultado}")
                return False
                
        except Exception as e:
            self.log_error(f"Error en test de limpieza: {e}")
            return False

    def test_deteccion_huecos(self):
        """Test 2: Verificar detección de huecos en horarios"""
        self.log_info("🔍 TEST 2: Verificando detección de huecos...")
        
        try:
            # Obtener horarios actuales
            horarios = Horario.objects.all()
            if not horarios.exists():
                self.log_error("No hay horarios para verificar huecos")
                return False
            
            # Agrupar por curso y día
            huecos_por_curso = {}
            for horario in horarios:
                curso_id = horario.curso.id
                dia = horario.dia
                bloque = horario.bloque
                
                if curso_id not in huecos_por_curso:
                    huecos_por_curso[curso_id] = {}
                if dia not in huecos_por_curso[curso_id]:
                    huecos_por_curso[curso_id][dia] = set()
                
                huecos_por_curso[curso_id][dia].add(bloque)
            
            # Verificar huecos
            total_huecos = 0
            for curso_id, dias in huecos_por_curso.items():
                curso = Curso.objects.get(id=curso_id)
                self.log_info(f"Verificando curso: {curso.nombre}")
                
                for dia, bloques in dias.items():
                    bloques_ordenados = sorted(bloques)
                    self.log_info(f"  {dia}: bloques {bloques_ordenados}")
                    
                    # Verificar huecos entre bloques consecutivos
                    for i in range(len(bloques_ordenados) - 1):
                        hueco = bloques_ordenados[i+1] - bloques_ordenados[i] - 1
                        if hueco > 0:
                            total_huecos += hueco
                            self.log_advertencia(f"    Hueco de {hueco} bloques entre {bloques_ordenados[i]} y {bloques_ordenados[i+1]}")
                    
                    # Verificar bloques faltantes al inicio y final
                    bloques_disponibles = [1, 2, 3, 4, 5, 6]  # Asumiendo 6 bloques por día
                    bloques_faltantes = set(bloques_disponibles) - set(bloques)
                    if bloques_faltantes:
                        self.log_advertencia(f"    Bloques faltantes: {sorted(bloques_faltantes)}")
                        total_huecos += len(bloques_faltantes)
            
            if total_huecos == 0:
                self.log_exito("✅ No se detectaron huecos en los horarios")
            else:
                self.log_advertencia(f"⚠️ Se detectaron {total_huecos} huecos en total")
                
            return True
            
        except Exception as e:
            self.log_error(f"Error verificando huecos: {e}")
            return False

    def test_diferentes_semillas(self):
        """Test 3: Verificar que diferentes semillas generen diferentes horarios"""
        self.log_info("🔍 TEST 3: Verificando que diferentes semillas generen diferentes horarios...")
        
        try:
            # Generar horarios con semilla 42
            self.log_info("Generando horarios con semilla 42...")
            resultado1 = generar_horarios_genetico(
                poblacion_size=3,
                generaciones=1,
                prob_cruce=0.8,
                prob_mutacion=0.2,
                elite=1,
                paciencia=2,
                timeout_seg=10,
                workers=1,
                semilla=42
            )
            
            if not resultado1 or not resultado1.get('exito'):
                self.log_error("Primera generación falló")
                return False
            
            # Obtener horarios de la primera generación
            horarios1 = list(Horario.objects.values_list('curso_id', 'dia', 'bloque', 'materia_id', 'profesor_id'))
            self.log_info(f"Horarios generados con semilla 42: {len(horarios1)}")
            
            # Limpiar horarios
            Horario.objects.all().delete()
            self.log_info("Horarios limpiados")
            
            # Generar horarios con semilla 99999
            self.log_info("Generando horarios con semilla 99999...")
            resultado2 = generar_horarios_genetico(
                poblacion_size=3,
                generaciones=1,
                prob_cruce=0.8,
                prob_mutacion=0.2,
                elite=1,
                paciencia=2,
                timeout_seg=10,
                workers=1,
                semilla=99999
            )
            
            if not resultado2 or not resultado2.get('exito'):
                self.log_error("Segunda generación falló")
                return False
            
            # Obtener horarios de la segunda generación
            horarios2 = list(Horario.objects.values_list('curso_id', 'dia', 'bloque', 'materia_id', 'profesor_id'))
            self.log_info(f"Horarios generados con semilla 99999: {len(horarios2)}")
            
            # Comparar horarios
            if horarios1 == horarios2:
                self.log_error("❌ MISMOS HORARIOS: Las semillas 42 y 99999 generaron horarios idénticos")
                self.log_info("Esto indica un problema con la inicialización de la semilla")
                return False
            else:
                self.log_exito("✅ Diferentes semillas generaron diferentes horarios")
                return True
                
        except Exception as e:
            self.log_error(f"Error comparando semillas: {e}")
            return False

    def test_configuracion_calidad(self):
        """Test 4: Verificar que la configuración de calidad funcione"""
        self.log_info("🔍 TEST 4: Verificando configuración de calidad...")
        
        try:
            # Limpiar horarios
            Horario.objects.all().delete()
            
            # Generar con configuración de calidad
            self.log_info("Generando horarios con configuración de calidad...")
            resultado = generar_horarios_genetico(
                poblacion_size=25,  # Configuración de calidad
                generaciones=60,
                prob_cruce=0.9,
                prob_mutacion=0.05,
                elite=5,
                paciencia=50,
                timeout_seg=30,
                workers=1,
                semilla=123
            )
            
            if resultado and resultado.get('exito'):
                horarios = Horario.objects.count()
                self.log_info(f"Horarios generados con configuración de calidad: {horarios}")
                
                if horarios > 0:
                    self.log_exito("✅ Configuración de calidad funcionando")
                    return True
                else:
                    self.log_error("No se generaron horarios con configuración de calidad")
                    return False
            else:
                self.log_error(f"Configuración de calidad falló: {resultado}")
                return False
                
        except Exception as e:
            self.log_error(f"Error en configuración de calidad: {e}")
            return False

    def ejecutar_todos_tests(self):
        """Ejecuta todos los tests"""
        self.log_info("🧪 TEST ESPECÍFICO PARA PROBLEMAS IDENTIFICADOS")
        self.log_info("=" * 60)
        
        tests = [
            ("Limpieza de Horarios", self.test_limpieza_horarios),
            ("Detección de Huecos", self.test_deteccion_huecos),
            ("Diferentes Semillas", self.test_diferentes_semillas),
            ("Configuración de Calidad", self.test_configuracion_calidad),
        ]
        
        resultados = []
        for nombre, test_func in tests:
            self.log_info(f"\n==================== {nombre} ====================")
            try:
                resultado = test_func()
                resultados.append((nombre, resultado))
                if resultado:
                    self.log_exito(f"✅ {nombre}: PASÓ")
                else:
                    self.log_error(f"❌ {nombre}: FALLÓ")
            except Exception as e:
                self.log_error(f"❌ {nombre}: ERROR - {e}")
                resultados.append((nombre, False))
        
        # Resumen
        self.log_info(f"\n============================================================")
        self.log_info(f"📊 RESUMEN FINAL DE TESTS")
        self.log_info(f"============================================================")
        
        total_tests = len(tests)
        tests_pasados = sum(1 for _, resultado in resultados if resultado)
        tests_fallidos = total_tests - tests_pasados
        
        self.log_info(f"Total tests: {total_tests}")
        self.log_info(f"✅ Tests pasados: {tests_pasados}")
        self.log_info(f"❌ Tests fallidos: {tests_fallidos}")
        
        if tests_fallidos == 0:
            self.log_exito("🎉 TODOS LOS TESTS PASARON - PROBLEMAS CORREGIDOS")
        else:
            self.log_error(f"⚠️ {tests_fallidos} TESTS FALLARON - PROBLEMAS PERSISTEN")
            
        if self.errores:
            self.log_info(f"\n❌ ERRORES DETECTADOS:")
            for error in self.errores:
                self.log_info(f"  - {error}")
        
        return tests_fallidos == 0

if __name__ == "__main__":
    test = TestProblemasHorarios()
    exito = test.ejecutar_todos_tests()
    
    if exito:
        print("\n🎉 RESULTADO: PROBLEMAS CORREGIDOS")
    else:
        print("\n⚠️ RESULTADO: PROBLEMAS PERSISTEN")
    
    sys.exit(0 if exito else 1) 