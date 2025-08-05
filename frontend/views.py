from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import FileResponse
from django.db.models import Count
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
from horarios.models import Curso, Profesor, Aula, Horario, MateriaGrado, MateriaProfesor, DisponibilidadProfesor
from horarios.exportador import exportar_horarios_excel
from horarios.genetico import generar_horarios_genetico

DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
BLOQUES = [1, 2, 3, 4, 5, 6]

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
    ruta = 'horarios_generados.xlsx'
    exportar_horarios_excel(ruta)
    return FileResponse(open(ruta, 'rb'), as_attachment=True, filename='horarios.xlsx')

def generar_horario(request):
    if request.method == 'POST':
        generar_horarios_genetico()
        messages.success(request, "✅ Horarios generados exitosamente.")
        return redirect('index')
    else:
        messages.error(request, "❌ Error al generar horarios. Inténtalo de nuevo.")
        return redirect('index')


def dashboard(request):
    total_cursos = Curso.objects.count()
    total_profesores = Profesor.objects.count()
    total_horarios = Horario.objects.count()

    materias_sin_profesor = MateriaGrado.objects.exclude(
        materia__in = MateriaProfesor.objects.values_list('materia', flat=True)
    )

    return render(request, 'frontend/dashboard.html', {
        'total_cursos': total_cursos,
        'total_profesores': total_profesores,
        'total_horarios': total_horarios,
        'materias_sin_profesor': materias_sin_profesor,
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
