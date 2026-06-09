import sqlite3, os, threading
from contextlib import contextmanager

DB_PATH = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'data', 'lagspanning.db')
)

# En persistent connection per tråd (undviker open/close-overhead per request)
_local = threading.local()


def _open_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -16000")  # 16 MB cache
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


@contextmanager
def get_db():
    """Återanvänder en persistent connection per tråd för att undvika nätverksoverhead."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = _open_conn()
    conn = _local.conn
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None
        raise


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    try:
        _create_tables(conn)
        conn.commit()

        tom = _is_tom(conn)
        if tom:
            from seed_data import fyll_i_startdata
            fyll_i_startdata(conn)
            conn.commit()
        else:
            _migrera(conn)

        from seed_data import fyll_egenkontroll
        fyll_egenkontroll(conn)
        conn.commit()
    finally:
        conn.close()


def _migrera(conn):
    """Kör eventuella databas-migrationer."""
    ver_rad = conn.execute(
        "SELECT varde FROM installningar WHERE nyckel='db_version'"
    ).fetchone()
    v = int(ver_rad['varde']) if ver_rad else 0

    if v < 2:
        conn.execute("DELETE FROM artikel_leverantor")
        from seed_data import fyll_nya_artiklar
        fyll_nya_artiklar(conn)
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','2')"
        )
        conn.commit()
        v = 2

    if v < 3:
        try:
            conn.execute("ALTER TABLE artiklar ADD COLUMN beskrivning TEXT")
        except Exception:
            pass
        conn.execute("""
            DELETE FROM artiklar WHERE id NOT IN (
                SELECT MIN(id) FROM artiklar GROUP BY artikelnamn, kategori_id
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','3')"
        )
        conn.commit()

    if v < 4:
        for namn in ['Kabelskarv PXE-SU5-SE01', 'Kabelskarv LJTM-W-4X035-150']:
            conn.execute("DELETE FROM artiklar WHERE artikelnamn=?", (namn,))
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','4')"
        )
        conn.commit()

    if v < 5:
        conn.execute(
            "DELETE FROM mall_inputfalt WHERE mall_id=1 AND faltnamn='ror_koppling_artikel_id'"
        )
        conn.execute(
            "DELETE FROM mall_inputfalt WHERE mall_id=1 AND faltnamn='antal_kabelander'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET etikett='Kabelskyddsband', hjalp='Välj kabelskyddsband' "
            "WHERE mall_id=1 AND faltnamn='kabelforband_artikel_id'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET alternativ=? "
            "WHERE mall_id=1 AND faltnamn='ror_artikel_id'",
            ('{"kategori_namn":"Rör och skyddsrör","filter":"skyddsrör|kabelrör|Styv PVC|Stålrör"}',)
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','5')"
        )
        conn.commit()
        v = 5

    if v < 6:
        ta_bort = [
            'ABB RK 5-fack', 'ABB RK 7-fack', 'ABB RK 10-fack', 'ABB RK 12-fack',
            'ABB Combiflex 4-fack', 'ABB Combiflex 6-fack',
            'Elmeko kabelskåp 4-fack', 'Elmeko kabelskåp 6-fack', 'Elmeko kabelskåp 8-fack',
            'Elmeko kabelskåp 10-fack', 'Elmeko kabelskåp 12-fack',
            'Ensto utomhus 4-fack', 'Ensto utomhus 6-fack',
            'Ensto utomhus 8-fack', 'Ensto utomhus 12-fack',
            'Hager kabelskåp 4-fack', 'Hager kabelskåp 6-fack', 'Hager kabelskåp 8-fack',
            'Schneider Linergy 6-fack', 'Schneider Linergy 12-fack',
            'Pehaka kabelskåp 4-fack', 'Pehaka kabelskåp 6-fack', 'Pehaka kabelskåp 8-fack',
            'Styv PVC-rör Ø50mm', 'Styv PVC-rör Ø63mm',
            'Styv PVC-rör Ø110mm', 'Styv PVC-rör Ø160mm',
            'Stålrör Ø50mm (väggenomföring)', 'Stålrör Ø100mm (väggenomföring)',
            'Rörkoppling Ø50mm', 'Rörkoppling Ø63mm', 'Rörkoppling Ø75mm',
            'Rörkoppling Ø90mm', 'Rörkoppling Ø110mm', 'Rörkoppling Ø160mm',
            'Markeringsband röd', 'Kabelskyddsnät röd', 'Kabelskyddsplatta (grön/svart)',
            'Kabelstege plast 200mm bredd', 'Kabelstege plast 300mm bredd',
            'Kabelsand', 'Betongfundament kabelskåp', 'Silikon och fogmassa',
            'Kabelgenomföring flerfack',
            'Märksystem H50 gul siffra 0-9', 'Märksystem H50 gul bokstav A-Z',
            'Märksystem H50 gul blank', 'Märksystem R5000 siffra 0-9 dekal',
        ]
        for namn in ta_bort:
            conn.execute("DELETE FROM artiklar WHERE artikelnamn=?", (namn,))

        kat = conn.execute(
            "SELECT id FROM kategorier WHERE namn='Övrigt smågods'"
        ).fetchone()
        if kat:
            kat_id = kat['id']
            max_sort = conn.execute(
                "SELECT COALESCE(MAX(sortering),49) FROM artiklar WHERE kategori_id=?",
                (kat_id,)
            ).fetchone()[0]
            r5000 = [f'Märksystem R5000 siffra {d}' for d in '0123456789'] + \
                    [f'Märksystem R5000 bokstav {c}'
                     for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
            for i, namn in enumerate(r5000):
                conn.execute(
                    "INSERT OR IGNORE INTO artiklar "
                    "(artikelnamn, kategori_id, enhet, sortering) VALUES (?,?,?,?)",
                    (namn, kat_id, 'st', max_sort + 1 + i)
                )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','6')"
        )
        conn.commit()

    if v < 7:
        conn.execute("""
            DELETE FROM artiklar WHERE id NOT IN (
                SELECT MIN(id) FROM artiklar GROUP BY artikelnamn, kategori_id
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','7')"
        )
        conn.commit()

    if v < 8:
        conn.execute(
            "UPDATE mall_inputfalt SET alternativ=? "
            "WHERE mall_id=1 AND faltnamn='kabelforband_artikel_id'",
            ('{"kategori_namn":"Övrigt smågods","filter":"kabelskydd"}',)
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','8')"
        )
        conn.commit()

    if v < 9:
        # v9: Korta schaktdjup-texten, lägg till kj.41-punkt i Mall 1
        conn.execute(
            "UPDATE mall_egenkontroll SET punkt='Schaktdjup kontrollerat' "
            "WHERE mall_id=1 AND punkt='Schaktdjup kontrollerat (min 0,7 m för markkabel)'"
        )
        # Lägg till ny punkt sist (högst sortering + 1)
        max_sort = conn.execute(
            "SELECT COALESCE(MAX(sortering), 0) FROM mall_egenkontroll WHERE mall_id=1"
        ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO mall_egenkontroll (mall_id, punkt, sortering) VALUES (?,?,?)",
            (1, 'Förlagt en kj. 41', max_sort + 1)
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','9')"
        )
        conn.commit()

    if v < 10:
        # v10: Lägg till meterfält för kabelskyddsband i Mall 1
        conn.execute("""
            INSERT OR IGNORE INTO mall_inputfalt
                (mall_id, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering)
            VALUES (1, 'kabelforband_meter', 'Kabelskyddsband (m)', 'number',
                    '{"min":0}', 'Meter kabelskyddsband', 0, 6)
        """)
        # Flytta inkl_kabelsand och inkl_markeringsband ett steg ned
        conn.execute(
            "UPDATE mall_inputfalt SET sortering=7 WHERE mall_id=1 AND faltnamn='inkl_kabelsand'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET sortering=8 WHERE mall_id=1 AND faltnamn='inkl_markeringsband'"
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','10')"
        )
        conn.commit()

    if v < 11:
        # v11: Ta bort punkter 3,4,7,10 och byt namn på punkt 6 i Mall 1
        for punkt in [
            'Kabelns förläggning godkänd av beställaren',
            'Mantelprovning utförd med godkända värden',
            'Kabelskyddsplatta monterad (vid vägkorsning o.d.)',
            'Faslikhet kontrollerad',
        ]:
            conn.execute(
                "DELETE FROM mall_egenkontroll WHERE mall_id=1 AND punkt=?", (punkt,)
            )
        conn.execute(
            "UPDATE mall_egenkontroll SET punkt='Kabelskyddsband utlagt' "
            "WHERE mall_id=1 AND punkt='Markeringsband utlagt'"
        )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','11')"
        )
        conn.commit()

    if v < 12:
        # v12: Lägg till SLD 00, SLD 000, SLE 1, SLE 2 som separata artiklar.
        # De gamla ihopslagna artiklarna raderas INTE (kan finnas i befintliga byggprotokoll).
        kat = conn.execute(
            "SELECT id FROM kategorier WHERE namn='Säkringslastfrånskiljare'"
        ).fetchone()
        if kat:
            kat_id = kat['id']
            max_sort = conn.execute(
                "SELECT COALESCE(MAX(sortering), 20) FROM artiklar WHERE kategori_id=?",
                (kat_id,)
            ).fetchone()[0]
            for i, namn in enumerate([
                'Säkringslastfrånskiljare SLD 00 500V',
                'Säkringslastfrånskiljare SLD 000 500V',
                'Säkringslastfrånskiljare SLE 1 690V',
                'Säkringslastfrånskiljare SLE 2 690V',
            ]):
                exists = conn.execute(
                    "SELECT 1 FROM artiklar WHERE artikelnamn=? AND kategori_id=?",
                    (namn, kat_id)
                ).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO artiklar (artikelnamn, kategori_id, enhet, sortering) "
                        "VALUES (?,?,?,?)",
                        (namn, kat_id, 'st', max_sort + 1 + i)
                    )
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','12')"
        )
        conn.commit()

    if v < 13:
        # v13: Fixa typo "Jordfförbindelsemätning", ta bort oanvända checkboxar i Mall 1,
        #      och säkerställ att db_version finns satt
        conn.execute("""
            UPDATE mall_egenkontroll
            SET punkt = REPLACE(punkt, 'Jordfförbindelsemätning', 'Jordförbindelsemätning')
            WHERE punkt LIKE '%Jordfförbindelsemätning%'
        """)
        for falt in ('inkl_kabelsand', 'inkl_markeringsband'):
            conn.execute(
                "DELETE FROM mall_inputfalt WHERE mall_id=1 AND faltnamn=?", (falt,)
            )
        # Säkerställ att foretagsnamn-nyckeln är konsekvent (inte foretag_namn)
        rad = conn.execute(
            "SELECT varde FROM installningar WHERE nyckel='foretag_namn'"
        ).fetchone()
        if rad:
            conn.execute(
                "INSERT OR IGNORE INTO installningar (nyckel,varde) VALUES ('foretagsnamn',?)",
                (rad['varde'],)
            )
            conn.execute("DELETE FROM installningar WHERE nyckel='foretag_namn'")
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','13')"
        )
        conn.commit()

    if v < 14:
        # v14: Lägg till konstruktioner-modulen
        try:
            conn.execute("ALTER TABLE artiklar ADD COLUMN moduler INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        # skapa_tabeller för konstruktioner körs redan via _create_tables
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','14')")
        conn.commit()

    if v < 15:
        # v15: Ersätt alla kategorier och artiklar med Excel-baserade (Byggprotokoll 1.0)
        #      samt uppdatera egenkontroll för alla mallar och inputfält-alternativ.

        # Nullställ artikel_id i rader så FK-constraint inte blockerar radering
        # (artikelnamn bevaras som text i raderna)
        conn.execute("UPDATE byggprotokoll_rader SET artikel_id = NULL")
        conn.execute("UPDATE konstruktion_rader SET artikel_id = NULL")

        # Radera allt befintligt
        conn.execute("DELETE FROM artikel_leverantor")
        conn.execute("DELETE FROM artiklar")
        conn.execute("DELETE FROM kategorier")

        # Radera befintlig egenkontroll för alla mallar
        conn.execute("DELETE FROM mall_egenkontroll")

        # Seeda nya kategorier, artiklar och egenkontroll från Excel
        from seed_data import fyll_i_startdata as _seed, fyll_egenkontroll as _egk
        # Kör bara kategori/artikel-delen (inte mallar/inställningar som redan finns)
        from seed_data import _kat, _art, _lev, _mall_falt

        kat_kabel   = _kat(conn, 'Kablar',                    1)
        kat_ansl    = _kat(conn, 'Anslutningsdon',             2)
        kat_sak     = _kat(conn, 'Säkringslastfrånskiljare',   3)
        kat_kniv    = _kat(conn, 'Knivssäkringar',             4)
        kat_kaps    = _kat(conn, 'Kapsling',                   5)
        kat_skarv   = _kat(conn, 'Kabelskarvar',               6)
        kat_skydd   = _kat(conn, 'Kabelskydd och rör',         7)
        kat_mark    = _kat(conn, 'Märkning',                   8)
        kat_ovrigt  = _kat(conn, 'Övrigt',                     9)

        for i, (namn, enhet) in enumerate([
            ('AML 4G25 1KV SV', 'm'), ('AML 4G50 1KV SV', 'm'),
            ('AML 4G95 1KV SV', 'm'), ('AML 4G150 1KV SV', 'm'),
            ('AML 4G240 1KV SV', 'm'), ('CU-LINA BELAGD 25MM²', 'm'),
        ]):
            _art(conn, namn, kat_kabel, enhet, i)

        for i, namn in enumerate([
            'ANSLUTNINGSDON ABB ADI 300 ISOLERAT',
            'ANSLUTNINGSDON ABB ADU 300 OISOLERAT',
            'ANSLUTNINGSDON ABB ADI 95 ISOLERAT',
            'ANSLUTNINGSDON ABB ADU 95 OISOLERAT',
            'ANSLUTNINGSDON AD 350',
            'ANSLUTNINGSDON PEN/PE CUZ 95',
            'ANSLUTNINGSDON PEN/PE CUZ 300',
            'ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 95',
            'ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 300',
        ]):
            _art(conn, namn, kat_ansl, 'st', i)

        for i, namn in enumerate([
            'SÄKRINGSLASTFRÅNSKILJARE SLD 00 500V',
            'SÄKRINGSLASTFRÅNSKILJARE SLD 000 500V',
            'SÄKRINGSLASTFRÅNSKILJARE SLE 1 690V',
            'SÄKRINGSLASTFRÅNSKILJARE SLE 2 690V',
            'SÄKRINGSLASFRÅNSK SLF160P',
            'SÄKRINGSLASFRÅNSK SLF250P',
            'SÄKRINGSLASFRÅNSK SLF400P',
            'SÄKRINGSLASFRÅNSK SLF630P',
        ]):
            _art(conn, namn, kat_sak, 'st', i)

        for i, namn in enumerate([
            'KNIVSSÄKRING ECO HICAP 000/10A GG 500V',
            'KNIVSSÄKRING ECO HICAP 000/16A GG 500V',
            'KNIVSSÄKRING ECO HICAP 000/25A GG 500V',
            'KNIVSSÄKRING ECO HICAP 000/35A GG 500V',
            'KNIVSSÄKRING ECO HICAP 000/50A GG 500V',
            'KNIVSSÄKRING ECO HICAP 000/63A GG 500V',
            'KNIVSSÄKRING ECO HICAP 000/80A GG 500V',
            'KNIVSSÄKRING ECO HICAP 000/100A GG 500V',
            'KNIVSSÄKRING ECO HICAP 00/125A GG 500V',
            'KNIVSSÄKRING ECO HICAP 00/160A GG 500V',
            'KNIVSSÄKRING ECO HICAP 1/63A GG 500V',
            'KNIVSSÄKRING ECO HICAP 1/80A GG 500V',
            'KNIVSSÄKRING ECO HICAP 1/100A GG 500V',
            'KNIVSSÄKRING ECO HICAP 1/125A GG 500V',
            'KNIVSSÄKRING ECO HICAP 1/160A GG 500V',
            'KNIVSSÄKRING ECO HICAP 1/200A GG 500V',
            'KNIVSSÄKRING ECO HICAP 1/250A GG 500V',
            'KNIVSSÄKRING ECO HICAP 2/100A GG 500V',
            'KNIVSSÄKRING ECO HICAP 2/125A GG 500V',
            'KNIVSSÄKRING ECO HICAP 2/160A GG 500V',
            'KNIVSSÄKRING ECO HICAP 2/200A GG 500V',
            'KNIVSSÄKRING ECO HICAP 2/250A GG 500V',
            'KNIVSSÄKRING ECO HICAP 2/315A GG 500V',
            'KNIVSSÄKRING ECO HICAP 2/355A GG 500V',
            'KOPPLINGSKNIV 1 KN 1 3ST',
        ]):
            enhet = 'sats' if 'KOPPLINGSKNIV' in namn else 'st'
            _art(conn, namn, kat_kniv, enhet, i)

        for i, (namn, moduler) in enumerate([
            ('KAPSLING CDC 420 K2', 20),
            ('KAPSLING CDC 440 K3', 40),
            ('KAPSLING CDC 460 K4', 60),
        ]):
            _art(conn, namn, kat_kaps, 'st', i, moduler=moduler)

        for i, namn in enumerate([
            'KABELSKARV 4-LED 6-50 MM² 1KV',
            'KABELSKARV 1KV AL/CU 50-95MM²',
            'KABELSKARV 1KV AL/CU 95-240MM²',
            'KABELSKARV PXE-SU5-SE01',
            'KABELSKARV LJTM-W-4X035-150',
            'KABELSKARV 1KV 95-240 MM²',
            'AVGRENINGSHYLSA C25-50',
            'ÄNDHÄTTA KALLKRYMP 16-30MM',
            'ÄNDHÄTTA KALLKRYMP 26-49MM',
            'ÄNDHÄTTA KALLKRYMP 46-84MM',
        ]):
            _art(conn, namn, kat_skarv, 'st', i)

        for i, (namn, enhet) in enumerate([
            ('KABELSKYDD PLANT 125-50', 'm'),
            ('KABELRÖR KORR UDV 160',   'm'),
            ('KABELRÖR UDV 110',         'm'),
            ('RAK-BÖJ 110 SRN',          'st'),
            ('RAK-BÖJ 160 SRN',          'st'),
        ]):
            _art(conn, namn, kat_skydd, enhet, i)

        mark_art = (
            [('MÄRKSYST R5000 SIFFRA {} DEKAL'.format(d), 'st') for d in '0123456789'] +
            [('MÄRKLIST TRANSP SKYLTHÅLL PL', 'st'), ('MARKERINGSSTÅNG KSPS 7', 'st'),
             ('E.ON KABELSKÅPSLOGO KLISTER', 'st')] +
            [('MÄRKSYSTEM H50 GUL SIFFRA {}'.format(d), 'st') for d in '0123456789'] +
            [('MÄRKSYSTEM H50 GUL BOKSTAV {}'.format(c), 'st') for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'] +
            [('MÄRKSYSTEM H50 GUL BLANK', 'st'), ('BOTTENPLATTA H50', 'st')]
        )
        for i, (namn, enhet) in enumerate(mark_art):
            _art(conn, namn, kat_mark, enhet, i)

        for i, (namn, enhet) in enumerate([
            ('HÅRDAD STÅLSPETS FS-11', 'st'), ('FRÄMRE RÖR FS-21', 'st'),
            ('FÖRLÄNGNINGSRÖR FS-31', 'st'), ('JORDLINA CCS 25 KAP', 'm'),
            ('JORDTAGSSTÅNG ELPRESS A9522463', 'st'), ('KABELSKO KRF 25-12', 'st'),
        ]):
            _art(conn, namn, kat_ovrigt, enhet, i)

        # Säkerställ att alla 4 mallar finns (kan saknas på extremt gamla installationer)
        for mid, namn in [(1,'Kabelförläggning'),(2,'Anslutning i kabelskåp'),
                          (3,'Nytt kabelskåp'),(4,'Anslutning i nätstation')]:
            conn.execute(
                "INSERT OR IGNORE INTO mallar (id,namn,beskrivning,sortering) VALUES (?,?,?,?)",
                (mid, namn, '', mid))

        # Seeda ny egenkontroll
        _egk(conn)

        # Uppdatera mall_inputfalt alternativ-JSON till nya kategorier
        upd = [
            (1, 'kabel_artikel_id',
             '{"kategori_namn":"Kablar"}'),
            (1, 'ror_artikel_id',
             '{"kategori_namn":"Kabelskydd och rör","filter":"Kabelrör|Rak-böj"}'),
            (1, 'kabelforband_artikel_id',
             '{"kategori_namn":"Kabelskydd och rör","filter":"kabelskydd"}'),
            (2, 'kabelskor_artikel_id',
             '{"kategori_namn":"Anslutningsdon"}'),
            (3, 'kabelskap_artikel_id',
             '{"kategori_namn":"Kapsling"}'),
            (3, 'kabelskor_artikel_id',
             '{"kategori_namn":"Anslutningsdon"}'),
            (4, 'kabel_artikel_id',
             '{"kategori_namn":"Kablar"}'),
            (4, 'kabelskor_artikel_id',
             '{"kategori_namn":"Anslutningsdon"}'),
        ]
        for mid, faltnamn, alternativ in upd:
            conn.execute(
                "UPDATE mall_inputfalt SET alternativ=? WHERE mall_id=? AND faltnamn=?",
                (alternativ, mid, faltnamn))

        # Uppdatera etikett för mall 2/3 kabelskor → anslutningsdon
        conn.execute(
            "UPDATE mall_inputfalt SET etikett='Anslutningsdon' WHERE faltnamn='kabelskor_artikel_id'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET etikett='Kapsling (välj ur katalog)' "
            "WHERE mall_id=3 AND faltnamn='kabelskap_artikel_id'"
        )
        conn.execute(
            "UPDATE mall_inputfalt SET hjalp='4 anslutningsdon (3L+N)' "
            "WHERE mall_id=4 AND faltnamn='kabelskor_artikel_id'"
        )

        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','15')")
        conn.commit()

    if v < 16:
        # v16: Sätt moduler för anslutningsdon (-1) och säkringslastfrånskiljare (-3/-4)
        modul_map = {
            'ANSLUTNINGSDON ABB ADI 300 ISOLERAT':     -1,
            'ANSLUTNINGSDON ABB ADU 300 OISOLERAT':    -1,
            'ANSLUTNINGSDON ABB ADI 95 ISOLERAT':      -1,
            'ANSLUTNINGSDON ABB ADU 95 OISOLERAT':     -1,
            'ANSLUTNINGSDON AD 350':                   -1,
            'ANSLUTNINGSDON PEN/PE CUZ 95':            -1,
            'ANSLUTNINGSDON PEN/PE CUZ 300':           -1,
            'ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 95':  -1,
            'ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 300': -1,
            'SÄKRINGSLASTFRÅNSKILJARE SLD 00 500V':    -3,
            'SÄKRINGSLASTFRÅNSKILJARE SLD 000 500V':   -3,
            'SÄKRINGSLASTFRÅNSKILJARE SLE 1 690V':     -3,
            'SÄKRINGSLASTFRÅNSKILJARE SLE 2 690V':     -3,
            'SÄKRINGSLASFRÅNSK SLF160P':               -4,
            'SÄKRINGSLASFRÅNSK SLF250P':               -4,
            'SÄKRINGSLASFRÅNSK SLF400P':               -4,
            'SÄKRINGSLASFRÅNSK SLF630P':               -4,
        }
        for namn, moduler in modul_map.items():
            conn.execute(
                "UPDATE artiklar SET moduler=? WHERE artikelnamn=? AND moduler=0",
                (moduler, namn)
            )
            conn.execute(
                "UPDATE konstruktion_rader SET moduler=? WHERE artikelnamn=? AND moduler=0",
                (moduler, namn)
            )
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','16')")
        conn.commit()


    if v < 17:
        # v17: Lägg till AML 4G10 1KV SV som kabel
        kat = conn.execute(
            "SELECT id FROM kategorier WHERE namn='Kablar'"
        ).fetchone()
        if kat:
            kat_id = kat['id']
            exists = conn.execute(
                "SELECT 1 FROM artiklar WHERE artikelnamn='AML 4G10 1KV SV' AND kategori_id=?",
                (kat_id,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO artiklar (artikelnamn, kategori_id, enhet, sortering) "
                    "VALUES ('AML 4G10 1KV SV', ?, 'm', -1)",
                    (kat_id,)
                )
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','17')")
        conn.commit()

    if v < 18:
        # v18: Lägg till E-nummer (artikelnummer) från Byggprotokoll 1.0.xlsm för Onninen
        conn.execute("INSERT OR IGNORE INTO leverantorer (namn) VALUES ('Onninen')")
        lev = conn.execute("SELECT id FROM leverantorer WHERE namn='Onninen'").fetchone()
        if lev:
            lev_id = lev['id']
            enr_map = [
                # Anslutningsdon
                ('ANSLUTNINGSDON ABB ADI 300 ISOLERAT',     'E0732794'),
                ('ANSLUTNINGSDON ABB ADU 300 OISOLERAT',    'E0732796'),
                ('ANSLUTNINGSDON ABB ADI 95 ISOLERAT',      'E0732795'),
                ('ANSLUTNINGSDON ABB ADU 95 OISOLERAT',     'E0732797'),
                ('ANSLUTNINGSDON AD 350',                   'E0732602'),
                ('ANSLUTNINGSDON PEN/PE CUZ 95',            'E0731209'),
                ('ANSLUTNINGSDON PEN/PE CUZ 300',           'E0731210'),
                ('ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 95',  'E0731207'),
                ('ANSLUTNINGSDON ISOLERAD Z-SKENA CIZ 300', 'E0731208'),
                # Säkringslastfrånskiljare
                ('SÄKRINGSLASTFRÅNSKILJARE SLD 00 500V',    'E0732749'),
                ('SÄKRINGSLASTFRÅNSKILJARE SLD 000 500V',   'E0732747'),
                ('SÄKRINGSLASTFRÅNSKILJARE SLE 1 690V',     'E0732771'),
                ('SÄKRINGSLASTFRÅNSKILJARE SLE 2 690V',     'E0732772'),
                ('SÄKRINGSLASFRÅNSK SLF160P',               'E0733146'),
                ('SÄKRINGSLASFRÅNSK SLF250P',               'E0733147'),
                ('SÄKRINGSLASFRÅNSK SLF400P',               'E0733148'),
                ('SÄKRINGSLASFRÅNSK SLF630P',               'E0733149'),
                # Knivssäkringar
                ('KNIVSSÄKRING ECO HICAP 000/10A GG 500V',  'E2044104'),
                ('KNIVSSÄKRING ECO HICAP 000/16A GG 500V',  'E2044106'),
                ('KNIVSSÄKRING ECO HICAP 000/25A GG 500V',  'E2044110'),
                ('KNIVSSÄKRING ECO HICAP 000/35A GG 500V',  'E2044114'),
                ('KNIVSSÄKRING ECO HICAP 000/50A GG 500V',  'E2044118'),
                ('KNIVSSÄKRING ECO HICAP 000/63A GG 500V',  'E2044120'),
                ('KNIVSSÄKRING ECO HICAP 000/80A GG 500V',  'E2044122'),
                ('KNIVSSÄKRING ECO HICAP 000/100A GG 500V', 'E2044124'),
                ('KNIVSSÄKRING ECO HICAP 00/125A GG 500V',  'E2044126'),
                ('KNIVSSÄKRING ECO HICAP 00/160A GG 500V',  'E2044128'),
                ('KNIVSSÄKRING ECO HICAP 1/63A GG 500V',   'E2044316'),
                ('KNIVSSÄKRING ECO HICAP 1/80A GG 500V',   'E2044318'),
                ('KNIVSSÄKRING ECO HICAP 1/100A GG 500V',  'E2044320'),
                ('KNIVSSÄKRING ECO HICAP 1/125A GG 500V',  'E2044322'),
                ('KNIVSSÄKRING ECO HICAP 1/160A GG 500V',  'E2044324'),
                ('KNIVSSÄKRING ECO HICAP 1/200A GG 500V',  'E2044326'),
                ('KNIVSSÄKRING ECO HICAP 1/250A GG 500V',  'E2044330'),
                ('KNIVSSÄKRING ECO HICAP 2/100A GG 500V',  'E2044410'),
                ('KNIVSSÄKRING ECO HICAP 2/160A GG 500V',  'E2044414'),
                ('KNIVSSÄKRING ECO HICAP 2/200A GG 500V',  'E2044416'),
                ('KNIVSSÄKRING ECO HICAP 2/250A GG 500V',  'E2044420'),
                ('KNIVSSÄKRING ECO HICAP 2/315A GG 500V',  'E2044422'),
                ('KNIVSSÄKRING ECO HICAP 2/355A GG 500V',  'E2044424'),
                ('KOPPLINGSKNIV 1 KN 1 3ST',               'E0732776'),
                # Kapsling
                ('KAPSLING CDC 420 K2',  'E0732130'),
                ('KAPSLING CDC 440 K3',  'E0732131'),
                ('KAPSLING CDC 460 K4',  'E0732132'),
                # Kabelskarvar
                ('KABELSKARV 4-LED 6-50 MM² 1KV',    'E0702026'),
                ('KABELSKARV 1KV AL/CU 50-95MM²',    'E0718322'),
                ('KABELSKARV 1KV AL/CU 95-240MM²',   'E0718323'),
                ('KABELSKARV PXE-SU5-SE01',           'E0702128'),
                ('KABELSKARV LJTM-W-4X035-150',       'E0716209'),
                ('KABELSKARV 1KV 95-240 MM²',         'E0702134'),
                ('AVGRENINGSHYLSA C25-50',            'E0825320'),
                ('ÄNDHÄTTA KALLKRYMP 16-30MM',        'E0714382'),
                ('ÄNDHÄTTA KALLKRYMP 26-49MM',        'E0714383'),
                ('ÄNDHÄTTA KALLKRYMP 46-84MM',        'E0714384'),
                # Kabelskydd och rör
                ('KABELSKYDD PLANT 125-50', 'E0663009'),
                ('KABELRÖR KORR UDV 160',   'E0663214'),
                ('KABELRÖR UDV 110',        'E0663206'),
                ('RAK-BÖJ 110 SRN',         'E0663185'),
                ('RAK-BÖJ 160 SRN',         'E0663186'),
                # Märkning
                ('MÄRKSYST R5000 SIFFRA 0 DEKAL', 'E2988710'),
                ('MÄRKSYST R5000 SIFFRA 1 DEKAL', 'E2988711'),
                ('MÄRKSYST R5000 SIFFRA 2 DEKAL', 'E2988712'),
                ('MÄRKSYST R5000 SIFFRA 3 DEKAL', 'E2988713'),
                ('MÄRKSYST R5000 SIFFRA 4 DEKAL', 'E2988714'),
                ('MÄRKSYST R5000 SIFFRA 5 DEKAL', 'E2988715'),
                ('MÄRKSYST R5000 SIFFRA 6 DEKAL', 'E2988716'),
                ('MÄRKSYST R5000 SIFFRA 7 DEKAL', 'E2988717'),
                ('MÄRKSYST R5000 SIFFRA 8 DEKAL', 'E2988718'),
                ('MÄRKSYST R5000 SIFFRA 9 DEKAL', 'E2988719'),
                ('MÄRKLIST TRANSP SKYLTHÅLL PL',   'E0668132'),
                ('MARKERINGSSTÅNG KSPS 7',          'E0731094'),
                ('E.ON KABELSKÅPSLOGO KLISTER',     'E992373505'),
                # Övrigt
                ('HÅRDAD STÅLSPETS FS-11',          'E0632207'),
                ('FRÄMRE RÖR FS-21',                'E0632201'),
                ('FÖRLÄNGNINGSRÖR FS-31',           'E0632233'),
            ]
            for artikelnamn, enr in enr_map:
                art = conn.execute(
                    "SELECT id FROM artiklar WHERE artikelnamn=? AND aktiv=1",
                    (artikelnamn,)
                ).fetchone()
                if art:
                    conn.execute(
                        "INSERT INTO artikel_leverantor (artikel_id, leverantor_id, artikelnummer) "
                        "VALUES (?,?,?) "
                        "ON CONFLICT(artikel_id, leverantor_id) DO UPDATE SET artikelnummer=excluded.artikelnummer",
                        (art['id'], lev_id, enr)
                    )
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','18')")
        conn.commit()

    if v < 19:
        try:
            conn.execute("ALTER TABLE konstruktioner ADD COLUMN projekt_id INTEGER REFERENCES projekt(id)")
        except Exception:
            pass
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','19')")
        conn.commit()

    if v < 20:
        for kolumn in (
            "ALTER TABLE projekt ADD COLUMN kund TEXT",
            "ALTER TABLE projekt ADD COLUMN anslutningspunkt TEXT",
            "ALTER TABLE projekt ADD COLUMN fas TEXT",
        ):
            try:
                conn.execute(kolumn)
            except Exception:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projekt_fas_datum (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                fas         TEXT NOT NULL,
                startdatum  DATE NOT NULL,
                slutdatum   DATE,
                skapad      DATETIME NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projekt_tillstand (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                namn        TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'Inväntas',
                datum       DATE,
                anteckning  TEXT,
                skapad      DATETIME NOT NULL,
                uppdaterad  DATETIME NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projekt_aktiviteter (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                tidpunkt    DATETIME NOT NULL,
                typ         TEXT NOT NULL DEFAULT 'anteckning',
                beskrivning TEXT NOT NULL
            )
        """)
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','20')")
        conn.commit()

    if v < 21:
        for kolumn in (
            "ALTER TABLE projekt ADD COLUMN ib_nummer TEXT",
            "ALTER TABLE projekt ADD COLUMN kategori TEXT",
            "ALTER TABLE projekt ADD COLUMN tilldelat_till TEXT",
            "ALTER TABLE projekt ADD COLUMN omrade TEXT",
            "ALTER TABLE projekt ADD COLUMN inkommande_bestallningar TEXT",
            "ALTER TABLE projekt ADD COLUMN bekraftade_bestallningar TEXT",
            "ALTER TABLE projekt ADD COLUMN beredning_start DATE",
            "ALTER TABLE projekt ADD COLUMN beredning_slut DATE",
        ):
            try:
                conn.execute(kolumn)
            except Exception:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projekt_checklistor (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                item_nr    INTEGER NOT NULL,
                utford     INTEGER NOT NULL DEFAULT 0,
                UNIQUE(projekt_id, item_nr)
            )
        """)
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','21')")
        conn.commit()

    if v < 22:
        try:
            conn.execute("ALTER TABLE projekt_checklistor ADD COLUMN ej_relevant INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','22')")
        conn.commit()

    if v < 23:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projekt_budget (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id        INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                budget_typ        TEXT NOT NULL,
                beskrivning       TEXT,
                budgeterat_belopp REAL NOT NULL DEFAULT 0,
                skapad            DATETIME NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projekt_kostnad (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                budget_typ  TEXT NOT NULL,
                beskrivning TEXT,
                leverantor  TEXT,
                belopp      REAL NOT NULL DEFAULT 0,
                datum       DATE,
                faktura_nr  TEXT,
                skapad      DATETIME NOT NULL
            );
        """)
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','23')")
        conn.commit()

    if v < 24:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projekt_intakt (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
                beskrivning TEXT,
                belopp      REAL NOT NULL DEFAULT 0,
                datum       DATE,
                faktura_nr  TEXT,
                skapad      DATETIME NOT NULL
            );
        """)
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','24')")
        conn.commit()

    if v < 25:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS anslutning_projekt (
                id         TEXT PRIMARY KEY,
                namn       TEXT NOT NULL DEFAULT '',
                kund       TEXT DEFAULT '',
                fas        TEXT NOT NULL DEFAULT 'Tidig fas',
                berStart   DATE,
                berSlut    DATE,
                montStart  DATE,
                montSlut   DATE,
                driftDat   DATE,
                blockering TEXT,
                notat      TEXT DEFAULT '',
                skapad     DATETIME NOT NULL
            );
        """)
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','25')")
        conn.commit()

    if v < 26:
        # v26: Återställ admin-lösenord till "admin" (sha256)
        import hashlib
        admin_hash = hashlib.sha256(b'admin').hexdigest()
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('admin_losenord',?)",
            (admin_hash,)
        )
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','26')")
        conn.commit()

    if v < 27:
        # v27: Lägg till kategorier, artiklar, mallar och inputfält för
        #      Stolpar, Tillbehör Stolpar, ALUS och HSP material

        def _kat27(namn, sort):
            conn.execute("INSERT OR IGNORE INTO kategorier (namn, sortering) VALUES (?,?)", (namn, sort))
            return conn.execute("SELECT id FROM kategorier WHERE namn=?", (namn,)).fetchone()['id']

        def _art27(namn, kat_id, enhet, sort):
            conn.execute(
                "INSERT OR IGNORE INTO artiklar (artikelnamn, kategori_id, enhet, sortering) VALUES (?,?,?,?)",
                (namn, kat_id, enhet, sort)
            )
            return conn.execute(
                "SELECT id FROM artiklar WHERE artikelnamn=? AND kategori_id=?", (namn, kat_id)
            ).fetchone()['id']

        def _enr27(art_id, lev_id, enr):
            conn.execute(
                "INSERT OR IGNORE INTO artikel_leverantor (artikel_id, leverantor_id, artikelnummer) "
                "VALUES (?,?,?)",
                (art_id, lev_id, enr)
            )

        # Säkerställ Onninen-leverantör
        conn.execute("INSERT OR IGNORE INTO leverantorer (namn) VALUES ('Onninen')")
        lev_id = conn.execute("SELECT id FROM leverantorer WHERE namn='Onninen'").fetchone()['id']

        # --- Kategorier ---
        kat_stolpar    = _kat27('Stolpar',            10)
        kat_tillbehor  = _kat27('Tillbehör Stolpar',  11)
        kat_alus       = _kat27('ALUS',               12)
        kat_hsp        = _kat27('HSP material',        13)

        # --- Stolpar ---
        stolpar_art = [
            ('FURUSTOLPE RVP REP N7',  'st'), ('FURUSTOLPE RVP REP N8',  'st'),
            ('FURUSTOLPE RVP REP N9',  'st'), ('FURUSTOLPE RVP REP N10', 'st'),
            ('FURUSTOLPE RVP REP N11', 'st'), ('FURUSTOLPE RVP REP N12', 'st'),
            ('FURUSTOLPE RVP REP N13', 'st'), ('FURUSTOLPE RVP REP N14', 'st'),
            ('FURUSTOLPE RVP REP N15', 'st'), ('FURUSTOLPE RVP REP N16', 'st'),
            ('FURUSTOLPE RVP REP N17', 'st'), ('FURUSTOLPE RVP REP N18', 'st'),
            ('FURUSTOLPE RVP REP N19', 'st'), ('FURUSTOLPE RVP REP N20', 'st'),
            ('FURUSTOLPE RVP REP G8',  'st'), ('FURUSTOLPE RVP REP G9',  'st'),
            ('FURUSTOLPE RVP REP G10', 'st'), ('FURUSTOLPE RVP REP G11', 'st'),
            ('FURUSTOLPE RVP REP G12', 'st'), ('FURUSTOLPE RVP REP G13', 'st'),
            ('FURUSTOLPE RVP REP G14', 'st'), ('FURUSTOLPE RVP REP G15', 'st'),
            ('FURUSTOLPE RVP REP G16', 'st'), ('FURUSTOLPE RVP REP G17', 'st'),
            ('FURUSTOLPE RVP REP G18', 'st'), ('FURUSTOLPE RVP REP G19', 'st'),
            ('FURUSTOLPE RVP REP G20', 'st'), ('FURUSTOLPE RVP REP G21', 'st'),
        ]
        stolpar_enr = [
            'E0620367', 'E0620371', 'E0620379', 'E0620389', 'E0620469', 'E0620486',
            'E0620496', 'E0620528', 'E0620557', 'E0620576', 'E0620587', 'E0620593',
            'E0620603', 'E0620714', 'E0620373', 'E0620381', 'E0620391', 'E0620471',
            'E0620487', 'E0620497', 'E0620536', 'E0620558', 'E0620577', 'E0620588',
            'E0620594', 'E0620653', 'E0620715', 'E0620719',
        ]
        for i, ((namn, enhet), enr) in enumerate(zip(stolpar_art, stolpar_enr)):
            aid = _art27(namn, kat_stolpar, enhet, i)
            _enr27(aid, lev_id, enr)

        # --- Tillbehör Stolpar ---
        tillbehor_art = [
            ('STOLPTAK 180 MM',                'st', 'E0630278'),
            ('STOLPTAK 210 MM 0037/F',         'st', 'E0630277'),
            ('STOLPTAK 270 MM 0034/F',         'st', 'E0630279'),
            ('0001/11 STAG RAKKILAD',          'st', 'E0600018'),
            ('0001/18 STAG RAKKILAD',          'st', 'E0600019'),
            ('0004/22 STAG RAKKILAD',          'st', 'E0600042'),
            ('0012/15 STAG RAKKILAD ISO 24',   'st', 'E0600123'),
            ('0012/22 STAG RAKKILAD ISO 24',   'st', 'E0600124'),
            ('0016P FÖRANKRING PLAST LÅNG',    'st', 'E0610171'),
            ('UPPLEDNINGSRÖR 58/50 1,7M SV',   'st', 'E0663731'),
            ('UPPLEDNINGSRÖR 83/75 1,7M SV',   'st', 'E0663733'),
            ('UPPLEDNINGSRÖR 120/110 1,7M SV', 'st', 'E0663735'),
            ('STOLPFÄSTE FÖR RÖR 58/50',       'st', 'E0665449'),
            ('STOLPFÄSTE FÖR RÖR 83/75',       'st', 'E0665450'),
            ('STOLPFÄSTE FÖR RÖR 120/110',     'st', 'E0665452'),
        ]
        for i, (namn, enhet, enr) in enumerate(tillbehor_art):
            aid = _art27(namn, kat_tillbehor, enhet, i)
            _enr27(aid, lev_id, enr)

        # --- ALUS ---
        alus_art = [
            ('ALUS-D 4X25',                         'm',    'E0031800'),
            ('ALUS-D 4X50',                         'm',    'E0031810'),
            ('ALUS-D 4X95',                         'm',    'E0031820'),
            ('ALUS-D 4X25 T500',                    '500m', 'E0031805'),
            ('ALUS-D 4X50 T500',                    '500m', 'E0031815'),
            ('ALUS-D 4X95 T500',                    '500m', 'E0031825'),
            ('0170 ALUS 0,4KV GENOMGÅENDE KROK',    'sats', 'E0601700'),
            ('0171 ALUS 0,4KV GENOMGÅENDE 2ST KROK','sats', 'E0601710'),
            ('0174 ALUS 0,4KV DUBBLA ALUS',         'sats', 'E0601740'),
            ('SPÄNNDON ALUS',                       'st',   'E0647404'),
            ('SPÄNNDON SO118.1201S',                'st',   'E0645121'),
            ('PINNKROK SOT21.216',                  'st',   'E0645145'),
            ('HÄNGDON 25-120mm²',                   'st',   'E0623000'),
            ('HÄNGDON ALUS 4 LED 25-95',            'st',   'E0647220'),
            ('UNIVERSALKLÄMMA UKRS 90',             'st',   'E0702972'),
            ('KABELFÄSTE SH709',                    'st',   'E0630084'),
            ('JORDNINGSKLÄMMA KG 42',               'st',   'E0632005'),
            ('FÖRLÄNGNINGSRÖR FS-31',               'st',   'E0632233'),
            ('FRÄMRE RÖR FS-21',                    'st',   'E0632201'),
            ('HÄRDAD STÅLSPETS FS-11',              'st',   'E0632207'),
            ('NEDLEDNINGSSKYDD FÖR LINA SH 208',    'st',   'E0632030'),
            ('SKENKLÄMMA KG 16',                    'st',   'E0650539'),
            ('JORDKLÄMMA CU 10-70',                 'st',   'E0632023'),
            ('JORDKLÄMMA CU 16-120',                'st',   'E0632386'),
            ('GRENKLÄMMA CU 6-70',                  'st',   'E0651010'),
            ('GRENKLÄMMA SL8.21 50-240 MM2',        'st',   'E0650059'),
            ('SKYDDSKÅPA SP16',                     'st',   'E0650209'),
            ('AVGRENINGSKLÄMMA SLIW50',             'st',   'E0650244'),
            ('AVGRENINGSKLÄMMA SLIW52',             'st',   'E0650002'),
            ('AVGRENINGSKLÄMMA SLIW 54',            'st',   'E0650245'),
            ('AVGRENINGSKLÄMMA SLIW57',             'st',   'E0650246'),
            ('AVGRENINGSKLÄMMA SLIW58',             'st',   'E0650247'),
            ('ÄNDSTOPP 4-50',                       'st',   'E0650200'),
        ]
        for i, (namn, enhet, enr) in enumerate(alus_art):
            aid = _art27(namn, kat_alus, enhet, i)
            _enr27(aid, lev_id, enr)

        # --- HSP material ---
        hsp_art = [
            ('KABELAVSLUT IXSU-F 3333-M',           'st', 'E0706339'),
            ('KABELSKARV MXSU 5311 24KV',           'st', 'E0716042'),
            ('KABELSKARV CPKJ-3311 12KV 3X35-95',   'st', 'E0716311'),
            ('KABELSKARV CPKJ-3331 12KV 3X95-240',  'st', 'E0716312'),
            ('KABELSKARV CPKJ-5311 24KV 3X35-95',   'st', 'E0716321'),
            ('KABELSKARV CPKJ-5331 24KV 3X95-240',  'st', 'E0716322'),
            ('KOMPLETTERINGSSATS TRIX MK II',        'st', 'E0716610'),
            ('KABELAVSLUT OXSU-F 5334-M',            'st', 'E0706322'),
            ('KABELAVSLUT OXSU-F 5131',              'st', 'E0706478'),
            ('KABELAVSLUT OXSU-F 5334',              'st', 'E0706496'),
            ('TILLÄGGSSATS TSFK 1',                  'st', 'E0706640'),
            ('ANSL-DON RSTI-5851-SE02',              'st', 'E0706780'),
            ('ANSL-DON RSTI-5854-SE02',              'st', 'E0706781'),
            ('TRANSFORMATORADAPTER PITO-E',          'st', 'E0709010'),
            ('FÄSTEN TILL PITO-E',                   'st', 'E0709021'),
            ('SKRUVKABELSKO BLMT-95/240-13',         'st', 'E0836914'),
            ('0053 FÖRANKRING',                      'st', 'E0600530'),
            ('NEDLEDNINGSSKYDD FÖR LINA SH 208',    'st', 'E0632030'),
            ('VENTILAVLEDARFÄSTE F. STOLPE',         'st', 'E0634035'),
            ('VENTILAVLEDARE 23KV',                  'st', 'E0634164'),
            ('GRENKLÄMMA SL 4.25',                   'st', 'E0650057'),
            ('CU-SKENA PSS 10.01',                   'st', 'E0650505'),
            ('SKENKLÄMMA KG 16',                     'st', 'E0650539'),
            ('SKENKLÄMMA',                           'st', 'E0650540'),
            ('AMS-KLÄMMA BLL 50-157 AL25-185',       'st', 'E0650606'),
            ('FRILEDNINNGSKLÄMMA FK 120',             'st', 'E0702962'),
            ('FRILEDNINNGSKLÄMMA FK 300',             'st', 'E0702963'),
            ('FÅGELSKYDD HU 150',                    'st', 'E0702315'),
            ('FÄSTE FKFB',                           'st', 'E0702967'),
            ('GRENFORMGODS 402 W248',                'st', 'E0776446'),
            ('2133 BLL FLEX KOMPOSIT',               'st', 'UF12633'),
        ]
        for i, (namn, enhet, enr) in enumerate(hsp_art):
            aid = _art27(namn, kat_hsp, enhet, i)
            _enr27(aid, lev_id, enr)

        # --- Mallar ---
        nya_mallar = [
            (5, 'Stolpar',            'Stolpar för luftledningsnät.',                   5),
            (6, 'Tillbehör Stolpar',  'Tillbehör och fästen för stolpmontering.',       6),
            (7, 'ALUS',               'Material för ALUS-ledningar (0,4 kV luftledning).', 7),
            (8, 'HSP material',       'Högspänningsmaterial, kabelskarvar och avslut.', 8),
        ]
        for mid, namn, beskr, sort in nya_mallar:
            conn.execute(
                "INSERT OR IGNORE INTO mallar (id, namn, beskrivning, sortering) VALUES (?,?,?,?)",
                (mid, namn, beskr, sort)
            )

        # --- Inputfält per mall (ett artikel_select-fält kopplat till rätt kategori) ---
        mall_falt = [
            (5, 'stolpe_artikel_id',    'Stolptyp',           'artikel_select',
             '{"kategori_namn":"Stolpar"}',
             'Välj stolptyp', 1, 1),
            (6, 'tillbehor_artikel_id', 'Tillbehör',          'artikel_select',
             '{"kategori_namn":"Tillbehör Stolpar"}',
             'Välj tillbehör', 1, 1),
            (7, 'alus_artikel_id',      'ALUS-material',      'artikel_select',
             '{"kategori_namn":"ALUS"}',
             'Välj ALUS-artikel', 1, 1),
            (8, 'hsp_artikel_id',       'HSP-material',       'artikel_select',
             '{"kategori_namn":"HSP material"}',
             'Välj HSP-material', 1, 1),
        ]
        for mid, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering in mall_falt:
            conn.execute(
                "INSERT OR IGNORE INTO mall_inputfalt "
                "(mall_id, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (mid, faltnamn, etikett, typ, alternativ, hjalp, obligatorisk, sortering)
            )

        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','27')")
        conn.commit()

    if v < 28:
        # v28: Lägg till bestallningKlar och beredare i anslutning_projekt
        for col in (
            "ALTER TABLE anslutning_projekt ADD COLUMN bestallningKlar DATE",
            "ALTER TABLE anslutning_projekt ADD COLUMN beredare TEXT",
        ):
            try:
                conn.execute(col)
            except Exception:
                pass
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','28')")
        conn.commit()

    if v < 29:
        # v29: Faktureringsstatistik-tabell
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fakturering (
                id             TEXT NOT NULL,
                projektnamn    TEXT NOT NULL DEFAULT '',
                projektledare  TEXT NOT NULL DEFAULT '',
                utestående     REAL NOT NULL DEFAULT 0,
                verklIntakt    REAL NOT NULL DEFAULT 0,
                budgIntakt     REAL NOT NULL DEFAULT 0,
                fardigt        REAL NOT NULL DEFAULT 0,
                manad          TEXT NOT NULL,
                importerad     DATETIME NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fakturering_manad ON fakturering(manad)")
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','29')")
        conn.commit()

    if v < 30:
        # v30: Lägg till verklKostn (Tot. verkl. kostn.) i fakturering
        try:
            conn.execute("ALTER TABLE fakturering ADD COLUMN verklKostn REAL NOT NULL DEFAULT 0")
        except Exception:
            pass
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','30')")
        conn.commit()

    if v < 31:
        # v31: Lägg till budgKostn (Tot. budgeterad kostn.) i fakturering
        try:
            conn.execute("ALTER TABLE fakturering ADD COLUMN budgKostn REAL NOT NULL DEFAULT 0")
        except Exception:
            pass
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','31')")
        conn.commit()

    if v < 32:
        # v32: Lägg till SAK300 och SAKI300 (anslutningsdon för STITEC) med Onninen-E-nummer.
        kat = conn.execute(
            "SELECT id FROM kategorier WHERE namn='Anslutningsdon'"
        ).fetchone()
        if kat:
            kat_id = kat['id']
            conn.execute("INSERT OR IGNORE INTO leverantorer (namn) VALUES ('Onninen')")
            lev = conn.execute("SELECT id FROM leverantorer WHERE namn='Onninen'").fetchone()
            lev_id = lev['id'] if lev else None
            max_sort = conn.execute(
                "SELECT COALESCE(MAX(sortering), 0) FROM artiklar WHERE kategori_id=?",
                (kat_id,)
            ).fetchone()[0]
            nya = [
                ('ANSLUTNINGSDON SAK300 (STITEC)',  'E0733139'),
                ('ANSLUTNINGSDON SAKI300 (STITEC)', 'E0733132'),
            ]
            for i, (namn, enr) in enumerate(nya):
                exists = conn.execute(
                    "SELECT id FROM artiklar WHERE artikelnamn=? AND kategori_id=?",
                    (namn, kat_id)
                ).fetchone()
                if exists:
                    aid = exists['id']
                else:
                    cur = conn.execute(
                        "INSERT INTO artiklar (artikelnamn, kategori_id, enhet, sortering, moduler) "
                        "VALUES (?,?,?,?,?)",
                        (namn, kat_id, 'st', max_sort + 1 + i, -1)
                    )
                    aid = cur.lastrowid
                if lev_id:
                    conn.execute(
                        "INSERT INTO artikel_leverantor (artikel_id, leverantor_id, artikelnummer) "
                        "VALUES (?,?,?) "
                        "ON CONFLICT(artikel_id, leverantor_id) DO UPDATE SET artikelnummer=excluded.artikelnummer",
                        (aid, lev_id, enr)
                    )
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','32')")
        conn.commit()

    if v < 33:
        # v33: Användarkonton. Skapa tabell + admin-konto + konto per befintlig beredare.
        import hashlib, re
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anvandare (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                anvandarnamn  TEXT UNIQUE NOT NULL,
                namn          TEXT NOT NULL DEFAULT '',
                losenord_hash TEXT NOT NULL,
                roll          TEXT NOT NULL DEFAULT 'beredare',
                beredare      TEXT,
                aktiv         INTEGER NOT NULL DEFAULT 1,
                skapad        DATETIME
            )
        """)

        def _h(p):
            return hashlib.sha256(p.encode()).hexdigest()

        def _slug(namn):
            s = namn.lower().translate(str.maketrans('åäöé', 'aaoe'))
            return re.sub(r'[^a-z0-9]', '', s)

        # Admin-konto (matchar standard admin-lösenord 'admin')
        conn.execute(
            "INSERT OR IGNORE INTO anvandare (anvandarnamn,namn,losenord_hash,roll,aktiv) "
            "VALUES ('admin','Administratör',?, 'admin', 1)",
            (_h('admin'),)
        )

        # Ett konto per befintlig beredare (standardlösenord 'oneco' – ska bytas)
        for rad in conn.execute("SELECT namn FROM beredare").fetchall():
            namn = rad['namn']
            slug = _slug(namn)
            if not slug:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO anvandare "
                "(anvandarnamn,namn,losenord_hash,roll,beredare,aktiv) "
                "VALUES (?,?,?, 'beredare', ?, 1)",
                (slug, namn, _h('oneco'), namn)
            )

        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','33')")
        conn.commit()

    if v < 34:
        # v34: Maskinplanering (delad planering med UE – ersätter Excel-filen).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maskinplanering (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                projekt_id  INTEGER REFERENCES projekt(id) ON DELETE SET NULL,
                projektnamn TEXT NOT NULL DEFAULT '',
                maskin      TEXT NOT NULL DEFAULT '',
                ue          TEXT,
                startdatum  DATE,
                slutdatum   DATE,
                status      TEXT NOT NULL DEFAULT 'Planerad',
                notat       TEXT,
                skapad      DATETIME NOT NULL,
                uppdaterad  DATETIME NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_maskinplan_start ON maskinplanering(startdatum)")
        conn.execute("INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','34')")
        conn.commit()


def _create_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS installningar (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            nyckel  TEXT UNIQUE NOT NULL,
            varde   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS beredare (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            namn    TEXT UNIQUE NOT NULL,
            aktiv   INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS kategorier (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            namn      TEXT UNIQUE NOT NULL,
            sortering INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS leverantorer (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            namn  TEXT UNIQUE NOT NULL,
            aktiv INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS artiklar (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            artikelnamn TEXT NOT NULL,
            kategori_id INTEGER NOT NULL REFERENCES kategorier(id),
            enhet       TEXT NOT NULL,
            beskrivning TEXT,
            sortering   INTEGER NOT NULL DEFAULT 0,
            aktiv       INTEGER NOT NULL DEFAULT 1,
            moduler     INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS artikel_leverantor (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            artikel_id    INTEGER NOT NULL REFERENCES artiklar(id) ON DELETE CASCADE,
            leverantor_id INTEGER NOT NULL REFERENCES leverantorer(id),
            artikelnummer TEXT,
            a_pris        REAL,
            UNIQUE(artikel_id, leverantor_id)
        );

        CREATE TABLE IF NOT EXISTS projekt (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            projektnummer    TEXT UNIQUE NOT NULL,
            projektnamn      TEXT NOT NULL,
            beredare         TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'Planerat'
                             CHECK(status IN ('Planerat','Pågående','Klart')),
            startdatum       DATE,
            anteckningar     TEXT,
            kund             TEXT,
            anslutningspunkt TEXT,
            fas              TEXT,
            ib_nummer            TEXT,
            kategori             TEXT,
            tilldelat_till       TEXT,
            omrade               TEXT,
            inkommande_bestallningar TEXT,
            bekraftade_bestallningar TEXT,
            beredning_start      DATE,
            beredning_slut       DATE,
            skapad           DATETIME NOT NULL,
            uppdaterad       DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mallar (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            namn        TEXT NOT NULL,
            beskrivning TEXT,
            sortering   INTEGER NOT NULL DEFAULT 0,
            aktiv       INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS mall_inputfalt (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mall_id     INTEGER NOT NULL REFERENCES mallar(id) ON DELETE CASCADE,
            faltnamn    TEXT NOT NULL,
            etikett     TEXT NOT NULL,
            typ         TEXT NOT NULL DEFAULT 'number',
            alternativ  TEXT,
            hjalp       TEXT,
            obligatorisk INTEGER NOT NULL DEFAULT 1,
            sortering   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS mall_egenkontroll (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mall_id     INTEGER NOT NULL REFERENCES mallar(id) ON DELETE CASCADE,
            punkt       TEXT NOT NULL,
            sortering   INTEGER NOT NULL DEFAULT 0,
            UNIQUE(mall_id, punkt)
        );

        CREATE TABLE IF NOT EXISTS byggprotokoll (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            mall_id     INTEGER NOT NULL REFERENCES mallar(id),
            mall_namn   TEXT NOT NULL,
            inputdata   TEXT NOT NULL DEFAULT '{}',
            anteckningar TEXT,
            status      TEXT NOT NULL DEFAULT 'Utkast',
            skapad      DATETIME NOT NULL,
            uppdaterad  DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS byggprotokoll_rader (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            protokoll_id    INTEGER NOT NULL REFERENCES byggprotokoll(id) ON DELETE CASCADE,
            artikel_id      INTEGER REFERENCES artiklar(id),
            artikelnamn     TEXT NOT NULL,
            kategori        TEXT,
            enhet           TEXT NOT NULL,
            antal           REAL NOT NULL,
            leverantor_id   INTEGER REFERENCES leverantorer(id),
            leverantor_namn TEXT,
            artikelnummer   TEXT,
            a_pris          REAL,
            anteckning      TEXT,
            manuell         INTEGER NOT NULL DEFAULT 0,
            sortering       INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS byggprotokoll_egenkontroll (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            protokoll_id    INTEGER NOT NULL REFERENCES byggprotokoll(id) ON DELETE CASCADE,
            punkt           TEXT NOT NULL,
            utford          INTEGER NOT NULL DEFAULT 0,
            ej_relevant     INTEGER NOT NULL DEFAULT 0,
            sortering       INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS konstruktioner (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER REFERENCES projekt(id),
            typ         TEXT NOT NULL,
            byggnr      TEXT,
            namn        TEXT NOT NULL,
            fri_id      TEXT,
            anmarkning  TEXT,
            status      TEXT NOT NULL DEFAULT 'Pågående',
            skapad      DATETIME NOT NULL,
            uppdaterad  DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS konstruktion_rader (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            konstruktion_id   INTEGER NOT NULL REFERENCES konstruktioner(id) ON DELETE CASCADE,
            artikel_id        INTEGER REFERENCES artiklar(id),
            artikelnamn       TEXT NOT NULL,
            enhet             TEXT NOT NULL,
            antal             REAL NOT NULL DEFAULT 1,
            moduler           INTEGER NOT NULL DEFAULT 0,
            anteckning        TEXT,
            sortering         INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS konstruktion_egenkontroll (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            konstruktion_id   INTEGER NOT NULL REFERENCES konstruktioner(id) ON DELETE CASCADE,
            punkt             TEXT NOT NULL,
            utford            INTEGER NOT NULL DEFAULT 0,
            ej_relevant       INTEGER NOT NULL DEFAULT 0,
            sortering         INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS projekt_fas_datum (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            fas         TEXT NOT NULL,
            startdatum  DATE NOT NULL,
            slutdatum   DATE,
            skapad      DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projekt_tillstand (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            namn        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'Inväntas',
            datum       DATE,
            anteckning  TEXT,
            skapad      DATETIME NOT NULL,
            uppdaterad  DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projekt_aktiviteter (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            tidpunkt    DATETIME NOT NULL,
            typ         TEXT NOT NULL DEFAULT 'anteckning',
            beskrivning TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projekt_checklistor (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            item_nr     INTEGER NOT NULL,
            utford      INTEGER NOT NULL DEFAULT 0,
            ej_relevant INTEGER NOT NULL DEFAULT 0,
            UNIQUE(projekt_id, item_nr)
        );

        CREATE TABLE IF NOT EXISTS projekt_budget (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id        INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            budget_typ        TEXT NOT NULL,
            beskrivning       TEXT,
            budgeterat_belopp REAL NOT NULL DEFAULT 0,
            skapad            DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projekt_kostnad (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            budget_typ  TEXT NOT NULL,
            beskrivning TEXT,
            leverantor  TEXT,
            belopp      REAL NOT NULL DEFAULT 0,
            datum       DATE,
            faktura_nr  TEXT,
            skapad      DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projekt_intakt (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER NOT NULL REFERENCES projekt(id) ON DELETE CASCADE,
            beskrivning TEXT,
            belopp      REAL NOT NULL DEFAULT 0,
            datum       DATE,
            faktura_nr  TEXT,
            skapad      DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS anslutning_projekt (
            id               TEXT PRIMARY KEY,
            namn             TEXT NOT NULL DEFAULT '',
            kund             TEXT DEFAULT '',
            fas              TEXT NOT NULL DEFAULT 'Tidig fas',
            berStart         DATE,
            berSlut          DATE,
            montStart        DATE,
            montSlut         DATE,
            driftDat         DATE,
            blockering       TEXT,
            notat            TEXT DEFAULT '',
            bestallningKlar  DATE,
            beredare         TEXT,
            skapad           DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fakturering (
            id             TEXT NOT NULL,
            projektnamn    TEXT NOT NULL DEFAULT '',
            projektledare  TEXT NOT NULL DEFAULT '',
            utestående     REAL NOT NULL DEFAULT 0,
            verklIntakt    REAL NOT NULL DEFAULT 0,
            verklKostn     REAL NOT NULL DEFAULT 0,
            budgIntakt     REAL NOT NULL DEFAULT 0,
            budgKostn      REAL NOT NULL DEFAULT 0,
            fardigt        REAL NOT NULL DEFAULT 0,
            manad          TEXT NOT NULL,
            importerad     DATETIME NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_fakturering_manad ON fakturering(manad);

        CREATE TABLE IF NOT EXISTS anvandare (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            anvandarnamn  TEXT UNIQUE NOT NULL,
            namn          TEXT NOT NULL DEFAULT '',
            losenord_hash TEXT NOT NULL,
            roll          TEXT NOT NULL DEFAULT 'beredare',
            beredare      TEXT,
            aktiv         INTEGER NOT NULL DEFAULT 1,
            skapad        DATETIME
        );

        CREATE TABLE IF NOT EXISTS maskinplanering (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            projekt_id  INTEGER REFERENCES projekt(id) ON DELETE SET NULL,
            projektnamn TEXT NOT NULL DEFAULT '',
            maskin      TEXT NOT NULL DEFAULT '',
            ue          TEXT,
            startdatum  DATE,
            slutdatum   DATE,
            status      TEXT NOT NULL DEFAULT 'Planerad',
            notat       TEXT,
            skapad      DATETIME NOT NULL,
            uppdaterad  DATETIME NOT NULL
        );
    """)


def _is_tom(conn):
    return conn.execute("SELECT COUNT(*) FROM artiklar").fetchone()[0] == 0


if __name__ == '__main__':
    init_db()
    print(f"Databas initierad: {os.path.abspath(DB_PATH)}")
