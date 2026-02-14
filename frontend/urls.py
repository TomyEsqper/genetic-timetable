from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('portal/dashboard/', views.dashboard_portal, name='dashboard_portal'),
    path('portal/como-probar/', views.how_to_portal, name='how_to_portal'),
    path('panel/', views.panel_coordinador, name='panel_coordinador'),
    path('documentacion/', views.portal_docs, name='docs_portal'),
    path('dashboard/horarios/', views.dashboard, name='dashboard'),
    path('curso/<int:curso_id>/', views.horario_curso, name='horario_curso'),
    path('profesor/<int:profesor_id>/', views.horario_profesor, name='horario_profesor'),
    path('aula/<int:aula_id>/', views.horario_aula, name='horario_aula'),
    path('validar/', views.validar_datos, name='validar_datos'),
    path('cursos/', views.lista_cursos, name='lista_cursos'),
    path('profesores/', views.lista_profesores, name='lista_profesores'),
    path('horario-ajax/', views.horario_ajax, name='horario_ajax'),
    path('estadisticas-ajax/', views.estadisticas_ajax, name='estadisticas_ajax'),
    path('progreso-ajax/', views.progreso_ajax, name='progreso_ajax'),
    path('limpiar-cache-progreso/', views.limpiar_cache_progreso, name='limpiar_cache_progreso'),
    path('generar-horario/', views.generar_horario, name='generar_horario'),
    # Alias de compatibilidad para enlaces antiguos
    path('generar/', views.generar_horario, name='generar_horario_alias'),
    path('pdf/curso/<int:curso_id>/', views.pdf_curso, name='pdf_curso'),
    path('descargar-excel/', views.descargar_excel, name='descargar_excel'),
    path('mover-horario-ajax/', views.mover_horario_ajax, name='mover_horario_ajax'),
]
