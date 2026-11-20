"""Analiza la producción de hidrocarburos y la participación de YPF.

Genera gráficos + un informe HTML con la pregunta central:
¿creció más el gas o el petróleo, y YPF ganó o perdió terreno?

Entradas (las baja descargar_datos.py):
  datos/produccion_total.csv
  datos/ypf_produccion.csv
  datos/otros_productores.csv
  datos/ingresos.csv

Salidas:
  datos/hidrocarburos_procesados.csv
  datos/resumen.json
  graficos/*.png
  index.html

Ejecutar con:  python analisis.py
"""
import json
import math
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # sin ventana: guarda PNG directo
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

BASE = Path(__file__).resolve().parent
DATOS = BASE / "datos"
GRAFICOS = BASE / "graficos"

MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

AZUL = "#0f172a"
VERDE = "#0f766e"
CELESTE = "#0891b2"
DORADO = "#d97706"
ROJO = "#b45309"
GRIS = "#64748b"
GRIS_CLARO = "#cbd5e1"

# Columna del CSV -> nombre legible en el informe.
PRODUCTORES = {
    "part_ypf": "YPF",
    "part_total_austral": "Total Austral",
    "part_pluspetrol": "Pluspetrol",
    "part_resto": "Resto de productores",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.titlecolor": AZUL,
    "axes.labelsize": 10.5,
    "axes.edgecolor": "#cbd5e1",
    "axes.labelcolor": GRIS,
    "xtick.color": GRIS,
    "ytick.color": GRIS,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


# ---------- Formatos en español ----------
def num(valor, decimales=0):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(valor, decimales=1):
    return f"{num(valor, decimales)}%"


def usd(valor, decimales=0):
    return f"US$ {num(valor, decimales)}"


def mes_corto(fecha):
    return f"{MESES[fecha.month - 1]} {fecha.year}"


def mes_largo(fecha):
    return f"{MESES_LARGOS[fecha.month - 1]} de {fecha.year}"


def formato_porcentaje(valor, _posicion=None):
    return f"{valor:,.0f}".replace(",", ".") + "%"


def formato_millones(valor, _posicion=None):
    return f"{valor:,.0f}".replace(",", ".")


def guardar(fig, nombre):
    fig.text(0.99, 0.005,
             "Fuente: Secretaría de Energía y Balance Cambiario (datos.gob.ar)",
             ha="right", va="bottom", fontsize=8, color=GRIS)
    fig.savefig(GRAFICOS / nombre, dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------- Datos ----------
def cargar():
    rutas = {
        "total": DATOS / "produccion_total.csv",
        "ypf": DATOS / "ypf_produccion.csv",
        "otros": DATOS / "otros_productores.csv",
        "ingresos": DATOS / "ingresos.csv",
    }
    for nombre, ruta in rutas.items():
        if not ruta.exists():
            raise SystemExit(
                f"Falta {ruta}. Ejecutá primero python descargar_datos.py."
            )

    total = pd.read_csv(rutas["total"], parse_dates=["fecha"]).sort_values("fecha").reset_index(drop=True)
    ypf = pd.read_csv(rutas["ypf"], parse_dates=["fecha"]).sort_values("fecha").reset_index(drop=True)
    otros = pd.read_csv(rutas["otros"], parse_dates=["fecha"]).sort_values("fecha").reset_index(drop=True)
    ingresos = pd.read_csv(rutas["ingresos"], parse_dates=["fecha"]).sort_values("fecha").reset_index(drop=True)

    # --- CONVERSIÓN DE UNIDADES: acá está la trampa del proyecto ---
    # Crudo total: miles de m³ | YPF crudo: m³ -> dividir por 1000.
    # Gas total: millones de m³ | YPF/empresas: miles de m³ -> dividir por 1000.
    ypf["ypf_crudo_miles"] = ypf["ypf_crudo"] / 1000.0
    ypf["ypf_gas_millones"] = ypf["ypf_gas"] / 1000.0
    otros["total_austral_millones"] = otros["total_austral_gas"] / 1000.0
    otros["pluspetrol_millones"] = otros["pluspetrol_gas"] / 1000.0

    # Matriz energética: cada serie se indexa desde su propio primer dato.
    # No descartamos meses: el crudo termina antes que el gas y queremos mostrar
    # cada serie hasta su fecha real, con las fechas escritas en el informe.
    matriz = total[["fecha", "crudo_total", "gas_total"]].copy()
    if len(matriz) < 24:
        raise SystemExit("No hay suficientes meses para analizar.")
    base_crudo = matriz["crudo_total"].dropna().iloc[0]
    base_gas = matriz["gas_total"].dropna().iloc[0]
    matriz["indice_crudo"] = matriz["crudo_total"] / base_crudo * 100
    matriz["indice_gas"] = matriz["gas_total"] / base_gas * 100
    matriz["anio"] = matriz["fecha"].dt.year

    # Crudo: total contra YPF.
    crudo = (
        total[["fecha", "crudo_total"]]
        .merge(ypf[["fecha", "ypf_crudo_miles"]], on="fecha", how="inner")
        .dropna()
        .reset_index(drop=True)
    )
    crudo["part_ypf"] = crudo["ypf_crudo_miles"] / crudo["crudo_total"] * 100
    crudo["part_resto"] = 100 - crudo["part_ypf"]

    # Gas: total contra YPF y los dos productores con serie mensual pública.
    gas = (
        total[["fecha", "gas_total"]]
        .merge(ypf[["fecha", "ypf_gas_millones"]], on="fecha", how="inner")
        .merge(otros[["fecha", "total_austral_millones", "pluspetrol_millones"]],
               on="fecha", how="inner")
        .dropna()
        .reset_index(drop=True)
    )
    gas["part_ypf"] = gas["ypf_gas_millones"] / gas["gas_total"] * 100
    gas["part_total_austral"] = gas["total_austral_millones"] / gas["gas_total"] * 100
    gas["part_pluspetrol"] = gas["pluspetrol_millones"] / gas["gas_total"] * 100
    # "Resto" es un residual: total menos las tres empresas informadas.
    gas["part_resto"] = 100 - (
        gas["part_ypf"] + gas["part_total_austral"] + gas["part_pluspetrol"]
    )

    # Ingresos en dólares. Media móvil de 12 meses para sacar el ruido mensual.
    for columna in ("cobros_petroleo", "exportaciones_hidrocarburos"):
        ingresos[f"{columna}_ma12"] = ingresos[columna].rolling(12, min_periods=12).mean()

    return matriz, crudo, gas, ingresos


def _cambio(serie, columna):
    validos = serie.dropna(subset=[columna])
    if len(validos) < 2:
        return {}
    primero, ultimo = validos.iloc[0], validos.iloc[-1]
    return {
        "desde": primero["fecha"].strftime("%d/%m/%Y"),
        "hasta": ultimo["fecha"].strftime("%d/%m/%Y"),
        "inicio": primero[columna],
        "fin": ultimo[columna],
        "variacion": (ultimo[columna] / primero[columna] - 1) * 100,
        "diferencia": ultimo[columna] - primero[columna],
    }


def calcular_resumen(matriz, crudo, gas, ingresos):
    ultima_matriz = matriz.iloc[-1]
    cambios_productores = {}
    for clave, etiqueta in PRODUCTORES.items():
        datos = _cambio(gas, clave)
        if datos:
            cambios_productores[etiqueta] = datos

    return {
        "generado": date.today().strftime("%d/%m/%Y"),
        "matriz_desde": matriz.iloc[0]["fecha"].strftime("%d/%m/%Y"),
        "matriz_hasta": ultima_matriz["fecha"].strftime("%d/%m/%Y"),
        "matriz_meses": len(matriz),
        "crudo": _cambio(matriz, "indice_crudo"),
        "gas": _cambio(matriz, "indice_gas"),
        "crudo_part": _cambio(crudo, "part_ypf"),
        "gas_part": _cambio(gas, "part_ypf"),
        "crudo_meses": len(crudo),
        "gas_meses": len(gas),
        "productores_gas": cambios_productores,
        "cobros": _cambio(ingresos, "cobros_petroleo"),
        "exportaciones": _cambio(ingresos, "exportaciones_hidrocarburos"),
        "ultimo_cobro": mes_largo(ingresos.dropna(subset=["cobros_petroleo"]).iloc[-1]["fecha"]),
        "ultima_exportacion": mes_largo(
            ingresos.dropna(subset=["exportaciones_hidrocarburos"]).iloc[-1]["fecha"]
        ),
    }


# ---------- Gráficos ----------
def grafico_matriz(matriz, resumen):
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.plot(matriz["fecha"], matriz["indice_crudo"], color=AZUL,
            linewidth=2.2, label="Petróleo crudo")
    ax.plot(matriz["fecha"], matriz["indice_gas"], color=VERDE,
            linewidth=2.2, label="Gas natural")

    fin_gas = matriz.dropna(subset=["indice_gas"]).iloc[-1]
    fin_crudo = matriz.dropna(subset=["indice_crudo"]).iloc[-1]
    ax.scatter([fin_gas["fecha"]], [fin_gas["indice_gas"]], color=VERDE, zorder=5, s=38)
    ax.scatter([fin_crudo["fecha"]], [fin_crudo["indice_crudo"]], color=AZUL, zorder=5, s=38)
    ax.annotate(f"Gas {pct(resumen['gas']['variacion'], 0)} ({mes_corto(fin_gas['fecha'])})",
                xy=(fin_gas["fecha"], fin_gas["indice_gas"]),
                xytext=(-10, 12), textcoords="offset points", ha="right",
                fontsize=9.5, color=VERDE, fontweight="bold")
    ax.annotate(f"Crudo {pct(resumen['crudo']['variacion'], 0)} ({mes_corto(fin_crudo['fecha'])})",
                xy=(fin_crudo["fecha"], fin_crudo["indice_crudo"]),
                xytext=(-10, -20), textcoords="offset points", ha="right",
                fontsize=9.5, color=AZUL, fontweight="bold")

    ax.axhline(100, color=GRIS_CLARO, linewidth=1)
    ax.set_title("El gas creció mucho más que el petróleo", loc="left", pad=12)
    ax.set_ylabel(f"Índice {resumen['matriz_desde']} = 100")
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(matriz["fecha"].min(), matriz["fecha"].max() + pd.Timedelta(days=40))
    ax.legend(loc="upper left", frameon=False, fontsize=9.5)
    guardar(fig, "01_crudo_vs_gas.png")


def grafico_participacion_ypf(crudo, gas, resumen):
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.plot(crudo["fecha"], crudo["part_ypf"], color=AZUL,
            linewidth=2.2, label="YPF en petróleo crudo")
    ax.plot(gas["fecha"], gas["part_ypf"], color=VERDE,
            linewidth=2.2, label="YPF en gas natural")

    for serie, color in ((crudo, AZUL), (gas, VERDE)):
        ultimo = serie.iloc[-1]
        ax.scatter([ultimo["fecha"]], [ultimo["part_ypf"]], color=color, zorder=5, s=38)
        ax.annotate(f"{pct(ultimo['part_ypf'])}",
                    xy=(ultimo["fecha"], ultimo["part_ypf"]),
                    xytext=(-8, 8), textcoords="offset points", ha="right",
                    fontsize=9.5, color=color, fontweight="bold")

    ax.set_title("YPF se mantuvo en crudo pero perdió terreno en gas",
                 loc="left", pad=12)
    ax.set_ylabel("Participación de YPF en la producción total")
    ax.set_ylim(0, 60)
    ax.yaxis.set_major_formatter(FuncFormatter(formato_porcentaje))
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="lower left", frameon=False, fontsize=9.5)
    guardar(fig, "02_participacion_ypf.png")


def grafico_productores_gas(gas):
    columnas = ["part_ypf", "part_total_austral", "part_pluspetrol", "part_resto"]
    etiquetas = [PRODUCTORES[c] for c in columnas]
    colores = [VERDE, CELESTE, DORADO, GRIS_CLARO]

    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.stackplot(gas["fecha"], *(gas[c] for c in columnas),
                 labels=etiquetas, colors=colores, alpha=0.9)
    ax.set_title("Quién produjo el gas: YPF, Total Austral, Pluspetrol y el resto",
                 loc="left", pad=12)
    ax.set_ylabel("Participación de la producción total de gas")
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(FuncFormatter(formato_porcentaje))
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(gas["fecha"].min(), gas["fecha"].max())
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.28), ncol=4,
              frameon=False, fontsize=9)
    guardar(fig, "03_productores_gas.png")


