"""
Testes estruturais (caixa-branca) de quatro downloader middlewares:
RedirectMiddleware, RetryMiddleware, HttpAuthMiddleware e OffsiteMiddleware.

Todos são testados chamando process_request/process_response/process_exception
diretamente, com um Crawler real (via get_crawler(), sem reactor rodando) --
não é uma requisição de verdade passando pelo engine, é o middleware isolado,
exatamente como o padrão "chain of responsibility" do Scrapy permite testar
cada elo da corrente sem montar a corrente inteira.
"""

from __future__ import annotations

import pytest

from scrapy import Request, Spider
from scrapy.downloadermiddlewares.httpauth import HttpAuthMiddleware
from scrapy.downloadermiddlewares.offsite import OffsiteMiddleware
from scrapy.downloadermiddlewares.redirect import RedirectMiddleware
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.exceptions import IgnoreRequest, NotConfigured
from scrapy.http import Response


# --------------------------------------------------------------------------
# RedirectMiddleware
# --------------------------------------------------------------------------


def test_redirect_sem_location_devolve_a_mesma_resposta(crawler_factory):
    crawler = crawler_factory()
    mw = RedirectMiddleware.from_crawler(crawler)
    req = Request("http://example.com/")
    resp = Response("http://example.com/", status=200)
    assert mw.process_response(req, resp) is resp


def test_redirect_com_dont_redirect_no_meta_ignora_redirecionamento(crawler_factory):
    crawler = crawler_factory()
    mw = RedirectMiddleware.from_crawler(crawler)
    req = Request("http://example.com/", meta={"dont_redirect": True})
    resp = Response(
        "http://example.com/", status=302, headers={"Location": "/novo"}
    )
    assert mw.process_response(req, resp) is resp


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_gera_nova_requisicao_para_location(crawler_factory, status):
    crawler = crawler_factory()
    mw = RedirectMiddleware.from_crawler(crawler)
    req = Request("http://example.com/origem")
    resp = Response(
        "http://example.com/origem", status=status, headers={"Location": "/destino"}
    )
    resultado = mw.process_response(req, resp)
    assert isinstance(resultado, Request)
    assert resultado.url == "http://example.com/destino"


@pytest.mark.parametrize("status", [301, 302])
def test_redirect_converte_post_em_get_para_301_e_302(crawler_factory, status):
    """Mata mutante que remova a condição 'request.method == \"POST\"' na troca de verbo."""
    crawler = crawler_factory()
    mw = RedirectMiddleware.from_crawler(crawler)
    req = Request("http://example.com/origem", method="POST", body=b"dados")
    resp = Response(
        "http://example.com/origem", status=status, headers={"Location": "/destino"}
    )
    resultado = mw.process_response(req, resp)
    assert resultado.method == "GET"
    assert resultado.body == b""


def test_redirect_307_nao_converte_post_em_get(crawler_factory):
    crawler = crawler_factory()
    mw = RedirectMiddleware.from_crawler(crawler)
    req = Request("http://example.com/origem", method="POST", body=b"dados")
    resp = Response(
        "http://example.com/origem", status=307, headers={"Location": "/destino"}
    )
    resultado = mw.process_response(req, resp)
    assert resultado.method == "POST"
    assert resultado.body == b"dados"


def test_redirect_303_converte_qualquer_metodo_nao_get_head_em_get(crawler_factory):
    crawler = crawler_factory()
    mw = RedirectMiddleware.from_crawler(crawler)
    req = Request("http://example.com/origem", method="PUT")
    resp = Response(
        "http://example.com/origem", status=303, headers={"Location": "/destino"}
    )
    resultado = mw.process_response(req, resp)
    assert resultado.method == "GET"


def test_redirect_remove_cookie_ao_trocar_de_host(crawler_factory):
    """Mata mutante que remova a checagem 'source_host != redirect_host'."""
    crawler = crawler_factory()
    mw = RedirectMiddleware.from_crawler(crawler)
    req = Request(
        "http://origem.example.com/", headers={"Cookie": "sessao=abc"}
    )
    resp = Response(
        "http://origem.example.com/",
        status=302,
        headers={"Location": "http://outro-host.example.com/pagina"},
    )
    resultado = mw.process_response(req, resp)
    assert "Cookie" not in resultado.headers


