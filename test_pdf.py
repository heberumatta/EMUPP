import sys
from core.pdf_engine import generar_pdf

datos = [{"nombre": "Juan", "apellido": "Perez", "mesa": "Mesa 1", "es_dudoso": False, "orden_alfabetico": "Perez, Juan"}]
meta = {"nombre_evento": "Test", "fecha": "hoy", "lugar": "aqui"}

try:
    print("Probando alfabetico...")
    pdf = generar_pdf(datos, meta, modo="alfabetico")
    print("Alfabetico OK")
except Exception as e:
    print(f"Error alfabetico: {type(e).__name__}: {e}")

try:
    print("Probando mesas (nombre)...")
    pdf = generar_pdf(datos, meta, modo="mesas", orden_mesas="nombre")
    print("Mesas (nombre) OK")
except Exception as e:
    print(f"Error mesas (nombre): {type(e).__name__}: {e}")
    
try:
    print("Probando mesas (numero)...")
    pdf = generar_pdf(datos, meta, modo="mesas", orden_mesas="numero")
    print("Mesas (numero) OK")
except Exception as e:
    print(f"Error mesas (numero): {type(e).__name__}: {e}")
