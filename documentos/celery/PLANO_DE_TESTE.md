# Plano de Teste — Celery (v2, metodologia formal)

Mesmo processo das duas versões anteriores: plano formal primeiro,
código depois. Alvo: as áreas de `app/task.py`, `canvas.py`,
`app/settings` (via `BaseSettings`), `utils/dispatch/signal.py` e
`backends/base.py` com mais condições combinadas — exatamente as que já
geraram os achados documentados na v1, agora formalizadas como tabela de
decisão em vez de descobertas ad-hoc.

---

## 1. `Task.retry()` em modo eager — tabela de decisão

Quatro condições combinadas decidem o que `self.retry()` realmente faz
quando a tarefa roda via `.apply()`/`task_always_eager`:

| Regra | `task_eager_propagates` | Tentativas ≤ `max_retries`? | `exc=` fornecido? | Resultado |
|---|---|---|---|---|
| E1 | `True` | — (irrelevante) | — | `Retry` escapa direto de `.apply()`; tarefa roda 1 vez |
| E2 | `False` | Sim | — | Tarefa reexecuta recursivamente via `sig.apply()`; roda de novo |
| E3 | `False` | Não (esgotado) | Sim | `.apply()` devolve `EagerResult` com a exceção original (`exc`) |
| E4 | `False` | Não (esgotado) | Não | `.apply()` devolve `EagerResult` com `MaxRetriesExceededError` |

A regra E1 é a mais contraintuitiva: **a configuração que parece só
afetar "se erro propaga ou não" na verdade decide se `retry()` retenta de
verdade ou não**, porque `task_eager_propagates=True` faz o tracer deixar
o `Retry` escapar como exceção, sem nunca chegar à lógica de reexecução
que vive depois da chamada ao tracer dentro de `.apply()`.

---

## 2. `Signature._merge()` — tabela de decisão (immutable × force × args extras)

| Regra | `immutable` | `force` (passado diretamente a `_merge`) | Args extras fornecidos | Args finais |
|---|---|---|---|---|
| M1 | `False` | — | Sim | Extras prepostos aos args originais |
| M2 | `False` | — | Não | Args originais, sem alteração |
| M3 | `True` | `False` (default) | Sim | Args originais (extras **ignorados**) |
| M4 | `True` | `True` | Sim | Extras prepostos (immutabilidade contornada) |

**Achado a confirmar no código:** `force` só tem efeito quando passado
**diretamente** para `Signature._merge(force=True)`. A API pública
`Signature.clone(args=.., force=True)` NÃO produz o mesmo efeito — `clone`
repassa todo `**opts` (incluindo `force`) como o dicionário de *options*
posicional de `_merge`, não como o parâmetro nomeado `force` — então
`clone(force=True)` deixa `force` com o valor padrão (`False`) dentro de
`_merge`, e o que era pra ser um "force" vira, sem aviso, uma entrada
qualquer dentro de `.options`. Verificado por execução direta antes de
escrever o teste (ver seção de casos, CT10 e CT11).

---

## 3. `SettingsAttribute.set()` (Scrapy `BaseSettings`, reaproveitado aqui como padrão análogo em `Blueprint`/config do Celery) — valor limite de prioridade

Nesta suíte usamos o equivalente direto do Celery: a checagem de
prioridade em `BaseSettings`-like não existe no Celery da mesma forma que
no Scrapy, então o valor-limite formal aqui é aplicado a
`HTTPAuthMiddleware`-like: a validação de prioridade em
`Blueprint._finalize_steps`/`claim_steps` não é numérica. Trocamos por um
alvo real do Celery com fronteira numérica clara:
**`RetryMiddleware`-equivalente do Celery é `retry()` com
`max_retries`** — já coberto na seção 1 (E2/E3 são exatamente o valor
limite "tentativas ≤ max" vs "tentativas > max").

Em vez de duplicar, esta seção testa o valor-limite **diretamente em
`max_retries`**: com `max_retries=2`, a 2ª tentativa (retries=2, ainda
`≤` o limite) deve reexecutar; a 3ª (retries=3, `>` o limite) deve
desistir. Ver CT05/CT06.

