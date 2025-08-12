from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
import re

def validate_nombre_profesor(value):
    """Valida que el nombre del profesor tenga el formato correcto"""
    if not re.match(r'^[A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+$', value):
        raise ValidationError('El nombre debe empezar con mayúscula y contener solo letras y espacios.')
    if len(value.strip()) < 2:
        raise ValidationError('El nombre debe tener al menos 2 caracteres.')

def validate_nombre_materia(value):
    """Valida que el nombre de la materia tenga el formato correcto"""
    if not re.match(r'^[A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+$', value):
        raise ValidationError('El nombre debe empezar con mayúscula y contener solo letras y espacios.')
    if len(value.strip()) < 2:
        raise ValidationError('El nombre debe tener al menos 2 caracteres.')

def validate_bloques_por_semana(value):
    """Valida que los bloques por semana sean razonables"""
    if value < 1:
        raise ValidationError('Debe tener al menos 1 bloque por semana.')
    if value > 40:
        raise ValidationError('No puede tener más de 40 bloques por semana.')

def validate_capacidad_aula(value):
    """Valida que la capacidad del aula sea razonable"""
    if value < 1:
        raise ValidationError('La capacidad debe ser al menos 1.')
    if value > 200:
        raise ValidationError('La capacidad no puede ser mayor a 200.')

class ConfiguracionColegio(models.Model):
    jornada = models.CharField(max_length=20, choices=[('mañana', 'Mañana'), ('tarde', 'Tarde'), ('completa', 'Completa')])
    bloques_por_dia = models.IntegerField(
        validators=[MinValueValidator(1, 'Debe tener al menos 1 bloque por día'), 
                   MaxValueValidator(12, 'No puede tener más de 12 bloques por día')]
    )
    duracion_bloque = models.IntegerField(
        validators=[MinValueValidator(30, 'La duración mínima es 30 minutos'), 
                   MaxValueValidator(120, 'La duración máxima es 120 minutos')]
    )  # en minutos
    dias_clase = models.CharField(max_length=100, default='lunes,martes,miércoles,jueves,viernes')

    def clean(self):
        super().clean()
        dias_validos = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
        dias_ingresados = [dia.strip() for dia in self.dias_clase.split(',')]
        for dia in dias_ingresados:
            if dia not in dias_validos:
                raise ValidationError(f'Día inválido: {dia}')

    def __str__(self):
        return f"Jornada {self.jornada} - {self.bloques_por_dia} bloques/día"

class Profesor(models.Model):
    nombre = models.CharField(max_length=100, validators=[validate_nombre_profesor])

    def clean(self):
        super().clean()
        # Verificar que no exista otro profesor con el mismo nombre
        if Profesor.objects.filter(nombre__iexact=self.nombre).exclude(id=self.id).exists():
            raise ValidationError('Ya existe un profesor con este nombre.')

    def __str__(self):
        return self.nombre

class DisponibilidadProfesor(models.Model):
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    dia = models.CharField(max_length=15, choices=[
            ('lunes','Lunes'), ('martes','Martes'), ('miércoles','Miércoles'),
            ('jueves','Jueves'), ('viernes','Viernes')
    ])
    bloque_inicio = models.IntegerField(
        validators=[MinValueValidator(1, 'El bloque de inicio debe ser al menos 1')]
    )
    bloque_fin = models.IntegerField(
        validators=[MinValueValidator(1, 'El bloque final debe ser al menos 1')]
    )

    def clean(self):
        super().clean()
        if self.bloque_inicio > self.bloque_fin:
            raise ValidationError('El bloque de inicio no puede ser mayor al bloque final.')
        if self.bloque_fin - self.bloque_inicio > 8:
            raise ValidationError('La disponibilidad no puede abarcar más de 8 bloques consecutivos.')

    class Meta:
        unique_together = ['profesor', 'dia']

    def __str__(self):
        return f"{self.profesor} - {self.dia} Bloques {self.bloque_inicio}-{self.bloque_fin}"

class Materia(models.Model):
    nombre = models.CharField(max_length=100, validators=[validate_nombre_materia])
    bloques_por_semana = models.IntegerField(validators=[validate_bloques_por_semana])
    jornada_preferida = models.CharField(max_length=20, choices=[
        ('mañana', 'Mañana'), ('tarde', 'Tarde'), ('cualquiera', 'Cualquiera')
    ], default='cualquiera')
    requiere_bloques_consecutivos = models.BooleanField(default=False)
    requiere_aula_especial = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        # Verificar que no exista otra materia con el mismo nombre
        if Materia.objects.filter(nombre__iexact=self.nombre).exclude(id=self.id).exists():
            raise ValidationError('Ya existe una materia con este nombre.')

    def __str__(self):
        return self.nombre

