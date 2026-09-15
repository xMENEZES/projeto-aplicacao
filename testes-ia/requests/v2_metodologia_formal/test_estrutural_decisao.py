"""
v2 — técnica estrutural (caixa-branca) via tabela de decisão: cada teste
aqui corresponde a uma REGRA de uma tabela de decisão do PLANO_DE_TESTE.md
(seções 4 e 5) -- ou seja, a uma combinação específica de condições que
juntas decidem o resultado, não a uma condição isolada.

A seção 2 do plano (prepare_content_length) foi removida desta suíte:
sem nenhuma evidência humana, direta ou indireta, e sem via pública para
observar o Content-Length calculado a não ser inspecionando esse header
interno diretamente, não existe um teste humano equivalente possível em
nenhum nível de abstração -- mantê-la só poluiria a comparação.
"""

from __future__ import annotations

import pytest

from requests.models import PreparedRequest, Response
from requests.sessions import Session
from requests.status_codes import codes


# ==========================================================================
# Seção 4 do plano — rebuild_method (status de redirect × método original)
# ==========================================================================


def _prepared(method):
    p = PreparedRequest()
    p.method = method
    return p


def _resposta(status_code):
    r = Response()
    r.status_code = status_code
    return r


@pytest.mark.parametrize(
    "id_caso, regra, status, metodo_original, metodo_esperado",
    [
        ("CT19", "R1", codes.see_other, "HEAD", "HEAD"),
        ("CT20", "R2", codes.see_other, "PUT", "GET"),
        ("CT21", "R3", codes.found, "POST", "GET"),
        ("CT22", "R4", codes.found, "GET", "GET"),
        ("CT23", "R5", codes.moved, "POST", "GET"),
        ("CT24", "R6", codes.moved, "PATCH", "PATCH"),
        ("CT25", "R7", 307, "POST", "POST"),
        ("CT26", "R7", 308, "POST", "POST"),
    ],
)
def test_rebuild_method_tabela_de_decisao(id_caso, regra, status, metodo_original, metodo_esperado):
    """CT19–CT26 — as 7 regras da tabela de decisão status × método.

    Cobre as 4 arestas de decisão da função (if 303..., if 302 and POST,
    if 301 and POST, else preserva) -- critério "todas-arestas" do grafo
    de fluxo de controle de rebuild_method, não só "todos-nós".
    """
    s = Session()
    p = _prepared(metodo_original)
    r = _resposta(status)
    s.rebuild_method(p, r)
    assert p.method == metodo_esperado


# ==========================================================================
# Seção 5 do plano — should_strip_auth (host × esquema × porta)
# ==========================================================================


@pytest.mark.parametrize(
    "id_caso, regra, url_original, url_novo, remove_esperado",
    [
        ("CT27", "R1", "http://x.com/a", "http://x.com/b", False),
        ("CT28", "R2", "http://x.com/a", "http://y.com/a", True),
        ("CT29", "R3", "http://x.com/a", "https://x.com/a", False),
        ("CT30", "R4", "http://x.com:8080/a", "http://x.com:9090/a", True),
    ],
)
def test_should_strip_auth_tabela_de_decisao(id_caso, regra, url_original, url_novo, remove_esperado):
    """CT27–CT30 — as 4 regras da tabela de decisão de remoção de credenciais
    num redirecionamento. R2 e R4 são as duas arestas "perigosas": sem
    elas, credenciais vazariam para um host ou porta diferentes."""
    s = Session()
    assert s.should_strip_auth(url_original, url_novo) is remove_esperado
