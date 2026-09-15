# Plano de Teste — Conan (v2, metodologia formal)

Mesmo processo das versões anteriores. Alvo: `Version.__lt__` (a lógica
de ordenação com pré-release, que tem 6 ramos combinados — o candidato
mais rico a tabela de decisão de todo o Conan), a deduplicação de
`Requirement` (`__eq__`/`__hash__`, já rendeu achado na v1, agora
formalizada) e `_PackageOption._set` (duas tabelas: congelamento e
marcação "importante").

Todas as linhas das tabelas abaixo foram **confirmadas por execução direta**
antes de virarem caso de teste — inclusive uma que corrigiu uma suposição
inicial errada (ver nota na seção 2).

**Atualização (2026-09-14):** na revisão de correspondência com testes
humanos, as seções 2 e 3 passaram a ser exercitadas via `TestClient` com
receitas reais (`self.requires()`/`self.build_requires()`/
`self.tool_requires()`, `options=`/`default_options=`, `-o` da CLI,
perfis), nunca instanciando `Requirements`/`_PackageOptions` direto — as
regras das tabelas abaixo não mudaram, só a forma de observá-las de
fora. Essa mudança também corrigiu uma suposição: o gatilho real do
congelamento de `_PackageOption` é o `configure()` da PRÓPRIA receita
tentando mudar um valor já resolvido (por `default_options`, `-o` ou
perfil) — não o `configure()` de um consumidor tentando mudar a opção
de uma dependência, que é simplesmente ignorado.

---

## 1. `Version.__lt__` — tabela de decisão (pré-release × pré-release × igualdade)

| Regra | `self` é pré-release? | `other` é pré-release? | `nonzero_items` iguais? | Resultado |
|---|---|---|---|---|
| V1 | Sim | Sim | — | Compara `(nonzero_items, pre, build)` completos |
| V2 | Sim | Não | Sim | `True` (pré-release < release da mesma versão) |
| V3 | Sim | Não | Não | Compara só `nonzero_items` |
| V4 | Não | Sim | Sim | `False` (release > sua própria pré-release) |
| V5 | Não | Sim | Não | Compara só `nonzero_items` |
| V6 | Não | Não | — | Compara `(nonzero_items, build)` |

V2/V4 são o par que garante a regra semver "1.0.0-alpha < 1.0.0" **só**
quando as duas versões são a mesma release por baixo — sem a checagem de
igualdade de `nonzero_items`, "2.0-alpha" poderia acabar comparado como
menor que "1.0" só por ser pré-release, o que seria errado (2.0 é maior
que 1.0 independente de prerelease).

---

## 2. `Requirement.__eq__`/`__hash__` — deduplicação de `requires()` (confirmada por execução)

`__hash__` é `(nome, build)`; `__eq__` verifica sobreposição de
`headers`/`libs`/`run` (entre outras). A suposição inicial era "dois
`build_require()` do mesmo nome sempre colidem, como dois `requires()`
normais" — **errada**: `build_require()` usa `run=False` por padrão, então
não colide a não ser que o `run` seja explicitado como `True` (que é
exatamente o default de `tool_require()`). Corrigido depois de rodar os
três cenários lado a lado antes de escrever o teste.

| Regra | Mesmo nome? | Mesmo `build`? | `headers` ambos `True`? | `libs` ambos `True`? | `run` ambos `True`? | Colide? |
|---|---|---|---|---|---|---|
| R1 | Sim | Sim | Sim | — | — | **Sim** — dois `requires()` normais (headers=True default) |
| R2 | Sim | Sim | Não | Não | Sim | **Sim** — dois `tool_require()` (run=True default) |
| R3 | Sim | Sim | Não | Não | Não | Não — dois `build_require()` puros (run=False default) |
| R4 | Sim | Não | — | — | — | Não — `requires()` e `build_require()` do mesmo nome (build difere) |
| R5 | Não | — | — | — | — | Não — nomes diferentes |

---

## 3. `_PackageOption._set` — duas tabelas de decisão independentes

**Congelamento (`conan_freeze()`):**

| Regra | `_freeze`? | Valor atual definido? | Novo valor difere do atual? | Ação |
|---|---|---|---|---|
| F1 | Não | — | — | Permite |
| F2 | Sim | Não (`None`) | — | Permite |
| F3 | Sim | Sim | Não (mesmo valor) | Permite |
| F4 | Sim | Sim | Sim | Levanta `ConanException` |

**Marcação "importante" (sufixo `!`):**

| Regra | Novo valor é "importante"? | Valor atual já era "importante"? | Aplica o novo valor? |
|---|---|---|---|
| I1 | Sim | Sim | Sim (importante sobrescreve importante) |
| I2 | Sim | Não | Sim |
| I3 | Não | Sim | **Não** (normal não sobrescreve importante) |
| I4 | Não | Não | Sim |

---

## Casos de teste derivados

| ID | Alvo | Entrada | Resultado Esperado | Técnica/Critério |
|---|---|---|---|---|
| CT01 | Version.__lt__ | `"1.0-alpha" < "1.0-beta"` | `True` | Decisão — V1 |
| CT02 | Version.__lt__ | `"1.0-alpha" < "1.0"` | `True` | Decisão — V2 |
| CT03 | Version.__lt__ | `"2.0-alpha" < "1.0"` | `False` | Decisão — V3 |
| CT04 | Version.__lt__ | `"1.0" < "1.0-alpha"` | `False` | Decisão — V4 |
| CT05 | Version.__lt__ | `"1.0" < "2.0-alpha"` | `True` | Decisão — V5 |
| CT06 | Version.__lt__ | `"1.0" < "2.0"` | `True` | Decisão — V6 |
| CT07 | Requirement dedup | dois `requires()`, nomes iguais, versões diferentes | `ConanException` | Decisão — R1 |
| CT08 | Requirement dedup | dois `tool_require()`, nomes iguais, versões diferentes | `ConanException` | Decisão — R2 |
| CT09 | Requirement dedup | dois `build_require()` puros, nomes iguais, versões diferentes | Não colide | Decisão — R3 |
| CT10 | Requirement dedup | `requires()` + `build_require()`, mesmo nome | Não colide | Decisão — R4 |
| CT11 | Requirement dedup | `requires()` de nomes diferentes | Não colide | Decisão — R5 |
| CT12 | _PackageOption freeze | Sem freeze, muda o valor | Permite | Decisão — F1 |
| CT13 | _PackageOption freeze | Freeze, valor nunca definido, define agora | Permite | Decisão — F2 |
| CT14 | _PackageOption freeze | Freeze, redefine com o MESMO valor | Permite | Decisão — F3 |
| CT15 | _PackageOption freeze | Freeze, tenta mudar para valor DIFERENTE | `ConanException` | Decisão — F4 |
| CT16 | _PackageOption important | Novo `!`, atual já `!` | Sobrescreve | Decisão — I1 |
| CT17 | _PackageOption important | Novo `!`, atual normal | Sobrescreve | Decisão — I2 |
| CT18 | _PackageOption important | Novo normal, atual `!` | **Não** sobrescreve | Decisão — I3 |
| CT19 | _PackageOption important | Novo normal, atual normal | Sobrescreve | Decisão — I4 |

19 casos cobrindo 3 tabelas de decisão (uma delas com 2 sub-tabelas
independentes). CT07–CT11 são o grupo mais valioso: a suposição inicial
errada sobre `build_require()` só foi corrigida por ter testado as 3
variações lado a lado antes de escrever qualquer `assert`.
