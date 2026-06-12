"""Enhetstester för ruttopt – körs direkt: python test_ruttopt.py"""
from ruttopt import optimera


def matris(n, restid_min=10):
    """NxN symmetrisk matris i sekunder, restid_min mellan alla skilda punkter."""
    return [[0 if i == j else restid_min * 60 for j in range(n)] for i in range(n)]


def tek(id, skills=(), start='07:00', slut='16:00', dep=0):
    def m(s):
        h, mi = s.split(':'); return int(h) * 60 + int(mi)
    return {'id': id, 'namn': f'T{id}', 'skills': set(skills),
            'start_min': m(start), 'end_min': m(slut), 'dep_start': dep, 'dep_end': dep}


def ar(id, pt, service=30, wf=None, wt=None, krav=()):
    def m(s):
        if s is None: return None
        h, mi = s.split(':'); return int(h) * 60 + int(mi)
    return {'id': id, 'pt': pt, 'service': service, 'wf': m(wf), 'wt': m(wt), 'krav': set(krav)}


def antal_placerade(res):
    return sum(len(v) for v in res['rutter'].values())


def test_grund():
    # 1 tekniker, 2 ärenden – båda ska placeras
    res = optimera([tek(1, dep=0)], [ar('A', 1), ar('B', 2)], matris(3))
    assert antal_placerade(res) == 2, res
    assert not res['ej_placerade'], res
    print('OK  grund: båda placerade')


def test_kompetens():
    # A kräver 'el' som bara T2 har
    res = optimera([tek(1, skills=['vatten']), tek(2, skills=['el'])],
                   [ar('A', 1, krav=['el'])], matris(2))
    assert res['rutter'][2] == ['A'], res
    assert res['rutter'][1] == [], res
    print('OK  kompetens: hamnade hos rätt tekniker')


def test_kompetens_saknas():
    res = optimera([tek(1, skills=['el'])], [ar('A', 1, krav=['kran'])], matris(2))
    assert res['ej_placerade'] and res['ej_placerade'][0]['orsak'].startswith('Ingen tekniker'), res
    print('OK  kompetens saknas: korrekt orsak')


def test_tidsfonster_omojligt():
    # Tekniker börjar 07:00, 10 min resa -> ankomst 07:10, men fönster stänger 06:40
    res = optimera([tek(1)], [ar('A', 1, wt='06:40')], matris(2))
    assert res['ej_placerade'], res
    assert 'Tidsfönster' in res['ej_placerade'][0]['orsak'], res
    print('OK  tidsfönster omöjligt: korrekt orsak')


def test_tidsfonster_ok():
    res = optimera([tek(1)], [ar('A', 1, wf='09:00', wt='12:00')], matris(2))
    assert res['rutter'][1] == ['A'], res
    assert res['ankomster']['A'] >= 9 * 60, res  # väntar till fönstret öppnar
    print('OK  tidsfönster ok: ankomst respekterar fönster')


def test_arbetstid_full():
    # Arbetstid 07:00–08:00 (60 min). 3 ärenden á 30 min + resor ryms ej alla.
    res = optimera([tek(1, start='07:00', slut='08:00')],
                   [ar('A', 1, service=30), ar('B', 2, service=30), ar('C', 3, service=30)],
                   matris(4))
    assert antal_placerade(res) < 3, res
    assert res['ej_placerade'], res
    print(f"OK  arbetstid full: {antal_placerade(res)} placerade, {len(res['ej_placerade'])} ej")


def test_tva_tekniker_delar():
    # Två kluster långt ifrån varandra med var sin depå – optimalt att dela upp.
    # Punkter: 0 dep1, 1 dep2, 2 A, 3 B (vid dep1), 4 C, 5 D (vid dep2)
    NARA, FJARRAN = 5 * 60, 60 * 60
    klus1, klus2 = {0, 2, 3}, {1, 4, 5}
    m = [[0] * 6 for _ in range(6)]
    for i in range(6):
        for j in range(6):
            if i == j:
                continue
            samma = (i in klus1 and j in klus1) or (i in klus2 and j in klus2)
            m[i][j] = NARA if samma else FJARRAN
    t1 = tek(1, dep=0)
    t2 = tek(2, dep=1)
    res = optimera([t1, t2], [ar('A', 2), ar('B', 3), ar('C', 4), ar('D', 5)], m)
    assert antal_placerade(res) == 4, res
    assert set(res['rutter'][1]) == {'A', 'B'}, res
    assert set(res['rutter'][2]) == {'C', 'D'}, res
    print('OK  två tekniker: kluster fördelade på rätt depå')


if __name__ == '__main__':
    for fn in [test_grund, test_kompetens, test_kompetens_saknas,
               test_tidsfonster_omojligt, test_tidsfonster_ok,
               test_arbetstid_full, test_tva_tekniker_delar]:
        fn()
    print('\nAlla tester gröna.')
