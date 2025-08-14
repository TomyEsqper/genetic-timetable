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
    
    # Nuevos campos para gestión de carga horaria
    max_bloques_por_semana = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Máximo número de bloques que puede dictar por semana"
    )
    puede_dictar_relleno = models.BooleanField(
        default=True,
        help_text="Indica si el profesor puede dictar materias de relleno"
    )
    especialidad = models.CharField(
        max_length=100,
        blank=True,
        help_text="Área de especialidad del profesor"
    )

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
    
    # Nuevos campos para materias de relleno y reglas pedagógicas
    es_relleno = models.BooleanField(
        default=False,
        help_text="Indica si esta materia puede usarse como relleno para completar horarios"
    )
    prioridad = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Prioridad de la materia (1=alta, 10=baja). Materias de relleno suelen tener prioridad baja"
    )
    max_bloques_por_dia = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(6)],
        help_text="Máximo número de bloques de esta materia que puede tener un curso en un día"
    )
    requiere_doble_bloque = models.BooleanField(
        default=False,
        help_text="Indica si la materia requiere bloques consecutivos (ej: laboratorios)"
    )
    
    TIPO_MATERIA_CHOICES = [
        ('obligatoria', 'Obligatoria'),
        ('relleno', 'Relleno'),
        ('electiva', 'Electiva'),
        ('proyecto', 'Proyecto'),
    ]
    tipo_materia = models.CharField(
        max_length=20,
        choices=TIPO_MATERIA_CHOICES,
        default='obligatoria',
        help_text="Tipo de materia para clasificación y priorización"
    )

    def clean(self):
        super().clean()
        # Verificar que no exista otra materia con el mismo nombre
        if Materia.objects.filter(nombre__iexact=self.nombre).exclude(id=self.id).exists():
            raise ValidationError('Ya existe una materia con este nombre.')
        
        # Validaciones específicas para materias de relleno
        if self.es_relleno:
            if self.prioridad < 5:
                raise ValidationError('Las materias de relleno deben tener prioridad baja (≥5)')
            if self.tipo_materia not in ['relleno', 'proyecto']:
                self.tipo_materia = 'relleno'

    def __str__(self):
        tipo_str = " (Relleno)" if self.es_relleno else ""
        return f"{self.nombre}{tipo_str}"

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

class Slot(models.Model):
    dia = models.CharField(max_length=15, choices=[
            ('lunes','Lunes'), ('martes','Martes'), ('miércoles','Miércoles'),
            ('jueves','Jueves'), ('viernes','Viernes')
    ])
    bloque = models.IntegerField(validators=[MinValueValidator(1)])
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    tipo = models.CharField(max_length=20, choices=[
        ('clase', 'Clase'), ('descanso', 'Descanso'), ('almuerzo', 'Almuerzo')
    ], default='clase')

    def clean(self):
        super().clean()
        if self.hora_inicio >= self.hora_fin:
            raise ValidationError('La hora de inicio debe ser anterior a la hora de fin.')

    class Meta:
        unique_together = ['dia', 'bloque']
        indexes = [
            models.Index(fields=['dia', 'bloque']),
        ]

    def __str__(self):
        return f"{self.dia} - Bloque {self.bloque} ({self.tipo})"

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
    slot = models.ForeignKey('Slot', null=True, blank=True, on_delete=models.SET_NULL)

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
        constraints = [
            models.UniqueConstraint(fields=['curso', 'slot'], name='uniq_horario_curso_slot'),
            models.UniqueConstraint(fields=['profesor', 'slot'], name='uniq_horario_profesor_slot'),
        ]

    def __str__(self):
        return f"{self.curso} - {self.materia} - {self.dia} Bloque {self.bloque}"

