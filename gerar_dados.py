"""Transforma os CSVs de csv/ (gerados por baixar_boletins.sh) nos arquivos que o site carrega.

O navegador não deixa uma página aberta do disco (file://) ler um CSV vizinho,
mas deixa carregar um <script src>. Rode de novo sempre que os CSVs mudarem:

    python gerar_dados.py

Saída em dados/:
- brasil.js: totais de cada município de todas as UFs (abre com a página)
- <UF>.js:   cada seção da UF, já somada por candidato (carregado ao abrir um município)
"""
import json
import re
from pathlib import Path

PASTA = Path(__file__).parent
ENTRADA = PASTA / 'csv'
SAIDA = PASTA / 'dados'
NOME_ARQ = re.compile(r'bweb_(1t|2t)_([A-Z]{2})_\d+_Presidente\.csv$')
COLS = ['NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO', 'NR_LOCAL_VOTACAO', 'QT_APTOS',
        'QT_COMPARECIMENTO', 'QT_ABSTENCOES', 'NM_VOTAVEL', 'QT_VOTOS']


def ler(caminho):
    """Agrega o CSV por seção: {(mun, zona, secao): [local, aptos, comp, abst, {nome: votos}]}."""
    secoes = {}
    with open(caminho, encoding='cp1252', newline='') as f:
        cab = f.readline().strip().split(';')
        iM, iZ, iS, iL, iA, iC, iB, iN, iV = (cab.index(c) for c in COLS)
        for linha in f:
            p = linha.rstrip('\r\n').split(';')
            if len(p) < len(cab):
                continue
            chave = (p[iM], int(p[iZ]), int(p[iS]))
            s = secoes.get(chave)
            if s is None:
                s = secoes[chave] = [int(p[iL]), int(p[iA]), int(p[iC]), int(p[iB]), {}]
            v = s[4]
            v[p[iN]] = v.get(p[iN], 0) + int(p[iV])
    return secoes


def main():
    arquivos = {}
    for f in sorted(ENTRADA.glob('*.csv')):
        m = NOME_ARQ.match(f.name)
        if m:
            arquivos.setdefault(m.group(2), {})[m.group(1)] = f
    SAIDA.mkdir(exist_ok=True)

    c1, c2 = {}, {}  # nome -> total no país, na ordem em que aparecem
    ufs = []
    for uf, fs in sorted(arquivos.items()):
        if set(fs) != {'1t', '2t'}:
            print(f'{uf}: falta um dos turnos, pulando')
            continue
        t1, t2 = ler(fs['1t']), ler(fs['2t'])
        n1 = sorted({n for s in t1.values() for n in s[4]})
        n2 = sorted({n for s in t2.values() for n in s[4]})
        chaves = sorted(set(t1) | set(t2), key=lambda k: (k[0], k[1], k[2]))
        muns = sorted({k[0] for k in chaves})
        ix_mun = {m: i for i, m in enumerate(muns)}

        linhas = []
        agg = {m: {'secoes': 0, 't1': [0, 0, 0], 't2': [0, 0, 0], 'v1': {}, 'v2': {}, 'tem1': False, 'tem2': False}
               for m in muns}
        for k in chaves:
            s1, s2 = t1.get(k), t2.get(k)
            local = (s1 or s2)[0]
            a = agg[k[0]]
            a['secoes'] += 1
            row = [ix_mun[k[0]], k[1], k[2], local]
            for s, t, nomes, tot, chave_v, chave_t in ((s1, 't1', n1, c1, 'v1', 'tem1'), (s2, 't2', n2, c2, 'v2', 'tem2')):
                if s is None:
                    row += [None, None, None]
                    continue
                a[chave_t] = True
                row += s[1:4]
                for i in range(3):
                    a[t][i] += s[1 + i]
                for n, v in s[4].items():
                    a[chave_v][n] = a[chave_v].get(n, 0) + v
                    tot[n] = tot.get(n, 0) + v
            row += [s1[4].get(n, 0) for n in n1] if s1 else [None] * len(n1)
            row += [s2[4].get(n, 0) for n in n2] if s2 else [None] * len(n2)
            linhas.append(row)

        dados_uf = {'mun': muns, 'c1': n1, 'c2': n2, 's': linhas}
        (SAIDA / f'{uf}.js').write_text(
            f'(window.DADOS_UF = window.DADOS_UF || {{}})[{json.dumps(uf)}] = '
            + json.dumps(dados_uf, ensure_ascii=False, separators=(',', ':')) + ';\n',
            encoding='utf-8')
        ufs.append({'uf': uf, 'mun': [
            {'nome': m, 'secoes': agg[m]['secoes'],
             't1': agg[m]['t1'] if agg[m]['tem1'] else None, 't2': agg[m]['t2'] if agg[m]['tem2'] else None,
             'v1': agg[m]['v1'] if agg[m]['tem1'] else None, 'v2': agg[m]['v2'] if agg[m]['tem2'] else None}
            for m in muns]})
        print(f'{uf}: {len(muns)} municípios, {len(linhas)} seções, '
              f'{(SAIDA / f"{uf}.js").stat().st_size / 1e6:.1f} MB')

    # Votos por município viram listas alinhadas aos nomes do país, para o arquivo ficar pequeno
    nomes1, nomes2 = list(c1), list(c2)
    for u in ufs:
        for m in u['mun']:
            m['v1'] = [m['v1'].get(n, 0) for n in nomes1] if m['v1'] is not None else None
            m['v2'] = [m['v2'].get(n, 0) for n in nomes2] if m['v2'] is not None else None
    brasil = {'c1': nomes1, 'c2': nomes2, 'ufs': ufs}
    (SAIDA / 'brasil.js').write_text(
        'window.DADOS_BRASIL = ' + json.dumps(brasil, ensure_ascii=False, separators=(',', ':')) + ';\n',
        encoding='utf-8')
    print(f'brasil.js: {len(ufs)} UFs, {(SAIDA / "brasil.js").stat().st_size / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
