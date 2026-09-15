"""
Testes estruturais (caixa-branca) de celery/app/task.py -- a classe Task,
seu modo de execução síncrona (apply/eager) e o mecanismo de retry.

Todos os testes usam `eager_app` (task_always_eager=True): a tarefa roda no
mesmo processo, de forma síncrona, sem broker real por trás. Isso é
suficiente para testar a lógica da classe Task isoladamente -- o
comportamento de fila/worker de verdade é coberto na camada de integração.
"""

from __future__ import annotations

import pytest

from celery import states
from celery.exceptions import MaxRetriesExceededError, Retry


# --------------------------------------------------------------------------
# apply() -- execução síncrona básica
# --------------------------------------------------------------------------


def test_apply_sucesso_devolve_eager_result_com_retorno_correto(eager_app):
    @eager_app.task
    def soma(a, b):
        return a + b

    resultado = soma.apply(args=(2, 3))
    assert resultado.get() == 5
    assert resultado.state == states.SUCCESS
    assert resultado.successful() is True


def test_apply_propaga_excecao_quando_eager_propagates_habilitado(eager_app):
    @eager_app.task
    def sempre_falha():
        raise ValueError("falhou de propósito")

    with pytest.raises(ValueError, match="falhou de propósito"):
        sempre_falha.apply()


def test_apply_com_throw_false_nao_propaga_e_marca_failure(eager_app):
    """Mata mutante que remova o parâmetro throw ou ignore seu valor explícito."""

    @eager_app.task
    def sempre_falha():
        raise ValueError("controlado")

    resultado = sempre_falha.apply(throw=False)
    assert resultado.state == states.FAILURE
    assert resultado.failed() is True
    assert isinstance(resultado.result, ValueError)


def test_delay_em_modo_eager_se_comporta_como_apply(eager_app):
    @eager_app.task
    def dobro(x):
        return x * 2

    resultado = dobro.delay(21)
    assert resultado.get() == 42
    assert resultado.state == states.SUCCESS


# --------------------------------------------------------------------------
# Hooks de ciclo de vida (before_start/on_success/on_failure/after_return)
# --------------------------------------------------------------------------


def test_hooks_de_sucesso_sao_chamados_na_ordem_esperada(eager_app):
    from celery import Task

    eventos = []

    class TarefaComHooks(Task):
        name = "tarefa-com-hooks-sucesso"

        def run(self, x):
            eventos.append(("run", x))
            return x + 1

        def before_start(self, task_id, args, kwargs):
            eventos.append(("before_start", args))

        def on_success(self, retval, task_id, args, kwargs):
            eventos.append(("on_success", retval))

        def after_return(self, status, retval, task_id, args, kwargs, einfo):
            eventos.append(("after_return", status))

    tarefa = eager_app.register_task(TarefaComHooks())
    tarefa.apply(args=(10,))

    assert eventos == [
        ("before_start", (10,)),
        ("run", 10),
        ("on_success", 11),
        ("after_return", states.SUCCESS),
    ]


def test_hook_on_failure_e_chamado_no_lugar_de_on_success(eager_app):
    """Mata mutante que troque a condição de sucesso/falha na tracer e chame
    o hook errado."""
    from celery import Task

    eventos = []

    class TarefaQueFalha(Task):
        name = "tarefa-com-hooks-falha"

        def run(self):
            raise RuntimeError("propositalmente quebrada")

        def on_success(self, retval, task_id, args, kwargs):
            eventos.append("on_success")

        def on_failure(self, exc, task_id, args, kwargs, einfo):
            eventos.append(("on_failure", str(exc)))

    tarefa = eager_app.register_task(TarefaQueFalha())
    tarefa.apply(throw=False)

    assert eventos == [("on_failure", "propositalmente quebrada")]


# --------------------------------------------------------------------------
# retry() -- e um achado importante sobre o comportamento em modo eager
# --------------------------------------------------------------------------


