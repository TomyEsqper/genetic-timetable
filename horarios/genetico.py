import random
from horarios.models import Curso, MateriaGrado, MateriaProfesor, DisponibilidadProfesor, Aula, Horario, BloqueHorario

DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']
def obtener_bloques_disponibles():
    return [b.numero for b in BloqueHorario.objects.filter(tipo='clase').order_by('numero')]

def obtener_disponibilidad(profesor):
    disponibilidad = DisponibilidadProfesor.objects.filter(profesor=profesor)
    return {(d.dia, b) for d in disponibilidad for b in range(d.bloque_inicio, d.bloque_fin + 1)}

def obtener_aula_disponible(dia, bloque, requiere_especial):
    aulas = Aula.objects.filter(tipo='comun' if not requiere_especial else None)
    if requiere_especial:
        aulas = Aula.objects.exclude(tipo='comun')
    for aula in aulas:
        conflicto = Horario.objects.filter(dia=dia, bloque=bloque, aula=aula).exists()
        if not conflicto:
            return aula
    return None

def crear_horario_random(curso):
    horario = []
    materias = MateriaGrado.objects.filter(grado=curso.grado)

    for mg in materias:
        materia = mg.materia
        bloques_necesarios = materia.bloques_por_semana
        posibles_profes = MateriaProfesor.objects.filter(materia=materia)

        if not posibles_profes.exists():
            continue

        profesor = random.choice(posibles_profes).profesor
        disponibilidad = list(obtener_disponibilidad(profesor))
        random.shuffle(disponibilidad)

        asignados = 0
        for dia, bloque in disponibilidad:
            if Horario.objects.filter(curso=curso, dia=dia, bloque=bloque).exists():
                continue
            if Horario.objects.filter(profesor=profesor, dia=dia, bloque=bloque).exists():
                continue

            aula = obtener_aula_disponible(dia, bloque, materia.requiere_aula_especial)
            if aula is None:
                continue

            horario.append({
                'curso': curso,
                'materia': materia,
                'profesor': profesor,
                'aula': aula,
                'dia': dia,
                'bloque': bloque
            })
            asignados += 1
            if asignados == bloques_necesarios:
                break

    return horario

def evaluar(horario):
    puntaje = 0
    usados = set()
    for h in horario:
        clave = (h['curso'].id, h['dia'], h['bloque'])
        prof_clave = (h['profesor'].id, h['dia'], h['bloque'])
        if clave in usados or prof_clave in usados:
            continue
        puntaje += 1
        usados.add(clave)
        usados.add(prof_clave)
    return puntaje

def generar_horarios_genetico(poblacion_size=10, generaciones=30):
    cursos = Curso.objects.all()
    mejor_horario = []

    for curso in cursos:
        poblacion = [crear_horario_random(curso) for _ in range(poblacion_size)]

        for _ in range(generaciones):
            poblacion.sort(key=evaluar, reverse=True)
            nueva_gen = poblacion[:2]  # elitismo

            while len(nueva_gen) < poblacion_size:
                padre = random.choice(poblacion[:5])
                hijo = mutar(padre)
                nueva_gen.append(hijo)

            poblacion = nueva_gen

        mejor = max(poblacion, key=evaluar)
        mejor_horario.extend(mejor)

    # Guardar en base de datos
    Horario.objects.all().delete()
    for item in mejor_horario:
        Horario.objects.create(
            curso=item['curso'],
            materia=item['materia'],
            profesor=item['profesor'],
            aula=item['aula'],
            dia=item['dia'],
            bloque=item['bloque']
        )

    print("✅ Horarios generados con éxito.")

def mutar(horario):
    nuevo = horario.copy()
    if not nuevo:
        return nuevo
    index = random.randint(0, len(nuevo) - 1)
    entrada = nuevo[index]
    nueva_entrada = entrada.copy()
    nueva_entrada['bloque'] = random.choice(obtener_bloques_disponibles())
    nueva_entrada['dia'] = random.choice(DIAS)
    nuevo[index] = nueva_entrada
    return nuevo
