"""
Descarga MOD11A1 (LST_Day_1km) y MOD13Q1 (NDVI, EVI) desde AppEEARS para los
puntos de Coordenadas/Coordenadas_SanMartin_<AÑO>.csv, usando la API de AppEEARS.

AppEEARS acepta como máximo 1000 coordenadas por solicitud, así que cada año se
divide en partes de hasta 1000 puntos y se envía una solicitud por parte y
producto. El script guarda su avance en appeears_tareas.json: si se corta
(o lo cierras), vuelve a ejecutarlo y continúa donde quedó, sin repetir envíos.

Uso (desde la raíz del repositorio):
    pip install requests pandas
    python descargar_appeears.py

Pide usuario y contraseña de NASA Earthdata (los mismos de la web de AppEEARS).
También puedes definir las variables de entorno EARTHDATA_USER y EARTHDATA_PASS.

Los resultados (*-results.csv) quedan en MOD11A1/ y MOD13Q1/, que es donde
los lee unificacion-de-datos.ipynb.
"""

import getpass
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

API = 'https://appeears.earthdatacloud.nasa.gov/api'
ANIO_INICIO, ANIO_FIN = 2000, 2024
MAX_PUNTOS = 1000
DIAS_PREVIOS_DESDE = '11-15'          # inicio: 15 de noviembre del año anterior
INICIO_MOD11A1 = '02-24-2000'         # primer día disponible del producto
ESPERA_SONDEO = 120                   # segundos entre revisiones de estado
ARCHIVO_ESTADO = Path('appeears_tareas.json')

PRODUCTOS = {
    'MOD11A1': {'carpeta': Path('MOD11A1'),
                'capas': [('MOD11A1.061', 'LST_Day_1km')]},
    'MOD13Q1': {'carpeta': Path('MOD13Q1'),
                'capas': [('MOD13Q1.061', '_250m_16_days_NDVI'),
                          ('MOD13Q1.061', '_250m_16_days_EVI')]},
}


# ---------------------------------------------------------------- utilidades
def cargar_estado():
    if ARCHIVO_ESTADO.exists():
        return json.loads(ARCHIVO_ESTADO.read_text(encoding='utf-8'))
    return {}


def guardar_estado(estado):
    ARCHIVO_ESTADO.write_text(json.dumps(estado, indent=2), encoding='utf-8')


def pedir(metodo, url, token=None, reintentos=5, **kw):
    """Petición HTTP con reintentos ante errores de red o saturación (429/5xx)."""
    headers = kw.pop('headers', {})
    if token:
        headers['Authorization'] = f'Bearer {token}'
    for i in range(reintentos):
        try:
            r = requests.request(metodo, url, headers=headers, timeout=300, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f'{r.status_code}: {r.text[:200]}')
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if i == reintentos - 1:
                raise
            espera = 30 * (i + 1)
            print(f'   aviso: {e}. Reintento en {espera}s')
            time.sleep(espera)


def login():
    usuario = os.environ.get('EARTHDATA_USER') or input('Usuario Earthdata: ')
    clave = os.environ.get('EARTHDATA_PASS') or getpass.getpass('Contraseña: ')
    r = requests.post(f'{API}/login', auth=(usuario, clave), timeout=60)
    if r.status_code != 200:
        sys.exit(f'No se pudo iniciar sesión ({r.status_code}): {r.text[:200]}')
    return r.json()['token']


def fechas_de(anio, producto):
    if anio == 2000:
        desde = INICIO_MOD11A1 if producto == 'MOD11A1' else '02-18-2000'
    else:
        desde = f'{DIAS_PREVIOS_DESDE}-{anio - 1}'
    return desde, f'12-31-{anio}'


# ------------------------------------------------------- 1. armar solicitudes
def planificar(estado):
    """Crea en el estado una entrada por (año, producto, parte) que aún no exista."""
    for anio in range(ANIO_INICIO, ANIO_FIN + 1):
        archivo = Path('Coordenadas') / f'Coordenadas_SanMartin_{anio}.csv'
        if not archivo.exists():
            sys.exit(f'Falta {archivo}. Ejecuta antes unificacion-de-datos.ipynb '
                     f'hasta la celda que genera las coordenadas.')
        pts = pd.read_csv(archivo)
        partes = [pts.iloc[i:i + MAX_PUNTOS]
                  for i in range(0, len(pts), MAX_PUNTOS)]
        for producto in PRODUCTOS:
            for k, parte in enumerate(partes):
                clave = f'{anio}_{producto}_p{k:02d}'
                if clave in estado:
                    continue
                desde, hasta = fechas_de(anio, producto)
                estado[clave] = {
                    'anio': anio, 'producto': producto, 'parte': k,
                    'desde': desde, 'hasta': hasta,
                    'coordenadas': [
                        {'id': str(int(f.id)), 'category': str(f.category),
                         'latitude': float(f.latitude),
                         'longitude': float(f.longitude)}
                        for f in parte.itertuples()],
                    'task_id': None, 'estado': 'sin_enviar', 'descargado': False,
                }
    guardar_estado(estado)


