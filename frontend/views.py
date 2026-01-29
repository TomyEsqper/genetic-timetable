from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import FileResponse, JsonResponse
from django.db.models import Count, Q
from django.template.loader import get_template
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from xhtml2pdf import pisa
from django.http import HttpResponse
from horarios.models import Curso, Profesor, Aula, Horario, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, BloqueHorario
from horarios.infrastructure.adapters.exportador import exportar_horario_csv, exportar_horario_por_curso_csv, exportar_horario_por_profesor_csv
from horarios.application.services.generador_demand_first import GeneradorDemandFirst
from horarios.domain.validators.validador_precondiciones import ValidadorPrecondiciones
from glob import glob

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
    # Optimizar consultas con select_related
    context = {
        'cursos': Curso.objects.select_related('grado', 'aula_fija').all(),
        'profesores': Profesor.objects.all(),
        'aulas': Aula.objects.all(),
    }
    return render(request, 'frontend/index.html', context)

def horario_curso(request, curso_id):
    # Optimizar consulta con select_related para obtener datos relacionados
    curso = get_object_or_404(Curso.objects.select_related('grado', 'aula_fija'), id=curso_id)
    horarios = Horario.objects.filter(curso=curso).select_related('materia', 'profesor', 'aula')
    
    return render(request, 'frontend/horario.html', {
        'titulo': f"Horario del curso {curso.nombre}",
        'horarios': horarios,
        'dias': DIAS,
        'bloques': BLOQUES,
        'filtro': 'curso',
    })

def horario_profesor(request, profesor_id):
    # Optimizar consulta con select_related
    profesor = get_object_or_404(Profesor, id=profesor_id)
    horarios = Horario.objects.filter(profesor=profesor).select_related('curso', 'materia', 'aula')
    
    return render(request, 'frontend/horario.html', {
        'titulo': f"Horario del profesor {profesor.nombre}",
        'horarios': horarios,
        'dias': DIAS,
        'bloques': BLOQUES,
        'filtro': 'profesor',
    })

def horario_aula(request, aula_id):
    # Optimizar consulta con select_related
    aula = get_object_or_404(Aula, id=aula_id)
    horarios = Horario.objects.filter(aula=aula).select_related('curso', 'materia', 'profesor')
    
    return render(request, 'frontend/horario.html', {
        'titulo': f"Horario del aula {aula.nombre}",
        'horarios': horarios,
        'dias': DIAS,
        'bloques': BLOQUES,
        'filtro': 'aula',
    })

def validar_datos(request):
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
    if request.method == 'POST':
        try:
            # Obtener parámetros del formulario (sin valores predeterminados)
            poblacion_size = int(request.POST.get('poblacion_size'))
            generaciones = int(request.POST.get('generaciones'))
            prob_cruce = float(request.POST.get('prob_cruce'))
            prob_mutacion = float(request.POST.get('prob_mutacion'))
            elite = int(request.POST.get('elite'))
            paciencia = int(request.POST.get('paciencia'))
            timeout_seg = int(request.POST.get('timeout_seg'))
            workers = int(request.POST.get('workers'))
            semilla = int(request.POST.get('semilla'))
            
            # Validar que todos los parámetros estén presentes
            if not all([poblacion_size, generaciones, prob_cruce, prob_mutacion, elite, paciencia, timeout_seg, workers, semilla]):
                messages.error(request, "❌ Todos los parámetros son obligatorios")
                return redirect('dashboard')
            
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

            generador = GeneradorDemandFirst()
            resultado = generador.generar_horarios(**parametros)

            if not resultado.get('exito'):
                razon = resultado.get('razon', 'Falló la generación')
                messages.error(request, f"❌ Error al generar horarios: {razon}")
                
                # Mostrar detalles si existen
                if 'factibilidad' in resultado:
                    for problema in resultado['factibilidad'].problemas:
                        messages.error(request, f"  - {problema.descripcion}")
            else:
                # Guardar en BD
                from django.db import transaction
                
                try:
                    with transaction.atomic():
                        Horario.objects.all().delete()
                        horarios_objetos = []
                        for h in resultado['horarios']:
                            curso = Curso.objects.get(id=h['curso_id'])
                            materia = Materia.objects.get(id=h['materia_id'])
                            profesor = Profesor.objects.get(id=h['profesor_id'])
                            aula = None
                            if h.get('aula_id'):
                                aula = Aula.objects.filter(id=h['aula_id']).first()
                            
                            horario = Horario(
                                curso=curso,
                                materia=materia,
                                profesor=profesor,
                                dia=h['dia'],
                                bloque=h['bloque'],
                                aula=aula
                            )
                            horarios_objetos.append(horario)
                        Horario.objects.bulk_create(horarios_objetos)
                        
                    # Success messages
                    estadisticas = resultado.get('estadisticas', {})
                    tiempo_total = estadisticas.get('tiempo_total', 0)
                    slots = estadisticas.get('slots_generados', 0)
                    calidad = resultado.get('calidad', 0)
                    
                    messages.success(request, f"✅ Horarios generados exitosamente en {tiempo_total:.2f} segundos")
                    messages.info(request, f"📊 Slots: {slots}, Calidad: {calidad:.2f}")
                    
                    # Advertencias
                    validacion = resultado.get('validacion_final')
                    if validacion and hasattr(validacion, 'es_valido') and not validacion.es_valido:
                        messages.warning(request, "⚠️ Se detectaron conflictos en el horario generado.")
                        
                except Exception as e:
                    messages.error(request, f"❌ Error guardando horarios: {str(e)}")
                
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
    """Devuelve progreso en tiempo real de la última ejecución.
    Lee el progreso desde la base de datos.
    """
    try:
        from horarios.models import Horario
        from django.core.cache import cache
        
        # Obtener información de horarios parciales
        horarios_parciales = Horario.objects.count()
        
        # Si hay horarios, asumimos que el proceso finalizó (Generación Síncrona)
        if horarios_parciales > 0:
            progreso = {
                'estado': 'finalizado',
                'generacion': 1,
                'mejor_fitness': 1.0,
                'fitness_promedio': 1.0,
                'fill_pct': 100.0,
                'horarios_parciales': horarios_parciales,
                'objetivo': 1,
                'tiempo_estimado': 'Completado',
                'mensaje': 'Horarios generados exitosamente'
            }
        else:
            # Si no hay horarios, verificar si hay una tarea asíncrona (opcional)
            # Por ahora, devolvemos estado inicial
            progreso = {
                'estado': 'sin_datos',
                'generacion': 0,
                'mejor_fitness': 0.0,
                'fitness_promedio': 0.0,
                'fill_pct': 0.0,
                'horarios_parciales': 0,
                'objetivo': 100,
                'tiempo_estimado': 'Sin datos',
                'mensaje': 'No hay proceso de generación activo'
            }
            
        return JsonResponse(progreso)
        
    except Exception as e:
        return JsonResponse({
            'estado': 'error',
            'mensaje': f'Error: {str(e)}',
            'generacion': 0,
            'mejor_fitness': 0.0,
            'fitness_promedio': 0.0,
            'fill_pct': 0.0,
            'horarios_parciales': 0
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
