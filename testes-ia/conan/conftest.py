"""
Configuração compartilhada da suíte de testes do Conan.

Garante que `import conan` resolva para a cópia exata do código-fonte
clonado em `repositorios-originais/conan` (versão 2.32.0-dev), e disponibiliza um atalho
para `conan.test.utils.tools.TestClient` -- o utilitário de testes que o
próprio Conan distribui dentro do pacote (não é a suíte interna do
repositório, que vive em `test/` na raiz e não foi tocada) para que
QUALQUER pessoa escrevendo receitas Conan possa testá-las: ele cria um
cache (`.conan2`) e uma pasta de trabalho totalmente isolados e temporários
por instância, e sabe rodar a CLI do Conan (`conan create`, `conan install`
etc.) de ponta a ponta dentro do próprio processo de teste, sem precisar de
um compilador C/C++ real -- desde que as receitas de teste não peçam de
fato para compilar nada (o que é o caso de todas as receitas desta suíte:
são pacotes "header-only" ou com build() vazio).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_SRC = str(Path(__file__).parent.parent.parent / "repositorios-originais" / "conan")
sys.path.insert(0, REPO_SRC)

import conan  # noqa: E402

assert conan.__version__ == "2.32.0-dev", (
    f"Esperava testar conan 2.32.0-dev (o checkout clonado), mas 'import conan' "
    f"resolveu para a versão {conan.__version__} em {conan.__file__!r}."
)

from conan.test.utils.tools import TestClient  # noqa: E402


@pytest.fixture
def client():
    """Um TestClient novo e isolado (cache + pasta de trabalho próprios,
    em diretórios temporários) para cada teste."""
    return TestClient(light=True)
