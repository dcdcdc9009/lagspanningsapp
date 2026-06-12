"""Ruttoptimering för fältservice – ren Python, ingen extern lösare.

Heuristik:
  1. Tilldelning via regret-baserad billigaste insättning (respekterar
     kompetens, tidsfönster, servicetid och teknikerns arbetstid).
  2. Förbättring via 2-opt inom rutt + relocate mellan rutter (tidsboxad).
  3. Ärenden som inte får plats hamnar i ej_placerade med orsak.

Mål: minimera total körtid. Sekundärt jämnas belastningen via regret-ordningen.

Tidsenhet: minuter från midnatt. matris: NxN restid i SEKUNDER.
"""
import time
import threading

OPT_LOCK = threading.Lock()


def _tt_min(matris, a, b):
    return matris[a][b] / 60.0


def _timing(seq, tek, matris):
    """Simulera en rutt. Returnerar {'drive','arrivals'} eller None om ogenomförbar."""
    t = tek['start_min']
    prev = tek['dep_start']
    drive = 0.0
    arrivals = []
    for a in seq:
        dr = _tt_min(matris, prev, a['pt'])
        drive += dr
        ank = t + dr
        start = ank if a['wf'] is None else max(ank, a['wf'])
        if a['wt'] is not None and start > a['wt'] + 1e-6:
            return None
        arrivals.append(start)
        t = start + a['service']
        prev = a['pt']
    drive += _tt_min(matris, prev, tek['dep_end'])
    if t + _tt_min(matris, prev, tek['dep_end']) > tek['end_min'] + 1e-6:
        return None
    return {'drive': drive, 'arrivals': arrivals}


def _basta_insattning(a, tek, seq, matris):
    """Billigaste genomförbara position för ärende a i teknikerns rutt.

    Returnerar (kostnad, pos) eller None."""
    if not a['krav'] <= tek['skills']:
        return None
    bas = _timing(seq, tek, matris)
    if bas is None:
        return None
    best = None
    for pos in range(len(seq) + 1):
        ny = seq[:pos] + [a] + seq[pos:]
        tm = _timing(ny, tek, matris)
        if tm is None:
            continue
        kostnad = tm['drive'] - bas['drive']
        if best is None or kostnad < best[0]:
            best = (kostnad, pos)
    return best


def _forbattra(rutter, tmap, matris, tidsbudget=2.0):
    start = time.time()
    forbattrad = True
    while forbattrad and time.time() - start < tidsbudget:
        forbattrad = False
        # 2-opt inom varje rutt
        for tid in list(rutter):
            seq = rutter[tid]
            if len(seq) < 3:
                continue
            tek = tmap[tid]
            base = _timing(seq, tek, matris)
            if base is None:
                continue
            base = base['drive']
            for i in range(len(seq) - 1):
                for k in range(i + 1, len(seq)):
                    ny = seq[:i] + seq[i:k + 1][::-1] + seq[k + 1:]
                    tm = _timing(ny, tek, matris)
                    if tm and tm['drive'] < base - 1e-6:
                        rutter[tid] = seq = ny
                        base = tm['drive']
                        forbattrad = True
            if time.time() - start > tidsbudget:
                return
        # relocate mellan rutter (starta om vid första förbättring)
        flyttad = False
        for tid_a in list(rutter):
            for ai in range(len(rutter[tid_a])):
                a = rutter[tid_a][ai]
                seqa = rutter[tid_a][:ai] + rutter[tid_a][ai + 1:]
                ta = _timing(seqa, tmap[tid_a], matris)
                if ta is None:
                    continue
                fore_a = _timing(rutter[tid_a], tmap[tid_a], matris)['drive']
                for tid_b in rutter:
                    if tid_b == tid_a:
                        continue
                    tekb = tmap[tid_b]
                    ins = _basta_insattning(a, tekb, rutter[tid_b], matris)
                    if ins is None:
                        continue
                    fore_b = _timing(rutter[tid_b], tekb, matris)['drive']
                    seqb = rutter[tid_b][:ins[1]] + [a] + rutter[tid_b][ins[1]:]
                    efter = ta['drive'] + _timing(seqb, tekb, matris)['drive']
                    if efter < fore_a + fore_b - 1e-6:
                        rutter[tid_a] = seqa
                        rutter[tid_b] = seqb
                        flyttad = forbattrad = True
                        break
                if flyttad:
                    break
            if flyttad or time.time() - start > tidsbudget:
                break


