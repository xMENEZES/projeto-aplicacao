# Relatório — Comparação de Testes Criados por IA vs. Testes Humanos Originais

Documento vivo: será atualizado a cada etapa relevante do projeto, na ordem em que as coisas forem acontecendo. Serve como registro completo do início ao fim, para consulta e para apresentação dos resultados.

---

## 1. Objetivo do projeto

Comparar, em 5 repositórios open source Python, a suíte de testes escrita por IA (Claude, sem acesso aos testes originais durante a escrita) contra a suíte de testes já existente, escrita por humanos — medindo cobertura, complexidade e qualidade real dos testes (via teste de mutação), não só se "passam ou não passam".

## 2. Repositórios em escopo

**NOTA (15/09/2026, outra sessão — reorganização para o GitHub
xMENEZES/projeto-aplicacao):** os caminhos abaixo mudaram. Código-fonte
original e testes de IA não ficam mais na mesma pasta `<repo>\`; cada
um tem sua própria árvore agora, e os `<repo>\human_original\` (clones
completos usados na comparação desta sessão) foram deixados exatamente
onde estavam, fora da reorganização, para não interromper nada em
andamento aqui.

| Repositório | Versão/commit | Testes de IA | Código-fonte original |
|---|---|---|---|
| Requests | 2.34.2 | `testes-ia\requests\` | `repositorios-originais\requests\` |
| Scrapy | 2.17.0 | `testes-ia\scrapy\` | `repositorios-originais\scrapy\` |
| Celery | 5.6.2 | `testes-ia\celery\` | `repositorios-originais\celery\` |
| Conan | 2.32.0-dev | `testes-ia\conan\` | `repositorios-originais\conan\` |
| Dask | commit 817e5ffc... | `testes-ia\dask\` | `repositorios-originais\dask\` |

(todos relativos a `C:\claude\projeto-aplicacao\`; testes humanos agora
em `testes-humanos\<repo>\`, extraídos permanentemente via clone fresco
hoje — o `human_original\` de cada repo continua existindo também, sem
mudanças, para o que esta comparação ainda precisar dele)

Cada pasta tem: código-fonte sob teste em `repo_src\`, suíte de IA v1 "ad-hoc" (testes soltos por tipo: estrutural/funcional/integração/aceitação) e suíte de IA v2 "metodologia formal" (aplicando classes de equivalência, valor limite, tabela de decisão, GFC — baseado na skill `gerador-de-testes`), na subpasta `v2_metodologia_formal\`. Total de 720 testes de IA escritos nos 5 repositórios (ver `RESUMO_TESTES_CRIADOS.md` na raiz de `projeto-aplicacao\`).

Regra seguida na criação: nenhum teste de IA foi escrito olhando a suíte humana já existente — só o código de produção — para que a comparação depois seja justa (duas suítes independentes sobre o mesmo código).

## 3. Etapa 1 — Mapeamento IA × Humano (5 agentes em paralelo)

Para cada repositório, um agente verificou, para cada classe/função que a IA testou, se existe um teste humano equivalente (via grep de import/uso real no diretório de testes humano original de cada projeto), e também rankeou por complexidade ciclomática (script próprio em `ast`, sem depender de instalação) as classes que **já têm** cobertura humana, para servir de alvo alternativo onde houver gap.

### Resultado — resumo geral

| Repositório | Unidades da IA verificadas | Gaps (sem par humano) |
|---|---|---|
| Requests | 24 | 9 |
| Scrapy | 17 | 0 |
| Celery | 13 | 0 |
| Conan | 14 | 3 (+1 parcial) |
| Dask | 22 | 1 |

### Gaps encontrados, por repositório

**Requests (9):** `PreparedRequest.prepare_url`, `.prepare_body`, `.prepare_content_length`; `SessionRedirectMixin.rebuild_method`; `merge_setting`; `merge_hooks`; `BaseAdapter`; `HTTPBasicAuth`; `HTTPProxyAuth`.

**Conan (3 + 1 parcial):** `_PackageOption` / `_PackageOptions`; `Requirement` / `Requirements`; `VersionRange` (parcial — coberta só indiretamente via CLI, nunca instanciada diretamente em teste humano).

**Dask (1):** `core.toposort` — nenhuma evidência humana em nenhum nível, direto ou indireto.

**Scrapy e Celery:** nenhum gap — todas as unidades testadas pela IA têm par humano confirmado.

(Rankings de complexidade completos por repositório, usados para decidir os ajustes abaixo, estão registrados na conversa; podem ser regerados a qualquer momento rodando de novo os agentes de mapeamento, já que a lógica é determinística.)

## 4. Etapa 2 — Ajustes definidos para viabilizar a comparação

Critério: um teste de IA só entra na comparação se existir (ou puder ser reescrito para existir) um par humano no mesmo nível de abstração. Onde isso é impossível em qualquer nível, o caso é removido — mantê-lo só como "teste de IA sem baseline" não serve ao objetivo de comparação.

### Requests
- **Remover:** `prepare_content_length` (nenhuma evidência humana em nenhum nível); `merge_setting`/`merge_hooks` (funções internas, nunca testadas isoladamente por humanos); `BaseAdapter` (classe abstrata, não testável isoladamente); `HTTPProxyAuth` (sem via pública equivalente identificada).
- **Reescrever** (mesma funcionalidade, nível de abstração mais alto, igual ao humano):
  - `prepare_url`/`prepare_body` → testar via `Request(...).prepare()` e conferir `.url`/`.body`, não chamar os métodos internos direto.
  - `rebuild_method` → testar via `Session().resolve_redirects(...)` ou um redirect 307/303 real via `session.get(...)`.
  - `HTTPBasicAuth` → testar via `requests.get(url, auth=(user, pass))` (o requests converte a tupla em `HTTPBasicAuth` internamente).

### Conan
- **Reescrever** (todos os 3, cobertura indireta via CLI já existe):
  - `_PackageOption`/`_PackageOptions` → via `TestClient` com conanfile declarando `options = {...}`.
  - `Requirement`/`Requirements` → via grafo (`TestClient`/`GraphManagerTest`, `requires="pkg/1.0"`).
  - `VersionRange` → via `requires="pkg/[>=1.0 <2.0]"` no conanfile.

### Dask
- **Remover:** `core.toposort` (sem par humano em nenhum nível). Os outros 8 casos de `core.py` continuam válidos sem mudança.

### Scrapy e Celery
- Nenhum ajuste necessário. Prontos para comparação imediata.

## 5. Etapa 3 — Metodologia de medição técnica escolhida

Como os 5 repositórios são **Python** (não Java), a stack de medição é:
- **Execução:** pytest
- **Cobertura** (equivalente ao JaCoCo): `coverage.py` via plugin `pytest-cov` (`--cov --cov-branch --cov-report=html`)
- **Teste de mutação** (equivalente ao PITest): `mutmut`

(JUnit/JaCoCo/PITest, mencionados no início da conversa, se aplicariam a um projeto Java — não é o caso aqui; a stack acima é o equivalente funcional em Python.)

## 6. Incidente registrado — perda do clone dos testes humanos

Os clones dos repositórios com os testes humanos originais (usados pelos agentes na Etapa 1) estavam em uma pasta temporária de sessão (`...\AppData\Local\Temp\claude\C--claude\4769887f-.../scratchpad\`), que foi removida pela limpeza automática do Windows depois de alguns dias. **Solução adotada:** re-clonar cada repositório humano em local permanente, como subpasta de cada projeto (ex.: `C:\claude\projeto-aplicacao\celery\human_original\`), fixando a mesma tag/versão usada originalmente, antes de qualquer medição.

## 7. Etapa 4 — Execução da comparação, repositório por repositório

### 7.1 Celery — EM ANDAMENTO (primeiro repositório escolhido para comparar)

Passo a passo definido (nenhum ajuste de teste necessário aqui — Celery não teve gaps):

1. Recriar clone humano permanente: `git clone --branch v5.6.2 --depth 1 https://github.com/celery/celery.git "C:\claude\projeto-aplicacao\celery\human_original"`
2. Ambiente: `py -m venv "C:\claude\projeto-aplicacao\celery\.venv"`, ativar, `pip install -r requirements-testes.txt` (suíte IA) e `pip install -e .` + `pip install -r requirements/test.txt -r requirements/default.txt` dentro de `human_original` (suíte humana); `pip install pytest-cov mutmut`.
3. Cobertura da suíte de IA: rodar pytest nos 9 arquivos de teste da IA com `--cov=celery --cov-branch --cov-report=html:cov_ia`. Abrir `cov_ia\index.html`.
4. Cobertura da suíte humana, restrita aos 7 arquivos-par (`t/unit/tasks/test_tasks.py`, `test_canvas.py`, `t/unit/worker/test_bootsteps.py`, `t/unit/utils/test_dispatcher.py`, `t/unit/backends/test_cache.py`, `test_base.py`, `t/unit/app/test_app.py`) com `--cov=celery --cov-branch --cov-report=html:cov_humano`.
5. Mutação da suíte de IA: `setup.cfg` com `[mutmut]` apontando `paths_to_mutate` para os 7 arquivos de produção (`repo_src/celery/...`) e `runner` chamando os testes de IA; `mutmut run` + `mutmut html`.
6. Mutação da suíte humana: mesmo processo dentro de `human_original`, `paths_to_mutate` sem o prefixo `repo_src/`, `runner` chamando os 7 arquivos de teste humano.
7. Prints definidos para o material de apresentação (8 no total): resumo de cobertura IA (1) e humano (3); drill-down linha a linha IA (2) e humano (4); resumo de mutação IA (5) e humano (7); um mutante sobrevivente específico IA (6) e humano (8), idealmente a mesma mutação nos dois lados.
8. Consolidar tudo numa tabela final: arquivo × % linha IA/Humano × % branch IA/Humano × escore de mutação IA/Humano.

