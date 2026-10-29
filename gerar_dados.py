"""Transforma os CSVs de csv/ (gerados por baixar_boletins.sh) nos arquivos que o site carrega.

O navegador não deixa uma página aberta do disco (file://) ler um CSV vizinho,
mas deixa carregar um <script src>. Rode de novo sempre que os CSVs mudarem:

    python gerar_dados.py

Saída em dados/:
- brasil.js: totais de cada município de todas as UFs, separados por classe de seção (para os filtros)
- <UF>.js:   cada seção da UF, já somada por candidato (carregado ao abrir um município)
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

PASTA = Path(__file__).parent
ENTRADA = PASTA / 'csv'
SAIDA = PASTA / 'dados'
NOME_ARQ = re.compile(r'bweb_(1t|2t)_([A-Z]{2})_\d+_Presidente\.csv$')
COLS = ['NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO', 'NR_LOCAL_VOTACAO', 'QT_APTOS', 'QT_COMPARECIMENTO',
        'QT_ABSTENCOES', 'QT_ELEI_BIOM_SEM_HABILITACAO', 'DT_ENCERRAMENTO', 'NM_VOTAVEL', 'QT_VOTOS']

# DT_ENCERRAMENTO vem na hora local da urna. Horas a somar para chegar à hora de Brasília.
# No exterior (ZZ) fica a hora local, porque lá a votação segue o horário de cada país.
#
# Cada seção cai numa classe = (faixa de encerramento no 2º turno, faixa de votação no 2º turno).
# Os municípios guardam os totais por classe, e o site soma as classes que atendem aos filtros
# escolhidos; assim qualquer combinação de filtros sai dos mesmos dados.
#
# Faixas de encerramento, em hora de Brasília: 0 = antes das 17h20, 1 = das 17h20 às 18h59,
# 2 = a partir das 19h, 3 = sem horário informado pelo TSE.
LIMITES_ENC = [(17, 20), (19, 0)]
FILTROS_ENC = [('antes das 17h20', [0]), ('a partir das 17h20', [1, 2]),
               ('antes das 19h', [0, 1]), ('a partir das 19h', [2])]
DESTAQUE_ENC = 2  # faixa que o site marca em vermelho quando nenhum filtro está escolhido
# Faixas de votação no 2º turno: 0 = nenhum candidato passa do limiar; 1 + j = o finalista j
# (ordem alfabética) teve mais que LIMIAR do total de votos da seção (o comparecimento).
LIMIAR = 0.8
OPCOES = {'Branco', 'Nulo'}
FUSO_UF = {'AC': 2, 'AM': 1, 'MS': 1, 'MT': 1, 'RO': 1, 'RR': 1}
FUSO_MUN = {
    # Oeste do Amazonas, no fuso do Acre (UTC−5). Lista conferida nos próprios dados: nesses
    # municípios a mediana do encerramento no 2º turno é 15h locais; no resto do AM, 16h.
    ('AM', 'AMATURÁ'): 2, ('AM', 'ATALAIA DO NORTE'): 2, ('AM', 'BENJAMIN CONSTANT'): 2,
    ('AM', 'EIRUNEPÉ'): 2, ('AM', 'ENVIRA'): 2, ('AM', 'GUAJARÁ'): 2, ('AM', 'IPIXUNA'): 2,
    ('AM', 'ITAMARATI'): 2, ('AM', 'JUTAÍ'): 2, ('AM', 'SÃO PAULO DE OLIVENÇA'): 2,
    ('AM', 'TABATINGA'): 2,
    # Fernando de Noronha (UTC−2)
    ('PE', 'FERNANDO DE NORONHA'): -1,
}


def fuso(uf, mun):
    return FUSO_MUN.get((uf, mun), FUSO_UF.get(uf, 0))


def ler(caminho):
    """Agrega o CSV por seção: {(mun, zona, secao): [local, aptos, comp, abst, biom, encerramento, {nome: votos}]}."""
    secoes = {}
    with open(caminho, encoding='cp1252', newline='') as f:
        cab = f.readline().strip().split(';')
        iM, iZ, iS, iL, iA, iC, iB, iBio, iE, iN, iV = (cab.index(c) for c in COLS)
        for linha in f:
            p = linha.rstrip('\r\n').split(';')
            if len(p) < len(cab):
                continue
            chave = (p[iM], int(p[iZ]), int(p[iS]))
            s = secoes.get(chave)
            if s is None:
                s = secoes[chave] = [int(p[iL]), int(p[iA]), int(p[iC]), int(p[iB]), int(p[iBio]), p[iE], {}]
            v = s[6]
            v[p[iN]] = v.get(p[iN], 0) + int(p[iV])
    return secoes


def hora_brasilia(uf, mun, encerramento):
    """'2026-10-25 15:03:59' na hora local -> (datetime em Brasília, faixa de encerramento).
    Algumas seções vêm sem encerramento no CSV do TSE: ficam sem hora, na faixa 3."""
    if not encerramento:
        return None, len(LIMITES_ENC) + 1
    local = datetime.strptime(encerramento, '%Y-%m-%d %H:%M:%S')
    br = local + timedelta(hours=fuso(uf, mun))
    dia = datetime.combine(local.date(), datetime.min.time())
    return br, sum(1 for h, m in LIMITES_ENC if br >= dia + timedelta(hours=h, minutes=m))


def faixa_voto(s2, finalistas):
    """Faixa de votação da seção no 2º turno (0 = nenhum finalista acima do limiar)."""
    if not s2 or s2[2] <= 0:
        return 0
    for j, n in enumerate(finalistas):
        if s2[6].get(n, 0) > LIMIAR * s2[2]:
            return 1 + j
    return 0


def novo_agg():
    return {'secoes': 0, 't1': None, 't2': None, 'v1': None, 'v2': None}


def somar(a, s, t):
    """Soma uma seção (aptos, comp, abst, biom e votos) no agregado a, no turno t ('1' ou '2')."""
    if a['t' + t] is None:
        a['t' + t], a['v' + t] = [0, 0, 0, 0], {}
    for i in range(4):
        a['t' + t][i] += s[1 + i]
    for n, x in s[6].items():
        a['v' + t][n] = a['v' + t].get(n, 0) + x


def main():
    arquivos = {}
    for f in sorted(ENTRADA.glob('*.csv')):
        m = NOME_ARQ.match(f.name)
        if m:
            arquivos.setdefault(m.group(2), {})[m.group(1)] = f
    SAIDA.mkdir(exist_ok=True)

    c1, c2 = {}, {}  # nome -> total no país, na ordem em que aparecem
    ufs = []
    finalistas = None
    n_classes = {}
    for uf, fs in sorted(arquivos.items()):
        if set(fs) != {'1t', '2t'}:
            print(f'{uf}: falta um dos turnos, pulando')
            continue
        t1, t2 = ler(fs['1t']), ler(fs['2t'])
        n1 = sorted({n for s in t1.values() for n in s[6]})
        n2 = sorted({n for s in t2.values() for n in s[6]})
        if finalistas is None:
            finalistas = [n for n in n2 if n not in OPCOES]
        chaves = sorted(set(t1) | set(t2))
        muns = sorted({k[0] for k in chaves})
        ix_mun = {m: i for i, m in enumerate(muns)}
        agg = {m: {} for m in muns}  # município -> classe -> agregado

        linhas = []
        for k in chaves:
            s1, s2 = t1.get(k), t2.get(k)
            mun = k[0]
            h1, _ = hora_brasilia(uf, mun, s1[5]) if s1 else (None, None)
            h2, fe = hora_brasilia(uf, mun, s2[5]) if s2 else (None, len(LIMITES_ENC) + 1)
            fv = faixa_voto(s2, finalistas)
            classe = f'{fe}{fv}'
            n_classes[classe] = n_classes.get(classe, 0) + 1
            a = agg[mun].setdefault(classe, novo_agg())
            a['secoes'] += 1
            if s1:
                somar(a, s1, '1')
            if s2:
                somar(a, s2, '2')
            for nome, x in (s1[6].items() if s1 else ()):
                c1[nome] = c1.get(nome, 0) + x
            for nome, x in (s2[6].items() if s2 else ()):
                c2[nome] = c2.get(nome, 0) + x
            row = [ix_mun[mun], k[1], k[2], (s1 or s2)[0]]
            row += s1[1:5] if s1 else [None] * 4
            row += s2[1:5] if s2 else [None] * 4
            row += [h1.strftime('%H:%M:%S') if h1 else None, h2.strftime('%H:%M:%S') if h2 else None, fe * 4 + fv]
            row += [s1[6].get(n, 0) for n in n1] if s1 else [None] * len(n1)
            row += [s2[6].get(n, 0) for n in n2] if s2 else [None] * len(n2)
            linhas.append(row)

        dados_uf = {'mun': muns, 'c1': n1, 'c2': n2, 's': linhas}
        (SAIDA / f'{uf}.js').write_text(
            f'(window.DADOS_UF = window.DADOS_UF || {{}})[{json.dumps(uf)}] = '
            + json.dumps(dados_uf, ensure_ascii=False, separators=(',', ':')) + ';\n',
            encoding='utf-8')
        ufs.append({'uf': uf, 'mun': [{'nome': m, 'cl': agg[m]} for m in muns]})
        print(f'{uf}: {len(muns)} municípios, {len(linhas)} seções, {(SAIDA / f"{uf}.js").stat().st_size / 1e6:.1f} MB')

    # Votos viram listas alinhadas aos nomes do país, para o arquivo ficar pequeno
    nomes1, nomes2 = list(c1), list(c2)

    def compactar(a):
        return {'s': a['secoes'], 't1': a['t1'], 't2': a['t2'],
                'v1': [a['v1'].get(n, 0) for n in nomes1] if a['v1'] is not None else None,
                'v2': [a['v2'].get(n, 0) for n in nomes2] if a['v2'] is not None else None}

    for u in ufs:
        for m in u['mun']:
            m['cl'] = {c: compactar(a) for c, a in sorted(m['cl'].items())}
    pct = round(LIMIAR * 100)
    filtros_voto = [(f'mais de {pct}% para {n}', [1 + j]) for j, n in enumerate(finalistas)]
    brasil = {'c1': nomes1, 'c2': nomes2, 'finalistas': finalistas, 'limiar': LIMIAR,
              'filtrosEnc': FILTROS_ENC, 'filtrosVoto': filtros_voto, 'destaqueEnc': DESTAQUE_ENC, 'ufs': ufs}
    (SAIDA / 'brasil.js').write_text(
        'window.DADOS_BRASIL = ' + json.dumps(brasil, ensure_ascii=False, separators=(',', ':')) + ';\n',
        encoding='utf-8')
    print(f'brasil.js: {len(ufs)} UFs, {(SAIDA / "brasil.js").stat().st_size / 1e6:.1f} MB')
    for rot, faixas in FILTROS_ENC:
        print(f'  encerradas {rot}: {sum(n for c, n in n_classes.items() if int(c[0]) in faixas)} seções')
    for rot, faixas in filtros_voto:
        print(f'  {rot}: {sum(n for c, n in n_classes.items() if int(c[1]) in faixas)} seções')


if __name__ == '__main__':
    main()
