"""Indicadores de soporte y segmentación con n por grupo (T8).

Lo usan el notebook y el dashboard, así ambos calculan exactamente lo mismo.
"""
import pandas as pd

N_MINIMO = 30  # por debajo de este n, un porcentaje puede variar mucho por azar


def kpis(df: pd.DataFrame) -> dict:
    """Indicadores globales del conjunto filtrado."""
    return {
        "tickets": len(df),
        "sla_pct": df["cumple_sla"].mean() * 100,
        "fcr_pct": df["fcr"].mean() * 100,
        "reincidencia_pct": df["reincidencia_30d"].mean() * 100,
        "mediana_h": df["tiempo_resolucion_h"].median(),
        "csat": df["satisfaccion"].mean(),
        "respuesta_csat_pct": df["satisfaccion"].notna().mean() * 100,
    }


def resumen_por(df: pd.DataFrame, grupo, n_minimo: int = N_MINIMO) -> pd.DataFrame:
    """Tabla de indicadores por grupo, con el n de cada grupo y una
    advertencia cuando el grupo es demasiado pequeño para comparar."""
    tabla = df.groupby(grupo, observed=True).agg(
        n=("id_ticket", "size"),
        sla_pct=("cumple_sla", "mean"),
        fcr_pct=("fcr", "mean"),
        reincidencia_pct=("reincidencia_30d", "mean"),
        visita_pct=("visita", "mean"),
        mediana_h=("tiempo_resolucion_h", "median"),
        csat=("satisfaccion", "mean"),
        n_csat=("satisfaccion", "count"),
    )
    for col in ["sla_pct", "fcr_pct", "reincidencia_pct", "visita_pct"]:
        tabla[col] = tabla[col] * 100
    tabla["advertencia"] = tabla["n"].lt(n_minimo).map({True: f"n < {n_minimo}", False: ""})
    return tabla.round(2)


def tasa_por_nodo(df: pd.DataFrame, nodos: pd.DataFrame, meses: float = None) -> pd.DataFrame:
    """Tickets por cada 100 clientes al mes: compara nodos de distinto tamaño.
    `meses` = duración del periodo en meses de 30,44 días. Por defecto se toma
    del primer al último día con tickets (el dashboard lo pasa según el filtro)."""
    if meses is None:
        dias = (df["fecha_apertura"].max().normalize() - df["fecha_apertura"].min().normalize()).days + 1
        meses = max(dias / 30.44, 1 / 30.44)
    t = resumen_por(df, "nodo").join(nodos.set_index("nodo"))
    t["tickets_100_clientes_mes"] = (t["n"] / t["clientes_activos"] * 100 / meses).round(2)
    t["sin_servicio_pct"] = (df.groupby("nodo")["tipo_falla"]
                             .apply(lambda s: s.eq("Sin servicio").mean() * 100).round(1))
    return t.sort_values("tickets_100_clientes_mes", ascending=False)
