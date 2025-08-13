#!/usr/bin/env python3
"""
Script de diagnóstico para identificar problemas en los datos del horario.

Este script analiza la base de datos para encontrar problemas que pueden estar
causando que el algoritmo genético no pueda generar una solución válida.
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
    MateriaGrado, MateriaProfesor, DisponibilidadProfesor,
    ConfiguracionColegio
)

def diagnosticar_problemas():
    """Ejecuta diagnóstico completo de los datos."""
    print("🔍 DIAGNÓSTICO COMPLETO DE DATOS DEL HORARIO")
    print("=" * 60)
    
    problemas = []
    
    # 1. Verificar bloques horarios
    print("\n1. VERIFICANDO BLOQUES HORARIOS...")
    bloques = BloqueHorario.objects.all()
    bloques_clase = bloques.filter(tipo='clase')
    
    if bloques_clase.count() == 0:
        problemas.append("❌ No hay bloques de tipo 'clase' definidos")
    else:
        print(f"✅ {bloques_clase.count()} bloques de tipo 'clase' encontrados")
        print(f"   Bloques: {list(bloques_clase.values_list('numero', flat=True))}")
    
    # 2. Verificar profesores y disponibilidad
    print("\n2. VERIFICANDO PROFESORES Y DISPONIBILIDAD...")
    profesores = Profesor.objects.all()
    profesores_con_disponibilidad = DisponibilidadProfesor.objects.values_list('profesor', flat=True).distinct()
    profesores_sin_disponibilidad = profesores.exclude(id__in=profesores_con_disponibilidad)
    
    print(f"✅ Total de profesores: {profesores.count()}")
    print(f"✅ Profesores con disponibilidad: {len(profesores_con_disponibilidad)}")
    
    if profesores_sin_disponibilidad.exists():
        problemas.append(f"❌ {profesores_sin_disponibilidad.count()} profesores sin disponibilidad definida")
        nombres = list(profesores_sin_disponibilidad.values_list('nombre', flat=True)[:10])
        print(f"   Profesores sin disponibilidad: {', '.join(nombres)}{'...' if len(nombres) == 10 else ''}")
    
    # 3. Verificar materias y profesores habilitados
    print("\n3. VERIFICANDO MATERIAS Y PROFESORES...")
    materias = Materia.objects.all()
    materias_con_profesor = MateriaProfesor.objects.values_list('materia', flat=True).distinct()
    materias_sin_profesor = materias.exclude(id__in=materias_con_profesor)
    
    print(f"✅ Total de materias: {materias.count()}")
    print(f"✅ Materias con profesor: {len(materias_con_profesor)}")
    
    if materias_sin_profesor.exists():
        problemas.append(f"❌ {materias_sin_profesor.count()} materias sin profesor asignado")
        nombres = list(materias_sin_profesor.values_list('nombre', flat=True)[:10])
        print(f"   Materias sin profesor: {', '.join(nombres)}{'...' if len(nombres) == 10 else ''}")
    
    # 4. Verificar cursos y materias del plan
    print("\n4. VERIFICANDO CURSOS Y PLAN DE ESTUDIOS...")
    cursos = Curso.objects.all()
    materias_grado = MateriaGrado.objects.all()
    
    print(f"✅ Total de cursos: {cursos.count()}")
    print(f"✅ Total de materias por grado: {materias_grado.count()}")
    
    # Verificar que cada curso tenga materias
    cursos_sin_materias = []
    for curso in cursos:
        materias_curso = materias_grado.filter(grado=curso.grado)
        if materias_curso.count() == 0:
            cursos_sin_materias.append(curso.nombre)
    
    if cursos_sin_materias:
        problemas.append(f"❌ {len(cursos_sin_materias)} cursos sin materias en el plan de estudios")
        print(f"   Cursos sin materias: {', '.join(cursos_sin_materias)}")
    
    # 5. Verificar factibilidad de bloques por semana
    print("\n5. VERIFICANDO FACTIBILIDAD DE BLOQUES POR SEMANA...")
    # Intentar leer desde configuración del colegio; si no, fallback razonable
    cfg = ConfiguracionColegio.objects.first()
    dias = [d.strip() for d in (cfg.dias_clase.split(',') if cfg and cfg.dias_clase else ['lunes','martes','miércoles','jueves','viernes'])]
    bloques_disponibles = len(dias) * bloques_clase.count()
    
    materias_inviables = []
    for materia in materias:
        if materia.bloques_por_semana > bloques_disponibles:
            materias_inviables.append(f"{materia.nombre} ({materia.bloques_por_semana} bloques)")
    
    if materias_inviables:
        problemas.append(f"❌ {len(materias_inviables)} materias requieren más bloques de los disponibles ({bloques_disponibles})")
        print(f"   Materias inviables: {', '.join(materias_inviables[:5])}{'...' if len(materias_inviables) > 5 else ''}")
    
    # 6. Verificar distribución de carga por profesor
    print("\n6. VERIFICANDO DISTRIBUCIÓN DE CARGA POR PROFESOR...")
    carga_por_profesor = defaultdict(int)
    
    for mp in MateriaProfesor.objects.all():
        carga_por_profesor[mp.profesor_id] += mp.materia.bloques_por_semana
    
    if carga_por_profesor:
        max_carga = max(carga_por_profesor.values())
        min_carga = min(carga_por_profesor.values())
        
        print(f"✅ Carga máxima por profesor: {max_carga} bloques")
        print(f"✅ Carga mínima por profesor: {min_carga} bloques")
        
        if max_carga > min_carga * 3:
            problemas.append(f"⚠️ Distribución de carga muy desigual: máximo {max_carga}, mínimo {min_carga}")
    
    # 7. Verificar disponibilidad por día
    print("\n7. VERIFICANDO DISPONIBILIDAD POR DÍA...")
    disponibilidad_por_dia = defaultdict(int)
    
    for disp in DisponibilidadProfesor.objects.all():
        for bloque in range(disp.bloque_inicio, disp.bloque_fin + 1):
            disponibilidad_por_dia[disp.dia] += 1
    
    print("   Disponibilidad por día:")
    for dia in dias:
        print(f"     {dia.capitalize()}: {disponibilidad_por_dia.get(dia, 0)} slots disponibles")
    
    # 8. Verificar aulas
    print("\n8. VERIFICANDO AULAS...")
    aulas = Aula.objects.all()
    
    print(f"✅ Total de aulas: {aulas.count()}")
    print(f"   Tipos de aula: {list(aulas.values_list('tipo', flat=True).distinct())}")
    
    # Verificar capacidad de aulas
    aulas_sin_capacidad = aulas.filter(capacidad__isnull=True)
    if aulas_sin_capacidad.exists():
        problemas.append(f"⚠️ {aulas_sin_capacidad.count()} aulas sin capacidad definida")
    
    # Resumen de problemas
    print("\n" + "=" * 60)
    print("📊 RESUMEN DEL DIAGNÓSTICO")
    print("=" * 60)
    
    if problemas:
        print(f"❌ Se encontraron {len(problemas)} problemas:")
        for i, problema in enumerate(problemas, 1):
            print(f"   {i}. {problema}")
        
        print(f"\n💡 RECOMENDACIONES:")
        if any("sin disponibilidad" in p for p in problemas):
            print("   • Definir disponibilidad para todos los profesores")
        if any("sin profesor" in p for p in problemas):
            print("   • Asignar profesores a todas las materias")
        if any("bloques" in p and "disponibles" in p for p in problemas):
            print("   • Revisar bloques_por_semana de las materias")
        if any("carga" in p for p in problemas):
            print("   • Revisar distribución de materias entre profesores")
        if any("capacidad" in p for p in problemas):
            print("   • Definir capacidad para todas las aulas")
    else:
        print("✅ No se encontraron problemas críticos en los datos")
    
    return problemas

def verificar_disponibilidad_específica():
    """Verifica disponibilidad específica de profesores problemáticos (detectados dinámicamente)."""
    print("\n🔍 VERIFICACIÓN ESPECÍFICA DE DISPONIBILIDAD")
    print("=" * 60)
    
    # Detectar profesores sin disponibilidad o con muy poca disponibilidad
    profesores = Profesor.objects.all()
    ids_con_disp = set(DisponibilidadProfesor.objects.values_list('profesor', flat=True))
    profesores_sin_disp = profesores.exclude(id__in=ids_con_disp)

    # Considerar problemáticos también a quienes tengan menos de 5 slots semanales
    def slots_profesor(pid: int):
        total = 0
        for d in DisponibilidadProfesor.objects.filter(profesor_id=pid):
            total += (d.bloque_fin - d.bloque_inicio + 1)
        return total

    profesores_pocos_slots = [p for p in profesores if slots_profesor(p.id) < 5]

    candidatos = list(profesores_sin_disp) + profesores_pocos_slots
    vistos = set()
    for profesor in candidatos:
        if profesor.id in vistos:
            continue
        vistos.add(profesor.id)
        disponibilidad = DisponibilidadProfesor.objects.filter(profesor=profesor)
        
        print(f"\nProfesor {profesor.id} ({profesor.nombre}):")
        
        if disponibilidad.exists():
            print("   Disponibilidad:")
            for disp in disponibilidad:
                print(f"     {disp.dia}: bloques {disp.bloque_inicio}-{disp.bloque_fin}")
        else:
            print("   ❌ SIN DISPONIBILIDAD DEFINIDA")
            
        # Verificar materias que puede impartir
        materias = MateriaProfesor.objects.filter(profesor=profesor)
        if materias.exists():
            print(f"   Materias: {', '.join([m.materia.nombre for m in materias])}")
        else:
            print("   ❌ SIN MATERIAS ASIGNADAS")

if __name__ == "__main__":
    # Constantes
    DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
    
    try:
        problemas = diagnosticar_problemas()
        verificar_disponibilidad_específica()
        
        if problemas:
            print(f"\n🚨 El algoritmo genético probablemente fallará debido a estos problemas.")
            print("   Corrija estos problemas antes de intentar generar horarios.")
        else:
            print(f"\n✅ Los datos parecen estar en buen estado.")
            print("   Si el algoritmo sigue fallando, revise la configuración del algoritmo.")
            
    except Exception as e:
        print(f"❌ Error durante el diagnóstico: {e}")
        import traceback
        traceback.print_exc() 