**Status (14/09/2026):** execução iniciada pelo usuário.
- Ambiente do usuário: **cmd.exe** (Prompt de Comando), não PowerShell nem Bash — `source`/`&`/`Set-ExecutionPolicy` não funcionam nele. Solução adotada: chamar sempre os `.exe` do venv por caminho completo (`.venv\Scripts\pip.exe`, `.venv\Scripts\pytest.exe`), sem precisar ativar o venv.
- Pegadinha resolvida: rodar `pip install -r requirements-testes.txt` só funciona estando na pasta certa, ou passando o caminho completo do arquivo — senão dá erro "Could not open requirements file", e como nada foi instalado, o `pytest.exe` seguinte também falha ("não é reconhecido").
- `py -m venv "C:\claude\projeto-aplicacao\celery\.venv"` criado com sucesso.
- `pip install -r requirements-testes.txt` (suíte de IA) concluído com sucesso — pytest 9.1.1, pytest-cov 7.1.0, kombu, billiard, amqp, click etc. instalados.
- Primeiro teste de fumaça: `pytest test_estrutural_task.py --cov=celery --cov-branch --cov-report=html:cov_ia` → 14 testes passaram, `cov_ia` gerado.
- Suíte completa de IA rodada com sucesso (`--cov=celery --cov-branch --cov-report=html:cov_ia`), total do pacote 31% (esperado — só 7 arquivos são alvo). Print 1 capturado e analisado.

**Cobertura da suíte de IA — os 7 arquivos-alvo (registrado em 14/09/2026):**

| Arquivo | % Linha | % Branch | % Total |
|---|---|---|---|
| `app\task.py` (Task) | 75% | 54% | 70% |
| `app\base.py` (Celery) | 68% | 42% | 63% |
| `canvas.py` (Signature/chain/group) | 50% | 29% | 44% |
| `bootsteps.py` (Blueprint/Step) | 80% | 62% | 77% |
| `utils\dispatch\signal.py` (Signal) | 76% | 75% | 76% |
| `backends\cache.py` (CacheBackend) | 61% | 17% | 59% |
| `backends\base.py` (Backend) | 53% | 40% | 50% |

Nota: `utils\dispatch\__init__.py` aparece 100%/100% no relatório mas é só um re-export de 2 linhas; o arquivo real da classe `Signal` é `signal.py`, usado acima.

- Clone humano (`human_original`) recriado com sucesso, versão confirmada (git describe), dependências instaladas (`pip install -e .` + `requirements/test.txt` + `requirements/default.txt`).
- Cobertura da suíte humana rodada nos mesmos 7 arquivos-par, total do pacote 33% (vs. 31% da IA — ballpark parecido).

**Comparação de cobertura IA vs. Humano — os 7 arquivos-alvo (registrado em 14/09/2026):**

