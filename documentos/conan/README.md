# Suíte de testes — Conan (4º repositório)

Suíte escrita **sem consultar a pasta `test/` na raiz do repositório
oficial** (onde vive a suíte interna, dividida em `functional/` e
`integration/`) — só o código de produção foi lido, incluindo o utilitário
`conan.test.utils.tools.TestClient`, que o próprio Conan distribui **dentro
do pacote** (`conan/test/utils/`, não `test/` na raiz) exatamente para que
qualquer pessoa escrevendo receitas Conan possa testá-las — documentado
como API pública, no mesmo espírito de `scrapy.utils.test` e
`celery.contrib.testing` usados nos dois repositórios anteriores.

## Escopo — o que cada módulo-alvo faz

- **`internal/model/version.py`** — `Version`: compara versões "à la
  Conan" (não é semver — aceita qualquer padrão com pontos/hífens),
  incluindo pré-release e build metadata.
- **`internal/model/version_range.py`** — `VersionRange`: resolve
  expressões como `>=1.0 <2.0`, `~1.2.3`, `1.2.*` ou `1.0 || 2.0` contra
  uma `Version`, decidindo quais versões publicadas satisfazem um
  `requires` declarado de forma flexível.
- **`internal/model/options.py`** — `Options`: o modelo de opções de um
  pacote (`shared`, `fPIC`, ou qualquer opção customizada da receita),
  com valores restritos (`possible_values`), congelamento (`freeze`) e
  marcação de "importante" (`!`) que impede sobrescrita acidental.
- **`internal/model/requires.py`** — `Requirement`/`Requirements`: como uma
  receita declara de que depende — `requires()` (biblioteca normal),
  `tool_requires()`/`build_requires()` (ferramenta que roda no build),
  `test_requires()` (framework de teste) — cada um com um conjunto
  diferente de defaults (propaga headers? propaga libs? é visível para
  quem depende de quem depende dele?).
- **`internal/graph/*`** (`graph.py`, `graph_builder.py`, `installer.py`) —
  o resolvedor de dependências propriamente dito: monta o grafo a partir
  dos `requires` declarados, resolve version ranges, decide contexto
  build/host, e instala os binários. Não testado por chamada isolada de
  método (é fortemente acoplado ao cache e ao restante da API) — validado
  de ponta a ponta pelas camadas de integração e aceitação.
- **`cli/commands/*` e `api/subapi/*`** — a camada de comando (`conan
  create`, `conan graph info`, `conan lock create`...) e a API pública que
  ela chama por baixo. Também validados só de ponta a ponta, via
  `TestClient`, não por teste unitário de cada comando.

`tools/*` (integrações com CMake, Meson, MSBuild etc.), `internal/cache/db`
e a parte de comunicação com servidores remotos (`internal/rest/`) não
foram alvo direto.

## Código sob teste

`repositorios-originais/conan/conan/` é uma cópia exata do checkout clonado (versão
`2.32.0-dev`), acompanhada de `repositorios-originais/conan/conans/` — um pacote legado
separado (servidor Conan antigo) do qual `conan.test.utils.tools`
depende para simular um remoto Artifactory em memória. `conftest.py`
insere `repositorios-originais/conan/` no `sys.path` e confere a versão com um `assert`.

## Como rodar

```bash
py -m pip install -r requirements-testes.txt
py -m pytest -q
py -m pytest -q --cov=conan --cov-report=term-missing
```

**Nenhum teste depende de um compilador C/C++ real, nem de um servidor
Artifactory de verdade.** Todas as receitas de teste são pacotes
"header-only" fictícios com `build()`/`package()` vazios — o suficiente
para exercitar o resolvedor de grafo, o cache local e a CLI de ponta a
ponta, sem nunca chamar um compilador. Cada teste recebe, via a fixture
`client`, um `TestClient` com cache (`.conan2`) e pasta de trabalho
próprios, num diretório temporário — zero compartilhamento de estado
entre testes.

## Organização por tipo de teste

| Arquivo | Tipo | O que valida |
|---|---|---|
| `test_estrutural_version.py` | Estrutural | `Version` (parsing, igualdade, ordenação, `bump`, por instanciação) e `VersionRange` (via `requires="pkg/[faixa]"` real, resolvido por `graph info`) |
| `test_estrutural_options.py` | Estrutural | `_PackageOption`/`_PackageOptions`: bool, validação, freeze, `!` -- via `TestClient`/receitas reais, nunca instanciando o modelo interno direto |
| `test_estrutural_requires.py` | Estrutural | `Requirement`/`Requirements`: deduplicação, contexto build/host -- via `TestClient`/grafo real |
| `test_funcional_cli.py` | Funcional | Comandos isolados da CLI (`new`, `create`, `list`, `remove`, `profile`, `config`, `graph info`) |
| `test_integracao_graph.py` | Integração | Grafo real de 2-3 pacotes: transitividade, version ranges, opções, contexto build/host, lockfile |
| `test_aceitacao_workflow.py` | Aceitação | Histórias de usuário, com o mesmo grafo real |

