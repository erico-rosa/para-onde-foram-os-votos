# Para onde foram os votos

Site estático que compara os votos para **Presidente da República em 2026** entre o 1º e o 2º turno. Ele começa no Brasil, desce para cada UF e município e chega a cada seção eleitoral.

Para cada linha (UF, município ou seção), o site mostra:

- aptos a votar, comparecimento, abstenções e biometria inválida nos dois turnos;
- os votos de cada candidato ou opção (Branco, Nulo) em cada turno;
- para os dois candidatos do 2º turno (Lula e Flávio Bolsonaro), a porcentagem do total de votos em cada turno e a variação em pontos percentuais;
- uma coluna **Var.** com a variação do 1º para o 2º turno e uma seta (▲ subiu, ▼ caiu, = igual), sempre que o número existe nos dois turnos. Ela pode ser ordenada como qualquer outra coluna. Em abstenções e biometria inválida as cores são invertidas: alta é vermelha;
- no nível de seção, a hora de encerramento da urna em cada turno.

Dois filtros, que podem ser combinados, restringem tudo a parte das seções: pela hora em que a urna foi encerrada no 2º turno (**antes ou a partir das 17h20, ou antes ou a partir das 19h de Brasília**) e pela votação no 2º turno (**mais de 80% do total de votos da seção para um dos candidatos**). Com qualquer um escolhido, os totais e a comparação entre os turnos consideram só essas seções.

Para abrir, basta dar dois cliques em `index.html`. Não precisa de servidor, internet nem instalação.

---

## Fontes

| Fonte | Endereço |
|---|---|
| Conjunto de dados do TSE (Portal de Dados Abertos) | https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna |
| API do portal, usada para listar os arquivos | https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-boletim-de-urna |
| Servidor dos arquivos (CDN do TSE) | https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/ |
| Dicionário de dados do boletim de urna | `_leiame-boletimurnaweb.pdf`, na pasta acima desta |

**Arquivos usados:** um zip por UF e por turno, 56 no total (27 UFs mais `ZZ`, que é o exterior), cada um acompanhado de um `.sha512`:

```
bweb_1t_<UF>_051020261403.zip   1º turno (4 de outubro de 2026), gerado em 05/10/2026 14:03
bweb_2t_<UF>_261020260742.zip   2º turno (25 de outubro de 2026), gerado em 26/10/2026 07:42
```

> **Atenção:** a página do conjunto de dados só lista o **1º turno**. Os arquivos do 2º turno estão no mesmo servidor, com o padrão de nome acima (o mesmo do arquivo do RJ baixado à mão no começo do projeto). Todos responderam com HTTP 200 e passaram na conferência do hash.

Cada zip traz um CSV do TSE com o boletim de urna de cada seção, para todos os cargos. O CSV usa `;` como separador, campos de texto entre aspas e codificação Latin-1. Os zips do 1º turno somam cerca de 4,8 GB (SP sozinho tem 1,3 GB) e os do 2º, cerca de 170 MB.

---

## Arquitetura

```
TSE (zips por UF e turno)
        │  baixar_boletins.sh: baixa, confere o SHA-512, filtra e apaga o zip
        ▼
csv/bweb_<turno>_<UF>_<data>_Presidente.csv      392 MB, uma linha por seção × candidato
        │  gerar_dados.py: soma por seção e por município, converte o horário de encerramento para Brasília
        ▼
dados/brasil.js     1,4 MB   totais de todos os municípios por classe de seção (abre com a página)
dados/<UF>.js       até 12 MB cada seção da UF (carregado ao abrir um município)
        │  <script src>
        ▼
index.html  Brasil › UF › município › seção
```

### 1. Download e limpeza: `baixar_boletins.sh`

Para cada UF e turno, o script faz:

