"""
v2 — técnica estrutural via tabela de decisão: RedirectMiddleware (guardas,
troca de verbo, remoção de Cookie/Authorization) e RetryMiddleware. Cada
teste corresponde a uma regra nomeada do PLANO_DE_TESTE.md (seções 1-3).
Reaproveita a fixture `crawler_factory` do conftest.py da pasta-mãe.
"""

from __future__ import annotations

import pytest

from scrapy import Request
from scrapy.downloadermiddlewares.redirect import RedirectMiddleware
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Response


# ==========================================================================
# Seção 1 — guardas de RedirectMiddleware.process_response
# ==========================================================================


def test_ct01_guarda_g1_dont_redirect_impede_redirecionamento(crawler_factory):
    mw = RedirectMiddleware.from_crawler(crawler_factory())
    req = Request("http://x.com/", meta={"dont_redirect": True})
    resp = Response("http://x.com/", status=302, headers={"Location": "/novo"})
    assert mw.process_response(req, resp) is resp


def test_ct02_guarda_g2_sem_header_location_impede_redirecionamento(crawler_factory):
    mw = RedirectMiddleware.from_crawler(crawler_factory())
    req = Request("http://x.com/")
    resp = Response("http://x.com/", status=302)  # sem Location
    assert mw.process_response(req, resp) is resp


def test_ct03_guarda_g3_status_fora_da_lista_de_redirect_impede(crawler_factory):
    mw = RedirectMiddleware.from_crawler(crawler_factory())
    req = Request("http://x.com/")
    resp = Response("http://x.com/", status=200, headers={"Location": "/novo"})
    assert mw.process_response(req, resp) is resp


# ==========================================================================
# Seção 1 — troca de verbo (guarda G4 satisfeita)
# ==========================================================================


@pytest.mark.parametrize(
    "id_caso, regra, status, metodo_original, metodo_esperado",
    [
        ("CT04", "R1", 301, "POST", "GET"),
        ("CT05", "R2", 302, "PUT", "PUT"),
        ("CT06", "R3", 303, "PUT", "GET"),
        ("CT07", "R4", 303, "HEAD", "HEAD"),
        ("CT08", "R5", 307, "POST", "POST"),
        ("CT09", "R5", 308, "POST", "POST"),
    ],
)
def test_troca_de_verbo_tabela_de_decisao(
    crawler_factory, id_caso, regra, status, metodo_original, metodo_esperado
):
    mw = RedirectMiddleware.from_crawler(crawler_factory())
    req = Request("http://x.com/origem", method=metodo_original)
    resp = Response("http://x.com/origem", status=status, headers={"Location": "/destino"})
    resultado = mw.process_response(req, resp)
    assert isinstance(resultado, Request)
    assert resultado.method == metodo_esperado


# ==========================================================================
# Seção 2 — remoção de Cookie / Authorization no redirect
# ==========================================================================


@pytest.mark.parametrize(
    "id_caso, regra, url_origem, url_destino, cookie_preservado",
    [
        ("CT10", "C1", "http://x.com/a", "https://x.com/a", True),  # upgrade seguro, mesmo host
        ("CT11", "C2", "http://x.com/a", "http://y.com/a", False),  # host diferente
        ("CT12", "C3", "https://x.com/a", "http://x.com/a", False),  # downgrade
    ],
)
def test_remocao_de_cookie_tabela_de_decisao(
    crawler_factory, id_caso, regra, url_origem, url_destino, cookie_preservado
):
    mw = RedirectMiddleware.from_crawler(crawler_factory())
    req = Request(url_origem, headers={"Cookie": "sessao=abc"})
    resp = Response(url_origem, status=302, headers={"Location": url_destino})
    resultado = mw.process_response(req, resp)
    if cookie_preservado:
        assert resultado.headers.get("Cookie") == b"sessao=abc"
    else:
        assert "Cookie" not in resultado.headers


@pytest.mark.parametrize(
    "id_caso, regra, url_origem, url_destino, auth_preservado",
    [
        ("CT13", "A1", "http://x.com/a", "http://x.com/a", True),  # tudo idêntico
        ("CT14", "A2", "http://x.com/a", "https://x.com/a", False),  # esquema diferente
        ("CT15", "A3", "http://x.com/a", "http://y.com/a", False),  # host diferente
        ("CT16", "A4", "http://x.com:80/a", "http://x.com:8080/a", False),  # só a porta muda
    ],
)
def test_remocao_de_authorization_tabela_de_decisao(
    crawler_factory, id_caso, regra, url_origem, url_destino, auth_preservado
):
    """A tabela de Authorization é mais estrita que a de Cookie -- mata
    mutante que reaproveite a mesma condição das duas remoções."""
    mw = RedirectMiddleware.from_crawler(crawler_factory())
    req = Request(url_origem, headers={"Authorization": "Bearer token"})
    resp = Response(url_origem, status=302, headers={"Location": url_destino})
    resultado = mw.process_response(req, resp)
    if auth_preservado:
        assert "Authorization" in resultado.headers
    else:
        assert "Authorization" not in resultado.headers


# ==========================================================================
# Seção 3 — RetryMiddleware.process_response
# ==========================================================================


@pytest.mark.parametrize(
    "id_caso, regra, dont_retry, status, e_retry",
    [
        ("CT17", "R1", True, 503, False),
        ("CT18", "R2", False, 200, False),
        ("CT19", "R3", False, 503, True),
    ],
)
def test_retry_process_response_tabela_de_decisao(
    crawler_factory, id_caso, regra, dont_retry, status, e_retry
):
    mw = RetryMiddleware.from_crawler(crawler_factory())
    req = Request("http://x.com/", meta={"dont_retry": dont_retry})
    resp = Response("http://x.com/", status=status)
    resultado = mw.process_response(req, resp)
    if e_retry:
        assert isinstance(resultado, Request)
        assert resultado.dont_filter is True
    else:
        assert resultado is resp
