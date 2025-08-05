from django.db import models

class ConfiguracionColegio(models.Model):
    jornada = models.CharField(max_length=20, choices=[('mañana', 'Mañana'), ('tarde', 'Tarde'), ('completa', 'Completa')])
    bloques_por_dia = models.IntegerField()
    duracion_bloque = models.IntegerField()  # en minutos
    dias_clase = models.CharField(max_length=100, default='lunes,martes,miércoles,jueves,viernes')

    def __str__(self):
        return f"Jornada {self.jornada} - {self.bloques_por_dia} bloques/día"

class Profesor(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class DisponibilidadProfesor(models.Model):
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    dia = models.CharField(max_length=15, choices=[
            ('lunes','Lunes'), ('martes','Martes'), ('miércoles','Miércoles'),
            ('jueves','Jueves'), ('viernes','Viernes')
    ])
    bloque_inicio = models.IntegerField()
    bloque_fin = models.IntegerField()

    def __str__(self):
        return f"{self.profesor} - {self.dia} Bloques {self.bloque_inicio}-{self.bloque_fin}"


class Materia(models.Model):
    nombre = models.CharField(max_length=100)
    bloques_por_semana = models.IntegerField()
    jornada_preferida = models.CharField(max_length=20, choices=[
        ('mañana', 'Mañana'), ('tarde', 'Tarde'), ('cualquiera', 'Cualquiera')
    ], default='cualquiera')
    requiere_bloques_consecutivos = models.BooleanField(default=False)
    requiere_aula_especial = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre

class MateriaProfesor(models.Model):
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.profesor} - {self.materia}"

class Grado(models.Model):
    nombre = models.CharField(max_length=20)

    def __str__(self):
        return self.nombre

class MateriaGrado(models.Model):
    grado = models.ForeignKey(Grado, on_delete=models.CASCADE)
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.grado} - {self.materia}"

class Curso(models.Model):
    nombre = models.CharField(max_length=20)
    grado = models.ForeignKey(Grado, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre

class Aula(models.Model):
    nombre = models.CharField(max_length=50)
    tipo = models.CharField(max_length=50, choices=[
        ('comun', 'Común'),
        ('laboratorio', 'Laboratorio'),
        ('arte', 'Arte'),
        ('educacion_fisica', 'Educación Física'),
        ('tecnologia', 'Tecnología')
    ], default='comun')
    capacidad = models.IntegerField(default=40)

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"


class BloqueHorario(models.Model):
    numero = models.IntegerField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    TIPO_CHOICES = [
        ('clase', 'Clase'),
        ('descanso', 'Descanso'),
        ('almuerzo', 'Almuerzo'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='clase')

    def __str__(self):
        return f"Bloque {self.numero} ({self.tipo})"


class Horario(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    aula = models.ForeignKey(Aula, null=True, blank=True, on_delete=models.SET_NULL)
    dia = models.CharField(max_length=15, choices=[
        ('lunes','Lunes'), ('martes','Martes'), ('miércoles','Miércoles'), ('jueves','Jueves'), ('viernes','Viernes')
    ])
    bloque = models.IntegerField()

    def clean(self):
        from django.core.exceptions import ValidationError
        bloque_obj = BloqueHorario.objects.filter(numero=self.bloque).first()
        if bloque_obj and bloque_obj.tipo != 'clase':
            raise ValidationError(f"No se pueden asignar clases en bloques tipo '{bloque_obj.tipo}'.")

    def __str__(self):
        return f"{self.curso} - {self.materia} - {self.dia} Bloque {self.bloque}"
