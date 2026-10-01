"""Tablero de soporte técnico · AndesNet (datos sintéticos).

Uso:  streamlit run app.py
Si no existen los datos procesados, los genera automáticamente.

Estructura (sigue la historia del análisis):
  Indicadores  -> SLA y reincidencia, las dos variables de la pregunta
  Pestaña 🚦   -> semáforo: ¿se activa cada decisión?
  Pestañas D1, D2, D3 -> la evidencia de cada decisión
  Pestaña 📋   -> detalle por grupo con su n
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))
from indicadores import N_MINIMO, kpis, resumen_por, tasa_por_nodo  # noqa: E402

PROCESADOS = RAIZ / "data" / "procesados"
AZUL, NARANJA, ROJO, GRIS = "#1F6F8B", "#E07A1F", "#C0392B", "#95A5A6"

# Límites de activación de cada decisión
LIM_D1_RENOVAR = 20     # tickets por 100 clientes al mes
LIM_D1_VIGILAR = 10
LIM_D2_SLA = 80         # % de visitas rurales dentro del SLA
LIM_D3_FCR = 75         # % de resolución en primer contacto en configuración

pio.templates["andes"] = go.layout.Template(layout=dict(font=dict(size=14)))
pio.templates.default = "plotly_white+andes"
st.set_page_config(page_title="Soporte técnico · AndesNet", page_icon="📶", layout="wide")


# ----------------------------------------------------------------- datos
@st.cache_data
def cargar_datos():
    if not (PROCESADOS / "tickets_limpios.csv").exists():
        import generar_datos
        import limpieza
        generar_datos.main()
        limpieza.main()
    df = pd.read_csv(PROCESADOS / "tickets_limpios.csv", parse_dates=["fecha_apertura", "fecha_cierre"])
    nodos = pd.read_csv(PROCESADOS / "nodos.csv")
    return df, nodos


df_total, nodos = cargar_datos()

# ----------------------------------------------------------------- filtros
st.sidebar.header("Filtros")
f_min, f_max = df_total["fecha_apertura"].min().date(), df_total["fecha_apertura"].max().date()
rango = st.sidebar.date_input("Periodo", (f_min, f_max), min_value=f_min, max_value=f_max, format="DD/MM/YYYY")
inicio, fin = rango if isinstance(rango, (tuple, list)) and len(rango) == 2 else (f_min, f_max)

filtros = {
    "zona": st.sidebar.multiselect("Zona", sorted(df_total["zona"].unique()), placeholder="Todas"),
    "tecnologia": st.sidebar.multiselect("Tecnología", sorted(df_total["tecnologia"].unique()), placeholder="Todas"),
    "nodo": st.sidebar.multiselect("Nodo", sorted(df_total["nodo"].unique()), placeholder="Todos"),
    "tipo_falla": st.sidebar.multiselect("Tipo de falla", sorted(df_total["tipo_falla"].unique()), placeholder="Todos"),
}
df = df_total[df_total["fecha_apertura"].dt.date.between(inicio, fin)]
for columna, valores in filtros.items():
    if valores:
        df = df[df[columna].isin(valores)]
meses = ((pd.Timestamp(fin) - pd.Timestamp(inicio)).days + 1) / 30.44

st.sidebar.caption(f"⚠ Los grupos con menos de {N_MINIMO} tickets se marcan: "
                   "con tan pocos casos, el porcentaje no es confiable.")

# ----------------------------------------------------------------- encabezado
st.title("📶 Soporte técnico · AndesNet")
st.markdown("**¿Dónde se concentran los incumplimientos de SLA y las reincidencias en el primer semestre de 2026?**")
st.caption("Usuaria: Coordinadora de Operaciones de Soporte · Datos sintéticos generados con "
           "`src/generar_datos.py` (semilla 2026).")

if df.empty:
    st.warning("Ningún ticket cumple los filtros seleccionados. Quita algún filtro.")
    st.stop()
if len(df) < N_MINIMO:
    st.warning(f"⚠ Solo hay **{len(df)} tickets** con estos filtros (menos de {N_MINIMO}). "
               "Los indicadores no son confiables: no conviene decidir con ellos.")

# ----------------------------------------------------------------- indicadores
k, k0 = kpis(df), kpis(df_total)
hay_filtro = len(df) < len(df_total)


def variacion(clave, sufijo):
    return f"{k[clave] - k0[clave]:+.1f}{sufijo} vs. total" if hay_filtro else None


c = st.columns(4)
c[0].metric("Tickets", f"{k['tickets']:,}".replace(",", "."), help="Reportes de falla únicos, sin duplicados.")
c[1].metric("Cumplimiento de SLA", f"{k['sla_pct']:.1f} %", variacion("sla_pct", " pp"),
            help="Tickets resueltos dentro del tiempo comprometido (24, 48 o 72 h según falla y zona).")
c[2].metric("Reincidencia a 30 días", f"{k['reincidencia_pct']:.1f} %", variacion("reincidencia_pct", " pp"),
            delta_color="inverse", help="Tickets de clientes que ya habían reportado en los 30 días previos.")
c[3].metric("Mediana de resolución", f"{k['mediana_h']:.1f} h", variacion("mediana_h", " h"),
            delta_color="inverse", help="Tiempo típico. Se usa la mediana porque hay cierres muy tardíos.")


# ----------------------------------------------------------------- utilidades de gráficos
def con_n(valores, ns, fmt):
    """Etiqueta de barra con su n; ⚠ si el grupo es pequeño."""
    return [("⚠ " if n < N_MINIMO else "") + fmt.format(v) + f" (n={n})" for v, n in zip(valores, ns)]


def opacidad(ns):
    return [.35 if n < N_MINIMO else 1 for n in ns]


def aviso_pequenos(nombres, ns):
    pequenos = [f"{a} (n={n})" for a, n in zip(nombres, ns) if n < N_MINIMO]
    if pequenos:
        st.info(f"⚠ Grupos con menos de {N_MINIMO} tickets, mostrados atenuados: {', '.join(pequenos)}.")


# ----------------------------------------------------------------- pestañas
t_sem, t_d1, t_d2, t_d3, t_det = st.tabs(
    ["🚦 Semáforo", "D1 · Nodos", "D2 · Técnicos", "D3 · Configuración", "📋 Detalle por grupo"])

por_nodo = tasa_por_nodo(df, nodos, meses)
visitas = df[df["visita"]]
visitas_rurales = visitas[visitas["zona"].eq("Rural")]
config = df[df["tipo_falla"].eq("Configuración router/WiFi")]

# --- Semáforo
with t_sem:
    st.subheader("¿Se activa cada decisión?")
    st.caption("Cada decisión tiene un indicador y un límite. Se recalcula con los filtros aplicados.")
    peor = por_nodo.iloc[0]
    sla_rural = visitas_rurales["cumple_sla"].mean() * 100 if len(visitas_rurales) else None
    fcr_cfg = config["fcr"].mean() * 100 if len(config) else None
    filas = [
        ("D1 · Renovar nodos críticos de radioenlace", "Jefe de Red / NOC",
         f"Nodo con más fallas: **{peor.name}** = {peor['tickets_100_clientes_mes']:.1f} tickets por 100 clientes al mes",
         f"más de {LIM_D1_RENOVAR}", peor["tickets_100_clientes_mes"] > LIM_D1_RENOVAR, int(peor["n"])),
        ("D2 · Reasignar técnicos de Quito al Norte", "Coordinadora de Operaciones",
         f"SLA de visitas rurales = **{sla_rural:.1f} %**" if sla_rural is not None else "Sin visitas rurales",
         f"menos de {LIM_D2_SLA} %", sla_rural is not None and sla_rural < LIM_D2_SLA, len(visitas_rurales)),
        ("D3 · Capacitar a la mesa de ayuda", "Supervisor de Mesa de Ayuda",
         f"Resolución en primer contacto en configuración = **{fcr_cfg:.1f} %**" if fcr_cfg is not None
         else "Sin tickets de configuración",
         f"menos de {LIM_D3_FCR} %", fcr_cfg is not None and fcr_cfg < LIM_D3_FCR, len(config)),
    ]
    for nombre, responsable, valor, limite, activa, n in filas:
        col1, col2 = st.columns([1, 4])
        col1.markdown("### 🔴 Activar" if activa else "### 🟢 En rango")
        aviso = f" · ⚠ n < {N_MINIMO}: poco confiable" if n < N_MINIMO else ""
        col2.markdown(f"**{nombre}** · responsable: {responsable}  \n{valor} · se activa con {limite} · n = {n}{aviso}")

# --- D1 · Nodos
with t_d1:
    st.subheader("D1 · ¿Qué nodos fallan demasiado?")
    st.caption(f"**Qué mirar:** los nodos a la derecha de la línea roja ({LIM_D1_RENOVAR}) necesitan renovación. "
               f"Entre {LIM_D1_VIGILAR} y {LIM_D1_RENOVAR}, vigilancia. Se divide por clientes para comparar "
               "nodos grandes y pequeños.")
    g = por_nodo.sort_values("tickets_100_clientes_mes").reset_index()
    colores = [ROJO if t > LIM_D1_RENOVAR else NARANJA if t > LIM_D1_VIGILAR else AZUL
               for t in g["tickets_100_clientes_mes"]]
    fig = go.Figure(go.Bar(
        x=g["tickets_100_clientes_mes"], y=g["nodo"], orientation="h",
        marker=dict(color=colores, opacity=opacidad(g["n"])),
        text=con_n(g["tickets_100_clientes_mes"], g["n"], "{:.1f}"), textposition="outside", cliponaxis=False,
        customdata=g[["tecnologia", "reincidencia_pct"]],
        hovertemplate="%{y}<br>%{customdata[0]}<br>Reincidencia: %{customdata[1]:.1f} %<extra></extra>"))
    fig.add_vline(x=LIM_D1_RENOVAR, line_dash="dash", line_color=ROJO,
                  annotation_text=f"Renovar ({LIM_D1_RENOVAR})", annotation_position="top")
    fig.add_vline(x=LIM_D1_VIGILAR, line_dash="dot", line_color=GRIS,
                  annotation_text=f"Vigilar ({LIM_D1_VIGILAR})", annotation_position="top")
    fig.update_layout(height=450, xaxis_title="Tickets por 100 clientes al mes", margin=dict(r=110, t=40))
    st.plotly_chart(fig, width="stretch")
    aviso_pequenos(g["nodo"], g["n"])

# --- D2 · Técnicos
with t_d2:
    st.subheader("D2 · ¿Dónde faltan técnicos?")
    if visitas.empty:
        st.info("No hay visitas técnicas con los filtros actuales.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Visitas por técnico, por cuadrilla**")
            st.caption("**Qué mirar:** la cuadrilla Norte tiene 4 técnicos; Quito, 8.")
            carga = visitas.groupby("cuadrilla").agg(n=("id_ticket", "size"), tecnicos=("tecnico_id", "nunique"))
            carga["por_tecnico"] = carga["n"] / carga["tecnicos"]
            carga = carga.reset_index()
            fig = go.Figure(go.Bar(
                x=carga["cuadrilla"], y=carga["por_tecnico"],
                marker_color=[NARANJA if c == "Norte" else AZUL for c in carga["cuadrilla"]],
                text=[f"{v:.0f} visitas/técnico<br>{t} técnicos (n={n})"
                      for v, t, n in zip(carga["por_tecnico"], carga["tecnicos"], carga["n"])],
                textposition="outside", cliponaxis=False))
            fig.update_layout(height=420, yaxis_title="Visitas por técnico",
                              yaxis_range=[0, carga["por_tecnico"].max() * 1.35])
            st.plotly_chart(fig, width="stretch")
        with col2:
            st.markdown("**% de visitas dentro del SLA, por zona**")
            st.caption(f"**Qué mirar:** la zona bajo la línea roja ({LIM_D2_SLA} %) incumple.")
            z = resumen_por(visitas, "zona").reset_index()
            fig = go.Figure(go.Bar(
                x=z["zona"], y=z["sla_pct"],
                marker=dict(color=[NARANJA if s < LIM_D2_SLA else AZUL for s in z["sla_pct"]],
                            opacity=opacidad(z["n"])),
                text=con_n(z["sla_pct"], z["n"], "{:.0f} %"), textposition="outside", cliponaxis=False))
            fig.add_hline(y=LIM_D2_SLA, line_dash="dash", line_color=ROJO,
                          annotation_text=f"Límite {LIM_D2_SLA} %", annotation_position="top left")
            fig.update_layout(height=420, yaxis_title="% dentro del SLA", yaxis_range=[0, 110])
            st.plotly_chart(fig, width="stretch")
            aviso_pequenos(z["zona"], z["n"])

# --- D3 · Configuración
with t_d3:
    st.subheader("D3 · ¿Qué visitas se podían evitar?")
    st.caption(f"**Qué mirar:** configuración de router/WiFi casi siempre se resuelve por teléfono, "
               f"pero una parte termina en visita. Meta de resolución en primer contacto: {LIM_D3_FCR} %.")
    t = resumen_por(df, "tipo_falla").sort_values("fcr_pct").reset_index()
    etiquetas = [("⚠ " if n < N_MINIMO else "") + f"{i} (n={n})" for i, n in zip(t["tipo_falla"], t["n"])]
    fig = go.Figure([
        go.Bar(y=etiquetas, x=t["fcr_pct"], orientation="h", name="Resuelto en el primer contacto",
               marker_color=AZUL, text=[f"{v:.0f} %" for v in t["fcr_pct"]], textposition="outside"),
        go.Bar(y=etiquetas, x=t["visita_pct"], orientation="h", name="Terminó en visita técnica",
               marker_color=NARANJA, text=[f"{v:.0f} %" for v in t["visita_pct"]], textposition="outside"),
    ])
    fig.add_vline(x=LIM_D3_FCR, line_dash="dash", line_color=ROJO,
                  annotation_text=f"Meta {LIM_D3_FCR} %", annotation_position="top")
    fig.update_layout(barmode="group", height=480, xaxis_title="% de tickets", xaxis_range=[0, 110],
                      legend=dict(orientation="h", y=-.15), margin=dict(t=40))
    st.plotly_chart(fig, width="stretch")
    if len(config):
        st.markdown(f"En configuración: **{int(config['visita'].sum())} visitas** en el periodo "
                    f"(n = {len(config)} tickets).")

# --- Detalle por grupo
with t_det:
    st.subheader("Indicadores por grupo, con el n de cada uno")
    dims = {"Segmento (zona · tecnología)": "segmento", "Nodo": "nodo", "Cuadrilla": "cuadrilla",
            "Zona": "zona", "Tipo de falla": "tipo_falla"}
    elegida = st.selectbox("Agrupar por", list(dims))
    tabla = resumen_por(df, dims[elegida])[["n", "sla_pct", "reincidencia_pct", "visita_pct", "mediana_h", "advertencia"]]
    tabla.columns = ["Tickets (n)", "SLA %", "Reincidencia %", "Con visita %", "Mediana h", "Advertencia"]
    st.dataframe(tabla.style.apply(lambda fila: ["background-color: #FDEDEC" if fila["Advertencia"] else ""
                                                 for _ in fila], axis=1).format(precision=1), width="stretch")
    st.caption(f"Filas resaltadas: menos de {N_MINIMO} tickets.")
