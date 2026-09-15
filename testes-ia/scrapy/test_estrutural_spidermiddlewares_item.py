"""
Testes estruturais (caixa-branca) de DepthMiddleware, UrlLengthMiddleware
(que herdam o Template Method de BaseSpiderMiddleware) e de scrapy/item.py.
"""

from __future__ import annotations

import pytest

from scrapy import Request
from scrapy.http import Response
from scrapy.item import Field, Item
from scrapy.spidermiddlewares.depth import DepthMiddleware
from scrapy.spidermiddlewares.urllength import UrlLengthMiddleware


def _resposta_com_profundidade(profundidade):
    r = Response("http://example.com/pagina")
    r.request = Request("http://example.com/pagina")
    r.meta["depth"] = profundidade
    return r


# --------------------------------------------------------------------------
# DepthMiddleware
# --------------------------------------------------------------------------


def test_depth_middleware_marca_profundidade_zero_na_primeira_resposta(crawler_factory):
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 0})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = Response("http://example.com/")
    resp.request = Request("http://example.com/")
    resultado = list(mw.process_spider_output(resp, []))
    assert resp.meta["depth"] == 0
    assert resultado == []


def test_depth_middleware_incrementa_profundidade_a_partir_da_resposta(crawler_factory):
    """Mata mutante que troque 'response.meta[\"depth\"] + 1' por outro valor."""
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 0})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(2)
    nova_req = Request("http://example.com/mais-fundo")
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert resultado[0].meta["depth"] == 3


def test_depth_middleware_descarta_requisicao_alem_do_limite(crawler_factory):
    """Mata mutante que troque 'depth > self.maxdepth' por '>=' ou '<'."""
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 2})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(2)  # próxima seria profundidade 3, além do limite
    nova_req = Request("http://example.com/muito-fundo")
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert resultado == []


def test_depth_middleware_permite_requisicao_exatamente_no_limite(crawler_factory):
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 3})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(2)  # próxima é profundidade 3, == limite
    nova_req = Request("http://example.com/no-limite")
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert len(resultado) == 1
    assert resultado[0].meta["depth"] == 3


def test_depth_middleware_sem_limite_configurado_nunca_descarta(crawler_factory):
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 0})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(50)
    nova_req = Request("http://example.com/muito-fundo-mesmo")
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert len(resultado) == 1


def test_depth_middleware_reduz_prioridade_proporcionalmente_a_profundidade(crawler_factory):
    """Mata mutante que troque '-=' por '+=' no ajuste de prioridade por profundidade."""
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 0, "DEPTH_PRIORITY": 1})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(0)
    nova_req = Request("http://example.com/x", priority=10)
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert resultado[0].priority < 10


def test_depth_middleware_itens_nao_request_passam_direto(crawler_factory):
    """Objetos que não são Request (ex.: dicts/Items extraídos) não são
    tocados pelo DepthMiddleware -- vão para get_processed_item, que por
    padrão (BaseSpiderMiddleware) apenas repassa o item."""
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 0})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(0)
    item = {"nome": "produto"}
    resultado = list(mw.process_spider_output(resp, [item]))
    assert resultado == [item]


def test_depth_reset_meta_zera_a_profundidade(crawler_factory):
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 0})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(10)
    nova_req = Request("http://outro-dominio.example.com/", meta={"depth_reset": True})
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert resultado[0].meta["depth"] == 0


# --------------------------------------------------------------------------
# UrlLengthMiddleware
# --------------------------------------------------------------------------


def test_urllength_middleware_sem_limite_configurado_levanta_not_configured(crawler_factory):
    from scrapy.exceptions import NotConfigured

    crawler = crawler_factory(settings_dict={"URLLENGTH_LIMIT": 0})
    with pytest.raises(NotConfigured):
        UrlLengthMiddleware.from_crawler(crawler)


def test_urllength_middleware_permite_url_dentro_do_limite(crawler_factory):
    crawler = crawler_factory(settings_dict={"URLLENGTH_LIMIT": 100})
    mw = UrlLengthMiddleware.from_crawler(crawler)
    resp = Response("http://example.com/")
    req = Request("http://example.com/curta")
    resultado = list(mw.process_spider_output(resp, [req]))
    assert resultado == [req]


def test_urllength_middleware_descarta_url_acima_do_limite(crawler_factory):
    """Mata mutante que troque '<=' por '<' na comparação de tamanho de URL."""
    crawler = crawler_factory(settings_dict={"URLLENGTH_LIMIT": 30})
    mw = UrlLengthMiddleware.from_crawler(crawler)
    resp = Response("http://example.com/")
    url_longa = "http://example.com/" + "x" * 50
    req = Request(url_longa)
    resultado = list(mw.process_spider_output(resp, [req]))
    assert resultado == []


def test_urllength_middleware_permite_url_exatamente_no_limite(crawler_factory):
    crawler = crawler_factory(settings_dict={"URLLENGTH_LIMIT": 200})
    mw = UrlLengthMiddleware.from_crawler(crawler)
    resp = Response("http://example.com/")
    req = Request("http://example.com/")
    limite = 200
    url_no_limite = req.url + "a" * (limite - len(req.url))
    req_no_limite = Request(url_no_limite)
    assert len(req_no_limite.url) == limite
    resultado = list(mw.process_spider_output(resp, [req_no_limite]))
    assert resultado == [req_no_limite]


# --------------------------------------------------------------------------
# Item / Field
# --------------------------------------------------------------------------


class Produto(Item):
    nome = Field()
    preco = Field()


def test_item_aceita_apenas_campos_declarados():
    p = Produto()
    p["nome"] = "Cadeira"
    assert p["nome"] == "Cadeira"


def test_item_campo_nao_declarado_levanta_key_error():
    """Mata mutante que remova a validação contra self.fields em __setitem__."""
    p = Produto()
    with pytest.raises(KeyError):
        p["campo_inexistente"] = "valor"


def test_item_getattr_de_campo_declarado_orienta_usar_colchetes():
    """Mata mutante que faça __getattr__ devolver o valor em vez de instruir
    o uso de item[...]."""
    p = Produto(nome="Mesa")
    with pytest.raises(AttributeError, match=r"item\['nome'\]"):
        p.nome


def test_item_setattr_de_atributo_publico_e_proibido():
    p = Produto()
    with pytest.raises(AttributeError):
        p.nome = "Mesa"


def test_item_construtor_aceita_dict_inicial():
    p = Produto({"nome": "Estante", "preco": 320.5})
    assert p["nome"] == "Estante"
    assert p["preco"] == 320.5


def test_item_copy_e_independente_do_original():
    p1 = Produto(nome="Cadeira")
    p2 = p1.copy()
    p2["nome"] = "Mesa"
    assert p1["nome"] == "Cadeira"
    assert p2["nome"] == "Mesa"


def test_item_repr_mostra_os_valores_como_dict():
    p = Produto(nome="Cadeira")
    assert "'nome': 'Cadeira'" in repr(p)


def test_item_herda_campos_da_classe_base():
    class ProdutoComDesconto(Produto):
        desconto = Field()

    p = ProdutoComDesconto(nome="Cadeira", desconto=0.1)
    assert set(p.fields) == {"nome", "preco", "desconto"}
