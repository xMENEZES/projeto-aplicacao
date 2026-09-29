#!/bin/bash
# Roda mutation_test.py para os 4 arquivos-alvo do Conan, lado IA.
set -e
PY='.venv\Scripts\python.exe'
MT='..\..\mutation_test.py'
OUT='../../comparativo-tests/conan/mutation_reports/ia'
TESTCMD='.venv\Scripts\python.exe -m pytest . -q'

declare -A FILES=(
  ["../../repositorios-originais/conan/conan/internal/model/options.py"]=15
  ["../../repositorios-originais/conan/conan/internal/model/requires.py"]=15
  ["../../repositorios-originais/conan/conan/internal/model/version.py"]=40
  ["../../repositorios-originais/conan/conan/internal/model/version_range.py"]=40
)

for f in "${!FILES[@]}"; do
  max="${FILES[$f]}"
  name=$(basename "$f")
  echo "=== IA: $name (max-mutants=$max) ==="
  $PY $MT "$f" --test-cmd "$TESTCMD" --cwd . --max-mutants "$max" --timeout 90
  cp "${f}.mutation_report.json" "$OUT/${name}.mutation_report.json"
done

echo "=== FIM DO LOTE IA (CONAN) ==="
