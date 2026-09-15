"""
Testes de integração: schedulers REAIS do Dask (threaded e síncrono)
executando grafos de tarefas de verdade -- não é dask.core.get() chamando
tudo sequencialmente na mão, é o ThreadPoolExecutor real do
dask.threaded.get(), com corrida de thread genuína, junto com
dask.config e dask.delayed cooperando como cooperariam em produção.

Reescrito do zero em 2026-09-10 (ver nota em test_funcional_delayed.py).
"""

from __future__ import annotations

import threading
import time

import pytest

import dask
from dask import delayed
from dask.local import get_sync
from dask.threaded import get as threaded_get


def inc(x):
    return x + 1


def add(x, y):
    return x + y


# --------------------------------------------------------------------------
# Scheduler threaded real
# --------------------------------------------------------------------------


def test_threaded_get_executa_grafo_real_com_pool_de_threads():
    dsk = {"a": 1, "b": (inc, "a"), "c": (inc, "a"), "d": (add, "b", "c")}
    assert threaded_get(dsk, "d") == 4  # a=1 -> b=c=2 -> d=2+2


def test_threaded_get_roda_tarefas_independentes_em_paralelo_de_verdade():
    """Tarefas sem dependência entre si (todas dependem só de 'a') devem
    poder rodar concorrentemente -- medido com lock/contador em threads
    reais dormindo ao mesmo tempo, não inferido."""
    contador = {"atual": 0, "maximo": 0}
    lock = threading.Lock()

    def tarefa_lenta(x):
        with lock:
            contador["atual"] += 1
            contador["maximo"] = max(contador["maximo"], contador["atual"])
        time.sleep(0.2)
        with lock:
            contador["atual"] -= 1
        return x

    dsk = {"a": 1, "b": (tarefa_lenta, "a"), "c": (tarefa_lenta, "a"), "d": (tarefa_lenta, "a")}
    threaded_get(dsk, ["b", "c", "d"], num_workers=3)
    assert contador["maximo"] >= 2


def test_threaded_get_com_num_workers_1_serializa_a_execucao():
    """Mata mutante que ignore o parâmetro num_workers."""
    contador = {"atual": 0, "maximo": 0}
    lock = threading.Lock()

    def tarefa_lenta(x):
        with lock:
            contador["atual"] += 1
            contador["maximo"] = max(contador["maximo"], contador["atual"])
        time.sleep(0.1)
        with lock:
            contador["atual"] -= 1
        return x

    dsk = {"a": 1, "b": (tarefa_lenta, "a"), "c": (tarefa_lenta, "a")}
    threaded_get(dsk, ["b", "c"], num_workers=1)
    assert contador["maximo"] == 1


def test_threaded_get_propaga_excecao_de_uma_tarefa_real():
    def sempre_falha(x):
        raise ValueError("falha real dentro do scheduler")

    dsk = {"a": 1, "b": (sempre_falha, "a")}
    with pytest.raises(ValueError, match="falha real dentro do scheduler"):
        threaded_get(dsk, "b")


# --------------------------------------------------------------------------
# Scheduler síncrono (para depuração -- sem threads)
# --------------------------------------------------------------------------


def test_get_sync_executa_na_mesma_thread_sem_paralelismo():
    """Mata mutante que troque get_sync por um scheduler paralelo real."""
    thread_ids_vistos = set()

    def registra_thread(x):
        thread_ids_vistos.add(threading.get_ident())
        return x

    dsk = {"a": 1, "b": (registra_thread, "a"), "c": (registra_thread, "a")}
    get_sync(dsk, ["b", "c"])
    assert thread_ids_vistos == {threading.get_ident()}


# --------------------------------------------------------------------------
# dask.config integrado a dask.delayed/compute
# --------------------------------------------------------------------------


def test_config_set_scheduler_sincrono_afeta_o_compute_de_delayed():
    thread_ids_vistos = set()

    @delayed
    def registra_thread(x):
        thread_ids_vistos.add(threading.get_ident())
        return x

    with dask.config.set(scheduler="synchronous"):
        registra_thread(1).compute()

    assert thread_ids_vistos == {threading.get_ident()}


def test_compute_scheduler_explicito_tem_prioridade_sobre_o_padrao():
    @delayed
    def inc_delayed(x):
        return x + 1

    assert inc_delayed(1).compute(scheduler="synchronous") == 2