1. Baixa o zip com `curl`, tentando de novo em caso de falha.
2. Baixa o `.sha512` e confere o hash. Se não bater, descarta o arquivo.
3. Lê o CSV **de dentro do zip** com `unzip -p`, sem descompactá-lo no disco.
4. Com `awk`, encontra as colunas pelo nome no cabeçalho, mantém só as linhas em que `DS_CARGO_PERGUNTA` é `"Presidente"` e grava as 11 colunas abaixo.
5. Apaga o zip.

Colunas mantidas, na ordem do arquivo:

| Coluna | Significado |
|---|---|
| `NM_MUNICIPIO` | Município (no exterior, a cidade) |
| `NR_ZONA` | Zona eleitoral |
| `NR_SECAO` | Seção eleitoral |
| `NR_LOCAL_VOTACAO` | Local de votação |
| `QT_APTOS` | Eleitores aptos na seção |
| `QT_COMPARECIMENTO` | Eleitores que compareceram |
| `QT_ABSTENCOES` | Abstenções |
| `NM_VOTAVEL` | Candidato, `Branco` ou `Nulo` |
| `QT_VOTOS` | Votos daquele candidato ou opção na seção |
| `QT_ELEI_BIOM_SEM_HABILITACAO` | Eleitores com biometria que não foram habilitados por meio dela. No site: **biometria inválida** |
| `DT_ENCERRAMENTO` | Data e hora de encerramento da urna eletrônica para votação, na **hora local** da urna. Vazio em 57 seções: 2 de MG no 1º turno e, no exterior, 28 no 1º turno e 27 no 2º |

As definições são as do dicionário de dados do TSE. `QT_APTOS`, `QT_COMPARECIMENTO`, `QT_ABSTENCOES`, `QT_ELEI_BIOM_SEM_HABILITACAO` e `DT_ENCERRAMENTO` valem para a seção inteira e se repetem em cada linha de candidato.

A saída continua no formato do TSE: `;` como separador, Latin-1 e fim de linha CRLF, mas sem aspas. Uma seção identifica-se por **município + zona + seção**, porque os números de zona e seção se repetem entre municípios. UFs já processadas são puladas; para refazer uma, apague o CSV dela.

### 2. Agregação: `gerar_dados.py`

O navegador não consegue ler milhões de linhas de CSV, e uma página aberta do disco (`file://`) não tem permissão para ler um CSV vizinho. Já um `<script src>` funciona. Por isso, o script transforma os CSVs em arquivos `.js` já somados:

- **`dados/brasil.js`** define `window.DADOS_BRASIL`:
  - `c1` e `c2`: nomes dos candidatos de cada turno;
  - `finalistas`: os dois candidatos do 2º turno, em ordem alfabética, e `limiar`: o corte de votação (0,8);
  - `filtrosEnc` e `filtrosVoto`: cada filtro como `[rótulo, faixas que ele aceita]`, por exemplo `["a partir das 17h20", [1, 2]]` e `["mais de 80% para LULA", [2]]`;
  - `destaqueEnc`: a faixa de encerramento que o site marca em vermelho sem filtro (2, a partir das 19h);
  - `ufs`: para cada UF, a lista de municípios. Cada município tem `cl`, os totais separados por **classe de seção**: a chave tem dois dígitos, a faixa de encerramento e a faixa de votação (veja abaixo), e só aparecem as classes que existem no município. O site soma todas as classes para o total sem filtro, e só as que atendem aos filtros escolhidos quando há filtro. Cada agregado traz o número de seções (`s`), `[aptos, comparecimento, abstenções, biometria inválida]` de cada turno (`t1`, `t2`) e os votos alinhados a `c1` e `c2` (`v1`, `v2`).
