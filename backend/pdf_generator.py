"""PDF-generering för byggprotokoll och materiallista."""
from io import BytesIO
from datetime import datetime
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Logotyp ──────────────────────────────────────────────────────────────────
_LOGO_PATH = os.path.join(os.path.dirname(__file__), 'static', 'oneco_logo.svg')
_logo_drawing = None

def _get_logo():
    global _logo_drawing
    if _logo_drawing is None:
        try:
            from svglib.svglib import svg2rlg
            drawing = svg2rlg(_LOGO_PATH)
            if drawing and drawing.width and drawing.height:
                _logo_drawing = drawing
            else:
                _logo_drawing = False
        except Exception as exc:
            import sys
            print(f"[PDF] Kunde inte ladda logo: {exc}", file=sys.stderr)
            _logo_drawing = False
    return _logo_drawing if _logo_drawing else None

# ── Färgpalett (projektpärm-tema) ────────────────────────────────────────────
PURPLE      = colors.HexColor('#5c2d90')   # Sektionsrubriker
PURPLE_DARK = colors.HexColor('#331751')   # Sidhuvud
PURPLE_MID  = colors.HexColor('#783cb6')   # Accentlinje / detaljer
PURPLE_LITE = colors.HexColor('#E8E3F5')   # Panelkant
PURPLE_PALE = colors.HexColor('#F5F2FA')   # Panelbakgrund
LIGHT_GRAY  = colors.HexColor('#F1F1F3')   # Tabellrader (alternativt)
MED_GRAY    = colors.HexColor('#C7C7CC')   # Kanter
DARK        = colors.HexColor('#19191E')   # Mörk text
GRAY        = colors.HexColor('#6B707A')   # Grå text (sidfot)
WHITE       = colors.white
GREEN       = colors.HexColor('#16a34a')
GREEN_LIGHT = colors.HexColor('#dcfce7')
GRAY_LIGHT  = colors.HexColor('#f1f5f9')

W, H = A4
MARGIN = 20 * mm


# ── Sidhuvud / Sidfot ────────────────────────────────────────────────────────

def _bygg_header_footer(canvas, doc, foretag, titel):
    canvas.saveState()

    # Lila topaccent (tunn rand längst upp, som projektpärmen)
    canvas.setFillColor(PURPLE_MID)
    canvas.rect(0, H - 3, W, 3, fill=1, stroke=0)

    # Mörklila huvudband
    canvas.setFillColor(PURPLE_DARK)
    canvas.rect(0, H - 22 * mm, W, 22 * mm - 3, fill=1, stroke=0)

    # Dokumenttitel (vänster, vit)
    canvas.setFillColor(WHITE)
    canvas.setFont('Helvetica-Bold', 14)
    canvas.drawString(MARGIN, H - 14 * mm, titel)

    # Höger sida: logotyp + företagsnamn
    logo = _get_logo()
    right_x = W - MARGIN
    if logo:
        from reportlab.graphics import renderPDF
        logo_h = 10 * mm
        scale  = logo_h / logo.height
        logo_w = logo.width * scale
        lx = right_x - logo_w
        ly = H - 22 * mm + 8 * mm
        canvas.translate(lx, ly)
        canvas.scale(scale, scale)
        renderPDF.draw(logo, canvas, 0, 0)
        canvas.scale(1 / scale, 1 / scale)
        canvas.translate(-lx, -ly)

    # Företagsnamn alltid synligt (under logotyp eller ensamt)
    canvas.setFillColor(WHITE)
    canvas.setFont('Helvetica-Bold' if not logo else 'Helvetica', 8 if logo else 10)
    canvas.drawRightString(right_x, H - 22 * mm + 3 * mm, foretag)

    # Sidfot – tunn linje + grå text (som projektpärmen)
    fy = 18
    canvas.setStrokeColor(MED_GRAY)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, fy + 10, W - MARGIN, fy + 10)
    canvas.setFillColor(GRAY)
    canvas.setFont('Helvetica', 7.5)
    canvas.drawString(MARGIN, fy, f"Utskrivet {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    canvas.drawRightString(W - MARGIN, fy, f"{titel}  |  Sida {doc.page}")

    canvas.restoreState()


# ── Stilar ───────────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    normal = ParagraphStyle('norm', parent=base['Normal'], fontSize=9, leading=12)
    small  = ParagraphStyle('small', parent=base['Normal'],
                            fontSize=8, textColor=GRAY, leading=11)
    cell   = ParagraphStyle('cell', parent=base['Normal'], fontSize=8, leading=10)
    label  = ParagraphStyle('label', parent=base['Normal'],
                            fontSize=8, textColor=PURPLE_DARK,
                            fontName='Helvetica-Bold', leading=11)
    return normal, small, cell, label


# ── Sektionsrubrik (lila fylld rektangel med vit text) ───────────────────────

def _sektion_rubrik(text, space_before=6):
    hdr_style = ParagraphStyle('sec_hdr', fontName='Helvetica-Bold',
                               fontSize=9, textColor=WHITE, leading=12)
    t = Table([[Paragraph(text, hdr_style)]],
              colWidths=[W - MARGIN * 2])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), PURPLE),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ]))
    return [Spacer(1, space_before * mm), t]