class ProfesorSlot(models.Model):
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    slot = models.ForeignKey(Slot, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['profesor', 'slot']
        indexes = [
            models.Index(fields=['profesor', 'slot']),
        ]

    def __str__(self):
        return f"{self.profesor} @ {self.slot}"

class CursoMateriaRequerida(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)
    bloques_requeridos = models.IntegerField(validators=[MinValueValidator(0)])

    class Meta:
        unique_together = ['curso', 'materia']
        indexes = [
            models.Index(fields=['curso', 'materia']),
        ]

    def __str__(self):
        return f"{self.curso} - {self.materia}: {self.bloques_requeridos} bloques"

class ReglaPedagogica(models.Model):
    """
    Modelo para definir reglas pedagógicas específicas del colegio
    """
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(help_text="Descripción detallada de la regla")
    activa = models.BooleanField(default=True)
    
    # Tipos de reglas
    TIPO_REGLA_CHOICES = [
        ('max_materia_dia', 'Máximo de una materia por día'),
        ('bloques_consecutivos', 'Bloques consecutivos requeridos'),
        ('distribucion_semanal', 'Distribución semanal equilibrada'),
        ('incompatibilidad', 'Materias incompatibles'),
        ('prioridad_horario', 'Prioridad de horario'),
    ]
    tipo_regla = models.CharField(max_length=30, choices=TIPO_REGLA_CHOICES)
    
    # Parámetros de la regla (JSON)
    parametros = models.JSONField(
        default=dict,
        help_text="Parámetros específicos de la regla en formato JSON"
    )
    
    # Prioridad de aplicación (1=alta, 10=baja)
    prioridad = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['prioridad', 'nombre']
        verbose_name = "Regla Pedagógica"
        verbose_name_plural = "Reglas Pedagógicas"
    
    def __str__(self):
        estado = "✓" if self.activa else "✗"
        return f"{estado} {self.nombre} (P{self.prioridad})"

class ConfiguracionCurso(models.Model):
    """
    Configuración específica por curso para manejo de carga horaria y relleno
    """
    curso = models.OneToOneField(Curso, on_delete=models.CASCADE, related_name='configuracion')
    
    # Configuración de slots
    slots_objetivo = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Número objetivo de slots/bloques por semana para este curso"
    )
    
    permite_relleno = models.BooleanField(
        default=True,
        help_text="Permite usar materias de relleno para completar la carga horaria"
    )
    
    min_bloques_relleno = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Mínimo número de bloques de relleno requeridos"
    )
    
    max_bloques_relleno = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Máximo número de bloques de relleno permitidos"
    )
    
    # Preferencias de distribución
    distribucion_equilibrada = models.BooleanField(
        default=True,
        help_text="Intenta distribuir las materias equilibradamente durante la semana"
    )
    
    evitar_huecos = models.BooleanField(
        default=True,
        help_text="Evita dejar bloques vacíos entre clases"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def clean(self):
        super().clean()
        if self.min_bloques_relleno > self.max_bloques_relleno:
            raise ValidationError('El mínimo de bloques de relleno no puede ser mayor al máximo')
    
    def calcular_bloques_faltantes(self):
        """Calcula cuántos bloques de relleno se necesitan para completar el objetivo"""
        # Obtener materias obligatorias del curso
        materias_obligatorias = MateriaGrado.objects.filter(
            grado=self.curso.grado,
            materia__es_relleno=False
        )
        
        total_obligatorios = sum(mg.materia.bloques_por_semana for mg in materias_obligatorias)
        faltantes = max(0, self.slots_objetivo - total_obligatorios)
        
        return min(faltantes, self.max_bloques_relleno)
    
    class Meta:
        verbose_name = "Configuración de Curso"
        verbose_name_plural = "Configuraciones de Curso"
    
    def __str__(self):
        return f"Config {self.curso.nombre} ({self.slots_objetivo} slots)"

class MateriaRelleno(models.Model):
    """
    Modelo específico para gestionar materias de relleno disponibles
    """
    materia = models.OneToOneField(
        Materia, 
        on_delete=models.CASCADE, 
        limit_choices_to={'es_relleno': True},
        related_name='config_relleno'
    )
    
    # Configuración específica de relleno
    flexible_bloques = models.BooleanField(
        default=True,
        help_text="Permite ajustar el número de bloques según necesidad"
    )
    
    min_bloques = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Mínimo número de bloques cuando se usa como relleno"
    )
    
    max_bloques = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1)],
        help_text="Máximo número de bloques cuando se usa como relleno"
    )
    
    # Compatibilidad con grados
    grados_compatibles = models.ManyToManyField(
        Grado,
        blank=True,
        help_text="Grados en los que se puede usar esta materia de relleno"
    )
    
    # Profesores que pueden dictarla
    profesores_disponibles = models.ManyToManyField(
        Profesor,
        limit_choices_to={'puede_dictar_relleno': True},
        help_text="Profesores que pueden dictar esta materia de relleno"
    )
    
    activa = models.BooleanField(default=True)
    
    def clean(self):
        super().clean()
        if not self.materia.es_relleno:
            raise ValidationError('Solo se pueden configurar materias marcadas como relleno')
        if self.min_bloques > self.max_bloques:
            raise ValidationError('El mínimo de bloques no puede ser mayor al máximo')
    
    class Meta:
        verbose_name = "Configuración de Materia de Relleno"
        verbose_name_plural = "Configuraciones de Materias de Relleno"
    
    def __str__(self):
        return f"Relleno: {self.materia.nombre} ({self.min_bloques}-{self.max_bloques} bloques)"

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

class Run(models.Model):
	params_json = models.JSONField()
	dataset_hash = models.CharField(max_length=64)
	started_at = models.DateTimeField(auto_now_add=True)
	ended_at = models.DateTimeField(null=True, blank=True)
	status = models.CharField(max_length=20, choices=[('queued','queued'),('running','running'),('done','done'),('failed','failed')], default='queued')
	best_obj = models.FloatField(default=0.0)
	log_path = models.CharField(max_length=255, blank=True)
	class Meta:
		indexes = [
			models.Index(fields=['started_at']),
			models.Index(fields=['status']),
		]

class RunMetric(models.Model):
	run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name='metrics')
	gen = models.IntegerField()
	best = models.FloatField()
	avg = models.FloatField()
	fill_pct = models.FloatField()
	conflicts = models.IntegerField(default=0)
	t_s = models.FloatField()
	class Meta:
		unique_together = ['run', 'gen']
		indexes = [models.Index(fields=['run','gen'])]