- **`dados/<UF>.js`** grava `window.DADOS_UF[<UF>]` com:
  - `mun`: os nomes dos municípios;
  - `c1` e `c2`: os candidatos daquela UF;
  - `s`: uma linha por seção, no formato `[índice do município, zona, seção, local, aptos1, comp1, abst1, biom1, aptos2, comp2, abst2, biom2, encerramento 1T, encerramento 2T, classe da seção (faixa de encerramento × 4 + faixa de votação), votos 1T…, votos 2T…]`. As horas de encerramento já estão na hora de Brasília, ou `null` quando o TSE não informa.

  Quando a seção não existe num dos turnos, os campos daquele turno ficam `null`.

#### Horário de encerramento e os filtros

`DT_ENCERRAMENTO` vem na hora local da urna: no Acre, por exemplo, quase todas as urnas do 2º turno foram encerradas às 15h, que equivalem às 17h de Brasília. Para que cada corte seja o mesmo instante no país inteiro, `gerar_dados.py` converte para a hora de Brasília antes de comparar:

| Onde | Horas somadas |
|---|---|
| AC; e no AM: Amaturá, Atalaia do Norte, Benjamin Constant, Eirunepé, Envira, Guajará, Ipixuna, Itamarati, Jutaí, São Paulo de Olivença e Tabatinga | +2 |
| Resto do AM; MS, MT, RO e RR | +1 |
| Fernando de Noronha (PE) | −1 |
| Demais UFs | 0 |
| Exterior (ZZ) | 0: fica a hora local, porque lá a votação segue o horário de cada país |

A lista do Amazonas foi conferida nos próprios dados: nesses 11 municípios a mediana do encerramento no 2º turno é 15h locais, e no resto do AM é 16h. Com a conversão, o encerramento mediano de cada município de AC, AM, MS, MT, RO e RR cai às 17h de Brasília. Com a hora da urna do 2º turno já em hora de Brasília, cada seção cai numa **faixa de encerramento**: 0 = antes das 17h20 (até 17:19:59), 1 = das 17:20:00 às 18:59:59, 2 = a partir das 19:00:00, 3 = sem horário informado. Os filtros são conjuntos de faixas: "antes das 17h20" = {0}, "a partir das 17h20" = {1, 2}, "antes das 19h" = {0, 1}, "a partir das 19h" = {2}. Cada par "antes"/"a partir" se complementa, e as seções sem horário ficam fora de todos.

#### Filtro de votação

Cada seção também cai numa **faixa de votação** no 2º turno: 0 = nenhum candidato passou do limiar, 1 = o primeiro finalista em ordem alfabética (Flávio Bolsonaro) teve **mais de 80%** do total de votos da seção, 2 = o segundo (Lula) teve mais de 80%. O total de votos da seção é o comparecimento, que inclui brancos e nulos. Uma seção com exatamente 80% não entra.

As faixas, os filtros e o limiar ficam no começo de `gerar_dados.py` (`LIMITES_ENC`, `FILTROS_ENC`, `LIMIAR`). Para mudar um corte, edite e rode o script de novo; o site monta os seletores a partir dos dados.

### 3. Site: `index.html`

Um único HTML, com o CSS e o JavaScript embutidos e nenhuma biblioteca externa.

- **Carregamento:** um pré-loader aparece enquanto `dados/brasil.js` carrega. O arquivo de uma UF só é pedido quando você abre um município dela, também com pré-loader, e fica guardado para as próximas vezes.
- **Navegação:** são três níveis, Brasil (por UF), UF (por município) e município (por seção). Para descer, clique no nome na tabela ou use os seletores. Para voltar, use a trilha `Brasil › UF › município` no topo.
- **Colunas:** primeiro os candidatos que disputaram os dois turnos, ordenados pelos votos do 2º turno no país. Depois vêm Branco, Nulo e os candidatos só do 1º turno, ordenados pelos votos do 1º turno.
- **Tabela:**
  - a linha de total fica sempre no topo;
  - clicar num cabeçalho ordena por aquela coluna;
  - o filtro de texto busca por nome, ou por zona, seção e local;
  - "Mostrar mais" exibe 500 linhas por vez (a capital de SP tem 26.683 seções);
  - as primeiras colunas e o cabeçalho ficam fixos ao rolar;
  - dá para focar uma linha, que então ganha destaque.
