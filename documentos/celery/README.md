# Suíte de testes — Celery (3º repositório)

Suíte escrita **sem consultar a pasta `t/` (testes) do repositório
oficial** — só o código de produção foi lido, incluindo os utilitários que
o próprio Celery expõe para QUEM USA a biblioteca escrever seus próprios
testes (`celery/contrib/testing/`, `celery/contrib/pytest.py`) — esses não
são a suíte interna do projeto, são parte da API pública distribuída no
pacote, no mesmo espírito de `scrapy/utils/test.py` usado no repositório
anterior.

## Escopo — o que cada módulo-alvo faz

- **`app/task.py`** — a classe `Task`: `.apply()` (execução síncrona/eager),
  `.apply_async()`/`.delay()` (execução assíncrona real), `.retry()`, e os
  hooks de ciclo de vida (`before_start`, `on_success`, `on_failure`,
  `after_return`) que um desenvolvedor sobrescreve para reagir ao resultado
  de uma tarefa.
- **`app/base.py`** — a classe `Celery`: o objeto de aplicação que registra
  tarefas (decorator `@app.task`), resolve configuração (`config_from_object`,
  `add_defaults`) e decide, via `send_task`, como uma tarefa chega ao broker.
- **`canvas.py`** — `Signature`, `chain`, `group` (e `chord`, não testado
  em profundidade): a "linguagem de composição" do Celery para descrever
  fluxos de tarefas — uma depois da outra, várias em paralelo — como
  objetos que podem ser montados, clonados e recombinados antes de rodar.
- **`bootsteps.py`** — `Blueprint`/`Step`/`StartStopStep`: o mesmo padrão
  de grafo de dependências já visto na análise de arquitetura, usado para
  decidir em que ordem os componentes internos do worker (conexão,
  consumidor, heartbeat...) sobem e caem.
- **`backends/base.py` (+ `backends/cache.py` como implementação concreta)**
  — onde o resultado de uma tarefa é guardado e recuperado; testado através
  de uma instância real de `CacheBackend` com backend `memory` (em processo,
  sem servidor externo).
- **`utils/dispatch/signal.py` + `signals.py`** — o sistema de eventos do
  Celery (inspirado no de sinais do Django): permite que qualquer parte do
  sistema reaja a um momento do ciclo de vida sem acoplamento direto.
- **`worker/`, `worker/consumer/`, `concurrency/`** — não testados por
  chamada isolada de método (dependem fortemente de um broker real e de um
  loop de consumo). Validados de ponta a ponta pelas camadas de integração
  e aceitação, através de um worker embutido real.

`app/amqp.py`, `events/`, `security/`, `beat.py`, `fixups/` e a maior parte
de `worker/` e `concurrency/` não foram alvo direto.

## Código sob teste

`repositorios-originais/celery/celery/` é uma cópia exata do checkout clonado (versão `5.6.2`).
`conftest.py` insere esse caminho no início do `sys.path` e confere isso com
um `assert` na importação.

## Como rodar

```bash
py -m pip install -r requirements-testes.txt
py -m pytest -q
py -m pytest -q --cov=celery --cov-report=term-missing
```

**Nenhum teste depende de Redis, RabbitMQ ou qualquer serviço externo.**
Todos usam `broker_url="memory://"` (transporte em processo do próprio
`kombu`) e `result_backend="cache+memory://"`. Os testes de integração e
aceitação sobem um **worker Celery real e embutido**, via
`celery.contrib.testing.worker.start_worker` — um utilitário de produção do
próprio pacote, feito exatamente para isso.

**Detalhe de ambiente específico do Windows:** o pool de execução padrão do
Celery (`prefork`) depende de `os.fork()`, que não existe no Windows. Por
isso todo `start_worker(...)` desta suíte roda com `pool="solo"` (que é,
inclusive, o default do próprio `start_worker` — não foi preciso configurar
nada extra). A suíte inteira roda em ~60 segundos; a maior parte desse tempo
é a sobrecarga de subir e derrubar um worker de verdade a cada teste de
integração/aceitação (cada `with start_worker(...)` sobe uma thread, um
Blueprint completo de boot e um Consumer).

## Organização por tipo de teste

