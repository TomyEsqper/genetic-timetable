from django.core.management.base import BaseCommand
from horarios.application.services.generador_demand_first import GeneradorDemandFirst
import time

class Command(BaseCommand):
    help = "🧪 Prueba la generación de horarios con lógica Demand-First"

    def add_arguments(self, parser):
        parser.add_argument("--iteraciones", type=int, default=3, help="Número de intentos de generación")
        parser.add_argument("--timeout", type=int, default=120, help="Timeout en segundos por intento (no usado directamente en DF)")

    def handle(self, *args, **options):
        self.stdout.write("🧪 Iniciando pruebas de generación de horarios (Demand-First)...")
        
        iteraciones = options["iteraciones"]
        
        exitosos = 0
        fallidos = 0
        
        for i in range(iteraciones):
            self.stdout.write(f"\n--- INTENTO {i+1}/{iteraciones} ---")
            
            try:
                inicio = time.time()
                
                # Parámetros para Demand First
                generador = GeneradorDemandFirst()
                resultado = generador.generar_horarios(
                    semilla=42 + i,
                    max_iteraciones=1000,
                    paciencia=100
                )
                
                tiempo_total = time.time() - inicio
                
                if resultado and resultado.get('exito'):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ ÉXITO en intento {i+1}:\n"
                            f"   - Calidad: {resultado.get('calidad', 'N/A')}\n"
                            f"   - Slots: {resultado.get('estadisticas', {}).get('slots_generados', 'N/A')}\n"
                            f"   - Tiempo: {tiempo_total:.2f}s"
                        )
                    )
                    exitosos += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  INTENTO {i+1} completado pero sin éxito"
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