---

## 4. `celery.utils.dispatch.Signal.send()` — tabela de decisão (sender do receptor × sender do envio)

| Regra | Sender do receptor (`connect(sender=...)`) | Sender do `send()` | Receptor é chamado? |
|---|---|---|---|
| S1 | `None` (qualquer remetente) | Qualquer valor | Sim |
| S2 | Valor específico `X` | `X` (igual) | Sim |
| S3 | Valor específico `X` | `Y` (diferente) | Não |

---

## 5. `Backend.mark_as_done` / `mark_as_failure` — decisão sobre `store_result`

| Regra | Método | `store_result=` | `backend.store_result()` é chamado? |
|---|---|---|---|
| B1 | `mark_as_done` | `True` (default) | Sim, com `state=SUCCESS` |
| B2 | `mark_as_done` | `False` | Não |
| B3 | `mark_as_failure` | `True` (default) | Sim, com `state=FAILURE` |
| B4 | `mark_as_failure` | `False` | Não |

---

## Casos de teste derivados

| ID | Alvo | Entrada | Resultado Esperado | Técnica/Critério |
|---|---|---|---|---|
| CT01 | retry() | eager, `propagates=True`, `max_retries=5` | `Retry` escapa, 1 execução | Decisão — E1 |
| CT02 | retry() | eager, `propagates=False`, `max_retries=3`, dentro do limite | Reexecuta 4x (1+3), `EagerResult` FAILURE | Decisão — E2 |
| CT03 | retry() | eager, `propagates=False`, `max_retries=2`, esgotado, `exc=ValueError` | `EagerResult.result` é o `ValueError` original | Decisão — E3 |
| CT04 | retry() | eager, `propagates=False`, `max_retries=2`, esgotado, sem `exc` | `EagerResult.result` é `MaxRetriesExceededError` | Decisão — E4 |
| CT05 | retry() (valor limite) | `max_retries=2`, tentativa nº 2 (`retries=2`) | Ainda reexecuta (2 ≤ 2) | Valor limite — na fronteira |
| CT06 | retry() (valor limite) | `max_retries=2`, tentativa nº 3 (`retries=3`) | Desiste (3 > 2) | Valor limite — 1 acima |
| CT07 | Signature._merge | `immutable=False`, args extras `(1,)` | Args = extras + originais | Decisão — M1 |
| CT08 | Signature._merge | `immutable=False`, sem args extras | Args = originais | Decisão — M2 |
| CT09 | Signature._merge | `immutable=True`, `force=False`, args extras | Args = originais (ignora extras) | Decisão — M3 |
| CT10 | Signature._merge | `immutable=True`, `force=True` (direto) | Args = extras + originais | Decisão — M4 |
| CT11 | Signature.clone | `immutable=True`, `clone(args=.., force=True)` | Args = originais (force NÃO chega ao `_merge`) | Decisão — M3 (achado: `clone(force=True)` não é M4) |
| CT12 | Signal.send | receptor com `sender=None` | Chamado para qualquer sender | Decisão — S1 |
| CT13 | Signal.send | receptor com `sender="A"`, envio com `sender="A"` | Chamado | Decisão — S2 |
| CT14 | Signal.send | receptor com `sender="A"`, envio com `sender="B"` | Não chamado | Decisão — S3 |
| CT15 | Backend.mark_as_done | `store_result=True` | `store_result()` chamado com SUCCESS | Decisão — B1 |
| CT16 | Backend.mark_as_done | `store_result=False` | `store_result()` não chamado | Decisão — B2 |
| CT17 | Backend.mark_as_failure | `store_result=True` | `store_result()` chamado com FAILURE | Decisão — B3 |
| CT18 | Backend.mark_as_failure | `store_result=False` | `store_result()` não chamado | Decisão — B4 |

18 casos cobrindo 5 tabelas de decisão. CT10/CT11 são o par que expõe o
achado da seção 2 — sem os dois lado a lado, a diferença entre "force
funciona" e "force não funciona pela API pública" passaria despercebida.