# ── Informationspanel (ljus bakgrund + lila vänsteraccent) ───────────────────

def _info_panel(rader):
    """rader = lista av (etikett, värde) tupler."""
    ACCENT_W = 4   # pixlar (lila vänsteraccent)
    COL_LABEL = 45 * mm
    COL_VALUE = W - MARGIN * 2 - COL_LABEL - ACCENT_W

    label_style = ParagraphStyle('il', fontName='Helvetica-Bold', fontSize=8,
                                 textColor=PURPLE_DARK, leading=11)
    value_style = ParagraphStyle('iv', fontName='Helvetica', fontSize=8,
                                 textColor=DARK, leading=11)

    inner_rows = [[Paragraph(e, label_style), Paragraph(str(v), value_style)]
                  for e, v in rader]

    inner = Table(inner_rows, colWidths=[COL_LABEL, COL_VALUE])
    inner.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), PURPLE_PALE),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('LINEBELOW',     (0, 0), (-1, -2), 0.4, MED_GRAY),
        ('BOX',           (0, 0), (-1, -1), 0.6, PURPLE_LITE),
    ]))

    # Lila vänsteraccent som en smal kolumn
    accent_cell = Table([['']], colWidths=[ACCENT_W],
                         rowHeights=[len(rader) * 17])
    accent_cell.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PURPLE),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    outer = Table([[accent_cell, inner]],
                  colWidths=[ACCENT_W, COL_LABEL + COL_VALUE])
    outer.setStyle(TableStyle([
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
    ]))
    return outer


# ── Materialtabell ───────────────────────────────────────────────────────────

