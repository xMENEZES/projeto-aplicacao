# Plano de Teste — Scrapy (v2, metodologia formal)

Mesmo processo aplicado ao Requests: plano formal primeiro (classes de
equivalência, valor limite, tabelas de decisão), código depois, cada caso
rastreável a uma linha específica. Alvo: as funções com mais lógica de
decisão combinada dentro dos módulos-alvo já mapeados no `README.md` da
v1 — `downloadermiddlewares/{redirect,retry}.py` e
`spidermiddlewares/{depth,urllength}.py` e `downloadermiddlewares/offsite.py`.

---

## 1. `RedirectMiddleware.process_response` — tabela de decisão (guardas + troca de método)

Duas camadas de decisão: primeiro guardas que abortam o redirecionamento
por completo, depois a regra de troca de verbo HTTP.

**Guardas (equivalência: redireciona ou não):**

| Regra | `dont_redirect` no meta? | Header `Location` presente? | Status em {301,302,303,307,308}? | Redireciona? |
|---|---|---|---|---|
| G1 | Sim | — | — | Não |
| G2 | Não | Não | — | Não |
| G3 | Não | Sim | Não | Não |
| G4 | Não | Sim | Sim | Sim (segue para a tabela 2) |

**Troca de verbo (só quando G4 se aplica):**

| Regra | Status | Método original | Novo método |
|---|---|---|---|
| R1 | 301 ou 302 | `POST` | `GET` |
| R2 | 301 ou 302 | Outro que não `POST` | Preservado |
| R3 | 303 | Não é `GET`/`HEAD` | `GET` |
| R4 | 303 | `GET` ou `HEAD` | Preservado |
| R5 | 307 ou 308 | Qualquer | Preservado (nunca muda) |

---

## 2. `RedirectMiddleware._build_redirect_request` — remoção de `Cookie`/`Authorization` (duas tabelas de decisão independentes)

**Remoção de `Cookie`:**

| Regra | Esquema do redirect | Host igual? | Remove `Cookie`? |
|---|---|---|---|
| C1 | Igual ao original, ou upgrade para `https` | Sim | Não |
| C2 | Qualquer | Não | **Sim** |
| C3 | Diferente do original e não é `https` | Sim | **Sim** |

**Remoção de `Authorization`** (mais estrita — qualquer mudança remove):

| Regra | Esquema igual? | Host igual? | Porta igual? | Remove `Authorization`? |
|---|---|---|---|---|
| A1 | Sim | Sim | Sim | Não |
| A2 | Não | — | — | **Sim** |
| A3 | — | Não | — | **Sim** |
| A4 | — | — | Não | **Sim** |

---

## 3. `RetryMiddleware.process_response` — tabela de decisão

| Regra | `dont_retry` no meta? | Status em `RETRY_HTTP_CODES`? | Ação |
|---|---|---|---|
| R1 | Sim | — (irrelevante) | Devolve a resposta como está, nunca reenvia |
| R2 | Não | Não | Devolve a resposta como está |
| R3 | Não | Sim | Gera nova `Request` (retry), `dont_filter=True` |

Complementado por valor-limite em `max_retry_times` (contagem de
tentativas): na tentativa exatamente igual ao limite ainda tenta, na
seguinte desiste.

---

## 4. `DepthMiddleware.get_processed_request` — tabela de decisão + valor limite

| Regra | `depth_reset` no meta? | Nova profundidade vs. `DEPTH_LIMIT` | Ação |
|---|---|---|---|
| D1 | Sim | — (profundidade recalculada para 0) | Permite, profundidade = 0 |
| D2 | Não | Nova profundidade ≤ limite | Permite |
| D3 | Não | Nova profundidade > limite | Descarta (`None`) |
| D4 | Não | `DEPTH_LIMIT = 0` (sem limite) | Sempre permite, não importa a profundidade |

**Valor limite** (com `DEPTH_LIMIT = N`): profundidade `N` (fronteira,
ainda permite — regra D2) e `N + 1` (primeira acima, descarta — regra D3).

---

## 5. `UrlLengthMiddleware.get_processed_request` — valor limite puro

| Classe | `len(request.url)` vs. `URLLENGTH_LIMIT` | Ação |
|---|---|---|
| Válida | `≤` limite | Permite |
| Inválida | `>` limite | Descarta, incrementa estatística |

**Valores limite:** `limite - 1` (abaixo), `limite` (na fronteira, ainda
válido — o operador é `<=`, não `<`), `limite + 1` (acima, inválido).

---

## 6. `OffsiteMiddleware.process_request` — tabela de decisão