def berakna_rutt(seq, tek, matris):
    """Mjuk timing för en (manuellt satt) rutt – failar aldrig, flaggar problem.

    Returnerar {arrivals, drive, slut, sena:[ärende-id], over_arbetstid:bool}."""
    t = tek['start_min']
    prev = tek['dep_start']
    drive = 0.0
    arrivals = []
    sena = []
    for a in seq:
        dr = _tt_min(matris, prev, a['pt'])
        drive += dr
        ank = t + dr
        start = ank if a['wf'] is None else max(ank, a['wf'])
        if a['wt'] is not None and start > a['wt'] + 1e-6:
            sena.append(a['id'])
        arrivals.append(start)
        t = start + a['service']
        prev = a['pt']
    back = _tt_min(matris, prev, tek['dep_end'])
    drive += back
    slut = t + back
    return {'arrivals': arrivals, 'drive': drive, 'slut': slut,
            'sena': sena, 'over_arbetstid': slut > tek['end_min'] + 1e-6}


def optimera(tekniker, arenden, matris, tidsbudget=2.0):
    """Tilldela ärenden till tekniker + körordning.

    tekniker: [{id, namn, skills:set, start_min, end_min, dep_start, dep_end}]
    arenden:  [{id, pt, service, wf, wt, krav:set}]
    matris:   NxN restid i sekunder.

    Returnerar {rutter: {tid:[arende...]}, ankomster:{aid:min}, ej_placerade:[{id,orsak}]}.
    """
    with OPT_LOCK:
        tmap = {t['id']: t for t in tekniker}
        rutter = {t['id']: [] for t in tekniker}
        oplacerade = list(arenden)

        # Regret-insättning
        while oplacerade:
            kandidater = []
            for a in oplacerade:
                ks = []
                for tek in tekniker:
                    b = _basta_insattning(a, tek, rutter[tek['id']], matris)
                    if b is not None:
                        ks.append((b[0], tek['id'], b[1]))
                if not ks:
                    continue
                ks.sort()
                bast = ks[0]
                nast = ks[1][0] if len(ks) > 1 else bast[0] + 1e6
                kandidater.append((nast - bast[0], -bast[0], a, bast[1], bast[2]))
            if not kandidater:
                break
            kandidater.sort(key=lambda x: (x[0], x[1]), reverse=True)
            _, _, a, tid, pos = kandidater[0]
            rutter[tid].insert(pos, a)
            oplacerade.remove(a)

        # Förbättring
        if any(rutter.values()):
            _forbattra(rutter, tmap, matris, tidsbudget)

        # Ankomsttider
        ankomster = {}
        for tid, seq in rutter.items():
            tm = _timing(seq, tmap[tid], matris)
            if tm:
                for a, ank in zip(seq, tm['arrivals']):
                    ankomster[a['id']] = int(round(ank))

        # Ej placerade – orsak
        ej = []
        for a in oplacerade:
            if not any(a['krav'] <= t['skills'] for t in tekniker):
                orsak = 'Ingen tekniker har rätt kompetens'
            elif not any(a['krav'] <= t['skills'] and _timing([a], t, matris)
                         for t in tekniker):
                orsak = 'Tidsfönster eller arbetstid omöjligt'
            else:
                orsak = 'Fick inte plats i någon rutt'
            ej.append({'id': a['id'], 'orsak': orsak})

        return {
            'rutter': {tid: [a['id'] for a in seq] for tid, seq in rutter.items()},
            'ankomster': ankomster,
            'ej_placerade': ej,
        }
