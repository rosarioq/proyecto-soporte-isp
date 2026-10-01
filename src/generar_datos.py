"""Generación SINTÉTICA de tickets de soporte técnico de un ISP regional (C2).

Empresa ficticia: "AndesNet", proveedor de internet con 10 nodos en Pichincha
e Imbabura. Periodo simulado: 1 de enero al 30 de junio de 2026.

Uso:  python src/generar_datos.py
Salidas:  data/crudos/tickets_soporte.csv   (tickets, con problemas de calidad)
          data/crudos/nodos.csv             (catálogo de nodos y clientes activos)

SUPUESTOS DEL MODELO (basados en la operación típica de soporte de un ISP)
1. Los tickets llegan por nodo y día según un proceso de Poisson. La tasa base
   es de ~4 tickets por cada 100 clientes al mes en fibra (FTTH) y ~9 en
   radioenlace; los nodos con equipos antiguos ("críticos") duplican esa tasa.
2. Temporada de lluvias en la Sierra (febrero-abril): los radioenlaces fallan
   un 35 % más (alineación de antenas, descargas) y la fibra un 10 % más.
3. El tipo de falla depende de la tecnología: en radioenlace predominan
   "Sin servicio" e "Intermitencia"; en fibra, la configuración del router/WiFi.
4. Resolución en primer contacto (FCR): alta en configuración, casi nula en
   daños físicos. Si no se resuelve, el ticket escala a soporte remoto N2 o a
   visita técnica.
5. Tiempo de resolución log-normal. Las visitas rurales tardan ~2 veces más que
   las urbanas (distancia, menos técnicos por zona); los tickets abiertos de
   noche esperan al turno siguiente; la lluvia retrasa las visitas a radioenlace.
6. Reincidencia: una fracción de clientes vuelve a reportar dentro de 30 días,
   más en intermitencia y en nodos críticos (la causa raíz no se corrigió).
7. Satisfacción (CSAT 1-5): baja con el tiempo de espera, la reincidencia y la
   visita. Solo ~60 % de clientes responde la encuesta.

PROBLEMAS DE CALIDAD INSERTADOS A PROPÓSITO (se corrigen en src/limpieza.py)
- Tickets duplicados por doble registro en el CRM (~1,5 %).
- Nombres de cantón con mayúsculas, espacios y tildes inconsistentes (~8 %).
- Fecha de cierre anterior a la de apertura por error de digitación (~0,5 %).
- Tickets cerrados administrativamente semanas después (atípicos, ~0,4 %).
- Satisfacción fuera de la escala 1-5 (valores 0 y 10, ~0,5 %).
- Canal de atención sin registrar (~1 %).
- Plan con formato inconsistente ("100 Mbps" / "100mbps").

Los identificadores de cliente son códigos aleatorios: el dataset no contiene
datos personales (nombres, cédulas, direcciones), en línea con la LOPDP.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEMILLA = 2026
INICIO, FIN = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-06-30 23:59:59")

RAIZ = Path(__file__).resolve().parent.parent
DIR_CRUDOS = RAIZ / "data" / "crudos"

# nodo, cantón, zona, tecnología, clientes activos, crítico, cuadrilla
NODOS = [
    ("N-QTO-01", "Quito", "Urbana", "FTTH", 3200, False, "Quito"),
    ("N-QTO-02", "Quito", "Urbana", "FTTH", 2800, False, "Quito"),
    ("N-QTO-03", "Quito", "Urbana", "FTTH", 1900, False, "Quito"),
    ("N-MEJ-01", "Mejía", "Rural", "FTTH", 520, False, "Quito"),
    ("N-CAY-01", "Cayambe", "Urbana", "FTTH", 900, False, "Norte"),
    ("N-CAY-02", "Cayambe", "Rural", "Radioenlace", 450, True, "Norte"),
    ("N-PMQ-01", "Pedro Moncayo", "Rural", "Radioenlace", 300, False, "Norte"),
    ("N-IBA-01", "Ibarra", "Urbana", "FTTH", 1600, False, "Norte"),
    ("N-OTA-01", "Otavalo", "Urbana", "FTTH", 700, False, "Norte"),
    ("N-OTA-02", "Otavalo", "Rural", "Radioenlace", 380, True, "Norte"),
]
TECNICOS = {"Quito": [f"T{i:02d}" for i in range(1, 9)],     # 8 técnicos
            "Norte": [f"T{i:02d}" for i in range(9, 13)]}     # 4 técnicos

TIPOS = ["Sin servicio", "Lentitud", "Intermitencia", "Configuración router/WiFi",
         "Daño físico (cable/antena)", "Equipo dañado"]
P_TIPO = {"FTTH":        [.18, .22, .15, .30, .10, .05],
          "Radioenlace": [.28, .18, .28, .14, .07, .05]}
P_FCR = dict(zip(TIPOS, [.20, .50, .30, .58, .02, .05]))     # resolución 1er contacto
P_VISITA = dict(zip(TIPOS, [.70, .45, .60, .50, .95, .90]))  # si no hubo FCR
P_REINC = dict(zip(TIPOS, [.10, .08, .22, .10, .06, .04]))


def _hora_apertura(rng, n):
    """Horas del día con picos en la mañana y en la noche (uso residencial)."""
    pesos = np.array([1, .6, .4, .3, .3, .5, 1, 2, 4, 5, 5, 4.5,
                      4, 3.5, 3.5, 3.5, 3.5, 4, 5, 6, 6, 5, 3.5, 2])
    return rng.choice(24, n, p=pesos / pesos.sum()) + rng.random(n)


def _turno(hora):
    return np.select([(hora >= 7) & (hora < 15), (hora >= 15) & (hora < 23)],
                     ["Mañana", "Tarde"], "Noche")


def _simular_tickets(rng, nodos):
    filas = []
    dias = pd.date_range(INICIO, FIN.normalize(), freq="D")
    lluvia = dias.month.isin([2, 3, 4])
    for _, nd in nodos.iterrows():
        base_mes = (.04 if nd.tecnologia == "FTTH" else .09) * (2 if nd.critico else 1)
        estacion = np.where(lluvia, 1.35 if nd.tecnologia == "Radioenlace" else 1.10, 1.0)
        n_dia = rng.poisson(nd.clientes_activos * base_mes / 30 * estacion)
        fechas = np.repeat(dias.values, n_dia)
        n = len(fechas)
        p_tipo = np.array(P_TIPO[nd.tecnologia])
        if nd.critico:  # equipos antiguos: más caídas e intermitencia
            p_tipo = p_tipo * np.array([1.6, 1, 1.4, .6, 1, 1.2])
        filas.append(pd.DataFrame({
            "fecha": fechas, "hora": _hora_apertura(rng, n),
            "nodo": nd.nodo, "tipo_falla": rng.choice(TIPOS, n, p=p_tipo / p_tipo.sum()),
            "cliente_id": [f"C{nd.nodo[-6:-3]}{c:05d}"
                           for c in rng.integers(1, nd.clientes_activos + 1, n)],
        }))
    t = pd.concat(filas, ignore_index=True)

    # Reincidencias: el mismo cliente vuelve a reportar dentro de 30 días
    p = t["tipo_falla"].map(P_REINC) * np.where(t["nodo"].isin(nodos.query("critico").nodo), 1.8, 1)
    orig = t[rng.random(len(t)) < p].copy()
    orig["fecha"] = orig["fecha"] + pd.to_timedelta(rng.integers(2, 30, len(orig)), unit="D")
    orig["hora"] = _hora_apertura(rng, len(orig))
    orig["tipo_falla"] = np.where(rng.random(len(orig)) < .7, orig["tipo_falla"],
                                  rng.choice(TIPOS, len(orig)))
    t = pd.concat([t, orig[orig["fecha"] <= FIN]], ignore_index=True)
    t["apertura"] = t["fecha"] + pd.to_timedelta(t["hora"], unit="h")
    return t.sort_values("apertura").reset_index(drop=True)


def _simular_atencion(rng, t, nodos):
    n = len(t)
    t = t.merge(nodos, on="nodo", how="left")
    t["canal"] = rng.choice(["Llamada", "WhatsApp", "App", "Presencial"], n, p=[.45, .35, .15, .05])
    plan_fibra = rng.choice(["50 Mbps", "100 Mbps", "300 Mbps", "Pyme"], n, p=[.30, .45, .15, .10])
    plan_radio = rng.choice(["20 Mbps", "50 Mbps", "Pyme"], n, p=[.60, .37, .03])
    t["plan"] = np.where(t["tecnologia"] == "FTTH", plan_fibra, plan_radio)

    fcr = rng.random(n) < t["tipo_falla"].map(P_FCR)
    visita = ~fcr & (rng.random(n) < t["tipo_falla"].map(P_VISITA))
    t["nivel_atencion"] = np.select([fcr, visita], ["N1 remoto", "Visita técnica"], "N2 remoto")
    t["resuelto_primer_contacto"] = np.where(fcr, "Sí", "No")

    turno = _turno(t["hora"].values)
    lluvia = t["apertura"].dt.month.isin([2, 3, 4]).values
    mediana = np.select([fcr, ~visita], [0.4, 5.0], 16.0)
    mediana = mediana * np.where(visita & (t["zona"] == "Rural"), 2.1, 1)
    mediana = mediana + np.where(visita & (turno == "Noche"), 7, 0)
    mediana = mediana * np.where(visita & lluvia & (t["tecnologia"] == "Radioenlace"), 1.25, 1)
    mediana = mediana + np.where(visita & t["critico"], 10, 0)
    horas = np.exp(np.log(mediana) + rng.normal(0, .6, n))
    t["cierre"] = t["apertura"] + pd.to_timedelta(horas, unit="h")

    tecnico = [rng.choice(TECNICOS[c]) for c in t["cuadrilla"]]
    t["tecnico_id"] = np.where(visita, tecnico, None)

    # Satisfacción depende de la espera, la visita y la reincidencia
    reinc = t.duplicated("cliente_id", keep="first")
    mu = (4.7 - .9 * (horas > 24) - .6 * (horas > 72) - .3 * visita
          - .5 * reinc + rng.normal(0, .7, n))
    t["satisfaccion"] = np.clip(np.round(mu), 1, 5)
    t.loc[rng.random(n) > .60, "satisfaccion"] = np.nan    # no responde la encuesta

    abierto = t["cierre"] > FIN
    t.loc[abierto, "cierre"] = pd.NaT
    t["estado"] = np.where(abierto, "Abierto", "Cerrado")
    return t


def _insertar_problemas(rng, t):
    n = len(t)
    # Cantón con formato inconsistente
    variantes = {"Quito": ["quito", "QUITO", " Quito "], "Mejía": ["Mejia", "MEJÍA", "mejía "],
                 "Cayambe": ["cayambe", "CAYAMBE "], "Pedro Moncayo": ["pedro moncayo", "Pedro  Moncayo"],
                 "Ibarra": ["ibarra", "IBARRA"], "Otavalo": ["otavalo ", "OTAVALO"]}
    idx = rng.choice(n, int(n * .08), replace=False)
    t.loc[idx, "canton"] = [rng.choice(variantes[c]) for c in t.loc[idx, "canton"]]
    # Plan sin espacio ni mayúscula
    idx = rng.choice(n, int(n * .05), replace=False)
    t.loc[idx, "plan"] = t.loc[idx, "plan"].str.replace(" Mbps", "mbps")
    # Fechas invertidas (error de digitación)
    cerr = t.index[t["cierre"].notna()]
    idx = rng.choice(cerr, int(n * .005), replace=False)
    t.loc[idx, ["apertura", "cierre"]] = t.loc[idx, ["cierre", "apertura"]].values
    # Cierres administrativos tardíos (atípicos)
    idx = rng.choice(cerr, int(n * .004), replace=False)
    t.loc[idx, "cierre"] = t.loc[idx, "apertura"] + pd.to_timedelta(rng.integers(20, 61, len(idx)), unit="D")
    t.loc[t["cierre"] > FIN, "cierre"] = FIN
    # Satisfacción fuera de escala y canal sin registrar
    con_nota = t.index[t["satisfaccion"].notna()]
    idx = rng.choice(con_nota, int(n * .005), replace=False)
    t.loc[idx, "satisfaccion"] = rng.choice([0, 10], len(idx))
    t.loc[rng.choice(n, int(n * .01), replace=False), "canal"] = np.nan
    # Duplicados por doble registro en el CRM
    dup = t.sample(frac=.015, random_state=SEMILLA)
    return pd.concat([t, dup]).sort_values("apertura", kind="stable").reset_index(drop=True)


def generar(semilla: int = SEMILLA):
    """Devuelve (tickets, nodos) como DataFrames crudos."""
    rng = np.random.default_rng(semilla)
    nodos = pd.DataFrame(NODOS, columns=["nodo", "canton", "zona", "tecnologia",
                                         "clientes_activos", "critico", "cuadrilla"])
    t = _simular_tickets(rng, nodos)
    t = _simular_atencion(rng, t, nodos)
    t["id_ticket"] = [f"TK-{i:06d}" for i in range(1, len(t) + 1)]
    t = _insertar_problemas(rng, t)
    fmt = "%Y-%m-%d %H:%M"
    t["fecha_apertura"] = t["apertura"].dt.strftime(fmt)
    t["fecha_cierre"] = t["cierre"].dt.strftime(fmt)
    columnas = ["id_ticket", "fecha_apertura", "fecha_cierre", "estado", "cliente_id",
                "canton", "nodo", "plan", "canal", "tipo_falla", "nivel_atencion",
                "resuelto_primer_contacto", "tecnico_id", "satisfaccion"]
    return t[columnas], nodos


def main():
    tickets, nodos = generar()
    DIR_CRUDOS.mkdir(parents=True, exist_ok=True)
    tickets.to_csv(DIR_CRUDOS / "tickets_soporte.csv", index=False, encoding="utf-8")
    nodos.to_csv(DIR_CRUDOS / "nodos.csv", index=False, encoding="utf-8")
    print(f"tickets_soporte.csv: {tickets.shape[0]:,} filas x {tickets.shape[1]} columnas")
    print(f"nodos.csv: {nodos.shape[0]} nodos, {nodos['clientes_activos'].sum():,} clientes")


if __name__ == "__main__":
    main()
