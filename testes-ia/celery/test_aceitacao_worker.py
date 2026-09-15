"""
Testes de aceitação: histórias de usuário, no vocabulário de quem usa o
Celery para tirar trabalho pesado do caminho síncrono de uma aplicação.
Todos rodam contra um worker embutido real (broker `memory://`).
"""

from __future__ import annotations

import pytest

from celery.contrib.testing.worker import start_worker


def test_desenvolvedor_manda_trabalho_para_segundo_plano_e_busca_o_resultado_depois(
    celery_app,
):
    """Como desenvolvedor, quero disparar uma tarefa pesada com .delay() e
    seguir com o resto do meu código, buscando o resultado só quando
    precisar dele -- sem bloquear a chamada original."""

    @celery_app.task
    def processamento_pesado(n):
        return sum(range(n))

    with start_worker(celery_app, perform_ping_check=False):
        promessa = processamento_pesado.delay(1000)
        # ... o "resto do código" aconteceria aqui ...
        assert promessa.get(timeout=10) == sum(range(1000))


def test_desenvolvedor_encadeia_etapas_de_processamento_sem_gerenciar_a_ordem_manualmente(
    celery_app,
):
    """Como desenvolvedor, quero descrever um pipeline de etapas (buscar ->
    transformar -> salvar) como uma composição declarativa, sem escrever
    o código de 'chamar a próxima etapa' eu mesmo."""

    @celery_app.task
    def buscar_numero():
        return 21

    @celery_app.task
    def dobrar(x):
        return x * 2

    @celery_app.task
    def formatar(x):
        return f"resultado final: {x}"

    with start_worker(celery_app, perform_ping_check=False):
        pipeline = buscar_numero.s() | dobrar.s() | formatar.s()
        assert pipeline.delay().get(timeout=10) == "resultado final: 42"


def test_desenvolvedor_dispara_varias_tarefas_independentes_de_uma_vez(celery_app):
    """Como desenvolvedor, quero disparar N tarefas independentes (ex.:
    enviar um e-mail para cada usuário de uma lista) e esperar todas
    terminarem, sem escrever um loop manual de 'esperar uma por vez'."""
    from celery import group

    @celery_app.task
    def notificar(usuario_id):
        return f"notificado:{usuario_id}"

    with start_worker(celery_app, perform_ping_check=False):
        tarefas = group(notificar.s(uid) for uid in (1, 2, 3))
        resultado = tarefas.apply_async()
        assert sorted(resultado.get(timeout=10)) == [
            "notificado:1",
            "notificado:2",
            "notificado:3",
        ]


def test_desenvolvedor_deixa_o_celery_tentar_de_novo_sozinho_apos_uma_falha_transitoria(
    celery_app,
):
    """Como desenvolvedor, quero que uma falha transitória (ex.: um serviço
    externo fora do ar por um instante) seja resolvida automaticamente por
    algumas tentativas, sem eu escrever um laço de retry manual."""
    chamadas = []

    @celery_app.task(bind=True, max_retries=4)
    def chamar_servico_externo_instavel(self):
        chamadas.append(1)
        if len(chamadas) < 3:
            raise self.retry(exc=ConnectionError("serviço fora do ar"), countdown=0)
        return "resposta do serviço"

    with start_worker(celery_app, perform_ping_check=False):
        resultado = chamar_servico_externo_instavel.delay()
        assert resultado.get(timeout=10) == "resposta do serviço"


def test_desenvolvedor_recebe_o_erro_original_quando_a_tarefa_falha_definitivamente(
    celery_app,
):
    """Como desenvolvedor, quero que uma falha real (não transitória) chegue
    até mim como a mesma exceção que o código da tarefa levantou, para eu
    poder tratá-la (ou deixar subir) do jeito que eu trataria qualquer
    outra exceção Python."""

    @celery_app.task
    def valida_idade(idade):
        if idade < 0:
            raise ValueError(f"idade inválida: {idade}")
        return idade

    with start_worker(celery_app, perform_ping_check=False):
        resultado = valida_idade.delay(-5)
        with pytest.raises(ValueError, match="idade inválida: -5"):
            resultado.get(timeout=10)
