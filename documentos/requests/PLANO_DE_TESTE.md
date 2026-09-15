# Plano de Teste — Requests (v2, metodologia formal)

Segunda versão da suíte do Requests, desta vez seguindo o processo da
skill *gerador-de-testes*: primeiro o raciocínio formal (classes de
equivalência, valor limite, tabelas de decisão), depois o código. A v1
(pasta-mãe) já cobria os mesmos módulos com boa cobertura, mas os casos
foram derivados de forma mais ad-hoc; aqui cada caso é rastreável a uma
classe, um limite ou uma linha de uma tabela de decisão específica.

Alvo: os mesmos módulos-alvo do `README.md` da v1 — `models.py`,
`sessions.py`, `auth.py` — mas com foco nas quatro funções com mais lógica
de decisão combinada, que são exatamente onde particionamento simples de
classes não basta e uma tabela de decisão revela combinações que
passariam despercebidas.

---

## 1. `PreparedRequest.prepare_url` — técnica funcional (classes de equivalência + valor limite)

| Condição | Classe(s) Válida(s) | Classe(s) Inválida(s) |
|---|---|---|
| Esquema da URL | `http`, `https` (qualquer esquema reconhecido por `parse_url`) | Ausente (`example.com/x`) → `MissingSchema` |
| Host | Presente, ASCII, sem `*`/`.` inicial | Ausente (`http://`) → `InvalidURL`; começa com `*` ou `.` → `InvalidURL` |
| Host com caracteres não-ASCII | Codificável via IDNA (`café.com`) | Não codificável via IDNA → `InvalidURL` |
| Esquema não-HTTP | `mailto:`, `data:` (passam direto, sem parsing) | — (não há inválida; é passthrough por definição) |
| Espaços à esquerda na string da URL | Removidos antes do parsing | — |
| Tipo do parâmetro `url` | `str`, `bytes` (decodificado como UTF-8) | — |
| Query params (`params`) | dict, string, `None` | — |

**Valor limite:** não há um limite numérico aqui (é uma condição estrutural, não uma faixa), mas o equivalente é a **fronteira entre ter e não ter** cada elemento obrigatório (esquema, host) — testado como par presente/ausente.

---

## 2. `PreparedRequest.prepare_content_length` — REMOVIDA

Esta seção (e os casos CT08–CT12 que dela derivavam) foi removida na
revisão de ajustes consolidados: não há nenhuma evidência humana, direta
ou indireta, de teste sobre este método, e não existe via pública para
observar o `Content-Length` calculado a não ser inspecionando esse
header interno diretamente — sem isso, não há nível de abstração em que
um teste equivalente possa existir. Mantê-la só poluiria a comparação
com um ponto que nunca vai ter par na suíte humana.

---

## 3. `Response.raise_for_status` — valor limite (fronteiras 400 e 500)

| Classe | Faixa | Resultado esperado |
|---|---|---|
| Sucesso/redirecionamento | status < 400 | Não levanta |
| Erro de cliente | 400 ≤ status < 500 | `HTTPError` com "Client Error" |
| Erro de servidor | 500 ≤ status < 600 | `HTTPError` com "Server Error" |
| Fora de faixa (acima) | status ≥ 600 | Não levanta |

**Valores limite obrigatórios:** 399, 400 (fronteira inferior de cliente), 499, 500 (fronteira cliente→servidor), 599, 600 (fronteira superior de servidor). São 6 valores — o próprio catálogo de valor-limite de uma faixa dupla fechada-aberta encostada na outra.

---

## 4. `Session.rebuild_method` — tabela de decisão (status de redirect × método original)

| Regra | Status | Método original | Novo método |
|---|---|---|---|
| R1 | 303 (See Other) | `HEAD` | `HEAD` (preservado) |
| R2 | 303 | Qualquer outro (`GET`, `POST`, `PUT`...) | `GET` |
| R3 | 302 (Found) | `POST` | `GET` |
| R4 | 302 | Outro que não `POST` | Preservado |
| R5 | 301 (Moved) | `POST` | `GET` |
| R6 | 301 | Outro que não `POST` | Preservado |
| R7 | 307/308 | Qualquer | Preservado (nunca muda) |

7 regras cobrindo as combinações que realmente importam — não é o produto cartesiano completo (status × método), porque a maioria dos métodos fora de `{GET, HEAD, POST}` se comporta como "outro" e uma única regra representativa basta (classes de equivalência dentro da própria tabela).

---

## 5. `Session.should_strip_auth` — tabela de decisão (esquema × host × porta)

| Regra | Host igual? | Esquema | Porta | Remove credenciais? |
|---|---|---|---|---|
| R1 | Sim | Igual | Igual | Não |
| R2 | Não | — | — | **Sim** |
| R3 | Sim | `http` → `https` | Portas padrão (80→443 implícitas) | Não (caso especial de upgrade seguro) |
| R4 | Sim | Igual | Diferente | **Sim** |

