import sqlite3, os
from datetime import datetime

DB_PATH = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'data', 'lagspanning.db')
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    try:
        _create_tables(conn)
        conn.commit()

        tom = _is_tom(conn)
        if tom:
            # Helt ny databas – fyll allt
            from seed_data import fyll_i_startdata
            fyll_i_startdata(conn)
            conn.commit()
        else:
            # Befintlig databas – kör migrationer + nya artiklar
            _migrera(conn)

        # Alltid: säkerställ egenkontroll-data för alla mallar
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
        # v2: Ta bort alla priser, lägg till nya artiklar
        conn.execute("DELETE FROM artikel_leverantor")
        from seed_data import fyll_nya_artiklar
        fyll_nya_artiklar(conn)
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','2')"
        )
        conn.commit()
        v = 2

    if v < 3:
        # v3: Lägg till beskrivning-kolumn, ta bort eventuella dubletter
        try:
            conn.execute("ALTER TABLE artiklar ADD COLUMN beskrivning TEXT")
        except Exception:
            pass  # Kolumnen finns redan
        # Ta bort dubletter – behåll lägst id per (artikelnamn, kategori_id)
        conn.execute("""
            DELETE FROM artiklar WHERE id NOT IN (
                SELECT MIN(id) FROM artiklar GROUP BY artikelnamn, kategori_id
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO installningar (nyckel,varde) VALUES ('db_version','3')"
        )
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
            aktiv       INTEGER NOT NULL DEFAULT 1
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
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            projektnummer TEXT UNIQUE NOT NULL,
            projektnamn   TEXT NOT NULL,
            beredare      TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'Planerat'
                          CHECK(status IN ('Planerat','Pågående','Klart')),
            startdatum    DATE,
            anteckningar  TEXT,
            skapad        DATETIME NOT NULL,
            uppdaterad    DATETIME NOT NULL
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
    """)


def _is_tom(conn):
    return conn.execute("SELECT COUNT(*) FROM artiklar").fetchone()[0] == 0


if __name__ == '__main__':
    init_db()
    print(f"Databas initierad: {os.path.abspath(DB_PATH)}")
