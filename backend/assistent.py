"""BPV-assistenten – AI via Claude API (Haiku) med verktygsåtkomst.

Läs-verktyg körs automatiskt. Skriv-verktyg (skapa/ändra) gatas av ett
bekräftelsesteg: modellen föreslår, frontend visar Bekräfta/Avbryt, och först
efter godkännande utförs ändringen. Endast användarens fråga + relevant data
skickas till API:t.
"""
import datetime
from database import get_db
from models import nu, nasta_projektnummer

MODELL = 'claude-haiku-4-5'
GILTIG_STATUS = ('Planerat', 'Pågående', 'Klart')
GILTIG_FAS = ('Beredning', 'Projektledning', 'Utförda')
VYER = ('projekt', 'konstruktioner', 'artiklar', 'anslutning', 'tjallmo',
        'kabeltrummor', 'kontakter', 'karta', 'ruttplanering', 'tidplan',
        'admin', 'hjalp', 'assistent')

_klient = [None]


def _få_klient():
    if _klient[0] is None:
        import anthropic
        _klient[0] = anthropic.Anthropic()  # läser ANTHROPIC_API_KEY från miljön
    return _klient[0]


def _veckonummer(d):
    return d.isocalendar()[1]


def _systemprompt(kontext):
    d = datetime.date.today()
    namn = (kontext or {}).get('namn') or 'användaren'
    return (
        "Du är BPV-assistenten – en hjälpsam AI inbyggd i BPV "
        "(Beredning och Projektlednings Verktyget), ett webbverktyg för OneCo "
        "Networks AB som hanterar lågspännings-elinstallationer åt E.ON.\n\n"
        f"Idag är {d.isoformat()} (vecka {_veckonummer(d)}). Du pratar med {namn}.\n\n"
        "SPRÅK: Svara alltid på svenska, kort, tydligt och vänligt.\n\n"
        "OM APPEN (flikar): Projekt (projekt-/ärendeöversikt, skapa ärende), "
        "Byggprotokoll/materiallista, Artiklar, Analys (anslutningsärenden), "
        "Tjällmo (fältplanering), Kabeltrummor, Kontaktuppgifter, Karta, "
        "Ruttplanering (optimera körrutter), Tidplan, Admin, Hjälp.\n"
        "Faser för ett projekt: Beredning → Projektledning → Utförda.\n\n"
        "BEREDNING: arbetet att förbereda en elnätsinstallation – platsbesök, "
        "schakt-/lednings-/återställningskartor, byggprotokoll, materiallista, "
        "kalkyl, tillstånd (ledningskollen, markägare, trafikverket m.m.) innan montage.\n\n"
        "VERKTYG: Använd verktygen för att slå upp riktig data i stället för att gissa. "
        "När du ska SKAPA eller ÄNDRA något: anropa rätt verktyg med föreslagna värden – "
        "systemet visar då en bekräftelseruta för användaren och utför ändringen först "
        "efter godkännande. Påstå aldrig att något är gjort förrän det bekräftats.\n\n"
        "ÄRLIGHET: Om du inte vet (t.ex. detaljer i EBR eller annat du inte fått data om), "
        "säg det rakt ut i stället för att hitta på."
    )


VERKTYG = [
    {"name": "projektoversikt", "description":
     "Hämta antal projekt totalt, per fas (Beredning/Projektledning/Utförda) och per beredare. "
     "Använd för frågor som 'hur många ärenden/projekt har vi'.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "sok_projekt", "description":
     "Sök bland projekt/ärenden på fritext (matchar projektnamn, projektnummer, IB-nummer, beredare, område).",
     "input_schema": {"type": "object", "properties": {
         "text": {"type": "string", "description": "Sökord"}}, "required": ["text"]}},
    {"name": "projekt_detalj", "description":
     "Hämta detaljer om ett specifikt projekt via dess projektnummer.",
     "input_schema": {"type": "object", "properties": {
         "projektnummer": {"type": "string"}}, "required": ["projektnummer"]}},
    {"name": "navigera", "description":
     "Öppna en flik i appen åt användaren. Giltiga vyer: " + ", ".join(VYER) + ".",
     "input_schema": {"type": "object", "properties": {
         "vy": {"type": "string"}}, "required": ["vy"]}},
    {"name": "skapa_projekt", "description":
     "Skapa ett nytt projekt/ärende i Projekt-fliken. Kräver projektnamn och beredare. "
     "Valfritt: fas (Beredning/Projektledning/Utförda), status (Planerat/Pågående/Klart), "
     "kund, omrade (C05/C12/C13), ib_nummer, anteckningar.",
     "input_schema": {"type": "object", "properties": {
         "projektnamn": {"type": "string"}, "beredare": {"type": "string"},
         "fas": {"type": "string"}, "status": {"type": "string"},
         "kund": {"type": "string"}, "omrade": {"type": "string"},
         "ib_nummer": {"type": "string"}, "anteckningar": {"type": "string"}},
         "required": ["projektnamn", "beredare"]}},
    {"name": "uppdatera_projekt", "description":
     "Uppdatera ett befintligt projekt via projektnummer. Ändra status, fas, beredare, kund, omrade, ib_nummer eller anteckningar.",
     "input_schema": {"type": "object", "properties": {
         "projektnummer": {"type": "string"},
         "status": {"type": "string"}, "fas": {"type": "string"},
         "beredare": {"type": "string"}, "kund": {"type": "string"},
         "omrade": {"type": "string"}, "ib_nummer": {"type": "string"},
         "anteckningar": {"type": "string"}}, "required": ["projektnummer"]}},
]

