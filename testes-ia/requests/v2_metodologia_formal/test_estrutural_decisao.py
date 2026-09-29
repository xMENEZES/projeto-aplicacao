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

ATUALIZAÇÃO: a seção 4 (rebuild_method) foi reescrita para exercitar o
método através de redirecionamentos reais contra o servidor local
(conftest.py::live_server), em vez de chamar `s.rebuild_method(p, r)`
isolado com objetos PreparedRequest/Response fabricados à mão. Motivo:
a suíte humana do Requests nunca chama rebuild_method diretamente em
nenhum nível -- só o observa indiretamente, através do método final da
requisição que efetivamente chegou ao destino após seguir o redirect
(resp.request.method). Testar a função isolada, do jeito que a v2
original fazia, não tem correspondente humano possível e mediria uma
via de acesso que nenhum consumidor real (nem os próprios mantenedores)
usa. As 7 regras da tabela de decisão continuam cobertas, uma por
requisição real, não por chamada direta.
"""

from __future__ import annotations

import pytest

import requests
from requests.sessions import Session


# ==========================================================================
# Seção 4 do plano — rebuild_method (status de redirect × método original),
# agora observado via redirect real contra o servidor local
# ==========================================================================


def test_rebuild_method_ct19_redirect_303_preserva_head(live_server):
    """CT19 — R1: redirect 303 é a única exceção que preserva HEAD."""
    resp = requests.head(f"{live_server}/redirect-303-see-other")
    assert resp.request.method == "HEAD"


def test_rebuild_method_ct20_redirect_303_converte_put_em_get(live_server):
    """CT20 — R2: redirect 303 converte qualquer outro método (aqui PUT) em GET."""
    resp = requests.put(f"{live_server}/redirect-303-see-other", data={"x": "1"})
    assert resp.request.method == "GET"


def test_rebuild_method_ct21_redirect_302_converte_post_em_get(live_server):
    """CT21 — R3: redirect 302 converte POST em GET."""
    resp = requests.post(f"{live_server}/redirect/1", data={"x": "1"})
    assert resp.request.method == "GET"


def test_rebuild_method_ct22_redirect_302_com_get_nao_muda_metodo(live_server):
    """CT22 — R4: redirect 302 com GET original não altera o método (caso trivial)."""
    resp = requests.get(f"{live_server}/redirect/1")
    assert resp.request.method == "GET"


def test_rebuild_method_ct23_redirect_301_converte_post_em_get(live_server):
    """CT23 — R5: redirect 301 converte POST em GET."""
    resp = requests.post(f"{live_server}/redirect-301-permanent", data={"x": "1"})
    assert resp.request.method == "GET"


def test_rebuild_method_ct24_redirect_301_preserva_metodo_nao_post(live_server):
    """CT24 — R6: redirect 301 preserva métodos que não são POST (aqui PATCH)."""
    resp = requests.patch(f"{live_server}/redirect-301-permanent", data={"x": "1"})
    assert resp.request.method == "PATCH"


def test_rebuild_method_ct25_redirect_307_preserva_metodo_e_corpo(live_server):
    """CT25 — R7: redirect 307 sempre preserva método e corpo originais (aqui POST)."""
    resp = requests.post(f"{live_server}/redirect-307-temporary", data={"x": "1"})
    assert resp.request.method == "POST"


def test_rebuild_method_ct26_redirect_308_preserva_metodo_e_corpo(live_server):
    """CT26 — R7: redirect 308 sempre preserva método e corpo originais (aqui POST)."""
    resp = requests.post(f"{live_server}/redirect-308-permanent-preserva", data={"x": "1"})
    assert resp.request.method == "POST"


# ==========================================================================
# Seção 5 do plano — should_strip_auth (host × esquema × porta)
# ==========================================================================
#
# should_strip_auth continua chamado isolado, direto na Session: é assim
# que a própria suíte humana do Requests testa esse método (ver
# test_should_strip_auth_host_change e vizinhos em tests/test_requests.py),
# então não há ajuste de "via de acesso" a fazer aqui.


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
