import json
import requests
import sys

# URL del servidor AWS (HTTPS)
URL = "https://52.14.216.149/api/engine/solve/"
# Archivo de payload
PAYLOAD_FILE = "payload_completo_3_cursos.json"

def main():
    print(f"Leyendo payload de {PAYLOAD_FILE}...")
    try:
        with open(PAYLOAD_FILE, 'r', encoding='utf-8') as f:
            payload = json.load(f)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {PAYLOAD_FILE}")
        return

    print(f"Enviando POST a {URL}...")
    print("Nota: Se ignora la verificación SSL (verify=False) para evitar errores de certificado self-signed.")
    
    try:
        # verify=False para aceptar certificados self-signed si es necesario
        response = requests.post(URL, json=payload, headers={'Content-Type': 'application/json'}, verify=False, timeout=120)
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            print("¡ÉXITO! El servidor respondió correctamente.")
            print("Respuesta (primeros 500 chars):")
            print(response.text[:500])
        elif response.status_code == 500:
            print("--- ERROR 500 DETECTADO ---")
            print("Esto indica un error interno en Django.")
            print("Contenido de la respuesta (HTML parcial):")
            # Intentar buscar traceback en el HTML si DEBUG=True
            text = response.text
            if "Traceback" in text:
                start = text.find("Traceback")
                print(text[start:start+2000])
            else:
                print(text[:2000])
        else:
            print(f"Error {response.status_code}:")
            print(response.text[:1000])
            
    except requests.exceptions.ConnectionError:
        print(f"Error de conexión: No se pudo contactar a {URL}")
    except requests.exceptions.Timeout:
        print("Error: Tiempo de espera agotado (Timeout).")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()
