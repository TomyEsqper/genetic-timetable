from django.core.management.base import BaseCommand
from horarios.application.services.genetico_funcion import generar_horarios_genetico
import time

class Command(BaseCommand):
    help = "🧪 Prueba la generación de horarios con parámetros optimizados"

    def add_arguments(self, parser):
        parser.add_argument("--iteraciones", type=int, default=3, help="Número de intentos de generación")
        parser.add_argument("--timeout", type=int, default=120, help="Timeout en segundos por intento")

    def handle(self, *args, **options):
        self.stdout.write("🧪 Iniciando pruebas de generación de horarios...")
        
        iteraciones = options["iteraciones"]
        timeout = options["timeout"]
        
        exitosos = 0
        fallidos = 0
        
        for i in range(iteraciones):
            self.stdout.write(f"\n--- INTENTO {i+1}/{iteraciones} ---")
            
            try:
                inicio = time.time()
                
                # Parámetros más conservadores para mayor estabilidad
                resultado = generar_horarios_genetico(
                    poblacion_size=30,        # Población más pequeña
                    generaciones=80,          # Menos generaciones
                    prob_cruce=0.8,           # Probabilidad de cruce más baja
                    prob_mutacion=0.15,       # Mutación más conservadora
                    elite=3,                  # Más individuos élite
                    paciencia=20,             # Más paciencia
                    timeout_seg=timeout,      # Timeout configurable
                    semilla=42 + i,           # Semilla diferente cada vez
                    workers=1                 # Un solo worker para estabilidad
                )
                
                tiempo_total = time.time() - inicio
                
                if resultado and resultado.get('mejor_fitness'):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ ÉXITO en intento {i+1}:\n"
                            f"   - Fitness: {resultado.get('mejor_fitness', 'N/A')}\n"
                            f"   - Generaciones: {resultado.get('generaciones_ejecutadas', 'N/A')}\n"
                            f"   - Tiempo: {tiempo_total:.2f}s"
                        )
                    )
                    exitosos += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  INTENTO {i+1} completado pero sin fitness válido"
                        )
                    )
                    fallidos += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ ERROR en intento {i+1}: {str(e)}"
                    )
                )
                fallidos += 1
        
        # Resumen final
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"📊 RESUMEN DE PRUEBAS:")
        self.stdout.write(f"   - Total de intentos: {iteraciones}")
        self.stdout.write(f"   - Exitosos: {exitosos}")
        self.stdout.write(f"   - Fallidos: {fallidos}")
        self.stdout.write(f"   - Tasa de éxito: {(exitosos/iteraciones)*100:.1f}%")
        
        if exitosos > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🎉 ¡La generación de horarios está funcionando!"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"\n💥 Todos los intentos fallaron. Revisar configuración."
                )
            ) 