| Arquivo | IA (linha/branch/total) | Humano (linha/branch/total) |
|---|---|---|
| `app\task.py` (Task) | 75% / 54% / 70% | 57% / 86% / 63% |
| `app\base.py` (Celery) | 68% / 42% / 63% | 65% / 93% / 71% |
| `canvas.py` (Signature/chain/group) | 50% / 29% / 44% | 68% / 82% / 72% |
| `bootsteps.py` (Blueprint/Step) | 80% / 62% / 77% | 52% / 79% / 57% |
| `utils\dispatch\signal.py` (Signal) | 76% / 75% / 76% | 38% / 100% / 45% |
| `backends\cache.py` (CacheBackend) | 61% / 17% / 59% | 100% / 100% / 100% |
| `backends\base.py` (Backend) | 53% / 40% / 50% | 92% / 83% / 90% |

**Observação preliminar:** em 6 dos 7 arquivos, a suíte humana tem cobertura de *branch* bem mais alta (82–100%) que a de IA, mesmo às vezes cobrindo menos linhas — sugere testes humanos mais "cirúrgicos" (poucas linhas, mas ambos os lados de cada decisão exercitados). `bootsteps.py` é a exceção, com a IA vencendo nos três números. Hipótese a confirmar na próxima etapa (mutação): cobertura de branch alta tende a prever escore de mutação alto, então a expectativa é a suíte humana matar proporcionalmente mais mutantes.

### Mutação — mudança de ferramenta e incidentes resolvidos (14/09/2026)

**mutmut não roda nativamente no Windows** (a própria ferramenta exige WSL). Em vez de instalar WSL (mudança de sistema mais pesada, não fizemos sem decisão consciente do usuário), foi criado um script próprio, standalone, só com biblioteca padrão do Python (`ast`/`subprocess`): **`C:\claude\projeto-aplicacao\mutation_test.py`**. Implementa os operadores ROR/AOR/COR (documentados em `references/teste-mutacao.md` da skill `gerador-de-testes`); não inclui SDL nem os operadores de OO nesta versão leve.

Uso:
```
py C:\claude\projeto-aplicacao\mutation_test.py <arquivo_fonte.py> --test-cmd "<comando de teste>" --cwd <diretorio> [--max-mutants N] [--disable-pytest-plugin-autoload]
```

**Dois bugs encontrados e corrigidos durante a validação, antes de gerar qualquer dado real:**

1. **Ordem de travessia da árvore inconsistente entre as duas passadas** (contar os pontos mutáveis vs. aplicar a mutação no N-ésimo ponto) fazia o script mutar o nó errado em expressões aninhadas (ex.: uma comparação dentro de um `and`/`or`). Corrigido fazendo as duas passadas em ordem "pai antes dos filhos".
2. **Path com barra normal (`/`) não funciona como executável ao chamar `subprocess.run(..., shell=True)` no Windows** (que usa `cmd.exe` por baixo) — precisa ser `.venv\Scripts\python.exe` com contra-barra nesse contexto específico, mesmo que barra normal funcione em outros lugares (Bash direto, `cwd`, etc.).
3. **Incidente adicional descoberto via teste de sanidade** (forçar um `raise Exception` no topo do arquivo e confirmar que os testes realmente quebram): ao instalar `pip install -e .` do clone humano (`human_original`) no **mesmo venv** da suíte de IA, o Celery registra seu próprio plugin de pytest (`celery.contrib.pytest`) via entry-point do pacote instalado. O pytest carrega esse plugin **antes** do `conftest.py` da IA rodar seu `sys.path.insert`, entao `import celery` resolvia para o clone humano em vez do `repo_src` — e como as duas versões são idênticas (5.6.2), o `assert` de proteção do `conftest.py` da IA não detectava o problema. **Solução:** rodar os testes da suíte de IA com a variável de ambiente `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` (flag `--disable-pytest-plugin-autoload` do `mutation_test.py`). Isso não afeta os números de cobertura já coletados (Fase 3, seção acima), pois foram medidos **antes** de instalar o `human_original` nesse venv — só rodadas feitas *depois* disso (mutação e qualquer nova cobertura) precisam da flag.

**Resultado oficial — `bootsteps.py`, lado IA (17/17 mutantes, todos os pontos do arquivo):**
- Mortos: 6 | Vivos: 11 | **Escore de mutação: 35,3%**
- Comando usado: `.venv\Scripts\python.exe -m pytest test_estrutural_bootsteps.py test_estrutural_task.py -q` com `--disable-pytest-plugin-autoload`

**Comando padrão recomendado para os demais arquivos (lado IA)** — usa a suíte rápida completa (estrutural+funcional+v2, exclui integração/aceitação que sobem um worker real e deixam cada mutante ~50x mais lento):
```
.venv\Scripts\python.exe -m pytest test_estrutural_task.py test_estrutural_canvas.py test_estrutural_bootsteps.py test_estrutural_signal_backend.py test_funcional_app.py v2_metodologia_formal\test_decisao_retry_merge.py v2_metodologia_formal\test_decisao_signal_backend.py -q
```

**Comando padrão (lado humano)** — não precisa da flag `--disable-pytest-plugin-autoload` (só é necessária quando dois checkouts do mesmo pacote convivem no mesmo venv, o que só acontece do lado da IA):
```
..\.venv\Scripts\python.exe -m pytest t\unit\tasks\test_tasks.py t\unit\tasks\test_canvas.py t\unit\worker\test_bootsteps.py t\unit\utils\test_dispatcher.py t\unit\backends\test_cache.py t\unit\backends\test_base.py t\unit\app\test_app.py -q
```

**Incidente adicional resolvido (mesmo dia):** no Windows, quando uma mutação trava de verdade (loop infinito real introduzido pela mutação), `subprocess.run(..., shell=True, timeout=N)` mata só o `cmd.exe` (processo direto), não o `python.exe`/pytest de verdade rodando por baixo — que fica órfão e trava a leitura da saída para sempre, ignorando o timeout. Corrigido usando `taskkill /F /T /PID <pid>` (mata a árvore inteira) em vez de depender do timeout nativo do `subprocess.run`. Também foi adicionada a flag `--start-at N` para retomar uma rodada sem repetir mutantes já testados.

**Resultado — `app\base.py` (Celery), lado HUMANO (40/40 mutantes, arquivo completo):**
- Mortos: 28 | Vivos: 12 | **Escore de mutação: 70,0%**

### Resultado final consolidado — Celery (14/09/2026)

Todos os 7 arquivos, cobertura + mutação, os dois lados. Duas coincidências foram checadas e confirmadas pelo usuário (reexecução independente): `canvas.py` e `backends/base.py` do lado IA deram exatamente iguais (40/7/33/17,5%); `base.py` e `canvas.py` do lado humano também deram exatamente iguais (40/28/12/70,0%) — não é erro de cópia, é o resultado real.

