#!/usr/bin/env python3
"""
Script para diagnosticar el problema de sobreasignación de materias.

Este script analiza por qué el algoritmo genético está asignando más bloques
de los requeridos para algunas materias.
"""

import os
import sys
import django
from collections import defaultdict, Counter

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

from horarios.models import (
    Profesor, Materia, Curso, Aula, BloqueHorario, 
    MateriaGrado, MateriaProfesor, DisponibilidadProfesor
)

def diagnosticar_sobreasignacion():
    """Diagnostica el problema de sobreasignación de materias."""
    print("🔍 DIAGNÓSTICO DE SOBREASIGNACIÓN DE MATERIAS")
    print("=" * 60)
    
    # Calcular bloques disponibles por semana (dinámico)
    bloques_disponibles = BloqueHorario.objects.filter(tipo='clase').count()
    dias_semana = 5
    bloques_totales = bloques_disponibles * dias_semana

    # 1. Escaneo dinámico de materias potencialmente problemáticas
    print("\n1. ESCANEANDO MATERIAS POTENCIALMENTE PROBLEMÁTICAS...")
    materias_sin_profesor = Materia.objects.exclude(
        id__in=MateriaProfesor.objects.values_list('materia', flat=True)
    )
    materias_inviables = Materia.objects.filter(bloques_por_semana__gt=bloques_totales)

    if materias_sin_profesor.exists():
        print(f"   ❌ Materias sin profesor asignado: {materias_sin_profesor.count()}")
        for m in materias_sin_profesor[:10]:
            print(f"     - {m.nombre} (bloques/semana: {m.bloques_por_semana})")
        if materias_sin_profesor.count() > 10:
            print("     … (más)" )
    else:
        print("   ✅ Todas las materias tienen al menos un profesor asignado")

    if materias_inviables.exists():
        print(f"   ❌ Materias con bloques_por_semana > bloques disponibles ({bloques_totales}): {materias_inviables.count()}")
        for m in materias_inviables[:10]:
            print(f"     - {m.nombre}: {m.bloques_por_semana} bloques")
        if materias_inviables.count() > 10:
            print("     … (más)")
    else:
        print("   ✅ Ninguna materia requiere más bloques de los disponibles por semana")
    
    # 2. Verificar cursos (dinámico)
    print(f"\n2. VERIFICANDO CURSOS Y SU PLAN DE ESTUDIOS...")
    for curso in Curso.objects.select_related('grado').all().order_by('nombre'):
        materias_plan = MateriaGrado.objects.filter(grado=curso.grado)
        print(f"\n🏫 {curso.nombre} (ID: {curso.id}):")
        print(f"   Materias en el plan: {materias_plan.count()}")
        for mg in materias_plan:
            materia = mg.materia
            print(f"     - {materia.nombre}: {materia.bloques_por_semana} bloques/semana")
    
    # 3. Verificar lógica de bloques por semana
    print(f"\n3. VERIFICANDO LÓGICA DE BLOQUES POR SEMANA...")
    print(f"   Bloques disponibles por día: {bloques_disponibles}")
    print(f"   Días de la semana: {dias_semana}")
    print(f"   Bloques totales por semana: {bloques_totales}")
    
    # Verificar si hay materias que requieren más bloques de los disponibles
    materias_inviables_lista = []
    for materia in Materia.objects.all():
        if materia.bloques_por_semana > bloques_totales:
            materias_inviables_lista.append(f"{materia.nombre}: {materia.bloques_por_semana} bloques")
    
    if materias_inviables_lista:
        print(f"   ⚠️ Materias con bloques por semana inviables:")
        for materia in materias_inviables_lista:
            print(f"     - {materia}")
    else:
        print(f"   ✅ Todas las materias tienen bloques por semana viables")
    
    # 4. Verificar distribución de materias por grado
    print(f"\n4. VERIFICANDO DISTRIBUCIÓN DE MATERIAS POR GRADO...")
    
    grados = set()
    for mg in MateriaGrado.objects.all():
        grados.add(mg.grado)
    
    for grado in sorted(grados, key=lambda g: g.nombre):
        materias_grado = MateriaGrado.objects.filter(grado=grado)
        total_bloques = sum(mg.materia.bloques_por_semana for mg in materias_grado)
        
        print(f"\n   📚 {grado.nombre}:")
        print(f"     Total de materias: {materias_grado.count()}")
        print(f"     Total de bloques requeridos: {total_bloques}")
        print(f"     Bloques disponibles: {bloques_totales}")
        
        if total_bloques > bloques_totales:
            print(f"     ❌ REQUIERE MÁS BLOQUES DE LOS DISPONIBLES")
        elif total_bloques == bloques_totales:
            print(f"     ✅ REQUIERE EXACTAMENTE LOS BLOQUES DISPONIBLES")
        else:
            diferencia = bloques_totales - total_bloques
            print(f"     ⚠️ SUBUTILIZA {diferencia} BLOQUES")
    
    # 5. Verificar duplicados en el plan
    print(f"\n5. VERIFICANDO DUPLICADOS EN PLAN DE ESTUDIOS...")
    
    duplicados_por_grado = defaultdict(list)
    for mg in MateriaGrado.objects.all():
        key = (mg.grado.id, mg.materia.id)
        duplicados_por_grado[key].append(mg)
    
    hay_duplicados = False
    for (grado_id, materia_id), materias in duplicados_por_grado.items():
        if len(materias) > 1:
            hay_duplicados = True
            grado = materias[0].grado
            materia = materias[0].materia
            print(f"   ❌ {materia.nombre} duplicada en {grado.nombre}: {len(materias)} entradas")
    
    if not hay_duplicados:
        print(f"   ✅ No hay materias duplicadas en el plan de estudios")
    
    # 6. Resumen y recomendaciones
    print(f"\n" + "=" * 60)
    print("📊 RESUMEN DEL DIAGNÓSTICO")
    print("=" * 60)
    
    problemas = []
    
    if materias_inviables_lista:
        problemas.append("Materias con bloques por semana inviables")
    
    if hay_duplicados:
        problemas.append("Materias duplicadas en el plan de estudios")
    
    # Verificar si algún grado requiere más bloques de los disponibles
    for grado in grados:
        materias_grado = MateriaGrado.objects.filter(grado=grado)
        total_bloques = sum(mg.materia.bloques_por_semana for mg in materias_grado)
        if total_bloques > bloques_totales:
            problemas.append(f"Grado {grado.nombre} requiere más bloques de los disponibles")
    
    if problemas:
        print(f"❌ Se encontraron {len(problemas)} problemas:")
        for i, problema in enumerate(problemas, 1):
            print(f"   {i}. {problema}")
        
        print(f"\n💡 RECOMENDACIONES:")
        print(f"   • Revisar bloques_por_semana de las materias problemáticas")
        print(f"   • Verificar que no haya materias duplicadas en el plan de estudios")
        print(f"   • Asegurar que la suma de bloques por grado no exceda {bloques_totales}")
    else:
        print(f"✅ No se encontraron problemas críticos en la configuración")
        print(f"   El problema puede estar en la lógica del algoritmo genético")
    
    return problemas

if __name__ == "__main__":
    try:
        problemas = diagnosticar_sobreasignacion()
        
        if problemas:
            print(f"\n🚨 Estos problemas pueden estar causando la sobreasignación.")
            print("   Corrija estos problemas antes de intentar generar horarios nuevamente.")
        else:
            print(f"\n✅ La configuración parece correcta.")
            print("   El problema puede estar en la lógica del algoritmo genético.")
            
    except Exception as e:
        print(f"❌ Error durante el diagnóstico: {e}")
        import traceback
        traceback.print_exc() 