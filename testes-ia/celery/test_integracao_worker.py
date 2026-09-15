"""
Testes de integração: um worker Celery EMBUTIDO E REAL (via
celery.contrib.testing.worker.start_worker), consumindo de um broker
`memory://` de verdade -- não é simulação, é o Blueprint de boot, o
Consumer, o pool de execução (`solo`, já que `prefork` depende de
os.fork() e não existe no Windows) e o backend de resultado cooperando
exatamente como cooperariam em produção, só que dentro do processo do
próprio pytest.

Diferença crucial em relação aos testes estruturais: aqui `task_always_eager`
fica desligado (é o padrão do fixture `celery_app`) -- a tarefa
efetivamente viaja pela fila até o worker, que é quem a executa.
"""

from __future__ import annotations

import pytest

from celery.contrib.testing.worker import start_worker


def test_tarefa_executada_por_um_worker_real_via_fila(celery_app):
    @celery_app.task
    def soma(a, b):
        return a + b

    with start_worker(celery_app, perform_ping_check=False):
        resultado = soma.delay(2, 3)
        assert resultado.get(timeout=10) == 5


def test_excecao_da_tarefa_e_repropagada_pelo_get(celery_app):
    @celery_app.task
    def sempre_falha():
        raise ValueError("erro real, vindo do worker")

    with start_worker(celery_app, perform_ping_check=False):
        resultado = sempre_falha.delay()
        with pytest.raises(ValueError, match="erro real, vindo do worker"):
            resultado.get(timeout=10)


def test_chain_real_passa_o_resultado_entre_tarefas_via_fila(celery_app):
    @celery_app.task
    def soma(a, b):
        return a + b

    @celery_app.task
    def dobro(x):
        return x * 2

    with start_worker(celery_app, perform_ping_check=False):
        encadeado = soma.s(3, 4) | dobro.s()
        resultado = encadeado.delay()
        assert resultado.get(timeout=10) == 14


def test_group_real_executa_todas_as_tarefas_e_recolhe_os_resultados(celery_app):
    @celery_app.task
    def quadrado(x):
        return x * x

    with start_worker(celery_app, perform_ping_check=False):
        from celery import group

        resultado = group(quadrado.s(1), quadrado.s(2), quadrado.s(3)).apply_async()
        assert sorted(resultado.get(timeout=10)) == [1, 4, 9]


def test_retry_atraves_de_um_worker_real_reexecuta_a_tarefa_pela_fila(celery_app):
    """Diferente do modo eager (ver test_estrutural_task.py), aqui
    self.retry() de fato passa por S.apply_async(): a nova tentativa é
    publicada de novo no broker e consumida pelo mesmo worker, como
    aconteceria em produção."""
    tentativas = []

    @celery_app.task(bind=True, max_retries=3)
    def instavel(self):
        tentativas.append(1)
        if len(tentativas) < 3:
            raise self.retry(exc=ValueError("ainda não"), countdown=0)
        return "estabilizou"

    with start_worker(celery_app, perform_ping_check=False):
        resultado = instavel.delay()
        assert resultado.get(timeout=10) == "estabilizou"

    assert len(tentativas) == 3


def test_estado_da_tarefa_e_visivel_durante_e_apos_a_execucao(celery_app):
    from celery import states

    @celery_app.task
    def tarefa_simples():
        return "pronto"

    with start_worker(celery_app, perform_ping_check=False):
        resultado = tarefa_simples.delay()
        valor = resultado.get(timeout=10)
        assert valor == "pronto"
        assert resultado.state == states.SUCCESS
        assert resultado.successful() is True
