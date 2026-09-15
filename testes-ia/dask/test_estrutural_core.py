"""
Testes estruturais (caixa-branca) de dask/core.py -- as primitivas puras de
grafo de tarefas: o que é uma "tarefa", como buscar dependências, como
detectar ciclos, como substituir valores dentro de uma tarefa. Nada aqui
precisa de scheduler, numpy ou pandas -- é só grafo, como dict + tuplas.
"""

from __future__ import annotations

import pytest

from dask.core import (
    flatten,
    get,
    get_dependencies,
    get_deps,
    getcycle,
    ishashable,
    iskey,
    isdag,
    istask,
    literal,
    quote,
    reshapelist,
    reverse_dict,
    subs,
    validate_key,
)


def inc(x):
    return x + 1


def add(x, y):
    return x + y


# --------------------------------------------------------------------------
# ishashable / istask / iskey
# --------------------------------------------------------------------------


@pytest.mark.parametrize("valor, esperado", [(1, True), ("a", True), ((1, 2), True), ([1], False), ({1: 2}, False)])
def test_ishashable(valor, esperado):
    assert ishashable(valor) is esperado


def test_istask_reconhece_tupla_com_callable_na_frente():
    assert istask((inc, "x")) is True


@pytest.mark.parametrize("valor", [1, "x", [inc, "x"], ()])
def test_istask_rejeita_nao_tarefas(valor):
    """Mata mutante que remova a checagem 'callable(x[0])' ou 'x' (tupla
    não-vazia). Nota: para tupla vazia, istask() devolve a própria tupla
    `()` (falsy, mas não o booleano False) -- o 'and' em cadeia da
    implementação para no primeiro operando falso e o devolve como está,
    em vez de normalizar para bool. Por isso a checagem aqui é 'not', não
    'is False'."""
    assert not istask(valor)


@pytest.mark.parametrize(
    "valor, esperado",
    [(1, True), (1.5, True), ("a", True), ((1, "a"), True), ([1], False), (b"bytes", False)],
)
def test_iskey(valor, esperado):
    assert iskey(valor) is esperado


def test_validate_key_aceita_chave_valida():
    validate_key("x")  # não levanta
    validate_key(("x", 0, 1))  # não levanta


def test_validate_key_rejeita_chave_invalida():
    with pytest.raises(TypeError):
        validate_key([1, 2])


def test_validate_key_tupla_com_elemento_invalido_indica_o_indice():
    with pytest.raises(TypeError, match="index=1"):
        validate_key(("x", [1, 2]))


# --------------------------------------------------------------------------
# get() -- execução direta do grafo (sem scheduler)
# --------------------------------------------------------------------------


def test_get_valor_simples():
    dsk = {"x": 1}
    assert get(dsk, "x") == 1


def test_get_executa_a_cadeia_de_tarefas():
    dsk = {"x": 1, "y": (inc, "x"), "z": (add, "x", "y")}
    assert get(dsk, "z") == 3


def test_get_lista_de_chaves_devolve_tupla_na_mesma_ordem():
    """Mata mutante que troque a ordem de _pack_result ao montar a tupla de saída."""
    dsk = {"x": 1, "y": (inc, "x")}
    assert get(dsk, ["y", "x"]) == (2, 1)


def test_get_chave_ausente_levanta_key_error():
    with pytest.raises(KeyError):
        get({"x": 1}, "y")


# --------------------------------------------------------------------------
# get_dependencies / get_deps
# --------------------------------------------------------------------------


def test_get_dependencies_ignora_valores_que_nao_sao_chaves():
    dsk = {"x": 1, "a": (add, (inc, "x"), 1)}
    assert get_dependencies(dsk, "a") == {"x"}


def test_get_dependencies_de_valor_literal_e_vazio():
    dsk = {"x": 1}
    assert get_dependencies(dsk, "x") == set()


def test_get_dependencies_sem_key_nem_task_levanta_value_error():
    with pytest.raises(ValueError):
        get_dependencies({"x": 1})


