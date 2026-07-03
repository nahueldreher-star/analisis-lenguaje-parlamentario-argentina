"""
matching_bloques.py
Construye la tabla de lookup autor+año -> bloque parlamentario
a partir del PDF de composición histórica de la Cámara de Diputados,
y la cruza con el CSV de proyectos limpios.

INPUTS:
  - proyectos_limpios.csv       (output de limpiar_proyectos.py)
  - Comp_Dip_1983-2025.pdf      (Dirección de Información Parlamentaria,
                                  "Composición de la Honorable Cámara de
                                  Diputados de la Nación, 1983-2025")

OUTPUTS:
  - diputados_bloques_historico.csv   (registros crudos extraídos del PDF)
  - lookup_autor_anio_bloque.csv      (tabla de referencia nombre+año -> bloque)
  - proyectos_con_bloque.csv          (dataset final con bloque asignado)

ADVERTENCIA:
  Los rangos de página (PERIOD_PAGES) fueron determinados manualmente
  inspeccionando el PDF descargado en junio de 2026. Si se usa una
  versión distinta o actualizada del PDF, estos rangos casi seguro
  van a estar mal y hay que re-detectarlos (ver función
  detectar_paginas_periodo() al final del archivo, no ejecutada por
  default).

Ejecutar: python matching_bloques.py
Requiere: pandas, pdfplumber
"""

import re
import unicodedata
from datetime import datetime

import pandas as pd
import pdfplumber

# ─── Configuración ──────────────────────────────────────────────────────────

PDF_PATH = "Comp_Dip_1983-2025.pdf"
PROYECTOS_LIMPIOS_PATH = "proyectos_limpios.csv"

OUT_DIPUTADOS = "diputados_bloques_historico.csv"
OUT_LOOKUP = "lookup_autor_anio_bloque.csv"
OUT_PROYECTOS_CON_BLOQUE = "proyectos_con_bloque.csv"

# Rango de páginas (1-indexed, inclusive) por bienio, para el PDF de
# junio 2026. VERIFICAR si se usa otro PDF.
PERIOD_PAGES = {
    "2007-2009": (259, 282),
    "2009-2011": (283, 303),
    "2011-2013": (304, 324),
    "2013-2015": (325, 344),
    "2015-2017": (345, 368),
    "2017-2019": (369, 391),
    "2019-2021": (392, 414),
    "2021-2023": (415, 438),
    "2023-2025": (439, 465),
}

# Filas de encabezado/navegación a descartar de las tablas extraídas
SKIP_PATTERNS = [
    "Legislador", "Distrito", "Mandato", "Ejercicio", "Bloque",
    "desde", "hasta", "Nombre", "Inicio", "Fin", "Observaciones",
    "Composición", "Honorable", "Cámara", "Diputados", "Dirección",
    "Parlamentaria", "Departamento", "Página", "diciembre",
]

MIN_YEAR_FOR_MATCH = 2008
MAX_YEAR_FOR_MATCH = 2025
EXPECTED_COLS_PROYECTOS = 9


# ─── Utilidades de normalización ────────────────────────────────────────────

def normalize_name(s: str) -> str:
    """Mayúsculas, sin tildes, sin comas/puntos, espacios colapsados."""
    s = str(s).upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r'[,.\"]', " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_date(s: str):
    """Parsea fechas dd/mm/YYYY o dd/mm/YY. Devuelve None si falla."""
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


# ─── Extracción del PDF ─────────────────────────────────────────────────────

