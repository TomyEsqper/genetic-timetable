from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import FileResponse, JsonResponse
from django.db import transaction
from django.db.models import Count, Q
from django.template.loader import get_template
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from xhtml2pdf import pisa
from django.http import HttpResponse
from horarios.models import Curso, Profesor, Aula, Horario, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, BloqueHorario
from horarios.infrastructure.adapters.exportador import exportar_horario_csv, exportar_horario_por_curso_csv, exportar_horario_por_profesor_csv
from horarios.infrastructure.utils.tasks import ejecutar_generacion_horarios
from horarios.application.services.generador_demand_first import GeneradorDemandFirst
from horarios.domain.validators.validador_precondiciones import ValidadorPrecondiciones
from glob import glob
try:
    from celery.result import AsyncResult
except ImportError:
    AsyncResult = None

def get_dias_clase():
    """
    Obtiene los días de clase desde la configuración de la base de datos.
    Retorna lista normalizada de días.
    """
    try:
        from horarios.models import ConfiguracionColegio
        config = ConfiguracionColegio.objects.first()
        if config and config.dias_clase:
            return [dia.strip().lower() for dia in config.dias_clase.split(',')]
        else:
            return ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
    except Exception:
        return ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']

def get_bloques_clase():
    """Obtiene los números de bloque de tipo 'clase' ordenados desde la BD."""
    try:
        return list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))
    except Exception:
        # Fallback común si aún no hay migraciones aplicadas
        return [1, 2, 3, 4, 5, 6]

# Obtener días y bloques dinámicamente
DIAS = get_dias_clase()
BLOQUES = get_bloques_clase()
HORARIO_TEMPLATE = 'frontend/horario.html'

def index(request):
    """
    Vista principal del dashboard público.
    Muestra resúmenes de cursos, profesores y aulas.
    """
    # Optimizar consultas con select_related
    context = {
        'cursos': Curso.objects.select_related('grado', 'aula_fija').all(),
        'profesores': Profesor.objects.all(),
        'aulas': Aula.objects.all(),
    }
    return render(request, 'frontend/index.html', context)

def horario_curso(request, curso_id):
    """
    Muestra la grilla de horario para un curso específico.
    """
    # Optimizar consulta con select_related para obtener datos relacionados
    curso = get_object_or_404(Curso.objects.select_related('grado', 'aula_fija'), id=curso_id)
    # horarios = Horario.objects.filter(curso=curso).select_related('materia', 'profesor', 'aula') # Desacoplado
    
    return render(request, 'frontend/horario.html', {
        'titulo': f"Horario del curso {curso.nombre}",
        # 'horarios': horarios, # Ya no se pasa por contexto
        'dias': DIAS,
        'bloques': BLOQUES,
        'filtro': 'curso',
        'obj_id': curso.id,
        'obj_tipo': 'curso',
    })

def horario_profesor(request, profesor_id):
    """
    Muestra la grilla de horario para un profesor específico.
    """
    # Optimizar consulta con select_related
    profesor = get_object_or_404(Profesor, id=profesor_id)
    # horarios = Horario.objects.filter(profesor=profesor).select_related('curso', 'materia', 'aula') # Desacoplado
    
    return render(request, 'frontend/horario.html', {
        'titulo': f"Horario del profesor {profesor.nombre}",
        # 'horarios': horarios, # Ya no se pasa por contexto
        'dias': DIAS,
        'bloques': BLOQUES,
        'filtro': 'profesor',
        'obj_id': profesor.id,
        'obj_tipo': 'profesor',
    })

def horario_aula(request, aula_id):
    """
    Muestra la grilla de ocupación para un aula específica.
    """
    # Optimizar consulta con select_related
    aula = get_object_or_404(Aula, id=aula_id)
    # horarios = Horario.objects.filter(aula=aula).select_related('curso', 'materia', 'profesor') # Desacoplado
    
    return render(request, 'frontend/horario.html', {
        'titulo': f"Horario del aula {aula.nombre}",
        # 'horarios': horarios, # Ya no se pasa por contexto
        'dias': DIAS,
        'bloques': BLOQUES,
        'filtro': 'aula',
        'obj_id': aula.id,
        'obj_tipo': 'aula',
    })

