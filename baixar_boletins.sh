#!/usr/bin/env bash
# Baixa os boletins de urna 2026 de cada UF (1º e 2º turno) no TSE, guarda só os votos
# para Presidente com as colunas usadas pelo site e apaga o zip em seguida.
#
#   bash baixar_boletins.sh            # todas as UFs
#   bash baixar_boletins.sh SP RJ      # só algumas
#
# Saída: csv/bweb_<turno>_<UF>_<data>_Presidente.csv (";", sem aspas, Latin-1).
# UFs já processadas são puladas; apague o CSV para refazer.
set -uo pipefail
export LC_ALL=C

BASE=https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb
PASTA="$(cd "$(dirname "$0")" && pwd)"
SAIDA="$PASTA/csv"
TMP="$PASTA/.download"
UFS=("$@")
[ ${#UFS[@]} -eq 0 ] && UFS=(AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ)
mkdir -p "$SAIDA" "$TMP"

processar() {
  local nome=$1 zip="$TMP/$1.zip" out="$SAIDA/$1_Presidente.csv"
  if [ -s "$out" ]; then echo "$nome: já existe, pulando"; return 0; fi
  echo "$nome: baixando…"
  curl -fsS --retry 3 --retry-delay 5 -o "$zip" "$BASE/$nome.zip" || { echo "$nome: ERRO no download"; rm -f "$zip"; return 1; }
  if curl -fsS --retry 3 -o "$zip.sha512" "$BASE/$nome.zip.sha512"; then
    local esperado real
    esperado=$(grep -oE '[0-9a-fA-F]{128}' "$zip.sha512" | head -1 | tr 'A-F' 'a-f')
    real=$(sha512sum "$zip" | cut -d' ' -f1)
    if [ -n "$esperado" ] && [ "$esperado" != "$real" ]; then echo "$nome: ERRO hash não confere"; rm -f "$zip" "$zip.sha512"; return 1; fi
  fi
  local csv
  csv=$(unzip -Z1 "$zip" | grep -iE '^bweb_.*\.csv$' | head -1)
  [ -z "$csv" ] && { echo "$nome: ERRO sem CSV no zip"; rm -f "$zip" "$zip.sha512"; return 1; }
  # Lê o CSV de dentro do zip sem gravá-lo; as colunas são achadas pelo nome no cabeçalho
  unzip -p "$zip" "$csv" | awk -F';' '
    NR == 1 {
      for (i = 1; i <= NF; i++) { c = $i; gsub(/["\r]/, "", c); ix[c] = i }
      split("NM_MUNICIPIO NR_ZONA NR_SECAO NR_LOCAL_VOTACAO QT_APTOS QT_COMPARECIMENTO QT_ABSTENCOES NM_VOTAVEL QT_VOTOS", cols, " ")
      for (k = 1; k <= 9; k++) if (!(cols[k] in ix)) { print "coluna ausente: " cols[k] > "/dev/stderr"; exit 2 }
      cargo = ix["DS_CARGO_PERGUNTA"]
      print "NM_MUNICIPIO;NR_ZONA;NR_SECAO;NR_LOCAL_VOTACAO;QT_APTOS;QT_COMPARECIMENTO;QT_ABSTENCOES;NM_VOTAVEL;QT_VOTOS\r"
      next
    }
    index($0, "\"Presidente\"") == 0 { next }
    $cargo == "\"Presidente\"" {
      o = $ix[cols[1]]
      for (k = 2; k <= 9; k++) o = o ";" $ix[cols[k]]
      gsub(/["\r]/, "", o)
      print o "\r"
    }' > "$out.parcial"
  local st=("${PIPESTATUS[@]}")
  rm -f "$zip" "$zip.sha512"
  if [ "${st[0]}" != 0 ] || [ "${st[1]}" != 0 ]; then echo "$nome: ERRO ao processar (${st[*]})"; rm -f "$out.parcial"; return 1; fi
  mv "$out.parcial" "$out"
  echo "$nome: ok, $(($(wc -l < "$out") - 1)) linhas, $(du -h "$out" | cut -f1)"
}

falhas=()
for uf in "${UFS[@]}"; do
  processar "bweb_1t_${uf}_051020261403" || falhas+=("1t_$uf")
  processar "bweb_2t_${uf}_261020260742" || falhas+=("2t_$uf")
done
rmdir "$TMP" 2>/dev/null
if [ ${#falhas[@]} -gt 0 ]; then echo "FALHAS: ${falhas[*]}"; exit 1; fi
echo "CONCLUÍDO"
