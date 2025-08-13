#!/usr/bin/env python3
"""
Script simple para analizar el problema de factibilidad de horarios
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'colegio.settings')
django.setup()

from horarios.models import Curso, Profesor, Aula, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, ConfiguracionColegio, BloqueHorario

def analizar_problema():
    """Analiza el problema de factibilidad"""
    print("🔍 ANÁLISIS DEL PROBLEMA DE FACTIBILIDAD")
    print("=" * 50)
    
    # Recursos disponibles
    total_cursos = Curso.objects.count()
    total_profesores = Profesor.objects.count()
    total_aulas = Aula.objects.count()
    
    # Calcular bloques totales requeridos
    total_bloques_requeridos = 0
    materias_por_grado = {}
    
    for mg in MateriaGrado.objects.all():
        grado = mg.grado.nombre
        materia = mg.materia.nombre
        bloques = mg.materia.bloques_por_semana
        
        if grado not in materias_por_grado:
            materias_por_grado[grado] = {}
        if materia not in materias_por_grado[grado]:
            materias_por_grado[grado][materia] = 0
        materias_por_grado[grado][materia] += bloques
        
        total_bloques_requeridos += bloques
    
    # Capacidad disponible (dinámica desde configuración y dominios reales)
    cfg = ConfiguracionColegio.objects.first()
    dias_clase = [d.strip() for d in (cfg.dias_clase.split(',') if cfg and cfg.dias_clase else ['lunes','martes','miércoles','jueves','viernes'])]
    bloques_clase = list(BloqueHorario.objects.filter(tipo='clase').values_list('numero', flat=True))
    capacidad_total = total_aulas * len(dias_clase) * len(bloques_clase)
    
    print(f"📊 RECURSOS DISPONIBLES:")
    print(f"   • Cursos: {total_cursos}")
    print(f"   • Profesores: {total_profesores}")
    print(f"   • Aulas: {total_aulas}")
    print(f"   • Días de clase: {dias_clase}")
    print(f"   • Bloques de clase: {sorted(bloques_clase)}")
    print(f"   • Capacidad total: {capacidad_total} bloques")
    
    print(f"\n📚 BLOQUES REQUERIDOS POR GRADO:")
    for grado, materias in materias_por_grado.items():
        total_grado = sum(materias.values())
        print(f"   • {grado}: {total_grado} bloques")
        for materia, bloques in materias.items():
            print(f"     - {materia}: {bloques} bloques")
    
    print(f"\n⏰ ANÁLISIS DE CAPACIDAD:")
    print(f"   • Bloques totales requeridos: {total_bloques_requeridos}")
    print(f"   • Capacidad total disponible: {capacidad_total}")
    if capacidad_total:
        print(f"   • Factor de ocupación: {total_bloques_requeridos/capacidad_total:.2%}")
    else:
        print(f"   • Factor de ocupación: N/A (sin bloques de clase)")
    
    # Análisis de factibilidad
    if capacidad_total == 0 or total_bloques_requeridos > capacidad_total:
        print(f"\n❌ PROBLEMA DE FACTIBILIDAD:")
        print(f"   • Se requieren {total_bloques_requeridos} bloques")
        print(f"   • Solo hay {capacidad_total} bloques disponibles")
        print(f"   • Faltan {max(0, total_bloques_requeridos - capacidad_total)} bloques")
        
        # Recomendaciones
        print(f"\n💡 RECOMENDACIONES:")
        print(f"   • Aumentar el número de aulas")
        print(f"   • Aumentar el número de días o bloques por día")
        print(f"   • Reducir las horas de algunas materias")
        print(f"   • Usar aulas en diferentes turnos")
        
    else:
        print(f"\n✅ PROBLEMA FACTIBLE:")
        print(f"   • Hay suficiente capacidad para generar horarios")
        print(f"   • Capacidad excedente: {capacidad_total - total_bloques_requeridos} bloques")
        
        # Configuración recomendada (orientativa) en función de la demanda
        print(f"\n⚙️ CONFIGURACIÓN RECOMENDADA:")
        if total_bloques_requeridos > 100:
            print(f"   • Población: 150-200 individuos")
            print(f"   • Generaciones: 500-800")
            print(f"   • Timeout: 600-900 segundos")
            print(f"   • Probabilidad de cruce: 0.9")
            print(f"   • Probabilidad de mutación: 0.15")
        elif total_bloques_requeridos > 50:
            print(f"   • Población: 100-150 individuos")
            print(f"   • Generaciones: 300-500")
            print(f"   • Timeout: 300-600 segundos")
            print(f"   • Probabilidad de cruce: 0.85")
            print(f"   • Probabilidad de mutación: 0.2")
        else:
            print(f"   • Población: 80-100 individuos")
            print(f"   • Generaciones: 200-300")
            print(f"   • Timeout: 180-300 segundos")
            print(f"   • Probabilidad de cruce: 0.8")
            print(f"   • Probabilidad de mutación: 0.25")
    
    return {
        'total_bloques_requeridos': total_bloques_requeridos,
        'capacidad_total': capacidad_total,
        'es_factible': capacidad_total > 0 and total_bloques_requeridos <= capacidad_total
    }

if __name__ == "__main__":
    analizar_problema() 