def _material_tabell(rader, visa_pris=False, visa_enr=False):
    hdr_s = ParagraphStyle('mh', fontName='Helvetica-Bold', fontSize=8,
                            textColor=WHITE, leading=10)
    cel_s = ParagraphStyle('mc', fontName='Helvetica', fontSize=8,
                            textColor=DARK, leading=10)
    enr_s = ParagraphStyle('me', fontName='Helvetica', fontSize=7,
                            textColor=GRAY, leading=10)

    if visa_enr:
        header = ['Artikel', 'E-nummer', 'Kategori', 'Enhet', 'Antal']
        col_w  = [60 * mm, 28 * mm, 38 * mm, 16 * mm, 16 * mm]
    else:
        header = ['Artikel', 'Kategori', 'Enhet', 'Antal']
        col_w  = [80 * mm, 45 * mm, 20 * mm, 20 * mm]
    if visa_pris:
        header += ['À-pris', 'Totalt']
        col_w  += [20 * mm, 22 * mm]
    col_w[-1] = W - MARGIN * 2 - sum(col_w[:-1])

    rows = [[Paragraph(h, hdr_s) for h in header]]
    for r in rader:
        pris  = r.get('a_pris')
        antal = r.get('antal', 0)
        rad = [Paragraph(r.get('artikelnamn', ''), cel_s)]
        if visa_enr:
            rad.append(Paragraph(r.get('artikelnummer') or '–', enr_s))
        rad += [
            r.get('kategori', ''),
            r.get('enhet', ''),
            f"{antal:g}",
        ]
        if visa_pris:
            rad.append(f"{pris:.2f}" if pris else '–')
            rad.append(f"{pris * antal:.2f}" if pris else '–')
        rows.append(rad)

    t = Table(rows, colWidths=col_w, repeatRows=1)
    style = [
        ('BACKGROUND',    (0, 0), (-1, 0), PURPLE),
        ('TEXTCOLOR',     (0, 0), (-1, 0), WHITE),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('ALIGN',         (3, 0), (-1, -1), 'RIGHT'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID',          (0, 0), (-1, -1), 0.4, MED_GRAY),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
    ]
    for i, r in enumerate(rader, start=1):
        if r.get('manuell'):
            style.append(('TEXTCOLOR', (0, i), (-1, i), colors.HexColor('#b45309')))
    t.setStyle(TableStyle(style))
    return t


# ── Egenkontrolltabell ───────────────────────────────────────────────────────

def _egenkontroll_tabell(egenkontroll):
    hdr_s  = ParagraphStyle('eh', fontName='Helvetica-Bold', fontSize=8,
                             textColor=WHITE, leading=11)
    cel_s  = ParagraphStyle('ec', fontName='Helvetica', fontSize=8,
                             textColor=DARK, leading=11)

    col_w = [8 * mm, None, 18 * mm, 18 * mm]
    col_w[1] = W - MARGIN * 2 - sum(x for x in col_w if x)

    header = [Paragraph(h, hdr_s)
              for h in ['#', 'Kontrollpunkt', 'Utförd', 'Ej rel.']]
    rows = [header]
    for i, e in enumerate(egenkontroll, start=1):
        utford = 'Ja' if e.get('utford')      else ''
        ej_rel = 'Ja' if e.get('ej_relevant') else ''
        rows.append([str(i), Paragraph(e.get('punkt', ''), cel_s), utford, ej_rel])

    t = Table(rows, colWidths=col_w, repeatRows=1)
    style = [
        ('BACKGROUND',    (0, 0), (-1, 0), PURPLE),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('ALIGN',         (0, 0), (0, -1), 'CENTER'),
        ('ALIGN',         (2, 0), (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID',          (0, 0), (-1, -1), 0.4, MED_GRAY),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
    ]
    for i, e in enumerate(egenkontroll, start=1):
        if e.get('utford'):
            style += [('BACKGROUND', (2, i), (2, i), GREEN_LIGHT),
                      ('TEXTCOLOR',  (2, i), (2, i), GREEN),
                      ('FONTNAME',   (2, i), (2, i), 'Helvetica-Bold')]
        if e.get('ej_relevant'):
            style += [('BACKGROUND', (3, i), (3, i), GRAY_LIGHT),
                      ('TEXTCOLOR',  (3, i), (3, i), GRAY)]
    t.setStyle(TableStyle(style))
    return t


# ── Underskrift ──────────────────────────────────────────────────────────────

def _underskrift():
    sign = Table(
        [['Utförd av:', '_' * 35, 'Datum:', '_' * 20]],
        colWidths=[25 * mm, 75 * mm, 20 * mm, 45 * mm]
    )
    sign.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('FONTNAME',      (0, 0), (0,  0),  'Helvetica-Bold'),
        ('FONTNAME',      (2, 0), (2,  0),  'Helvetica-Bold'),
        ('TEXTCOLOR',     (0, 0), (0,  0),  PURPLE_DARK),
        ('TEXTCOLOR',     (2, 0), (2,  0),  PURPLE_DARK),
        ('ALIGN',         (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [
        Spacer(1, 10 * mm),
        HRFlowable(width='100%', thickness=0.6, color=MED_GRAY),
        Spacer(1, 3 * mm),
        sign,
    ]


# ── BYGGPROTOKOLL PDF ─────────────────────────────────────────────────────────

def skapa_byggprotokoll_pdf(protokoll, projekt, installningar):
    foretag = installningar.get('foretagsnamn',
               installningar.get('foretag_namn', 'Oneco Networks AB'))
    buf = BytesIO()

    def on_page(canvas, doc):
        _bygg_header_footer(canvas, doc, foretag, 'Byggprotokoll')

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=28 * mm, bottomMargin=16 * mm,
    )

    normal, small, cell, label = _styles()
    story = []

    # ── Projektinfo ──
    story += _sektion_rubrik('Projektinformation', space_before=2)
    pi_rader = [
        ('Projektnummer:',  projekt.get('projektnummer', '')),
        ('Projektnamn:',    projekt.get('projektnamn', '')),
        ('Beredare:',       projekt.get('beredare', '')),
        ('Status:',         projekt.get('status', '')),
        ('Startdatum:',     projekt.get('startdatum', '') or '–'),
        ('Mall:',           protokoll.get('mall_namn', '')),
        ('Protokollstatus:',protokoll.get('status', '')),
        ('Skapad:',         (protokoll.get('skapad', '') or '')[:16]),
        ('Uppdaterad:',     (protokoll.get('uppdaterad', '') or '')[:16]),
    ]
    if protokoll.get('anteckningar'):
        pi_rader.append(('Anteckning:', protokoll['anteckningar']))
    story.append(Spacer(1, 1 * mm))
    story.append(_info_panel(pi_rader))

    # ── Material ──
    rader = protokoll.get('rader', [])
    story += _sektion_rubrik('Material')
    if rader:
        story.append(Spacer(1, 1 * mm))
        story.append(_material_tabell(rader, visa_pris=False))
    else:
        story.append(Spacer(1, 1 * mm))
        story.append(Paragraph('Inga materialrader registrerade.', small))

    # ── Egenkontroll ──
    egenkontroll = protokoll.get('egenkontroll', [])
    if egenkontroll:
        story += _sektion_rubrik('Egenkontroll')
        story.append(Spacer(1, 1 * mm))
        story.append(_egenkontroll_tabell(egenkontroll))
        utforda = sum(1 for e in egenkontroll if e.get('utford'))
        ej_rel  = sum(1 for e in egenkontroll if e.get('ej_relevant'))
        totalt  = len(egenkontroll)
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            f"Utförda: {utforda}/{totalt}  |  Ej relevanta: {ej_rel}", small))

    story += _underskrift()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


# ── MATERIALLISTA PDF (projekt) ───────────────────────────────────────────────

def skapa_materiallista_pdf(projekt, protokoll_lista, installningar, enr_lookup=None):
    foretag = installningar.get('foretagsnamn',
               installningar.get('foretag_namn', 'Oneco Networks AB'))
    buf = BytesIO()

    def on_page(canvas, doc):
        _bygg_header_footer(canvas, doc, foretag, 'Materiallista')

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=28 * mm, bottomMargin=16 * mm,
    )

    normal, small, cell, label = _styles()
    story = []

    # ── Projektinfo ──
    story += _sektion_rubrik('Projektinformation', space_before=2)
    pi_rader = [
        ('Projektnummer:',    projekt.get('projektnummer', '')),
        ('Projektnamn:',      projekt.get('projektnamn', '')),
        ('Beredare:',         projekt.get('beredare', '')),
        ('Antal protokoll:',  str(len(protokoll_lista))),
    ]
    story.append(Spacer(1, 1 * mm))
    story.append(_info_panel(pi_rader))

    # Aggregera per artikel
    aggregat = {}
    for bp in protokoll_lista:
        for r in bp.get('rader', []):
            key = (r.get('artikel_id'), r.get('artikelnamn', ''))
            if key not in aggregat:
                aggregat[key] = {**r, 'antal': 0.0, 'manuell': 0}
            aggregat[key]['antal'] += r.get('antal', 0)

    # Berika med E-nummer efter aggregering (samma mönster som Excel-exporten)
    if enr_lookup:
        for row in aggregat.values():
            if not row.get('artikelnummer'):
                row['artikelnummer'] = enr_lookup.get(row.get('artikelnamn', ''))

    sorterade = sorted(aggregat.values(),
                       key=lambda x: (x['kategori'], x['artikelnamn']))

    if not sorterade:
        story += _sektion_rubrik('Material')
        story.append(Spacer(1, 1 * mm))
        story.append(Paragraph('Inga materialrader finns för detta projekt.', small))
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
        return buf.getvalue()

    # Gruppera per kategori
    grupper = {}
    for r in sorterade:
        grupper.setdefault(r['kategori'] or 'Övrigt', []).append(r)

    for kat, rader in grupper.items():
        story += _sektion_rubrik(kat)
        story.append(Spacer(1, 1 * mm))
        story.append(_material_tabell(rader, visa_pris=False, visa_enr=True))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


# ── KONSTRUKTIONER MATERIALLISTA PDF ─────────────────────────────────────────

def skapa_konstruktioner_materiallista_pdf(konstruktioner, installningar):
    foretag = installningar.get('foretagsnamn',
               installningar.get('foretag_namn', 'Oneco Networks AB'))
    buf = BytesIO()

    def on_page(canvas, doc):
        _bygg_header_footer(canvas, doc, foretag, 'Materiallista')

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=28 * mm, bottomMargin=16 * mm,
    )

    normal, small, cell, label = _styles()
    story = []

    antal_konstr   = len(konstruktioner)
    antal_med_rad  = sum(1 for k in konstruktioner if k.get('rader'))

    story += _sektion_rubrik('Sammanställning', space_before=2)
    story.append(Spacer(1, 1 * mm))
    story.append(_info_panel([
        ('Antal protokoll:', str(antal_konstr)),
        ('Med material:',    str(antal_med_rad)),
    ]))

    typer_ordning = ['Kabelskåp', 'Kabelförläggning', 'Nätstation', 'Övrigt']
    grupper = {}
    for k in konstruktioner:
        grupper.setdefault(k.get('typ', 'Övrigt'), []).append(k)

    sorterade_typer  = [t for t in typer_ordning if t in grupper]
    sorterade_typer += [t for t in grupper if t not in sorterade_typer]

    hdr_s = ParagraphStyle('kh', fontName='Helvetica-Bold', fontSize=8,
                            textColor=WHITE, leading=10)
    cel_s = ParagraphStyle('kc', fontName='Helvetica', fontSize=8,
                            textColor=DARK, leading=10)
    anv_s = ParagraphStyle('ka', fontName='Helvetica', fontSize=7,
                            textColor=GRAY, leading=9)

    har_innehall = False
    for typ in sorterade_typer:
        aggregat = {}
        for k in grupper[typ]:
            for r in k.get('rader', []):
                key = r.get('artikelnamn', '').strip()
                if not key:
                    continue
                if key not in aggregat:
                    aggregat[key] = {'artikelnamn': key,
                                     'enhet': r.get('enhet', ''),
                                     'antal': 0.0, 'konstruktioner': []}
                aggregat[key]['antal'] += float(r.get('antal', 0) or 0)
                knamn = k.get('namn', '')
                if knamn not in aggregat[key]['konstruktioner']:
                    aggregat[key]['konstruktioner'].append(knamn)

        if not aggregat:
            continue

        har_innehall = True
        story += _sektion_rubrik(typ)

        col_anvands = 65 * mm
        col_enhet   = 18 * mm
        col_antal   = 18 * mm
        col_artikel = W - MARGIN * 2 - col_enhet - col_antal - col_anvands
        col_w = [col_artikel, col_enhet, col_antal, col_anvands]

        rows = [[Paragraph(h, hdr_s)
                 for h in ['Artikel', 'Enhet', 'Antal', 'Används i']]]
        for art in sorted(aggregat.values(), key=lambda x: x['artikelnamn']):
            anv = ', '.join(art['konstruktioner'][:5])
            if len(art['konstruktioner']) > 5:
                anv += f" +{len(art['konstruktioner'])-5} till"
            rows.append([
                Paragraph(art['artikelnamn'], cel_s),
                art['enhet'],
                f"{art['antal']:g}",
                Paragraph(anv, anv_s),
            ])

        t = Table(rows, colWidths=col_w, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), PURPLE),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 8),
            ('ALIGN',         (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID',          (0, 0), (-1, -1), 0.4, MED_GRAY),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ]))
        story.append(Spacer(1, 1 * mm))
        story.append(t)

    if not har_innehall:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph('Inga materialrader finns för några konstruktioner.', small))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


# ── BYGGPROTOKOLL (Konstruktion) PDF ─────────────────────────────────────────

def skapa_konstruktion_pdf(konstruktion, installningar):
    foretag = installningar.get('foretagsnamn',
               installningar.get('foretag_namn', 'Oneco Networks AB'))
    buf = BytesIO()

    def on_page(canvas, doc):
        _bygg_header_footer(canvas, doc, foretag, 'Byggprotokoll')

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=28 * mm, bottomMargin=16 * mm,
    )

    normal, small, cell, label = _styles()
    story = []

    # ── Info ──
    story += _sektion_rubrik('Konstruktionsinformation', space_before=2)
    pi = [
        ('Typ:',       konstruktion.get('typ', '')),
        ('Byggnr:',    konstruktion.get('byggnr', '') or '–'),
        ('Namn:',      konstruktion.get('namn', '')),
        ('Fri ID:',    konstruktion.get('fri_id', '') or '–'),
        ('Status:',    konstruktion.get('status', '')),
        ('Datum:',     (konstruktion.get('skapad', '') or '')[:16]),
    ]
    if konstruktion.get('anmarkning'):
        pi.append(('Anmärkning:', konstruktion['anmarkning']))
    story.append(Spacer(1, 1 * mm))
    story.append(_info_panel(pi))

    # ── Material ──
    rader = konstruktion.get('rader', [])
    story += _sektion_rubrik('Material')
    story.append(Spacer(1, 1 * mm))

    if rader:
        hdr_s = ParagraphStyle('bh', fontName='Helvetica-Bold', fontSize=8,
                               textColor=WHITE, leading=10)
        cel_s = ParagraphStyle('bc', fontName='Helvetica', fontSize=8,
                               textColor=DARK, leading=10)

        col_w = [100 * mm, 22 * mm, 22 * mm, 22 * mm]
        col_w[-1] = W - MARGIN * 2 - sum(col_w[:-1])

        rows = [[Paragraph(h, hdr_s) for h in ['Artikel', 'Enhet', 'Antal', 'Moduler']]]
        for r in rader:
            moduler_val = r.get('moduler', 0)
            rows.append([
                Paragraph(r.get('artikelnamn', ''), cel_s),
                r.get('enhet', ''),
                f"{r.get('antal', 0):g}",
                str(int(moduler_val)) if moduler_val else '-',
            ])

        t = Table(rows, colWidths=col_w, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), PURPLE),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 8),
            ('ALIGN',         (2, 0), (-1, -1), 'RIGHT'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID',          (0, 0), (-1, -1), 0.4, MED_GRAY),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ]))
        story.append(t)

    else:
        story.append(Paragraph('Inga materialrader registrerade.', small))

    # ── Egenkontroll ──
    egenkontroll = konstruktion.get('egenkontroll', [])
    if egenkontroll:
        story += _sektion_rubrik('Egenkontroll')
        story.append(Spacer(1, 1 * mm))
        story.append(_egenkontroll_tabell(egenkontroll))
        utforda = sum(1 for e in egenkontroll if e.get('utford'))
        ej_rel  = sum(1 for e in egenkontroll if e.get('ej_relevant'))
        totalt  = len(egenkontroll)
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            f"Utförda: {utforda}/{totalt}  |  Ej relevanta: {ej_rel}", small))

    story += _underskrift()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
