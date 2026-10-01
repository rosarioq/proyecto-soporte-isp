"""Limpieza y variables derivadas de los tickets de soporte (T1 a T7).

Cada función devuelve una COPIA del DataFrame y registra en `bitacora`
cuántas filas afectó, para documentar el n de cada decisión.
Uso:  python src/limpieza.py   -> data/procesados/tickets_limpios.csv
"""
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utilidades import limpiar_nombres_columnas, limites_iqr, normalizar_texto  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
FECHA_CORTE = pd.Timestamp("2026-06-30 23:59:59")

CANTONES = ["Quito", "Mejía", "Cayambe", "Pedro Moncayo", "Ibarra", "Otavalo"]
# Meta de SLA (horas) acordada con el cliente: más holgada en zona rural
META_SLA = {("Sin servicio", "Urbana"): 24, ("Sin servicio", "Rural"): 48}
META_SLA_OTROS = {"Urbana": 48, "Rural": 72}
N_MINIMO = 30  # grupos con menos tickets se reportan con advertencia


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


class Bitacora(list):
    def anotar(self, paso, decision, filas_afectadas, filas_resultantes):
        self.append({"paso": paso, "decision": decision,
                     "filas_afectadas": int(filas_afectadas),
                     "filas_resultantes": int(filas_resultantes)})

    def tabla(self):
        return pd.DataFrame(self)


# --------------------------------------------------------------------- T1
def cargar(ruta_tickets, ruta_nodos):
    """T1 · Carga con tipos explícitos: fechas como datetime, IDs como texto."""
    tickets = pd.read_csv(ruta_tickets, dtype={"id_ticket": str, "cliente_id": str,
                                               "tecnico_id": str})
    tickets = limpiar_nombres_columnas(tickets)
    for col in ["fecha_apertura", "fecha_cierre"]:
        tickets[col] = pd.to_datetime(tickets[col], format="%Y-%m-%d %H:%M", errors="coerce")
    nodos = pd.read_csv(ruta_nodos)
    return tickets, nodos


# --------------------------------------------------------------------- T2
def quitar_duplicados(df, bit):
    """T2 · Un ticket = un id_ticket. Las filas repetidas son doble registro del CRM."""
    antes = len(df)
    out = df.drop_duplicates(subset="id_ticket", keep="first")
    bit.anotar("T2", "Eliminar tickets duplicados (mismo id_ticket)", antes - len(out), len(out))
    return out.reset_index(drop=True)


# --------------------------------------------------------------------- T3
def tratar_nulos(df, bit):
    """T3 · Los nulos se clasifican antes de decidir:
    - fecha_cierre nula en tickets 'Abierto': estructural, se conserva.
    - tecnico_id nulo sin visita técnica: estructural, se conserva.
    - satisfaccion nula: el cliente no respondió; no se imputa (se reporta la tasa de respuesta).
    - canal nulo: faltante real; se etiqueta 'Sin registro' para no perder el ticket.
    """
    out = df.copy()
    n_canal = out["canal"].isna().sum()
    out["canal"] = out["canal"].fillna("Sin registro")
    bit.anotar("T3", "Canal faltante -> 'Sin registro' (no se elimina el ticket)", n_canal, len(out))
    n_sat = out["satisfaccion"].isna().sum()
    bit.anotar("T3", "Satisfacción sin respuesta: se conserva como NaN, no se imputa", n_sat, len(out))
    return out


# --------------------------------------------------------------------- T4
def estandarizar_categorias(df, bit):
    """T4 · Cantón y plan escritos de varias formas se llevan a una sola etiqueta."""
    out = df.copy()
    canonico = {_sin_tildes(c).lower(): c for c in CANTONES}
    clave = normalizar_texto(out["canton"]).map(lambda s: _sin_tildes(s) if isinstance(s, str) else s)
    nuevo = clave.map(canonico)
    n_canton = (nuevo != out["canton"]).sum()
    out["canton"] = nuevo
    bit.anotar("T4", "Cantón: espacios, mayúsculas y tildes unificados", n_canton, len(out))

    nuevo_plan = out["plan"].str.replace(r"\s*mbps$", " Mbps", regex=True, case=False)
    bit.anotar("T4", "Plan: '100mbps' -> '100 Mbps'", (nuevo_plan != out["plan"]).sum(), len(out))
    out["plan"] = nuevo_plan
    return out


# --------------------------------------------------------------------- T5
def corregir_errores_logicos(df, nodos, bit):
    """T5 · Reglas de negocio que un dato válido debe cumplir."""
    out = df.copy()
    # a) cierre antes de apertura: los campos se digitaron invertidos -> se intercambian
    inv = out["fecha_cierre"] < out["fecha_apertura"]
    out.loc[inv, ["fecha_apertura", "fecha_cierre"]] = out.loc[inv, ["fecha_cierre", "fecha_apertura"]].values
    out["fecha_corregida"] = inv
    bit.anotar("T5", "Fecha de cierre anterior a la apertura: se intercambian", inv.sum(), len(out))
    # b) satisfacción fuera de 1-5: no se puede saber el valor real -> NaN
    fuera = out["satisfaccion"].notna() & ~out["satisfaccion"].between(1, 5)
    out.loc[fuera, "satisfaccion"] = np.nan
    bit.anotar("T5", "Satisfacción fuera de la escala 1-5 -> NaN", fuera.sum(), len(out))
    # c) el cantón debe coincidir con el del nodo
    ref = out["nodo"].map(nodos.set_index("nodo")["canton"])
    incoherente = (ref != out["canton"]).sum()
    bit.anotar("T5", "Verificación cantón vs. nodo (0 = coherente)", incoherente, len(out))
    return out


