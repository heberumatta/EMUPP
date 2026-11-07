"""
tests/test_pdf_engine.py
========================
Pruebas unitarias completas para core/pdf_engine.py.

Cubre:
- Normalización de diacríticos y preservación de Ñ.
- Clave de ordenación alfabética según reglas de español.
- Agrupación por letra y por mesa.
- Generación de PDF con WeasyPrint en memoria.
- Selección dinámica de columnas (1, 2, 3, 4).
- Modo con y sin portada (ahorro de hojas).
- Búsqueda de texto y flujo continuo de columnas (sin descarte de espacio).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Permitir importar módulos de core desde la raíz
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.pdf_engine import (
    _agrupar_alfabetico,
    _agrupar_por_mesa,
    _clave_alfabetica,
    _obtener_letra_grupo,
    _remover_diacriticos,
    generar_pdf,
)


# ===========================================================================
# Tests: Utilidades lingüísticas para español
# ===========================================================================


class TestUtilidadesEspanol:
    def test_remover_diacriticos_preserva_enie(self) -> None:
        assert _remover_diacriticos("Álvarez") == "Alvarez"
        assert _remover_diacriticos("Martínez") == "Martinez"
        assert _remover_diacriticos("Íñigo") == "Iñigo"
        assert _remover_diacriticos("Ñáñez") == "Ñañez"
        assert _remover_diacriticos("Úbeda") == "Ubeda"
        assert _remover_diacriticos("Güell") == "Guell"

    def test_obtener_letra_grupo(self) -> None:
        assert _obtener_letra_grupo({"apellido": "Álvarez"}) == "A"
        assert _obtener_letra_grupo({"apellido": "Écija"}) == "E"
        assert _obtener_letra_grupo({"apellido": "Íñigo"}) == "I"
        assert _obtener_letra_grupo({"apellido": "Óbando"}) == "O"
        assert _obtener_letra_grupo({"apellido": "Úbeda"}) == "U"
        assert _obtener_letra_grupo({"apellido": "Ñáñez"}) == "Ñ"
        assert _obtener_letra_grupo({"apellido": "Pérez"}) == "P"
        assert _obtener_letra_grupo({"apellido": ""}) == "#"
        assert _obtener_letra_grupo({"nombre": "SoloNombre"}) == "S"

    def test_clave_alfabetica_orden_espanol(self) -> None:
        invitados = [
            {"apellido": "Zapata", "orden_alfabetico": "Zapata, Zoe"},
            {"apellido": "Álvarez", "orden_alfabetico": "Álvarez, Carlos"},
            {"apellido": "Alonso", "orden_alfabetico": "Alonso, Ana"},
            {"apellido": "Benítez", "orden_alfabetico": "Benítez, Beatriz"},
            {"apellido": "Navarro", "orden_alfabetico": "Navarro, Pedro"},
            {"apellido": "Núñez", "orden_alfabetico": "Núñez, Ramón"},
            {"apellido": "Ñáñez", "orden_alfabetico": "Ñáñez, Ñoño"},
            {"apellido": "Olmedo", "orden_alfabetico": "Olmedo, Luis"},
        ]

        ordenados = sorted(invitados, key=_clave_alfabetica)
        apellidos_ordenados = [x["apellido"] for x in ordenados]

        # En español: Alonso < Álvarez < Benítez < Navarro < Núñez < Ñáñez < Olmedo < Zapata
        assert apellidos_ordenados == [
            "Alonso",
            "Álvarez",
            "Benítez",
            "Navarro",
            "Núñez",
            "Ñáñez",
            "Olmedo",
            "Zapata",
        ]


# ===========================================================================
# Tests: Agrupación
# ===========================================================================


class TestAgrupacion:
    def test_agrupar_alfabetico_unifica_acentos(self) -> None:
        invitados = [
            {"apellido": "Álvarez", "nombre": "Carlos", "orden_alfabetico": "Álvarez, Carlos"},
            {"apellido": "Alonso", "nombre": "Ana", "orden_alfabetico": "Alonso, Ana"},
            {"apellido": "Benítez", "nombre": "Beatriz", "orden_alfabetico": "Benítez, Beatriz"},
        ]
        grupos = _agrupar_alfabetico(invitados)
        assert len(grupos) == 2
        assert grupos[0]["letra"] == "A"
        assert len(grupos[0]["invitados"]) == 2
        assert grupos[0]["invitados"][0]["apellido"] == "Alonso"
        assert grupos[0]["invitados"][1]["apellido"] == "Álvarez"
        assert grupos[1]["letra"] == "B"

    def test_agrupar_por_mesa_orden_nombre(self) -> None:
        invitados = [
            {"apellido": "Gómez", "mesa": "Mesa 10"},
            {"apellido": "Pérez", "mesa": "Mesa 2"},
            {"apellido": "Díaz", "mesa": "Living 1"},
            {"apellido": "López", "mesa": "Sin Mesa"},
        ]
        grupos = _agrupar_por_mesa(invitados, orden_mesas="nombre")
        mesas = [g["mesa"] for g in grupos]
        assert mesas == ["Mesa 2", "Mesa 10", "Living 1", "Sin Mesa"]

    def test_agrupar_por_mesa_orden_numero(self) -> None:
        invitados = [
            {"apellido": "Gómez", "mesa": "10"},
            {"apellido": "Pérez", "mesa": "2"},
            {"apellido": "Díaz", "mesa": "1"},
        ]
        grupos = _agrupar_por_mesa(invitados, orden_mesas="numero")
        mesas = [g["mesa"] for g in grupos]
        assert mesas == ["1", "2", "10"]


# ===========================================================================
# Tests: Generación de PDF y Opciones
# ===========================================================================


class TestGenerarPDF:
    @pytest.fixture
    def datos_muestra(self) -> list[dict]:
        return [
            {
                "nombre": "Ana",
                "apellido": "García",
                "orden_alfabetico": "García, Ana",
                "mesa": "Mesa 1",
                "menu": "Celíaco",
                "acompanantes": "1",
                "es_dudoso": False,
            },
            {
                "nombre": "Carlos",
                "apellido": "Álvarez",
                "orden_alfabetico": "Álvarez, Carlos",
                "mesa": "Mesa 2",
                "menu": "",
                "acompanantes": "0",
                "es_dudoso": False,
            },
        ]

    @pytest.fixture
    def metadata_evento(self) -> dict[str, str]:
        return {
            "nombre_evento": "Gala de Prueba",
            "fecha": "15 de Diciembre 2026",
            "lugar": "Palacio Real",
        }

    def test_modo_invalido_lanza_error(self, datos_muestra, metadata_evento) -> None:
        with pytest.raises(ValueError, match="Modo inválido"):
            generar_pdf(datos_muestra, metadata_evento, modo="invalido")

    def test_generar_pdf_alfabetico_columnas(self, datos_muestra, metadata_evento) -> None:
        for cols in [1, 2, 3, 4]:
            pdf_bytes = generar_pdf(
                datos_muestra,
                metadata_evento,
                modo="alfabetico",
                columnas=cols,
                incluir_portada=True,
            )
            assert isinstance(pdf_bytes, bytes)
            assert len(pdf_bytes) > 1000
            assert pdf_bytes.startswith(b"%PDF-")

    def test_generar_pdf_sin_portada(self, datos_muestra, metadata_evento) -> None:
        pdf_bytes = generar_pdf(
            datos_muestra,
            metadata_evento,
            modo="alfabetico",
            columnas=3,
            incluir_portada=False,
        )
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")

    def test_generar_pdf_modo_mesas(self, datos_muestra, metadata_evento) -> None:
        pdf_bytes = generar_pdf(
            datos_muestra,
            metadata_evento,
            modo="mesas",
            salto_pagina_mesas=False,
            columnas=3,
        )
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")


# ===========================================================================
# Tests: Búsqueda de Texto y Optimización de Columnas
# ===========================================================================


class TestOptimizacionPDF:
    def test_texto_es_buscable_en_pdf(self) -> None:
        datos = [
            {
                "nombre": "Mariana",
                "apellido": "Valenzuela",
                "orden_alfabetico": "Valenzuela, Mariana",
                "mesa": "Mesa 8",
                "menu": "Vegetariano",
                "es_dudoso": False,
            }
        ]
        meta = {
            "nombre_evento": "Boda Mariana y Roberto",
            "fecha": "18 de Mayo 2026",
            "lugar": "Hacienda del Valle",
        }
        pdf_bytes = generar_pdf(
            datos, meta, modo="alfabetico", columnas=3, incluir_portada=False
        )

        # Usar pdftotext si está disponible en el sistema
        try:
            res = subprocess.run(
                ["pdftotext", "-", "-"],
                input=pdf_bytes,
                capture_output=True,
                check=True,
            )
            texto_extraido = res.stdout.decode("utf-8")
            assert "Valenzuela" in texto_extraido
            assert "Mariana" in texto_extraido
            assert "Mesa 8" in texto_extraido
            assert "Vegetariano" in texto_extraido
            assert "Boda Mariana y Roberto" in texto_extraido
        except FileNotFoundError:
            pytest.skip("pdftotext no disponible en entorno de pruebas")

    def test_menu_nan_no_aparece_en_pdf(self) -> None:
        import numpy as np
        datos = [
            {
                "nombre": "Pedro",
                "apellido": "Alonso",
                "orden_alfabetico": "Alonso, Pedro",
                "mesa": "Mesa 1",
                "menu": "nan",
                "es_dudoso": False,
            },
            {
                "nombre": "Lucía",
                "apellido": "Gómez",
                "orden_alfabetico": "Gómez, Lucía",
                "mesa": "Mesa 2",
                "menu": np.nan,
                "es_dudoso": False,
            },
        ]
        meta = {
            "nombre_evento": "Evento Prueba Limpieza",
            "fecha": "2026",
            "lugar": "Madrid",
        }
        pdf_bytes = generar_pdf(
            datos, meta, modo="alfabetico", columnas=3, incluir_portada=False
        )

        try:
            res = subprocess.run(
                ["pdftotext", "-", "-"],
                input=pdf_bytes,
                capture_output=True,
                check=True,
            )
            texto_extraido = res.stdout.decode("utf-8")
            palabras = [w.strip().lower() for w in texto_extraido.split()]
            assert "nan" not in palabras
            assert "none" not in palabras
        except FileNotFoundError:
            pytest.skip("pdftotext no disponible en entorno de pruebas")
            pytest.skip("pdftotext no disponible en entorno de pruebas")

    def test_flujo_continuo_letras_aprovecha_columnas(self) -> None:
        # Generar lista con letra A larga (40 invitados) y letra B (15 invitados)
        datos = []
        for i in range(1, 41):
            datos.append(
                {
                    "nombre": f"NombreA{i}",
                    "apellido": f"Alvarez{i}",
                    "orden_alfabetico": f"Alvarez{i}, NombreA{i}",
                    "mesa": "1",
                    "es_dudoso": False,
                }
            )
        for i in range(1, 16):
            datos.append(
                {
                    "nombre": f"NombreB{i}",
                    "apellido": f"Benitez{i}",
                    "orden_alfabetico": f"Benitez{i}, NombreB{i}",
                    "mesa": "2",
                    "es_dudoso": False,
                }
            )

        meta = {"nombre_evento": "Evento Denso", "fecha": "2026", "lugar": "Centro"}
        pdf_bytes = generar_pdf(
            datos, meta, modo="alfabetico", columnas=3, incluir_portada=False
        )
        assert len(pdf_bytes) > 0

        try:
            res = subprocess.run(
                ["pdftotext", "-", "-"],
                input=pdf_bytes,
                capture_output=True,
                check=True,
            )
            paginas = res.stdout.decode("utf-8").split("\x0c")
            paginas_con_contenido = [p for p in paginas if p.strip()]
            # En 3 columnas sin portada, 55 invitados caben holgadamente en 1 sola hoja
            assert len(paginas_con_contenido) == 1
        except FileNotFoundError:
            pytest.skip("pdftotext no disponible en entorno de pruebas")

    def test_no_encabezado_letra_huerfano(self) -> None:
        """
        Verifica que el título de una letra no quede huérfano al pie de una columna
        separado de su primer invitado en la siguiente columna.
        """
        try:
            from weasyprint import HTML
        except Exception:
            pytest.skip("WeasyPrint no disponible")

        # 154 invitados con 'A' causaban que 'B' quedara al final de la columna 1
        # mientras el primer invitado de 'B' pasaba al tope de la columna 2.
        datos = [
            {
                "nombre": f"Nombre{i}",
                "apellido": f"Alvarez{i}",
                "mesa": "1",
                "es_dudoso": False,
            }
            for i in range(154)
        ]
        for i in range(5):
            datos.append(
                {
                    "nombre": f"Nombre{i}",
                    "apellido": f"Benitez{i}",
                    "mesa": "2",
                    "es_dudoso": False,
                }
            )

        meta = {"nombre_evento": "Evento Test Huérfano", "fecha": "2026", "lugar": "Centro"}
        pdf_bytes = generar_pdf(
            datos, meta, modo="alfabetico", columnas=3, incluir_portada=False
        )
        assert len(pdf_bytes) > 0

        # Renderizar árbol de cajas para verificar posición de 'B' y su primer invitado
        from core.pdf_engine import _TEMPLATES_DIR, _agrupar_alfabetico
        import jinja2

        env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)
        template = env.get_template("printable.html")
        css_content = (_TEMPLATES_DIR / "styles.css").read_text(encoding="utf-8")
        grupos = _agrupar_alfabetico(datos)
        html = template.render(
            evento=meta,
            grupos=grupos,
            modo="alfabetico",
            columnas=3,
            incluir_portada=False,
            css_content=css_content,
            total_invitados=len(datos),
        )
        doc = HTML(string=html, base_url=str(_TEMPLATES_DIR)).render()

        def _buscar_posiciones(box, objetivo):
            res = []
            txt = getattr(box, "text", "") or ""
            if txt.strip() == objetivo:
                res.append((getattr(box, "position_x", 0), getattr(box, "position_y", 0)))
            for c in getattr(box, "children", []):
                res.extend(_buscar_posiciones(c, objetivo))
            return res

        for page in doc.pages:
            pos_b = _buscar_posiciones(page._page_box, "B")
            pos_ben = _buscar_posiciones(page._page_box, "Benitez0")
            if pos_b and pos_ben:
                # Deben estar en la misma columna (misma coordenada X aproximadamente)
                assert abs(pos_b[0][0] - pos_ben[0][0]) < 10, "El título 'B' quedó en diferente columna a su primer invitado"
            elif pos_b and not pos_ben:
                pytest.fail("El título 'B' apareció en una página sin su primer invitado")