def validar_datos(request):
    """
    Vista de diagnóstico que muestra problemas en los datos maestros.
    Ej: Cursos sin materias, materias sin profesor, etc.
    """
    errores = []

    # Optimizar consultas para validaciones
    cursos = Curso.objects.select_related('grado').all()
    materias_grado = MateriaGrado.objects.select_related('grado', 'materia').all()
    materias_profesor = MateriaProfesor.objects.select_related('profesor', 'materia').all()
    disponibilidades = DisponibilidadProfesor.objects.select_related('profesor').all()

    # Cursos sin materias
    for curso in cursos:
        materias = [mg for mg in materias_grado if mg.grado == curso.grado]
        if not materias:
            errores.append(f"❌ El curso {curso.nombre} no tiene materias asignadas.")

    # Materias sin profesor
    materias_con_profesor = set(mp.materia.id for mp in materias_profesor)
    for mg in materias_grado:
        if mg.materia.id not in materias_con_profesor:
            errores.append(f"❌ La materia {mg.materia.nombre} del grado {mg.grado.nombre} no tiene profesor.")

    # Profesores sin disponibilidad
    profesores_con_disponibilidad = set(dp.profesor.id for dp in disponibilidades)
    for mp in materias_profesor:
        if mp.profesor.id not in profesores_con_disponibilidad:
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
    """
    Endpoint que procesa la solicitud de generación de horarios.
    Recibe parámetros de configuración, ejecuta el algoritmo y redirige al dashboard.
    """
    if request.method == 'POST':
        try:
            # Obtener parámetros del formulario con valores predeterminados seguros
            # Esto maneja tanto el formulario completo como los botones de "Generación Rápida"
            poblacion_size = int(request.POST.get('poblacion_size', 80))
            generaciones = int(request.POST.get('generaciones', 1000))
            prob_cruce = float(request.POST.get('prob_cruce', 0.9))
            prob_mutacion = float(request.POST.get('prob_mutacion', 0.05))
            elite = int(request.POST.get('elite', 5))
            timeout_seg = int(request.POST.get('timeout_seg', 600))
            paciencia = int(request.POST.get('paciencia', 50))
            workers = int(request.POST.get('workers', 1))
            semilla = int(request.POST.get('semilla', 94601))
            
            # Ejecutar algoritmo Demand First (Reemplazando Genético)
            # Mapeo de parámetros
            parametros = {
                'max_iteraciones': generaciones, # Reusing generaciones input as max_iteraciones
                'paciencia': paciencia,
                'semilla': semilla
            }
            
            # Validación previa
            validador = ValidadorPrecondiciones()
            resultado_factibilidad = validador.validar_factibilidad_completa()
            
            if not resultado_factibilidad.es_factible:
                messages.error(request, "❌ Error de validación previa: La configuración actual no es factible.")
                for problema in resultado_factibilidad.problemas:
                    messages.error(request, f"  - {problema.descripcion}")
                return redirect('dashboard')

            # Ejecución centralizada (Asíncrona)
            # Usamos el mismo entrypoint que la API para consistencia
            resultado = ejecutar_generacion_horarios(
                colegio_id=1, 
                async_mode=True, 
                params=parametros
            )

            if resultado.get('status') == 'task_created':
                # Modo asíncrono: Guardar ID de tarea en sesión
                request.session['task_id'] = resultado.get('task_id')
                messages.success(request, "🚀 Generación iniciada en segundo plano. Los resultados aparecerán pronto.")
            elif not resultado.get('exito'):
                # Modo síncrono (fallback) o error inmediato
                razon = resultado.get('error', 'Falló la generación')
                messages.error(request, f"❌ Error al generar horarios: {razon}")
            else:
                # Modo síncrono: Éxito
                tiempo_total = resultado.get('tiempo_ejecucion', 0)
                slots = resultado.get('slots_generados', 0)
                calidad = resultado.get('calidad_final', 0)
                
                messages.success(request, f"✅ Horarios generados exitosamente en {tiempo_total:.2f} segundos")
                messages.info(request, f"📊 Slots: {slots}, Calidad: {calidad:.2f}")
                
        except Exception as e:
            messages.error(request, f"❌ Error interno al generar horarios: {str(e)}")
            import traceback
            messages.error(request, f"  - Traceback: {traceback.format_exc()[:200]}...")
        
        return redirect('dashboard')
    else:
        return redirect('dashboard')