# --------------------------------------------------------------------- T6
def marcar_atipicos(df, bit, k=1.5):
    """T6 · Atípicos en tiempo de resolución: IQR sobre log(horas) DENTRO de cada
    nivel de atención. Un ticket remoto (minutos) y una visita (días) son
    poblaciones distintas; un solo umbral global no detectaría nada.
    Se MARCAN pero no se eliminan: son tickets reales que incumplieron el SLA
    (p. ej. cierres administrativos tardíos). Borrarlos maquillaría el indicador.
    Para describir el tiempo típico se usa la mediana, robusta a estos valores."""
    out = df.copy()
    horas = (out["fecha_cierre"] - out["fecha_apertura"]).dt.total_seconds() / 3600
    out["tiempo_resolucion_h"] = horas.round(2)
    out["atipico_tiempo"] = False
    umbrales = []
    for nivel, idx in out.groupby("nivel_atencion").groups.items():
        _, lim_sup = limites_iqr(np.log(horas.loc[idx].dropna()), k=k)
        out.loc[idx, "atipico_tiempo"] = horas.loc[idx] > np.exp(lim_sup)
        umbrales.append(f"{nivel} > {np.exp(lim_sup):,.1f} h")
    bit.anotar("T6", "Atípicos marcados (se conservan): " + "; ".join(umbrales),
               out["atipico_tiempo"].sum(), len(out))
    return out


# --------------------------------------------------------------------- T7
def agregar_variables(df, nodos):
    """T7 · Variables derivadas e indicadores por ticket."""
    out = df.merge(nodos, on=["nodo", "canton"], how="left")
    ap = out["fecha_apertura"]
    out["mes"] = ap.dt.to_period("M").astype(str)
    out["semana"] = ap.dt.to_period("W-SUN").dt.start_time
    out["hora"] = ap.dt.hour
    out["turno"] = np.select([out["hora"].between(7, 14), out["hora"].between(15, 22)],
                             ["Mañana", "Tarde"], "Noche")
    out["temporada"] = np.where(ap.dt.month.isin([2, 3, 4]), "Lluvias (feb-abr)", "Seca")
    out["segmento"] = out["zona"] + " · " + out["tecnologia"]
    out["fcr"] = out["resuelto_primer_contacto"].eq("Sí")
    out["visita"] = out["nivel_atencion"].eq("Visita técnica")

    # SLA: cerrado a tiempo / fuera de tiempo; abierto y vencido = incumple; abierto en plazo = NaN
    meta = [META_SLA.get((t, z), META_SLA_OTROS[z]) for t, z in zip(out["tipo_falla"], out["zona"])]
    out["meta_sla_h"] = meta
    transcurrido = (FECHA_CORTE - ap).dt.total_seconds() / 3600
    out["cumple_sla"] = np.where(
        out["estado"].eq("Cerrado"), out["tiempo_resolucion_h"] <= out["meta_sla_h"],
        np.where(transcurrido > out["meta_sla_h"], False, np.nan))
    out["cumple_sla"] = out["cumple_sla"].astype("float")  # 1/0/NaN: permite promediar

    # Reincidencia: el cliente ya había reportado en los 30 días previos
    out = out.sort_values("fecha_apertura")
    previo = out.groupby("cliente_id")["fecha_apertura"].shift()
    out["reincidencia_30d"] = (ap.loc[out.index] - previo).dt.days.le(30)
    return out.reset_index(drop=True)


def limpiar(ruta_tickets, ruta_nodos):
    """Ejecuta T1 a T7 y devuelve (tickets_limpios, nodos, bitacora)."""
    bit = Bitacora()
    tickets, nodos = cargar(ruta_tickets, ruta_nodos)
    bit.anotar("T1", "Carga con fechas y códigos tipados", 0, len(tickets))
    df = quitar_duplicados(tickets, bit)
    df = tratar_nulos(df, bit)
    df = estandarizar_categorias(df, bit)
    df = corregir_errores_logicos(df, nodos, bit)
    df = marcar_atipicos(df, bit)
    df = agregar_variables(df, nodos)
    bit.anotar("T7", "Variables derivadas: tiempo, turno, SLA, FCR, reincidencia, segmento", 0, len(df))
    return df, nodos, bit.tabla()


def main():
    crudos, procesados = RAIZ / "data" / "crudos", RAIZ / "data" / "procesados"
    df, nodos, bitacora = limpiar(crudos / "tickets_soporte.csv", crudos / "nodos.csv")
    procesados.mkdir(parents=True, exist_ok=True)
    df.to_csv(procesados / "tickets_limpios.csv", index=False)
    nodos.to_csv(procesados / "nodos.csv", index=False)
    bitacora.to_csv(procesados / "bitacora_limpieza.csv", index=False)
    with pd.option_context("display.max_colwidth", 70, "display.width", 140):
        print(bitacora.to_string(index=False))
    print(f"\nGuardado: data/procesados/tickets_limpios.csv ({len(df):,} tickets)")


if __name__ == "__main__":
    main()
