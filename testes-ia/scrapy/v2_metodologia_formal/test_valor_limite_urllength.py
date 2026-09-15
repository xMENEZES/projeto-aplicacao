"""
v2 — técnica funcional: valor limite puro em UrlLengthMiddleware. Casos
CT24-CT26 do PLANO_DE_TESTE.md (seção 5).
"""

from __future__ import annotations

import pytest

from scrapy import Request
from scrapy.http import Response
from scrapy.spidermiddlewares.urllength import UrlLengthMiddleware

LIMITE = 50


def _url_com_tamanho(tamanho):
    base = "http://x.com/"
    assert tamanho >= len(base)
    return base + "a" * (tamanho - len(base))


@pytest.mark.parametrize(
    "id_caso, tamanho_url, permite",
    [
        ("CT24", LIMITE - 1, True),
        ("CT25", LIMITE, True),  # fronteira: operador é <=, não <
        ("CT26", LIMITE + 1, False),
    ],
)
def test_urllength_valor_limite(crawler_factory, id_caso, tamanho_url, permite):
    """Mata mutante que troque '<=' por '<' (ou vice-versa) na comparação
    de tamanho de URL -- é exatamente o caso CT25, na própria fronteira,
    que expõe essa troca."""
    crawler = crawler_factory(settings_dict={"URLLENGTH_LIMIT": LIMITE})
    mw = UrlLengthMiddleware.from_crawler(crawler)
    resp = Response("http://x.com/")
    url = _url_com_tamanho(tamanho_url)
    assert len(url) == tamanho_url
    req = Request(url)
    resultado = list(mw.process_spider_output(resp, [req]))
    if permite:
        assert resultado == [req]
    else:
        assert resultado == []