- **Filtros "Urnas encerradas no 2º turno"** (Todas, antes ou a partir das 17h20, antes ou a partir das 19h) **e "Votação no 2º turno"** (Todas, mais de 80% para cada candidato), que podem ser combinados:
  - troca todos os totais (cartões, tabela, linha de total e resumo) pela soma das classes que atendem ao filtro, montada só na primeira vez que a combinação é usada;
  - os seletores e as tabelas passam a mostrar só UFs e municípios que têm essas seções;
  - na visão por seção, aparecem só as seções filtradas;
  - se a UF ou o município aberto não tem nenhuma seção no filtro, o site avisa.
- **Visão por seção:** as colunas "Encerr. 1T" e "Encerr. 2T" mostram a hora de encerramento da urna em hora de Brasília, ou "–" quando o TSE não informa. Sem filtro, a hora do 2º turno aparece em vermelho quando é a partir das 19h. Com um filtro escolhido, as horas que o atendem aparecem em azul.
- **Porcentagem dos finalistas:** Lula e Flávio Bolsonaro têm, além de 1T, 2T e Var., as colunas % 1T e % 2T (votos do candidato ÷ comparecimento do turno) e Var. p.p. (diferença em pontos percentuais). As três ordenam como as outras. Nas linhas de total, a porcentagem é calculada a partir dos totais somados.
- **Coluna de variação:** cada grupo que existe nos dois turnos tem as colunas 1T, 2T e Var. (2T − 1T). A variação é um campo da linha (`aptos_var`, `LULA (var)` etc.), por isso ordena como as outras. Nas linhas de total, ela é calculada a partir dos totais somados. A seta da coluna é desenhada pelo CSS (`::before`), então o texto da célula continua sendo só o número com sinal. Nos cartões do topo, a variação aparece ao lado do valor do 2º turno (`::after` com `attr(data-var)`).
- **Tema:** claro ou escuro, conforme a preferência do sistema (`prefers-color-scheme`).

---

## Arquivos

| Arquivo / pasta | O que é |
|---|---|
| `index.html` | O site |
| `dados/brasil.js` | Totais por município do país todo (gerado) |
| `dados/<UF>.js` | Seções de cada UF, 28 arquivos (gerados) |
| `csv/bweb_1t_<UF>_051020261403_Presidente.csv` | Votos para Presidente no 1º turno, por seção e candidato |
| `csv/bweb_2t_<UF>_261020260742_Presidente.csv` | Votos para Presidente no 2º turno, por seção e candidato |
| `baixar_boletins.sh` | Baixa, confere e filtra os boletins do TSE |
| `gerar_dados.py` | Gera `dados/` a partir de `csv/` |
| `baixar_boletins.log` | Registro da última execução do download |
| `og-image.png` | Imagem de compartilhamento, 1200×630 (WhatsApp, Facebook, X, LinkedIn, Telegram) |
| `compartilhamento/imagem.html` | Fonte da imagem de compartilhamento |

### Compartilhamento

O `<head>` do `index.html` tem a descrição da página, as tags Open Graph (`og:*`), que WhatsApp, Facebook, LinkedIn e Telegram leem, e as tags `twitter:*`, para o X.

O site está publicado no GitHub Pages, em https://erico-rosa.github.io/para-onde-foram-os-votos/. As tags `og:url`, `og:image`, `twitter:image` e o `<link rel="canonical">` usam esse endereço completo, porque WhatsApp e Facebook só mostram a imagem quando o endereço dela é **absoluto**. Se o site mudar de endereço, troque nessas quatro tags.

O WhatsApp guarda a pré-visualização em cache. Se o link foi compartilhado antes de a imagem ser publicada, a pré-visualização nova pode demorar a aparecer.