| Arquivo | Cobertura Linha (IA/Hum) | Cobertura Branch (IA/Hum) | Escore de Mutação (IA/Hum) |
|---|---|---|---|
| `app\task.py` (Task) | 75% / 57% | 54% / 86% | 35,0% / 67,6% |
| `app\base.py` (Celery) | 68% / 65% | 42% / 93% | 37,5% / 70,0% |
| `canvas.py` (Signature/chain/group) | 50% / 68% | 29% / 82% | 17,5% / 70,0% |
| `bootsteps.py` (Blueprint/Step) | 80% / 52% | 62% / 79% | 35,3% / 64,7% |
| `utils\dispatch\signal.py` (Signal) | 76% / 38% | 75% / 100% | 60,0% / 70,0% |
| `backends\cache.py` (CacheBackend) | 61% / 100% | 17% / 100% | 100,0% / 100,0% |
| `backends\base.py` (Backend) | 53% / 92% | 40% / 83% | 17,5% / 62,5% |

**Conclusão do Celery:** a suíte humana venceu o escore de mutação em **6 dos 7 arquivos** (empate só em `cache.py`, onde ambas chegam a 100%). Isso confirma a hipótese levantada na etapa de cobertura: a suíte de IA às vezes toca mais linhas (`task.py`, `bootsteps.py`, `signal.py`), mas verifica menos decisões de fato — cobertura de linha alta não é sinônimo de teste forte. A suíte humana, mesmo cobrindo menos linhas em alguns arquivos (`canvas.py`, `backends/base.py`), mata proporcionalmente mais mutantes, ou seja, testa com mais intenção cada desvio de decisão.

**Status: Celery CONCLUÍDO.** Próximo repositório a comparar: a decidir com o usuário (Scrapy é o mais indicado por não ter nenhum ajuste pendente).

### 7.2 Scrapy (15/09/2026)

