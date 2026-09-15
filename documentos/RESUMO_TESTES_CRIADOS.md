# Resumo dos testes criados — 5 repositórios

Descrição de todos os testes criados nesta iniciativa: para cada
repositório, o caminho completo local, a origem do código, os arquivos de
teste (v1 — ad-hoc, e v2 — metodologia formal de QA) e as classes/módulos
especificamente exercitados por eles.

Metodologia comum aos 5: nenhum teste foi escrito olhando a suíte de
testes já existente do próprio projeto (só código de produção) — o
objetivo é comparar depois esta suíte independente contra a suíte
mantida pelos humanos de cada projeto.

---

## 1. Requests

- **Testes de IA:** `C:\claude\projeto-aplicacao\testes-ia\requests\`
- **Código-fonte sob teste:** `C:\claude\projeto-aplicacao\repositorios-originais\requests\requests\`
- **Origem:** [github.com/psf/requests](https://github.com/psf/requests), versão `2.34.2`

> **CAMINHO DOS TESTES ORIGINAIS DO PROJETO (humanos, nunca lidos/usados na escrita dos testes de IA):**
> `tests/` na raiz do clone — irmã do pacote `src/requests/`.
> Localização permanente: `C:\claude\projeto-aplicacao\testes-humanos\requests\tests\`

### v1 — suíte ad-hoc (181 testes; revisados em 14/09 — ver nota abaixo)

| Arquivo | Tipo | Classes/módulos testados |
|---|---|---|
| `test_estrutural_models.py` | Estrutural | `PreparedRequest`, `Request`, `Response` (`prepare_url`/`prepare_body` via `Request(...).prepare()`, `raise_for_status`, `iter_content`, `json()`, `links`) |
| `test_estrutural_sessions.py` | Estrutural | `Session`, `SessionRedirectMixin` (`rebuild_method` via redirects reais, `should_strip_auth`, `get_adapter`) |
| `test_estrutural_adapters_auth.py` | Estrutural | `HTTPAdapter`, `HTTPBasicAuth` (igualdade), `HTTPDigestAuth` |
| `test_estrutural_cookies_hooks.py` | Estrutural | `RequestsCookieJar`, `CaseInsensitiveDict`, `LookupDict`, `dispatch_hook` |
| `test_funcional_api.py` | Funcional | API pública (`requests.get/post/put/...`, `Session`) |
| `test_integracao.py` | Integração | `Session` + `HTTPAdapter` + `HTTPBasicAuth` (via `auth=(user,pass)`)/`HTTPDigestAuth` + cookies, ponta a ponta |
| `test_aceitacao.py` | Aceitação | Histórias de usuário sobre a API pública |

### v2 — metodologia formal (28 testes; revisados em 14/09)

Caminho dos testes: `C:\claude\projeto-aplicacao\testes-ia\requests\v2_metodologia_formal\` — plano: `documentos\requests\PLANO_DE_TESTE.md`

| Arquivo | Classes/módulos testados |
|---|---|
| `test_funcional_classes_valor_limite.py` | `PreparedRequest.prepare_url` (classes de equivalência), `Response.raise_for_status` (valor limite 399/400/499/500/599/600), `HTTPBasicAuth`, `HTTPDigestAuth` |
| `test_estrutural_decisao.py` | `Session.rebuild_method`, `Session.should_strip_auth` (tabelas de decisão) |

**Total Requests: 209 testes.**

**Nota (14/09/2026) — ajustes consolidados de correspondência com testes
humanos:** removidos `PreparedRequest.prepare_content_length`,
`merge_setting`/`merge_hooks`, `BaseAdapter` e `HTTPProxyAuth` (sem
correspondente humano possível, em nenhum nível — detalhe no
[README.md](requests/README.md) do repositório); `prepare_url`,
`prepare_body`, `rebuild_method` e `HTTPBasicAuth` foram reescritos para
o mesmo nível de abstração que um consumidor da biblioteca observaria,
em vez de chamar o método/classe interno direto.

---

## 2. Scrapy

- **Testes de IA:** `C:\claude\projeto-aplicacao\testes-ia\scrapy\`
- **Código-fonte sob teste:** `C:\claude\projeto-aplicacao\repositorios-originais\scrapy\scrapy\`
- **Origem:** [github.com/scrapy/scrapy](https://github.com/scrapy/scrapy), versão `2.17.0`

> **CAMINHO DOS TESTES ORIGINAIS DO PROJETO (humanos, nunca lidos/usados na escrita dos testes de IA):**
> `tests/` (e `tests_typing/`) na raiz do clone — irmã do pacote `scrapy/`.
> Localização permanente: `C:\claude\projeto-aplicacao\testes-humanos\scrapy\tests\`

### v1 — suíte ad-hoc (144 testes)

| Arquivo | Tipo | Classes/módulos testados |
|---|---|---|
| `test_estrutural_http.py` | Estrutural | `Request`, `Response`, `TextResponse`, `HtmlResponse` |
| `test_estrutural_settings_signals.py` | Estrutural | `BaseSettings`, `Settings`, `SignalManager` |
| `test_estrutural_downloadermiddlewares.py` | Estrutural | `RedirectMiddleware`, `RetryMiddleware`, `HttpAuthMiddleware`, `OffsiteMiddleware` |
| `test_estrutural_spidermiddlewares_item.py` | Estrutural | `DepthMiddleware`, `UrlLengthMiddleware`, `Item`, `Field` |
| `test_integracao_crawl.py` | Integração | `Spider`, `CrawlerRunner`, engine + reactor Twisted reais (crawl completo) |
| `test_aceitacao_crawl.py` | Aceitação | Histórias de usuário com crawls reais |

### v2 — metodologia formal (32 testes)

Caminho dos testes: `C:\claude\projeto-aplicacao\testes-ia\scrapy\v2_metodologia_formal\` — plano: `documentos\scrapy\PLANO_DE_TESTE.md`

| Arquivo | Classes/módulos testados |
|---|---|
| `test_decisao_redirect_retry.py` | `RedirectMiddleware` (guardas + troca de verbo + remoção de `Cookie`/`Authorization`), `RetryMiddleware` |
| `test_decisao_depth_offsite.py` | `DepthMiddleware`, `OffsiteMiddleware` |
| `test_valor_limite_urllength.py` | `UrlLengthMiddleware` (valor limite) |

**Total Scrapy: 176 testes.**

---

## 3. Celery

- **Testes de IA:** `C:\claude\projeto-aplicacao\testes-ia\celery\`
- **Código-fonte sob teste:** `C:\claude\projeto-aplicacao\repositorios-originais\celery\celery\`
- **Origem:** [github.com/celery/celery](https://github.com/celery/celery), versão `5.6.2`

> **CAMINHO DOS TESTES ORIGINAIS DO PROJETO (humanos, nunca lidos/usados na escrita dos testes de IA):**
> `t/` na raiz do clone — irmã do pacote `celery/`.
> Localização permanente: `C:\claude\projeto-aplicacao\testes-humanos\celery\t\`

### v1 — suíte ad-hoc (65 testes)

| Arquivo | Tipo | Classes/módulos testados |
|---|---|---|
| `test_estrutural_task.py` | Estrutural | `Task` (`.apply`, `.retry`, hooks `before_start`/`on_success`/`on_failure`) |
| `test_estrutural_canvas.py` | Estrutural | `Signature`, `chain`, `group` |
| `test_estrutural_bootsteps.py` | Estrutural | `Blueprint`, `Step`, `StartStopStep` |
| `test_estrutural_signal_backend.py` | Estrutural | `Signal` (`celery.utils.dispatch`), `CacheBackend` |
| `test_funcional_app.py` | Funcional | `Celery` (app: registro de tasks, `config_from_object`, `send_task`) |
| `test_integracao_worker.py` | Integração | Worker embutido real (`start_worker`), fila→execução→resultado |
| `test_aceitacao_worker.py` | Aceitação | Histórias de usuário com worker real |

### v2 — metodologia formal (18 testes)

Caminho dos testes: `C:\claude\projeto-aplicacao\testes-ia\celery\v2_metodologia_formal\` — plano: `documentos\celery\PLANO_DE_TESTE.md`

| Arquivo | Classes/módulos testados |
|---|---|
| `test_decisao_retry_merge.py` | `Task.retry()` (modo eager), `Signature._merge()`/`clone()` |
| `test_decisao_signal_backend.py` | `Signal.send()`, `Backend.mark_as_done`/`mark_as_failure` |

**Total Celery: 83 testes.**

---

## 4. Conan

- **Testes de IA:** `C:\claude\projeto-aplicacao\testes-ia\conan\`
- **Código-fonte sob teste:** `C:\claude\projeto-aplicacao\repositorios-originais\conan\conan\` (+ `conans\`, pacote legado de servidor)
- **Origem:** [github.com/conan-io/conan](https://github.com/conan-io/conan), versão `2.32.0-dev`

> **CAMINHO DOS TESTES ORIGINAIS DO PROJETO (humanos, nunca lidos/usados na escrita dos testes de IA):**
> `test/functional/` e `test/integration/` na raiz do clone — **não** confundir
> com `conan/test/utils/` (dentro do pacote), que é a ferramenta pública de
> teste do próprio Conan (`TestClient`), legitimamente usada nesta suíte.
> Localização permanente: `C:\claude\projeto-aplicacao\testes-humanos\conan\test\`

### v1 — suíte ad-hoc (70 testes; revisados em 14/09 — ver nota abaixo)

| Arquivo | Tipo | Classes/módulos testados |
|---|---|---|
| `test_estrutural_version.py` | Estrutural | `Version` (por instanciação), `VersionRange` (via `requires="pkg/[faixa]"` real + `graph info`) |
| `test_estrutural_options.py` | Estrutural | `_PackageOption`, `_PackageOptions`, `Options` — via `TestClient`/receitas reais |
| `test_estrutural_requires.py` | Estrutural | `Requirement`, `Requirements` — via `TestClient`/grafo real |
| `test_funcional_cli.py` | Funcional | CLI (`conan new/create/list/remove/profile/config/graph info`) via `TestClient` |
| `test_integracao_graph.py` | Integração | Resolução real de grafo (`internal/graph/*`), version ranges, opções, lockfile |
| `test_aceitacao_workflow.py` | Aceitação | Histórias de usuário com o mesmo grafo real |

### v2 — metodologia formal (19 testes; revisados em 14/09)

Caminho dos testes: `C:\claude\projeto-aplicacao\testes-ia\conan\v2_metodologia_formal\` — plano: `documentos\conan\PLANO_DE_TESTE.md`

| Arquivo | Classes/módulos testados |
|---|---|
| `test_decisao_version_requires.py` | `Version.__lt__` (por instanciação), `Requirement.__eq__`/`__hash__` (deduplicação, via `TestClient`/grafo) |
| `test_decisao_package_option.py` | `_PackageOption._set` (congelamento e marcação "importante") — via `TestClient`/receitas reais |

**Total Conan: 89 testes.**

**Nota (14/09/2026) — ajustes consolidados:** diferente do Requests,
nenhum dos 3 alvos revistos (`_PackageOption`/`_PackageOptions`,
`Requirement`/`Requirements`, `VersionRange`) foi removido — todos
tinham correspondente humano possível, só precisavam ser exercitados
via `TestClient` com receitas reais e o grafo resolvido, nunca
instanciando o modelo interno direto (detalhe no
[README.md](conan/README.md) do repositório).

---

## 5. Dask

- **Testes de IA:** `C:\claude\projeto-aplicacao\testes-ia\dask\`
- **Código-fonte sob teste:** `C:\claude\projeto-aplicacao\repositorios-originais\dask\dask\`
- **Origem:** [github.com/dask/dask](https://github.com/dask/dask), commit `817e5ffc1208346630b111860571024b0c6ec9bd` (clone raso, sem tag de versão)

> **CAMINHO DOS TESTES ORIGINAIS DO PROJETO (humanos, nunca lidos/usados na escrita dos testes de IA):**
> Não existe uma pasta única — o Dask espalha `tests/` **dentro de cada
> subpacote de produção**: `dask/array/tests/`, `dask/dataframe/tests/`,
> `dask/bag/tests/`, `dask/bytes/tests/`, `dask/diagnostics/tests/`,
> `dask/widgets/tests/`, `dask/array/_array_expr/tests/`, entre outros.
> Foi justamente essa mistura que causou o incidente descrito no achado
> abaixo. Localização permanente: `C:\claude\projeto-aplicacao\testes-humanos\dask\dask\`
> (subpastas `<módulo>\tests\` dentro dela, mesma estrutura relativa do original).

### v1 — suíte ad-hoc (105 testes; reescrita em 10/09 após o incidente descrito no achado abaixo, e revisada em 14/09 — ver nota abaixo)

| Arquivo | Tipo | Classes/módulos testados |
|---|---|---|
| `test_estrutural_core.py` | Estrutural | `core.py` (`istask`, `iskey`, `get`, `get_dependencies`, `getcycle`, `isdag`, `subs`, `quote`, `literal`) |
| `test_estrutural_tokenize.py` | Estrutural | `tokenize()`, `normalize_token` |
| `test_estrutural_config.py` | Estrutural | `config.update`, `config.merge`, `config.set`, `config.get`, `collect_env` |
| `test_estrutural_optimization.py` | Estrutural | `cull()`, `inline()` |
| `test_funcional_delayed.py` | Funcional | `delayed()`, `Delayed` |
| `test_integracao_scheduler.py` | Integração | `threaded.get` (pool de threads real), `local.get_sync` |
| `test_aceitacao_pipeline.py` | Aceitação | Histórias de usuário com schedulers reais |

### v2 — metodologia formal (14 testes)

Caminho dos testes: `C:\claude\projeto-aplicacao\testes-ia\dask\v2_metodologia_formal\` — plano: `documentos\dask\PLANO_DE_TESTE.md`

| Arquivo | Classes/módulos testados |
|---|---|
| `test_decisao_config_tokenize.py` | `dask.config.update()`, `tokenize._maybe_raise_nondeterministic`, `dask.config.get()` |

**Total Dask: 119 testes.**

**Nota (14/09/2026) — ajustes consolidados:** removida
`core.toposort()` (a função pública que devolve a ordem topológica) —
nenhuma das 177 pastas `tests/` do repositório a exercita, em nenhum
nível, direto ou indireto. `getcycle`/`isdag` continuam testadas
normalmente: elas compartilham o algoritmo interno `_toposort`, só não
passam pelo caminho específico de `toposort()` (detalhe no
[README.md](dask/README.md) do repositório).

---

## Total geral

Requests, Conan e Dask foram revisados em 14/09/2026 (ajustes
consolidados de correspondência com testes humanos — ver nota em cada
seção); Scrapy e Celery não foram alterados nessa revisão.

| Repositório | v1 | v2 | Total |
|---|---|---|---|
| Requests | 181 | 28 | 209 |
| Scrapy | 144 | 32 | 176 |
| Celery | 65 | 18 | 83 |
| Conan | 70 | 19 | 89 |
| Dask | 105 | 14 | 119 |
| **Geral** | **565** | **111** | **676** |

---

## Pergunta à parte: a clonagem dos repositórios trouxe os testes humanos?

**Sim, trouxe — o `git clone` sempre traz o repositório inteiro no HEAD,
testes incluídos.** A decisão de "não olhar os testes" nunca foi sobre
impedir que eles existissem no disco, foi sobre eu não ler/copiar essas
pastas para o material usado na escrita dos testes. O que mudou de
repositório para repositório foi *onde* essas pastas vivem e se isso
tornou fácil ou difícil evitá-las:

- **Requests, Scrapy, Celery** — o repositório oficial guarda os testes
  numa pasta **separada, na raiz**, fora do pacote de produção
  (`tests/` no Requests e no Scrapy; `t/` no Celery). Como eu só copiei o
  pacote de produção (`src/requests`, `scrapy/scrapy`, `celery/celery`)
  para dentro do que hoje é `repositorios-originais/`, essas pastas nunca
  chegaram a ser copiadas para o material de escrita — mesmo estando
  presentes no clone bruto.
- **Conan** — a suíte real também fica numa pasta `test/` na raiz
  (`test/functional/`, `test/integration/`), separada do pacote `conan/`.
  Existe uma segunda pasta chamada `test/`, mas **dentro** do pacote
  (`conan/test/utils/tools.py`) — essa é uma ferramenta pública que o
  próprio Conan distribui para quem quiser testar receitas (o
  `TestClient` usado nesta suíte), não a suíte interna do projeto. As
  duas têm o mesmo nome de pasta por coincidência; só a de dentro do
  pacote foi copiada, de propósito.
- **Dask — o único caso onde isso deu errado por um instante.** O Dask
  organiza os testes humanos **dentro** do próprio pacote de produção
  (`dask/array/tests/`, `dask/dataframe/tests/`, `dask/bag/tests/` etc.),
  não numa pasta separada. Ao copiar o pacote `dask/dask/dask` inteiro
  para o que hoje é `repositorios-originais/dask/`, esses subdiretórios
  de teste vieram junto sem eu perceber de imediato. Um `pytest -q` sem argumento específico chegou a
  **coletar e rodar por alguns segundos** uma fatia real da suíte humana
  do Dask antes de eu notar (pelo volume de testes muito maior que o
  esperado) e interromper. Nenhum conteúdo desses testes foi lido — a
  saída visível era só símbolos de passou/pulou, sem nomes, sem código —
  mas foi um contato comportamental real, não só a presença do arquivo no
  disco. Os diretórios de teste foram apagados de `repo_src/` na hora, e
  os três arquivos da v1 escritos depois desse ponto
  (`test_funcional_delayed.py`, `test_integracao_scheduler.py`,
  `test_aceitacao_pipeline.py`) foram deletados e reescritos do zero
  posteriormente, sem reaproveitar nada da versão anterior, para eliminar
  qualquer resíduo possível.

**Nota (15/09/2026) — reorganização para o GitHub e extração permanente
dos testes humanos:** os clones originais citados acima (usados só para
localizar essas pastas, nunca para copiar conteúdo para a escrita dos
testes de IA) viviam numa pasta temporária de sessão e foram apagados
pela limpeza automática do Windows (mesmo incidente registrado por outra
sessão em `documentos/RELATORIO_COMPARACAO_TESTES_IA_HUMANOS.md`, seção
6, ao recriar o clone do Celery). Para dar uma estrutura permanente e
separada ao repositório [github.com/xMENEZES/projeto-aplicacao](https://github.com/xMENEZES/projeto-aplicacao)
— código-fonte original, testes humanos e testes de IA em pastas
distintas — os 5 repositórios foram re-clonados (Requests/Scrapy/Conan
via clone raso na tag/branch correspondente; Dask via clone completo e
`checkout` no commit exato `817e5ffc...`; Celery já tinha sido
recriado por outra sessão em `celery/human_original/`), e só a pasta de
testes humanos de cada um foi copiada para
`testes-humanos/<repositório>/`, permanentemente. Os clones completos
(`<repositório>/human_original/`) foram mantidos fora da estrutura
final (fora de `repositorios-originais/`, `testes-humanos/`,
`testes-ia/` e `documentos/`) porque outra sessão os usa ativamente
para a comparação de cobertura/mutação em andamento — ver
`documentos/RELATORIO_COMPARACAO_TESTES_IA_HUMANOS.md`.
