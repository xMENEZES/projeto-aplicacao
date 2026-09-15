"""
v2 — técnica estrutural via tabela de decisão: dask.config.update()
(seção 1), tokenize._maybe_raise_nondeterministic via config global
(seção 2) e dask.config.get() (seção 3). Casos CT01-CT14 do
PLANO_DE_TESTE.md.
"""

from __future__ import annotations

import pytest

import dask
from dask.config import get, update
from dask.tokenize import TokenizationError, tokenize


# ==========================================================================
# Seção 1 — dask.config.update() (6 regras)
# ==========================================================================


def test_ct01_regra_u1_priority_new_sobrescreve_valor_existente():
    old = {"x": 1}
    update(old, {"x": 2}, priority="new")
    assert old["x"] == 2


def test_ct02_regra_u2_priority_old_com_chave_ausente_ainda_seta():
    """A prioridade 'old' só protege chaves que JÁ existem -- uma chave
    nova é sempre adicionada, não importa a prioridade."""
    old = {}
    update(old, {"x": 1}, priority="old")
    assert old["x"] == 1


def test_ct03_regra_u3_priority_old_com_chave_existente_preserva():
    old = {"x": 1}
    update(old, {"x": 2}, priority="old")
    assert old["x"] == 1


def test_ct04_regra_u4_new_defaults_com_valor_nao_customizado_sobrescreve():
    old = {"x": 0}
    update(old, {"x": 99}, priority="new-defaults", defaults={"x": 0})
    assert old["x"] == 99


def test_ct05_regra_u5_new_defaults_com_valor_customizado_preserva():
    """Mata mutante que remova a comparação 'defaults[k] == old[k]'."""
    old = {"x": 5}  # usuário já mudou de 0 (default) para 5
    update(old, {"x": 99}, priority="new-defaults", defaults={"x": 0})
    assert old["x"] == 5


def test_ct06_regra_u6_new_defaults_com_chave_ausente_ainda_seta():
    old = {}
    update(old, {"x": 1}, priority="new-defaults", defaults={"x": 0})
    assert old["x"] == 1


# ==========================================================================
# Seção 2 — tokenize + config global (4 regras)
# ==========================================================================


def test_ct07_regra_t1_ensure_deterministic_true_sempre_levanta():
    with pytest.raises(TokenizationError):
        tokenize(object(), ensure_deterministic=True)


def test_ct08_regra_t2_ensure_deterministic_false_nunca_levanta():
    tokenize(object(), ensure_deterministic=False)  # não deve levantar


def test_ct09_regra_t3_config_global_true_faz_levantar_sem_passar_o_parametro():
    """ACHADO/decisão pouco óbvia: sem passar ensure_deterministic
    explicitamente, configurar tokenize.ensure-deterministic=True via
    dask.config.set() já é suficiente para tornar object() um erro."""
    with dask.config.set({"tokenize.ensure-deterministic": True}):
        with pytest.raises(TokenizationError):
            tokenize(object())


def test_ct10_regra_t4_config_padrao_nao_levanta_sem_passar_o_parametro():
    tokenize(object())  # config padrão (False) -- não deve levantar


# ==========================================================================
# Seção 3 — dask.config.get() (4 regras)
# ==========================================================================


def test_ct11_regra_g1_override_with_ignora_o_config():
    assert get("qualquer.coisa", config={}, override_with="X") == "X"


def test_ct12_regra_g2_chave_presente_devolve_o_valor_do_config():
    assert get("x", config={"x": 42}) == 42


def test_ct13_regra_g3_chave_ausente_com_default_devolve_o_default():
    assert get("x", default=123, config={}) == 123


def test_ct14_regra_g4_chave_ausente_sem_default_levanta_key_error():
    with pytest.raises(KeyError):
        get("x", config={})
