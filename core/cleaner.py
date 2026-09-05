"""
core/cleaner.py
================
Módulo de limpieza, normalización y heurísticas de nombres en español.

Responsabilidades:
- Normalizar espacios y caracteres extraños.
- Separar nombre y apellido con heurísticas para texto sin coma y con coma.
- Aplicar Smart Title Case respetando partículas patronímicas.
- Reportar nivel de confianza (es_dudoso) y motivo.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

#: Partículas patronímicas que NO llevan mayúscula inicial cuando van en posición
#: intermedia de un nombre compuesto.
PARTICULAS: frozenset[str] = frozenset(
    {
        "de",
        "del",
        "der",
        "de la",
        "de las",
        "de los",
        "san",
        "santa",
        "van",
        "von",
        "y",
        "e",
        "i",
        "mac",
        "mc",
        "ibn",
        "bin",
        "binti",
    }
)

#: Variantes compuestas de partículas ordenadas de mayor a menor longitud para
#: que el algoritmo las detecte antes de las simples (ej: "de la" antes que "de").
PARTICULAS_COMPUESTAS: list[str] = sorted(
    (p for p in PARTICULAS if " " in p),
    key=len,
    reverse=True,
)

# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------


def normalizar_espacios(texto: str) -> str:
    """
    Limpia dobles espacios, tabulaciones y espacios de bordes.

    Parameters
    ----------
    texto:
        Cadena de texto cruda.

    Returns
    -------
    str
        Cadena sin espacios redundantes ni caracteres de control invisibles.
    """
    if not isinstance(texto, str):
        texto = str(texto) if texto is not None else ""
    # Reemplazar tabs y retornos por espacio
    texto = texto.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    # Colapsar múltiples espacios en uno
    texto = re.sub(r" {2,}", " ", texto)
    return texto.strip()


def _smart_title(palabra: str) -> str:
    """
    Capitaliza una palabra, respetando caracteres acentuados.

    Parameters
    ----------
    palabra:
        Token individual.

    Returns
    -------
    str
        Palabra con primera letra en mayúscula y el resto en minúscula.
    """
    if not palabra:
        return palabra
    return palabra[0].upper() + palabra[1:].lower()


def aplicar_smart_title_case(segmento: str) -> str:
    """
    Aplica Title Case inteligente a un segmento (nombre o apellido).

    Reglas:
    - La primera palabra siempre lleva mayúscula, sin importar si es partícula.
    - Las partículas en posición NO inicial permanecen en minúscula.
    - Las demás palabras llevan mayúscula inicial.

    Parameters
    ----------
    segmento:
        Cadena que puede contener varias palabras.

    Returns
    -------
    str
        Segmento con capitales aplicadas correctamente.
    """
    if not segmento:
        return segmento

    # Tokenizar respetando partículas compuestas primero
    tokens = _tokenizar_con_particulas(segmento)
    resultado: list[str] = []

    for i, token in enumerate(tokens):
        token_lower = token.lower()
        if i == 0:
            # Primera posición: siempre mayúscula
            resultado.append(_smart_title(token))
        elif token_lower in PARTICULAS:
            resultado.append(token_lower)
        else:
            resultado.append(_smart_title(token))

    return " ".join(resultado)


# ---------------------------------------------------------------------------
# Tokenización con partículas
# ---------------------------------------------------------------------------


def _tokenizar_con_particulas(texto: str) -> list[str]:
    """
    Tokeniza el texto agrupando partículas compuestas como un solo token.

    Por ejemplo: "María de la Cruz" → ["María", "de la", "Cruz"]

    Parameters
    ----------
    texto:
        Texto a tokenizar.

    Returns
    -------
    list[str]
        Lista de tokens donde las partículas compuestas aparecen unidas.
    """
    texto = normalizar_espacios(texto)
    palabras = texto.split(" ")
    tokens: list[str] = []
    i = 0

    while i < len(palabras):
        # Intentar emparejar partículas compuestas (de la, de los, etc.)
        emparejado = False
        for particula in PARTICULAS_COMPUESTAS:
            partes = particula.split(" ")
            longitud = len(partes)
            if i + longitud <= len(palabras):
                candidato = " ".join(palabras[i : i + longitud]).lower()
                if candidato == particula:
                    tokens.append(particula)
                    i += longitud
                    emparejado = True
                    break
        if not emparejado:
            tokens.append(palabras[i])
            i += 1

    return tokens


# ---------------------------------------------------------------------------
# Lógica principal de procesamiento
# ---------------------------------------------------------------------------


def procesar_nombre(texto_crudo: str) -> dict[str, object]:
    """
    Analiza y normaliza un nombre completo en formato libre.

    Soporta:
    - Formato ``"Apellido, Nombre"`` (con coma → separación directa).
    - Formato libre ``"Juan de la Cruz Pérez"`` → heurísticas por cantidad de tokens.

    Heurísticas sin coma
    --------------------
    - **2 tokens**: [Nombre, Apellido]
    - **3 tokens**: [Nombre, Apellido1 Apellido2] — marcado como dudoso
    - **4+ tokens**: se parte por la mitad → [Nombres, Apellidos] — marcado como dudoso

    Parameters
    ----------
    texto_crudo:
        Cadena de entrada tal como viene del Excel/CSV.

    Returns
    -------
    dict
        Diccionario con claves:
        - ``nombre`` (str): Nombre(s) procesado(s).
        - ``apellido`` (str): Apellido(s) procesado(s).
        - ``orden_alfabetico`` (str): ``"Apellido, Nombre"`` normalizado para ordenar.
        - ``es_dudoso`` (bool): True si la heurística tiene baja confianza.
        - ``motivo`` (str): Descripción del método de separación usado.
    """
    texto = normalizar_espacios(texto_crudo)

    if not texto:
        return {
            "nombre": "",
            "apellido": "",
            "orden_alfabetico": "",
            "es_dudoso": True,
            "motivo": "Entrada vacía",
        }

    # ── Caso 1: Formato "Apellido, Nombre" ──────────────────────────────────
    if "," in texto:
        partes = texto.split(",", maxsplit=1)
        apellido_raw = partes[0].strip()
        nombre_raw = partes[1].strip() if len(partes) > 1 else ""

        nombre = aplicar_smart_title_case(nombre_raw)
        apellido = aplicar_smart_title_case(apellido_raw)

        return {
            "nombre": nombre,
            "apellido": apellido,
            "orden_alfabetico": f"{apellido}, {nombre}",
            "es_dudoso": False,
            "motivo": "Separación por coma (Apellido, Nombre)",
        }

    # ── Caso 2: Texto libre ──────────────────────────────────────────────────
    tokens = _tokenizar_con_particulas(texto)
    n = len(tokens)

    if n == 1:
        # Solo un token: no se puede distinguir nombre de apellido
        palabra = aplicar_smart_title_case(tokens[0])
        return {
            "nombre": palabra,
            "apellido": "",
            "orden_alfabetico": palabra,
            "es_dudoso": True,
            "motivo": "Un solo token: no se puede distinguir nombre de apellido",
        }

    if n == 2:
        # Dos tokens: [Nombre, Apellido] — regla simple
        nombre = aplicar_smart_title_case(tokens[0])
        apellido = aplicar_smart_title_case(tokens[1])
        return {
            "nombre": nombre,
            "apellido": apellido,
            "orden_alfabetico": f"{apellido}, {nombre}",
            "es_dudoso": False,
            "motivo": "2 tokens: [Nombre, Apellido]",
        }

    if n == 3:
        # Tres tokens: [Nombre, Apellido1 Apellido2]
        nombre = aplicar_smart_title_case(tokens[0])
        apellido = aplicar_smart_title_case(tokens[1]) + " " + aplicar_smart_title_case(tokens[2])
        apellido = apellido.strip()
        return {
            "nombre": nombre,
            "apellido": apellido,
            "orden_alfabetico": f"{apellido}, {nombre}",
            "es_dudoso": True,
            "motivo": "3 tokens: asumido [Nombre, Ap1 Ap2] — revisar si es [N1 N2, Ap]",
        }

    # n >= 4: partir por la mitad
    mitad = n // 2
    nombre = " ".join(aplicar_smart_title_case(t) for t in tokens[:mitad])
    apellido = " ".join(aplicar_smart_title_case(t) for t in tokens[mitad:])

    return {
        "nombre": nombre,
        "apellido": apellido,
        "orden_alfabetico": f"{apellido}, {nombre}",
        "es_dudoso": True,
        "motivo": f"{n} tokens: partido por la mitad — revisar manualmente",
    }


def _normalizar_mesa(texto: str) -> str:
    """Normaliza el valor de la mesa:

    - Elimina un prefijo tipo "mesa" (case-insensitive) si existe.
    - Si el valor resultante es numérico, lo devuelve tal cual (ej: "7").
    - En caso contrario aplica `aplicar_smart_title_case` para formato legible.
    """
    if not texto:
        return ""
    t = str(texto).strip()
    # Quitar prefijos como "mesa", "Mesa:", "mesa -", etc.
    t = re.sub(r'^(mesa[:\.\-\s]+)', '', t, flags=re.IGNORECASE).strip()
    if re.fullmatch(r"\d+", t):
        return t
    return aplicar_smart_title_case(t)


# ---------------------------------------------------------------------------
# Procesamiento de DataFrame completo
# ---------------------------------------------------------------------------


def procesar_dataframe(
    df: pd.DataFrame,
    columna_nombres: Optional[str] = None,
    columna_mesa: Optional[str] = None,
    columna_acompanantes: Optional[str] = None,
    columna_menu: Optional[str] = None,
    columna_apellido: Optional[str] = None,
    columna_dni: Optional[str] = None,
) -> pd.DataFrame:
    """
    Aplica normalización a cada fila de un DataFrame y devuelve uno nuevo
    con columnas normalizadas.

    Soporta dos modos de entrada:

    **Modo nombre completo** (``columna_nombres`` definida, ``columna_apellido`` = None):
        Aplica ``procesar_nombre`` con heurísticas de separación.

    **Modo columnas separadas** (``columna_nombres`` = nombre, ``columna_apellido`` = apellido):
        Omite las heurísticas. Solo aplica Smart Title Case a cada columna.
        Nunca marca filas como dudosas salvo que ambas columnas estén vacías.

    Parameters
    ----------
    df:
        DataFrame original.
    columna_nombres:
        Columna con nombre completo (modo heurístico) o solo el nombre (modo separado).
    columna_mesa:
        Columna de mesa (opcional).
    columna_acompanantes:
        Columna de acompañantes (opcional).
    columna_menu:
        Columna de menú/dieta (opcional).
    columna_apellido:
        Columna de apellido separada (opcional). Si se indica, activa el modo separado.

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas: ``nombre``, ``apellido``, ``orden_alfabetico``,
        ``es_dudoso``, ``motivo`` y las columnas opcionales preservadas.
    """
    # Manejar caso df es None
    if df is None:
        columnas_plantilla = [
            "nombre",
            "apellido",
            "orden_alfabetico",
            "mesa",
            "acompanantes",
            "menu",
            "dni",
            "es_dudoso",
            "motivo",
        ]
        return pd.DataFrame(columns=columnas_plantilla)

    resultados: list[dict[str, object]] = []
    modo_separado = columna_apellido is not None and columna_apellido in df.columns

    # ── Eliminar filas completamente vacías (cuando todas las columnas mapeadas están vacías)
    columnas_a_check = [
        c
        for c in (
            columna_nombres,
            columna_apellido,
            columna_mesa,
            columna_acompanantes,
            columna_menu,
            columna_dni,
        )
        if c and c in df.columns
    ]
    if columnas_a_check:
        subset = df[columnas_a_check].fillna("").astype(str)
        # strip each value and compare to empty string in a column-wise manner
        mask_todas_vacias = subset.apply(lambda col: col.str.strip() == "").all(axis=1)
        if mask_todas_vacias.any():
            df = df.loc[~mask_todas_vacias].reset_index(drop=True)

    for _, fila in df.iterrows():

        if modo_separado:
            # ── Modo columnas separadas: solo normalizar casing ──────────────
            nombre_raw = str(fila.get(columna_nombres, "") or "").strip() if columna_nombres else ""
            apellido_raw = str(fila.get(columna_apellido, "") or "").strip()  # type: ignore[index]

            nombre = aplicar_smart_title_case(normalizar_espacios(nombre_raw))
            apellido = aplicar_smart_title_case(normalizar_espacios(apellido_raw))

            vacio = not nombre and not apellido
            orden = f"{apellido}, {nombre}".strip(", ") if (apellido or nombre) else ""

            resultado: dict[str, object] = {
                "nombre": nombre,
                "apellido": apellido,
                "orden_alfabetico": orden,
                "es_dudoso": vacio,
                "motivo": "Columnas separadas — normalización directa" if not vacio
                          else "Columnas separadas — nombre y apellido vacíos",
            }
        else:
            # ── Modo nombre completo: heurísticas ────────────────────────────
            texto_crudo = str(fila.get(columna_nombres, "") or "") if columna_nombres else ""
            resultado = procesar_nombre(texto_crudo)

        # Preservar columnas opcionales
        mesa_str = (
            str(fila[columna_mesa]).strip()
            if columna_mesa and columna_mesa in df.columns
            else ""
        )
        resultado["mesa"] = _normalizar_mesa(mesa_str) if mesa_str else ""
        resultado["acompanantes"] = (
            str(fila[columna_acompanantes]).strip()
            if columna_acompanantes and columna_acompanantes in df.columns
            else ""
        )
        resultado["menu"] = (
            str(fila[columna_menu]).strip()
            if columna_menu and columna_menu in df.columns
            else ""
        )

        resultado["dni"] = (
            str(fila[columna_dni]).strip()
            if columna_dni and columna_dni in df.columns
            else ""
        )

        resultados.append(resultado)

    df_resultado = pd.DataFrame(resultados)

    columnas_ordenadas = [
        "nombre",
        "apellido",
        "orden_alfabetico",
        "mesa",
        "acompanantes",
        "menu",
        "dni",
        "es_dudoso",
        "motivo",
    ]
    columnas_finales = [c for c in columnas_ordenadas if c in df_resultado.columns]
    return df_resultado[columnas_finales]
