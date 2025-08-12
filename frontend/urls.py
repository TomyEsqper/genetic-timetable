from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),

    # Vista por curso
    path('curso/<int:curso_id>/', views.horario_curso, name='horario_curso'),

    # Vista por profesor
    path('profesor/<int:profesor_id>/', views.horario_profesor, name='horario_profesor'),

    # Vista por aula
    path('aula/<int:aula_id>/', views.horario_aula, name='horario_aula'),

    # Descargar CSV
    path('descargar/', views.descargar_excel, name='descargar_excel'),
    path('descargar/por-curso/', views.descargar_excel_por_curso, name='descargar_excel_por_curso'),
    path('descargar/por-profesor/', views.descargar_excel_por_profesor, name='descargar_excel_por_profesor'),

    path('generar/', views.generar_horario, name='generar_horario'),
    path('validar/', views.validar_datos, name='validar_datos'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('pdf/curso/<int:curso_id>/', views.pdf_curso, name='pdf_curso'),

    # Nuevas vistas con paginación
    path('cursos/', views.lista_cursos, name='lista_cursos'),
    path('profesores/', views.lista_profesores, name='lista_profesores'),

    # Vistas AJAX
    path('horario-ajax/', views.horario_ajax, name='horario_ajax'),
    path('estadisticas-ajax/', views.estadisticas_ajax, name='estadisticas_ajax'),
]