**Reorganização de pastas (mesmo dia, outra sessão em paralelo — ver nota da seção 2):** a suíte de IA agora mora em `testes-ia\scrapy\`, o código-fonte original em `repositorios-originais\scrapy\`, e o clone humano permanente em `scrapy\human_original\` (mesmo padrão do Celery, criado pela outra sessão). `conftest.py` da IA já veio ajustado para o novo caminho.

**Ambiente:** venv próprio em `testes-ia\scrapy\.venv` (deps de `requirements-testes.txt` + `defusedxml`, que faltava no arquivo) e outro em `scrapy\human_original\.venv` (`pip install -e .` + deps de teste do `tox.ini`: attrs, coverage, httpx, pexpect, pyftpdlib, pygments, pytest, pytest-cov, pytest-xdist, sybil, testfixtures, pytest-twisted).

**14 arquivos-alvo** (Scrapy não teve nenhum gap — todos com par humano confirmado):

| Arquivo | Classe(s) | Cobertura Linha (IA/Hum) | Cobertura Branch (IA/Hum) | Cobertura Total (IA/Hum) |
|---|---|---|---|---|
| `crawler.py` | CrawlerRunner | 45% / 71% | 20% / 54% | 39% / 67% |
| `downloadermiddlewares/httpauth.py` | HttpAuthMiddleware | 85% / 100% | 71% / 100% | 82% / 100% |
| `downloadermiddlewares/offsite.py` | OffsiteMiddleware | 98% / 100% | 83% / 100% | 96% / 100% |
| `downloadermiddlewares/redirect.py` | RedirectMiddleware | 81% / 92% | 60% / 81% | 76% / 89% |
| `downloadermiddlewares/retry.py` | RetryMiddleware | 91% / 99% | 69% / 96% | 85% / 98% |
| `http/request/__init__.py` | Request | 87% / 91% | 74% / 74% | 84% / 87% |
| `http/response/__init__.py` | Response | 91% / 98% | 83% / 92% | 90% / 97% |
| `http/response/text.py` | TextResponse/HtmlResponse | 90% / 97% | 70% / 92% | 85% / 96% |
| `item.py` | Item/Field | 93% / 100% | 95% / 100% | 93% / 100% |
| `settings/__init__.py` | BaseSettings/Settings | 71% / 100% | 58% / 100% | 67% / 100% |
| `signalmanager.py` | SignalManager | 82% / 76% | 100% / 100% | 82% / 76% |
| `spidermiddlewares/depth.py` | DepthMiddleware | 96% / 92% | 75% / 71% | 91% / 88% |
| `spidermiddlewares/urllength.py` | UrlLengthMiddleware | 100% / 100% | 100% / 100% | 100% / 100% |
| `spiders/__init__.py` | Spider | 83% / 93% | 70% / 80% | 81% / 91% |

**Observação preliminar:** ao contrário do Celery, aqui a IA às vezes vence (signalmanager.py, depth.py) — o padrão "humano sempre ganha" não é universal, precisa confirmar com mutação.

**Mutação — 3 incidentes durante a execução, todos resolvidos:**

1. **Mesmo bug de barra normal de novo** (agora nos scripts de lote `run_mutation_ia.sh`/`run_mutation_humano.sh`, variável `PY=".venv/Scripts/python.exe"`) — gerou uma primeira rodada inteira com **100% de escore em todos os arquivos, dos dois lados**, que parecia bom demais pra ser verdade e era: o comando nunca chegava a rodar (cmd.exe não resolve o executável com barra normal), então TODO mutante "morria" por o comando falhar sempre, não por causa da mutação. Descartados os `.mutation_report.json` dessa rodada e refeito com contra-barra.
2. **`--disable-pytest-plugin-autoload` quebrou os testes de crawl real** (`crawler.py`/`spiders/__init__.py`) — essa flag também desliga o `pytest-twisted` (autocarregado do mesmo jeito), que o Scrapy precisa para rodar as funções `async def` dos testes de integração/aceitação. Diferente do Celery, aqui os venvs da IA e do humano são **separados** desde o início, então essa flag nunca foi necessária — removida do script da IA.
3. **Notificação de conclusão falsa do harness** para o lote do lado humano: recebi "completed" enquanto o processo (confirmado via `Get-CimInstance Win32_Process`) ainda rodava de verdade, several arquivos adiante do ponto onde o log parecia ter parado. Ao intervir achando que tinha travado, apaguei por engano o `.mutation_backup` que o processo ainda usava, causando um `FileNotFoundError` no `shutil.copy2` de restauração final só para `request/__init__.py` (lado humano) — o conteúdo do arquivo em si não foi perdido (o restore por-mutante já tinha devolvido o original antes disso), só a rodada daquele arquivo específico crashou e teve que ser refeita isolada no final. Lição: **verificar processos reais via `Get-CimInstance`/`Get-Process` antes de agir sobre uma notificação de conclusão de uma tarefa em segundo plano com cadeia de subprocessos profunda (bash → py → python → subprocess shell=True → cmd.exe)**, não confiar cegamente nela.

**Resultado final consolidado — Scrapy (15/09/2026):**

| Arquivo | Classe | Linha (IA/Hum) | Branch (IA/Hum) | Mutação (IA/Hum) |
|---|---|---|---|---|
| `crawler.py` | CrawlerRunner | 45% / 71% | 20% / 54% | 8,3% / 30,0% |
| `downloadermiddlewares/httpauth.py` | HttpAuthMiddleware | 85% / 100% | 71% / 100% | 62,5% / 62,5% |
| `downloadermiddlewares/offsite.py` | OffsiteMiddleware | 98% / 100% | 83% / 100% | 80,0% / 100,0% |
| `downloadermiddlewares/redirect.py` | RedirectMiddleware | 81% / 92% | 60% / 81% | 58,6% / 75,0% |
| `downloadermiddlewares/retry.py` | RetryMiddleware | 91% / 99% | 69% / 96% | 80,0% / 100,0% |
| `http/request/__init__.py` | Request | 87% / 91% | 74% / 74% | 75,0% / 62,5% |
| `http/response/__init__.py` | Response | 91% / 98% | 83% / 92% | 70,0% / 75,0% |
| `http/response/text.py` | TextResponse/HtmlResponse | 90% / 97% | 70% / 92% | 100,0% / 100,0% |
| `item.py` | Item/Field | 93% / 100% | 95% / 100% | 100,0% / 100,0% |
| `settings/__init__.py` | BaseSettings/Settings | 71% / 100% | 58% / 100% | 16,0% / 75,0% |
| `signalmanager.py` | SignalManager | 82% / 76% | 100% / 100% | 47,4% / 47,4% |
| `spidermiddlewares/depth.py` | DepthMiddleware | 96% / 92% | 75% / 71% | 75,0% / 100,0% |
| `spidermiddlewares/urllength.py` | UrlLengthMiddleware | 100% / 100% | 100% / 100% | 100,0% / 100,0% |
| `spiders/__init__.py` | Spider | 83% / 93% | 70% / 80% | 100,0% / 100,0% |

**Conclusão do Scrapy:** dos 14 arquivos, a suíte humana venceu em **7** (`crawler.py`, `offsite.py`, `redirect.py`, `retry.py`, `settings/__init__.py`, `depth.py`, `response/__init__.py`), empatou em **6** (`httpauth.py`, `response/text.py`, `item.py`, `urllength.py`, `spiders/__init__.py`, `signalmanager.py`) e a IA venceu em **apenas 1** (`request/__init__.py`, 75% vs. 62,5%). Mesmo padrão do Celery se repete: a suíte humana testa com mais intenção as decisões do código, mesmo quando a IA cobre mais linhas (ex.: `crawler.py` e `settings/__init__.py`, onde a diferença de escore de mutação é grande apesar da cobertura de linha não ser tão díspar).

### Ampliação do `mutation_test.py` (15/09/2026, a pedido do usuário)

`response/__init__.py` e `signalmanager.py` inicialmente ficaram sem escore de mutação porque o código deles não usa nenhum operador relacional/aritmético/lógico — só `isinstance()`, checagens `is None`/`is not None` e chamadas de repasse. Adicionados dois operadores novos ao script, mantendo o mecanismo antigo (ROR/AOR/COR, por contador) intocado e testado sem regressão antes de aceitar dados novos:
- **IOR** (Identity Operator Replacement): troca `is` ↔ `is not`, reaproveitando o mesmo `visit_Compare` já usado por ROR (mesma ordem de contagem, sem risco de dessincronizar).
- **SDL** (Statement Deletion): substitui um comando simples (`Assign`, `Return`, `Raise`, `Expr`, `Delete`, `Assert`, `Break`, `Continue` — docstrings excluídas de propósito) por `pass`. Implementado com um mecanismo **independente** do contador antigo: localiza cada comando por posição exata no código-fonte (linha + coluna + tipo), que é garantidamente idêntica entre duas chamadas de `ast.parse()` sobre o mesmo texto — evita por construção o tipo de bug de ordem de travessia que já mordeu o ROR/AOR/COR uma vez.

Com isso: `response/__init__.py` foi de "sem pontos mutáveis" para 70,0% (IA) / 75,0% (humano); `signalmanager.py` foi de "sem pontos mutáveis" para 47,4% / 47,4% (empate exato, ambos os lados testam essa classe pequena com o mesmo nível — modesto — de rigor).

**Status: Scrapy CONCLUÍDO (14/14 arquivos com escore de mutação).**

### 7.3 Requests — CONCLUÍDO

**Ajustes da Etapa 2 aplicados e validados (28/09/2026):**
- `v2_metodologia_formal/test_funcional_classes_valor_limite.py`: CT01–CT07 (`prepare_url`) reescritos para passar por `Request(...).prepare()` em vez de chamar `PreparedRequest.prepare_url()` isolado; CT31 (`HTTPBasicAuth`) reescrito para usar `auth=(123, "senha")` (tupla) em vez de instanciar `HTTPBasicAuth` direto.
- `v2_metodologia_formal/test_estrutural_decisao.py`: CT19–CT26 (`rebuild_method`) reescritos para passar por redirecionamentos reais contra o servidor local (`conftest.py::live_server`), em vez de chamar `Session.rebuild_method(p, r)` isolado com objetos fabricados — confirmado por grep que a suíte humana (`tests/test_requests.py`) nunca chama `rebuild_method` direto em nenhum nível, só observa o método final da requisição após o redirect. Duas rotas novas (`/redirect-307-temporary`, `/redirect-308-permanent-preserva`) adicionadas ao `conftest.py` para cobrir as regras R7 (307/308 sempre preservam método e corpo) que não tinham endpoint ainda.
- `should_strip_auth` (CT27–CT30) e o Digest (CT32–CT33) mantidos como já estavam: a própria suíte humana também chama `should_strip_auth` isolado, então não havia ajuste a fazer ali.
- **Removidos** (sem par humano possível, confirmado nesta etapa): `prepare_content_length`, `merge_setting`/`merge_hooks`, `BaseAdapter`, `HTTPProxyAuth` — já não tinham teste na suíte de IA (ajuste feito em sessão anterior).
- Validado: suíte de IA completa (v1 + v2) — **209 testes, todos passando** (`.venv\Scripts\python.exe -m pytest . -q`).

**Ambiente:**
- `testes-ia\requests\.venv\` criado, dependências de `requirements-testes.txt` instaladas.
- `requests\human_original\.venv\` criado, `pip install -e ".[socks]"` + `pytest-httpbin`/`httpbin`/`trustme` instalados. Versão confirmada: `requests 2.34.2` resolvendo para `human_original\src\requests\`.
- **Incidente:** 1 teste humano falha por ambiente (`test_different_connection_pool_for_tls_settings_verify_bundle_unexpired_cert`) — o bundle de certificado `tests/certs/valid/ca/ca.crt` não existe no checkout (pasta `certs/valid/ca` vazia; só `certs/expired/ca` tem os arquivos gerados). Não é um problema introduzido por este projeto — é um artefato de geração de certificado (`trustme`/Makefile) que não roda neste ambiente. Deselecionado (`--deselect`) de todos os comandos de teste do lado humano, documentado aqui em vez de silenciado.

**Arquivos-alvo (8, mapeados por área do código-fonte testada por cada arquivo estrutural da IA):** `models.py`, `sessions.py`, `adapters.py`, `auth.py`, `cookies.py`, `hooks.py`, `structures.py`, `api.py`.

**Cobertura medida (`pytest --cov=requests --cov-branch --cov-report=html`):**

| Arquivo | Linha IA | Linha Humano | Branch IA | Branch Humano |
|---|---|---|---|---|
| models.py | 75,0% | 92,2% | 59,8% | 88,6% |
| sessions.py | 90,0% | 95,0% | 76,0% | 91,7% |
| adapters.py | 73,7% | 86,6% | 48,6% | 82,4% |
| auth.py | 82,7% | 86,9% | 56,1% | 62,1% |
| cookies.py | 75,6% | 79,3% | 57,1% | 56,1% |
| hooks.py | 100,0% | 100,0% | 100,0% | 100,0% |
| structures.py | 92,0% | 98,0% | 66,7% | 83,3% |
| api.py | 95,5% | 86,4% | — (sem desvios) | — (sem desvios) |

**Mutação** (`mutation_test.py`, `--max-mutants 15` para os 5 arquivos grandes — `models/sessions/adapters/auth/cookies`, ~150–370 pontos mutáveis cada — e `--max-mutants 40` (sem corte real) para `hooks/structures/api`; mesmo corte nos dois lados para sortear e comparar exatamente os mesmos pontos):

| Arquivo | Mutantes | Escore IA | Escore Humano |
|---|---|---|---|
| models.py | 15 | 60,0% | 86,7% |
| sessions.py | 15 | 46,7% | 73,3% |
| adapters.py | 15 | 33,3% | 66,7% |
| auth.py | 15 | 46,7% | 33,3% |
| cookies.py | 15 | 53,3% | 66,7% |
| hooks.py | 10 | 100,0% | 100,0% |
| structures.py | 30 | 60,0% | 76,7% |
| api.py | 9 | 88,9% | 55,6% |

**Incidente — flakiness intermitente no lote humano:** o lote (`requests\human_original\run_mutation_humano.sh`) travou 3 vezes na checagem de ambiente ("comando falha mesmo sem mutação"), sempre num arquivo diferente, sem padrão de qual arquivo. Confirmado por reexecução manual do EXATO mesmo comando, isolado, logo em seguida — sempre passou (364 testes) — descartando comando quebrado. Causa provável: esgotamento de portas/`TIME_WAIT` do servidor local que `pytest-httpbin` sobe a cada execução, depois de dezenas de execuções seguidas na mesma sessão do Windows (não confirmado com certeza, mas é a explicação mais provável dada a natureza do teste). **Correção:** adicionado retry (até 3 tentativas, com 20s de espera entre elas) em `run_mutation_humano.sh` — na prática, todo arquivo passou já na 1ª ou 2ª tentativa depois disso.

**Conclusão do Requests:** dos 8 arquivos, a suíte humana venceu em **5** (`models.py`, `sessions.py`, `adapters.py`, `cookies.py`, `structures.py`), a IA venceu em **2** (`auth.py`, `api.py`) e empatou em **1** (`hooks.py`, 100%/100%). Mesmo padrão dos outros dois repositórios: mesmo onde a IA cobre mais linha/branch (ex.: `sessions.py`: 90%/76% IA vs. 95%/91,7% Humano — diferença pequena de cobertura), o escore de mutação humano é bem maior (46,7% vs. 73,3%), sinal de testes mais intencionais, não só mais abrangentes. A IA se destacou em `api.py` (testes de aceitação/integração fim-a-fim contra o servidor local, cobrindo a API pública de ponta a ponta) e em `auth.py` (onde a suíte humana tem menos casos de borda do Digest/Basic auth do que a suíte de IA gerada a partir das técnicas formais da skill).

**Status: Requests CONCLUÍDO (8/8 arquivos com cobertura + mutação).**

**Correção pós-entrega (29/09/2026):** `cov_ia`/`cov_humano` reduzidos de 19 para 16 arquivos cada, removendo páginas de módulos fora do escopo (`__init__.py`, `_internal_utils.py`, `certs.py`, `compat.py`, `exceptions.py`, `help.py`, `packages.py`, `status_codes.py`, `utils.py`) que o `coverage.py` gerava por serem tocados durante a execução dos testes, mesmo sem fazer parte da comparação. Ver detalhes técnicos (incluindo um bug real encontrado na tentativa inicial de restringir via `--cov=` pontuado) na seção 7.4, nota sobre o Conan.

### 7.4 Conan — CONCLUÍDO

**Ajustes da Etapa 2:** ao revisar a suíte de IA, os 3 arquivos v1 (`test_estrutural_options.py`, `test_estrutural_requires.py`) e os 2 arquivos v2 (`test_decisao_package_option.py`, `test_decisao_version_requires.py`) já estavam corretamente reescritos via `TestClient` (receitas reais + `conan create`/`graph info`), sem nenhuma instanciação direta de `_PackageOption(s)`/`Requirement(s)`. Só restava um ponto: `test_estrutural_version.py::test_upper_bound_exclui_prereleases` ainda instanciava `VersionRange(...)` isolado — reescrito para resolver a mesma regra (pré-release da própria versão-limite não entra na faixa) via `requires="liba/[<limite]"` real, resolvido por `graph info`, reaproveitando os helpers (`_lib`, `_app_com_faixa`, `_versao_resolvida`) já usados pelo resto do arquivo para `VersionRange`. Import de `VersionRange` agora não usado, removido. Validado: suíte de IA completa (v1 + v2) — **89 testes, todos passando**.

**Incidente — versão do clone humano não batia com a da suíte de IA (28/09/2026):** ao instalar o `conan/human_original/` (clonado por outra sessão em 11/09/2026), `conan.__version__` acusou `2.33.0-dev`, enquanto `repositorios-originais/conan` (usado pela suíte de IA) é `2.32.0-dev` — **códigos-fonte de commits diferentes**, o que invalidaria a comparação (diferenças de escore poderiam vir do código, não dos testes). `repositorios-originais/conan` não tem `.git` próprio (só arquivos copiados pela reorg da outra sessão), então não havia como obter o hash exato ali. Resolvido cruzando a API do GitHub (`conan-io/conan`): a janela de commits com `__version__ == '2.32.0-dev'` vai de `638dbef1` (23/07/2026) a `1521d2cf` (bump para 2.32.0 em 31/08/2026); dentro dela, só um commit (`a8f9da35`, 26/08/2026) tocou `requires.py` (feature `package_type_traits`) — como `repositorios-originais/conan` **não tem** essa feature, o commit usado é necessariamente o pai dele. Confirmado por diff byte-a-byte (ignorando CRLF/LF) dos 4 arquivos-alvo (`options.py`, `requires.py`, `version.py`, `version_range.py`) contra o commit `bff82174` — os 4 batem exatamente. `conan/human_original/` realinhado para esse commit (`git fetch --depth 1` + `git reset --hard`, dentro do próprio repositório git já existente, sem apagar a pasta) e reinstalado (`pip install -e .`); `conan.__version__` confirma `2.32.0-dev` agora.

**Ambiente:**
- `testes-ia\conan\.venv\` criado, dependências de `requirements-testes.txt` instaladas.
- `conan\human_original\.venv\` criado, `pip install -r conans/requirements.txt -r conans/requirements_dev.txt` + `pip install -e .`.

**Arquivos-alvo (4):** `options.py`, `requires.py`, `version.py`, `version_range.py` (todos em `conan/internal/model/`). Suíte humana do Conan não tem 1 arquivo de teste por classe (como Celery/Scrapy) nem é monolítica (como Requests) — é organizada em `test/unittests/` (unitário direto) e `test/integration/`+`test/functional/` (via CLI/grafo). `options.py` e `version.py`/`version_range.py` têm unittest direto (`test/unittests/model/options_test.py`, `test/unittests/model/version/*.py`); `requires.py` **não tem nenhum unittest direto** — só é exercitado via integração (`self.requires()`/`tool_requires()` num conanfile real, resolvido por `conan create`/`graph info`), confirmado por busca no código-fonte da suíte humana — é exatamente o mesmo nível de abstração que a suíte de IA reescrita usa agora para essa classe.

**Cobertura medida (`pytest --cov=conan --cov-branch --cov-report=html`):**

| Arquivo | Linha IA | Linha Humano | Branch IA | Branch Humano |
|---|---|---|---|---|
| options.py | 84,9% | 95,6% | 72,6% | 89,6% |
| requires.py | 67,7% | 84,6% | 48,7% | 71,7% |
| version.py | 89,0% | 94,1% | 96,7% | 100,0% |
| version_range.py | 53,9% | 94,1% | 44,7% | 93,2% |

**Mutação** (`--max-mutants 15` para `options.py`/`requires.py` — mais lentos do lado humano, ~58–61s por execução via `TestClient` real — e `--max-mutants 40` para `version.py`/`version_range.py`, mesmo corte nos dois lados):

| Arquivo | Mutantes | Escore IA | Escore Humano |
|---|---|---|---|
| options.py | 15 | 66,7% | 86,7% |
| requires.py | 15 | 53,3% | 60,0% |
| version.py | 40 | 85,0% | 65,0% |
| version_range.py | 40 | 32,5% | 85,0% |

**Conclusão do Conan:** dos 4 arquivos, a suíte humana venceu em **3** (`options.py`, `requires.py`, `version_range.py`) e a IA venceu em **1** (`version.py`, 85,0% vs. 65,0%). `version_range.py` é o caso mais marcante do repositório inteiro: cobertura de linha da IA bem menor (53,9% vs. 94,1% humano — a IA testa a faixa de versão quase só pelos operadores "felizes", sem explorar tantos casos de erro/borda quanto a suíte humana, que tem décadas de bugs de parsing de versão acumulados em forma de teste de regressão), e o escore de mutação reflete isso de forma amplificada (32,5% vs. 85,0%). Já em `version.py` — a única classe de valor pura do lote, sem depender de grafo/cache — a suíte de IA (gerada com foco explícito em classes de equivalência e casos de borda: zeros à direita, `bump()`, comparação numérica vs. lexicográfica) supera a suíte humana, um padrão que também apareceu em `auth.py`/`api.py` do Requests: em unidades pequenas e autocontidas, a técnica formal de geração de testes consegue igualar ou superar décadas de teste de regressão humano.

**Status: Conan CONCLUÍDO (4/4 arquivos com cobertura + mutação).**

**Correção pós-entrega (29/09/2026) — pastas `cov_ia`/`cov_humano` com centenas de arquivos irrelevantes:** o comando original (`--cov=conan`, pacote inteiro) fazia o `coverage.py` gerar uma página HTML para *todo* módulo tocado durante a execução dos testes — no Conan isso significa ~330 páginas por lado (o `TestClient` aciona por baixo dos panos dezenas de módulos internos: parser de CLI, cache, toolchains etc.), quando só 4 nos interessam. Corrigido gerando a cobertura do pacote inteiro (continua sendo o jeito confiável de medir) e depois filtrando o relatório HTML só para os 4 arquivos-alvo via `coverage html --include=".../options.py,.../requires.py,.../version.py,.../version_range.py"` — reduz `cov_ia/`/`cov_humano/` de ~330 para 12 arquivos cada (4 páginas de código + índice/assets do próprio coverage.py), sem mudar nenhum número (conferido). Mesma correção aplicada retroativamente a Requests (19→16 arquivos) e ao Dask (185→13/... arquivos) abaixo.

**Nota técnica (mesmo incidente):** a primeira tentativa de restringir foi passar `--cov=conan.internal.model.options --cov=conan.internal.model.requires ...` (múltiplos módulos pontuados) direto no `pytest`. Isso funcionou para o Conan, mas quebrou 161 dos 364 testes do lado humano do **Requests** com `ValueError: You can only merge into CookieJar` — um `isinstance()` falhando contra a própria classe, sintoma clássico de duas cópias do mesmo módulo carregadas em `sys.modules` (a instalação editável do Requests, via `pip install -e .`, parece reagir mal a `--cov=` apontando pra submódulos específicos antes do pytest terminar de resolver o path). Resolvido usando sempre `--cov=<pacote inteiro>` para coletar os dados (nunca falhou, nos 3 repositórios) e filtrando só na geração do HTML.

### 7.5 Dask — CONCLUÍDO

**Ajuste da Etapa 2:** já feito em sessão anterior — `test_estrutural_core.py` documenta explicitamente por que `core.toposort()` não tem teste (sem par humano em nenhum nível, nas 177 pastas `tests/` do repositório). Confirmado por grep: nenhuma chamada a `toposort` na suíte de IA. Suíte de IA completa validada: **119 testes, todos passando**.

**Arquivos-alvo (5):** `core.py`, `config.py`, `optimization.py`, `tokenize.py`, `delayed.py` (todos em `dask/`, mapeados 1:1 pelos arquivos estruturais/funcionais da IA). Confirmado que os 5 arquivos são byte-a-byte idênticos entre `repositorios-originais/dask` e `dask/human_original` (commit `817e5ffc`, já fixado corretamente desde a reorg da outra sessão — sem o incidente de versão que aconteceu no Conan).

**Ambiente:**
- `testes-ia\dask\.venv\` criado, dependências de `requirements-testes.txt` instaladas.
- `dask\human_original\.venv\` criado, `pip install -e .` (deps principais: click/cloudpickle/fsspec/packaging/partd/pyyaml) + plugins de teste mínimos (pytest-mock/rerunfailures/timeout/xdist) — sem `numpy`/`pandas`/`distributed`, que não são necessários para os 5 arquivos-alvo (mesmo escopo "sem numpy/pandas" que a suíte de IA já usa); suíte humana pula ~59 testes que dependem desses extras opcionais, o que é esperado e não afeta a comparação.
- Ambos os lados MUITO mais rápidos que Requests/Conan (suíte humana completa dos 5 arquivos roda em ~8s) — mantido `--max-mutants 40` (padrão, sem corte) nos dois lados.

**Cobertura medida (`pytest --cov=dask --cov-branch --cov-report=html`):**

| Arquivo | Linha IA | Linha Humano | Branch IA | Branch Humano |
|---|---|---|---|---|
| core.py | 87,0% | 90,9% | 82,4% | 86,6% |
| config.py | 68,7% | 94,4% | 60,7% | 94,4% |
| optimization.py | 15,4% | 94,5% | 12,2% | 87,4% |
| tokenize.py | 51,2% | 56,5% | 55,0% | 67,5% |
| delayed.py | 53,8% | 88,2% | 32,0% | 81,2% |

(core.py humano remedido junto da correção de escopo da cobertura — 90,9%/86,6%, ~1 p.p. acima da primeira medição por variação natural entre execuções, sem nenhuma mutação residual no arquivo, confirmado por `git status` limpo.)

**Mutação** (`--max-mutants 40`, padrão, sem corte — os 5 arquivos são pequenos o bastante para caber inteiros nesse limite):

| Arquivo | Mutantes | Escore IA | Escore Humano |
|---|---|---|---|
| core.py | 40 | 75,0% | 65,0% |
| config.py | 40 | 52,5% | 77,5% |
| optimization.py | 40 | 10,0% | 77,5% |
| tokenize.py | 40 | 37,5% | 55,0% |
| delayed.py | 40 | 40,0% | 82,5% |

**Conclusão do Dask:** dos 5 arquivos, a suíte humana venceu em **4** (`config.py`, `optimization.py`, `tokenize.py`, `delayed.py`) e a IA venceu em **1** (`core.py`, 75,0% vs. 65,0%). `optimization.py` é o caso mais extremo de todo o projeto até aqui: a suíte de IA cobre só 15,4% das linhas (contra 94,5% da suíte humana) e mata apenas 10,0% dos mutantes (contra 77,5%) — a suíte de IA testa `cull()`/`inline()` só nos casos de uso mais diretos, enquanto a suíte humana do Dask exercita `optimization.py` indiretamente através de praticamente toda a bateria de testes de grafos de tarefas do projeto (schedulers, collections, etc.), um nível de cobertura indireta que a suíte de IA — escrita olhando só a assinatura pública das duas funções — não tinha como replicar. Em `core.py`, por outro lado — as primitivas puras de grafo de tarefas (dict + tuplas, sem I/O) — a suíte de IA, com foco explícito em classes de equivalência e detecção de ciclo, supera a humana; mesmo padrão de "IA se destaca em unidades pequenas e autocontidas" já visto em `version.py` (Conan) e `auth.py`/`api.py` (Requests).

**Status: Dask CONCLUÍDO (5/5 arquivos com cobertura + mutação). Os 5 repositórios da comparação estão concluídos.**

## 8. Próximos passos

- [x] Celery concluído (cobertura + mutação, tabela final na seção 7.1).
- [x] Scrapy concluído (cobertura + mutação, tabela final na seção 7.2).
- [x] Requests concluído (cobertura + mutação, tabela final na seção 7.3).
- [x] Conan concluído (cobertura + mutação, tabela final na seção 7.4).
- [x] Gerar `descricao-comparacao.txt` + material de apresentação de Requests e Conan em `comparativo-tests\requests\` e `comparativo-tests\conan\` (mesmo padrão do Celery/Scrapy).
- [x] Dask concluído (cobertura + mutação, tabela final na seção 7.5) — `toposort` já estava fora do escopo desde uma sessão anterior.
- [x] Corrigir escopo das pastas `cov_ia`/`cov_humano` de Requests, Conan e Dask para conter só os arquivos comparados (não o pacote inteiro).
- [ ] Gerar `descricao-comparacao.txt` + material de apresentação do Dask em `comparativo-tests\dask\`.
- [ ] Montar o material de apresentação final com os 5 repositórios.