def dashboard(request):
    # Optimizar todas las consultas con select_related y prefetch_related
    total_cursos = Curso.objects.count()
    total_profesores = Profesor.objects.count()
    total_horarios = Horario.objects.count()

    # Optimizar consulta de materias sin profesor
    materias_sin_profesor = MateriaGrado.objects.select_related('grado', 'materia').exclude(
        materia__in = MateriaProfesor.objects.values_list('materia', flat=True)
    )
    
    # Obtener bloques disponibles del colegio (solo tipo 'clase')
    bloques_disponibles = list(BloqueHorario.objects.filter(tipo='clase').order_by('numero').values_list('numero', flat=True))
    
    # Obtener horarios organizados por curso con optimización
    horarios_por_curso = {}
    cursos = Curso.objects.select_related('grado', 'aula_fija').all()
    
    for curso in cursos:
        horarios = Horario.objects.filter(curso=curso).select_related('materia', 'profesor', 'aula').order_by('dia', 'bloque')
        horarios_por_curso[curso] = horarios

    # Obtener estadísticas adicionales de los horarios
    estadisticas_horarios = {}
    if total_horarios > 0:
        # Contar materias únicas
        materias_unicas = Horario.objects.values('materia__nombre').distinct().count()
        # Contar profesores únicos
        profesores_unicos = Horario.objects.values('profesor__nombre').distinct().count()
        # Contar aulas únicas
        aulas_unicas = Horario.objects.values('aula__nombre').distinct().count()
        
        estadisticas_horarios = {
            'materias_unicas': materias_unicas,
            'profesores_unicos': profesores_unicos,
            'aulas_unicas': aulas_unicas,
            'promedio_materias_por_curso': total_horarios / total_cursos if total_cursos > 0 else 0,
        }

    return render(request, 'frontend/dashboard.html', {
        'total_cursos': total_cursos,
        'total_profesores': total_profesores,
        'total_horarios': total_horarios,
        'materias_sin_profesor': materias_sin_profesor,
        'dias': DIAS,
        'bloques_disponibles': bloques_disponibles,
        'horarios_por_curso': horarios_por_curso,
        'estadisticas_horarios': estadisticas_horarios,
    })

def pdf_curso(request, curso_id):
    """
    Genera un archivo PDF con el horario del curso.
    Usa xhtml2pdf para renderizar HTML a PDF.
    """
    # Optimizar consulta para PDF
    curso = get_object_or_404(Curso.objects.select_related('grado', 'aula_fija'), id=curso_id)
    horarios = Horario.objects.filter(curso=curso).select_related('materia', 'profesor', 'aula')

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

# Nuevas vistas optimizadas con paginación y filtros

def lista_cursos(request):
    """Vista paginada de cursos con filtros"""
    cursos_list = Curso.objects.select_related('grado', 'aula_fija').all()
    
    # Filtros
    grado_filter = request.GET.get('grado')
    if grado_filter:
        cursos_list = cursos_list.filter(grado__nombre__icontains=grado_filter)
    
    # Paginación
    paginator = Paginator(cursos_list, 10)  # 10 cursos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'frontend/lista_cursos.html', {
        'page_obj': page_obj,
        'grados': Curso.objects.values_list('grado__nombre', flat=True).distinct(),
    })

def lista_profesores(request):
    """Vista paginada de profesores con filtros"""
    profesores_list = Profesor.objects.all()
    
    # Filtros
    nombre_filter = request.GET.get('nombre')
    if nombre_filter:
        profesores_list = profesores_list.filter(nombre__icontains=nombre_filter)
    
    # Paginación
    paginator = Paginator(profesores_list, 15)  # 15 profesores por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'frontend/lista_profesores.html', {
        'page_obj': page_obj,
    })

# Vistas AJAX para carga dinámica