class MateriaProfesor(models.Model):
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)

    def clean(self):
        super().clean()
        # Verificar que no exista la misma asignación
        if MateriaProfesor.objects.filter(profesor=self.profesor, materia=self.materia).exclude(id=self.id).exists():
            raise ValidationError('Esta asignación de profesor-materia ya existe.')

    class Meta:
        unique_together = ['profesor', 'materia']

    def __str__(self):
        return f"{self.profesor} - {self.materia}"

class Grado(models.Model):
    nombre = models.CharField(max_length=20)

    def clean(self):
        super().clean()
        if not re.match(r'^[A-Z0-9\s]+$', self.nombre):
            raise ValidationError('El nombre del grado debe contener solo letras mayúsculas, números y espacios.')
        if Grado.objects.filter(nombre__iexact=self.nombre).exclude(id=self.id).exists():
            raise ValidationError('Ya existe un grado con este nombre.')

    def __str__(self):
        return self.nombre

class MateriaGrado(models.Model):
    grado = models.ForeignKey(Grado, on_delete=models.CASCADE)
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)

    def clean(self):
        super().clean()
        if MateriaGrado.objects.filter(grado=self.grado, materia=self.materia).exclude(id=self.id).exists():
            raise ValidationError('Esta asignación de materia-grado ya existe.')

    class Meta:
        unique_together = ['grado', 'materia']

    def __str__(self):
        return f"{self.grado} - {self.materia}"

class Curso(models.Model):
    nombre = models.CharField(max_length=20)
    grado = models.ForeignKey(Grado, on_delete=models.CASCADE)
    aula_fija = models.ForeignKey('Aula', on_delete=models.SET_NULL, null=True, blank=True, related_name='cursos_asignados')

    def clean(self):
        super().clean()
        if not re.match(r'^[A-Z0-9\s]+$', self.nombre):
            raise ValidationError('El nombre del curso debe contener solo letras mayúsculas, números y espacios.')
        if Curso.objects.filter(nombre__iexact=self.nombre).exclude(id=self.id).exists():
            raise ValidationError('Ya existe un curso con este nombre.')

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
    capacidad = models.IntegerField(default=40, validators=[validate_capacidad_aula])

    def clean(self):
        super().clean()
        if not re.match(r'^[A-Z0-9\s\-]+$', self.nombre):
            raise ValidationError('El nombre del aula debe contener solo letras mayúsculas, números, espacios y guiones.')
        if Aula.objects.filter(nombre__iexact=self.nombre).exclude(id=self.id).exists():
            raise ValidationError('Ya existe un aula con este nombre.')

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"

class BloqueHorario(models.Model):
    numero = models.IntegerField(
        validators=[MinValueValidator(1, 'El número de bloque debe ser al menos 1')]
    )
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    TIPO_CHOICES = [
        ('clase', 'Clase'),
        ('descanso', 'Descanso'),
        ('almuerzo', 'Almuerzo'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='clase')

    def clean(self):
        super().clean()
        if self.hora_inicio >= self.hora_fin:
            raise ValidationError('La hora de inicio debe ser anterior a la hora de fin.')

    class Meta:
        unique_together = ['numero', 'tipo']

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
    bloque = models.IntegerField(
        validators=[MinValueValidator(1, 'El bloque debe ser al menos 1')]
    )

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        
        # Verificar que el bloque sea de tipo 'clase'
        bloque_obj = BloqueHorario.objects.filter(numero=self.bloque).first()
        if bloque_obj and bloque_obj.tipo != 'clase':
            raise ValidationError(f"No se pueden asignar clases en bloques tipo '{bloque_obj.tipo}'.")
        
        # Verificar que el profesor tenga disponibilidad en ese día y bloque
        if not DisponibilidadProfesor.objects.filter(
            profesor=self.profesor,
            dia=self.dia,
            bloque_inicio__lte=self.bloque,
            bloque_fin__gte=self.bloque
        ).exists():
            raise ValidationError(f"El profesor {self.profesor.nombre} no tiene disponibilidad en {self.dia} bloque {self.bloque}.")
        
        # Verificar que el aula sea apropiada para la materia
        if self.aula and self.materia.requiere_aula_especial and self.aula.tipo == 'comun':
            raise ValidationError(f"La materia {self.materia.nombre} requiere un aula especial, no un aula común.")

    class Meta:
        # Restricciones para evitar solapes
        unique_together = [
            ['curso', 'dia', 'bloque'],  # Un curso no puede tener dos materias en el mismo día y bloque
            ['profesor', 'dia', 'bloque']  # Un profesor no puede estar en dos lugares al mismo tiempo
        ]

    def __str__(self):
        return f"{self.curso} - {self.materia} - {self.dia} Bloque {self.bloque}"
