"""
limpiar_proyectos.py
Script de preprocesamiento para proyectos_parlamentarios.csv (HCDN)
Output: proyectos_limpios.csv
Ejecutar: python limpiar_proyectos.py
"""

import csv
import io
import re
import sys
from pathlib import Path

INPUT_FILE  = "proyectos_parlamentarios2_2.csv"
OUTPUT_FILE = "proyectos_limpios.csv"
EXPECTED_COLS = 9

def fix_entities(text: str) -> str:
    text = re.sub(r'(&[a-zA-Z]+)\";\"', r'\1;', text)
    text = re.sub(r'(&[a-zA-Z]+)\";(?!\")', r'\1;', text)
    text = re.sub(r'(&[a-zA-Z]+);\"', r'\1;', text)
    return text

def parse_line(raw_line: str):
    fixed = fix_entities(raw_line.rstrip("\r\n").rstrip(";"))
    try:
        outer = next(csv.reader(io.StringIO(fixed)))
        if not outer:
            return None
        inner = next(csv.reader(io.StringIO(outer[0])))
        return inner if len(inner) == EXPECTED_COLS else None
    except (StopIteration, csv.Error):
        return None

def main():
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        print(f"ERROR: No se encuentra {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"Procesando {INPUT_FILE}...")
    ok = 0
    dropped = 0
    header = ["PROYECTO_ID", "TITULO", "PUBLICACION_FECHA",
              "PUBLICACION_ID", "CAMARA_ORIGEN", "EXP_DIPUTADOS",
              "EXP_SENADO", "TIPO", "AUTOR"]

    with (
        open(INPUT_FILE, "r", encoding="utf-8") as fin,
        open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as fout,
    ):
        writer = csv.writer(fout, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)
        next(fin)
        for line in fin:
            parsed = parse_line(line)
            if parsed:
                writer.writerow(parsed)
                ok += 1
            else:
                dropped += 1

    print(f"Filas escritas : {ok:,}")
    print(f"Filas dropeadas: {dropped:,}")
    print(f"Recovery rate  : {ok / (ok + dropped) * 100:.1f}%")
    print(f"Output: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
