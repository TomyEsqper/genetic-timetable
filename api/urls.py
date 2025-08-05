from django.urls import path
from . import views
from .views import GenerarHorarioView
from .views import GenerarHorarioDesacopladoView


urlpatterns = [
    path('profesores/', views.ProfesorList.as_view(), name='api_profesores'),
    path('materias/', views.MateriaList.as_view(), name='api_materias'),
    path('cursos/', views.CursoList.as_view(), name='api_cursos'),
    path('aulas/', views.AulaList.as_view(), name='api_aulas'),
    path('horarios/', views.HorarioList.as_view(), name='api_horarios'),
    path('generar/', GenerarHorarioView.as_view(), name='api_generar_horario'),
    path('generar-horario-json/', GenerarHorarioDesacopladoView.as_view(), name='generar_horario_json'),

]
