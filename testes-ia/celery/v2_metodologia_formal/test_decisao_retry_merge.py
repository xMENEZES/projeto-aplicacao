"""
v2 — técnica estrutural via tabela de decisão: Task.retry() em modo eager
(seções 1 e 3 do plano) e Signature._merge()/clone() (seção 2). Casos
CT01-CT11 do PLANO_DE_TESTE.md. Reaproveita as fixtures `celery_app` e
`eager_app` do conftest.py da pasta-mãe.
"""

from __future__ import annotations

from celery import Task, states
from celery.exceptions import MaxRetriesExceededError


def _app_eager_com_propagates(celery_app, propagates):
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = propagates
    return celery_app


# ==========================================================================
# Seção 1 — Task.retry() em modo eager
# ==========================================================================


def test_ct01_regra_e1_propagates_true_retry_escapa_e_roda_uma_vez(celery_app):
    import pytest
    from celery.exceptions import Retry

    app = _app_eager_com_propagates(celery_app, propagates=True)
    tentativas = []

    class TarefaComRetry(Task):
        name = "ct01"
        max_retries = 5

        def run(self):
            tentativas.append(1)
            try:
                raise ValueError("erro")
            except ValueError as exc:
                raise self.retry(exc=exc, countdown=0)

    tarefa = app.register_task(TarefaComRetry())
    with pytest.raises(Retry):
        tarefa.apply()
    assert len(tentativas) == 1


def test_ct02_regra_e2_propagates_false_reexecuta_dentro_do_limite(celery_app):
    app = _app_eager_com_propagates(celery_app, propagates=False)
    tentativas = []

    class TarefaComRetry(Task):
        name = "ct02"
        max_retries = 3

        def run(self):
            tentativas.append(1)
            try:
                raise ValueError("erro")
            except ValueError as exc:
                raise self.retry(exc=exc, countdown=0)

    tarefa = app.register_task(TarefaComRetry())
    resultado = tarefa.apply()
    assert len(tentativas) == 4  # 1 original + 3 retries
    assert resultado.state == states.FAILURE


def test_ct03_regra_e3_esgotado_com_exc_devolve_a_excecao_original(celery_app):
    app = _app_eager_com_propagates(celery_app, propagates=False)

    class TarefaComRetry(Task):
        name = "ct03"
        max_retries = 2

        def run(self):
            try:
                raise ValueError("erro-original")
            except ValueError as exc:
                raise self.retry(exc=exc, countdown=0)

    tarefa = app.register_task(TarefaComRetry())
    resultado = tarefa.apply()
    assert isinstance(resultado.result, ValueError)
    assert str(resultado.result) == "erro-original"


def test_ct04_regra_e4_esgotado_sem_exc_devolve_max_retries_exceeded(celery_app):
    app = _app_eager_com_propagates(celery_app, propagates=False)

    class TarefaComRetry(Task):
        name = "ct04"
        max_retries = 2

        def run(self):
            raise self.retry(countdown=0)

    tarefa = app.register_task(TarefaComRetry())
    resultado = tarefa.apply()
    assert isinstance(resultado.result, MaxRetriesExceededError)


# ==========================================================================
# Seção 3 — valor limite em max_retries
# ==========================================================================


def test_ct05_valor_limite_tentativa_na_fronteira_ainda_reexecuta(celery_app):
    """max_retries=2: a chamada onde retries chega a 2 (2ª retentativa)
    ainda está dentro do limite (2 <= 2) e deve reexecutar."""
    app = _app_eager_com_propagates(celery_app, propagates=False)
    tentativas = []

    class TarefaComRetry(Task):
        name = "ct05"
        max_retries = 2

        def run(self):
            tentativas.append(1)
            if len(tentativas) <= 2:  # força reexecução até a 3a chamada
                raise self.retry(countdown=0)
            return "ok"

    tarefa = app.register_task(TarefaComRetry())
    resultado = tarefa.apply()
    assert len(tentativas) == 3  # 1 original + 2 retries (na fronteira) = sucesso
    assert resultado.result == "ok"


def test_ct06_valor_limite_uma_tentativa_alem_da_fronteira_desiste(celery_app):
    """max_retries=2: se a tarefa insiste em falhar além da 2a retentativa,
    a 3a tentativa de retry (retries=3 > 2) desiste."""
    app = _app_eager_com_propagates(celery_app, propagates=False)
    tentativas = []

    class TarefaComRetry(Task):
        name = "ct06"
        max_retries = 2

        def run(self):
            tentativas.append(1)
            raise self.retry(countdown=0)  # sempre falha, nunca converge

    tarefa = app.register_task(TarefaComRetry())
    resultado = tarefa.apply()
    assert len(tentativas) == 3  # 1 original + 2 retries; a 3a chamada de retry() desiste
    assert isinstance(resultado.result, MaxRetriesExceededError)


# ==========================================================================
# Seção 2 — Signature._merge() / clone()
# ==========================================================================


def test_ct07_regra_m1_mutavel_com_args_extras_prepoe(eager_app):
    @eager_app.task
    def soma(a, b):
        return a + b

    sig = soma.s(2)  # args=(2,)
    args, kwargs, options = sig._merge(args=(1,))
    assert args == (1, 2)


def test_ct08_regra_m2_mutavel_sem_args_extras_preserva(eager_app):
    @eager_app.task
    def soma(a, b):
        return a + b

    sig = soma.s(1, 2)
    args, kwargs, options = sig._merge()
    assert args == (1, 2)


def test_ct09_regra_m3_imutavel_sem_force_ignora_args_extras(eager_app):
    @eager_app.task
    def dobro(x):
        return x * 2

    sig = dobro.si(10)
    args, kwargs, options = sig._merge(args=(999,))
    assert args == (10,)  # 999 foi ignorado


def test_ct10_regra_m4_imutavel_com_force_direto_contorna_imutabilidade(eager_app):
    """Mata mutante que remova a checagem 'and not force' em _merge."""
    @eager_app.task
    def dobro(x):
        return x * 2

    sig = dobro.si(10)
    args, kwargs, options = sig._merge(args=(999,), force=True)
    assert args == (999, 10)


def test_ct11_achado_clone_force_true_nao_produz_o_mesmo_efeito_que_merge(eager_app):
    """ACHADO: Signature.clone(args=.., force=True) NÃO contorna a
    imutabilidade como _merge(force=True) contorna. clone() repassa
    **opts (incluindo 'force') como o argumento POSICIONAL `options` de
    _merge(), não como o parâmetro nomeado `force` -- então o 'force' do
    usuário vira uma entrada qualquer dentro de .options, e o parâmetro
    real `force` de _merge fica no default (False). Resultado: continua
    caindo na regra M3, não na M4, apesar da intenção do chamador."""
    @eager_app.task
    def dobro(x):
        return x * 2

    sig = dobro.si(10)
    clone = sig.clone(args=(999,), force=True)
    assert clone.args == (10,)  # e não (999, 10) como CT10
    assert clone.options.get("force") is True  # 'force' "vazou" para dentro de .options