LAS_VERKTYG = {"projektoversikt", "sok_projekt", "projekt_detalj", "navigera"}
SKRIV_VERKTYG = {"skapa_projekt", "uppdatera_projekt"}


# ---- Verktygsutförande -> (text_till_modellen, ev. frontend-åtgärd) ----
def _kor(namn, inp):
    inp = inp or {}
    if namn == "projektoversikt":
        with get_db() as conn:
            tot = conn.execute("SELECT COUNT(*) FROM projekt").fetchone()[0]
            faser = {f: conn.execute("SELECT COUNT(*) FROM projekt WHERE fas=?", (f,)).fetchone()[0] for f in GILTIG_FAS}
            ingen = conn.execute("SELECT COUNT(*) FROM projekt WHERE fas IS NULL").fetchone()[0]
            ber = conn.execute("SELECT COALESCE(beredare,'okänd') b, COUNT(*) c FROM projekt GROUP BY beredare ORDER BY c DESC").fetchall()
        per_ber = "; ".join(f"{r['b']}: {r['c']}" for r in ber) or "inga"
        return (f"Totalt {tot} projekt. Per fas — Beredning: {faser['Beredning']}, "
                f"Projektledning: {faser['Projektledning']}, Utförda: {faser['Utförda']}, "
                f"utan fas: {ingen}. Per beredare — {per_ber}.", None)

    if namn == "sok_projekt":
        q = (inp.get("text") or "").strip()
        with get_db() as conn:
            rows = conn.execute(
                "SELECT projektnummer,projektnamn,beredare,fas,status FROM projekt "
                "WHERE projektnummer LIKE ? OR projektnamn LIKE ? OR ib_nummer LIKE ? "
                "OR beredare LIKE ? OR omrade LIKE ? ORDER BY skapad DESC LIMIT 15",
                tuple([f'%{q}%'] * 5)).fetchall()
        if not rows:
            return (f"Inga projekt matchade '{q}'.", None)
        lista = "\n".join(
            f"{r['projektnummer']} · {r['projektnamn']} · beredare {r['beredare']} "
            f"· fas {r['fas'] or '–'} · {r['status']}" for r in rows)
        return (f"{len(rows)} träffar:\n{lista}", None)

    if namn == "projekt_detalj":
        nr = (inp.get("projektnummer") or "").strip()
        with get_db() as conn:
            r = conn.execute("SELECT * FROM projekt WHERE projektnummer=?", (nr,)).fetchone()
        if not r:
            return (f"Hittade inget projekt med nummer {nr}.", None)
        d = dict(r)
        return (f"Projekt {d['projektnummer']} – {d['projektnamn']}. Beredare: {d.get('beredare')}. "
                f"Fas: {d.get('fas') or '–'}. Status: {d.get('status')}. Kund: {d.get('kund') or '–'}. "
                f"Område: {d.get('omrade') or '–'}. IB-nr: {d.get('ib_nummer') or '–'}. "
                f"Anteckningar: {d.get('anteckningar') or '–'}.", None)

    if namn == "navigera":
        vy = (inp.get("vy") or "").strip()
        if vy not in VYER:
            return (f"Ogiltig vy '{vy}'.", None)
        return (f"Öppnar fliken {vy}.", {"typ": "navigera", "vy": vy})

    if namn == "skapa_projekt":
        pnamn = (inp.get("projektnamn") or "").strip()
        beredare = (inp.get("beredare") or "").strip()
        if not pnamn or not beredare:
            return ("Saknar projektnamn eller beredare.", None)
        fas = (inp.get("fas") or "").strip() or None
        if fas and fas not in GILTIG_FAS:
            return (f"Ogiltig fas '{fas}'. Välj Beredning, Projektledning eller Utförda.", None)
        status = (inp.get("status") or "").strip()
        if status not in GILTIG_STATUS:
            status = "Planerat"
        t = nu(); idag = t[:10]
        with get_db() as conn:
            pnr = nasta_projektnummer(conn)
            conn.execute(
                "INSERT INTO projekt (projektnummer,projektnamn,beredare,status,fas,kund,omrade,"
                "ib_nummer,anteckningar,skapad,uppdaterad) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pnr, pnamn, beredare, status, fas,
                 (inp.get("kund") or "").strip() or None,
                 (inp.get("omrade") or "").strip() or None,
                 (inp.get("ib_nummer") or "").strip() or None,
                 (inp.get("anteckningar") or "").strip() or None, t, t))
            pid = conn.execute("SELECT id FROM projekt WHERE projektnummer=?", (pnr,)).fetchone()[0]
            if fas:
                conn.execute("INSERT INTO projekt_fas_datum (projekt_id,fas,startdatum,skapad) VALUES (?,?,?,?)",
                             (pid, fas, idag, t))
            conn.commit()
        return (f"Skapade projekt {pnr} – {pnamn} (beredare {beredare}"
                f"{', fas ' + fas if fas else ''}).", {"typ": "navigera", "vy": "projekt"})

    if namn == "uppdatera_projekt":
        nr = (inp.get("projektnummer") or "").strip()
        with get_db() as conn:
            r = conn.execute("SELECT id FROM projekt WHERE projektnummer=?", (nr,)).fetchone()
            if not r:
                return (f"Hittade inget projekt med nummer {nr}.", None)
            falt, vals, andrade = [], [], []
            for k in ("status", "fas", "beredare", "kund", "omrade", "ib_nummer", "anteckningar"):
                if inp.get(k) is not None:
                    v = str(inp[k]).strip()
                    if k == "fas" and v and v not in GILTIG_FAS:
                        return (f"Ogiltig fas '{v}'.", None)
                    if k == "status" and v and v not in GILTIG_STATUS:
                        return (f"Ogiltig status '{v}'. Välj Planerat, Pågående eller Klart.", None)
                    falt.append(f"{k}=?"); vals.append(v or None); andrade.append(k)
            if not falt:
                return ("Inga fält att uppdatera angavs.", None)
            vals += [nu(), r["id"]]
            conn.execute(f"UPDATE projekt SET {', '.join(falt)}, uppdaterad=? WHERE id=?", vals)
            conn.commit()
        return (f"Uppdaterade projekt {nr}: {', '.join(andrade)}.", {"typ": "navigera", "vy": "projekt"})

    return (f"Okänt verktyg: {namn}.", None)


