"""
Configuração compartilhada da suíte de testes do Dask.

Garante que `import dask` resolva para a cópia exata do código-fonte
clonado em `repositorios-originais/dask/` -- este checkout não tem um `_version.py` gerado
(a versão é calculada em build-time via setuptools_scm, e o clone é raso,
sem tags), então em vez de comparar `dask.__version__` (que cairia no
fallback "unknown", perdendo o sentido da checagem), confirmamos que
`dask.__file__` está de fato dentro de `repositorios-originais/dask/`, o que garante a mesma
coisa: estamos testando o checkout clonado, não uma cópia qualquer do
Dask que porventura já esteja instalada no ambiente.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_SRC = Path(__file__).parent.parent.parent / "repositorios-originais" / "dask"
sys.path.insert(0, str(REPO_SRC))

import dask  # noqa: E402

_dask_file = Path(dask.__file__).resolve()
_repo_src = REPO_SRC.resolve()
assert _repo_src in _dask_file.parents, (
    f"Esperava testar o checkout clonado em {_repo_src}, mas 'import dask' "
    f"resolveu para {_dask_file!r} -- fora dessa pasta."
)
