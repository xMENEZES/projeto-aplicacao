"""
Testes estruturais (caixa-branca) de dois módulos que não têm relação direta
entre si, mas que juntos completam o conjunto de "módulos centrais" da
análise de arquitetura: celery/utils/dispatch/signal.py (o sistema de
eventos do Celery, parecido com o de sinais do Django) e o backend de
resultado (celery/backends/base.py + backends/cache.py), testado através
de uma instância real de CacheBackend (`cache+memory://`), sem broker.
"""

from __future__ import annotations

import pytest

from celery import states
from celery.utils.dispatch import Signal


# --------------------------------------------------------------------------
# celery.utils.dispatch.Signal
# --------------------------------------------------------------------------


def test_connect_e_send_entrega_kwargs_ao_receptor():
    sinal = Signal(name="teste")
    recebido = {}

    def receptor(sender, **kwargs):
        recebido["sender"] = sender
        recebido["valor"] = kwargs.get("valor")

    sinal.connect(receptor, weak=False)
    sinal.send(sender="origem", valor=42)

    assert recebido == {"sender": "origem", "valor": 42}


def test_send_filtra_receptores_por_sender_especifico():
    """Mata mutante que remova a comparação 'r_senderkey == senderkey'."""
    sinal = Signal(name="teste")
    chamadas = []

    def receptor(sender, **kwargs):
        chamadas.append(sender)

    sinal.connect(receptor, sender="app-a", weak=False)
    sinal.send(sender="app-b")  # sender diferente: não deve disparar
    assert chamadas == []
    sinal.send(sender="app-a")
    assert chamadas == ["app-a"]


def test_receptor_sem_sender_recebe_de_qualquer_remetente():
    sinal = Signal(name="teste")
    chamadas = []

    def receptor(sender, **kwargs):
        chamadas.append(sender)

    sinal.connect(receptor, sender=None, weak=False)
    sinal.send(sender="qualquer-coisa")
    assert chamadas == ["qualquer-coisa"]


def test_receptor_que_nao_aceita_kwargs_e_rejeitado_no_connect():
    """Mata mutante que remova a validação fun_accepts_kwargs()."""
    sinal = Signal(name="teste")

    def receptor_sem_kwargs(sender):
        pass

    with pytest.raises(ValueError):
        sinal.connect(receptor_sem_kwargs, weak=False)


def test_disconnect_por_dispatch_uid_remove_o_receptor_certo():
    sinal = Signal(name="teste")
    chamadas = []

    def receptor(sender, **kwargs):
        chamadas.append(1)

    sinal.connect(receptor, dispatch_uid="meu-id", weak=False)
    removido = sinal.disconnect(dispatch_uid="meu-id")
    sinal.send(sender=None)

    assert removido is True
    assert chamadas == []


def test_connect_com_mesmo_dispatch_uid_nao_duplica_receptor():
    sinal = Signal(name="teste")
    chamadas = []

    def receptor(sender, **kwargs):
        chamadas.append(1)

    sinal.connect(receptor, dispatch_uid="mesmo-id", weak=False)
    sinal.connect(receptor, dispatch_uid="mesmo-id", weak=False)
    sinal.send(sender=None)

    assert chamadas == [1]  # e não [1, 1]


def test_send_captura_excecao_do_receptor_e_devolve_na_resposta():
    """Mata mutante que remova o try/except em torno da chamada ao receptor."""
    sinal = Signal(name="teste")

    def receptor_com_erro(sender, **kwargs):
        raise RuntimeError("falha proposital")

    sinal.connect(receptor_com_erro, weak=False)
    respostas = sinal.send(sender=None)  # não deve levantar

    assert len(respostas) == 1
    _receptor, resultado = respostas[0]
    assert isinstance(resultado, RuntimeError)


def test_connect_como_decorator_com_sender_fixo():
    sinal = Signal(name="teste")
    chamadas = []

    @sinal.connect(sender="app-x", weak=False)
    def receptor(sender, **kwargs):
        chamadas.append(sender)

    sinal.send(sender="app-x")
    assert chamadas == ["app-x"]


def test_has_listeners_reflete_conexoes_ativas():
    sinal = Signal(name="teste")
    assert sinal.has_listeners() is False

    def receptor(sender, **kwargs):
        pass

    sinal.connect(receptor, weak=False)
    assert sinal.has_listeners() is True


# --------------------------------------------------------------------------
# Backend de resultado (CacheBackend real, sem broker)
# --------------------------------------------------------------------------


def test_get_task_meta_de_id_desconhecido_devolve_pending(eager_app):
    meta = eager_app.backend.get_task_meta("id-que-nao-existe")
    assert meta["status"] == states.PENDING


def test_mark_as_done_e_recuperavel_via_get_task_meta(eager_app):
    backend = eager_app.backend
    backend.mark_as_done("tarefa-1", {"ok": True})
    meta = backend.get_task_meta("tarefa-1")
    assert meta["status"] == states.SUCCESS
    assert meta["result"] == {"ok": True}


def test_mark_as_failure_guarda_a_excecao_original(eager_app):
    backend = eager_app.backend
    erro = ValueError("algo deu errado")
    backend.mark_as_failure("tarefa-2", erro)
    meta = backend.get_task_meta("tarefa-2")
    assert meta["status"] == states.FAILURE
    assert isinstance(meta["result"], ValueError)
    assert str(meta["result"]) == "algo deu errado"


def test_async_result_reflete_o_estado_gravado_no_backend(eager_app):
    """Integra Backend + AsyncResult: o resultado é escrito diretamente no
    backend (sem tarefa nenhuma envolvida) e lido de volta através da API
    pública que um usuário realmente usaria."""
    eager_app.backend.mark_as_done("tarefa-3", 123)
    resultado = eager_app.AsyncResult("tarefa-3")
    assert resultado.state == states.SUCCESS
    assert resultado.get() == 123
