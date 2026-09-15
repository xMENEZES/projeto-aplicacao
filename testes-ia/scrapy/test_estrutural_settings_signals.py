"""
Testes estruturais (caixa-branca) de scrapy/settings/__init__.py
(BaseSettings/Settings) e scrapy/signalmanager.py.

Nenhum destes dois módulos depende do reactor Twisted -- Settings é um
dicionário com prioridades, SignalManager é uma fila de pub/sub síncrona
(pydispatch) por baixo dos panos.
"""

from __future__ import annotations

import pytest

from scrapy.settings import BaseSettings, Settings
from scrapy.signalmanager import SignalManager


# --------------------------------------------------------------------------
# BaseSettings -- prioridades
# --------------------------------------------------------------------------


def test_set_com_prioridade_menor_nao_sobrescreve_valor_existente():
    """Mata mutante que troque 'priority >= self.priority' por '>' ou '<='."""
    s = BaseSettings()
    s.set("X", "valor-projeto", priority="project")  # 20
    s.set("X", "valor-default", priority="default")  # 0, menor
    assert s["X"] == "valor-projeto"


def test_set_com_prioridade_igual_sobrescreve_valor_existente():
    s = BaseSettings()
    s.set("X", "primeiro", priority="project")
    s.set("X", "segundo", priority="project")
    assert s["X"] == "segundo"


def test_set_com_prioridade_maior_sobrescreve():
    s = BaseSettings()
    s.set("X", "valor-projeto", priority="project")
    s.set("X", "valor-cmdline", priority="cmdline")  # 40, maior
    assert s["X"] == "valor-cmdline"


def test_getitem_chave_ausente_retorna_none_sem_levantar():
    s = BaseSettings()
    assert s["NAO_EXISTE"] is None


def test_get_usa_default_quando_ausente():
    s = BaseSettings()
    assert s.get("NAO_EXISTE", "padrao") == "padrao"


@pytest.mark.parametrize(
    "valor, esperado", [(1, True), ("1", True), (True, True), ("True", True), ("true", True)]
)
def test_getbool_valores_verdadeiros(valor, esperado):
    s = BaseSettings({"X": valor})
    assert s.getbool("X") is esperado


@pytest.mark.parametrize(
    "valor, esperado",
    [(0, False), ("0", False), (False, False), ("False", False), ("false", False), (None, False)],
)
def test_getbool_valores_falsos(valor, esperado):
    s = BaseSettings({"X": valor})
    assert s.getbool("X") is esperado


def test_getbool_valor_invalido_levanta_value_error():
    s = BaseSettings({"X": "talvez"})
    with pytest.raises(ValueError):
        s.getbool("X")


def test_getint_e_getfloat_convertem_o_tipo():
    s = BaseSettings({"N": "42", "F": "3.5"})
    assert s.getint("N") == 42
    assert s.getfloat("F") == 3.5


def test_getlist_string_separada_por_virgula():
    s = BaseSettings({"L": "um,dois,tres"})
    assert s.getlist("L") == ["um", "dois", "tres"]


def test_getlist_string_vazia_retorna_lista_vazia():
    """Mata mutante que remova a checagem 'if not value' antes do split."""
    s = BaseSettings({"L": ""})
    assert s.getlist("L") == []


def test_getdict_string_json():
    s = BaseSettings({"D": '{"a": 1, "b": 2}'})
    assert s.getdict("D") == {"a": 1, "b": 2}


def test_getdictorlist_aceita_json_de_lista():
    s = BaseSettings({"X": '["um", "dois"]'})
    assert s.getdictorlist("X") == ["um", "dois"]


def test_getdictorlist_fallback_para_csv_quando_nao_e_json_valido():
    """Mata mutante que remova o fallback de split(',') quando json.loads falha."""
    s = BaseSettings({"X": "um,dois,tres"})
    assert s.getdictorlist("X") == ["um", "dois", "tres"]


def test_getwithbase_combina_setting_e_seu_sufixo_base():
    s = BaseSettings({"X_BASE": {"a": 1}, "X": {"b": 2}})
    combinado = s.getwithbase("X")
    assert dict(combinado) == {"a": 1, "b": 2}


def test_getpriority_retorna_none_para_chave_ausente():
    s = BaseSettings()
    assert s.getpriority("NAO_EXISTE") is None


def test_getpriority_retorna_o_valor_numerico_da_prioridade_usada():
    s = BaseSettings()
    s.set("X", "valor", priority="spider")
    assert s.getpriority("X") == 30


