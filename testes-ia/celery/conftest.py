"""
Configuração compartilhada da suíte de testes do Celery.

1. Garante que `import celery` resolva para a cópia exata do código-fonte
   clonado em `repositorios-originais/celery` (versão 5.6.2), não para qualquer instalação
   via pip que porventura já exista no ambiente.

2. Fornece um app Celery real, mas isolado, para cada teste -- usando o
   transporte de broker `memory://` (em processo, do próprio kombu) e o
   backend de resultado `cache+memory://`. Nenhum teste desta suíte depende
   de Redis, RabbitMQ ou qualquer serviço externo: tudo roda dentro do
   próprio processo do pytest.

3. Para os testes de integração/aceitação, que rodam um worker embutido de
   verdade (via `celery.contrib.testing.worker.start_worker`), o pool é
   forçado para `solo` -- o pool `prefork` padrão do Celery depende de
   `os.fork()`, que não existe no Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# --- 1. Garantir que estamos testando o código-fonte clonado ---------------

REPO_SRC = str(Path(__file__).parent.parent.parent / "repositorios-originais" / "celery")
sys.path.insert(0, REPO_SRC)

import celery  # noqa: E402

assert celery.__version__ == "5.6.2", (
    f"Esperava testar celery 5.6.2 (o checkout clonado), mas 'import celery' "
    f"resolveu para a versão {celery.__version__} em {celery.__file__!r}."
)

from celery.contrib.testing.app import TestApp, setup_default_app  # noqa: E402


@pytest.fixture
def celery_app():
    """Um app Celery real, com broker e backend em memória, isolado por
    teste. Usa `celery.contrib.testing.app.TestApp`, utilitário de produção
    do próprio pacote (não um arquivo de teste do repositório) desenhado
    exatamente para este propósito."""
    app = TestApp(set_as_current=False)
    with setup_default_app(app):
        yield app


@pytest.fixture
def eager_app(celery_app):
    """Variante configurada para executar tarefas de forma síncrona/eager --
    útil para os testes estruturais e funcionais, que não precisam de um
    worker real."""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.task_store_eager_result = True
    return celery_app
