# Soporte técnico de un ISP regional: ¿dónde se pierde el SLA y qué hacer?

Proyecto final de análisis exploratorio de datos (EDA) y dashboard en Python.
Caso: **AndesNet**, proveedor de internet ficticio con 10 nodos en Pichincha e
Imbabura (Ecuador). Periodo simulado: enero a junio de 2026.

## 1. Contexto, usuario y pregunta

**Problema de la profesión.** En el área de soporte técnico de un ISP, cada falla
reportada (*ticket*) tiene un tiempo máximo de solución comprometido con el cliente
(**SLA**). Incumplirlo genera reclamos, compensaciones y pérdida de clientes. El reto
diario no es contar tickets, sino saber **dónde y por qué se incumple el SLA** para
mover recursos limitados: técnicos, mantenimiento y capacitación.

**Usuaria.** Coordinadora de Operaciones de Soporte. Cada mes decide cómo repartir
12 técnicos de campo entre dos cuadrillas (Quito y Norte), qué nodos entran a
mantenimiento preventivo y qué refuerza en la capacitación de la mesa de ayuda.

**Pregunta de análisis.** ¿Dónde se concentran los incumplimientos de SLA y las
reincidencias en el servicio de soporte de AndesNet durante el primer semestre de 2026?

**Contexto real.** Según el módulo de equipamiento de la ENEMDU (INEC, dic. 2020),
el 60,9 % de los hogares urbanos encuestados tenía internet, frente al 34,4 % de los
rurales. En la zona rural, donde el acceso ya es escaso, la calidad del soporte pesa más.

## 2. Datos

| Archivo | Descripción |
|---|---|
| `data/crudos/tickets_soporte.csv` | 4.909 tickets × 14 columnas, **con problemas de calidad insertados** |
| `data/crudos/nodos.csv` | 10 nodos: cantón, zona, tecnología, clientes activos, cuadrilla |
| `data/procesados/tickets_limpios.csv` | 4.836 tickets limpios, con variables derivadas |
| `data/procesados/bitacora_limpieza.csv` | Cada decisión de limpieza y cuántas filas afectó |
| `data/externos/202012_multibdd_equipamiento.csv` | ENEMDU real (INEC), solo como contexto |

**Origen.** Los datos de clientes de un ISP son confidenciales y están protegidos
por la LOPDP, así que se **simularon** con `src/generar_datos.py` (semilla `2026`).
El encabezado del script documenta los 7 supuestos del modelo y los 7 problemas de
calidad insertados: duplicados, texto inconsistente, fechas invertidas, cierres
tardíos, notas fuera de escala, canal vacío y formato de plan. Los identificadores
de cliente son códigos aleatorios, sin datos personales.

El diccionario de datos completo está en el notebook (Paso 2) y en el informe técnico.

## 3. Estructura

```
proyecto-soporte-isp/
├── app.py                          # Dashboard (Streamlit + Plotly)
├── ejecutar.py                     # Pipeline: generar datos -> limpiar
├── requirements.txt                # Versiones exactas
├── data/
│   ├── crudos/                     # Salida de generar_datos.py
│   ├── procesados/                 # Salida de limpieza.py
│   └── externos/                   # ENEMDU (INEC), contexto
├── notebooks/
│   └── analisis_soporte_isp.ipynb  # EDA en 7 pasos, con T1–T8
├── src/
│   ├── generar_datos.py            # Simulación con semilla (C2)
│   ├── limpieza.py                 # T1–T7 con bitácora
│   ├── indicadores.py              # KPIs y segmentación con n (T8)
│   └── utilidades.py               # Funciones propias de limpieza/EDA
├── tests/
│   └── test_app.py                 # 7 pruebas automáticas del dashboard
└── reportes/
  └── img/                        # Gráficos generados por el notebook
```

## 4. Cómo ejecutar

Requisitos: **Python 3.11 o superior** y Git.

### Windows (PowerShell / terminal de VS Code)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
# Si aparece "la ejecución de scripts está deshabilitada", ejecuta una vez:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
python -m pip install -r requirements.txt

