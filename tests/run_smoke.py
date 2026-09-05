import sys
sys.path.insert(0, r'c:\Users\rsimo\OneDrive\Desktop\Render Heber\Cosas\Github\EMUPP')
import pandas as pd
from core.cleaner import procesar_dataframe

# Crear DataFrame de ejemplo
df = pd.DataFrame([
    {"nombres": "Ana Pérez", "mesa": "Mesa 7", "dni": ""},
    {"nombres": "Luis", "mesa": "Living 7", "dni": ""},
    {"nombres": "", "mesa": "", "dni": ""},
])

print('input:')
print(df)

res = procesar_dataframe(df, columna_nombres='nombres', columna_mesa='mesa')
print('\nprocessed:')
print(res)
