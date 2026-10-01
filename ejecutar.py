"""Pipeline completo: generar datos -> limpiar -> guardar procesados.
Uso:  python ejecutar.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import generar_datos  # noqa: E402
import limpieza       # noqa: E402

if __name__ == "__main__":
    print("1/2 Generando datos sintéticos (semilla 2026)...")
    generar_datos.main()
    print("\n2/2 Limpiando (T1 a T7)...")
    limpieza.main()
