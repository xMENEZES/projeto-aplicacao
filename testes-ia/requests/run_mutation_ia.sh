#!/bin/bash
# Roda mutation_test.py para os 8 arquivos-alvo do Requests, lado IA.
set -e
PY='.venv\Scripts\python.exe'
MT='..\..\mutation_test.py'
OUT='../../comparativo-tests/requests/mutation_reports/ia'
TESTCMD='.venv\Scripts\python.exe -m pytest . -q'

declare -A FILES=(
  ["../../repositorios-originais/requests/requests/models.py"]=15
  ["../../repositorios-originais/requests/requests/sessions.py"]=15
  ["../../repositorios-originais/requests/requests/adapters.py"]=15
  ["../../repositorios-originais/requests/requests/auth.py"]=15
  ["../../repositorios-originais/requests/requests/cookies.py"]=15
  ["../../repositorios-originais/requests/requests/hooks.py"]=40
  ["../../repositorios-originais/requests/requests/structures.py"]=40
  ["../../repositorios-originais/requests/requests/api.py"]=40
)

for f in "${!FILES[@]}"; do
  max="${FILES[$f]}"
  name=$(basename "$f")
  echo "=== IA: $name (max-mutants=$max) ==="
  $PY $MT "$f" --test-cmd "$TESTCMD" --cwd . --max-mutants "$max" --timeout 60
  cp "${f}.mutation_report.json" "$OUT/${name}.mutation_report.json"
done

echo "=== FIM DO LOTE IA ==="