def extraer_diputados_del_pdf(pdf_path: str, period_pages: dict) -> pd.DataFrame:
    """
    Recorre las páginas indicadas en period_pages y extrae, de cada tabla
    encontrada, los registros de legislador/bloque/período de pertenencia.

    Estructura esperada de columnas en cada fila de tabla (0-indexed):
      0: Legislador (nombre, puede venir con salto de línea)
      1: Distrito
      2: Mandato (ej. "2007-2011")
      3: Ejercicio desde
      4: Ejercicio hasta
      5: Bloque (nombre)
      6: Bloque inicio (fecha)
      7: Bloque fin (fecha)
      8: Observaciones

    Esta estructura fue verificada visualmente en una muestra de páginas,
    no en la totalidad. Si pdfplumber cambia de versión el layout de
    extracción de tablas puede variar.
    """
    records = []

    with pdfplumber.open(pdf_path) as pdf:
        for period, (start, end) in period_pages.items():
            for page_num in range(start, end + 1):
                page = pdf.pages[page_num - 1]  # pdfplumber es 0-indexed
                for table in page.extract_tables():
                    for row in table:
                        if not row or not row[0]:
                            continue
                        c0 = str(row[0]).strip()

                        if any(p in c0 for p in SKIP_PATTERNS):
                            continue
                        if not c0 or c0 == "None" or len(c0) < 3:
                            continue
                        if not re.match(r"[A-ZÁÉÍÓÚÜÑ]", c0):
                            continue

                        bloque = str(row[5] or "").replace("\n", " ").strip()
                        if bloque in ("None", "", "Nombre"):
                            continue

                        records.append({
                            "bienio": period,
                            "legislador": c0.replace("\n", " ").strip(),
                            "mandato": str(row[2] or "").strip(),
                            "bl_inicio": str(row[6] or "").strip(),
                            "bl_fin": str(row[7] or "").strip(),
                            "bloque": bloque,
                        })

    df = pd.DataFrame(records)
    df["nombre_norm"] = df["legislador"].apply(normalize_name)
    return df


# ─── Construcción del lookup autor+año -> bloque ───────────────────────────

def construir_lookup(df_diputados: pd.DataFrame) -> pd.DataFrame:
    """
    Expande cada registro legislador/bloque (con rango de fechas de
    pertenencia al bloque) a una fila por año cubierto, para poder
    hacer join directo por año contra los proyectos de ley.

    Si un legislador tuvo más de un bloque en el mismo año (cambio de
    bloque a mitad de año), se queda con el PRIMER bloque detectado para
    ese año-nombre (`drop_duplicates` sin `keep=` usa el default de pandas:
    `keep="first"`). El orden de extracción del PDF sigue el orden
    cronológico de inicio de bloque en el 99.5% de los casos (367/369
    verificados), por lo que `keep="first"` asigna sistemáticamente el
    bloque MÁS ANTIGUO del año para legisladores con cambio intra-año.

    Impacto medido: 373 de 6.027 pares (nombre, año) tienen cambio de
    bloque intra-año (6.19%). A nivel proyecto: 7.610 proyectos reciben
    bloque distinto bajo keep="first" vs keep="last" (7.80% de matcheados).
    De esos, solo 437 (0.46% del total matcheado) cruzan familia política.
    Como todas las figuras del análisis operan a nivel familia, el impacto
    real sobre los resultados es 0.46%. Se optó por mantener keep="first"
    (no implementar fix por fecha exacta) porque el match por rango de
    fechas baja la cobertura 2.5 puntos para corregir 0.46%: trade neto
    negativo. Limitación documentada en la sección de Metodología del paper.
    """
    df = df_diputados.copy()
    df["inicio_dt"] = df["bl_inicio"].apply(parse_date)
    df["fin_dt"] = df["bl_fin"].apply(parse_date)
    df["anio_inicio"] = df["inicio_dt"].apply(lambda d: d.year if d else None)
    df["anio_fin"] = df["fin_dt"].apply(lambda d: d.year if d else None)

    rows = []
    for _, row in df.iterrows():
        if pd.isna(row["anio_inicio"]) or pd.isna(row["anio_fin"]):
            continue
        for yr in range(int(row["anio_inicio"]), int(row["anio_fin"]) + 1):
            rows.append({
                "nombre_norm": row["nombre_norm"],
                "anio": yr,
                "bloque": row["bloque"],
            })

    lookup = pd.DataFrame(rows).drop_duplicates(subset=["nombre_norm", "anio"], keep="first")  # intencional: ver docstring
    return lookup