def test_redirect_mantem_cookie_no_mesmo_host(crawler_factory):
    crawler = crawler_factory()
    mw = RedirectMiddleware.from_crawler(crawler)
    req = Request(
        "http://example.com/origem", headers={"Cookie": "sessao=abc"}
    )
    resp = Response(
        "http://example.com/origem", status=302, headers={"Location": "/destino"}
    )
    resultado = mw.process_response(req, resp)
    assert resultado.headers.get("Cookie") == b"sessao=abc"


def test_redirect_alem_do_limite_maximo_levanta_ignore_request(crawler_factory):
    """Mata mutante que troque 'redirects <= self.max_redirect_times' por outra comparação."""
    crawler = crawler_factory(settings_dict={"REDIRECT_MAX_TIMES": 1})
    mw = RedirectMiddleware.from_crawler(crawler)
    req = Request("http://example.com/origem", meta={"redirect_times": 1})
    resp = Response(
        "http://example.com/origem", status=302, headers={"Location": "/destino"}
    )
    with pytest.raises(IgnoreRequest):
        mw.process_response(req, resp)


# --------------------------------------------------------------------------
# RetryMiddleware
# --------------------------------------------------------------------------


def test_retry_middleware_desabilitada_levanta_not_configured(crawler_factory):
    crawler = crawler_factory(settings_dict={"RETRY_ENABLED": False})
    with pytest.raises(NotConfigured):
        RetryMiddleware.from_crawler(crawler)


def test_retry_process_response_ignora_status_fora_da_lista(crawler_factory):
    crawler = crawler_factory()
    mw = RetryMiddleware.from_crawler(crawler)
    req = Request("http://example.com/")
    resp = Response("http://example.com/", status=200)
    assert mw.process_response(req, resp) is resp


def test_retry_process_response_gera_nova_requisicao_para_status_configurado(crawler_factory):
    crawler = crawler_factory()
    mw = RetryMiddleware.from_crawler(crawler)
    req = Request("http://example.com/")
    resp = Response("http://example.com/", status=503)  # está em RETRY_HTTP_CODES por padrão
    resultado = mw.process_response(req, resp)
    assert isinstance(resultado, Request)
    assert resultado.meta["retry_times"] == 1
    assert resultado.dont_filter is True


def test_retry_process_response_respeita_dont_retry(crawler_factory):
    """Mata mutante que remova a checagem de dont_retry em process_response."""
    crawler = crawler_factory()
    mw = RetryMiddleware.from_crawler(crawler)
    req = Request("http://example.com/", meta={"dont_retry": True})
    resp = Response("http://example.com/", status=503)
    assert mw.process_response(req, resp) is resp


def test_retry_esgota_tentativas_e_devolve_a_resposta_original(crawler_factory):
    crawler = crawler_factory(settings_dict={"RETRY_TIMES": 1})
    mw = RetryMiddleware.from_crawler(crawler)
    req = Request("http://example.com/", meta={"retry_times": 1})  # já tentou 1 vez
    resp = Response("http://example.com/", status=503)
    resultado = mw.process_response(req, resp)
    assert resultado is resp  # get_retry_request devolveu None -> "or response"


def test_retry_process_exception_retenta_para_excecao_configurada(crawler_factory):
    crawler = crawler_factory()
    mw = RetryMiddleware.from_crawler(crawler)
    req = Request("http://example.com/")
    resultado = mw.process_exception(req, ConnectionError("falha de rede"))
    assert isinstance(resultado, Request)
    assert resultado.meta["retry_times"] == 1


def test_retry_process_exception_ignora_excecao_nao_configurada(crawler_factory):
    crawler = crawler_factory()
    mw = RetryMiddleware.from_crawler(crawler)
    req = Request("http://example.com/")

    class ErroQueNaoDeveSerRetentado(Exception):
        pass

    assert mw.process_exception(req, ErroQueNaoDeveSerRetentado()) is None


# --------------------------------------------------------------------------
# HttpAuthMiddleware
# --------------------------------------------------------------------------


def test_httpauth_usuario_sem_dominio_explicito_levanta_value_error(crawler_factory):
    """Mata mutante que troque 'domain_priority <= default' por outra comparação."""
    crawler = crawler_factory(settings_dict={"HTTPAUTH_USER": "spider"})
    with pytest.raises(ValueError):
        HttpAuthMiddleware.from_crawler(crawler)


