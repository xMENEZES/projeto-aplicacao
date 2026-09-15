"""
Testes de aceitação: histórias de usuário, no vocabulário de quem usa o
Dask para paralelizar um pipeline de processamento em Python puro -- não
de quem implementa o motor de grafos. Todos rodam contra schedulers reais
(threaded/síncrono), sem numpy/pandas, só delayed + funções Python comuns.

Reescrito do zero em 2026-09-10 (ver nota em test_funcional_delayed.py).
"""

from __future__ import annotations

import threading

import pytest

import dask
from dask import compute, delayed


def test_desenvolvedor_paraleliza_um_pipeline_sem_reescrever_a_logica():
    """Como desenvolvedor, quero pegar um pipeline sequencial comum
    (buscar -> transformar -> agregar) e paralelizar as partes
    independentes só decorando as funções com @delayed, sem reescrever a
    lógica de negócio em si."""

    @delayed
    def buscar(fonte):
        return {"a": 1, "b": 2, "c": 3}[fonte]

    @delayed
    def transformar(valor):
        return valor * 10

    @delayed
    def agregar(*valores):
        return sum(valores)

    transformados = [transformar(buscar(f)) for f in ["a", "b", "c"]]
    total = agregar(*transformados)

    assert total.compute() == 60  # (1+2+3)*10


def test_desenvolvedor_computa_varios_resultados_sem_recalcular_o_que_e_comum():
    """Como desenvolvedor, quero pedir vários resultados finais de uma vez
    (dask.compute(a, b, c)) e ter certeza de que qualquer trabalho
    compartilhado entre eles roda uma única vez, sem eu precisar
    gerenciar isso manualmente com cache ou memoization."""
    chamadas_ao_banco = []

    @delayed
    def consulta_pesada_ao_banco():
        chamadas_ao_banco.append(1)
        return list(range(100))

    @delayed
    def soma(dados):
        return sum(dados)

    @delayed
    def media(dados):
        return sum(dados) / len(dados)

    dados = consulta_pesada_ao_banco()
    total, media_valor = compute(soma(dados), media(dados))

    assert total == sum(range(100))
    assert media_valor == sum(range(100)) / 100
    assert len(chamadas_ao_banco) == 1


def test_desenvolvedor_troca_o_scheduler_sem_mudar_o_pipeline():
    """Como desenvolvedor, quero poder trocar entre rodar em threads
    (produção) ou de forma síncrona (debugging passo a passo) só mudando
    uma configuração, sem tocar no código do pipeline em si."""

    @delayed
    def inc(x):
        return x + 1

    pipeline = inc(inc(inc(1)))

    assert pipeline.compute(scheduler="threads") == 4
    assert pipeline.compute(scheduler="synchronous") == 4


def test_desenvolvedor_confia_que_erros_de_uma_etapa_nao_ficam_silenciosos():
    """Como desenvolvedor, quero que uma falha em qualquer etapa do
    pipeline pare o compute() e me devolva a exceção original, em vez de
    um resultado parcial ou silenciosamente incompleto."""

    @delayed
    def divide(a, b):
        return a / b

    with pytest.raises(ZeroDivisionError):
        divide(10, 0).compute()


def test_desenvolvedor_isola_uma_configuracao_customizada_a_um_trecho_do_codigo():
    """Como desenvolvedor, quero poder aplicar uma configuração especial
    (ex.: forçar um scheduler específico) só para um trecho do meu
    código, sem afetar o resto do programa depois que aquele trecho
    termina."""
    thread_ids = set()

    @delayed
    def registra(x):
        thread_ids.add(threading.get_ident())
        return x

    with dask.config.set(scheduler="synchronous"):
        registra(1).compute()
    configuracao_depois_do_bloco = dask.config.get("scheduler", None)

    assert thread_ids == {threading.get_ident()}
    assert configuracao_depois_do_bloco != "synchronous"