python ejecutar.py          # 1. genera los datos y los limpia
streamlit run app.py        # 2. abre el dashboard en http://localhost:8501
```

### macOS / Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python ejecutar.py
streamlit run app.py
```

### Notebook

Abre `notebooks/analisis_soporte_isp.ipynb`, elige el kernel de `.venv` y ejecuta
**Run All** (o `Kernel → Restart & Run All` en Jupyter). Regenera los gráficos de
`reportes/img/`.

### Pruebas

```bash
python src/utilidades.py     # pruebas de las funciones propias
python tests/test_app.py     # 7 pruebas del dashboard (filtros, grupos pequeños, etc.)
```

### Resultado esperado de `python ejecutar.py`

```
tickets_soporte.csv: 4,909 filas x 14 columnas
...
Guardado: data/procesados/tickets_limpios.csv (4,836 tickets)
```

La semilla fija garantiza exactamente los mismos datos en cualquier computador.

## 5. Método: EDA en 7 pasos

| Paso | Contenido | Técnica (T) |
|---|---|---|
| 1 | Problema, usuario y pregunta | — |
| 2 | Conocer los datos: origen, supuestos y diccionario | — |
| 3 | Calidad y limpieza | T1 carga y tipos · T2 duplicados · T3 nulos · T4 categorías · T5 errores lógicos · T6 atípicos |
| 4 | Variables derivadas y análisis univariado | T7 variables derivadas |
| 5 | Análisis bivariado | — |
| 6 | Segmentación con n por grupo | T8 segmentación y regla n < 30 |
| 7 | Conclusiones y decisiones | — |

## 6. Dashboard

`streamlit run app.py` muestra:

- **4 indicadores**: tickets, cumplimiento de SLA, reincidencia a 30 días y
  mediana de resolución. Con filtros, cada uno muestra su variación frente al total.
- **5 filtros**: periodo, zona, tecnología, nodo y tipo de falla.
- **5 pestañas**, una por paso de la historia: semáforo de decisiones, D1 · Nodos,
  D2 · Técnicos, D3 · Configuración y detalle por grupo con su n.
- **Advertencia de grupos pequeños**: todo grupo con menos de 30 tickets se marca
  con ⚠, se atenúa en los gráficos y se resalta en la tabla.

## 7. Decisiones

| # | Decisión | Evidencia | Responsable | Indicador · límite |
|---|---|---|---|---|
| D1 | Renovar los radioenlaces de los nodos críticos N-CAY-02 y N-OTA-02 | ~26 tickets/100 clientes/mes vs. ~5 en fibra urbana; 35 % de reincidencia | Jefe de Red / NOC | Tickets/100 clientes/mes > 20 → renovación (entre 10 y 20: vigilancia) |
| D2 | Reasignar 2 técnicos de la cuadrilla Quito a la cuadrilla Norte | 280 vs. 116 visitas por técnico; SLA de visitas 74 % vs. 90 % | Coordinadora de Operaciones | SLA de visitas rurales < 80 % dos semanas seguidas → refuerzo |
| D3 | Capacitar a la mesa de ayuda en diagnóstico remoto de router/WiFi | FCR 60 %; ~210 visitas evitables | Supervisor de Mesa de Ayuda | FCR en configuración: meta ≥ 75 % |

## 8. Limitaciones

Los datos son simulados: las magnitudes dependen de los supuestos del generador.
El método (limpieza, indicadores y dashboard) puede aplicarse a una exportación
real del CRM sin cambiar el código. Detalle en el informe técnico.

## 9. Declaración de uso de IA

Este proyecto se desarrolló con asistencia de **Claude (Anthropic)** para generar
y depurar código (simulación, limpieza, indicadores, visualizaciones y dashboard),
redactar el informe y estructurar el repositorio. Todo el código se ejecutó y
verificó: el notebook corre de principio a fin y el dashboard pasa 7 pruebas
automáticas. El caso de negocio se basa en la experiencia del autor como técnico
de soporte de un ISP; las decisiones, su interpretación y las conclusiones fueron
revisadas por el autor.

## Autor: Rosario Quispe