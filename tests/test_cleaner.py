"""
tests/test_cleaner.py
=====================
Pruebas unitarias de core/cleaner.py.

Cubre:
- Normalización de espacios.
- Separación por coma.
- Heurísticas de 1, 2, 3 y 4+ tokens.
- Smart Title Case con partículas patronímicas.
- Casos borde: vacío, solo partículas, unicode acentuado.

Ejecutar con:
    python -m pytest tests/test_cleaner.py -v
"""

from __future__ import annotations

import sys
import os

# Permitir importar el módulo core desde la raíz del proyecto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from core.cleaner import (
    aplicar_smart_title_case,
    normalizar_espacios,
    procesar_nombre,
)


# ===========================================================================
# Tests: normalizar_espacios
# ===========================================================================


class TestNormalizarEspacios:
    def test_elimina_dobles_espacios(self) -> None:
        assert normalizar_espacios("Juan  Pablo") == "Juan Pablo"

    def test_elimina_tabs(self) -> None:
        assert normalizar_espacios("Juan\tPablo") == "Juan Pablo"

    def test_recorta_extremos(self) -> None:
        assert normalizar_espacios("  Juan Pablo  ") == "Juan Pablo"

    def test_multiples_espacios_mixtos(self) -> None:
        assert normalizar_espacios("  Juan   de   la   Cruz  ") == "Juan de la Cruz"

    def test_cadena_vacia(self) -> None:
        assert normalizar_espacios("") == ""

    def test_none_como_entrada(self) -> None:
        assert normalizar_espacios(None) == ""  # type: ignore[arg-type]

    def test_retorno_de_carro(self) -> None:
        assert normalizar_espacios("Juan\nPablo") == "Juan Pablo"


# ===========================================================================
# Tests: aplicar_smart_title_case
# ===========================================================================


class TestSmartTitleCase:
    def test_titulo_simple(self) -> None:
        assert aplicar_smart_title_case("juan") == "Juan"

    def test_particula_intermedia_minuscula(self) -> None:
        resultado = aplicar_smart_title_case("juan de la cruz")
        assert resultado == "Juan de la Cruz"

    def test_particula_del(self) -> None:
        resultado = aplicar_smart_title_case("juan del rio")
        assert resultado == "Juan del Rio"

    def test_particula_primera_posicion_mayuscula(self) -> None:
        # "de" en primera posición debe llevar mayúscula
        resultado = aplicar_smart_title_case("de la peña")
        assert resultado == "De la Peña"

    def test_todo_mayusculas(self) -> None:
        resultado = aplicar_smart_title_case("JUAN PÉREZ")
        assert resultado == "Juan Pérez"

    def test_todo_minusculas(self) -> None:
        resultado = aplicar_smart_title_case("juan pérez")
        assert resultado == "Juan Pérez"

    def test_van_von(self) -> None:
        resultado = aplicar_smart_title_case("maría van der berg")
        assert resultado == "María van der Berg"

    def test_cadena_vacia(self) -> None:
        assert aplicar_smart_title_case("") == ""


# ===========================================================================
# Tests: procesar_nombre — formato con coma
# ===========================================================================


class TestProcesarNombreConComa:
    def test_apellido_coma_nombre(self) -> None:
        r = procesar_nombre("Pérez, Juan")
        assert r["apellido"] == "Pérez"
        assert r["nombre"] == "Juan"
        assert r["es_dudoso"] is False

    def test_apellido_compuesto_con_coma(self) -> None:
        r = procesar_nombre("de la Cruz, María")
        assert r["apellido"] == "De la Cruz"
        assert r["nombre"] == "María"

    def test_mayusculas_crudas_con_coma(self) -> None:
        r = procesar_nombre("GARCIA LOPEZ, ANTONIO")
        assert r["apellido"] == "Garcia Lopez"
        assert r["nombre"] == "Antonio"
        assert r["es_dudoso"] is False

    def test_orden_alfabetico_con_coma(self) -> None:
        r = procesar_nombre("López, Carlos")
        assert r["orden_alfabetico"] == "López, Carlos"

    def test_coma_sin_nombre(self) -> None:
        r = procesar_nombre("Rodríguez,")
        assert r["apellido"] == "Rodríguez"
        assert r["nombre"] == ""


# ===========================================================================
# Tests: procesar_nombre — formato libre (sin coma)
# ===========================================================================


class TestProcesarNombreLibre:
    def test_un_token(self) -> None:
        r = procesar_nombre("Juanito")
        assert r["nombre"] == "Juanito"
        assert r["apellido"] == ""
        assert r["es_dudoso"] is True

    def test_dos_tokens(self) -> None:
        r = procesar_nombre("Juan García")
        assert r["nombre"] == "Juan"
        assert r["apellido"] == "García"
        assert r["es_dudoso"] is False

    def test_tres_tokens(self) -> None:
        r = procesar_nombre("Juan García López")
        assert r["nombre"] == "Juan"
        assert r["apellido"] == "García López"
        assert r["es_dudoso"] is True

    def test_cuatro_tokens(self) -> None:
        r = procesar_nombre("Juan Carlos García López")
        assert r["nombre"] == "Juan Carlos"
        assert r["apellido"] == "García López"
        assert r["es_dudoso"] is True

    def test_particula_en_apellido(self) -> None:
        r = procesar_nombre("María de la Cruz")
        # "de la" es una partícula compuesta → 2 tokens efectivos: ["María", "de la Cruz"]
        # Pero "Cruz" es token separado → 3 tokens efectivos: ["María", "de la", "Cruz"]
        # Resultado esperado: nombre=María, apellido=de la Cruz
        assert r["nombre"] == "María"
        assert "Cruz" in r["apellido"]

    def test_todo_en_minusculas(self) -> None:
        r = procesar_nombre("ana martínez torres")
        assert r["nombre"] == "Ana"
        assert r["apellido"] == "Martínez Torres"

    def test_todo_en_mayusculas(self) -> None:
        r = procesar_nombre("ANA MARTÍNEZ TORRES")
        assert r["nombre"] == "Ana"
        assert r["apellido"] == "Martínez Torres"

    def test_cadena_vacia(self) -> None:
        r = procesar_nombre("")
        assert r["es_dudoso"] is True
        assert r["nombre"] == ""

    def test_espacios_extras(self) -> None:
        r = procesar_nombre("  Juan   García  ")
        assert r["nombre"] == "Juan"
        assert r["apellido"] == "García"

    def test_cinco_tokens(self) -> None:
        r = procesar_nombre("José María García de la Fuente")
        assert r["es_dudoso"] is True
        assert r["nombre"] != ""
        assert r["apellido"] != ""


# ===========================================================================
# Tests: orden_alfabetico
# ===========================================================================


class TestOrdenAlfabetico:
    def test_formato_correcto_dos_tokens(self) -> None:
        r = procesar_nombre("María González")
        assert r["orden_alfabetico"] == "González, María"

    def test_formato_correcto_con_coma(self) -> None:
        r = procesar_nombre("Sánchez, Pedro")
        assert r["orden_alfabetico"] == "Sánchez, Pedro"
