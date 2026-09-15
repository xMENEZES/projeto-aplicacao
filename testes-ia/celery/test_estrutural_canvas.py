"""
Testes estruturais (caixa-branca) de celery/canvas.py -- Signature, chain e
group. Tudo roda em modo eager (task_always_eager=True), sem broker real:
o interesse aqui é a lógica de composição (como argumentos e resultados
fluem entre tarefas encadeadas), não a entrega de mensagens.
"""

from __future__ import annotations

from celery.result import GroupResult


def _tasks(app):
    @app.task
    def soma(a, b):
        return a + b

    @app.task
    def dobro(x):
        return x * 2

    return soma, dobro


# --------------------------------------------------------------------------
# Signature -- clone, immutable, merge de args/kwargs/options
# --------------------------------------------------------------------------


def test_signature_clone_preserva_task_e_args_originais(eager_app):
    soma, _ = _tasks(eager_app)
    sig = soma.s(1, 2)
    clone = sig.clone()
    assert clone.task == sig.task
    assert clone.args == sig.args
    assert clone is not sig


def test_signature_clone_com_args_extra_prepende_aos_existentes(eager_app):
    """Mata mutante que troque a ordem de concatenação em _merge (extra + self.args)."""
    soma, _ = _tasks(eager_app)
    sig = soma.s(2)  # args=(2,) -- espera um segundo argumento no apply
    clone = sig.clone(args=(1,))
    assert clone.args == (1, 2)


def test_signature_immutable_ignora_args_extras_no_apply(eager_app):
    """Mata mutante que remova a checagem 'if self.immutable and not force'."""
    _, dobro = _tasks(eager_app)
    sig = dobro.si(10)  # imutável, args fixos = (10,)
    resultado = sig.apply(args=(999,))  # 999 deveria ser ignorado
    assert resultado.get() == 20


def test_signature_mutavel_aceita_args_extras_no_apply(eager_app):
    _, dobro = _tasks(eager_app)
    sig = dobro.s()  # mutável, sem args próprios
    resultado = sig.apply(args=(21,))
    assert resultado.get() == 42


def test_signature_options_extras_sao_mesclados_sem_sobrescrever_indevidamente(eager_app):
    """Nota: kwargs passados para .s(...) tornam-se kwargs DA TAREFA (o
    parâmetro que a função recebe), não opções da signature (priority,
    countdown etc.) -- essas só existem via .set(**opcoes) ou options=."""
    soma, _ = _tasks(eager_app)
    sig = soma.s(1, 2).set(priority=5)
    clone = sig.clone(countdown=10)
    assert clone.options["priority"] == 5
    assert clone.options["countdown"] == 10


# --------------------------------------------------------------------------
# chain -- operador | e propagação de resultado entre etapas
# --------------------------------------------------------------------------


def test_operador_or_entre_duas_signatures_produz_chain(eager_app):
    from celery.canvas import _chain

    soma, dobro = _tasks(eager_app)
    encadeado = soma.s(1, 2) | dobro.s()
    assert isinstance(encadeado, _chain)
    assert len(encadeado.tasks) == 2


def test_chain_apply_passa_resultado_de_uma_etapa_para_a_proxima(eager_app):
    """Mata mutante que remova 'last and (last.get(),)' na montagem dos args
    da próxima etapa -- sem isso o resultado da etapa anterior nunca chega
    na próxima."""
    soma, dobro = _tasks(eager_app)
    encadeado = soma.s(3, 4) | dobro.s()  # (3+4) depois *2 = 14
    resultado = encadeado.apply()
    assert resultado.get() == 14


def test_chain_com_etapa_imutavel_nao_recebe_resultado_anterior(eager_app):
    soma, _ = _tasks(eager_app)

    @eager_app.task
    def sempre_dez():
        return 10

    encadeado = soma.s(1, 2) | sempre_dez.si()  # segunda etapa ignora o 3 anterior
    resultado = encadeado.apply()
    assert resultado.get() == 10


def test_chain_de_tres_etapas_encadeia_todas(eager_app):
    soma, dobro = _tasks(eager_app)

    @eager_app.task
    def menos_um(x):
        return x - 1

    encadeado = soma.s(2, 3) | dobro.s() | menos_um.s()  # ((2+3)*2)-1 = 9
    assert encadeado.apply().get() == 9


# --------------------------------------------------------------------------
# group -- execução em "paralelo" (eager: sequencial, mas isolado por tarefa)
# --------------------------------------------------------------------------


def test_group_de_assinaturas_independentes_roda_todas(eager_app):
    from celery import group

    soma, _ = _tasks(eager_app)
    g = group(soma.s(1, 2), soma.s(10, 20), soma.s(100, 200))
    resultado = g.apply()
    assert isinstance(resultado, GroupResult)
    assert sorted(resultado.get()) == [3, 30, 300]


def test_group_vazio_devolve_group_result_vazio(eager_app):
    from celery import group

    g = group()
    resultado = g.apply()
    assert list(resultado.results) == []
