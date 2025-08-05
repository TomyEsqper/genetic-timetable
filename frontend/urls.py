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

    # Descargar Excel
    path('descargar/', views.descargar_excel, name='descargar_excel'),

    path('generar/', views.generar_horario, name='generar_horario'),
    path('validar/', views.validar_datos, name='validar_datos'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('pdf/curso/<int:curso_id>/', views.pdf_curso, name='pdf_curso'),

]