def grafico_ingresos(ingresos, resumen):
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.plot(ingresos["fecha"], ingresos["cobros_petroleo"],
            color=AZUL, linewidth=0.8, alpha=0.25)
    ax.plot(ingresos["fecha"], ingresos["exportaciones_hidrocarburos"],
            color=DORADO, linewidth=0.8, alpha=0.25)
    ax.plot(ingresos["fecha"], ingresos["cobros_petroleo_ma12"],
            color=AZUL, linewidth=2.2, label="Cobros por petróleo (promedio 12 meses)")
    ax.plot(ingresos["fecha"], ingresos["exportaciones_hidrocarburos_ma12"],
            color=DORADO, linewidth=2.2,
            label="Exportaciones de hidrocarburos (promedio 12 meses)")

    ax.set_title("Los dólares del petróleo, sin deflactar", loc="left", pad=12)
    ax.set_ylabel("Millones de dólares por mes")
    ax.yaxis.set_major_formatter(FuncFormatter(formato_millones))
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(ingresos["fecha"].min(), ingresos["fecha"].max() + pd.Timedelta(days=40))
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    guardar(fig, "04_ingresos_usd.png")


def grafico_cambio_participacion(resumen):
    etiquetas = ["Petróleo crudo", "Gas natural"]
    inicio = [resumen["crudo_part"]["inicio"], resumen["gas_part"]["inicio"]]
    fin = [resumen["crudo_part"]["fin"], resumen["gas_part"]["fin"]]

    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    x = range(len(etiquetas))
    ancho = 0.32
    b1 = ax.bar([i - ancho / 2 for i in x], inicio, ancho,
                color=GRIS_CLARO, label="Inicio de la serie")
    b2 = ax.bar([i + ancho / 2 for i in x], fin, ancho,
                color=VERDE, label="Último dato")

    for barras, valores in ((b1, inicio), (b2, fin)):
        for barra, valor in zip(barras, valores):
            ax.annotate(f"{pct(valor)}",
                        xy=(barra.get_x() + barra.get_width() / 2, barra.get_height()),
                        xytext=(0, 4), textcoords="offset points",
                        ha="center", fontsize=9.5, color=AZUL, fontweight="bold")

    ax.set_xticks(list(x))
    ax.set_xticklabels(etiquetas)
    ax.set_ylabel("Participación de YPF")
    ax.set_ylim(0, max(inicio + fin) * 1.2)
    ax.yaxis.set_major_formatter(FuncFormatter(formato_porcentaje))
    ax.set_title("Participación de YPF: inicio contra hoy", loc="left", pad=12)
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    guardar(fig, "05_cambio_participacion.png")