| Arquivo | Tipo | O que valida |
|---|---|---|
| `test_estrutural_task.py` | Estrutural | `Task.apply`, hooks de ciclo de vida, `retry()` em modo eager |
| `test_estrutural_canvas.py` | Estrutural | `Signature` (clone/immutable), `chain` (`\|`), `group`, em modo eager |
| `test_estrutural_bootsteps.py` | Estrutural | `Blueprint`/`Step`/`StartStopStep`: ordenação por dependência, ciclo start/stop |
| `test_estrutural_signal_backend.py` | Estrutural | `Signal` (connect/send/sender/dispatch_uid) e `CacheBackend` real |
| `test_funcional_app.py` | Funcional | API pública do objeto `Celery`: registro de tarefas, configuração, `send_task` |
| `test_integracao_worker.py` | Integração | Worker real: fila→execução→resultado, chain/group reais, retry via broker |
| `test_aceitacao_worker.py` | Aceitação | Histórias de usuário, também com worker real |

**65 testes, todos passando** (rodados juntos, ~60s). Cobertura de linha
medida nos módulos-alvo: `signals.py` 100%, `task.py` 75%, `bootsteps.py`
80%, `utils/dispatch/signal.py` 76%, `app/base.py` 68%, `cache.py` 61%,
`backends/base.py` 53% (a maior parte do restante em `backends/base.py` são
backends concretos de terceiros — MongoDB, Cassandra, S3 etc. — que essa
classe também herda/expõe, e que não fazem parte do escopo), `canvas.py`
50% (a parte não coberta é majoritariamente `chord`, deliberadamente fora
do escopo por depender de suporte nativo de "join" do backend).

## Sobre os testes de mutação

Mesma decisão das duas suítes anteriores: nenhuma ferramenta de mutação foi
executada — os casos foram desenhados para matar mutações específicas,
documentadas no teste onde o alvo não é evidente. Padrões mais comuns aqui:

- **Guardas de fluxo de controle que mudam o comportamento por completo**
  (`request.called_directly` em `retry()` — ver achado nº 1 abaixo)
- **Ordenação por grafo de dependências** (`Blueprint._finalize_steps`/topsort)
- **Merge condicional de args/kwargs/options** (`Signature._merge`,
  a diferença entre signature mutável e imutável)
- **Escolha de hook correto conforme sucesso/falha** (`on_success` vs.
  `on_failure` sendo disparados pelo tracer)

## Achados durante a escrita (relevantes para a comparação com testes humanos)

Três comportamentos que só ficaram claros rodando o código de verdade, não
lendo a assinatura dos métodos:

1. **`self.retry()` em modo eager só "retenta" de fato quando
   `task_eager_propagates=False`.** `Task.apply()` captura o retorno do
   tracer e, se for uma instância de `Retry` com `.sig` definido, chama
   `retval.sig.apply(retries=n+1)` recursivamente — isso reexecuta a
   tarefa de verdade, dentro da mesma chamada síncrona, até esgotar
   `max_retries`. Mas isso só acontece se o tracer *devolver* o `Retry`
   como retorno normal. Com `task_eager_propagates=True` (que este projeto
   liga no fixture `eager_app`, e que muitos times ligam por padrão para
   simplificar testes de falha), o tracer deixa o `Retry` escapar como
   exceção direto de `.apply()` — a lógica de reexecução nunca roda, e a
   tarefa é chamada uma única vez. Duas configurações aparentemente
   cosméticas (`task_eager_propagates`) mudam completamente se `retry()`
   retenta ou não. Ver os três testes de retry em `test_estrutural_task.py`.
2. **`app.send_task()` ignora `task_always_eager` — só avisa.** Diferente
   de `Task.apply_async()`, que checa a config e desvia para `.apply()`
   quando ligada, `send_task()` (usado para disparar uma tarefa só pelo
   nome, sem a referência à função) sempre publica uma mensagem real no
   broker, emitindo apenas um `AlwaysEagerIgnored` warning. Num teste com
   broker `memory://` e nenhum worker consumindo, isso significa que
   `.get()` **nunca retorna** — o primeiro rascunho deste teste travou o
   pytest indefinidamente até isso ser identificado. Ver
   `test_send_task_ignora_task_always_eager_e_publica_de_verdade`.
3. **Nem todo `Step` participa do ciclo `start`/`stop` do worker.**
   `Blueprint.start()` itera `parent.steps`, uma lista, mas só
   `StartStopStep.include()` de fato adiciona o step a essa lista
   (`parent.steps.append(self)`); um `Step` puro (usado só para participar
   do grafo de *criação*, via `requires`) nunca aparece em `parent.steps` e
   por isso nunca teria `.start()`/`.stop()` chamados por essa via, mesmo
   declarando esses métodos. Ver
   `test_blueprint_start_executa_steps_na_ordem_de_boot`, que só passou
   depois de trocar `Step` por `StartStopStep` nas classes de teste.