def test_get_deps_monta_dependencies_e_dependents():
    dsk = {"a": 1, "b": (inc, "a"), "c": (inc, "b")}
    dependencies, dependents = get_deps(dsk)
    assert dependencies == {"a": set(), "b": {"a"}, "c": {"b"}}
    assert dependents == {"a": {"b"}, "b": {"c"}, "c": set()}


# --------------------------------------------------------------------------
# flatten / reverse_dict
# --------------------------------------------------------------------------


def test_flatten_aninhado():
    assert list(flatten([[1, [2, 3]], [4]])) == [1, 2, 3, 4]


def test_flatten_nao_desmancha_tuplas():
    """Mata mutante que troque o container padrão de list para (list, tuple)."""
    assert list(flatten([(1, 2), (3, 4)])) == [(1, 2), (3, 4)]


def test_flatten_string_e_tratada_como_atomo_nao_iteravel():
    assert list(flatten("abc")) == ["abc"]


def test_reverse_dict_inverte_as_arestas():
    d = {"a": ["b", "c"], "b": ["c"]}
    assert reverse_dict(d) == {"a": set(), "b": {"a"}, "c": {"a", "b"}}


# --------------------------------------------------------------------------
# subs -- substituição dentro de uma tarefa
# --------------------------------------------------------------------------


def test_subs_substitui_chave_por_valor_em_tarefa_simples():
    assert subs((inc, "x"), "x", 5) == (inc, 5)


def test_subs_substitui_recursivamente_em_tarefas_aninhadas():
    tarefa = (add, (inc, "x"), "x")
    assert subs(tarefa, "x", 10) == (add, (inc, 10), 10)


def test_subs_em_valor_nao_tarefa_que_bate_com_a_chave():
    assert subs("x", "x", 99) == 99


def test_subs_dentro_de_lista():
    assert subs(["x", "y"], "x", 1) == [1, "y"]


# --------------------------------------------------------------------------
# getcycle / isdag -- detecção de ciclos
#
# toposort() não tem teste aqui: nenhuma das 177 pastas tests/ do
# repositório (em nenhum nível, direto ou indireto) exercita essa função
# -- mantê-la só poluiria a comparação com um ponto sem par possível.
# --------------------------------------------------------------------------


def test_isdag_verdadeiro_para_grafo_aciclico():
    dsk = {"x": 0, "y": (inc, "x")}
    assert isdag(dsk, "y") is True


def test_isdag_falso_para_grafo_com_ciclo():
    """Mata mutante que inverta a lógica de detecção de ciclo em isdag."""
    dsk = {"x": (inc, "y"), "y": (inc, "x")}
    assert isdag(dsk, "y") is False


def test_getcycle_devolve_a_cadeia_do_ciclo():
    dsk = {"x": (inc, "z"), "y": (inc, "x"), "z": (inc, "y")}
    ciclo = getcycle(dsk, "x")
    assert ciclo[0] == ciclo[-1]  # fecha o laço
    assert set(ciclo) == {"x", "y", "z"}


def test_getcycle_vazio_quando_nao_ha_ciclo():
    dsk = {"x": 0, "y": (inc, "x")}
    assert getcycle(dsk, "y") == []


# --------------------------------------------------------------------------
# literal / quote
# --------------------------------------------------------------------------


def test_literal_e_chamavel_e_devolve_o_dado_original():
    lit = literal([1, 2, 3])
    assert lit() == [1, 2, 3]


def test_quote_protege_uma_tarefa_de_ser_interpretada_como_tal():
    """Mata mutante que remova a checagem istask()/list/dict em quote()."""
    tarefa_quotada = quote((add, 1, 2))
    assert len(tarefa_quotada) == 1
    assert tarefa_quotada[0]() == (add, 1, 2)


def test_quote_nao_afeta_valores_comuns():
    assert quote(5) == 5
    assert quote("texto") == "texto"


# --------------------------------------------------------------------------
# reshapelist
# --------------------------------------------------------------------------


def test_reshapelist_organiza_sequencia_plana_em_blocos():
    assert reshapelist((2, 3), list(range(6))) == [[0, 1, 2], [3, 4, 5]]


def test_reshapelist_uma_dimensao_devolve_lista_simples():
    assert reshapelist((5,), list(range(5))) == [0, 1, 2, 3, 4]