@require_http_methods(["GET"])
def horario_ajax(request):
    """Vista AJAX para cargar horarios dinámicamente"""
    tipo = request.GET.get('tipo')
    id_obj = request.GET.get('id')
    
    if not tipo or not id_obj:
        return JsonResponse({'error': 'Parámetros faltantes'}, status=400)
    
    try:
        if tipo == 'curso':
            curso = get_object_or_404(Curso, id=id_obj)
            horarios = Horario.objects.filter(curso=curso).select_related('materia', 'profesor', 'aula')
            titulo = f"Horario del curso {curso.nombre}"
        elif tipo == 'profesor':
            profesor = get_object_or_404(Profesor, id=id_obj)
            horarios = Horario.objects.filter(profesor=profesor).select_related('curso', 'materia', 'aula')
            titulo = f"Horario del profesor {profesor.nombre}"
        elif tipo == 'aula':
            aula = get_object_or_404(Aula, id=id_obj)
            horarios = Horario.objects.filter(aula=aula).select_related('curso', 'materia', 'profesor')
            titulo = f"Horario del aula {aula.nombre}"
        else:
            return JsonResponse({'error': 'Tipo no válido'}, status=400)
        
        # Convertir horarios a formato JSON
        horarios_data = []
        for horario in horarios:
            horarios_data.append({
                'id': horario.id,
                'dia': horario.dia,
                'bloque': horario.bloque,
                'materia': horario.materia.nombre,
                'profesor': horario.profesor.nombre,
                'aula': horario.aula.nombre if horario.aula else 'Sin asignar',
                'curso': horario.curso.nombre if hasattr(horario, 'curso') else None,
            })
        
        return JsonResponse({
            'titulo': titulo,
            'horarios': horarios_data,
            'dias': DIAS,
            'bloques': BLOQUES,
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def estadisticas_ajax(request):
    """Vista AJAX para obtener estadísticas en tiempo real"""
    try:
        total_cursos = Curso.objects.count()
        total_profesores = Profesor.objects.count()
        total_horarios = Horario.objects.count()
        total_aulas = Aula.objects.count()
        
        # Estadísticas adicionales
        materias_sin_profesor = MateriaGrado.objects.exclude(
            materia__in = MateriaProfesor.objects.values_list('materia', flat=True)
        ).count()
        
        profesores_sin_disponibilidad = Profesor.objects.exclude(
            id__in = DisponibilidadProfesor.objects.values_list('profesor', flat=True)
        ).count()
        
        return JsonResponse({
            'total_cursos': total_cursos,
            'total_profesores': total_profesores,
            'total_horarios': total_horarios,
            'total_aulas': total_aulas,
            'materias_sin_profesor': materias_sin_profesor,
            'profesores_sin_disponibilidad': profesores_sin_disponibilidad,
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def progreso_ajax(request):
    """Devuelve progreso en tiempo real de la última ejecución."""
    try:
        from horarios.models import Horario
        
        # 1. Verificar si hay una tarea asíncrona en sesión
        task_id = request.session.get('task_id')
        
        if task_id and AsyncResult:
            res = AsyncResult(task_id)
            
            if res.state == 'PROGRESS' or res.state == 'STARTED':
                info = res.info if isinstance(res.info, dict) else {}
                return JsonResponse({
                    'estado': 'en_progreso',
                    'generacion': info.get('generacion', 0),
                    'mejor_fitness': info.get('fitness', 0.0),
                    'fitness_promedio': info.get('fitness', 0.0), # Fallback
                    'fill_pct': info.get('ocupacion', 0.0),
                    'horarios_parciales': info.get('horarios', 0),
                    'objetivo': info.get('total_generaciones', 100),
                    'mensaje': info.get('status', 'Procesando...')
                })
                
            elif res.state == 'SUCCESS':
                # Tarea finalizada exitosamente
                # Limpiar task_id de sesión para no seguir consultando
                # request.session.pop('task_id', None) # Lo mantenemos un poco más por si acaso
                
                result_data = res.result if isinstance(res.result, dict) else {}
                return JsonResponse({
                    'estado': 'finalizado',
                    'mensaje': 'Generación completada',
                    'mejor_fitness': result_data.get('calidad_final', 1.0),
                    'horarios_parciales': result_data.get('slots_generados', 0)
                })
                
            elif res.state == 'FAILURE':
                return JsonResponse({
                    'estado': 'error',
                    'mensaje': f"Error en la tarea: {str(res.result)}"
                })
                
            elif res.state == 'PENDING':
                return JsonResponse({
                    'estado': 'en_progreso',
                    'mensaje': 'Iniciando tarea...',
                    'generacion': 0
                })
        
        # 2. Fallback: Verificar base de datos (para modo síncrono o si se perdió la sesión)
        horarios_parciales = Horario.objects.count()
        if horarios_parciales > 0:
            return JsonResponse({
                'estado': 'finalizado',
                'mensaje': 'Horarios existentes',
                'horarios_parciales': horarios_parciales
            })
            
        return JsonResponse({'estado': 'sin_datos', 'mensaje': 'No hay proceso activo'})
        
    except Exception as e:
        return JsonResponse({
            'estado': 'error',
            'mensaje': f'Error interno: {str(e)}'
        })

@require_http_methods(["GET"])
def limpiar_cache_progreso(request):
    """Limpia el cache de progreso cuando el proceso ha terminado"""
    try:
        # Ya no usamos cache para progreso, pero mantenemos el endpoint para evitar errores 404
        return JsonResponse({
            'estado': 'exito',
            'mensaje': 'Cache de progreso limpiado'
        })
        
    except Exception as e:
        return JsonResponse({
            'estado': 'error',
            'mensaje': f'Error: {str(e)}'
        }, status=500)

@require_http_methods(["POST"])
def mover_horario_ajax(request):
    """Mueve un horario a otro día/bloque vía AJAX (con soporte para SWAP)"""
    try:
        import json
        data = json.loads(request.body)
        
        horario_id = data.get('horario_id')
        nuevo_dia = data.get('nuevo_dia')
        nuevo_bloque = int(data.get('nuevo_bloque'))
        
        if not all([horario_id, nuevo_dia, nuevo_bloque]):
            return JsonResponse({'error': 'Faltan parámetros'}, status=400)
            
        horario = get_object_or_404(Horario, id=horario_id)
        
        # Guardar valores originales para posible swap
        dia_original = horario.dia
        bloque_original = horario.bloque
        
        # 1. Detectar si hay un horario en el destino para el MISMO curso (Conflicto de Curso -> SWAP)
        horario_destino = Horario.objects.filter(
            curso=horario.curso, 
            dia=nuevo_dia, 
            bloque=nuevo_bloque
        ).exclude(id=horario.id).first()
        
        if horario_destino:
            # --- Lógica de SWAP ---
            # Validar conflictos de Profesor Cruzados:
            # A (horario) va a Destino. ¿Profesor de A está libre en Destino (excepto por la clase que ya está ahí, que se va a mover)?
            # B (horario_destino) va a Origen. ¿Profesor de B está libre en Origen (excepto por la clase A que se va)?
            
            # Validar Profesor A en Destino (Ignorando a B que ocupa ese lugar ahora)
            if Horario.objects.filter(profesor=horario.profesor, dia=nuevo_dia, bloque=nuevo_bloque).exclude(id=horario.id).exclude(id=horario_destino.id).exists():
                 return JsonResponse({'error': f'El profesor {horario.profesor.nombre} ya tiene otra clase (en otro curso) en {nuevo_dia} bloque {nuevo_bloque}.'}, status=400)

            # Validar Profesor B en Origen (Ignorando a A que ocupa ese lugar ahora)
            if Horario.objects.filter(profesor=horario_destino.profesor, dia=dia_original, bloque=bloque_original).exclude(id=horario_destino.id).exclude(id=horario.id).exists():
                 return JsonResponse({'error': f'El profesor {horario_destino.profesor.nombre} ya tiene otra clase (en otro curso) en {dia_original} bloque {bloque_original}.'}, status=400)

            # Ejecutar SWAP atómico
            with transaction.atomic():
                # Mover A a temporal (para evitar colisiones de unique constraints si las hubiera)
                horario.dia = 'TEMP' 
                horario.save()
                
                # Mover B a Origen
                horario_destino.dia = dia_original
                horario_destino.bloque = bloque_original
                horario_destino.save()
                
                # Mover A a Destino
                horario.dia = nuevo_dia
                horario.bloque = nuevo_bloque
                horario.save()
                
            return JsonResponse({
                'status': 'success',
                'message': 'Intercambio realizado correctamente',
                'swap': True,
                'origen': {'dia': dia_original, 'bloque': bloque_original},
                'destino': {'dia': nuevo_dia, 'bloque': nuevo_bloque}
            })

        else:
            # --- Lógica de Movimiento Simple ---
            
            # Validar colisión de Curso (El curso ya tiene clase en ese bloque?) -> Ya chequeado arriba, es horario_destino
            # Si llegamos aquí, horario_destino es None, así que no hay colisión de curso.

            # Validar colisión de Profesor (El profesor ya tiene clase en ese bloque con otro curso?)
            if Horario.objects.filter(profesor=horario.profesor, dia=nuevo_dia, bloque=nuevo_bloque).exclude(id=horario.id).exists():
                 return JsonResponse({'error': f'El profesor {horario.profesor.nombre} ya tiene clase en {nuevo_dia} bloque {nuevo_bloque}.'}, status=400)

            # Actualizar horario
            horario.dia = nuevo_dia
            horario.bloque = nuevo_bloque
            horario.save()
        
        return JsonResponse({
            'status': 'success',
            'horario': {
                'id': horario.id,
                'dia': horario.dia,
                'bloque': horario.bloque
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
