# Plano de Teste — Dask (v2, metodologia formal)

Último dos cinco, mesmo processo. Alvo: `dask.config.update()` (a função
com mais condições combinadas de todo o núcleo do Dask — 3 modos de
prioridade × chave presente/ausente × comparação com defaults),
`tokenize._maybe_raise_nondeterministic` (decisão condicionada por
configuração global) e `dask.config.get` (guarda de `override_with` +
presença/ausência de default). Todas as linhas foram confirmadas por
execução direta antes de virarem caso de teste.

---

## 1. `dask.config.update(old, new, priority, defaults)` — tabela de decisão (6 regras)

| Regra | `priority` | Chave já existe em `old`? | (`new-defaults`) valor atual == default conhecido? | Sobrescreve? |
|---|---|---|---|---|
| U1 | `"new"` | — (irrelevante) | — | **Sim**, sempre |
| U2 | `"old"` | Não | — | **Sim** (chave nova, nada para preservar) |
| U3 | `"old"` | Sim | — | Não — preserva o valor de `old` |
| U4 | `"new-defaults"` | Sim | Sim (nunca customizado) | **Sim** |
| U5 | `"new-defaults"` | Sim | Não (usuário customizou) | Não — preserva a customização |
| U6 | `"new-defaults"` | Não | — | **Sim** (chave nova) |

U2 e U6 são a parte não óbvia: mesmo com `priority='old'` ou
`'new-defaults'` (que soam como "não sobrescrever"), uma chave que ainda
não existe em `old` é sempre adicionada — a prioridade só governa o que
fazer quando já existe um valor para preservar.

---

## 2. `tokenize._maybe_raise_nondeterministic` — decisão condicionada por config global

| Regra | `ensure_deterministic=` passado a `tokenize()` | `config.get("tokenize.ensure-deterministic")` | Levanta `TokenizationError`? |
|---|---|---|---|
| T1 | `True` | — (irrelevante) | **Sim** |
| T2 | `False` | — (irrelevante) | Não |
| T3 | Não passado (`None`) | `True` (via `dask.config.set`) | **Sim** |
| T4 | Não passado (`None`) | `False` (default de fábrica) | Não |

T3 é o caso menos óbvio: **sem passar nada explicitamente para
`tokenize()`**, é possível tornar toda tokenização não-determinística
"estrita" globalmente, só configurando `tokenize.ensure-deterministic`.

---

## 3. `dask.config.get(key, default, config, override_with)` — tabela de decisão

| Regra | `override_with` | Chave existe? | `default` fornecido? | Resultado |
|---|---|---|---|---|
| G1 | Não é `None` | — (irrelevante) | — (irrelevante) | Devolve `override_with` direto, sem tocar no config |
| G2 | `None` | Sim | — | Devolve o valor do config |
| G3 | `None` | Não | Sim | Devolve o `default` |
| G4 | `None` | Não | Não | Levanta `KeyError` |

---

## Casos de teste derivados

| ID | Alvo | Entrada | Resultado Esperado | Técnica/Critério |
|---|---|---|---|---|
| CT01 | config.update | `priority="new"`, chave já existe | Valor novo prevalece | Decisão — U1 |
| CT02 | config.update | `priority="old"`, chave ausente | Valor novo é setado | Decisão — U2 |
| CT03 | config.update | `priority="old"`, chave já existe | Valor antigo preservado | Decisão — U3 |
| CT04 | config.update | `priority="new-defaults"`, valor atual == default | Valor novo prevalece | Decisão — U4 |
| CT05 | config.update | `priority="new-defaults"`, valor atual customizado (≠ default) | Valor customizado preservado | Decisão — U5 |
| CT06 | config.update | `priority="new-defaults"`, chave ausente | Valor novo é setado | Decisão — U6 |
| CT07 | tokenize | `tokenize(object(), ensure_deterministic=True)` | `TokenizationError` | Decisão — T1 |
| CT08 | tokenize | `tokenize(object(), ensure_deterministic=False)` | Não levanta | Decisão — T2 |
| CT09 | tokenize | `tokenize(object())` dentro de `config.set({"tokenize.ensure-deterministic": True})` | `TokenizationError` | Decisão — T3 |
| CT10 | tokenize | `tokenize(object())` com config padrão (não setado) | Não levanta | Decisão — T4 |
| CT11 | config.get | `override_with="X"`, config vazio | `"X"` | Decisão — G1 |
| CT12 | config.get | chave presente, sem override | Valor do config | Decisão — G2 |
| CT13 | config.get | chave ausente, `default=123` | `123` | Decisão — G3 |
| CT14 | config.get | chave ausente, sem default | `KeyError` | Decisão — G4 |

14 casos cobrindo 3 tabelas de decisão. CT01–CT06 são o grupo mais denso:
`update()` tem 3 modos de prioridade que interagem com "a chave já existe
ou não" de um jeito que só fica claro testando as 6 combinações lado a
lado — testar só "priority=new" e só "priority=old" separadamente, sem
cruzar com presença/ausência da chave, deixaria as regras U2 e U6
inteiramente sem cobertura.
