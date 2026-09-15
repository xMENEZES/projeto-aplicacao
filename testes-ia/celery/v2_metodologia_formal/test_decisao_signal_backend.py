"""
v2 — técnica estrutural via tabela de decisão: Signal.send() (sender do
receptor × sender do envio) e Backend.mark_as_done/mark_as_failure
(store_result). Casos CT12-CT18 do PLANO_DE_TESTE.md (seções 4 e 5).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from celery import states
from celery.utils.dispatch import Signal


# ==========================================================================
# Seção 4 — Signal.send() (sender do receptor × sender do envio)
# ==========================================================================


def test_ct12_regra_s1_receptor_sem_sender_e_chamado_para_qualquer_envio():
    sinal = Signal(name="teste")
    chamadas = []
    sinal.connect(lambda sender, **kw: chamadas.append(sender), sender=None, weak=False)
    sinal.send(sender="qualquer-coisa")
    assert chamadas == ["qualquer-coisa"]


def test_ct13_regra_s2_sender_do_envio_igual_ao_do_receptor_e_chamado():
    sinal = Signal(name="teste")
    chamadas = []
    sinal.connect(lambda sender, **kw: chamadas.append(sender), sender="A", weak=False)
    sinal.send(sender="A")
    assert chamadas == ["A"]


def test_ct14_regra_s3_sender_do_envio_diferente_nao_e_chamado():
    """Mata mutante que remova o filtro de sender em _live_receivers."""
    sinal = Signal(name="teste")
    chamadas = []
    sinal.connect(lambda sender, **kw: chamadas.append(sender), sender="A", weak=False)
    sinal.send(sender="B")
    assert chamadas == []


# ==========================================================================
# Seção 5 — Backend.mark_as_done / mark_as_failure × store_result
# ==========================================================================


def test_ct15_regra_b1_mark_as_done_com_store_result_true_grava(eager_app):
    backend = eager_app.backend
    espiao = MagicMock(wraps=backend.store_result)
    backend.store_result = espiao

    backend.mark_as_done("id-1", "valor", store_result=True)

    espiao.assert_called_once()
    assert espiao.call_args.args[2] == states.SUCCESS


def test_ct16_regra_b2_mark_as_done_com_store_result_false_nao_grava(eager_app):
    """Mata mutante que remova a checagem 'if store_result' em mark_as_done."""
    backend = eager_app.backend
    espiao = MagicMock(wraps=backend.store_result)
    backend.store_result = espiao

    backend.mark_as_done("id-2", "valor", store_result=False)

    espiao.assert_not_called()


def test_ct17_regra_b3_mark_as_failure_com_store_result_true_grava(eager_app):
    backend = eager_app.backend
    espiao = MagicMock(wraps=backend.store_result)
    backend.store_result = espiao

    backend.mark_as_failure("id-3", ValueError("erro"), store_result=True)

    espiao.assert_called_once()


def test_ct18_regra_b4_mark_as_failure_com_store_result_false_nao_grava(eager_app):
    backend = eager_app.backend
    espiao = MagicMock(wraps=backend.store_result)
    backend.store_result = espiao

    backend.mark_as_failure("id-4", ValueError("erro"), store_result=False)

    espiao.assert_not_called()
