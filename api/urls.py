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
]
