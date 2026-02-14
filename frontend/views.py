from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.core.paginator import Paginator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import transaction
from horarios.models import Curso, Profesor, Aula, Horario, Materia
from horarios.application.services.generador_demand_first import GeneradorDemandFirst
from django.utils.timezone import now
import json

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
    cursos = Curso.objects.order_by('grado__nombre', 'nombre')
    horarios_por_curso = {}
    for c in cursos:
        horarios_por_curso[c] = list(Horario.objects.filter(curso=c).select_related('materia', 'profesor', 'aula').order_by('dia', 'bloque'))
    dias_all = list(Horario.objects.values_list('dia', flat=True).distinct())
    orden_dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado']
    dias = [d for d in orden_dias if d in dias_all] or orden_dias[:5]
    bloques_disponibles = sorted(set(Horario.objects.values_list('bloque', flat=True))) or [1,2,3,4,5,6]
    return render(request, 'frontend/dashboard.html', {
        'total_cursos': total_cursos,
        'total_profesores': total_profesores,
        'total_horarios': total_horarios,
        'horarios_por_curso': horarios_por_curso,
        'dias': dias,
        'bloques_disponibles': bloques_disponibles,
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
    if request.method == 'POST':
        try:
            generador = GeneradorDemandFirst()
            resultado = generador.generar_horarios(semilla=94601, max_iteraciones=1000, paciencia=50)
            if not resultado.get('exito'):
                return redirect('dashboard')
            horarios_dicts = resultado.get('horarios', [])
            with transaction.atomic():
                Horario.objects.all().delete()
                nuevos = []
                for h in horarios_dicts:
                    try:
                        curso = Curso.objects.get(id=h['curso_id'])
                        materia = Materia.objects.get(id=h['materia_id'])
                        profesor = Profesor.objects.get(id=h['profesor_id'])
                        aula = Aula.objects.get(id=h['aula_id']) if h.get('aula_id') else None
                        nuevos.append(Horario(
                            curso=curso,
                            materia=materia,
                            profesor=profesor,
                            dia=h['dia'],
                            bloque=h['bloque'],
                            aula=aula
                        ))
                    except Exception:
                        continue
                if nuevos:
                    Horario.objects.bulk_create(nuevos)
        except Exception:
            pass
        return redirect('dashboard')
    return redirect('dashboard')

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

def mover_horario_ajax(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    try:
        payload = json.loads(request.body.decode('utf-8'))
        horario_id = payload.get('horario_id')
        nuevo_dia = payload.get('nuevo_dia')
        nuevo_bloque = int(payload.get('nuevo_bloque'))
        if not horario_id or not nuevo_dia or not nuevo_bloque:
            return JsonResponse({'error': 'parámetros inválidos'}, status=400)
        horario = get_object_or_404(Horario, id=horario_id)
        dia_original = horario.dia
        bloque_original = horario.bloque
        destino_mismo_curso = Horario.objects.filter(curso=horario.curso, dia=nuevo_dia, bloque=nuevo_bloque).exclude(id=horario.id).first()
        if destino_mismo_curso:
            if Horario.objects.filter(profesor=horario.profesor, dia=nuevo_dia, bloque=nuevo_bloque).exclude(id__in=[horario.id, destino_mismo_curso.id]).exists():
                return JsonResponse({'error': 'conflicto_profesor_destino'}, status=400)
            if Horario.objects.filter(profesor=destino_mismo_curso.profesor, dia=dia_original, bloque=bloque_original).exclude(id__in=[horario.id, destino_mismo_curso.id]).exists():
                return JsonResponse({'error': 'conflicto_profesor_origen'}, status=400)
            with transaction.atomic():
                horario.dia = 'TMP'
                horario.save(update_fields=['dia'])
                destino_mismo_curso.dia = dia_original
                destino_mismo_curso.bloque = bloque_original
                destino_mismo_curso.save(update_fields=['dia', 'bloque'])
                horario.dia = nuevo_dia
                horario.bloque = nuevo_bloque
                horario.save(update_fields=['dia', 'bloque'])
            return JsonResponse({'status': 'ok', 'swap': True, 'horario': {'id': horario.id, 'dia': horario.dia, 'bloque': horario.bloque}})
        else:
            if Horario.objects.filter(profesor=horario.profesor, dia=nuevo_dia, bloque=nuevo_bloque).exclude(id=horario.id).exists():
                return JsonResponse({'error': 'conflicto_profesor'}, status=400)
            horario.dia = nuevo_dia
            horario.bloque = nuevo_bloque
            horario.save(update_fields=['dia', 'bloque'])
            return JsonResponse({'status': 'ok', 'swap': False, 'horario': {'id': horario.id, 'dia': horario.dia, 'bloque': horario.bloque}})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
