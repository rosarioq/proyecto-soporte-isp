"""Funciones propias de limpieza y EDA para DataFrames de pandas.

Uso en el proyecto:
- limpiar_nombres_columnas -> src/limpieza.py, cargar()                  (T1)
- reporte_nulos            -> notebook, Paso 3                           (T3)
- normalizar_texto         -> src/limpieza.py, estandarizar_categorias() (T4)
- limites_iqr              -> src/limpieza.py, marcar_atipicos()         (T6)

Pruebas:  python src/utilidades.py
"""
import re
import unicodedata

import pandas as pd


def limpiar_nombres_columnas(df):
    """Estandariza los nombres de columnas: minúsculas, sin tildes, sin espacios
    al inicio/fin, espacios internos -> "_".
        Parámetro: DataFrame
        Devuelve una COPIA del DataFrame con los nombres de columna limpios.
        Uso: T1, al cargar el CSV de tickets."""
    df = df.copy()
    nuevas_columnas = []
    for col in df.columns:
        col = str(col).strip()
        col = unicodedata.normalize("NFKD", col).encode("ascii", "ignore").decode("ascii")  # quita tildes
        col = col.lower()
        col = re.sub(r"\s+", "_", col)
        nuevas_columnas.append(col)
    df.columns = nuevas_columnas
    return df


def reporte_nulos(df):
    """Resume los valores nulos por columna.
        Parámetro: DataFrame
        Devuelve un DataFrame con columnas "columna", "n_nulos", "pct_nulos",
        ordenado de mayor a menor porcentaje de nulos.
        Uso: T3, diagnóstico de nulos antes de decidir su tratamiento."""
    n_nulos = df.isna().sum()
    pct_nulos = (df.isna().mean() * 100).round(2)
    reporte = pd.DataFrame({
        "columna": df.columns,
        "n_nulos": n_nulos.values,
        "pct_nulos": pct_nulos.values,
    })
    return reporte.sort_values("pct_nulos", ascending=False).reset_index(drop=True)


def normalizar_texto(serie):
    """Normaliza una columna de texto: quita espacios al inicio/fin, pasa a
    minúsculas y colapsa espacios internos múltiples a uno solo.
        Parámetro: Series de texto
        Devuelve una Series normalizada (los NaN se conservan).
        Uso: T4, unificar los nombres de cantón escritos de varias formas."""
    return (
        serie.astype("string")
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
    )


def limites_iqr(serie, k=1.5):
    """Calcula los límites de atípicos con el método IQR (Tukey):
    lim_inf = Q1 - k*IQR, lim_sup = Q3 + k*IQR.
        Parámetros: serie numérica; k = factor multiplicador del IQR (1.5 por defecto)
        Devuelve la tupla (lim_inf, lim_sup).
        Uso: T6, umbral de tiempos atípicos por nivel de atención (sobre log de horas)."""
    q1 = serie.quantile(0.25)
    q3 = serie.quantile(0.75)
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr


""" Probando las funciones de utilidades.py"""
if __name__ == "__main__":

    # Prueba limpiar_nombres_columnas
    df_prueba = pd.DataFrame({" Fecha Apertura ": ["2026-01-01"], "Cantón": ["Quito"]})
    assert limpiar_nombres_columnas(df_prueba).columns.tolist() == ["fecha_apertura", "canton"]

    # Prueba reporte_nulos
    df_nulos = pd.DataFrame({"canal": ["Llamada", None, "App"], "nodo": ["N-QTO-01", "N-QTO-02", "N-IBA-01"]})
    rep = reporte_nulos(df_nulos)
    assert rep.loc[rep["columna"] == "canal", "n_nulos"].iloc[0] == 1
    assert rep.loc[rep["columna"] == "nodo", "n_nulos"].iloc[0] == 0
    assert rep.loc[0, "columna"] == "canal"          # ordenado de mayor a menor

    # Prueba normalizar_texto
    serie_prueba = pd.Series(["  Quito", "QUITO  ", "pedro   moncayo", None])
    resultado = normalizar_texto(serie_prueba)
    assert resultado.iloc[:3].tolist() == ["quito", "quito", "pedro moncayo"]
    assert pd.isna(resultado.iloc[3])                # los NaN se conservan

    # Prueba limites_iqr
    lim_inf, lim_sup = limites_iqr(pd.Series([1, 2, 3, 4, 5, 100]))
    assert (float(lim_inf), float(lim_sup)) == (-1.5, 8.5)

    print("Todas las pruebas fueron exitosas.")