Os números da imagem estão escritos à mão em `compartilhamento/imagem.html`. Se os dados mudarem, edite esse arquivo e gere o PNG de novo pelo Edge em modo headless:

```bash
"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new --hide-scrollbars --force-device-scale-factor=1 --window-size=1200,630 --screenshot="$(pwd -W)/og-image.png" "file:///$(pwd -W)/compartilhamento/imagem.html"
```

---

## Como atualizar

Os dois comandos abaixo rodam na pasta do projeto. Para baixar tudo de novo, apague a pasta `csv/` antes; se passar UFs como argumento, só elas são processadas:

```bash
bash baixar_boletins.sh
```

Depois, gere os dados do site:

```bash
python gerar_dados.py
```

**Requisitos:**
- **Para baixar os dados:** Bash com `curl`, `unzip`, `awk` e `sha512sum`. O Git Bash do Windows serve.
- **Para gerar os dados:** Python 3, só com a biblioteca padrão.
- **Para usar o site:** qualquer navegador atual.

Se a data de geração dos arquivos do TSE mudar, ajuste os nomes no fim de `baixar_boletins.sh`. Eles aparecem nas linhas que chamam `processar`.

---

## Números de referência

Valores conferidos somando direto os CSVs de `csv/`:

| | 1º turno | 2º turno |
|---|---|---|
| Seções | 499.206 | 499.205 |
| Municípios no Brasil | 5.571 | 5.571 |
| Cidades no exterior | 145 | 144 |
| Aptos | 158.745.007 | 158.744.977 |
| Comparecimento | 125.275.835 | 128.236.074 |
| Abstenções | 33.469.172 | 30.508.903 |
| Biometria inválida | 8.342.249 | 8.632.488 |

**Filtros de encerramento** (hora de encerramento da urna no 2º turno, em hora de Brasília):

| Filtro | Seções | Municípios | Comparecimento 1º turno | Comparecimento 2º turno |
|---|---|---|---|---|
| Antes das 17h20 | 490.928 | 5.687 | 122.984.221 | 125.854.781 |
| A partir das 17h20 | 8.250 | 452 | 2.290.825 | 2.380.462 |
| Antes das 19h | 492.826 | 5.688 | 123.485.872 | 126.373.984 |
| A partir das 19h | 6.352 | 147 | 1.789.174 | 1.861.259 |

**Filtro de votação** (mais de 80% do total de votos da seção no 2º turno):

| Filtro | Seções | Municípios | Comparecimento 1º turno | Comparecimento 2º turno |
|---|---|---|---|---|
| Mais de 80% para Flávio Bolsonaro | 4.657 | 688 | 1.103.729 | 1.118.864 |
| Mais de 80% para Lula | 26.805 | 1.943 | 5.792.139 | 5.891.319 |

Combinando os dois, 111 seções em 39 municípios tiveram a urna encerrada a partir das 19h e mais de 80% para Lula. No RJ, a contagem do filtro de votação (6 seções acima de 80% para Lula, 24 para Flávio) foi refeita com `awk` direto nos CSVs e bate com o site.

Cada par de filtros de encerramento ("antes" e "a partir" do mesmo horário) soma 499.178 seções: as 499.205 do 2º turno menos as 27 do exterior sem encerramento informado. No corte das 19h, as maiores concentrações são RJ (2.805), SP (1.571), BA (936), PE (657) e PB (275). As contas do RJ em todos os filtros foram refeitas com `awk` direto nos CSVs e batem com o site.

**Verificações:**
- Em todas as UFs e nos dois turnos, a soma dos votos é igual ao comparecimento.
- No exterior, o 2º turno tem uma seção a menos que o 1º (1.308 contra 1.309) e uma cidade a menos. Nos dois lugares em que essa seção falta, o site mostra "–".
- O site soma 5.716 municípios e cidades no nível Brasil: os 5.571 do Brasil mais os 145 do exterior.