# ---------- Informe HTML ----------
CSS = """
:root {
  --tinta: #0f172a;
  --tinta-suave: #334155;
  --gris: #64748b;
  --borde: #e2e8f0;
  --fondo: #f8fafc;
  --verde: #0f766e;
  --acento: #b45309;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: var(--tinta);
  background: #ffffff;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
.hero {
  background: linear-gradient(135deg, #0f172a 0%, #78350f 55%, #b45309 100%);
  color: #ffffff;
  padding: 72px 24px 64px;
}
.hero .contenedor { max-width: 900px; margin: 0 auto; }
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 12px;
  font-weight: 700;
  color: #fcd34d;
  margin: 0 0 16px;
}
.hero h1 {
  font-size: clamp(34px, 5.5vw, 56px);
  line-height: 1.08;
  margin: 0 0 18px;
  letter-spacing: -0.02em;
}
.hero .lead {
  font-size: clamp(17px, 2.1vw, 21px);
  color: #fde68a;
  max-width: 760px;
  margin: 0 0 26px;
}
.hero .meta { font-size: 14px; color: #d6d3d1; margin: 0; }
main { max-width: 900px; margin: 0 auto; padding: 0 24px 72px; }
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 16px;
  margin: -34px 0 48px;
  position: relative;
}
.card {
  background: #ffffff;
  border: 1px solid var(--borde);
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 12px 30px -18px rgba(15, 23, 42, 0.35);
}
.card .rotulo {
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--gris);
  font-weight: 700;
  margin: 0 0 8px;
}
.card .valor {
  font-size: clamp(24px, 3.4vw, 32px);
  font-weight: 800;
  line-height: 1.1;
  margin: 0;
  color: var(--verde);
  letter-spacing: -0.02em;
}
.card .detalle { font-size: 13px; color: var(--gris); margin: 8px 0 0; }
section { margin: 0 0 56px; }
section h2 {
  font-size: clamp(23px, 3vw, 30px);
  line-height: 1.2;
  margin: 0 0 12px;
  letter-spacing: -0.01em;
}
section p { color: var(--tinta-suave); margin: 0 0 16px; }
section p strong { color: var(--tinta); }
section ul { color: var(--tinta-suave); }
figure { margin: 24px 0 8px; }
figure img {
  width: 100%;
  height: auto;
  border: 1px solid var(--borde);
  border-radius: 12px;
  background: #ffffff;
}
figcaption { font-size: 13px; color: var(--gris); margin-top: 10px; }
.destacado {
  border-left: 4px solid var(--acento);
  background: #fffbeb;
  padding: 16px 20px;
  border-radius: 0 10px 10px 0;
  margin: 22px 0;
  color: #92400e;
  font-size: 15px;
}
.tabla-envoltorio { overflow-x: auto; margin: 20px 0; }
table { border-collapse: collapse; width: 100%; font-size: 14.5px; }
th, td { padding: 10px 14px; border-bottom: 1px solid var(--borde); text-align: left; }
th {
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--gris);
}
td.numerico, th.numerico { text-align: right; font-variant-numeric: tabular-nums; }
tbody tr:hover { background: var(--fondo); }
.metodo {
  background: var(--fondo);
  border: 1px solid var(--borde);
  border-radius: 14px;
  padding: 26px 28px;
}
.metodo h2 { font-size: 24px; }
.metodo ul { padding-left: 20px; }
.metodo li { margin-bottom: 8px; }
code {
  font-family: "Cascadia Code", Consolas, monospace;
  background: #e2e8f0;
  padding: 2px 6px;
  border-radius: 5px;
  font-size: 0.88em;
}
pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 18px 20px;
  border-radius: 10px;
  overflow-x: auto;
  font-size: 13.5px;
}
pre code { background: none; padding: 0; color: inherit; }
footer {
  border-top: 1px solid var(--borde);
  padding-top: 26px;
  color: var(--gris);
  font-size: 13.5px;
}
footer a { color: var(--acento); }
@media (max-width: 640px) {
  .hero { padding: 48px 20px 56px; }
  main { padding: 0 20px 56px; }
  .cards { margin-top: -26px; }
  section { margin-bottom: 44px; }
}
"""


