"""
Testes de integração: crawls REAIS, rodando o engine e o reactor Twisted de
verdade (via pytest-twisted), contra o servidor HTML local. Diferente dos
testes estruturais, aqui ninguém chama process_request/process_response na
mão -- é o Scheduler, o Downloader, o Engine, os middlewares e o dupefilter
cooperando exatamente como cooperariam num crawl de produção. É o nível de
teste que só faz sentido existir porque o Scrapy inteiro gira em torno de um
loop assíncrono que nenhum teste estrutural isolado consegue exercitar.
"""

from __future__ import annotations

import pytest_twisted
from twisted.python.failure import Failure

from scrapy import Field, Request, Spider
from scrapy.crawler import CrawlerRunner
from scrapy.item import Item


# --------------------------------------------------------------------------
# Seguir links reais / dedup via RFPDupeFilter
# --------------------------------------------------------------------------


@pytest_twisted.ensureDeferred
async def test_crawl_segue_links_da_homepage_e_visita_as_duas_paginas(
    html_server, reactor_settings
):
    visitadas = []

    class SpiderDeLinks(Spider):
        name = "links"
        start_urls = [html_server + "/"]

        def parse(self, response):
            visitadas.append(response.url)
            if response.url.endswith("/"):
                yield from response.follow_all(css="a")

    runner = CrawlerRunner(reactor_settings)
    await runner.crawl(SpiderDeLinks)

    assert sorted(visitadas) == sorted(
        [html_server + "/", html_server + "/pagina2", html_server + "/pagina3"]
    )


@pytest_twisted.ensureDeferred
async def test_dupefilter_real_evita_visitar_a_mesma_url_duas_vezes(
    html_server, reactor_settings
):
    """A homepage aponta duas vezes para /pagina2 (como aconteceria com dois
    links <a> repetidos numa página real) -- o RFPDupeFilter, ativo por
    padrão, deve descartar a segunda.

    Detalhe que só apareceu ao rodar isto de verdade: uma primeira versão
    deste teste fazia o spider seguir de volta para a própria start_url, e
    a página inicial era visitada DUAS vezes, não uma. O motivo: requisições
    de start_urls nascem com dont_filter=True (é assim que Spider.start()
    as cria), e o scheduler só registra uma requisição no dupefilter quando
    dont_filter é False -- então a start_url nunca chega a ficar "vista" para
    o filtro, e uma segunda requisição para a mesma URL, gerada depois via
    response.follow(), não é reconhecida como duplicata. O dedup real só
    entra em ação entre requisições que NÃO são de start_urls, como abaixo."""
    visitas_pagina2 = []

    class SpiderComLinkRepetido(Spider):
        name = "link-repetido"
        start_urls = [html_server + "/"]

        def parse(self, response):
            if response.url.endswith("/pagina2"):
                visitas_pagina2.append(1)
                return
            yield response.follow("/pagina2")
            yield response.follow("/pagina2")  # mesmo destino, segunda vez

    runner = CrawlerRunner(reactor_settings)
    await runner.crawl(SpiderComLinkRepetido)

    assert len(visitas_pagina2) == 1


# --------------------------------------------------------------------------
# RedirectMiddleware real
# --------------------------------------------------------------------------


@pytest_twisted.ensureDeferred
async def test_crawl_segue_redirecionamento_real_ate_a_pagina_final(
    html_server, reactor_settings
):
    urls_finais = []

    class SpiderComRedirect(Spider):
        name = "redirect"
        start_urls = [html_server + "/redirect-para-pagina2"]

        def parse(self, response):
            urls_finais.append(response.url)

    runner = CrawlerRunner(reactor_settings)
    await runner.crawl(SpiderComRedirect)

    assert urls_finais == [html_server + "/pagina2"]


# --------------------------------------------------------------------------
# RetryMiddleware real
# --------------------------------------------------------------------------


