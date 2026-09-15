"""
Testes estruturais (caixa-branca) de scrapy/http/request/__init__.py e
scrapy/http/response/{__init__.py,text.py}.

Todos os testes aqui constroem Request/Response/TextResponse diretamente em
memória -- sem crawler, sem reactor, sem rede. É a camada de dados mais pura
do Scrapy, e por isso a mais barata de testar exaustivamente.
"""

from __future__ import annotations

import pytest

from scrapy.exceptions import NotSupported
from scrapy.http import HtmlResponse, Response, TextResponse
from scrapy.http.request import NO_CALLBACK, Request
from scrapy.link import Link


# --------------------------------------------------------------------------
# Request
# --------------------------------------------------------------------------


def test_request_metodo_padrao_e_get_em_maiusculas():
    r = Request("http://example.com/")
    assert r.method == "GET"


def test_request_metodo_customizado_e_normalizado_para_maiusculas():
    """Mata mutante que remova o .upper() em str(method).upper()."""
    r = Request("http://example.com/", method="post")
    assert r.method == "POST"


def test_request_url_nao_string_levanta_type_error():
    with pytest.raises(TypeError):
        Request(url=123)


def test_request_url_sem_esquema_levanta_value_error():
    with pytest.raises(ValueError):
        Request("example.com/sem-esquema")


@pytest.mark.parametrize("url", ["about:blank", "data:text/plain,oi"])
def test_request_aceita_esquemas_especiais_about_e_data(url):
    """Mata mutante que remova a exceção para about:/data: na validação de esquema."""
    r = Request(url)
    assert r.url == url


def test_request_prioridade_nao_inteira_levanta_type_error():
    with pytest.raises(TypeError):
        Request("http://example.com/", priority="alta")


def test_request_callback_nao_callable_levanta_type_error():
    with pytest.raises(TypeError):
        Request("http://example.com/", callback="nao-e-funcao")


def test_request_errback_nao_callable_levanta_type_error():
    with pytest.raises(TypeError):
        Request("http://example.com/", errback="nao-e-funcao")


def test_request_meta_cb_kwargs_flags_cookies_sao_independentes_por_instancia():
    """Mata mutante que troque os valores default de meta/cb_kwargs/flags/cookies
    por um dicionário ou lista mutável compartilhada entre instâncias."""
    r1 = Request("http://example.com/")
    r2 = Request("http://example.com/")
    r1.meta["chave"] = "valor"
    r1.cb_kwargs["outra"] = 1
    r1.flags.append("marcado")
    assert r2.meta == {}
    assert r2.cb_kwargs == {}
    assert r2.flags == []


def test_request_repr_contem_metodo_e_url():
    r = Request("http://example.com/caminho", method="POST")
    assert repr(r) == "<POST http://example.com/caminho>"


def test_request_copy_preserva_todos_os_atributos_publicos():
    r = Request("http://example.com/", method="POST", meta={"x": 1}, priority=5)
    copia = r.copy()
    assert copia.url == r.url
    assert copia.method == r.method
    assert copia.meta == r.meta
    assert copia.priority == r.priority
    assert copia is not r


def test_request_replace_troca_apenas_o_atributo_pedido():
    r = Request("http://example.com/original", method="GET")
    substituto = r.replace(url="http://example.com/novo")
    assert substituto.url == "http://example.com/novo"
    assert substituto.method == "GET"  # preservado


def test_request_to_dict_inclui_classe_apenas_para_subclasses():
    """Mata mutante que sempre (ou nunca) inclua a chave _class no dict."""
    from scrapy.http import FormRequest

    base = Request("http://example.com/")
    subclasse = FormRequest("http://example.com/")
    assert "_class" not in base.to_dict()
    assert subclasse.to_dict()["_class"].endswith("FormRequest")


def test_no_callback_levanta_runtime_error_ao_ser_chamado():
    with pytest.raises(RuntimeError):
        NO_CALLBACK()


# --------------------------------------------------------------------------
# Response (base, não-texto)
# --------------------------------------------------------------------------


def test_response_status_padrao_e_200_e_e_convertido_para_int():
    r = Response("http://example.com/", status="404")
    assert r.status == 404
    assert isinstance(r.status, int)


def test_response_body_nao_bytes_levanta_type_error():
    with pytest.raises(TypeError):
        Response("http://example.com/", body="corpo em str")


def test_response_body_none_vira_bytes_vazio():
    r = Response("http://example.com/", body=None)
    assert r.body == b""


def test_response_url_nao_string_levanta_type_error():
    with pytest.raises(TypeError):
        Response(url=123)


def test_response_repr_contem_status_e_url():
    r = Response("http://example.com/pagina", status=404)
    assert repr(r) == "<404 http://example.com/pagina>"


def test_response_base_text_levanta_attribute_error():
    r = Response("http://example.com/")
    with pytest.raises(AttributeError):
        r.text


@pytest.mark.parametrize("metodo", ["css", "xpath", "jmespath"])
def test_response_base_seletores_levantam_not_supported(metodo):
    """Mata mutante que troque NotSupported por outra exceção nos métodos
    de seletor da classe base (só TextResponse os implementa de fato)."""
    r = Response("http://example.com/")
    with pytest.raises(NotSupported):
        getattr(r, metodo)("qualquer coisa")