def test_retry_com_eager_propagates_reexecuta_a_tarefa_de_verdade(celery_app):
    """ACHADO, e não o que a primeira leitura de retry() sugere: em modo
    eager, self.retry() levanta um objeto Retry que carrega a signature da
    própria tarefa (Retry.sig). Se task_eager_propagates estiver desligado
    (o default REAL do Celery -- task_eager_propagates=False; o fixture
    eager_app desta suíte o liga para simplificar os testes de falha
    simples, então este teste usa celery_app puro e configura na mão), o
    tracer interno CAPTURA esse Retry em vez de deixá-lo escapar, e
    apply() detecta 'isinstance(retval, Retry) and retval.sig is not None'
    e reexecuta a tarefa chamando retval.sig.apply(retries=n+1) -- de
    verdade, de novo, de forma recursiva, dentro da mesma chamada
    síncrona. O resultado: a tarefa roda max_retries + 1 vezes no total."""
    from celery import Task

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False

    tentativas = []

    class TarefaComRetry(Task):
        name = "tarefa-com-retry-reexecuta"
        max_retries = 3

        def run(self):
            tentativas.append(1)
            try:
                raise ValueError("erro temporário")
            except ValueError as exc:
                raise self.retry(exc=exc, countdown=0)

    tarefa = celery_app.register_task(TarefaComRetry())
    resultado = tarefa.apply()

    assert len(tentativas) == 4  # 1 tentativa original + 3 retries
    assert resultado.state == states.FAILURE
    assert isinstance(resultado.result, ValueError)


def test_max_retries_excedido_sem_exc_devolve_max_retries_exceeded_error(celery_app):
    from celery import Task

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False

    tentativas = []

    class TarefaSemExcExplicito(Task):
        name = "tarefa-retry-sem-exc"
        max_retries = 2

        def run(self):
            tentativas.append(1)
            raise self.retry(countdown=0)

    tarefa = celery_app.register_task(TarefaSemExcExplicito())
    resultado = tarefa.apply()

    assert len(tentativas) == 3  # 1 original + 2 retries
    assert isinstance(resultado.result, MaxRetriesExceededError)


def test_retry_com_eager_propagates_true_levanta_retry_apos_uma_unica_tentativa(
    eager_app,
):
    """Com task_eager_propagates=True (o que o fixture eager_app liga, e
    que muitos projetos também ligam nos próprios testes para simplificar
    a verificação de falhas), o tracer NÃO captura o Retry -- ele escapa
    direto de .apply(), e a lógica de reexecução em apply() (que só roda
    depois que o tracer retorna normalmente) nunca chega a ser acionada.
    Resultado: a tarefa roda uma única vez, e quem chamou .apply() recebe
    a exceção Retry (não a ValueError original, embora ela fique acessível
    via Retry.exc)."""
    from celery import Task

    tentativas = []

    class TarefaComRetry(Task):
        name = "tarefa-com-retry-propagates-true"
        max_retries = 5

        def run(self):
            tentativas.append(1)
            try:
                raise ValueError("erro-original")
            except ValueError as exc:
                raise self.retry(exc=exc, countdown=0)

    tarefa = eager_app.register_task(TarefaComRetry())
    with pytest.raises(Retry) as exc_info:
        tarefa.apply()

    assert len(tentativas) == 1
    assert isinstance(exc_info.value.exc, ValueError)


# --------------------------------------------------------------------------
# signature() / .s() / .si()
# --------------------------------------------------------------------------


def test_s_cria_signature_com_args_posicionais(eager_app):
    @eager_app.task
    def soma(a, b):
        return a + b

    sig = soma.s(2, 3)
    assert sig.task == soma.name
    assert sig.args == (2, 3)
    assert sig.immutable is False


def test_si_cria_signature_imutavel(eager_app):
    """Mata mutante que remova immutable=True em si()."""

    @eager_app.task
    def soma(a, b):
        return a + b

    sig = soma.si(2, 3)
    assert sig.immutable is True


def test_signature_executa_via_apply(eager_app):
    @eager_app.task
    def multiplica(a, b):
        return a * b

    sig = multiplica.s(6, 7)
    resultado = sig.apply()
    assert resultado.get() == 42


# --------------------------------------------------------------------------
# request / contexto da tarefa em execução
# --------------------------------------------------------------------------


def test_request_reflete_argumentos_durante_a_execucao(eager_app):
    capturado = {}

    @eager_app.task(bind=True)
    def tarefa_que_le_o_proprio_request(self, valor):
        capturado["id"] = self.request.id
        capturado["is_eager"] = self.request.is_eager
        return valor

    tarefa_que_le_o_proprio_request.apply(args=(99,))
    assert capturado["is_eager"] is True
    assert capturado["id"] is not None


def test_request_fora_de_execucao_devolve_contexto_padrao_vazio(eager_app):
    @eager_app.task
    def tarefa_qualquer():
        return None

    assert tarefa_qualquer.request.id is None