@pytest_twisted.ensureDeferred
async def test_crawl_reenvia_requisicao_apos_falhas_intermitentes_ate_ter_sucesso(
    html_server, reactor_settings
):
    sucesso = []

    class SpiderComRetry(Spider):
        name = "retry"
        start_urls = [html_server + "/intermitente?id=integracao"]
        custom_settings = {"RETRY_TIMES": 3}

        def parse(self, response):
            sucesso.append(response.status)

    runner = CrawlerRunner(reactor_settings)
    await runner.crawl(SpiderComRetry)

    assert sucesso == [200]  # só chega ao parse() depois que o retry teve sucesso


@pytest_twisted.ensureDeferred
async def test_crawl_desiste_apos_esgotar_tentativas_e_chama_errback(
    html_server, reactor_settings
):
    erros = []

    class SpiderQueDesiste(Spider):
        name = "desiste"
        custom_settings = {"RETRY_TIMES": 1}

        async def start(self):
            yield Request(
                html_server + "/erro-500", callback=self.parse, errback=self.on_error
            )

        def parse(self, response):
            pass  # nunca deve ser chamado: 500 persistente esgota as tentativas

        def on_error(self, failure: Failure):
            erros.append(failure.value.response.status)

    runner = CrawlerRunner(reactor_settings)
    await runner.crawl(SpiderQueDesiste)

    assert erros == [500]


# --------------------------------------------------------------------------
# DepthMiddleware real
# --------------------------------------------------------------------------


@pytest_twisted.ensureDeferred
async def test_crawl_respeita_depth_limit_real(html_server, reactor_settings):
    niveis_visitados = []

    class SpiderProfundo(Spider):
        name = "profundo"
        start_urls = [html_server + "/profundo/0"]
        custom_settings = {"DEPTH_LIMIT": 2}

        def parse(self, response):
            niveis_visitados.append(response.meta["depth"])
            yield from response.follow_all(css="a")

    runner = CrawlerRunner(reactor_settings)
    await runner.crawl(SpiderProfundo)

    assert sorted(niveis_visitados) == [0, 1, 2]  # nível 3 foi descartado pelo DEPTH_LIMIT


# --------------------------------------------------------------------------
# HttpAuthMiddleware real
# --------------------------------------------------------------------------


@pytest_twisted.ensureDeferred
async def test_crawl_acessa_area_protegida_com_credenciais_configuradas(
    html_server, reactor_settings
):
    conteudo = []

    class SpiderAutenticado(Spider):
        name = "autenticado"
        start_urls = [html_server + "/protegido"]
        custom_settings = {
            "HTTPAUTH_USER": "spider",
            "HTTPAUTH_PASS": "segredo",
            "HTTPAUTH_DOMAIN": None,
        }

        def parse(self, response):
            conteudo.append(response.status)

    runner = CrawlerRunner(reactor_settings)
    await runner.crawl(SpiderAutenticado)

    assert conteudo == [200]


# --------------------------------------------------------------------------
# Item pipeline real (engine -> spidermw -> scraper -> pipeline)
# --------------------------------------------------------------------------


class Produto(Item):
    nome = Field()
    preco = Field()


class ColetaPipeline:
    itens: list = []

    def process_item(self, item, spider=None):
        ColetaPipeline.itens.append(dict(item))
        return item


@pytest_twisted.ensureDeferred
async def test_crawl_extrai_itens_e_entrega_ao_pipeline(html_server, reactor_settings):
    ColetaPipeline.itens = []

    class SpiderDeProdutos(Spider):
        name = "produtos"
        start_urls = [html_server + "/produtos"]
        custom_settings = {
            "ITEM_PIPELINES": {f"{__name__}.ColetaPipeline": 100},
        }

        def parse(self, response):
            for produto in response.css("div.produto"):
                yield Produto(
                    nome=produto.css(".nome::text").get(),
                    preco=produto.css(".preco::text").get(),
                )

    runner = CrawlerRunner(reactor_settings)
    await runner.crawl(SpiderDeProdutos)

    assert len(ColetaPipeline.itens) == 3
    assert {p["nome"] for p in ColetaPipeline.itens} == {"Cadeira", "Mesa", "Estante"}