# ─── Cruce con proyectos ────────────────────────────────────────────────────

def cruzar_proyectos_con_bloque(
    proyectos_path: str, lookup: pd.DataFrame
) -> pd.DataFrame:
    proy = pd.read_csv(proyectos_path)

    if proy.shape[1] != EXPECTED_COLS_PROYECTOS:
        raise ValueError(
            f"Se esperaban {EXPECTED_COLS_PROYECTOS} columnas en "
            f"{proyectos_path}, se encontraron {proy.shape[1]}. "
            "Verificar que el CSV de entrada sea el output correcto "
            "de limpiar_proyectos.py."
        )

    proy["anio"] = pd.to_datetime(
        proy["PUBLICACION_FECHA"], errors="coerce"
    ).dt.year
    proy = proy[proy["anio"].between(MIN_YEAR_FOR_MATCH, MAX_YEAR_FOR_MATCH)]
    proy["autor_norm"] = proy["AUTOR"].apply(
        lambda x: normalize_name(str(x).replace(",", " "))
    )

    merged = proy.merge(
        lookup,
        left_on=["autor_norm", "anio"],
        right_on=["nombre_norm", "anio"],
        how="left",
    )
    return merged


# ─── Ejecución principal ────────────────────────────────────────────────────

def main():
    print(f"Extrayendo diputados desde {PDF_PATH}...")
    df_diputados = extraer_diputados_del_pdf(PDF_PATH, PERIOD_PAGES)
    print(f"  Registros extraídos: {len(df_diputados):,}")
    print(f"  Legisladores únicos: {df_diputados['nombre_norm'].nunique():,}")

    print("Construyendo lookup autor+año -> bloque...")
    lookup = construir_lookup(df_diputados)
    print(f"  Filas en lookup: {len(lookup):,}")

    print(f"Cruzando con {PROYECTOS_LIMPIOS_PATH}...")
    proy_final = cruzar_proyectos_con_bloque(PROYECTOS_LIMPIOS_PATH, lookup)

    matched = proy_final["bloque"].notna()
    print(f"  Proyectos en rango {MIN_YEAR_FOR_MATCH}-{MAX_YEAR_FOR_MATCH}: "
          f"{len(proy_final):,}")
    print(f"  Con bloque asignado: {matched.sum():,} "
          f"({matched.mean() * 100:.1f}%)")
    print(f"  Sin bloque (unmatched): {(~matched).sum():,}")

    df_diputados.to_csv(OUT_DIPUTADOS, index=False)
    lookup.to_csv(OUT_LOOKUP, index=False)
    proy_final.to_csv(OUT_PROYECTOS_CON_BLOQUE, index=False)

    print(f"\nGuardado: {OUT_DIPUTADOS}")
    print(f"Guardado: {OUT_LOOKUP}")
    print(f"Guardado: {OUT_PROYECTOS_CON_BLOQUE}")


# ─── Utilidad NO ejecutada por default: re-detección de páginas ───────────

def detectar_paginas_periodo(pdf_path: str, anio_desde: int, anio_hasta: int):
    """
    Escanea el PDF completo buscando los encabezados de período
    ("10 de diciembre de AAAA a 9 de diciembre de AAAA") para
    re-mapear PERIOD_PAGES si se usa un PDF distinto al validado
    originalmente. No se ejecuta en el flujo principal: es una
    herramienta de diagnóstico manual.
    """
    import pdfplumber as _pp

    transitions = {}
    prev_period = None
    with _pp.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            m = re.search(
                r"10 de diciembre de (\d{4}) a 9 de diciembre de (\d{4})",
                text,
            )
            if m:
                period = f"{m.group(1)}-{m.group(2)}"
                if period != prev_period:
                    transitions[period] = page_num
                    prev_period = period
    return transitions


if __name__ == "__main__":
    main()
