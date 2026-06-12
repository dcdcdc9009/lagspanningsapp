"""Restider för ruttplanering.

Bygger en restidsmatris mellan punkter (depåer + ärenden):
  1. slå upp i restidscachen (rutt_restidscache)
  2. för saknade par: OSRM:s publika demoserver (endast koordinater)
  3. fallback: haversine × 1,3 vägfaktor @ 60 km/h

Endast råa koordinater skickas till OSRM – aldrig ärendedata.
Inga externa beroenden (stdlib urllib).
"""
import json
import math
import time
import threading
import urllib.request
import urllib.error

OSRM_BAS = 'https://router.project-osrm.org'
_OSRM_LOCK = threading.Lock()
_senaste_anrop = [0.0]
VAGFAKTOR = 1.3
SNITT_MS = 60_000.0 / 3600.0  # 60 km/h i meter/sekund


def haversine_m(lat1, lon1, lat2, lon2):
    """Fågelvägsavstånd i meter."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2)**2
    return 2 * R * math.asin(math.sqrt(a))


def _haversine_par(a, b):
    """(restid_sekunder, avstand_meter) via haversine-fallback."""
    d = haversine_m(a[0], a[1], b[0], b[1]) * VAGFAKTOR
    return d / SNITT_MS, d


def _osrm_get(url):
    """Hämta JSON från OSRM med timeout + max 1 anrop/sekund. None vid fel."""
    with _OSRM_LOCK:
        vanta = 1.0 - (time.time() - _senaste_anrop[0])
        if vanta > 0:
            time.sleep(vanta)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'BPV-ruttplanering'})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.load(r)
            return data
        except Exception:
            return None
        finally:
            _senaste_anrop[0] = time.time()


def _osrm_table(punkter):
    """OSRM table för alla punkter. Returnerar (dur, dist) i sek/meter eller None.

    Batchar källrader i grupper om <=80 (URL listar alla koordinater)."""
    n = len(punkter)
    coordstr = ';'.join(f'{lon},{lat}' for lat, lon in punkter)
    dur = [[None] * n for _ in range(n)]
    dist = [[None] * n for _ in range(n)]
    for start in range(0, n, 80):
        idx = list(range(start, min(start + 80, n)))
        src = ';'.join(str(i) for i in idx)
        url = (f'{OSRM_BAS}/table/v1/driving/{coordstr}'
               f'?annotations=duration,distance&sources={src}')
        data = _osrm_get(url)
        if not data or data.get('code') != 'Ok':
            return None
        durs = data.get('durations') or []
        dists = data.get('distances') or []
        for a, row in zip(idx, durs):
            for b in range(n):
                dur[a][b] = row[b]
        for a, row in zip(idx, dists):
            for b in range(n):
                dist[a][b] = row[b]
    return dur, dist


def _runda(lat, lon):
    return round(lat, 5), round(lon, 5)


def bygg_matris(conn, punkter, bara_cache=False):
    """Bygg restidsmatris (sekunder) + avståndsmatris (meter) för punkter.

    punkter: lista [(lat, lon), ...] i WGS84.
    bara_cache=True: anropa aldrig OSRM – saknade par fylls med haversine
        (används vid läsning, t.ex. för att visa sammanfattning utan nätverk).
    Returnerar (dur, dist, kalla) där kalla = 'cache' | 'osrm' | 'haversine' | 'blandad'.
    """
    n = len(punkter)
    rp = [_runda(la, lo) for la, lo in punkter]
    dur = [[0.0] * n for _ in range(n)]
    dist = [[0.0] * n for _ in range(n)]

    # 1) cache
    cmap = {}
    rader = conn.execute("SELECT from_lat,from_lon,to_lat,to_lon,restid_sekunder,avstand_meter FROM rutt_restidscache").fetchall()
    for r in rader:
        cmap[(r[0], r[1], r[2], r[3])] = (r[4], r[5])

    saknas = []
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            key = (rp[i][0], rp[i][1], rp[j][0], rp[j][1])
            if key in cmap:
                dur[i][j], dist[i][j] = cmap[key]
            else:
                saknas.append((i, j))

    if not saknas:
        return dur, dist, 'cache'

    # 2) OSRM för hela punktmängden (hoppas över vid bara_cache)
    if bara_cache:
        for (i, j) in saknas:
            sek, avs = _haversine_par(rp[i], rp[j])
            dur[i][j], dist[i][j] = sek, avs
        return dur, dist, 'blandad'

    kalla = 'osrm'
    tabell = _osrm_table(rp)
    if tabell is None:
        kalla = 'haversine'

    nya = []
    for (i, j) in saknas:
        sek = avs = None
        if tabell is not None:
            sek = tabell[0][i][j]
            avs = tabell[1][i][j]
        if sek is None or avs is None:
            sek, avs = _haversine_par(rp[i], rp[j])
            if kalla == 'osrm':
                kalla = 'blandad'  # OSRM svarade men vissa par föll tillbaka
        dur[i][j] = sek
        dist[i][j] = avs
        nya.append((rp[i][0], rp[i][1], rp[j][0], rp[j][1], int(round(sek)), int(round(avs)),
                    'osrm' if tabell is not None else 'haversine'))

    # 3) cacha
    conn.executemany(
        "INSERT OR REPLACE INTO rutt_restidscache "
        "(from_lat,from_lon,to_lat,to_lon,restid_sekunder,avstand_meter,kalla,skapad) "
        "VALUES (?,?,?,?,?,?,?,datetime('now'))", nya)
    conn.commit()
    return dur, dist, kalla
