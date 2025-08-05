from django.contrib import admin
from .models import (
    ConfiguracionColegio, Profesor, DisponibilidadProfesor,
    Materia, MateriaProfesor, Grado, MateriaGrado,
    Curso, Aula, BloqueHorario, Horario
)

admin.site.register(ConfiguracionColegio)
admin.site.register(Profesor)
admin.site.register(DisponibilidadProfesor)
admin.site.register(Materia)
admin.site.register(MateriaProfesor)
admin.site.register(Grado)
admin.site.register(MateriaGrado)
admin.site.register(Curso)
admin.site.register(Aula)
admin.site.register(BloqueHorario)
admin.site.register(Horario)
