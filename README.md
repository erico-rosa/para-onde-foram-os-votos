# Para onde foram os votos

Site estático que compara os votos para **Presidente da República em 2026** entre o 1º e o 2º turno. Ele começa no Brasil, desce para cada UF e município e chega a cada seção eleitoral.

Para cada linha (UF, município ou seção), o site mostra:

- aptos a votar, comparecimento e abstenções nos dois turnos;
- os votos de cada candidato ou opção (Branco, Nulo) em cada turno;
- uma seta (▲ subiu, ▼ caiu, = igual) com a variação entre parênteses, sempre que o número existe nos dois turnos. Em abstenções as cores são invertidas: alta é vermelha.

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
csv/bweb_<turno>_<UF>_<data>_Presidente.csv      267 MB, uma linha por seção × candidato
        │  gerar_dados.py: soma por seção e por município
        ▼
dados/brasil.js     0,9 MB   totais de todos os municípios (abre com a página)
dados/<UF>.js       até 9 MB cada seção da UF (carregado ao abrir um município)
        │  <script src>
        ▼
index.html  Brasil › UF › município › seção
```

### 1. Download e limpeza: `baixar_boletins.sh`

Para cada UF e turno, o script faz:

1. Baixa o zip com `curl`, tentando de novo em caso de falha.
2. Baixa o `.sha512` e confere o hash. Se não bater, descarta o arquivo.
3. Lê o CSV **de dentro do zip** com `unzip -p`, sem descompactá-lo no disco.
4. Com `awk`, encontra as colunas pelo nome no cabeçalho, mantém só as linhas em que `DS_CARGO_PERGUNTA` é `"Presidente"` e grava as 9 colunas abaixo.
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

A saída continua no formato do TSE: `;` como separador, Latin-1 e fim de linha CRLF, mas sem aspas. Uma seção identifica-se por **município + zona + seção**, porque os números de zona e seção se repetem entre municípios. UFs já processadas são puladas; para refazer uma, apague o CSV dela.

### 2. Agregação: `gerar_dados.py`

O navegador não consegue ler milhões de linhas de CSV, e uma página aberta do disco (`file://`) não tem permissão para ler um CSV vizinho. Já um `<script src>` funciona. Por isso, o script transforma os CSVs em arquivos `.js` já somados:

- **`dados/brasil.js`** define `window.DADOS_BRASIL`:
  - `c1` e `c2`: nomes dos candidatos de cada turno;
  - `ufs`: para cada UF, a lista de municípios com seções, `[aptos, comparecimento, abstenções]` de cada turno e os votos alinhados a `c1` e `c2`.
- **`dados/<UF>.js`** grava `window.DADOS_UF[<UF>]` com:
  - `mun`: os nomes dos municípios;
  - `c1` e `c2`: os candidatos daquela UF;
  - `s`: uma linha por seção, no formato `[índice do município, zona, seção, local, aptos1, comp1, abst1, aptos2, comp2, abst2, votos 1T…, votos 2T…]`.

  Quando a seção não existe num dos turnos, os campos daquele turno ficam `null`.

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
- **Seta e variação:** são desenhadas pelo CSS (`::after` com `attr(data-var)`). Assim o texto da célula continua sendo só o número, e a ordenação usa o valor puro.
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

**Verificações:**
- Em todas as UFs e nos dois turnos, a soma dos votos é igual ao comparecimento.
- No exterior, o 2º turno tem uma seção a menos que o 1º (1.308 contra 1.309) e uma cidade a menos. Nos dois lugares em que essa seção falta, o site mostra "–".
- O site soma 5.716 municípios e cidades no nível Brasil: os 5.571 do Brasil mais os 145 do exterior.