# --------------------------------------------------------------- 2. enviar
def enviar(estado, token):
    pendientes = [c for c, t in estado.items() if t['task_id'] is None]
    print(f'Solicitudes por enviar: {len(pendientes)}')
    for clave in pendientes:
        t = estado[clave]
        cuerpo = {
            'task_type': 'point',
            'task_name': f"SM_{clave}",
            'params': {
                'dates': [{'startDate': t['desde'], 'endDate': t['hasta']}],
                'layers': [{'product': p, 'layer': l}
                           for p, l in PRODUCTOS[t['producto']]['capas']],
                'coordinates': t['coordenadas'],
            },
        }
        try:
            r = pedir('POST', f'{API}/task', token, json=cuerpo, reintentos=2)
        except requests.RequestException as e:
            # Por ejemplo, si AppEEARS limita las tareas en cola por usuario.
            # Se reintentará en la siguiente vuelta del sondeo.
            detalle = getattr(getattr(e, 'response', None), 'text', '') or str(e)
            print(f'   no se pudo enviar {clave}: {detalle[:300]}')
            print('   Se seguirá intentando en la próxima revisión.')
            return
        t['task_id'] = r.json()['task_id']
        t['estado'] = 'enviada'
        guardar_estado(estado)            # se guarda tras cada envío
        print(f"   enviada {clave} ({len(t['coordenadas'])} puntos, "
              f"{t['desde']} a {t['hasta']})")
        time.sleep(2)


# ----------------------------------------------- 3. esperar y descargar
def descargar_tarea(t, token):
    carpeta = PRODUCTOS[t['producto']]['carpeta']
    carpeta.mkdir(exist_ok=True)
    archivos = pedir('GET', f"{API}/bundle/{t['task_id']}", token).json()['files']
    resultados = [f for f in archivos if f['file_name'].endswith('-results.csv')]
    if not resultados:
        raise RuntimeError(f"La tarea {t['task_id']} no tiene *-results.csv")
    for f in resultados:
        destino = carpeta / Path(f['file_name']).name
        r = pedir('GET', f"{API}/bundle/{t['task_id']}/{f['file_id']}", token,
                  stream=True, allow_redirects=True)
        with open(destino, 'wb') as fh:
            for bloque in r.iter_content(chunk_size=1 << 20):
                fh.write(bloque)
        print(f'   descargado {destino}')


def esperar_y_descargar(estado, token):
    while True:
        faltan = [c for c, t in estado.items() if not t['descargado']]
        if not faltan:
            break

        # Una sola petición para conocer el estado de todas las tareas del usuario
        lista = pedir('GET', f'{API}/task', token).json()
        estados_api = {x['task_id']: x['status'] for x in lista}

        for clave in faltan:
            t = estado[clave]
            st = estados_api.get(t['task_id'], t['estado'])
            t['estado'] = st
            if st == 'done':
                descargar_tarea(t, token)
                t['descargado'] = True
            elif st == 'error':
                print(f"   ERROR en {clave} (task {t['task_id']}). Se reenviará.")
                t['task_id'] = None
                t['estado'] = 'sin_enviar'
        guardar_estado(estado)

        if any(t['task_id'] is None for t in estado.values()):
            enviar(estado, token)

        conteo = pd.Series([t['estado'] for t in estado.values()]).value_counts()
        listas = sum(t['descargado'] for t in estado.values())
        print(f"[{time.strftime('%H:%M')}] descargadas {listas}/{len(estado)} · "
              + ' · '.join(f'{k}: {v}' for k, v in conteo.items()))
        if listas < len(estado):
            time.sleep(ESPERA_SONDEO)


# ------------------------------------------------------------------- main
if __name__ == '__main__':
    estado = cargar_estado()
    planificar(estado)
    total = len(estado)
    print(f'Total de solicitudes: {total} '
          f'({total // len(PRODUCTOS)} por producto)')

    token = login()
    enviar(estado, token)
    print('\nTodas enviadas. Esperando a que AppEEARS las procese '
          '(puede tardar horas). Puedes cerrar el script y volver a '
          'ejecutarlo luego: retoma desde appeears_tareas.json.\n')
    esperar_y_descargar(estado, token)
    print('\nListo. Ya puedes ejecutar unificacion-de-datos.ipynb completo.')
