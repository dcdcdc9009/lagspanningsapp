"""PDF-generering för byggprotokoll och materiallista."""
from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus.frames import Frame
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

NAVY  = colors.HexColor('#1a3a5c')
LIGHT = colors.HexColor('#e8f0f8')
GRAY  = colors.HexColor('#666666')
WHITE = colors.white
BLACK = colors.black

W, H = A4
MARGIN = 20 * mm


# ----------------------------------------------------------------
# SIDFOT / HEADER canvas
# ----------------------------------------------------------------

def _bygg_header_footer(canvas, doc, foretag, titel):
    canvas.saveState()
    # Toppbanderoll
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 22 * mm, W, 22 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont('Helvetica-Bold', 13)
    canvas.drawString(MARGIN, H - 14 * mm, titel)
    canvas.setFont('Helvetica', 9)
    canvas.drawRightString(W - MARGIN, H - 14 * mm, foretag)

    # Sidfot
    canvas.setFillColor(LIGHT)
    canvas.rect(0, 0, W, 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(GRAY)
    canvas.setFont('Helvetica', 8)
    canvas.drawString(MARGIN, 4 * mm, f"Utskrivet {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    canvas.drawCentredString(W / 2, 4 * mm, foretag)
    canvas.drawRightString(W - MARGIN, 4 * mm, f"Sida {doc.page}")
    canvas.restoreState()


# ----------------------------------------------------------------
# HJÄLPFUNKTIONER
# ----------------------------------------------------------------

def _styles():
    base = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=base['Normal'],
                         fontSize=12, textColor=NAVY, leading=16,
                         spaceAfter=4, fontName='Helvetica-Bold')
    normal = ParagraphStyle('norm', parent=base['Normal'],
                             fontSize=9, leading=12)
    small = ParagraphStyle('small', parent=base['Normal'],
                            fontSize=8, textColor=GRAY, leading=11)
    cell = ParagraphStyle('cell', parent=base['Normal'],
                           fontSize=8, leading=10)
    return h1, normal, small, cell


def _info_tabell(data, col_w=None):
    """2-kolumns info-tabell (etikett: värde)."""
    if col_w is None:
        col_w = [55 * mm, 105 * mm]
    t = Table(data, colWidths=col_w)
    t.setStyle(TableStyle([
        ('FONTNAME',  (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',  (0, 0), (-1, -1), 9),
        ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), NAVY),
        ('VALIGN',    (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    return t


def _material_tabell(rader, visa_pris=True):
    """Materialtabell med samtliga rader."""
    header = ['Artikel', 'Kategori', 'Enhet', 'Antal']
    col_w  = [75 * mm, 40 * mm, 20 * mm, 20 * mm]
    if visa_pris:
        header += ['À-pris', 'Totalt']
        col_w  += [20 * mm, 22 * mm]
    col_w[-1] = W - MARGIN * 2 - sum(col_w[:-1])

    rows = [header]
    for r in rader:
        pris = r.get('a_pris')
        antal = r.get('antal', 0)
        rad = [
            r.get('artikelnamn', ''),
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
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR',  (0, 0), (-1, 0), WHITE),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 8),
        ('ALIGN',      (3, 0), (-1, -1), 'RIGHT'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('GRID',       (0, 0), (-1, -1), 0.25, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT]),
    ]
    # Markera manuella rader
    for i, r in enumerate(rader, start=1):
        if r.get('manuell'):
            style.append(('TEXTCOLOR', (0, i), (-1, i), colors.HexColor('#8B4513')))
    t.setStyle(TableStyle(style))
    return t


# ----------------------------------------------------------------
# BYGGPROTOKOLL PDF
# ----------------------------------------------------------------

def skapa_byggprotokoll_pdf(protokoll, projekt, installningar):
    """
    protokoll: dict med alla fält + 'rader' lista
    projekt:   dict med projektnummer, projektnamn, beredare, status
    installningar: dict  {nyckel: varde}
    Returnerar bytes.
    """
    foretag = installningar.get('foretag_namn', 'Lågspänningsberedning')
    buf = BytesIO()

    def on_page(canvas, doc):
        _bygg_header_footer(canvas, doc, foretag, 'Byggprotokoll')

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=28 * mm, bottomMargin=18 * mm,
        onFirstPage=on_page, onLaterPages=on_page,
    )

    h1, normal, small, cell = _styles()
    story = []

    # Projektrubrik
    story.append(Paragraph(
        f"{projekt.get('projektnummer', '')} – {projekt.get('projektnamn', '')}",
        h1
    ))
    story.append(HRFlowable(width='100%', thickness=1, color=NAVY, spaceAfter=6))

    # Projektinfo + protokollinfo sida vid sida
    pi = [
        ['Projektnummer:', projekt.get('projektnummer', '')],
        ['Projektnamn:',   projekt.get('projektnamn', '')],
        ['Beredare:',      projekt.get('beredare', '')],
        ['Status:',        projekt.get('status', '')],
        ['Startdatum:',    projekt.get('startdatum', '') or '–'],
    ]
    bp = [
        ['Mall:',         protokoll.get('mall_namn', '')],
        ['Prot.-status:', protokoll.get('status', '')],
        ['Skapad:',       (protokoll.get('skapad', '') or '')[:16]],
        ['Uppdaterad:',   (protokoll.get('uppdaterad', '') or '')[:16]],
    ]
    if protokoll.get('anteckningar'):
        bp.append(['Anteckning:', protokoll['anteckningar']])

    left  = _info_tabell(pi, col_w=[42 * mm, 48 * mm])
    right = _info_tabell(bp, col_w=[38 * mm, 47 * mm])
    combo = Table([[left, right]], colWidths=[95 * mm, 90 * mm])
    combo.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(combo)
    story.append(Spacer(1, 8 * mm))

    # Materialrader
    rader = protokoll.get('rader', [])
    if rader:
        story.append(Paragraph('Material', h1))
        story.append(_material_tabell(rader, visa_pris=True))
    else:
        story.append(Paragraph('Inga materialrader registrerade.', small))

    # Totalsumma
    total = sum(
        (r.get('a_pris') or 0) * (r.get('antal') or 0)
        for r in rader if r.get('a_pris')
    )
    if total:
        story.append(Spacer(1, 4 * mm))
        tot_rad = [['', '', '', '', 'Totalt:', f"{total:.2f} kr"]]
        t = Table(tot_rad, colWidths=[75*mm, 40*mm, 20*mm, 20*mm, 20*mm, None])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN',    (4, 0), (-1, -1), 'RIGHT'),
            ('TEXTCOLOR',(4, 0), (-1, -1), NAVY),
        ]))
        story.append(t)

    # Underskrift
    story.append(Spacer(1, 12 * mm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GRAY))
    story.append(Spacer(1, 2 * mm))
    sign = Table(
        [['Utförd av:', '_' * 35, 'Datum:', '_' * 20]],
        colWidths=[25 * mm, 75 * mm, 20 * mm, 45 * mm]
    )
    sign.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
        ('ALIGN',    (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(sign)

    doc.build(story)
    return buf.getvalue()


# ----------------------------------------------------------------
# MATERIALLISTA PDF  (aggregerad för hela projektet)
# ----------------------------------------------------------------

def skapa_materiallista_pdf(projekt, protokoll_lista, installningar):
    """
    projekt:         dict
    protokoll_lista: lista av dicts, varje med 'rader'
    installningar:   dict
    Returnerar bytes.
    """
    foretag = installningar.get('foretag_namn', 'Lågspänningsberedning')
    buf = BytesIO()

    def on_page(canvas, doc):
        _bygg_header_footer(canvas, doc, foretag, 'Materiallista')

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=28 * mm, bottomMargin=18 * mm,
        onFirstPage=on_page, onLaterPages=on_page,
    )

    h1, normal, small, cell = _styles()
    story = []

    # Projektrubrik
    story.append(Paragraph(
        f"{projekt.get('projektnummer', '')} – {projekt.get('projektnamn', '')}",
        h1
    ))
    story.append(HRFlowable(width='100%', thickness=1, color=NAVY, spaceAfter=4))
    pi = [
        ['Projektnummer:', projekt.get('projektnummer', '')],
        ['Projektnamn:',   projekt.get('projektnamn', '')],
        ['Beredare:',      projekt.get('beredare', '')],
        ['Antal protokoll:', str(len(protokoll_lista))],
    ]
    story.append(_info_tabell(pi))
    story.append(Spacer(1, 6 * mm))

    # Aggregera rader per artikel_id + artikelnamn
    aggregat = {}
    for bp in protokoll_lista:
        for r in bp.get('rader', []):
            key = (r.get('artikel_id'), r.get('artikelnamn', ''))
            if key not in aggregat:
                aggregat[key] = {
                    'artikel_id':      r.get('artikel_id'),
                    'artikelnamn':     r.get('artikelnamn', ''),
                    'kategori':        r.get('kategori', ''),
                    'enhet':           r.get('enhet', ''),
                    'antal':           0.0,
                    'a_pris':          r.get('a_pris'),
                    'leverantor_namn': r.get('leverantor_namn'),
                    'artikelnummer':   r.get('artikelnummer'),
                    'manuell':         0,
                }
            aggregat[key]['antal'] += r.get('antal', 0)

    # Sortera per kategori, sedan artikelnamn
    sorterade = sorted(aggregat.values(), key=lambda x: (x['kategori'], x['artikelnamn']))

    if not sorterade:
        story.append(Paragraph('Inga materialrader finns för detta projekt.', small))
        doc.build(story)
        return buf.getvalue()

    # Gruppera per kategori
    kategori_grupper = {}
    for r in sorterade:
        kat = r['kategori'] or 'Övrigt'
        kategori_grupper.setdefault(kat, []).append(r)

    grand_total = 0.0

    for kat, rader in kategori_grupper.items():
        story.append(Paragraph(kat, h1))
        story.append(_material_tabell(rader, visa_pris=True))

        kat_total = sum(
            (r.get('a_pris') or 0) * (r.get('antal') or 0)
            for r in rader if r.get('a_pris')
        )
        grand_total += kat_total
        if kat_total:
            tot_rad = [['', '', '', '', 'Delsumma:', f"{kat_total:.2f} kr"]]
            t = Table(tot_rad, colWidths=[75*mm, 40*mm, 20*mm, 20*mm, 20*mm, None])
            t.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN',    (4, 0), (-1, -1), 'RIGHT'),
                ('TEXTCOLOR',(4, 0), (-1, -1), GRAY),
            ]))
            story.append(t)
        story.append(Spacer(1, 6 * mm))

    # Totalsumma
    if grand_total:
        story.append(HRFlowable(width='100%', thickness=1, color=NAVY))
        story.append(Spacer(1, 2 * mm))
        tot = Table(
            [['', '', '', '', 'TOTALT:', f"{grand_total:.2f} kr"]],
            colWidths=[75*mm, 40*mm, 20*mm, 20*mm, 20*mm, None]
        )
        tot.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN',    (4, 0), (-1, -1), 'RIGHT'),
            ('TEXTCOLOR',(4, 0), (-1, -1), NAVY),
        ]))
        story.append(tot)

    doc.build(story)
    return buf.getvalue()
