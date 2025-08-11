from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import FileResponse
from django.db.models import Count
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
from horarios.models import Curso, Profesor, Aula, Horario, MateriaGrado, MateriaProfesor, DisponibilidadProfesor
from horarios.exportador import exportar_horario_csv, exportar_horario_por_curso_csv, exportar_horario_por_profesor_csv
from horarios.genetico_funcion import generar_horarios_genetico

DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
BLOQUES = [1, 2, 3, 4, 5, 6]
HORARIO_TEMPLATE = 'frontend/horario.html'

def index(request):
    context = {
        'cursos': Curso.objects.all(),
        'profesores': Profesor.objects.all(),
        'aulas': Aula.objects.all(),
    }
    return render(request, 'frontend/index.html', context)

def horario_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    horarios = Horario.objects.filter(curso=curso)
    return render(request, 'frontend/horario.html', {
        'titulo': f"Horario del curso {curso.nombre}",
        'horarios': horarios,
        'dias': DIAS,
        'bloques': BLOQUES,
        'filtro': 'curso',
    })


def horario_profesor(request, profesor_id):
    profesor = get_object_or_404(Profesor, id=profesor_id)
    horarios = Horario.objects.filter(profesor=profesor)
    return render(request, 'frontend/horario.html', {
        'titulo': f"Horario del profesor {profesor.nombre}",
        'horarios': horarios,
        'dias': DIAS,
        'bloques': BLOQUES,
        'filtro': 'profesor',
    })

def horario_aula(request, aula_id):
    aula = get_object_or_404(Aula, id=aula_id)
    horarios = Horario.objects.filter(aula=aula)
    return render(request, 'frontend/horario.html', {
        'titulo': f"Horario del aula {aula.nombre}",
        'horarios': horarios,
        'dias': DIAS,
        'bloques': BLOQUES,
        'filtro': 'aula',
    })

def validar_datos(request):
    errores = []

    # Cursos sin materias
    for curso in Curso.objects.all():
        materias = MateriaGrado.objects.filter(grado=curso.grado)
        if not materias.exists():
            errores.append(f"❌ El curso {curso.nombre} no tiene materias asignadas.")

    # Materias sin profesor
    for mg in MateriaGrado.objects.all():
        if not MateriaProfesor.objects.filter(materia=mg.materia).exists():
            errores.append(f"❌ La materia {mg.materia.nombre} del grado {mg.grado.nombre} no tiene profesor.")

    # Profesores sin disponibilidad
    for mp in MateriaProfesor.objects.all():
        if not DisponibilidadProfesor.objects.filter(profesor=mp.profesor).exists():
            errores.append(f"⚠️ El profesor {mp.profesor.nombre} no tiene disponibilidad registrada.")

    return render(request, 'frontend/validaciones.html', {'errores': errores})

def descargar_excel(request):
    """Descarga el horario en formato CSV."""
    return exportar_horario_csv()

def descargar_excel_por_curso(request):
    """Descarga el horario organizado por curso en formato CSV."""
    return exportar_horario_por_curso_csv()

def descargar_excel_por_profesor(request):
    """Descarga el horario organizado por profesor en formato CSV."""
    return exportar_horario_por_profesor_csv()

def generar_horario(request):
    if request.method == 'POST':
        try:
            # Obtener parámetros del formulario
            poblacion_size = int(request.POST.get('poblacion_size', 80))
            generaciones = int(request.POST.get('generaciones', 500))
            prob_cruce = float(request.POST.get('prob_cruce', 0.85))
            prob_mutacion = float(request.POST.get('prob_mutacion', 0.25))
            elite = int(request.POST.get('elite', 4))
            paciencia = int(request.POST.get('paciencia', 25))
            timeout_seg = int(request.POST.get('timeout_seg', 180))
            
            # Ejecutar algoritmo genético robusto
            resultado = generar_horarios_genetico(
                poblacion_size=poblacion_size,
                generaciones=generaciones,
                prob_cruce=prob_cruce,
                prob_mutacion=prob_mutacion,
                elite=elite,
                paciencia=paciencia,
                timeout_seg=timeout_seg
            )
            
            if resultado.get('status') == 'error':
                messages.error(request, f"❌ Error al generar horarios: {resultado.get('mensaje')}")
                if resultado.get('errores'):
                    for error in resultado['errores']:
                        messages.error(request, f"  - {error}")
            else:
                metricas = resultado.get('metricas', {})
                messages.success(request, f"✅ Horarios generados exitosamente en {metricas.get('tiempo_total_segundos', 0):.2f} segundos")
                messages.info(request, f"📊 Generaciones: {metricas.get('generaciones_completadas', 0)}, Fitness: {metricas.get('mejor_fitness_final', 0):.2f}")
                
                # Mostrar información de validación
                validacion = resultado.get('validacion_final', {})
                if validacion.get('advertencias', 0) > 0:
                    messages.warning(request, f"⚠️ {validacion.get('advertencias', 0)} advertencias detectadas")
                
        except Exception as e:
            messages.error(request, f"❌ Error interno al generar horarios: {str(e)}")
        
        return redirect('dashboard')
    else:
        return redirect('dashboard')


def dashboard(request):
    total_cursos = Curso.objects.count()
    total_profesores = Profesor.objects.count()
    total_horarios = Horario.objects.count()

    materias_sin_profesor = MateriaGrado.objects.exclude(
        materia__in = MateriaProfesor.objects.values_list('materia', flat=True)
    )
    
    # Obtener bloques disponibles del colegio (solo tipo 'clase')
    from horarios.models import BloqueHorario
    bloques_disponibles = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))
    
    # Obtener horarios organizados por curso
    horarios_por_curso = {}
    for curso in Curso.objects.all():
        horarios = Horario.objects.filter(curso=curso).select_related('materia', 'profesor')
        horarios_por_curso[curso] = horarios

    return render(request, 'frontend/dashboard.html', {
        'total_cursos': total_cursos,
        'total_profesores': total_profesores,
        'total_horarios': total_horarios,
        'materias_sin_profesor': materias_sin_profesor,
        'dias': DIAS,
        'bloques_disponibles': bloques_disponibles,
        'horarios_por_curso': horarios_por_curso,
    })

def pdf_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    horarios = Horario.objects.filter(curso=curso)

    template = get_template('frontend/pdf_curso.html')
    html = template.render({
        'curso': curso,
        'horarios': horarios,
        'dias': DIAS,
        'bloques': BLOQUES,
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="horario_{curso.nombre}.pdf"'
    pisa.CreatePDF(html, dest=response)
    return response
