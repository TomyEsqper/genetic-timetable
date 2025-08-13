from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
import re
from django.utils import timezone

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

class TrackerCorrida(models.Model):
    """
    Modelo para tracking de corridas del algoritmo genético.
    Permite comparar configuraciones y reproducir resultados.
    """
    
    # Identificación única
    run_id = models.CharField(max_length=50, unique=True)
    timestamp_inicio = models.DateTimeField(auto_now_add=True)
    timestamp_fin = models.DateTimeField(null=True, blank=True)
    
    # Configuración del algoritmo
    semilla = models.IntegerField()
    poblacion_size = models.IntegerField()
    generaciones = models.IntegerField()
    prob_cruce = models.FloatField()
    prob_mutacion = models.FloatField()
    elite = models.IntegerField()
    paciencia = models.IntegerField()
    workers = models.IntegerField()
    tournament_size = models.IntegerField()
    random_immigrants_rate = models.FloatField()
    
    # Pesos del fitness
    peso_huecos = models.FloatField()
    peso_primeras_ultimas = models.FloatField()
    peso_balance_dia = models.FloatField()
    peso_bloques_semana = models.FloatField()
    
    # Resultados
    exito = models.BooleanField(default=False)
    fitness_final = models.FloatField()
    generaciones_completadas = models.IntegerField()
    convergencia = models.BooleanField(default=False)
    tiempo_total_s = models.FloatField()
    
    # KPIs de calidad
    num_solapes = models.IntegerField(default=0)
    num_huecos = models.IntegerField(default=0)
    porcentaje_primeras_ultimas = models.FloatField(default=0.0)
    desviacion_balance_dia = models.FloatField(default=0.0)
    
    # Estado del sistema
    estado_sistema_hash = models.CharField(max_length=64)  # Hash de los datos de entrada
    num_cursos = models.IntegerField()
    num_profesores = models.IntegerField()
    num_materias = models.IntegerField()
    
    # Metadata
    comentarios = models.TextField(blank=True)
    tags = models.CharField(max_length=200, blank=True)  # CSV de tags
    
    class Meta:
        ordering = ['-timestamp_inicio']
        indexes = [
            models.Index(fields=['exito', 'fitness_final']),
            models.Index(fields=['semilla', 'timestamp_inicio']),
            models.Index(fields=['estado_sistema_hash']),
        ]
    
    def __str__(self):
        return f"Run {self.run_id} - {self.timestamp_inicio.strftime('%Y-%m-%d %H:%M')} - Fitness: {self.fitness_final:.2f}"
    
    def calcular_hash_sistema(self):
        """Calcula hash del estado actual del sistema para reproducibilidad"""
        import hashlib
        import json
        
        # Obtener estado del sistema
        estado = {
            'cursos': list(Curso.objects.values('id', 'nombre', 'grado_id', 'aula_fija_id').order_by('id')),
            'profesores': list(Profesor.objects.values('id', 'nombre').order_by('id')),
            'materias': list(Materia.objects.values('id', 'nombre', 'bloques_por_semana').order_by('id')),
            'materia_grado': list(MateriaGrado.objects.values('materia_id', 'grado_id').order_by('materia_id')),
            'materia_profesor': list(MateriaProfesor.objects.values('materia_id', 'profesor_id').order_by('materia_id')),
            'disponibilidad': list(DisponibilidadProfesor.objects.values('profesor_id', 'dia', 'bloque_inicio', 'bloque_fin').order_by('profesor_id')),
            'bloques': list(BloqueHorario.objects.values('numero', 'tipo').order_by('numero')),
        }
        
        # Convertir a JSON y calcular hash
        estado_json = json.dumps(estado, sort_keys=True)
        return hashlib.sha256(estado_json.encode()).hexdigest()
    
    def actualizar_estado_sistema(self):
        """Actualiza el estado del sistema con conteos actuales"""
        self.num_cursos = Curso.objects.count()
        self.num_profesores = Profesor.objects.count()
        self.num_materias = Materia.objects.count()
        self.estado_sistema_hash = self.calcular_hash_sistema()
    
    def es_reproducible(self):
        """Verifica si la corrida es reproducible con el estado actual"""
        return self.estado_sistema_hash == self.calcular_hash_sistema()
    
    def obtener_configuracion(self):
        """Retorna la configuración como diccionario para reproducir"""
        return {
            'semilla': self.semilla,
            'poblacion_size': self.poblacion_size,
            'generaciones': self.generaciones,
            'prob_cruce': self.prob_cruce,
            'prob_mutacion': self.prob_mutacion,
            'elite': self.elite,
            'paciencia': self.paciencia,
            'workers': self.workers,
            'tournament_size': self.tournament_size,
            'random_immigrants_rate': self.random_immigrants_rate,
            'peso_huecos': self.peso_huecos,
            'peso_primeras_ultimas': self.peso_primeras_ultimas,
            'peso_balance_dia': self.peso_balance_dia,
            'peso_bloques_semana': self.peso_bloques_semana,
        }
    
    def marcar_como_exitosa(self, resultado):
        """Marca la corrida como exitosa y guarda resultados"""
        self.exito = True
        self.fitness_final = resultado.get('mejor_fitness', 0.0)
        self.generaciones_completadas = resultado.get('generaciones_completadas', 0)
        self.convergencia = resultado.get('convergencia', False)
        self.tiempo_total_s = resultado.get('tiempo_total_s', 0.0)
        
        # Extraer KPIs si están disponibles
        if 'metricas' in resultado:
            metricas = resultado['metricas']
            self.num_solapes = metricas.get('num_solapes', 0)
            self.num_huecos = metricas.get('num_huecos', 0)
            self.porcentaje_primeras_ultimas = metricas.get('porcentaje_primeras_ultimas', 0.0)
            self.desviacion_balance_dia = metricas.get('desviacion_balance_dia', 0.0)
        
        self.timestamp_fin = timezone.now()
        self.save()
    
    def marcar_como_fallida(self, error, tiempo_total):
        """Marca la corrida como fallida"""
        self.exito = False
        self.tiempo_total_s = tiempo_total
        self.timestamp_fin = timezone.now()
        self.comentarios = f"Error: {error}"
        self.save()
    
    @classmethod
    def obtener_mejores_corridas(cls, limite=10):
        """Obtiene las mejores corridas exitosas ordenadas por fitness"""
        return cls.objects.filter(exito=True).order_by('fitness_final')[:limite]
    
    @classmethod
    def obtener_corridas_por_semilla(cls, semilla):
        """Obtiene todas las corridas con una semilla específica"""
        return cls.objects.filter(semilla=semilla).order_by('-timestamp_inicio')
    
    @classmethod
    def obtener_corridas_reproducibles(cls):
        """Obtiene corridas que pueden reproducirse con el estado actual"""
        corridas = cls.objects.filter(exito=True)
        return [c for c in corridas if c.es_reproducible()]
