"""
Módulo para exportar horarios en diferentes formatos.
"""

import csv
import io
from datetime import datetime
from django.http import HttpResponse
from django.db.models import Prefetch
from horarios.models import Horario, Curso, Materia, Profesor, Aula, BloqueHorario


def exportar_horario_csv():
    """
    Exporta el horario actual a formato CSV.
    
    Returns:
        HttpResponse con el archivo CSV
    """
    # Obtener todos los horarios con relaciones precargadas
    horarios = Horario.objects.select_related(
        'curso', 'materia', 'profesor', 'aula'
    ).prefetch_related(
        Prefetch('curso__grado')
    ).order_by('curso__grado__nombre', 'curso__nombre', 'dia', 'bloque')
    
    # Crear respuesta HTTP
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="horario_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    # Crear writer CSV
    writer = csv.writer(response)
    
    # Escribir encabezados
    writer.writerow([
        'Grado',
        'Curso',
        'Día',
        'Bloque',
        'Hora Inicio',
        'Hora Fin',
        'Materia',
        'Profesor',
        'Aula',
        'Tipo Aula'
    ])
    
    # Escribir datos
    for horario in horarios:
        # Obtener información del bloque
        try:
            bloque_obj = BloqueHorario.objects.get(numero=horario.bloque)
            hora_inicio = bloque_obj.hora_inicio.strftime('%H:%M')
            hora_fin = bloque_obj.hora_fin.strftime('%H:%M')
        except BloqueHorario.DoesNotExist:
            hora_inicio = "N/A"
            hora_fin = "N/A"
        
        writer.writerow([
            horario.curso.grado.nombre,
            horario.curso.nombre,
            horario.dia.capitalize(),
            horario.bloque,
            hora_inicio,
            hora_fin,
            horario.materia.nombre,
            horario.profesor.nombre,
            horario.aula.nombre if horario.aula else "N/A",
            horario.aula.tipo if horario.aula else "N/A"
        ])
    
    return response


def exportar_horario_por_curso_csv():
    """
    Exporta el horario organizado por curso en formato CSV.
    
    Returns:
        HttpResponse con el archivo CSV
    """
    # Obtener todos los cursos con sus horarios
    cursos = Curso.objects.select_related('grado').prefetch_related(
        Prefetch(
            'horario_set',
            queryset=Horario.objects.select_related('materia', 'profesor', 'aula').order_by('dia', 'bloque')
        )
    ).order_by('grado__nombre', 'nombre')
    
    # Crear respuesta HTTP
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="horario_por_curso_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    # Crear writer CSV
    writer = csv.writer(response)
    
    # Escribir encabezados
    dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    headers = ['Curso', 'Grado']
    for dia in dias:
        headers.extend([f'{dia} - Bloque', f'{dia} - Materia', f'{dia} - Profesor'])
    
    writer.writerow(headers)
    
    # Escribir datos por curso
    for curso in cursos:
        # Crear diccionario para organizar horarios por día
        horarios_por_dia = {
            'lunes': {},
            'martes': {},
            'miércoles': {},
            'jueves': {},
            'viernes': {}
        }
        
        # Organizar horarios del curso por día y bloque
        for horario in curso.horario_set.all():
            horarios_por_dia[horario.dia][horario.bloque] = horario
        
        # Escribir fila del curso
        fila = [curso.nombre, curso.grado.nombre]
        
        for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
            # Obtener todos los bloques disponibles
            bloques_disponibles = BloqueHorario.objects.filter(tipo='clase').order_by('numero')
            
            for bloque in bloques_disponibles:
                if bloque.numero in horarios_por_dia[dia]:
                    horario = horarios_por_dia[dia][bloque.numero]
                    fila.extend([
                        f"{bloque.numero} ({bloque.hora_inicio.strftime('%H:%M')}-{bloque.hora_fin.strftime('%H:%M')})",
                        horario.materia.nombre,
                        horario.profesor.nombre
                    ])
                else:
                    fila.extend(['', '', ''])
        
        writer.writerow(fila)
    
    return response