def filas_productores(resumen):
    filas = []
    for etiqueta, datos in resumen["productores_gas"].items():
        filas.append(
            f'<tr><td>{etiqueta}</td>'
            f'<td class="numerico">{pct(datos["inicio"])}</td>'
            f'<td class="numerico">{pct(datos["fin"])}</td>'
            f'<td class="numerico"><strong>{pct(datos["diferencia"])}</strong></td></tr>'
        )
    return "\n".join(filas)


def generar_informe(resumen):
    hoy = resumen["generado"]
    cobros = resumen["cobros"]
    exportaciones = resumen["exportaciones"]
    gas_part = resumen["gas_part"]
    crudo_part = resumen["crudo_part"]

    contenido = f"""
<header class="hero">
  <div class="contenedor">
    <p class="eyebrow">Proyecto de análisis de datos · Energía e hidrocarburos</p>
    <h1>El gas creció, YPF se quedó:<br>quién ganó el terreno en Argentina</h1>
    <p class="lead">Treinta años de producción de petróleo y gas, la participación de YPF
    frente a otros productores y los dólares que entraron por el sector.</p>
    <p class="meta">Por Sebastián Catenacci · Fuente: Secretaría de Energía y Balance
    Cambiario vía datos.gob.ar · Crudo hasta {resumen['crudo']['hasta']} · gas hasta
    {resumen['gas']['hasta']} · Publicado: {hoy}</p>
  </div>
</header>

<main>
  <div class="cards">
    <div class="card">
      <p class="rotulo">Crecimiento del gas</p>
      <p class="valor">{pct(resumen['gas']['variacion'], 0)}</p>
      <p class="detalle">Desde {resumen['matriz_desde']}, en volumen físico</p>
    </div>
    <div class="card">
      <p class="rotulo">Crecimiento del crudo</p>
      <p class="valor">{pct(resumen['crudo']['variacion'], 0)}</p>
      <p class="detalle">Mismo período y misma base</p>
    </div>
    <div class="card">
      <p class="rotulo">YPF en petróleo</p>
      <p class="valor">{pct(crudo_part['fin'])}</p>
      <p class="detalle">Participación al {crudo_part['hasta']}</p>
    </div>
    <div class="card">
      <p class="rotulo">YPF en gas</p>
      <p class="valor">{pct(gas_part['fin'])}</p>
      <p class="detalle">Era {pct(gas_part['inicio'])} en {gas_part['desde'][-4:]}</p>
    </div>
  </div>

  <section>
    <h2>La matriz se volcó al gas</h2>
    <p>Desde {resumen['matriz_desde']}, la producción de gas natural subió
    <strong>{pct(resumen['gas']['variacion'])}</strong> (hasta {resumen['gas']['hasta']}),
    mientras que la del petróleo crudo apenas cambió
    <strong>{pct(resumen['crudo']['variacion'])}</strong> (hasta
    {resumen['crudo']['hasta']}). Cada serie se mide hasta su último mes disponible:
    los meses que se comparan son <strong>{resumen['matriz_meses']} en total</strong>,
    de series oficiales de la Secretaría de Energía.</p>
    <p>Ambas líneas empiezan en 100 para poder compararlas aunque sus unidades sean
    distintas: el crudo se mide en miles de metros cúbicos y el gas en millones.</p>
    <div class="destacado">
      Acá está la headline: en volumen, el gas creció casi siete veces más que el
      petróleo en el mismo período. No es un cambio de precios, es un cambio de qué
      se extrae.
    </div>
    <figure>
      <img src="graficos/01_crudo_vs_gas.png"
           alt="Líneas con la producción de petróleo y gas, indexadas a 100">
      <figcaption>Índice 100 = {resumen['matriz_desde']}. Volúmenes físicos, no dólares.</figcaption>
    </figure>
  </section>

  <section>
    <h2>YPF: estable en crudo, en retroceso en gas</h2>
    <p>En petróleo, YPF pasó de <strong>{pct(crudo_part['inicio'])}</strong> a
    <strong>{pct(crudo_part['fin'])}</strong> de la producción nacional: se mantuvo
    e incluso ganó un poco. En gas, en cambio, cayó de
    <strong>{pct(gas_part['inicio'])}</strong> a
    <strong>{pct(gas_part['fin'])}</strong>, una pérdida de
    <strong>{pct(abs(gas_part['diferencia']))}</strong> de participación.</p>
    <p>Es la misma empresa con dos comportamientos distintos según el hidrocarburo.
    Por eso un promedio de "producción total de YPF" escondería la historia.</p>
    <figure>
      <img src="graficos/02_participacion_ypf.png"
           alt="Participación de YPF en crudo y en gas a lo largo del tiempo">
      <figcaption>Participación de YPF sobre el total nacional de cada hidrocarburo.</figcaption>
    </figure>
  </section>

  <section>
    <h2>Quién ocupó ese lugar</h2>
    <p>El gas que dejó YPF no desapareció: lo produjeron otros. Estas son las
    participaciones de las empresas con serie mensual pública (en millones de m³
    convertidos desde miles de m³):</p>
    <div class="tabla-envoltorio">
      <table>
        <thead><tr><th>Productor</th><th class="numerico">Inicio</th>
        <th class="numerico">Último dato</th><th class="numerico">Cambio (puntos)</th></tr></thead>
        <tbody>
          {filas_productores(resumen)}
        </tbody>
      </table>
    </div>
    <p>El "resto" se calcula por diferencia entre el total nacional y las tres
    empresas informadas, así que incluye a todos los demás productores.</p>
    <figure>
      <img src="graficos/03_productores_gas.png"
           alt="Gráfico apilado con la participación de cada productor de gas">
      <figcaption>Participación porcentual en la producción total de gas natural.</figcaption>
    </figure>
  </section>

  <section>
    <h2>Los dólares, en dólares</h2>
    <p>Los cobros por petróleo del balance cambiario pasaron de
    <strong>{usd(cobros['inicio'])} millones</strong> a
    <strong>{usd(cobros['fin'])} millones</strong> por mes:
    <strong>{pct(cobros['variacion'], 0)}</strong>. Las exportaciones de gas de
    petróleo y otros hidrocarburos pasaron de {usd(exportaciones['inicio'], 1)} a
    {usd(exportaciones['fin'], 1)} millones.</p>
    <div class="destacado">
      Acá NO deflacto con el IPC: estas series están en dólares. Usar el índice de
      precios argentino sería mezclar monedas. Es el error inverso al del proyecto
      de recaudación, donde el IPC sí era el deflactor correcto.
    </div>
    <p>La línea fina es el dato mensual y la gruesa, el promedio móvil de 12 meses:
    el sector es muy volátil y el promedio ayuda a ver la tendencia.</p>
    <figure>
      <img src="graficos/04_ingresos_usd.png"
           alt="Cobros por petróleo y exportaciones de hidrocarburos en millones de dólares">
      <figcaption>Millones de dólares por mes. Línea gruesa: promedio móvil de 12 meses.</figcaption>
    </figure>
  </section>

  <section>
    <h2>En una mirada</h2>
    <p>La participación de YPF en crudo se movió de {pct(crudo_part['inicio'])} a
    {pct(crudo_part['fin'])}, mientras que en gas cayó de {pct(gas_part['inicio'])}
    a {pct(gas_part['fin'])}. El gráfico resume las dos caras de la misma empresa.</p>
    <figure>
      <img src="graficos/05_cambio_participacion.png"
           alt="Barras comparando la participación inicial y final de YPF en crudo y gas">
      <figcaption>Comparación entre el primer y el último mes disponible de cada serie.</figcaption>
    </figure>
  </section>

  <section class="metodo">
    <h2>Cómo se hizo (y dónde está la trampa)</h2>
    <p>Todo el proceso es reproducible: los datos se descargan de la API oficial y
    el informe se genera con un script de Python.</p>
    <ul>
      <li><strong>Fuentes:</strong> Secretaría de Energía (producción por empresa y
      total) y Balance Cambiario del BCRA (cobros por petróleo), vía <code>datos.gob.ar</code>.</li>
      <li><strong>Series:</strong> 8 series oficiales en 4 grupos, guardadas como CSV
      junto con sus metadatos en <code>datos/fuente.json</code>.</li>
      <li><strong>Conversiones:</strong> la producción de YPF en crudo viene en m³ y
      el total en miles de m³ (dividir por 1.000). El gas de YPF y de las otras
      empresas viene en miles de m³ y el total en millones (dividir por 1.000 otra vez).</li>
      <li><strong>Período:</strong> matriz {resumen['matriz_desde']} a
      {resumen['matriz_hasta']} ({resumen['matriz_meses']} meses);
      participaciones {gas_part['desde']} a {gas_part['hasta']}.</li>
      <li><strong>Participación:</strong> producción de la empresa ÷ producción total
      nacional × 100. Se asume que la serie total incluye a todas las empresas.</li>
      <li><strong>Actualizar:</strong> <code>python descargar_datos.py</code> y después
      <code>python analisis.py</code>. En Windows también podés hacer doble clic en
      <code>actualizar.bat</code>.</li>
    </ul>
    <p><strong>Limitaciones:</strong> las series no terminan en el mismo mes (el crudo
    total llega hasta {resumen['crudo']['hasta']} y el gas hasta {resumen['gas']['hasta']});
    por eso cada indicador informa su propia fecha y las participaciones usan solo los
    meses en común. "Cobros por petróleo" y
    "exportaciones" no son exactamente lo mismo: el primero registra entradas de
    divisas por el rubro petrolero y el segundo, ventas externas declaradas. El
    trabajo es descriptivo: no es un pronóstico ni una recomendación de inversión.</p>
  </section>

  <footer>
    <p>Hecho por <strong>Sebastián Catenacci</strong> con Python, pandas y matplotlib.
    Código y datos: <a href="https://github.com/SebaCatena/hidrocarburos-ypf">github.com/SebaCatena/hidrocarburos-ypf</a>.</p>
    <p>Datos públicos de la Secretaría de Energía y del Banco Central.
    Informe generado automáticamente desde <code>analisis.py</code>.</p>
  </footer>
</main>
"""
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gas, petróleo y YPF · Sebastián Catenacci</title>
<meta name="description" content="Análisis de la producción argentina de hidrocarburos: gas versus petróleo, participación de YPF frente a otros productores e ingresos en dólares. Datos oficiales.">
<meta property="og:title" content="El gas creció, YPF se quedó">
<meta property="og:description" content="Treinta años de hidrocarburos argentinos: el gas creció 71% y YPF perdió 15 puntos de participación. Datos oficiales y reproducibles.">
<meta property="og:type" content="article">
<meta property="og:url" content="https://sebacatena.github.io/hidrocarburos-ypf/">
<meta property="og:image" content="https://sebacatena.github.io/hidrocarburos-ypf/graficos/02_participacion_ypf.png">
<meta name="twitter:card" content="summary_large_image">
<style>{CSS}</style>
</head>
<body>
{contenido}
</body>
</html>
"""
    (BASE / "index.html").write_text(html, encoding="utf-8")


def main():
    GRAFICOS.mkdir(exist_ok=True)
    matriz, crudo, gas, ingresos = cargar()
    resumen = calcular_resumen(matriz, crudo, gas, ingresos)

    procesada = gas[
        ["fecha", "gas_total", "ypf_gas_millones", "total_austral_millones",
         "pluspetrol_millones", "part_ypf", "part_total_austral",
         "part_pluspetrol", "part_resto"]
    ].copy()
    procesada["fecha"] = procesada["fecha"].dt.strftime("%Y-%m-%d")
    procesada.to_csv(DATOS / "hidrocarburos_procesados.csv", index=False,
                     float_format="%.4f")
    with open(DATOS / "resumen.json", "w", encoding="utf-8") as archivo:
        json.dump(resumen, archivo, ensure_ascii=False, indent=2)

    grafico_matriz(matriz, resumen)
    grafico_participacion_ypf(crudo, gas, resumen)
    grafico_productores_gas(gas)
    grafico_ingresos(ingresos, resumen)
    grafico_cambio_participacion(resumen)
    generar_informe(resumen)

    print(f"Matriz: {resumen['matriz_desde']} a {resumen['matriz_hasta']} "
          f"({resumen['matriz_meses']} meses)")
    print(f"Gas: {pct(resumen['gas']['variacion'])} | "
          f"Crudo: {pct(resumen['crudo']['variacion'])}")
    print(f"YPF crudo: {pct(resumen['crudo_part']['inicio'])} -> "
          f"{pct(resumen['crudo_part']['fin'])}")
    print(f"YPF gas: {pct(resumen['gas_part']['inicio'])} -> "
          f"{pct(resumen['gas_part']['fin'])}")
    print(f"Cobros petroleo: {usd(resumen['cobros']['fin'])} M "
          f"({pct(resumen['cobros']['variacion'], 0)})")
    print(f"Informe: {BASE / 'index.html'}")
    print(f"Gráficos: {GRAFICOS}")


if __name__ == "__main__":
    main()