def _serialisera(blocks):
    ut = []
    for b in blocks:
        if b.type == "text":
            ut.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            ut.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return ut


def _tool_uses(meddelande):
    c = meddelande.get("content")
    return [b for b in c if isinstance(b, dict) and b.get("type") == "tool_use"] if isinstance(c, list) else []


def chatta(messages, bekrafta, kontext):
    """Kör en chatt-runda. Returnerar {typ, text, messages, atgarder, bekrafta?}."""
    klient = _få_klient()
    system = _systemprompt(kontext)
    atgarder = []

    # Lös ut en väntande skriv-åtgärd (efter bekräftelse) – ge tool_result för ALLA tool_use i sista assistentmeddelandet
    if bekrafta and messages and messages[-1].get("role") == "assistant":
        godkand_id = bekrafta.get("tool_use_id")
        godkand = bool(bekrafta.get("godkand"))
        results = []
        for tu in _tool_uses(messages[-1]):
            if tu["id"] == godkand_id:
                if godkand:
                    txt, extra = _kor(tu["name"], tu["input"])
                    if extra:
                        atgarder.append(extra)
                else:
                    txt = "Användaren avbröt åtgärden."
            elif tu["name"] in LAS_VERKTYG:
                txt, extra = _kor(tu["name"], tu["input"])
                if extra:
                    atgarder.append(extra)
            else:
                txt = "Hoppade över (en åtgärd i taget)."
            results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": txt})
        if results:
            messages.append({"role": "user", "content": results})

    for _ in range(6):
        svar = klient.messages.create(model=MODELL, max_tokens=1024,
                                      system=system, tools=VERKTYG, messages=messages)
        assistent = _serialisera(svar.content)
        messages.append({"role": "assistant", "content": assistent})
        text = "".join(b["text"] for b in assistent if b["type"] == "text").strip()

        if svar.stop_reason != "tool_use":
            return {"typ": "svar", "text": text, "messages": messages, "atgarder": atgarder}

        # Finns en skriv-åtgärd? -> pausa för bekräftelse (utför inga verktyg ännu)
        skriv = next((b for b in assistent if b["type"] == "tool_use" and b["name"] in SKRIV_VERKTYG), None)
        if skriv:
            return {"typ": "bekrafta", "text": text,
                    "bekrafta": {"tool_use_id": skriv["id"], "verktyg": skriv["name"], "input": skriv["input"]},
                    "messages": messages, "atgarder": atgarder}

        # Endast läs-verktyg -> kör dem och fortsätt
        results = []
        for b in assistent:
            if b["type"] == "tool_use":
                txt, extra = _kor(b["name"], b["input"])
                if extra:
                    atgarder.append(extra)
                results.append({"type": "tool_result", "tool_use_id": b["id"], "content": txt})
        messages.append({"role": "user", "content": results})

    return {"typ": "svar", "text": "Jag fastnade i för många steg – prova att fråga igen.",
            "messages": messages, "atgarder": atgarder}
