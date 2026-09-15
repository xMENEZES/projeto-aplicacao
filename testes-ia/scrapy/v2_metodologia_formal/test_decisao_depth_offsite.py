"""
v2 — técnica estrutural via tabela de decisão: DepthMiddleware e
OffsiteMiddleware. Casos CT20-CT23 e CT27-CT32 do PLANO_DE_TESTE.md
(seções 4 e 6).
"""

from __future__ import annotations

import pytest

from scrapy import Request, Spider
from scrapy.downloadermiddlewares.offsite import OffsiteMiddleware
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Response
from scrapy.spidermiddlewares.depth import DepthMiddleware


def _resposta_com_profundidade(profundidade):
    r = Response("http://x.com/pagina")
    r.request = Request("http://x.com/pagina")
    r.meta["depth"] = profundidade
    return r


# ==========================================================================
# Seção 4 — DepthMiddleware.get_processed_request
# ==========================================================================


def test_ct20_regra_d1_depth_reset_zera_a_profundidade(crawler_factory):
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 0})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(10)
    nova_req = Request("http://x.com/x", meta={"depth_reset": True})
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert resultado[0].meta["depth"] == 0


def test_ct21_regra_d2_profundidade_na_fronteira_do_limite_permite(crawler_factory):
    """Valor limite: DEPTH_LIMIT=3, origem em profundidade 2 -> nova = 3 (== limite, permite)."""
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 3})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(2)
    nova_req = Request("http://x.com/x")
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert len(resultado) == 1
    assert resultado[0].meta["depth"] == 3


def test_ct22_regra_d3_profundidade_um_acima_do_limite_descarta(crawler_factory):
    """Valor limite: DEPTH_LIMIT=3, origem em profundidade 3 -> nova = 4 (> limite, descarta)."""
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 3})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(3)
    nova_req = Request("http://x.com/x")
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert resultado == []


def test_ct23_regra_d4_depth_limit_zero_nunca_descarta(crawler_factory):
    crawler = crawler_factory(settings_dict={"DEPTH_LIMIT": 0})
    mw = DepthMiddleware.from_crawler(crawler)
    resp = _resposta_com_profundidade(500)  # profundidade absurdamente alta
    nova_req = Request("http://x.com/x")
    resultado = list(mw.process_spider_output(resp, [nova_req]))
    assert len(resultado) == 1


# ==========================================================================
# Seção 6 — OffsiteMiddleware.process_request
# ==========================================================================


class _SpiderComDominio(Spider):
    name = "com-dominio"
    allowed_domains = ["permitido.com"]


class _SpiderSemDominio(Spider):
    name = "sem-dominio"


@pytest.mark.parametrize(
    "id_caso, regra, spidercls, url, dont_filter, allow_offsite_meta, bloqueia",
    [
        ("CT27", "O1", _SpiderSemDominio, "http://qualquer.com/", False, False, False),
        ("CT28", "O2", _SpiderComDominio, "http://permitido.com/", False, False, False),
        ("CT29", "O2-var", _SpiderComDominio, "http://sub.permitido.com/", False, False, False),
        ("CT30", "O3", _SpiderComDominio, "http://fora.com/", False, False, True),
        ("CT31", "O4", _SpiderComDominio, "http://fora.com/", True, False, False),
        ("CT32", "O5", _SpiderComDominio, "http://fora.com/", False, True, False),
    ],
)
def test_offsite_tabela_de_decisao(
    crawler_factory, id_caso, regra, spidercls, url, dont_filter, allow_offsite_meta, bloqueia
):
    crawler = crawler_factory(spidercls)
    mw = OffsiteMiddleware.from_crawler(crawler)
    mw.spider_opened(crawler.spider)
    meta = {"allow_offsite": True} if allow_offsite_meta else {}
    req = Request(url, dont_filter=dont_filter, meta=meta)
    if bloqueia:
        with pytest.raises(IgnoreRequest):
            mw.process_request(req)
    else:
        mw.process_request(req)  # não deve levantar
