"""
Testes funcionais (caixa-preta) do objeto Celery (app/base.py): registro de
tarefas via decorator, configuração via add_defaults/config_from_object, e
o fluxo de despacho por nome. Tudo em modo eager -- caixa-preta no sentido
de que só a API pública é exercitada, sem inspecionar estado interno.
"""

from __future__ import annotations

from celery import states


def test_task_decorator_registra_a_tarefa_pelo_nome_do_modulo_e_funcao(eager_app):
    @eager_app.task
    def minha_funcao():
        return "ok"

    assert minha_funcao.name in eager_app.tasks
    # o decorator devolve um PromiseProxy; app.tasks guarda a instância
    # reala por trás dele -- 'is' entre os dois não é garantido, mas o
    # nome e o comportamento (apply) precisam ser os mesmos.
    assert eager_app.tasks[minha_funcao.name].name == minha_funcao.name
    assert eager_app.tasks[minha_funcao.name].apply().get() == "ok"


def test_task_decorator_aceita_nome_customizado(eager_app):
    @eager_app.task(name="fila.tarefa-customizada")
    def qualquer_nome():
        return "ok"

    assert "fila.tarefa-customizada" in eager_app.tasks
    assert qualquer_nome.name == "fila.tarefa-customizada"


def test_task_bind_true_da_acesso_a_self_dentro_da_tarefa(eager_app):
    capturado = {}

    @eager_app.task(bind=True)
    def tarefa_com_bind(self):
        capturado["nome_via_self"] = self.name

    tarefa_com_bind.apply()
    assert capturado["nome_via_self"] == tarefa_com_bind.name


def test_add_defaults_nao_sobrescreve_configuracao_ja_definida(celery_app):
    """Mata mutante que faça add_defaults() sobrescrever valores explícitos."""
    celery_app.conf.task_default_queue = "minha-fila"
    celery_app.add_defaults({"task_default_queue": "fila-padrao-generica"})
    assert celery_app.conf.task_default_queue == "minha-fila"


def test_add_defaults_preenche_configuracao_ainda_nao_definida(celery_app):
    celery_app.add_defaults({"task_annotations": {"*": {"rate_limit": "5/s"}}})
    assert celery_app.conf.task_annotations == {"*": {"rate_limit": "5/s"}}


def test_config_from_object_le_configuracao_de_um_objeto_simples(celery_app):
    class ConfigDoProjeto:
        task_default_queue = "fila-do-objeto"
        worker_concurrency = 7

    celery_app.config_from_object(ConfigDoProjeto)
    assert celery_app.conf.task_default_queue == "fila-do-objeto"
    assert celery_app.conf.worker_concurrency == 7


def test_send_task_ignora_task_always_eager_e_publica_de_verdade(eager_app):
    """ACHADO: diferente de Task.apply_async(), que checa task_always_eager
    e chama .apply() no mesmo processo quando ligado, app.send_task() NUNCA
    olha para essa configuração -- ele sempre publica uma mensagem real no
    broker (só emite um aviso `AlwaysEagerIgnored` avisando disso). Como
    esta suíte usa broker_url='memory://' e não há nenhum worker consumindo
    a fila neste teste, o .get() do resultado nunca é satisfeito: o teste
    abaixo prova exatamente isso, esperando o TimeoutError em vez de um
    resultado. Um `soma.delay(4, 5)` (via Task.apply_async) teria voltado
    na hora -- é o send_task() direto por nome que se comporta diferente.
    Ver test_integracao_worker.py para o caminho feliz com um worker real."""
    import pytest

    from celery.exceptions import AlwaysEagerIgnored, TimeoutError as CeleryTimeoutError

    @eager_app.task(name="tarefa.por-nome")
    def soma(a, b):
        return a + b

    with pytest.warns(AlwaysEagerIgnored):
        resultado = eager_app.send_task("tarefa.por-nome", args=(4, 5))

    with pytest.raises(CeleryTimeoutError):
        resultado.get(timeout=1)


def test_async_result_por_id_recupera_o_mesmo_resultado_da_chamada_original(eager_app):
    @eager_app.task
    def tarefa_qualquer():
        return "valor-produzido"

    r1 = tarefa_qualquer.delay()
    r2 = eager_app.AsyncResult(r1.id)
    assert r2.state == states.SUCCESS
    assert r2.get() == "valor-produzido"
