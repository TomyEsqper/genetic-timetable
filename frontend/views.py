from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.core.paginator import Paginator
from django.views.decorators.csrf import ensure_csrf_cookie
from horarios.models import Curso, Profesor, Aula, Horario
from django.utils.timezone import now

def portal_docs(request):
    return render(request, 'frontend/portal_docs.html')

def index(request):
    cursos = Curso.objects.order_by('grado__nombre', 'nombre')[:10]
    profesores = Profesor.objects.order_by('nombre')[:10]
    aulas = Aula.objects.order_by('nombre')[:10]
    return render(request, 'frontend/portal_home.html', {
        'cursos': cursos,
        'profesores': profesores,
        'aulas': aulas,
    })

def dashboard_portal(request):
    total_cursos = Curso.objects.count()
    total_profesores = Profesor.objects.count()
    total_horarios = Horario.objects.count()
    return render(request, 'frontend/portal_dashboard.html', {
        'total_cursos': total_cursos,
        'total_profesores': total_profesores,
        'total_horarios': total_horarios,
    })

def how_to_portal(request):
    return render(request, 'frontend/portal_how_to.html')

def panel_coordinador(request):
    cursos = Curso.objects.order_by('grado__nombre', 'nombre')
    profesores = Profesor.objects.order_by('nombre')
    aulas = Aula.objects.order_by('nombre')
    return render(request, 'frontend/index.html', {
        'cursos': cursos,
        'profesores': profesores,
        'aulas': aulas,
    })

@ensure_csrf_cookie
def dashboard(request):
    total_cursos = Curso.objects.count()
    total_profesores = Profesor.objects.count()
    total_horarios = Horario.objects.count()
    return render(request, 'frontend/dashboard.html', {
        'total_cursos': total_cursos,
        'total_profesores': total_profesores,
        'total_horarios': total_horarios,
    })

def horario_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    return render(request, 'frontend/horario.html', {'tipo': 'curso', 'entidad': curso})

def horario_profesor(request, profesor_id):
    profesor = get_object_or_404(Profesor, id=profesor_id)
    return render(request, 'frontend/horario.html', {'tipo': 'profesor', 'entidad': profesor})

def horario_aula(request, aula_id):
    aula = get_object_or_404(Aula, id=aula_id)
    return render(request, 'frontend/horario.html', {'tipo': 'aula', 'entidad': aula})

def validar_datos(request):
    errores = []
    return render(request, 'frontend/validaciones.html', {'errores': errores})

def lista_cursos(request):
    qs = Curso.objects.order_by('grado__nombre', 'nombre')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    return render(request, 'frontend/lista_cursos.html', {'page_obj': page_obj})

def lista_profesores(request):
    qs = Profesor.objects.order_by('nombre')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    return render(request, 'frontend/lista_profesores.html', {'page_obj': page_obj})

def horario_ajax(request):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    tipo = request.GET.get('tipo')
    try_id = request.GET.get('id')
    if not tipo or not try_id:
        return JsonResponse({'error': 'parámetros inválidos'}, status=400)
    if tipo == 'curso':
        entidad = get_object_or_404(Curso, id=try_id)
        horarios = Horario.objects.filter(curso=entidad).select_related('materia', 'profesor', 'aula')
        titulo = f'Horario de curso {entidad.nombre}'
    elif tipo == 'profesor':
        entidad = get_object_or_404(Profesor, id=try_id)
        horarios = Horario.objects.filter(profesor=entidad).select_related('materia', 'curso', 'aula')
        titulo = f'Horario de profesor {entidad.nombre}'
    elif tipo == 'aula':
        entidad = get_object_or_404(Aula, id=try_id)
        horarios = Horario.objects.filter(aula=entidad).select_related('materia', 'curso', 'profesor')
        titulo = f'Horario de aula {entidad.nombre}'
    else:
        return JsonResponse({'error': 'tipo desconocido'}, status=400)
    data = []
    for h in horarios:
        data.append({
            'dia': h.dia,
            'bloque': h.bloque,
            'materia': h.materia.nombre,
            'profesor': h.profesor.nombre,
            'curso': h.curso.nombre,
            'aula': h.aula.nombre if h.aula else None,
            'id': h.id,
        })
    return JsonResponse({'titulo': titulo, 'horarios': data})

def estadisticas_ajax(request):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    return JsonResponse({
        'total_cursos': Curso.objects.count(),
        'total_profesores': Profesor.objects.count(),
        'total_horarios': Horario.objects.count(),
    })

def generar_horario(request):
    if request.method == 'GET':
        return redirect('dashboard')
    return HttpResponseNotAllowed(['GET'])

def pdf_curso(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\nxref\n0 1\n0000000000 65535 f \ntrailer<< /Size 1 >>\nstartxref\n0\n%%EOF"
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename=\"horario_curso_{curso.id}.pdf\"'
    return resp

def descargar_excel(request):
    encabezados = "Curso,Profesor,Materia,Dia,Bloque,Aula\n"
    filas = []
    for h in Horario.objects.select_related('curso', 'profesor', 'materia', 'aula'):
        filas.append(f"{h.curso.nombre},{h.profesor.nombre},{h.materia.nombre},{h.dia},{h.bloque},{h.aula.nombre if h.aula else ''}")
    contenido = encabezados + "\n".join(filas)
    resp = HttpResponse(contenido, content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename=horarios_{now().date()}.csv'
    return resp

def progreso_ajax(request):
    return JsonResponse({'estado': 'sin_datos'})

def limpiar_cache_progreso(request):
    return JsonResponse({'mensaje': 'ok'})