def test_response_meta_sem_request_associado_levanta_attribute_error():
    r = Response("http://example.com/")
    with pytest.raises(AttributeError, match="não é possível|not available"):
        r.meta


def test_response_urljoin_resolve_caminho_relativo():
    r = Response("http://example.com/dir/pagina.html")
    assert r.urljoin("outra.html") == "http://example.com/dir/outra.html"


def test_response_follow_resolve_url_relativa_para_absoluta():
    r = Response("http://example.com/dir/")
    req = r.follow("pagina.html")
    assert req.url == "http://example.com/dir/pagina.html"


def test_response_follow_aceita_objeto_link():
    r = Response("http://example.com/")
    req = r.follow(Link(url="http://example.com/via-link"))
    assert req.url == "http://example.com/via-link"


def test_response_follow_url_none_levanta_value_error():
    r = Response("http://example.com/")
    with pytest.raises(ValueError):
        r.follow(None)


def test_response_follow_encoding_none_levanta_value_error():
    r = Response("http://example.com/")
    with pytest.raises(ValueError):
        r.follow("pagina.html", encoding=None)


def test_response_follow_all_nao_iteravel_levanta_type_error():
    r = Response("http://example.com/")
    with pytest.raises(TypeError):
        r.follow_all(urls=123)


def test_response_replace_preserva_status_e_troca_url():
    r = Response("http://example.com/", status=201, body=b"conteudo")
    r2 = r.replace(url="http://example.com/outra")
    assert r2.status == 201
    assert r2.body == b"conteudo"
    assert r2.url == "http://example.com/outra"


# --------------------------------------------------------------------------
# TextResponse / HtmlResponse -- detecção de encoding, seletores, follow
# --------------------------------------------------------------------------


def test_text_response_usa_encoding_explicito_quando_informado():
    r = TextResponse("http://example.com/", encoding="latin-1", body="olá".encode("latin-1"))
    assert r.encoding == "latin-1"
    assert r.text == "olá"


def test_text_response_deteta_encoding_via_header_content_type():
    """Mata mutante que remova a leitura do charset a partir do header.

    Nota: w3lib.encoding.resolve_encoding mapeia "iso-8859-1" para "cp1252"
    (o WHATWG faz o mesmo mapeamento por compatibilidade legada com
    navegadores) -- por isso o valor final não é literalmente "iso-8859-1",
    mas o header foi, comprovadamente, o que decidiu o encoding."""
    r = TextResponse(
        "http://example.com/",
        headers={"Content-Type": "text/html; charset=iso-8859-1"},
        body="café".encode("iso-8859-1"),
    )
    assert r.encoding == "cp1252"
    assert r.text == "café"


def test_text_response_deteta_encoding_via_meta_tag_no_html():
    html = '<html><head><meta charset="utf-8"></head><body>ação</body></html>'
    r = HtmlResponse("http://example.com/", body=html.encode("utf-8"))
    assert r.encoding == "utf-8"
    assert "ação" in r.text


def test_text_response_body_string_exige_encoding_explicito():
    with pytest.raises(TypeError):
        TextResponse("http://example.com/", body="sem encoding definido")


def test_text_response_json_decodifica_corpo():
    r = TextResponse(
        "http://example.com/",
        encoding="utf-8",
        headers={"Content-Type": "application/json"},
        body=b'{"chave": "valor"}',
    )
    assert r.json() == {"chave": "valor"}


def test_text_response_css_e_xpath_encontram_elementos():
    html = "<html><body><h1 class='titulo'>Oi</h1></body></html>"
    r = HtmlResponse("http://example.com/", body=html.encode("utf-8"))
    assert r.css("h1.titulo::text").get() == "Oi"
    assert r.xpath("//h1/text()").get() == "Oi"


def test_text_response_follow_com_selector_de_link_extrai_href():
    html = '<html><body><a href="/destino">ir</a></body></html>'
    r = HtmlResponse("http://example.com/pagina", body=html.encode("utf-8"))
    link_selector = r.css("a")[0]
    req = r.follow(link_selector)
    assert req.url == "http://example.com/destino"


def test_text_response_follow_com_seletor_de_tag_sem_href_levanta_erro():
    html = '<html><body><a>sem href</a></body></html>'
    r = HtmlResponse("http://example.com/pagina", body=html.encode("utf-8"))
    link_selector = r.css("a")[0]
    with pytest.raises(ValueError):
        r.follow(link_selector)


def test_text_response_follow_all_exige_exatamente_um_argumento():
    html = '<html><body><a href="/a">a</a><a href="/b">b</a></body></html>'
    r = HtmlResponse("http://example.com/", body=html.encode("utf-8"))
    with pytest.raises(ValueError):
        list(r.follow_all(urls=["/a"], css="a"))


def test_text_response_follow_all_via_css_gera_uma_requisicao_por_link():
    html = '<html><body><a href="/a">a</a><a href="/b">b</a></body></html>'
    r = HtmlResponse("http://example.com/", body=html.encode("utf-8"))
    reqs = list(r.follow_all(css="a"))
    assert {req.url for req in reqs} == {"http://example.com/a", "http://example.com/b"}
