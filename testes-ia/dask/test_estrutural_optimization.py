"""
Testes estruturais (caixa-branca) de dask/optimization.py -- cull() (remove
tarefas não alcançáveis a partir das chaves pedidas) e inline() (substitui
uma tarefa pelo seu próprio valor/expressão em quem a usa).
"""

from __future__ import annotations

from dask.optimization import cull, inline


def inc(x):
    return x + 1


def add(x, y):
    return x + y


# --------------------------------------------------------------------------
# cull
# --------------------------------------------------------------------------


def test_cull_remove_tarefas_nao_alcancaveis():
    dsk = {"x": 1, "y": (inc, "x"), "out": (add, "x", 10), "lixo": (inc, "y")}
    culled, dependencies = cull(dsk, "out")
    assert set(culled) == {"x", "out"}
    assert "lixo" not in culled
    assert "y" not in culled


def test_cull_preserva_tarefas_realmente_necessarias():
    dsk = {"x": 1, "y": (inc, "x"), "z": (add, "x", "y")}
    culled, dependencies = cull(dsk, "z")
    assert set(culled) == {"x", "y", "z"}


def test_cull_devolve_dependencies_como_efeito_colateral_util():
    dsk = {"x": 1, "y": (inc, "x"), "out": (add, "x", "y")}
    _, dependencies = cull(dsk, "out")
    assert set(dependencies["out"]) == {"x", "y"}
    assert list(dependencies["x"]) == []


def test_cull_com_lista_de_chaves_mantem_a_uniao_das_dependencias():
    dsk = {"a": 1, "b": 2, "x": (inc, "a"), "y": (inc, "b"), "lixo": (inc, "a")}
    culled, _ = cull(dsk, ["x", "y"])
    assert set(culled) == {"a", "b", "x", "y"}


# --------------------------------------------------------------------------
# inline
# --------------------------------------------------------------------------


def test_inline_substitui_constantes_por_padrao():
    """Mata mutante que troque o default de inline_constants para False."""
    dsk = {"x": 1, "y": (inc, "x")}
    resultado = inline(dsk)
    assert resultado["y"] == (inc, 1)  # "x" foi inlinado, não fica como referência


def test_inline_sem_inline_constants_preserva_a_referencia():
    dsk = {"x": 1, "y": (inc, "x")}
    resultado = inline(dsk, inline_constants=False)
    assert resultado["y"] == (inc, "x")


def test_inline_de_chave_especifica_propaga_para_quem_a_usa():
    dsk = {"x": 1, "y": (inc, "x"), "z": (add, "x", "y")}
    resultado = inline(dsk, keys="y", inline_constants=False)
    # "z" passa a conter a expressão de "y" embutida, não mais a referência "y"
    assert resultado["z"] == (add, "x", (inc, "x"))


def test_inline_mantem_a_chave_original_no_grafo_resultante():
    """inline() não remove a chave inlinada -- só embute o valor onde ela
    era usada. Remover exige combinar com cull() depois."""
    dsk = {"x": 1, "y": (inc, "x")}
    resultado = inline(dsk)
    assert "x" in resultado  # ainda está lá, mesmo já tendo sido embutida em "y"
