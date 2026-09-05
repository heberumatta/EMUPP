import re
from typing import Any

mesas = ["mesa 1", "Living 1", "Mesa 10", "Living 2", "1", "10", "Sin Mesa", 2]

def _clave_nombre(texto: str) -> list[Any]:
    t = str(texto).lower().strip()
    if "mesa" in t:
        pref = 0
    elif "living" in t:
        pref = 1
    else:
        pref = 2
    partes = re.split(r'(\d+)', t)
    return [pref] + [int(p) if p.isdigit() else p for p in partes]

def _clave_numero(texto: str) -> list[Any]:
    t = str(texto).lower().strip()
    numeros = re.findall(r'\d+', t)
    num = int(numeros[0]) if numeros else float('inf')
    return [num, t]

try:
    print("Orden nombre:")
    for k in sorted(mesas, key=_clave_nombre):
        print(k)
except Exception as e:
    print(f"Error _clave_nombre: {type(e).__name__}: {e}")

try:
    print("\nOrden numero:")
    for k in sorted(mesas, key=_clave_numero):
        print(k)
except Exception as e:
    print(f"Error _clave_numero: {type(e).__name__}: {e}")