| Regra | `allowed_domains` vazio? | Domínio do request bate (ou é subdomínio)? | `dont_filter`? | `meta["allow_offsite"]`? | Bloqueia (`IgnoreRequest`)? |
|---|---|---|---|---|---|
| O1 | Sim | — | — | — | Não (sem restrição definida) |
| O2 | Não | Sim | — | — | Não |
| O3 | Não | Não | Não | Não | **Sim** |
| O4 | Não | Não | Sim | — | Não (bypass explícito por request) |
| O5 | Não | Não | — | Sim | Não (bypass explícito por meta) |

---

## Casos de teste derivados

| ID | Alvo | Entrada | Resultado Esperado | Técnica/Critério |
|---|---|---|---|---|
| CT01 | Redirect | `dont_redirect=True`, status 302 c/ Location | Resposta original, sem redirect | Decisão — G1 |
| CT02 | Redirect | status 302 sem header `Location` | Resposta original | Decisão — G2 |
| CT03 | Redirect | Location presente, status 200 | Resposta original | Decisão — G3 |
| CT04 | Redirect | status 301, método `POST` | Nova Request, método `GET` | Decisão — R1 |
| CT05 | Redirect | status 302, método `PUT` | Nova Request, método `PUT` (preservado) | Decisão — R2 |
| CT06 | Redirect | status 303, método `PUT` | Nova Request, método `GET` | Decisão — R3 |
| CT07 | Redirect | status 303, método `HEAD` | Nova Request, método `HEAD` (preservado) | Decisão — R4 |
| CT08 | Redirect | status 307, método `POST` | Nova Request, método `POST` (preservado) | Decisão — R5 |
| CT09 | Redirect | status 308, método `POST` | Nova Request, método `POST` (preservado) | Decisão — R5 (status diferente) |
| CT10 | Redirect (cookie) | Mesmo host, upgrade http→https | `Cookie` preservado | Decisão — C1 |
| CT11 | Redirect (cookie) | Host diferente | `Cookie` removido | Decisão — C2 |
| CT12 | Redirect (cookie) | Mesmo host, downgrade https→http | `Cookie` removido | Decisão — C3 |
| CT13 | Redirect (auth) | Esquema/host/porta idênticos | `Authorization` preservado | Decisão — A1 |
| CT14 | Redirect (auth) | Esquema diferente | `Authorization` removido | Decisão — A2 |
| CT15 | Redirect (auth) | Host diferente | `Authorization` removido | Decisão — A3 |
| CT16 | Redirect (auth) | Só a porta diferente | `Authorization` removido | Decisão — A4 |
| CT17 | Retry | `dont_retry=True`, status 503 | Resposta original | Decisão — R1 |
| CT18 | Retry | status 200 (fora da lista) | Resposta original | Decisão — R2 |
| CT19 | Retry | status 503 (na lista) | Nova Request, `dont_filter=True` | Decisão — R3 |
| CT20 | Depth | `depth_reset=True`, profundidade da origem = 10 | Nova profundidade = 0 | Decisão — D1 |
| CT21 | Depth | `DEPTH_LIMIT=3`, origem em profundidade 2 (nova = 3) | Permite | Decisão/limite — D2 (fronteira) |
| CT22 | Depth | `DEPTH_LIMIT=3`, origem em profundidade 3 (nova = 4) | Descarta | Decisão/limite — D3 (1 acima) |
| CT23 | Depth | `DEPTH_LIMIT=0`, profundidade alta | Sempre permite | Decisão — D4 |
| CT24 | UrlLength | `URLLENGTH_LIMIT=50`, url com 49 chars | Permite | Valor limite — abaixo |
| CT25 | UrlLength | `URLLENGTH_LIMIT=50`, url com exatos 50 chars | Permite | Valor limite — na fronteira |
| CT26 | UrlLength | `URLLENGTH_LIMIT=50`, url com 51 chars | Descarta | Valor limite — 1 acima |
| CT27 | Offsite | `allowed_domains` não definido | Nunca bloqueia | Decisão — O1 |
| CT28 | Offsite | domínio exato na lista | Permite | Decisão — O2 |
| CT29 | Offsite | subdomínio do domínio permitido | Permite | Decisão — O2 (variante) |
| CT30 | Offsite | domínio fora da lista | Bloqueia | Decisão — O3 |
| CT31 | Offsite | domínio fora da lista, `dont_filter=True` | Permite (bypass) | Decisão — O4 |
| CT32 | Offsite | domínio fora da lista, `meta["allow_offsite"]=True` | Permite (bypass) | Decisão — O5 |

32 casos cobrindo 6 tabelas de decisão + 1 valor-limite puro (UrlLength).
