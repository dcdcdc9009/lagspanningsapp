from datetime import datetime


def row_to_dict(row):
    return dict(row) if row else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


def nu():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def nasta_projektnummer(conn):
    ar = datetime.now().year
    prefix = f"{ar}-"
    rader = conn.execute(
        "SELECT projektnummer FROM projekt WHERE projektnummer LIKE ? ORDER BY projektnummer DESC",
        (prefix + '%',)
    ).fetchall()
    lopnummer = 1
    for rad in rader:
        try:
            n = int(rad['projektnummer'].split('-')[1])
            lopnummer = n + 1
            break
        except (ValueError, IndexError):
            continue
    return f"{ar}-{lopnummer:04d}"
