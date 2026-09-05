"""
core/pdf_engine.py
==================
Motor de generación de PDF editorial usando Jinja2 y WeasyPrint.

Flujo:
1. Recibe una lista de diccionarios de invitados ya procesados y metadatos del evento.
2. Agrupa los datos según el modo ("alfabetico" o "mesas").
3. Renderiza el HTML con Jinja2 inyectando los estilos CSS embebidos.
4. Compila a binario PDF en memoria con WeasyPrint (sin archivos temporales).
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import jinja2
# Importación de WeasyPrint diferida dentro de `generar_pdf` porque
# WeasyPrint requiere bibliotecas del sistema (pango/cairo) que pueden
# no estar presentes en entornos de CI/local sin instalación previa.
# from weasyprint import HTML, CSS

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


# ---------------------------------------------------------------------------
# Funciones auxiliares de agrupación
# ---------------------------------------------------------------------------


def _agrupar_alfabetico(invitados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Agrupa y ordena invitados por letra inicial del apellido.

    Parameters
    ----------
    invitados:
        Lista de dicts con al menos ``apellido`` y ``nombre``.

    Returns
    -------
    list[dict]
        Lista de grupos: ``{"letra": str, "invitados": list[dict]}``.
    """
    # Ordenar por campo orden_alfabetico (apellido, nombre)
    ordenados = sorted(
        invitados,
        key=lambda x: x.get("orden_alfabetico", "").upper(),
    )

    grupos: list[dict[str, Any]] = []
    letra_actual: str = ""

    for inv in ordenados:
        apellido = inv.get("apellido", "") or inv.get("nombre", "")
        # Obtener primera letra significativa (ignorar artículos iniciales)
        primera_letra = apellido[0].upper() if apellido else "#"

        if primera_letra != letra_actual:
            letra_actual = primera_letra
            grupos.append({"letra": letra_actual, "invitados": []})

        grupos[-1]["invitados"].append(inv)

    return grupos


def _agrupar_por_mesa(invitados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Agrupa invitados por número/nombre de mesa, ordenados internamente por apellido.

    Parameters
    ----------
    invitados:
        Lista de dicts con al menos ``mesa``.

    Returns
    -------
    list[dict]
        Lista de grupos: ``{"mesa": str, "invitados": list[dict]}``.
    """
    import re

    mesas: dict[str, list[dict[str, Any]]] = {}

    for inv in invitados:
        mesa = inv.get("mesa", "Sin Mesa") or "Sin Mesa"
        if mesa not in mesas:
            mesas[mesa] = []
        mesas[mesa].append(inv)

    def _clave_natural(texto: str) -> list[Any]:
        """
        Clave de ordenamiento natural (human sort).
        Divide la cadena en fragmentos alfabéticos y numéricos,
        convirtiendo los numéricos a int para comparación correcta.
        Ejemplos: "mesa 2" < "mesa 10", "living 1" < "living 10".
        """
        partes = re.split(r'(\d+)', texto.lower().strip())
        return [int(p) if p.isdigit() else p for p in partes]

    grupos: list[dict[str, Any]] = []
    for mesa in sorted(mesas.keys(), key=_clave_natural):
        invitados_mesa = sorted(
            mesas[mesa],
            key=lambda x: x.get("orden_alfabetico", "").upper(),
        )
        # Determinar si la clave de mesa representa un número puro
        mesa_is_number = bool(re.fullmatch(r"\d+", str(mesa).strip()))
        grupos.append({"mesa": mesa, "invitados": invitados_mesa, "mesa_is_number": mesa_is_number})

    return grupos


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def generar_pdf(
    datos_invitados: list[dict[str, Any]],
    metadata_evento: dict[str, str],
    modo: str = "alfabetico",
    salto_pagina_mesas: bool = True,
) -> bytes:
    """
    Genera un PDF de imprenta en memoria a partir de los datos de invitados.

    Parameters
    ----------
    datos_invitados:
        Lista de diccionarios con los campos del invitado ya normalizados.
        Campos esperados: ``nombre``, ``apellido``, ``orden_alfabetico``,
        ``mesa`` (opcional), ``acompanantes`` (opcional), ``menu`` (opcional).
    metadata_evento:
        Diccionario con metadatos del evento:
        ``{"nombre_evento": str, "fecha": str, "lugar": str}``.
    modo:
        ``"alfabetico"`` para listado A-Z en 2 columnas, o
        ``"mesas"`` para listado por mesa con salto de página entre mesas.
    salto_pagina_mesas:
        Si es True (defecto), inserta un salto de página entre cada mesa
        en modo ``"mesas"``. Si es False, las mesas se listan de forma continua.

    Returns
    -------
    bytes
        Contenido binario del PDF generado, listo para descarga o impresión.

    Raises
    ------
    ValueError
        Si ``modo`` no es ``"alfabetico"`` ni ``"mesas"``.
    FileNotFoundError
        Si no se encuentran los templates de Jinja2.
    """
    if modo not in ("alfabetico", "mesas"):
        raise ValueError(f"Modo inválido: '{modo}'. Use 'alfabetico' o 'mesas'.")

    # ── Cargar entorno Jinja2 ────────────────────────────────────────────────
    if not _TEMPLATES_DIR.exists():
        raise FileNotFoundError(
            f"Directorio de templates no encontrado: {_TEMPLATES_DIR}"
        )

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )

    template = env.get_template("printable.html")

    # ── Agrupar datos ────────────────────────────────────────────────────────
    # Normalizar/y añadir banderas útiles para la plantilla
    import re as _re
    for inv in datos_invitados:
        mesa_val = str(inv.get("mesa", "") or "").strip()
        inv["mesa"] = mesa_val
        inv["mesa_is_number"] = bool(_re.fullmatch(r"\d+", mesa_val))

    if modo == "alfabetico":
        grupos = _agrupar_alfabetico(datos_invitados)
    else:
        grupos = _agrupar_por_mesa(datos_invitados)

    # ── Leer CSS embebido ────────────────────────────────────────────────────
    css_path = _TEMPLATES_DIR / "styles.css"
    css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    # ── Renderizar HTML ──────────────────────────────────────────────────────
    total_invitados = len(datos_invitados)
    html_content = template.render(
        evento=metadata_evento,
        grupos=grupos,
        modo=modo,
        salto_pagina_mesas=salto_pagina_mesas,
        total_invitados=total_invitados,
        css_content=css_content,
    )

    # ── Compilar a PDF con WeasyPrint en memoria ─────────────────────────────
    # Importar WeasyPrint solo cuando sea necesario (runtime). Si falta,
    # lanzamos un error informativo en vez de romper la importación del módulo.
    try:
        from weasyprint import HTML, CSS
    except Exception as e:  # pragma: no cover - entorno local puede no tener deps
        raise RuntimeError(
            "WeasyPrint no está disponible: instala las dependencias del sistema "
            "requeridas (pango/cairo) y la librería Python 'weasyprint'. "
            f"Detalle: {e}"
        )

    pdf_buffer = io.BytesIO()
    HTML(string=html_content, base_url=str(_TEMPLATES_DIR)).write_pdf(
        pdf_buffer,
        stylesheets=[CSS(string=css_content)],
    )
    pdf_buffer.seek(0)
    return pdf_buffer.read()
