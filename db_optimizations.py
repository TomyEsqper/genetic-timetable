"""Utilidades para optimizar el rendimiento de la base de datos PostgreSQL.

Este módulo proporciona funciones para optimizar el rendimiento de PostgreSQL
cuando se trabaja con grandes volúmenes de datos en el sistema de horarios.

Nota: Este módulo asume que se está utilizando PostgreSQL como base de datos.
Para otros motores de base de datos, algunas optimizaciones pueden no ser aplicables.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from django.db import connection, transaction
from django.conf import settings


def check_postgres_availability() -> bool:
    """Verifica si se está utilizando PostgreSQL como motor de base de datos.
    
    Returns:
        bool: True si se está utilizando PostgreSQL, False en caso contrario.
    """
    try:
        engine = settings.DATABASES['default']['ENGINE']
        return 'postgresql' in engine
    except (KeyError, AttributeError):
        return False


def optimize_postgres_for_horarios() -> Dict[str, Any]:
    """Aplica optimizaciones específicas para PostgreSQL en el contexto de horarios.
    
    Esta función crea índices específicos para mejorar el rendimiento de las consultas
    relacionadas con la generación y consulta de horarios escolares.
    
    Returns:
        Dict[str, Any]: Resultado de las optimizaciones aplicadas.
    """
    if not check_postgres_availability():
        logging.warning("No se está utilizando PostgreSQL. Las optimizaciones no son aplicables.")
        return {'status': 'skipped', 'reason': 'PostgreSQL no detectado'}
    
    optimizations_applied = []
    errors = []
    
    # Lista de índices a crear
    indices = [
        # Índices para DisponibilidadProfesor (consultas frecuentes por profesor y día/hora)
        "CREATE INDEX IF NOT EXISTS idx_disponibilidad_profesor ON horarios_disponibilidadprofesor(profesor_id, dia, hora);",
        
        # Índices para Horario (consultas frecuentes por curso, profesor, día/hora)
        "CREATE INDEX IF NOT EXISTS idx_horario_curso ON horarios_horario(curso_id);",
        "CREATE INDEX IF NOT EXISTS idx_horario_profesor ON horarios_horario(profesor_id);",
        "CREATE INDEX IF NOT EXISTS idx_horario_dia_hora ON horarios_horario(dia, hora);",
        "CREATE INDEX IF NOT EXISTS idx_horario_completo ON horarios_horario(curso_id, profesor_id, dia, hora);",
        
        # Índices para MateriaProfesor (consultas frecuentes por profesor y materia)
        "CREATE INDEX IF NOT EXISTS idx_materia_profesor ON horarios_materiaprofesor(profesor_id, materia_id);",
        
        # Índices para MateriaGrado (consultas frecuentes por grado)
        "CREATE INDEX IF NOT EXISTS idx_materia_grado ON horarios_materiagrado(grado_id);",
    ]
    
    # Configuraciones de PostgreSQL para mejorar rendimiento
    configs = [
        # Aumentar work_mem para operaciones de ordenamiento y hash
        "SET work_mem = '16MB';",
        
        # Aumentar maintenance_work_mem para operaciones de mantenimiento
        "SET maintenance_work_mem = '64MB';",
        
        # Configurar effective_cache_size para optimizar planificación de consultas
        "SET effective_cache_size = '1GB';",
        
        # Configurar random_page_cost para SSD
        "SET random_page_cost = 1.1;",
    ]
    
    try:
        with connection.cursor() as cursor:
            # Aplicar configuraciones
            for config in configs:
                try:
                    cursor.execute(config)
                    optimizations_applied.append(f"Configuración aplicada: {config}")
                except Exception as e:
                    errors.append(f"Error al aplicar configuración {config}: {str(e)}")
            
            # Crear índices
            for index_sql in indices:
                try:
                    cursor.execute(index_sql)
                    optimizations_applied.append(f"Índice creado: {index_sql}")
                except Exception as e:
                    errors.append(f"Error al crear índice {index_sql}: {str(e)}")
        
        logging.info(f"Optimizaciones de PostgreSQL aplicadas: {len(optimizations_applied)} exitosas, {len(errors)} errores")
        return {
            'status': 'success',
            'optimizations_applied': optimizations_applied,
            'errors': errors
        }
    
    except Exception as e:
        logging.error(f"Error al aplicar optimizaciones de PostgreSQL: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


def create_materialized_view_for_disponibilidad() -> Dict[str, Any]:
    """Crea una vista materializada para la disponibilidad de profesores.
    
    Esta vista materializada mejora el rendimiento de las consultas de disponibilidad
    que son frecuentes durante la generación de horarios.
    
    Returns:
        Dict[str, Any]: Resultado de la creación de la vista materializada.
    """
    if not check_postgres_availability():
        return {'status': 'skipped', 'reason': 'PostgreSQL no detectado'}
    
    sql = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_disponibilidad_profesores AS
    SELECT 
        p.id AS profesor_id,
        p.nombre AS profesor_nombre,
        d.dia,
        d.hora,
        d.disponible,
        array_agg(DISTINCT mp.materia_id) AS materias_ids
    FROM 
        horarios_profesor p
    JOIN 
        horarios_disponibilidadprofesor d ON p.id = d.profesor_id
    LEFT JOIN 
        horarios_materiaprofesor mp ON p.id = mp.profesor_id
    GROUP BY 
        p.id, p.nombre, d.dia, d.hora, d.disponible
    WITH DATA;
    
    CREATE INDEX IF NOT EXISTS idx_mv_disponibilidad_dia_hora ON mv_disponibilidad_profesores(dia, hora);
    CREATE INDEX IF NOT EXISTS idx_mv_disponibilidad_profesor ON mv_disponibilidad_profesores(profesor_id);
    """
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        
        logging.info("Vista materializada para disponibilidad de profesores creada exitosamente")
        return {
            'status': 'success',
            'message': 'Vista materializada creada exitosamente'
        }
    
    except Exception as e:
        logging.error(f"Error al crear vista materializada: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


def refresh_materialized_views() -> Dict[str, Any]:
    """Actualiza las vistas materializadas para reflejar los cambios en los datos.
    
    Returns:
        Dict[str, Any]: Resultado de la actualización de las vistas materializadas.
    """
    if not check_postgres_availability():
        return {'status': 'skipped', 'reason': 'PostgreSQL no detectado'}
    
    views = [
        'mv_disponibilidad_profesores'
    ]
    
    results = {}
    
    try:
        with connection.cursor() as cursor:
            for view in views:
                try:
                    cursor.execute(f"REFRESH MATERIALIZED VIEW {view};")
                    results[view] = 'success'
                except Exception as e:
                    results[view] = f'error: {str(e)}'
        
        logging.info(f"Vistas materializadas actualizadas: {results}")
        return {
            'status': 'success',
            'results': results
        }
    
    except Exception as e:
        logging.error(f"Error al actualizar vistas materializadas: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


def optimize_bulk_horario_creation(horarios_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Optimiza la creación masiva de registros de horarios.
    
    Esta función utiliza la funcionalidad de inserción masiva de PostgreSQL para
    mejorar el rendimiento al crear múltiples registros de horarios a la vez.
    
    Args:
        horarios_data: Lista de diccionarios con los datos de los horarios a crear.
            Cada diccionario debe contener: curso_id, profesor_id, materia_id, dia, hora, aula_id, tipo.
    
    Returns:
        Dict[str, Any]: Resultado de la operación de inserción masiva.
    """
    if not check_postgres_availability():
        return {'status': 'skipped', 'reason': 'PostgreSQL no detectado'}
    
    if not horarios_data:
        return {'status': 'skipped', 'reason': 'No hay datos para insertar'}
    
    # Preparar la consulta SQL para inserción masiva
    sql = """
    INSERT INTO horarios_horario 
        (curso_id, profesor_id, materia_id, dia, hora, aula_id, tipo) 
    VALUES 
        %s
    """
    
    # Preparar los valores para la inserción
    values = []
    for h in horarios_data:
        values.append((
            h.get('curso_id'),
            h.get('profesor_id'),
            h.get('materia_id'),
            h.get('dia'),
            h.get('hora'),
            h.get('aula_id'),
            h.get('tipo', 'clase')
        ))
    
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # Primero eliminamos los horarios existentes si es necesario
                cursor.execute("DELETE FROM horarios_horario WHERE curso_id IN %s", 
                              [tuple(set(h.get('curso_id') for h in horarios_data))])
                
                # Luego insertamos los nuevos horarios
                cursor.executemany(sql, values)
        
        logging.info(f"Inserción masiva de {len(values)} horarios completada exitosamente")
        return {
            'status': 'success',
            'inserted_count': len(values)
        }
    
    except Exception as e:
        logging.error(f"Error en inserción masiva de horarios: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


def get_optimized_query_for_horarios(colegio_id: int) -> str:
    """Genera una consulta SQL optimizada para obtener los horarios de un colegio.
    
    Esta función devuelve una consulta SQL optimizada que puede ser utilizada
    para obtener los horarios de un colegio específico con un rendimiento mejorado.
    
    Args:
        colegio_id: ID del colegio para el que se generará la consulta.
    
    Returns:
        str: Consulta SQL optimizada.
    """
    return """
    SELECT 
        h.id,
        c.id AS curso_id,
        c.nombre AS curso_nombre,
        g.id AS grado_id,
        g.nombre AS grado_nombre,
        p.id AS profesor_id,
        p.nombre AS profesor_nombre,
        m.id AS materia_id,
        m.nombre AS materia_nombre,
        h.dia,
        h.hora,
        a.id AS aula_id,
        a.nombre AS aula_nombre,
        h.tipo
    FROM 
        horarios_horario h
    JOIN 
        horarios_curso c ON h.curso_id = c.id
    JOIN 
        horarios_grado g ON c.grado_id = g.id
    JOIN 
        horarios_profesor p ON h.profesor_id = p.id
    JOIN 
        horarios_materia m ON h.materia_id = m.id
    LEFT JOIN 
        horarios_aula a ON h.aula_id = a.id
    WHERE 
        g.colegio_id = %s
    ORDER BY 
        c.nombre, h.dia, h.hora
    """


def apply_all_optimizations() -> Dict[str, Any]:
    """Aplica todas las optimizaciones disponibles para PostgreSQL.
    
    Returns:
        Dict[str, Any]: Resultado de todas las optimizaciones aplicadas.
    """
    results = {}
    
    # Verificar disponibilidad de PostgreSQL
    if not check_postgres_availability():
        return {'status': 'skipped', 'reason': 'PostgreSQL no detectado'}
    
    # Aplicar optimizaciones básicas
    results['basic_optimizations'] = optimize_postgres_for_horarios()
    
    # Crear vistas materializadas
    results['materialized_views'] = create_materialized_view_for_disponibilidad()
    
    logging.info("Todas las optimizaciones de PostgreSQL han sido aplicadas")
    return {
        'status': 'success',
        'results': results
    }