def exportar_horario_por_profesor_csv():
    """
    Exporta el horario organizado por profesor en formato CSV.
    
    Returns:
        HttpResponse con el archivo CSV
    """
    # Obtener todos los profesores con sus horarios
    profesores = Profesor.objects.prefetch_related(
        Prefetch(
            'horario_set',
            queryset=Horario.objects.select_related('curso', 'materia', 'aula').order_by('dia', 'bloque')
        )
    ).order_by('nombre')
    
    # Crear respuesta HTTP
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="horario_por_profesor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    # Crear writer CSV
    writer = csv.writer(response)
    
    # Escribir encabezados
    dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    headers = ['Profesor']
    for dia in dias:
        headers.extend([f'{dia} - Bloque', f'{dia} - Curso', f'{dia} - Materia', f'{dia} - Aula'])
    
    writer.writerow(headers)
    
    # Escribir datos por profesor
    for profesor in profesores:
        # Crear diccionario para organizar horarios por día
        horarios_por_dia = {
            'lunes': {},
            'martes': {},
            'miércoles': {},
            'jueves': {},
            'viernes': {}
        }
        
        # Organizar horarios del profesor por día y bloque
        for horario in profesor.horario_set.all():
            horarios_por_dia[horario.dia][horario.bloque] = horario
        
        # Escribir fila del profesor
        fila = [profesor.nombre]
        
        for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
            # Obtener todos los bloques disponibles
            bloques_disponibles = BloqueHorario.objects.filter(tipo='clase').order_by('numero')
            
            for bloque in bloques_disponibles:
                if bloque.numero in horarios_por_dia[dia]:
                    horario = horarios_por_dia[dia][bloque.numero]
                    fila.extend([
                        f"{bloque.numero} ({bloque.hora_inicio.strftime('%H:%M')}-{bloque.hora_fin.strftime('%H:%M')})",
                        f"{horario.curso.grado.nombre} {horario.curso.nombre}",
                        horario.materia.nombre,
                        horario.aula.nombre if horario.aula else "N/A"
                    ])
                else:
                    fila.extend(['', '', '', ''])
        
        writer.writerow(fila)
    
    return response


def generar_resumen_horario():
    """
    Genera un resumen estadístico del horario actual.
    
    Returns:
        Dict con estadísticas del horario
    """
    total_horarios = Horario.objects.count()
    
    # Estadísticas por curso
    cursos_con_horario = Horario.objects.values('curso__nombre').distinct().count()
    total_cursos = Curso.objects.count()
    
    # Estadísticas por profesor
    profesores_con_horario = Horario.objects.values('profesor__nombre').distinct().count()
    total_profesores = Profesor.objects.count()
    
    # Estadísticas por materia
    materias_con_horario = Horario.objects.values('materia__nombre').distinct().count()
    total_materias = Materia.objects.count()
    
    # Estadísticas por día
    horarios_por_dia = {}
    for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
        horarios_por_dia[dia] = Horario.objects.filter(dia=dia).count()
    
    # Estadísticas por bloque
    horarios_por_bloque = {}
    bloques = BloqueHorario.objects.filter(tipo='clase').order_by('numero')
    for bloque in bloques:
        horarios_por_bloque[f"Bloque {bloque.numero}"] = Horario.objects.filter(bloque=bloque.numero).count()
    
    return {
        'total_horarios': total_horarios,
        'cursos': {
            'con_horario': cursos_con_horario,
            'total': total_cursos,
            'porcentaje': round((cursos_con_horario / total_cursos * 100), 2) if total_cursos > 0 else 0
        },
        'profesores': {
            'con_horario': profesores_con_horario,
            'total': total_profesores,
            'porcentaje': round((profesores_con_horario / total_profesores * 100), 2) if total_profesores > 0 else 0
        },
        'materias': {
            'con_horario': materias_con_horario,
            'total': total_materias,
            'porcentaje': round((materias_con_horario / total_materias * 100), 2) if total_materias > 0 else 0
        },
        'horarios_por_dia': horarios_por_dia,
        'horarios_por_bloque': horarios_por_bloque
    }


