#!/bin/bash
set -uo pipefail
cd "C:/claude/projeto-aplicacao/testes-ia/scrapy"
PY='.venv\Scripts\python.exe'
MT="C:/claude/projeto-aplicacao/mutation_test.py"
FAST="$PY -m pytest test_estrutural_http.py test_estrutural_settings_signals.py test_estrutural_downloadermiddlewares.py test_estrutural_spidermiddlewares_item.py v2_metodologia_formal/test_decisao_redirect_retry.py v2_metodologia_formal/test_decisao_depth_offsite.py v2_metodologia_formal/test_valor_limite_urllength.py -q"
SLOW="$PY -m pytest test_integracao_crawl.py test_aceitacao_crawl.py -q"

LOG="mutation_ia_results.txt"
> "$LOG"

run_one() {
  local file="$1"
  local cmd="$2"
  echo "===== $file =====" | tee -a "$LOG"
  # SEM --disable-pytest-plugin-autoload aqui: essa flag so e necessaria quando o
  # mesmo venv tem dois checkouts do pacote instalados (caso do Celery). Aqui os
  # venvs sao separados (testes-ia/scrapy/.venv vs scrapy/human_original/.venv),
  # e essa flag quebraria os testes de crawl real (desliga o pytest-twisted junto).
  py "$MT" "$file" --test-cmd "$cmd" --cwd "C:/claude/projeto-aplicacao/testes-ia/scrapy" 2>&1 | tail -6 | tee -a "$LOG"
  echo "" >> "$LOG"
}

run_one "../../repositorios-originais/scrapy/scrapy/downloadermiddlewares/httpauth.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/downloadermiddlewares/offsite.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/downloadermiddlewares/redirect.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/downloadermiddlewares/retry.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/http/request/__init__.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/http/response/__init__.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/http/response/text.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/item.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/settings/__init__.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/signalmanager.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/spidermiddlewares/depth.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/spidermiddlewares/urllength.py" "$FAST"
run_one "../../repositorios-originais/scrapy/scrapy/crawler.py" "$SLOW"
run_one "../../repositorios-originais/scrapy/scrapy/spiders/__init__.py" "$SLOW"

echo "TUDO PRONTO (lado IA)" | tee -a "$LOG"
