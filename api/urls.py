from django.urls import path
from . import views

urlpatterns = [
    # Endpoints de lectura estándar
    path('profesores/', views.ProfesorList.as_view(), name='api_profesores'),
    path('materias/', views.MateriaList.as_view(), name='api_materias'),
    path('cursos/', views.CursoList.as_view(), name='api_cursos'),
    path('aulas/', views.AulaList.as_view(), name='api_aulas'),
    path('horarios/', views.HorarioList.as_view(), name='api_horarios'),
    
    # Endpoint principal para generación de horarios (POST)
    path('generar-horario/', views.GenerarHorarioView.as_view(), name='api_generar_horario'),
    
    # Endpoint de validación previa
    path('validar-prerrequisitos/', views.ValidarPrerrequisitosView.as_view(), name='api_validar_prerrequisitos'),
    
    # Endpoint de estado del sistema
    path('estado-sistema/', views.EstadoSistemaView.as_view(), name='api_estado_sistema'),

    # Jobs async
    path('jobs/generar-horario/', views.JobsGenerarHorarioView.as_view(), name='api_jobs_generar_horario'),
    path('jobs/estado/<str:task_id>/', views.JobsEstadoView.as_view(), name='api_jobs_estado'),
    path('jobs/cancelar/<str:task_id>/', views.JobsCancelarView.as_view(), name='api_jobs_cancelar'),

    # Regeneración parcial
    path('regenerar-parcial/', views.RegenerarParcialView.as_view(), name='api_regenerar_parcial'),

    # Exportes por rol
    path('export/curso/<int:curso_id>/<str:formato>/', views.ExportCursoView.as_view(), name='api_export_curso'),
    path('export/profesor/<int:profesor_id>/<str:formato>/', views.ExportProfesorView.as_view(), name='api_export_profesor'),
]