---

## 6. `HTTPBasicAuth`/`HTTPDigestAuth` — classes de equivalência (credenciais)

| Campo | Classe válida | Classe inválida/limítrofe |
|---|---|---|
| `username`/`password` | `str` ou `bytes` | Não-string (ex.: `int`) → aceito, mas emite `DeprecationWarning` |
| Desafio Digest (`qop`) | `"auth"`, ausente (`None`) | `"auth-int"` → não suportado, `build_digest_header` devolve `None` |
| Algoritmo Digest | `MD5`, `SHA`, `SHA-256`, `SHA-512` (case-insensitive) | Algoritmo desconhecido → devolve `None` |

---

## Casos de teste derivados

| ID | Alvo | Entrada | Resultado Esperado | Técnica/Critério | Arquivo |
|---|---|---|---|---|---|
| CT01 | prepare_url | `"example.com/x"` (sem esquema) | `MissingSchema` | Classe inválida — esquema ausente | test_funcional_classes_valor_limite.py |
| CT02 | prepare_url | `"http://"` (sem host) | `InvalidURL` | Classe inválida — host ausente | idem |
| CT03 | prepare_url | `"http://*.x.com/"` | `InvalidURL` | Classe inválida — host com wildcard | idem |
| CT04 | prepare_url | `"http://café.com/"` | Host IDNA-encoded, não levanta | Classe válida — host não-ASCII codificável | idem |
| CT05 | prepare_url | `"mailto:a@b.com"` | URL preservada como está | Classe válida — esquema não-HTTP (passthrough) | idem |
| CT06 | prepare_url | `"   http://x.com/"` (espaços) | `"http://x.com/"` | Classe válida — espaços à esquerda removidos | idem |
| CT07 | prepare_url | `b"http://x.com/"` (bytes) | Decodificado e processado normalmente | Classe válida — tipo bytes | idem |
| CT13 | raise_for_status | 399 | Não levanta | Valor limite — abaixo da fronteira cliente | idem |
| CT14 | raise_for_status | 400 | `HTTPError` Client Error | Valor limite — fronteira cliente inferior | idem |
| CT15 | raise_for_status | 499 | `HTTPError` Client Error | Valor limite — fronteira cliente superior | idem |
| CT16 | raise_for_status | 500 | `HTTPError` Server Error | Valor limite — fronteira servidor inferior | idem |
| CT17 | raise_for_status | 599 | `HTTPError` Server Error | Valor limite — fronteira servidor superior | idem |
| CT18 | raise_for_status | 600 | Não levanta | Valor limite — acima da fronteira servidor | idem |
| CT19 | rebuild_method | 303 + `HEAD` | `HEAD` | Decisão — R1 | test_estrutural_decisao.py |
| CT20 | rebuild_method | 303 + `PUT` | `GET` | Decisão — R2 | idem |
| CT21 | rebuild_method | 302 + `POST` | `GET` | Decisão — R3 | idem |
| CT22 | rebuild_method | 302 + `GET` | `GET` (preservado) | Decisão — R4 | idem |
| CT23 | rebuild_method | 301 + `POST` | `GET` | Decisão — R5 | idem |
| CT24 | rebuild_method | 301 + `PATCH` | `PATCH` (preservado) | Decisão — R6 | idem |
| CT25 | rebuild_method | 307 + `POST` | `POST` (preservado) | Decisão — R7 | idem |
| CT26 | rebuild_method | 308 + `POST` | `POST` (preservado) | Decisão — R7 (mesma regra, status diferente) | idem |
| CT27 | should_strip_auth | mesmo host, mesmo esquema, mesma porta | Não remove | Decisão — R1 | idem |
| CT28 | should_strip_auth | host diferente | Remove | Decisão — R2 | idem |
| CT29 | should_strip_auth | http→https, portas padrão | Não remove | Decisão — R3 | idem |
| CT30 | should_strip_auth | mesmo host/esquema, porta diferente | Remove | Decisão — R4 | idem |
| CT31 | HTTPBasicAuth | username=`123` (int) | `DeprecationWarning`, funciona mesmo assim | Classe limítrofe — tipo não-string | test_funcional_classes_valor_limite.py |
| CT32 | HTTPDigestAuth | `qop="auth-int"` | `build_digest_header` devolve `None` | Classe inválida — qop não suportado | idem |
| CT33 | HTTPDigestAuth | `algorithm="INEXISTENTE"` | `build_digest_header` devolve `None` | Classe inválida — algoritmo desconhecido | idem |

28 casos (33 originais menos CT08–CT12, removidos por não terem
correspondente humano possível), cobrindo 5 tabelas/particionamentos
formais. CT19–CT26 são o exemplo que resta de por que tabela de decisão
supera classe de equivalência isolada nesta suíte.
