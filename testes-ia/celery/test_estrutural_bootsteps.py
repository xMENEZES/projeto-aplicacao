"""
Testes estruturais (caixa-branca) de celery/bootsteps.py -- o Blueprint e os
Step/StartStopStep/ConsumerStep que organizam a inicialização do worker como
um grafo de dependências. Nada aqui depende de broker, worker real ou
reactor: Blueprint.apply() só monta e ordena objetos Python.
"""

from __future__ import annotations

from celery.bootsteps import Blueprint, StartStopStep, Step


class _ObjetoQualquer:
    """Parent genérico o suficiente para Blueprint.apply() funcionar --
    só precisa aceitar um atributo `.steps` de lista."""

    def __init__(self):
        self.steps = []


# `requires` é resolvido via kombu.utils.imports.symbol_by_name, que trata
# cada item como um caminho de import ("modulo:Atributo") -- por isso as
# classes de Step usadas nos testes de dependência precisam viver no nível
# do módulo (não dentro da função de teste) e serem referenciadas pelo seu
# caminho totalmente qualificado, exatamente como o próprio Celery faz em
# `ConsumerStep.requires = ('celery.worker.consumer:Connection',)`.

ORDEM_DE_CRIACAO: list[str] = []
ORDEM_DE_BOOT: list[str] = []


class _StepA(Step):
    name = "testes.A"

    def __init__(self, parent, **kwargs):
        ORDEM_DE_CRIACAO.append("A")


class _StepB(Step):
    name = "testes.B"
    requires = (f"{__name__}:_StepA",)

    def __init__(self, parent, **kwargs):
        ORDEM_DE_CRIACAO.append("B")


class _StepC(Step):
    name = "testes.C"
    requires = (f"{__name__}:_StepB",)

    def __init__(self, parent, **kwargs):
        ORDEM_DE_CRIACAO.append("C")


class _StepPrimeiro(StartStopStep):
    """Precisa ser StartStopStep, não Step puro: Blueprint.start() itera
    `parent.steps`, e só StartStopStep.include() de fato registra o step
    ali (`parent.steps.append(self)`) -- um Step comum participa do grafo
    de criação, mas nunca do ciclo start/stop dessa forma."""

    name = "testes.primeiro"

    def start(self, parent):
        ORDEM_DE_BOOT.append("primeiro")


class _StepSegundo(StartStopStep):
    name = "testes.segundo"
    requires = (f"{__name__}:_StepPrimeiro",)

    def start(self, parent):
        ORDEM_DE_BOOT.append("segundo")


# --------------------------------------------------------------------------
# Ordenação por dependência (requires)
# --------------------------------------------------------------------------


def test_blueprint_ordena_steps_respeitando_requires():
    """Mata mutante que remova ou inverta o topsort do grafo de dependências."""
    ORDEM_DE_CRIACAO.clear()
    parent = _ObjetoQualquer()
    # Propositalmente fora de ordem na declaração -- o Blueprint deve
    # reordenar de acordo com requires, não com a ordem da lista.
    blueprint = Blueprint(steps=[_StepC, _StepA, _StepB])
    blueprint.apply(parent)

    assert ORDEM_DE_CRIACAO == ["A", "B", "C"]


def test_blueprint_start_executa_steps_na_ordem_de_boot():
    ORDEM_DE_BOOT.clear()
    parent = _ObjetoQualquer()
    blueprint = Blueprint(steps=[_StepSegundo, _StepPrimeiro])
    blueprint.apply(parent)
    blueprint.start(parent)

    assert ORDEM_DE_BOOT == ["primeiro", "segundo"]


# --------------------------------------------------------------------------
# include_if / enabled -- steps condicionais
# --------------------------------------------------------------------------


def test_step_desabilitado_nao_e_incluido_no_boot():
    """Mata mutante que troque include_if para sempre retornar True."""

    class StepDesabilitado(Step):
        name = "testes.desabilitado"
        enabled = False

    parent = _ObjetoQualquer()
    blueprint = Blueprint(steps=[StepDesabilitado])
    blueprint.apply(parent)

    step = blueprint.steps["testes.desabilitado"]
    assert step.include(parent) is False


def test_step_habilitado_e_incluido_no_boot():
    class StepHabilitado(Step):
        name = "testes.habilitado"

    parent = _ObjetoQualquer()
    blueprint = Blueprint(steps=[StepHabilitado])
    blueprint.apply(parent)

    step = blueprint.steps["testes.habilitado"]
    assert step.include(parent) is True


# --------------------------------------------------------------------------
# StartStopStep -- ciclo de vida start/stop delegado ao objeto criado
# --------------------------------------------------------------------------


def test_start_stop_step_delega_start_e_stop_ao_objeto_criado():
    eventos = []

    class ServicoFake:
        def start(self):
            eventos.append("start")

        def stop(self):
            eventos.append("stop")

    class StepDeServico(StartStopStep):
        name = "testes.servico"

        def create(self, parent):
            return ServicoFake()

    parent = _ObjetoQualquer()
    blueprint = Blueprint(steps=[StepDeServico])
    blueprint.apply(parent)
    step = blueprint.steps["testes.servico"]
    step.include(parent)  # cria o objeto e registra em parent.steps

    assert isinstance(step.obj, ServicoFake)
    step.start(parent)
    step.stop(parent)
    assert eventos == ["start", "stop"]


def test_start_stop_step_sem_objeto_nao_levanta_ao_parar():
    """Mata mutante que remova a checagem 'if self.obj' antes de chamar stop()."""

    class StepSemObjeto(StartStopStep):
        name = "testes.sem-objeto"

    parent = _ObjetoQualquer()
    blueprint = Blueprint(steps=[StepSemObjeto])
    blueprint.apply(parent)
    step = blueprint.steps["testes.sem-objeto"]

    assert step.stop(parent) is None  # não levanta, mesmo sem self.obj


def test_start_stop_step_terminate_usa_terminate_ou_stop_como_fallback():
    eventos = []

    class ServicoSemTerminate:
        def start(self):
            pass

        def stop(self):
            eventos.append("stop-usado-como-fallback")

    class StepDeServico(StartStopStep):
        name = "testes.servico-sem-terminate"

        def create(self, parent):
            return ServicoSemTerminate()

    parent = _ObjetoQualquer()
    blueprint = Blueprint(steps=[StepDeServico])
    blueprint.apply(parent)
    step = blueprint.steps["testes.servico-sem-terminate"]
    step.include(parent)
    step.terminate(parent)

    assert eventos == ["stop-usado-como-fallback"]


# --------------------------------------------------------------------------
# Blueprint.state / human_state
# --------------------------------------------------------------------------


def test_blueprint_human_state_reflete_o_ciclo_de_vida():
    parent = _ObjetoQualquer()
    blueprint = Blueprint(steps=[])
    blueprint.apply(parent)
    assert blueprint.human_state() == "initializing"
    blueprint.start(parent)
    assert blueprint.human_state() == "running"
    blueprint.stop(parent)
    assert blueprint.human_state() == "terminating"
