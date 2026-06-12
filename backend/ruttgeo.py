"""Koordinathantering för ruttplanering.

SWEREF99 TM (EPSG:3006) -> WGS84 (EPSG:4326) via Gauss-Conformal/Krüger-projektion
enligt Lantmäteriets parametrar. Ingen extern dependency (pyproj behövs ej).
"""
import math


def sweref99tm_to_wgs84(n, e):
    """Transformera SWEREF99 TM (northing n, easting e) -> (lat, lon) i WGS84-grader."""
    # GRS 80
    axis = 6378137.0
    flattening = 1.0 / 298.257222101
    central_meridian = 15.00
    scale = 0.9996
    false_northing = 0.0
    false_easting = 500000.0

    e2 = flattening * (2.0 - flattening)
    n_ = flattening / (2.0 - flattening)
    a_roof = axis / (1.0 + n_) * (1.0 + n_**2 / 4.0 + n_**4 / 64.0)

    delta1 = n_ / 2.0 - 2.0 * n_**2 / 3.0 + 37.0 * n_**3 / 96.0 - n_**4 / 360.0
    delta2 = n_**2 / 48.0 + n_**3 / 15.0 - 437.0 * n_**4 / 1440.0
    delta3 = 17.0 * n_**3 / 480.0 - 37.0 * n_**4 / 840.0
    delta4 = 4397.0 * n_**4 / 161280.0

    a_star = e2 + e2**2 + e2**3 + e2**4
    b_star = -(7.0 * e2**2 + 17.0 * e2**3 + 30.0 * e2**4) / 6.0
    c_star = (224.0 * e2**3 + 889.0 * e2**4) / 120.0
    d_star = -(4279.0 * e2**4) / 1260.0

    deg2rad = math.pi / 180.0
    lambda_zero = central_meridian * deg2rad
    xi = (n - false_northing) / (scale * a_roof)
    eta = (e - false_easting) / (scale * a_roof)

    xi_prim = (xi
               - delta1 * math.sin(2.0 * xi) * math.cosh(2.0 * eta)
               - delta2 * math.sin(4.0 * xi) * math.cosh(4.0 * eta)
               - delta3 * math.sin(6.0 * xi) * math.cosh(6.0 * eta)
               - delta4 * math.sin(8.0 * xi) * math.cosh(8.0 * eta))
    eta_prim = (eta
                - delta1 * math.cos(2.0 * xi) * math.sinh(2.0 * eta)
                - delta2 * math.cos(4.0 * xi) * math.sinh(4.0 * eta)
                - delta3 * math.cos(6.0 * xi) * math.sinh(6.0 * eta)
                - delta4 * math.cos(8.0 * xi) * math.sinh(8.0 * eta))

    phi_star = math.asin(math.sin(xi_prim) / math.cosh(eta_prim))
    delta_lambda = math.atan(math.sinh(eta_prim) / math.cos(xi_prim))
    lon_radian = lambda_zero + delta_lambda
    lat_radian = (phi_star + math.sin(phi_star) * math.cos(phi_star)
                  * (a_star
                     + b_star * math.sin(phi_star)**2
                     + c_star * math.sin(phi_star)**4
                     + d_star * math.sin(phi_star)**6))
    return lat_radian / deg2rad, lon_radian / deg2rad


def _tal(v):
    """Tolka ett koordinatvärde (hanterar svensk decimalkomma och blanksteg)."""
    if v is None:
        return None
    s = str(v).strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
    if s == '':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _ar_northing(v):
    return 6000000.0 <= v <= 7800000.0


def _ar_easting(v):
    return 150000.0 <= v <= 1000000.0


def normalisera_koordinat(a, b):
    """Tolka två råa koordinatvärden (lat/lon-kolumnerna) till WGS84.

    Returnerar (lat, lon, kalla) där kalla = 'wgs84' | 'sweref99tm',
    eller (None, None, orsak) där orsak = 'saknas' | 'ogiltig' | 'utanfor_omrade'.
    Autodetekterar koordinatsystem och hanterar omkastad N/E-ordning.
    """
    fa, fb = _tal(a), _tal(b)
    if fa is None or fb is None:
        return None, None, 'saknas'
    # WGS84 (grader)
    if abs(fa) <= 90.0 and abs(fb) <= 180.0 and not (_ar_northing(fa) or _ar_northing(fb)):
        return fa, fb, 'wgs84'
    # SWEREF99 TM – lista ut vilket som är northing (6.0–7.8 M) och easting (150–1000 k)
    if _ar_northing(fa) and _ar_easting(fb):
        lat, lon = sweref99tm_to_wgs84(fa, fb)
        return lat, lon, 'sweref99tm'
    if _ar_northing(fb) and _ar_easting(fa):
        lat, lon = sweref99tm_to_wgs84(fb, fa)
        return lat, lon, 'sweref99tm'
    return None, None, 'utanfor_omrade'