def test_httpauth_com_dominio_definido_como_none_e_valido(crawler_factory):
    """Definir HTTPAUTH_DOMAIN=None (explicitamente, prioridade acima de
    'default') é o jeito documentado de dizer 'envie a credencial para
    qualquer host'. Precisa ir junto no settings_dict inicial: depois que
    get_crawler() roda, _apply_settings() já congela o objeto Settings."""
    crawler = crawler_factory(
        settings_dict={
            "HTTPAUTH_USER": "spider",
            "HTTPAUTH_PASS": "segredo",
            "HTTPAUTH_DOMAIN": None,
        }
    )
    mw = HttpAuthMiddleware.from_crawler(crawler)
    req = Request("http://qualquer-host.example.com/")
    mw.process_request(req)
    assert "Authorization" in req.headers


def test_httpauth_restringe_credencial_ao_dominio_configurado(crawler_factory):
    crawler = crawler_factory(
        settings_dict={
            "HTTPAUTH_USER": "spider",
            "HTTPAUTH_DOMAIN": "permitido.example.com",
        }
    )
    mw = HttpAuthMiddleware.from_crawler(crawler)

    req_permitido = Request("http://permitido.example.com/")
    mw.process_request(req_permitido)
    assert "Authorization" in req_permitido.headers

    req_fora_do_dominio = Request("http://outro.example.com/")
    mw.process_request(req_fora_do_dominio)
    assert "Authorization" not in req_fora_do_dominio.headers


def test_httpauth_nao_sobrescreve_authorization_ja_definido(crawler_factory):
    """Mata mutante que remova a checagem 'if b\"Authorization\" in request.headers'."""
    crawler = crawler_factory(
        settings_dict={"HTTPAUTH_USER": "spider", "HTTPAUTH_DOMAIN": None}
    )
    mw = HttpAuthMiddleware.from_crawler(crawler)
    req = Request(
        "http://example.com/", headers={"Authorization": "Bearer token-customizado"}
    )
    mw.process_request(req)
    assert req.headers["Authorization"] == b"Bearer token-customizado"


# --------------------------------------------------------------------------
# OffsiteMiddleware
# --------------------------------------------------------------------------


class _SpiderComDominioPermitido(Spider):
    name = "com-dominio"
    allowed_domains = ["permitido.example.com"]


class _SpiderSemAllowedDomains(Spider):
    name = "sem-dominio"


def test_offsite_sem_allowed_domains_permite_tudo(crawler_factory):
    crawler = crawler_factory(_SpiderSemAllowedDomains)
    mw = OffsiteMiddleware.from_crawler(crawler)
    mw.spider_opened(crawler.spider)
    req = Request("http://qualquer-lugar.example.com/")
    mw.process_request(req)  # não deve levantar


def test_offsite_bloqueia_dominio_fora_da_lista(crawler_factory):
    crawler = crawler_factory(_SpiderComDominioPermitido)
    mw = OffsiteMiddleware.from_crawler(crawler)
    mw.spider_opened(crawler.spider)
    req = Request("http://fora.example.com/")
    with pytest.raises(IgnoreRequest):
        mw.process_request(req)


def test_offsite_permite_subdominio_do_dominio_permitido(crawler_factory):
    """Mata mutante que troque o regex '^(.*\\.)?(dominio)$' por match exato."""
    crawler = crawler_factory(_SpiderComDominioPermitido)
    mw = OffsiteMiddleware.from_crawler(crawler)
    mw.spider_opened(crawler.spider)
    req = Request("http://sub.permitido.example.com/")
    mw.process_request(req)  # não deve levantar


def test_offsite_dont_filter_ignora_a_restricao_de_dominio(crawler_factory):
    crawler = crawler_factory(_SpiderComDominioPermitido)
    mw = OffsiteMiddleware.from_crawler(crawler)
    mw.spider_opened(crawler.spider)
    req = Request("http://fora.example.com/", dont_filter=True)
    mw.process_request(req)  # não deve levantar


def test_offsite_meta_allow_offsite_ignora_a_restricao_de_dominio(crawler_factory):
    crawler = crawler_factory(_SpiderComDominioPermitido)
    mw = OffsiteMiddleware.from_crawler(crawler)
    mw.spider_opened(crawler.spider)
    req = Request("http://fora.example.com/", meta={"allow_offsite": True})
    mw.process_request(req)  # não deve levantar
