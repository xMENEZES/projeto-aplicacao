#!/bin/bash
# Roda mutation_test.py para os 5 arquivos-alvo do Dask, lado IA.
set -e
PY='.venv\Scripts\python.exe'
MT='..\..\mutation_test.py'
OUT='../../comparativo-tests/dask/mutation_reports/ia'
TESTCMD='.venv\Scripts\python.exe -m pytest . -q'

declare -A FILES=(
  ["../../repositorios-originais/dask/dask/core.py"]=40
  ["../../repositorios-originais/dask/dask/config.py"]=40
  ["../../repositorios-originais/dask/dask/optimization.py"]=40
  ["../../repositorios-originais/dask/dask/tokenize.py"]=40
  ["../../repositorios-originais/dask/dask/delayed.py"]=40
)

for f in "${!FILES[@]}"; do
  max="${FILES[$f]}"
  name=$(basename "$f")
  echo "=== IA: $name (max-mutants=$max) ==="
  $PY $MT "$f" --test-cmd "$TESTCMD" --cwd . --max-mutants "$max" --timeout 60
  cp "${f}.mutation_report.json" "$OUT/${name}.mutation_report.json"
done

echo "=== FIM DO LOTE IA (DASK) ==="
