"""Descarga datos de hidrocarburos desde la API oficial de datos.gob.ar.

No usa pandas: solo la biblioteca estándar. Así se pueden bajar los datos
 aunque todavía no estén instaladas las librerías de análisis.

Cuatro grupos de series, todos mensuales:

1. Producción total de crudo (miles de m³) y gas (millones de m³).
2. Producción de YPF: crudo en m³ y gas en miles de m³.
3. Producción de gas de otros productores (miles de m³).
4. Ingresos en dólares: cobros por petróleo y exportaciones de hidrocarburos.

Ojo con las unidades: no son iguales entre grupos. analisis.py se encarga
de convertirlas antes de comparar.

Fuentes: Secretaría de Energía y Balance Cambiario (BCRA), vía datos.gob.ar.
"""
import csv
import json
import urllib.request
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATOS = BASE / "datos"

# La API rechaza el User-Agent por defecto de Python (HTTP 403).
HEADERS = {
    "User-Agent": "proyecto-hidrocarburos/1.0 (portfolio; Python urllib)",
    "Accept": "application/json",
}

# Cada grupo se pide en una sola llamada y se guarda en su propio CSV.
# ID de la serie -> nombre de columna en el CSV.
GRUPOS = {
    "produccion_total.csv": {
        "363.3_PRODUCCIONUDO__28": "crudo_total",
        "364.3_PRODUCCIoNRAL__25": "gas_total",
    },
    "ypf_produccion.csv": {
        "365.3_PRODUCCION_SA__35": "ypf_crudo",
        "365.3_PRODUCCION_SA__32": "ypf_gas",
    },
    "otros_productores.csv": {
        "365.3_PRODUCCION.A.__42": "total_austral_gas",
        "365.3_PRODUCCION_SA__39": "pluspetrol_gas",
    },
    "ingresos.csv": {
        "184.1_BIENES_COBLEO_0_M_22": "cobros_petroleo",
        "75.3_GPOH_0_M_32": "exportaciones_hidrocarburos",
    },
}


def descargar(series):
    """Pide varias series en una sola llamada y devuelve (payload, url)."""
    ids = ",".join(series)
    url = f"https://apis.datos.gob.ar/series/api/series/?ids={ids}&limit=5000"
    pedido = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(pedido, timeout=60) as respuesta:
        return json.load(respuesta), url


def guardar_csv(filas, columnas, destino):
    """Escribe una matriz de filas con encabezado 'fecha' + columnas."""
    with open(destino, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["fecha"] + columnas)
        for fila in filas:
            # La API devuelve None cuando una serie no tiene dato en esa fecha.
            escritor.writerow([fila[0]] + ["" if v is None else v for v in fila[1:]])


def describir(payload, url, series):
    """Extrae los metadatos que después se publican en datos/fuente.json."""
    meta = payload.get("meta", [])
    rango = meta[0] if meta else {}
    campos = [m for m in meta[1:] if isinstance(m, dict) and "field" in m]
    unidades = {m["field"].get("id"): m["field"].get("units") for m in campos}
    dataset = campos[0].get("dataset", {}) if campos else {}

    return {
        "dataset": dataset.get("title"),
        "organismo": dataset.get("source"),
        "desde": rango.get("start_date"),
        "hasta": rango.get("end_date"),
        "url": url,
        "series": [
            {"id": clave, "columna": columna, "unidad": unidades.get(clave)}
            for clave, columna in series.items()
        ],
    }


def main():
    DATOS.mkdir(exist_ok=True)
    fuente = {"descargado": date.today().isoformat(), "grupos": {}}

    for nombre_archivo, series in GRUPOS.items():
        print(f"Descargando {nombre_archivo}...")
        payload, url = descargar(series)
        filas = payload.get("data", [])
        if not filas:
            raise SystemExit(f"La API no devolvió datos para {nombre_archivo}.")

        guardar_csv(filas, list(series.values()), DATOS / nombre_archivo)
        fuente["grupos"][nombre_archivo] = describir(payload, url, series)
        print(f"  OK: {len(filas)} filas ({filas[0][0]} a {filas[-1][0]})")

    with open(DATOS / "fuente.json", "w", encoding="utf-8") as archivo:
        json.dump(fuente, archivo, ensure_ascii=False, indent=2)

    print(f"Listo. Datos y fuentes guardados en: {DATOS}")


if __name__ == "__main__":
    main()
