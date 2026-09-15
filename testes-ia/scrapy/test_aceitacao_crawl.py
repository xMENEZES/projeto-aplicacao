"""
Testes de aceitação: histórias de usuário, escritas no vocabulário de quem
usa o Scrapy para montar um spider -- não de quem implementa o framework.
Todos rodam crawls reais (via pytest-twisted) contra o servidor HTML local.
"""

from __future__ import annotations

import pytest_twisted

from scrapy import Field, Spider
from scrapy.crawler import CrawlerRunner
from scrapy.item import Item


@pytest_twisted.ensureDeferred
async def test_desenvolvedor_extrai_o_titulo_de_uma_pagina(html_server, reactor_settings):
    """Como desenvolvedor, quero escrever um spider simples que baixa uma
    página e extrai um texto usando um seletor CSS, sem lidar com sockets,
    parsing de HTML cru ou o loop de eventos manualmente."""
    titulos = []

    class SpiderDeTitulo(Spider):
        name = "titulo"
        start_urls = [html_server + "/pagina2"]

        def parse(self, response):
            titulos.append(response.css("h1::text").get())

    await CrawlerRunner(reactor_settings).crawl(SpiderDeTitulo)
    assert titulos == ["Página 2"]


@pytest_twisted.ensureDeferred
async def test_desenvolvedor_segue_links_automaticamente(html_server, reactor_settings):
    """Como desenvolvedor, quero que meu spider siga os links de uma página
    de listagem automaticamente, sem eu precisar montar cada Request na mão
    com a URL absoluta calculada manualmente."""
    paginas_visitadas = set()

    class SpiderQueSegueLinks(Spider):
        name = "segue-links"
        start_urls = [html_server + "/"]

        def parse(self, response):
            paginas_visitadas.add(response.url)
            if response.url == html_server + "/":
                yield from response.follow_all(css="a::attr(href)")

    await CrawlerRunner(reactor_settings).crawl(SpiderQueSegueLinks)

    assert html_server + "/pagina2" in paginas_visitadas
    assert html_server + "/pagina3" in paginas_visitadas


@pytest_twisted.ensureDeferred
async def test_desenvolvedor_limita_a_profundidade_do_rastreamento(
    html_server, reactor_settings
):
    """Como desenvolvedor, quero limitar até onde meu spider rastreia um
    site profundo demais, só configurando DEPTH_LIMIT -- sem precisar
    controlar contadores de profundidade manualmente no meu próprio código."""
    profundidades = []

    class SpiderLimitado(Spider):
        name = "limitado"
        start_urls = [html_server + "/profundo/0"]
        custom_settings = {"DEPTH_LIMIT": 1}

        def parse(self, response):
            profundidades.append(response.meta["depth"])
            yield from response.follow_all(css="a")

    await CrawlerRunner(reactor_settings).crawl(SpiderLimitado)

    assert max(profundidades) == 1
    assert len(profundidades) == 2  # nível 0 e nível 1, nunca o 2


@pytest_twisted.ensureDeferred
async def test_desenvolvedor_recebe_a_pagina_final_apos_redirecionamentos(
    html_server, reactor_settings
):
    """Como desenvolvedor, quero receber a resposta da página final depois
    de um redirecionamento, sem tratar o 302 manualmente no meu callback."""
    respostas = []

    class SpiderComRedirect(Spider):
        name = "aceita-redirect"
        start_urls = [html_server + "/redirect-para-pagina2"]

        def parse(self, response):
            respostas.append((response.status, response.url))

    await CrawlerRunner(reactor_settings).crawl(SpiderComRedirect)

    assert respostas == [(200, html_server + "/pagina2")]


@pytest_twisted.ensureDeferred
async def test_desenvolvedor_recebe_erros_temporarios_ja_resolvidos_por_retry(
    html_server, reactor_settings
):
    """Como desenvolvedor, quero que uma falha temporária do servidor (um
    500 esporádico) seja resolvida sozinha, sem eu escrever lógica de
    'tentar de novo' no meu spider."""
    chegou_ao_parse_com_sucesso = []

    class SpiderResiliente(Spider):
        name = "resiliente"
        start_urls = [html_server + "/intermitente?id=aceitacao"]
        custom_settings = {"RETRY_TIMES": 3}

        def parse(self, response):
            chegou_ao_parse_com_sucesso.append(response.status == 200)

    await CrawlerRunner(reactor_settings).crawl(SpiderResiliente)

    assert chegou_ao_parse_com_sucesso == [True]


@pytest_twisted.ensureDeferred
async def test_desenvolvedor_extrai_uma_listagem_como_itens_estruturados(
    html_server, reactor_settings
):
    """Como desenvolvedor, quero declarar um Item com os campos que me
    interessam e extrair uma listagem inteira de produtos como uma lista de
    objetos estruturados, em vez de dicionários soltos e inconsistentes."""

    class Produto(Item):
        nome = Field()
        preco = Field()

    itens_coletados = []

    class SpiderDeProdutos(Spider):
        name = "produtos-aceitacao"
        start_urls = [html_server + "/produtos"]

        def parse(self, response):
            for produto in response.css("div.produto"):
                item = Produto(
                    nome=produto.css(".nome::text").get(),
                    preco=produto.css(".preco::text").get(),
                )
                itens_coletados.append(item)
                yield item

    await CrawlerRunner(reactor_settings).crawl(SpiderDeProdutos)

    assert len(itens_coletados) == 3
    assert all(isinstance(item, Produto) for item in itens_coletados)
    assert {i["nome"] for i in itens_coletados} == {"Cadeira", "Mesa", "Estante"}


@pytest_twisted.ensureDeferred
async def test_desenvolvedor_acessa_conteudo_protegido_so_com_configuracao(
    html_server, reactor_settings
):
    """Como desenvolvedor, quero acessar uma página que exige usuário e
    senha apenas configurando HTTPAUTH_USER/HTTPAUTH_PASS, sem montar o
    cabeçalho Authorization manualmente em cada requisição."""
    resultados = []

    class SpiderAutenticado(Spider):
        name = "aceita-auth"
        start_urls = [html_server + "/protegido"]
        custom_settings = {
            "HTTPAUTH_USER": "spider",
            "HTTPAUTH_PASS": "segredo",
            "HTTPAUTH_DOMAIN": None,
        }

        def parse(self, response):
            resultados.append(response.css("h1::text").get())

    await CrawlerRunner(reactor_settings).crawl(SpiderAutenticado)

    assert resultados == ["acesso liberado"]
