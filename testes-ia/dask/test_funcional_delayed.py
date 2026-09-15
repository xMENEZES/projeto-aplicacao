"""
Testes funcionais (caixa-preta) de dask.delayed -- a API pública mais usada
do Dask para paralelizar código Python genérico. Só interessa aqui o
comportamento observável (laziness, encadeamento, compute), não a
implementação interna da classe Delayed.

Reescrito do zero em 2026-09-10: os três arquivos que originalmente
completavam esta pasta (este, o de integração e o de aceitação) foram
apagados e recriados sem reaproveitar nada do código anterior, para
eliminar qualquer chance de resíduo de um incidente em que o pytest
chegou a coletar e rodar por alguns segundos a suíte de testes humana do
Dask (sem exibir conteúdo dela -- só símbolos de passou/pulou) antes de
ser interrompido. Cada comportamento abaixo foi reconfirmado por execução
direta antes de virar teste, do mesmo jeito que a v2 já fazia.
"""

from __future__ import annotations

import dask
from dask import delayed


def test_delayed_e_lazy_a_funcao_so_roda_no_compute():
    chamadas = []

    @delayed
    def rastreado(x):
        chamadas.append(x)
        return x

    atraso = rastreado(1)
    assert chamadas == []  # nada rodou ainda
    resultado = atraso.compute()
    assert chamadas == [1]
    assert resultado == 1


def test_delayed_encadeia_chamadas_e_computa_o_resultado_final():
    @delayed
    def inc(x):
        return x + 1

    @delayed
    def soma(a, b):
        return a + b

    grafo = soma(inc(1), inc(2))
    assert grafo.compute() == 5


def test_delayed_de_valor_simples_computa_para_o_proprio_valor():
    assert delayed(42).compute() == 42


def test_dask_compute_em_lote_executa_subtarefa_compartilhada_uma_unica_vez():
    """Duas saídas que dependem da mesma tarefa de base, computadas juntas
    via dask.compute(), não devem recalcular essa base duas vezes."""
    chamadas = []

    @delayed
    def base():
        chamadas.append("base")
        return 10

    @delayed
    def inc(x):
        return x + 1

    @delayed
    def dobro(x):
        return x * 2

    b = base()
    resultado = dask.compute(inc(b), dobro(b))

    assert resultado == (11, 20)
    assert chamadas == ["base"]


def test_delayed_pure_true_produz_a_mesma_chave_para_a_mesma_chamada():
    @delayed(pure=True)
    def inc(x):
        return x + 1

    assert inc(5).key == inc(5).key


def test_delayed_sem_pure_produz_chaves_diferentes_por_chamada():
    @delayed
    def inc(x):
        return x + 1

    assert inc(5).key != inc(5).key


def test_delayed_acesso_a_atributo_de_objeto_tambem_e_lazy():
    class Config:
        valor = 99

    atraso_do_atributo = delayed(Config()).valor
    assert atraso_do_atributo.compute() == 99


def test_delayed_indexacao_tambem_e_lazy():
    assert delayed([10, 20, 30])[1].compute() == 20


def test_delayed_com_nout_permite_desempacotar_em_variaveis_separadas():
    @delayed(nout=2)
    def divide_em_duas_partes(par):
        return par[0], par[1]

    primeira, segunda = divide_em_duas_partes((1, 2))
    assert primeira.compute() == 1
    assert segunda.compute() == 2