**70 testes, todos passando** (revisão de 2026-09-14 -- ver "Ajustes
consolidados" abaixo; eram 89 antes dela; rodados juntos, ~15s). As
percentuais de cobertura de linha abaixo foram medidas ANTES dessa
revisão e não foram re-medidas depois -- ficaram só como referência
histórica: `version.py` 88%, `options.py` 86%, `requires.py` 68%,
`internal/graph/graph.py` 80%, `installer.py` 68%, `version_range.py`
53%, `graph_builder.py` 49%.

## Ajustes consolidados (2026-09-14) — correspondência com testes humanos

Revisão feita sob o critério "um teste da IA só sobrevive se existir, ou
puder existir reescrito no mesmo nível de abstração, um teste humano
equivalente" -- sem nenhum contato com a suíte humana real. Diferente do
Requests, nenhum dos 3 alvos revistos (`_PackageOption`/`_PackageOptions`,
`Requirement`/`Requirements`, `VersionRange`) foi removido -- os três
tinham correspondente humano possível, só precisavam ser exercitados num
nível mais alto: via `conan.test.utils.tools.TestClient` com receitas
reais (`options=`/`default_options=`/`requires=`) e o grafo resolvido por
`conan create`/`graph info`, nunca instanciando `_PackageOptions`,
`Requirements` ou `VersionRange` isoladamente.

Alguns sub-casos bem finos da v1 anterior (ex.: os defaults exatos de
`headers`/`libs`/`visible`/`run` por tipo de `requires`, ou o
comportamento de opções "não-constrained" vindas de perfil) foram
consolidados em cenários mais robustos em vez de portados 1:1 -- não há
garantia de que esses detalhes fiquem expostos de forma estável no
`graph info --format=json`, e testá-los do mesmo jeito arriscaria um
teste frágil por um motivo que não tem a ver com o comportamento real.
Cada arquivo rewrite documenta, no próprio docstring, o que ficou de
fora e por quê. Todos os cenários mantidos foram confirmados por
execução direta contra o `conan` clonado antes de fechar a suíte --
inclusive uma correção de rota (o gatilho real do "congelamento" de
opções é o `configure()` da PRÓPRIA receita, não de um consumidor
downstream, e só depois do valor já ter sido resolvido por
`default_options`/`-o`/perfil; `config_options()` roda antes desse
congelamento).

## Sobre os testes de mutação

Mesma decisão das suítes anteriores: nenhuma ferramenta de mutação foi
executada — os casos foram desenhados para matar mutações específicas,
documentadas no teste onde o alvo não é evidente. Padrões mais comuns
aqui:

- **Comparação numérica vs. lexicográfica** (`Version`: "1.9" < "1.10")
- **Remoção de zeros à direita antes de comparar** (`Version.__eq__`)
- **Hash/igualdade composta** (`Requirement`: `(nome, build)`, não só o nome)
- **Guardas de validação cruzada** (`Requirement.__init__`: visible+consistent)
- **Escolha da versão máxima vs. mínima numa faixa** (`VersionRange` + resolução real do grafo)

## Achados durante a escrita (relevantes para a comparação com testes humanos)

Dois comportamentos que só ficaram claros rodando o código, não lendo a
assinatura ou o docstring dos métodos — e um deles contradiz o próprio
docstring:

1. **`Version.bump()` não faz o que o próprio docstring promete.** O
   docstring dá o exemplo `1.5.7 => bump(0) => 2.0.0` (incrementa o campo
   escolhido e ZERA os campos à direita). O código, porém, calcula quantos
   zeros acrescentar como `len(items) - index - 1` — e nesse ponto da
   função, `items` já é a lista truncada em `:index` com o valor
   incrementado recém-anexado, então esse cálculo é **sempre zero**,
   independente do índice. Na prática, `bump()` **trunca** em vez de
   zerar: `Version("1.5.7").bump(0)` devolve `"2"`, não `"2.0.0"`. O
   próprio exemplo mais simples do docstring (`2.5 => bump(1) => 2.6`) não
   revela o problema porque, com um único campo à direita, truncar e
   zerar dão o mesmo resultado. Ver
   `test_bump_na_pratica_trunca_em_vez_de_zerar_a_direita`.
2. **Comparar uma opção contra um valor fora da lista de valores possíveis
   levanta excepção, não devolve `False`.** `_PackageOption.__eq__`
   valida o valor comparado através de `_check_valid_value` antes de
   comparar — então `self.options.build_type == "não-existe"` quebra o
   programa com `ConanException` em vez de simplesmente avaliar como
   falso, sempre que a opção tiver `possible_values` restritos (o caso
   comum para opções declaradas em receita). Ver
   `test_package_option_comparar_com_valor_invalido_levanta_exception`.
3. **Duas versões diferentes do mesmo pacote, ambas como `requires()`
   normal no mesmo conanfile, conflitam entre si.** `Requirement.__hash__`
   é `(ref.name, build)` — não inclui a versão — e `__eq__` já retorna
   `True` quando ambos os requirements propagam headers ou libs (o
   default). Isso significa que `self.requires("zlib/1.2.11")` seguido de
   `self.requires("zlib/1.3.1")` no mesmo conanfile levanta
   `ConanException("Duplicated requirement")`, não porque a versão
   conflita, mas porque o nome (mais headers/libs) já é considerado o
   mesmo requirement. Ver
   `test_requires_duplicado_pelo_mesmo_nome_levanta_mesmo_com_versoes_diferentes`.
