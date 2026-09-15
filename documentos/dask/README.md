# Suíte de testes — Dask (5º e último repositório)

Suíte escrita **sem consultar nenhuma pasta `tests/` do repositório
oficial** (elas existem espalhadas por `array/tests/`, `dataframe/tests/`,
`bag/tests/` etc., e foram removidas da cópia local antes de qualquer
teste ser escrito) — só o código de produção foi lido. Diferente dos
quatro repositórios anteriores, o Dask não tem um utilitário de teste
"oficial" equivalente a `TestClient`/`start_worker` — o núcleo (grafos,
scheduler local, `delayed`, config) é simples e leve o suficiente para
testar diretamente, sem infraestrutura nenhuma.

## Escopo — o que cada módulo-alvo faz

- **`core.py`** — as primitivas mais básicas de todas: o que é uma
  "tarefa" (`istask`), o que é uma "chave" válida (`iskey`), como executar
  um grafo direto sem scheduler (`get`), como achar dependências
  (`get_dependencies`), como detectar ciclos (`getcycle`/`isdag`) e
  como substituir valores dentro de uma tarefa (`subs`). É o alfabeto que
  todo o resto do Dask usa.
- **`tokenize.py`** — o hashing determinístico (`tokenize`) que decide se
  duas chamadas são "a mesma computação" para fins de cache/dedup — a
  base de por que `dask.compute()` não recalcula a mesma subtarefa duas
  vezes quando ela é pedida por dois caminhos diferentes.
- **`config.py`** — a configuração em camadas (default embutido em YAML <
  variável de ambiente `DASK_*` < contexto em runtime via `with
  dask.config.set(...)`), usada para controlar de scheduler padrão a
  tamanho de chunk de arrays.
- **`optimization.py`** — `cull()` (remove tarefas inalcançáveis a partir
  das chaves pedidas) e `inline()` (embute o valor de uma tarefa direto
  onde ela é usada) — otimizações que rodam sobre o grafo antes da
  execução.
- **`delayed.py`** — a API mais usada por quem só quer paralelizar código
  Python comum: `@delayed` transforma uma função qualquer numa promessa
  lazy que só roda de fato dentro de `.compute()`.
- **`threaded.py` + `local.py`** — o scheduler local de verdade: um
  `ThreadPoolExecutor` real (`threaded.get`) e a variante síncrona
  (`local.get_sync`, útil para depuração passo a passo). Não são
  simulados nos testes de integração/aceitação — são o scheduler
  genuíno rodando threads genuínas.

`array/`, `dataframe/`, `bag/` (as coleções de alto nível, que dependem de
numpy/pandas) e `distributed.py` não foram alvo — o escopo ficou
deliberadamente no núcleo puro-Python, que é onde a arquitetura central
(grafo + scheduler + config) realmente vive.

## Código sob teste

`repositorios-originais/dask/dask/` é uma cópia do checkout clonado, com as pastas `tests/`
removidas antes de qualquer leitura de teste começar. Esse clone é raso
(sem tags git) e não tem um `_version.py` gerado — a versão do Dask é
calculada em build-time via `setuptools_scm`, e sem isso `dask.__version__`
cairia no fallback `"unknown"`, o que tornaria uma comparação de versão
sem sentido. Em vez disso, `conftest.py` confirma que `dask.__file__`
resolve para dentro de `repositorios-originais/dask/` — a garantia que interessa (estamos
testando o checkout clonado, não uma cópia qualquer já instalada) sem
depender de uma versão que este clone específico não tem como declarar.

## Como rodar

```bash
py -m pip install -r requirements-testes.txt
py -m pytest -q
py -m pytest -q --cov=dask --cov-report=term-missing
```

Nenhum teste depende de numpy, pandas ou de um cluster `distributed` --
só o núcleo puro-Python do Dask. Os testes de integração/aceitação usam o
`ThreadPoolExecutor` real por trás de `dask.threaded.get()`, com corrida
de thread genuína (medida com locks e contadores, não inferida).

## Organização por tipo de teste

