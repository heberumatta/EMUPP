"""
app.py
======
Interfaz Streamlit completa para el Event Guest Manager.

Flujo de la aplicación:
1. El usuario carga un archivo Excel/CSV (o el dataset de prueba).
2. Selecciona la columna de nombres y columnas opcionales.
3. El sistema procesa y normaliza los nombres.
4. El operador revisa y edita inline los casos dudosos.
5. Exporta Excel limpio y/o PDF de imprenta.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# Ajustar path para importar core desde cualquier directorio
import sys

sys.path.insert(0, str(Path(__file__).parent))

from core.cleaner import procesar_dataframe
from core.pdf_engine import generar_pdf

# ===========================================================================
# Configuración de la página
# ===========================================================================

VERSION = "1.0.0"

st.set_page_config(
    page_title=f"Gestor de Invitados v{VERSION}",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===========================================================================
# CSS personalizado para Streamlit
# ===========================================================================

st.markdown(
    """
    <style>
    /* ── Ocultar UI de Streamlit (Header, Footer, Menú en inglés) ── */
    footer {visibility: hidden;}
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}

    /* ── Traducción del componente de subida de archivos ── */
    [data-testid="stFileUploadDropzone"] > div > div > span { display:none; }
    [data-testid="stFileUploadDropzone"] > div > div::before { 
        content: "Arrastra y suelta tu archivo aquí"; 
        font-weight: 500; 
        font-size: 14px;
        display: block;
        margin-bottom: 5px;
    }
    [data-testid="stFileUploadDropzone"] > div > div > small { display:none; }

    /* ── Fuentes ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Tarjetas de métricas ── */
    [data-testid="stMetric"] {
        background: var(--secondary-background-color);
        border: 1px solid var(--secondary-background-color);
        border-radius: 12px;
        padding: 1rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(201,168,76,0.15);
    }

    [data-testid="stMetricLabel"] { font-size: 0.78rem; }
    [data-testid="stMetricValue"] { color: #c9a84c !important; font-size: 2rem !important; font-weight: 700 !important; }
    [data-testid="stMetricDelta"] { font-size: 0.85rem; }

    /* ── Botones principales ── */
    .stButton > button {
        background: linear-gradient(135deg, #c9a84c, #e8c86d);
        color: #1a1a2e !important;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.4rem;
        transition: all 0.25s ease;
        box-shadow: 0 4px 12px rgba(201,168,76,0.3);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #e8c86d, #f0da8f);
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(201,168,76,0.45);
        color: #1a1a2e !important;
    }

    /* ── Download buttons ── */
    .stDownloadButton > button {
        background: transparent;
        color: #c9a84c;
        border: 1px solid rgba(201,168,76,0.4);
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.25s ease;
    }
    .stDownloadButton > button:hover {
        background: rgba(201,168,76,0.1);
        border-color: #c9a84c;
        transform: translateY(-1px);
        color: #c9a84c;
    }

    /* ── Badge de dudoso ── */
    .badge-dudoso {
        background: linear-gradient(135deg, #f0ad4e, #e8890e);
        color: white;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 20px;
        letter-spacing: 0.05em;
    }

    /* ── Sección de exportación ── */
    .export-section {
        background: var(--secondary-background-color);
        border: 1px solid rgba(201,168,76,0.2);
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 1rem;
    }

    /* ── Banner de alerta personalizado ── */
    .alerta-info {
        background: var(--secondary-background-color);
        border-left: 3px solid #c9a84c;
        border-radius: 0 8px 8px 0;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        font-size: 0.88rem;
        color: var(--text-color);
    }

    /* ── Título hero ── */
    .hero-title {
        font-size: 2.4rem;
        font-weight: 700;
        color: var(--text-color);
        margin-bottom: 0.25rem;
    }

    .hero-subtitle {
        color: var(--text-color);
        opacity: 0.7;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ===========================================================================
# Utilidades de exportación
# ===========================================================================


def generar_excel(df: pd.DataFrame) -> bytes:
    """
    Genera un archivo Excel formateado en memoria.

    Parameters
    ----------
    df:
        DataFrame procesado y posiblemente editado por el operador.

    Returns
    -------
    bytes
        Contenido binario del archivo .xlsx.
    """
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        # Eliminar columna de motivo del Excel final (solo para uso interno)
        df_export = df.copy()

        # Mapear columnas a nombres amigables
        renombrado = {
            "nombre": "Nombre",
            "apellido": "Apellido",
            "orden_alfabetico": "Orden Alfabético",
            "mesa": "Mesa",
            "acompanantes": "Acompañantes",
            "menu": "Menú",
            "dni": "DNI",
            "es_dudoso": "¿Revisar?",
            "motivo": "Nota",
        }
        df_export = df_export.rename(
            columns={k: v for k, v in renombrado.items() if k in df_export.columns}
        )
        df_export["¿Revisar?"] = df_export.get("¿Revisar?", pd.Series(False)).map(
            {True: "⚠️ Sí", False: "✓ OK"}
        )

        df_export.to_excel(writer, index=False, sheet_name="Invitados")

        workbook = writer.book
        worksheet = writer.sheets["Invitados"]

        # Formatos
        fmt_header = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#1a1a2e",
                "font_color": "#c9a84c",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "font_size": 10,
            }
        )
        fmt_ok = workbook.add_format(
            {"bg_color": "#f0fff4", "font_color": "#2d6a4f", "font_size": 9}
        )
        fmt_dudoso = workbook.add_format(
            {"bg_color": "#fff3cd", "font_color": "#856404", "font_size": 9, "bold": True}
        )
        fmt_normal = workbook.add_format({"font_size": 9, "valign": "vcenter"})
        fmt_alternado = workbook.add_format(
            {"font_size": 9, "valign": "vcenter", "bg_color": "#f9f9f6"}
        )

        # Encabezados
        for col_num, col_name in enumerate(df_export.columns):
            worksheet.write(0, col_num, col_name, fmt_header)

        # Filas
        revisar_col = df_export.columns.get_loc("¿Revisar?") if "¿Revisar?" in df_export.columns else -1

        for row_num, row_data in enumerate(df_export.itertuples(index=False), start=1):
            es_dudoso = False
            if revisar_col >= 0:
                es_dudoso = str(getattr(row_data, "_" + str(revisar_col), "")) == "⚠️ Sí"

            fmt_fila = fmt_dudoso if es_dudoso else (fmt_ok if row_num % 2 == 0 else fmt_alternado)

            for col_num, value in enumerate(row_data):
                worksheet.write(row_num, col_num, str(value) if value is not None else "", fmt_fila)

        # Anchos de columna
        anchos = {
            "Nombre": 20,
            "Apellido": 22,
            "Orden Alfabético": 28,
            "Mesa": 10,
            "Acompañantes": 13,
            "Menú": 14,
            "DNI": 14,
            "¿Revisar?": 10,
            "Nota": 40,
        }
        for col_num, col_name in enumerate(df_export.columns):
            ancho = anchos.get(col_name, 15)
            worksheet.set_column(col_num, col_num, ancho)

        # Fila de encabezado con altura
        worksheet.set_row(0, 22)

        # Filtros automáticos
        worksheet.autofilter(0, 0, len(df_export), len(df_export.columns) - 1)

    buffer.seek(0)
    return buffer.read()


# ===========================================================================
# Sidebar — Configuración del evento
# ===========================================================================


def render_sidebar() -> dict[str, str]:
    """
    Renderiza el panel lateral con la configuración del evento.

    Returns
    -------
    dict[str, str]
        Metadatos del evento: nombre, fecha, lugar.
    """
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center; padding-bottom: 0.5rem;">
                <div style="font-size:2.8rem; line-height:1;">📝</div>
                <div style="font-size:1.4rem; font-weight:800; color:#c9a84c; letter-spacing:0.05em; margin-top: 8px;">
                    EMUPP
                </div>
                <div style="font-size:0.85rem; color:rgba(255,255,255,0.6); line-height:1.4; margin-top: 12px;">
                    Normaliza nombres, corrige formatos inconsistentes y genera listas para imprenta en PDF A4.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<hr style='margin: 1.5rem 0 1rem 0; opacity: 0.2;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 1rem; font-weight: 600; margin-bottom: 15px; color: #fff;'>📋 Datos del Evento</div>", unsafe_allow_html=True)

        nombre_evento = st.text_input(
            "Nombre del evento",
            placeholder="Ej: Boda Martínez-García",
            key="input_nombre_evento",
        )
        fecha = st.text_input(
            "Fecha",
            placeholder="Ej: 15 de enero de 2026",
            key="input_fecha",
        )
        lugar = st.text_input(
            "Lugar / Salón",
            placeholder="Ej: Salón Dorado, Madrid",
            key="input_lugar",
        )

    return {"nombre_evento": nombre_evento, "fecha": fecha, "lugar": lugar}


# ===========================================================================
# Sección de carga de datos
# ===========================================================================


def render_carga() -> Optional[pd.DataFrame]:
    """
    Renderiza la sección de carga de archivo y devuelve el DataFrame crudo.

    Returns
    -------
    pd.DataFrame | None
        DataFrame cargado o None si no hay datos.
    """
    st.markdown("#### 📂 Subir archivo de invitados")
    archivo = st.file_uploader(
        "Arrastra aquí tu archivo Excel o CSV (.xlsx, .xls, .csv)",
        type=["xlsx", "xls", "csv"],
        help="El archivo debe contener al menos una columna con nombres.",
        label_visibility="visible",
        key="file_uploader",
    )

    if archivo is not None:
        if archivo.size > 20 * 1024 * 1024:
            st.error("❌ El archivo supera el límite de 20MB. Por favor, sube un archivo más ligero.")
            return None
        try:
            if archivo.name.lower().endswith(".csv"):
                df = pd.read_csv(archivo, dtype=str)
            else:
                df = pd.read_excel(archivo, dtype=str)
            df = df.fillna("")
            st.session_state["df_crudo"] = df
            st.success(
                f"✓ **{archivo.name}** cargado — "
                f"{len(df):,} filas · {len(df.columns)} columnas."
            )
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            return None

    return st.session_state.get("df_crudo", None)


# ===========================================================================
# Sección de configuración de columnas
# ===========================================================================


def render_configuracion_columnas(df: pd.DataFrame) -> dict[str, Optional[str]]:
    """
    UI de mapeo flexible de columnas.

    Modo A — Nombre completo:
        Una sola columna contiene el nombre y apellido juntos.
        El motor aplica heurísticas de separación.

    Modo B — Columnas separadas:
        El Excel ya trae una columna para nombre y otra para apellido.
        Solo se aplica Smart Title Case, sin heurísticas.

    En ambos modos el usuario selecciona qué columna del Excel
    corresponde a cada campo destino mediante selectboxes.

    Parameters
    ----------
    df:
        DataFrame crudo para inspeccionar columnas disponibles.

    Returns
    -------
    dict
        Mapeo ``{campo: nombre_columna_o_None}``.
    """
    columnas_excel = list(df.columns)
    opciones_con_ninguna = ["(ninguna)"] + columnas_excel

    st.markdown("#### 🗂️ Mapeo de columnas")

    # ── Selector de modo ──────────────────────────────────────────────────────
    modo_entrada = st.radio(
        "Formato de los nombres en el Excel",
        options=[
            "🔤 Nombre completo en una sola columna",
            "📋 Columnas separadas (Nombre | Apellido)",
        ],
        horizontal=True,
        key="radio_modo_entrada",
        help=(
            "Elige cómo vienen los nombres en tu archivo. "
            "Si el Excel tiene 'nombre completo' usa la primera opción; "
            "si ya tiene columnas separadas de nombre y apellido usa la segunda."
        ),
    )
    modo_separado = "separadas" in modo_entrada

    # ── Tabla de mapeo: Campo destino → Columna del Excel ────────────────────
    st.markdown(
        '<div style="font-size:0.8rem; color:rgba(255,255,255,0.45); margin-bottom:0.5rem;">'
        'Para cada <b>campo destino</b> elige la <b>columna del Excel</b> correspondiente. '
        'Selecciona <code>(ninguna)</code> para omitir ese campo.'
        '</div>',
        unsafe_allow_html=True,
    )

    if not modo_separado:
        # ── Modo A: nombre completo ───────────────────────────────────────────
        col_header1, col_header2 = st.columns([1, 2], gap="small")
        with col_header1:
            st.markdown(
                '<div style="font-size:0.75rem; font-weight:600; '
                'color:rgba(255,255,255,0.4); text-transform:uppercase; '
                'letter-spacing:0.08em; padding-bottom:4px;">Campo destino</div>',
                unsafe_allow_html=True,
            )
        with col_header2:
            st.markdown(
                '<div style="font-size:0.75rem; font-weight:600; '
                'color:rgba(255,255,255,0.4); text-transform:uppercase; '
                'letter-spacing:0.08em; padding-bottom:4px;">Columna del Excel</div>',
                unsafe_allow_html=True,
            )

        campos_a = [
            ("🏷️ Nombre completo *",   "nombres",       columnas_excel,        False),
            ("🪑 Mesa",                 "mesa",          opciones_con_ninguna,  True),
            ("👥 Acompañantes",         "acompanantes",  opciones_con_ninguna,  True),
            ("🍽️ Menú / Dieta",         "menu",          opciones_con_ninguna,  True),
            ("🂴 DNI",                  "dni",           opciones_con_ninguna,  True),
        ]

        sel: dict[str, Optional[str]] = {}
        for label, clave, opciones, tiene_ninguna in campos_a:
            c1, c2 = st.columns([1, 2], gap="small")
            with c1:
                st.markdown(
                    f'<div style="padding:6px 0; font-size:0.9rem; '
                    f'color:rgba(255,255,255,0.75);">{label}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                # Determinar índice por defecto inteligente
                nombre_probable = clave  # ej: "mesa" → buscar col llamada "mesa"
                if nombre_probable in opciones:
                    idx_default = opciones.index(nombre_probable)
                elif clave == "nombres" and columnas_excel:
                    idx_default = 0
                else:
                    idx_default = 0

                valor = st.selectbox(
                    label,
                    options=opciones,
                    index=idx_default,
                    key=f"map_{clave}",
                    label_visibility="collapsed",
                )
                sel[clave] = None if (tiene_ninguna and valor == "(ninguna)") else valor

        return {
            "columna_nombres":      sel.get("nombres"),
            "columna_apellido":     None,
            "columna_mesa":         sel.get("mesa"),
            "columna_acompanantes": sel.get("acompanantes"),
            "columna_menu":         sel.get("menu"),
            "columna_dni":          sel.get("dni"),
        }

    else:
        # ── Modo B: columnas separadas ────────────────────────────────────────
        col_header1, col_header2 = st.columns([1, 2], gap="small")
        with col_header1:
            st.markdown(
                '<div style="font-size:0.75rem; font-weight:600; '
                'color:rgba(255,255,255,0.4); text-transform:uppercase; '
                'letter-spacing:0.08em; padding-bottom:4px;">Campo destino</div>',
                unsafe_allow_html=True,
            )
        with col_header2:
            st.markdown(
                '<div style="font-size:0.75rem; font-weight:600; '
                'color:rgba(255,255,255,0.4); text-transform:uppercase; '
                'letter-spacing:0.08em; padding-bottom:4px;">Columna del Excel</div>',
                unsafe_allow_html=True,
            )

        campos_b = [
            ("🏷️ Nombre(s) *",         "nombres",       opciones_con_ninguna,  True),
            ("📝 Apellido(s) *",        "apellido",      opciones_con_ninguna,  True),
            ("🪑 Mesa",                 "mesa",          opciones_con_ninguna,  True),
            ("👥 Acompañantes",         "acompanantes",  opciones_con_ninguna,  True),
            ("🍽️ Menú / Dieta",         "menu",          opciones_con_ninguna,  True),
            ("🂴 DNI",                  "dni",           opciones_con_ninguna,  True),
        ]

        sel_b: dict[str, Optional[str]] = {}
        for label, clave, opciones, tiene_ninguna in campos_b:
            c1, c2 = st.columns([1, 2], gap="small")
            with c1:
                st.markdown(
                    f'<div style="padding:6px 0; font-size:0.9rem; '
                    f'color:rgba(255,255,255,0.75);">{label}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                # Determinar índice por defecto inteligente
                if clave == "nombres":
                    candidatos = ["nombre", "nombres", "first_name", "name"]
                elif clave == "apellido":
                    candidatos = ["apellido", "apellidos", "last_name", "surname"]
                elif clave == "dni":
                    candidatos = ["dni", "documento", "cedula", "id"]
                else:
                    candidatos = [clave]

                idx_default = 0
                for candidato in candidatos:
                    if candidato in opciones:
                        idx_default = opciones.index(candidato)
                        break

                valor = st.selectbox(
                    label,
                    options=opciones,
                    index=idx_default,
                    key=f"map_sep_{clave}",
                    label_visibility="collapsed",
                )
                sel_b[clave] = None if (tiene_ninguna and valor == "(ninguna)") else valor

        if sel_b.get("apellido") is None:
            st.warning("⚠️ Selecciona la columna de **Apellido**.")

        return {
            "columna_nombres":      sel_b.get("nombres"),
            "columna_apellido":     sel_b.get("apellido"),
            "columna_mesa":         sel_b.get("mesa"),
            "columna_acompanantes": sel_b.get("acompanantes"),
            "columna_menu":         sel_b.get("menu"),
            "columna_dni":          sel_b.get("dni"),
        }


# ===========================================================================
# Panel de control — métricas + editor
# ===========================================================================


def render_panel_control(df_procesado: pd.DataFrame) -> pd.DataFrame:
    """
    Muestra las métricas, opciones de ordenamiento, el editor inline y el
    botón de guardado que persiste los cambios en session_state.

    Parameters
    ----------
    df_procesado:
        DataFrame ya normalizado por procesar_dataframe.

    Returns
    -------
    pd.DataFrame
        DataFrame tal como está guardado en session_state (post-edición).
    """
    import re as _re

    # ── Métricas ──────────────────────────────────────────────────────────────
    total = len(df_procesado)
    dudosos = int(df_procesado["es_dudoso"].sum()) if "es_dudoso" in df_procesado.columns else 0
    ok = total - dudosos

    col_m1, col_m2, col_m3, col_m4 = st.columns(4, gap="medium")
    with col_m1:
        st.metric("👥 Total invitados", total)
    with col_m2:
        st.metric("✅ Confirmados OK", ok, delta=f"{ok/total*100:.0f}%" if total else "0%")
    with col_m3:
        st.metric(
            "⚠️ Dudosos",
            dudosos,
            delta=f"-{dudosos}" if dudosos else "0",
            delta_color="inverse",
        )
    with col_m4:
        mesas_unicas = df_procesado["mesa"].nunique() if "mesa" in df_procesado.columns else 0
        st.metric("🪑 Mesas", mesas_unicas if mesas_unicas > 0 else "N/A")

    st.markdown("---")

    # ── Opciones de visualización ──────────────────────────────────────────────────
    col_ord, col_filtro, _ = st.columns([2, 2, 4], gap="medium")

    with col_ord:
        orden = st.selectbox(
            "📊 Ordenar por",
            options=["Apellido (A→Z)", "Nombre (A→Z)", "Mesa", "Estado (Dudosos primero)"],
            key="sel_orden",
        )

    with col_filtro:
        filtro = st.selectbox(
            "🔍 Mostrar",
            options=["Todos", "Solo dudosos", "Solo confirmados"],
            key="sel_filtro",
        )

    # Aplicar ordenamiento (natural sort para Mesa)
    def _nat_key(s: str) -> list:
        partes = _re.split(r'(\d+)', str(s).lower())
        return [int(p) if p.isdigit() else p for p in partes]

    df_vista = df_procesado.copy()

    if orden == "Apellido (A→Z)":
        df_vista = df_vista.sort_values("orden_alfabetico", ascending=True)
    elif orden == "Nombre (A→Z)":
        df_vista = df_vista.sort_values("nombre", ascending=True)
    elif orden == "Mesa" and "mesa" in df_vista.columns:
        df_vista = df_vista.iloc[
            sorted(range(len(df_vista)), key=lambda i: _nat_key(df_vista.iloc[i]["mesa"]))
        ]
    elif orden == "Estado (Dudosos primero)":
        df_vista = df_vista.sort_values("es_dudoso", ascending=False)

    # Aplicar filtro
    if filtro == "Solo dudosos" and "es_dudoso" in df_vista.columns:
        df_vista = df_vista[df_vista["es_dudoso"]]
    elif filtro == "Solo confirmados" and "es_dudoso" in df_vista.columns:
        df_vista = df_vista[~df_vista["es_dudoso"]]

    # ── Editor inline ──────────────────────────────────────────────────────────
    st.markdown("#### ✏️ Editor de invitados")
    st.markdown(
        '<div class="alerta-info">'
        "Edita cualquier celda directamente. Cuando termines, pulsa "
        "<b>💾 Guardar cambios</b> para aplicarlos: las filas con "
        "nombre y apellido completos se marcarán automáticamente como ✅ OK."
        "</div>",
        unsafe_allow_html=True,
    )

    # Preparar DataFrame para el editor (columna visual de estado)
    df_editor = df_vista.copy()
    if "es_dudoso" in df_editor.columns:
        df_editor.insert(
            0,
            "Estado",
            df_editor["es_dudoso"].map({True: "⚠️ Dudoso", False: "✅ OK"}),
        )
    # Añadir columna auxiliar para marcar filas a eliminar desde el editor
    if "Eliminar" not in df_editor.columns:
        df_editor.insert(0, "Eliminar", False)

    # Configuración de columnas para el editor
    column_config: dict = {
        "Eliminar": st.column_config.CheckboxColumn("Eliminar", width="small"),
        "Estado": st.column_config.TextColumn("Estado", width="small", disabled=True),
        "nombre": st.column_config.TextColumn("Nombre", width="medium"),
        "apellido": st.column_config.TextColumn("Apellido", width="medium"),
        "orden_alfabetico": st.column_config.TextColumn(
            "Orden Alfabético", width="medium", disabled=True
        ),
        "mesa": st.column_config.TextColumn("Mesa", width="small"),
        "acompanantes": st.column_config.TextColumn("Acompañantes", width="small"),
        "menu": st.column_config.TextColumn("Menú", width="small"),
        "dni": st.column_config.TextColumn("DNI", width="small"),
        "es_dudoso": st.column_config.CheckboxColumn("Dudoso", width="small"),
        "motivo": st.column_config.TextColumn("Nota / Motivo", width="large", disabled=True),
    }

    df_editado = st.data_editor(
        df_editor,
        column_config=column_config,
        column_order=[
            "Estado",
            "Eliminar",
            "es_dudoso",
            "apellido",
            "nombre",
            "orden_alfabetico",
            "mesa",
            "acompanantes",
            "menu",
            "dni",
            "motivo"
        ],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="editor_principal",
    )

    # ── Botón de guardado con auto-corrección ─────────────────────────────────────
    col_btn_save, col_save_info = st.columns([2, 6], gap="medium")
    with col_btn_save:
        if st.button("💾 Guardar cambios", use_container_width=True, key="btn_guardar_cambios"):
            df_save = df_editado.copy()

            # Eliminar columna visual antes de guardar
            if "Estado" in df_save.columns:
                df_save = df_save.drop(columns=["Estado"])

            # Eliminar filas marcadas por el usuario
            if "Eliminar" in df_save.columns:
                try:
                    mask_eliminar = df_save["Eliminar"].astype(bool)
                except Exception:
                    mask_eliminar = df_save["Eliminar"] == True
                if mask_eliminar.any():
                    df_save = df_save.loc[~mask_eliminar]
                df_save = df_save.drop(columns=["Eliminar"])

            # Ignorar filas completamente vacías (no tratarlas como 'Campo vacio')
            campos_check = [c for c in ("nombre", "apellido", "mesa", "acompanantes", "menu", "dni") if c in df_save.columns]
            if campos_check:
                mask_vacias = (
                    df_save[campos_check].fillna("")
                    .applymap(lambda x: str(x).strip() == "")
                    .all(axis=1)
                )
                if mask_vacias.any():
                    df_save = df_save.loc[~mask_vacias]

            # Recalcular orden_alfabetico
            if "nombre" in df_save.columns and "apellido" in df_save.columns:
                df_save["orden_alfabetico"] = (
                    df_save["apellido"].fillna("").str.strip()
                    + ", "
                    + df_save["nombre"].fillna("").str.strip()
                ).str.strip(", ")

            # Limpiar 'motivo' si es_dudoso fue desmarcado manualmente
            if "es_dudoso" in df_save.columns:
                # Para todos los que terminan con es_dudoso == False, limpiar motivo
                df_save.loc[~df_save["es_dudoso"], "motivo"] = "Editado manualmente ✓"

            # Actualizar solo las filas correspondientes en el DataFrame original
            df_original = st.session_state["df_procesado"].copy()
            df_original.loc[df_save.index, df_save.columns] = df_save
            st.session_state["df_procesado"] = df_original
            st.rerun()

    with col_save_info:
        pend = int(df_editado["es_dudoso"].sum()) if "es_dudoso" in df_editado.columns else 0
        st.markdown(
            f'<div style="font-size:0.8rem; color:rgba(255,255,255,0.4); padding-top:0.6rem;">'
            f"Mostrando {len(df_vista):,} de {len(df_procesado):,} invitados. "
            f"{'<b style=\"color:#f0ad4e\">' + str(pend) + ' pendiente(s) de revisión.</b>' if pend else '<span style=\"color:#6fcf97;\">Todo OK ✔</span>'}"
            f'</div>',
            unsafe_allow_html=True,
        )

    # Preparar el dataframe que se devuelve al flujo normal
    df_para_exportar = df_editado.copy()
    if "Estado" in df_para_exportar.columns:
        df_para_exportar = df_para_exportar.drop(columns=["Estado"])
    if "nombre" in df_para_exportar.columns and "apellido" in df_para_exportar.columns:
        df_para_exportar["orden_alfabetico"] = (
            df_para_exportar["apellido"].fillna("").str.strip() + ", " + df_para_exportar["nombre"].fillna("").str.strip()
        ).str.strip(", ")

    return df_para_exportar


# ===========================================================================
# Sección de exportación
# ===========================================================================


def render_exportacion(
    df_procesado: pd.DataFrame,
    metadata_evento: dict[str, str],
) -> None:
    """
    Renderiza los botones de exportación a Excel y PDF con su propio filtro.

    Parameters
    ----------
    df_procesado:
        DataFrame completo con los invitados.
    metadata_evento:
        Metadatos del evento para el encabezado del PDF.
    """
    st.markdown("---")
    st.markdown("### 📤 Exportar")

    # ── Opciones de Exportación ───────────────────────────────────────────────
    col_filtro, col_modo, col_salto = st.columns([2, 2, 2], gap="medium")
    
    with col_filtro:
        filtro_export = st.selectbox(
            "Filtrar invitados a exportar",
            options=["Todos", "Solo dudosos", "Solo confirmados"],
            key="filtro_export",
        )
    
    with col_modo:
        modo_pdf = st.radio(
            "Modo del PDF",
            options=["Alfabético (2 columnas)", "Por Mesas"],
            horizontal=True,
            key="radio_modo_pdf",
        )
        
    with col_salto:
        modo_key = "alfabetico" if "Alfabético" in modo_pdf else "mesas"
        if modo_key == "mesas":
            st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
            salto_pagina = st.checkbox(
                "Salto de página entre mesas",
                value=True,
                key="chk_salto_pagina",
            )
        else:
            salto_pagina = True

    # Aplicar el filtro para la exportación
    df_export = df_procesado.copy()
    if filtro_export == "Solo dudosos" and "es_dudoso" in df_export.columns:
        df_export = df_export[df_export["es_dudoso"]]
    elif filtro_export == "Solo confirmados" and "es_dudoso" in df_export.columns:
        df_export = df_export[~df_export["es_dudoso"]]

    nombre_evento_slug = (
        metadata_evento.get("nombre_evento", "invitados")
        .lower()
        .replace(" ", "_")[:30]
    )

    pdf_status_placeholder = st.empty()
    col_excel, col_pdf, col_info = st.columns([2, 2, 4], gap="medium")

    # ── Exportar Excel ────────────────────────────────────────────────────────
    with col_excel:
        st.markdown("**📊 Excel limpio**")
        try:
            excel_bytes = generar_excel(df_export)
            st.download_button(
                label="⬇ Descargar Excel (.xlsx)",
                data=excel_bytes,
                file_name=f"invitados_{nombre_evento_slug}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="btn_download_excel",
            )
        except Exception as e:
            st.error(f"Error generando Excel: {e}")

    # ── Exportar PDF ──────────────────────────────────────────────────────────
    with col_pdf:
        st.markdown("**🖨️ PDF de Imprenta**")
        if st.button("🔄 Generar PDF", use_container_width=True, key="btn_generar_pdf"):
            with pdf_status_placeholder:
                with st.spinner("Compilando PDF con WeasyPrint…"):
                    try:
                        registros = df_export.to_dict(orient="records")
                        pdf_bytes = generar_pdf(
                            datos_invitados=registros,
                            metadata_evento=metadata_evento,
                            modo=modo_key,
                            salto_pagina_mesas=salto_pagina,
                        )
                        st.session_state["pdf_bytes"] = pdf_bytes
                        st.session_state["pdf_modo"] = modo_key
                        st.success("PDF generado correctamente.")
                    except Exception as e:
                        st.error(f"Error generando PDF: {e}")

        if "pdf_bytes" in st.session_state:
            st.download_button(
                label="⬇ Descargar PDF (.pdf)",
                data=st.session_state["pdf_bytes"],
                file_name=f"lista_imprenta_{nombre_evento_slug}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="btn_download_pdf",
            )

    with col_info:
        total = len(df_export)
        dudosos = int(df_export["es_dudoso"].sum()) if "es_dudoso" in df_export.columns else 0
        salto_txt = "con salto de página" if salto_pagina else "continuo (sin saltos)"
        st.markdown(
            f"""
            <div style="font-size:0.82rem; color:rgba(255,255,255,0.5); padding-top:1.8rem;">
            📋 Se exportarán <b style="color:#c9a84c">{total}</b> invitados en modo
            <b style="color:#c9a84c">{"alfabético" if modo_key=="alfabetico" else f"por mesas ({salto_txt})"}</b>.
            {"<br>⚠️ Aún hay <b style='color:#f0ad4e'>" + str(dudosos) + "</b> entrada(s) dudosa(s) sin revisar." if dudosos > 0 else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )



# ===========================================================================
# Punto de entrada principal
# ===========================================================================


def main() -> None:
    """Función principal de la aplicación Streamlit."""

    # ── Inicializar estados ───────────────────────────────────────────────────
    if "df_crudo" not in st.session_state:
        st.session_state["df_crudo"] = None
    if "df_procesado" not in st.session_state:
        st.session_state["df_procesado"] = None
    if "mostrar_tutorial" not in st.session_state:
        st.session_state["mostrar_tutorial"] = False

    # ── Encabezado hero y Botón Tutorial ──────────────────────────────────────
    col_hero, col_tut = st.columns([5, 1], gap="medium")
    with col_hero:
        st.markdown(
            f"""
            <div class="hero-title" style="display: flex; align-items: center;">
                🎉 Gestor de Invitados 
                <span style="font-size: 0.85rem; background: rgba(201,168,76,0.1); color: #c9a84c; padding: 4px 12px; border-radius: 20px; font-weight: 600; border: 1px solid rgba(201,168,76,0.3); margin-left: 15px; margin-top: 8px;">v{VERSION}</span>
            </div>
            <div class="hero-subtitle">
                Normalización inteligente de listas de invitados · Exportación PDF de imprenta A4
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with col_tut:
        st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
        if st.button("📘 Tutorial", use_container_width=True):
            st.session_state["mostrar_tutorial"] = not st.session_state["mostrar_tutorial"]
            st.rerun()
            
    if st.session_state["mostrar_tutorial"]:
        with st.expander("📖 **Guía rápida: ¿Cómo usar EMUPP?**", expanded=True):
            st.markdown(
                """
                1. **Configura el evento**: Ve a la barra lateral izquierda e ingresa el nombre, fecha y lugar de tu evento.
                2. **Sube tu archivo**: Arrastra tu lista de invitados en formato Excel (`.xlsx`) o CSV al área de carga.
                3. **Mapea las columnas**: Selecciona qué columna de tu Excel corresponde al nombre, apellido, mesa, etc.
                4. **Procesa y revisa**: Pulsa el botón **⚡ Procesar nombres**. El sistema normalizará los nombres automáticamente. Revisa los casos marcados como ⚠️ **Dudosos**.
                5. **Edita y Guarda**: Si hay algún error, corrígelo directamente sobre la tabla y pulsa **💾 Guardar cambios**.
                6. **Exporta**: Por último, genera tu PDF ordenado (alfabéticamente o por mesas) listo para la imprenta, o descarga un Excel limpio.
                """
            )

    # ── Sidebar ───────────────────────────────────────────────────────────────
    metadata_evento = render_sidebar()

    # ── Carga de datos ────────────────────────────────────────────────────────
    with st.container():
        df_crudo = render_carga()

    if df_crudo is None:
        st.markdown(
            """
            <div style="text-align:center; padding: 4rem 2rem; color:rgba(255,255,255,0.3);">
                <div style="font-size:3rem;">📁</div>
                <div style="font-size:1rem; margin-top:1rem;">
                    Sube un archivo Excel o CSV para comenzar.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # ── Preview del archivo crudo ─────────────────────────────────────────────
    with st.expander("👁️ Vista previa del archivo original", expanded=False):
        st.dataframe(df_crudo.head(10), use_container_width=True)
        st.caption(f"Mostrando 10 de {len(df_crudo)} filas · {len(df_crudo.columns)} columnas")

    st.markdown("---")

    # ── Configuración de columnas ─────────────────────────────────────────────
    config_columnas = render_configuracion_columnas(df_crudo)

    # ── Botón de procesamiento ────────────────────────────────────────────────
    col_btn, col_info_proc = st.columns([2, 6], gap="medium")
    with col_btn:
        procesar = st.button(
            "⚡ Procesar nombres",
            type="primary",
            use_container_width=True,
            key="btn_procesar",
        )

    if procesar:
        with st.spinner("Normalizando nombres…"):
            try:
                df_proc = procesar_dataframe(
                    df=df_crudo,
                    columna_nombres=config_columnas["columna_nombres"],
                    columna_mesa=config_columnas["columna_mesa"],
                    columna_acompanantes=config_columnas["columna_acompanantes"],
                    columna_menu=config_columnas["columna_menu"],
                    columna_apellido=config_columnas.get("columna_apellido"),
                    columna_dni=config_columnas.get("columna_dni"),
                )
                st.session_state["df_procesado"] = df_proc
                dudosos = int(df_proc["es_dudoso"].sum()) if "es_dudoso" in df_proc.columns else 0
                st.success(
                    f"✓ {len(df_proc)} invitados procesados — "
                    f"{len(df_proc) - dudosos} OK · {dudosos} ⚠️ dudosos"
                )
            except Exception as e:
                st.error(f"Error durante el procesamiento: {e}")

    # ── Panel de control (si hay datos procesados) ────────────────────────────
    if st.session_state.get("df_procesado") is not None:
        st.markdown("---")
        st.markdown("## 📊 Panel de Control")

        df_editado = render_panel_control(st.session_state["df_procesado"])

        # ── Exportación ───────────────────────────────────────────────────────
        render_exportacion(st.session_state["df_procesado"], metadata_evento)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    main()