def test_delete_respeita_prioridade_minima():
    """Mata mutante que remova a checagem de prioridade em delete()."""
    s = BaseSettings()
    s.set("X", "valor", priority="spider")  # 30
    s.delete("X", priority="default")  # 0, menor: não deve remover
    assert s["X"] == "valor"
    s.delete("X", priority="spider")  # 30, igual: remove
    assert "X" not in s


def test_freeze_impede_novas_alteracoes():
    s = BaseSettings({"X": 1})
    s.freeze()
    with pytest.raises(TypeError):
        s.set("Y", 2)


def test_frozencopy_nao_afeta_o_original():
    s = BaseSettings({"X": 1})
    copia_congelada = s.frozencopy()
    assert copia_congelada.frozen is True
    assert s.frozen is False
    s.set("Y", 2)  # ainda mutável no original


def test_copy_e_independente_do_original():
    s = BaseSettings({"X": [1, 2, 3]})
    copia = s.copy()
    copia.set("X", [9], priority="cmdline")
    assert s["X"] == [1, 2, 3]


def test_settings_publica_carrega_defaults_do_projeto():
    """Settings() (a subclasse pública) já vem populada; BaseSettings() não."""
    s = Settings()
    assert s.get("RETRY_TIMES") is not None
    assert BaseSettings().get("RETRY_TIMES") is None


# --------------------------------------------------------------------------
# SignalManager
# --------------------------------------------------------------------------


def test_connect_e_send_catch_log_entrega_kwargs_ao_receptor():
    sm = SignalManager()
    recebido = {}

    def receptor(valor, **kwargs):
        recebido["valor"] = valor

    sinal = object()
    sm.connect(receptor, sinal)
    sm.send_catch_log(sinal, valor=42)
    assert recebido["valor"] == 42


def test_send_catch_log_captura_excecao_do_receptor_sem_propagar():
    """Mata mutante que remova o catch de exceções dentro do dispatcher."""
    sm = SignalManager()

    def receptor_com_erro(**kwargs):
        raise ValueError("falha proposital")

    sinal = object()
    sm.connect(receptor_com_erro, sinal)
    resultados = sm.send_catch_log(sinal)  # não deve levantar
    # o resultado inclui o par (receptor, Failure) com o erro capturado
    assert len(resultados) == 1
    _receptor, resultado = resultados[0]
    assert resultado.check(ValueError)


def test_disconnect_remove_o_receptor():
    sm = SignalManager()
    chamadas = []

    def receptor(**kwargs):
        chamadas.append(1)

    sinal = object()
    sm.connect(receptor, sinal)
    sm.disconnect(receptor, sinal)
    sm.send_catch_log(sinal)
    assert chamadas == []


def test_disconnect_all_remove_o_unico_receptor_do_sinal():
    sm = SignalManager()
    chamadas = []

    def receptor(**kwargs):
        chamadas.append(1)

    sinal = object()
    sm.connect(receptor, sinal)
    sm.disconnect_all(sinal)
    sm.send_catch_log(sinal)
    assert chamadas == []


def test_disconnect_all_com_dois_receptores_deixa_um_conectado():
    """ACHADO, não premissa: `scrapy.utils.signal.disconnect_all` itera
    `liveReceivers(getAllReceivers(...))` e desconecta cada item DENTRO do
    mesmo laço que está iterando essa lista -- um clássico "mutar a lista
    enquanto itera". Com exatamente 2 receptores no mesmo sinal, o segundo
    sobrevive de forma reprodutível (confirmado em 3 execuções seguidas,
    sempre com o mesmo resultado). Este teste documenta o comportamento
    real observado, não o que o nome do método sugere. Vale conferir se a
    suíte oficial testa disconnect_all() com mais de um receptor por sinal --
    é o tipo de caso que só aparece com múltiplos receptores."""
    sm = SignalManager()
    chamadas = []

    def receptor_a(**kwargs):
        chamadas.append("a")

    def receptor_b(**kwargs):
        chamadas.append("b")

    sinal = object()
    sm.connect(receptor_a, sinal)
    sm.connect(receptor_b, sinal)
    sm.disconnect_all(sinal)
    sm.send_catch_log(sinal)
    assert chamadas == ["b"]  # receptor_a foi removido; receptor_b, não


def test_sinais_com_sender_diferente_nao_se_misturam():
    """Mata mutante que remova o kwargs.setdefault('sender', self.sender)."""
    sm_a = SignalManager(sender="A")
    sm_b = SignalManager(sender="B")
    chamadas = []

    def receptor(**kwargs):
        chamadas.append(kwargs.get("sender"))

    sinal = object()
    sm_a.connect(receptor, sinal)
    sm_b.send_catch_log(sinal)  # sender diferente, não deveria disparar o receptor de A
    assert chamadas == []
    sm_a.send_catch_log(sinal)
    assert chamadas == ["A"]