| Arquivo | Tipo | O que valida |
|---|---|---|
| `test_estrutural_core.py` | Estrutural | `istask`/`iskey`, `get()`, `get_dependencies`, `getcycle`/`isdag`, `subs`, `quote` |
| `test_estrutural_tokenize.py` | Estrutural | `tokenize()`: determinismo, dicts, `__dask_tokenize__`, `ensure_deterministic` |
| `test_estrutural_config.py` | Estrutural | `canonical_name`, `update`/`merge` por prioridade, `dask.config.set`, `collect_env` |
| `test_estrutural_optimization.py` | Estrutural | `cull()` e `inline()` |
| `test_funcional_delayed.py` | Funcional | `@delayed`: laziness, encadeamento, `pure=`, atributo/índice lazy, `nout` |
| `test_integracao_scheduler.py` | Integração | `dask.threaded.get()` real com pool de threads, `get_sync`, config afetando `compute()` |
| `test_aceitacao_pipeline.py` | Aceitação | Histórias de usuário, pipelines reais com schedulers reais |

**105 testes, todos passando** (revisão de 2026-09-14: `toposort()` foi
removida por não ter correspondente humano possível em nenhum nível --
ver nota abaixo; eram 106 antes dela). Rodados juntos, <1s -- o núcleo puro-Python
do Dask não tem overhead de rede, worker ou cache em disco como os quatro
repositórios anteriores). Cobertura de linha medida nos módulos-alvo:
`core.py` 87%, `threaded.py` 87%, `local.py` 83%, `config.py` 69%,
`delayed.py` 54%, `tokenize.py` 51%. `optimization.py` fica em 15% porque
a suíte cobriu só `cull`/`inline`, deliberadamente — o resto do módulo é
a família de otimizações `fuse`, fora do escopo.

## Sobre os testes de mutação

Mesma decisão das quatro suítes anteriores: nenhuma ferramenta de mutação
foi executada — os casos foram desenhados para matar mutações
específicas, documentadas no teste onde o alvo não é evidente. Padrões
mais comuns aqui:

- **Curto-circuito em cadeias de `and`** (`istask`: tupla vazia devolve a
  própria tupla, não `False`, por causa de como o `and` avalia)
- **Prioridade em merge de configuração** (`update()`: `'old'` vs `'new'`
  vs `'new-defaults'`)
- **Ordenação/desempate em detecção de ciclo** (`getcycle`/`isdag`, que
  compartilham o algoritmo interno `_toposort`: distinguir "seen" de
  "completed")
- **Determinismo condicional** (`tokenize`: `ensure_deterministic=True`
  muda o comportamento por completo para um único tipo especial)

## Achados durante a escrita (relevantes para a comparação com testes humanos)

Dois comportamentos que só ficaram claros rodando o código, não lendo a
assinatura ou o docstring:

1. **`dask.config.set()` com um dict aninhado SUBSTITUI o ramo, não
   mescla.** Isso contraria a expectativa natural de quem já viu
   `dask.config.update()`/`merge()` mesclarem dicionários aninhados
   recursivamente. A diferença: `set.__init__` faz `key.split(".")`
   **na chave** do argumento recebido (`{"a": {...}}` vira uma única
   atribuição na chave `"a"`), e o valor -- mesmo sendo um dict -- é
   atribuído como está, sem descer recursivamente. Depois de
   `dask.config.set({"a": {"x": 1}})`, um `dask.config.set({"a": {"y":
   2}})` aninhado apaga o `"x"` de dentro do bloco `with` — porque
   substituiu `"a"` inteiro. Para mesclar de fato, a chave completa
   precisa vir com ponto: `dask.config.set({"a.y": 2})`. Ver
   `test_config_set_com_dict_aninhado_substitui_o_ramo_em_vez_de_mesclar`
   e o contraste em `test_config_set_com_chave_pontilhada_faz_a_mesclagem_esperada`.
2. **Só uma instância do tipo `object` *puro* cai no fallback
   não-determinístico do `tokenize()` — uma instância de classe comum,
   não.** `normalize_object()` em `tokenize.py` checa especificamente
   `type(o) is object` (não `isinstance`) para decidir se usa
   `id(o)` (não-determinístico) em vez de tentar `pickle.dumps()`
   primeiro. Uma classe Python qualquer, mesmo sem `__dask_tokenize__`
   definido, tokeniza de forma perfeitamente determinística via pickle,
   desde que seu estado seja picklable e não contenha nada
   memory-address-dependent. Só `object()` "cru" força o caminho
   instável. Ver `test_tokenize_instancia_comum_e_deterministica_via_pickle`
   vs. `test_tokenize_ensure_deterministic_levanta_para_object_puro`.
