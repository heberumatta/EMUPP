# core/__init__.py
"""
Módulo core del Event Guest Manager.
Expone los submódulos de limpieza y generación de PDF.
"""

from .cleaner import procesar_nombre, normalizar_espacios, procesar_dataframe
from .pdf_engine import generar_pdf

__all__ = [
    "procesar_nombre",
    "normalizar_espacios",
    "procesar_dataframe",
    "generar_pdf",
]
