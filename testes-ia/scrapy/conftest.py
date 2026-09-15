"""
Configuração compartilhada da suíte de testes do Scrapy.

Três responsabilidades, na mesma linha do que foi feito para o Requests:

1. Garante que `import scrapy` resolva para a cópia exata do código-fonte
   clonado em `repositorios-originais/scrapy` (versão 2.17.0), e não para uma cópia
   qualquer que porventura já esteja instalada no ambiente -- mesmo que,
   neste caso específico, as duas versões coincidam, a garantia evita que
   a suíte comece a testar a versão errada silenciosamente se algum dia
   isso deixar de ser verdade.

2. Sobe um servidor HTTP local que serve páginas HTML (não JSON, como no
   Requests) -- é o que um spider de verdade rastreia. Usado pelos testes
   funcionais/integração/aceitação, que rodam crawls reais.

3. Configura o `pytest-twisted` (plugin de terceiros, carregado automati-
   camente) para usar o mesmo reactor Twisted que o Scrapy 2.17 espera por
   padrão (asyncio) -- sem isso, o primeiro crawl real de cada sessão de
   teste falha com "installed reactor does not match the requested one".
"""

from __future__ import annotations

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

# --- 1. Garantir que estamos testando o código-fonte clonado ---------------

REPO_SRC = __file__.rsplit("\\", 1)[0] + "\\..\\..\\repositorios-originais\\scrapy"
sys.path.insert(0, REPO_SRC)

import scrapy  # noqa: E402

assert scrapy.__version__ == "2.17.0", (
    f"Esperava testar scrapy 2.17.0 (o checkout clonado), mas 'import scrapy' "
    f"resolveu para a versão {scrapy.__version__} em {scrapy.__file__!r}."
)

from scrapy.utils.test import get_reactor_settings  # noqa: E402


@pytest.fixture(scope="session")
def reactor_settings():
    """Settings mínimos necessários para o Crawler aceitar rodar no reactor
    Twisted que o pytest-twisted já instalou nesta sessão."""
    return get_reactor_settings()


@pytest.fixture
def crawler_factory(reactor_settings):
    """Devolve uma função que constrói um Crawler real (não um dublê) já com
    `.spider` populado -- o suficiente para testar middlewares isoladamente
    (from_crawler + process_request/process_response) sem precisar rodar o
    engine/reactor de verdade. Usa scrapy.utils.test.get_crawler, que é um
    utilitário de produção do próprio pacote (scrapy/utils/test.py), não um
    arquivo de teste do repositório."""
    from scrapy.utils.test import get_crawler

    def _build(spidercls=None, settings_dict=None):
        settings = {**reactor_settings, **(settings_dict or {})}
        crawler = get_crawler(spidercls, settings)
        crawler.spider = crawler._create_spider()
        return crawler

    return _build


# --- 2. Servidor HTML local usado pelos crawls reais ------------------------

_CONTADORES_INTERMITENTES: dict[str, int] = {}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def _html(self, status: int, body: str, extra_headers: dict | None = None) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path

        if path == "/":
            self._html(
                200,
                """<html><body>
                    <h1>Página inicial</h1>
                    <a href="/pagina2">segunda página</a>
                    <a href="/pagina3">terceira página</a>
                </body></html>""",
            )
            return

        if path == "/pagina2":
            self._html(200, "<html><body><h1>Página 2</h1></body></html>")
            return

        if path == "/pagina3":
            self._html(200, "<html><body><h1>Página 3</h1></body></html>")
            return

        if path == "/redirect-para-pagina2":
            self.send_response(302)
            self.send_header("Location", "/pagina2")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/erro-500":
            self._html(500, "<html><body>erro interno</body></html>")
            return

        if path == "/intermitente":
            # a chave "id" isola o contador por teste -- vários testes usam
            # esta mesma rota, e o servidor vive por toda a sessão de pytest,
            # então sem isolamento o contador de um teste "vazaria" pro outro
            chave = parsed.query or "default"
            _CONTADORES_INTERMITENTES[chave] = _CONTADORES_INTERMITENTES.get(chave, 0) + 1
            if _CONTADORES_INTERMITENTES[chave] <= 2:
                self._html(500, "<html><body>tente de novo</body></html>")
            else:
                self._html(200, "<html><body><h1>funcionou na 3a tentativa</h1></body></html>")
            return

        if path == "/protegido":
            auth = self.headers.get("Authorization", "")
            if auth == "Basic " + __import__("base64").b64encode(b"spider:segredo").decode():
                self._html(200, "<html><body><h1>acesso liberado</h1></body></html>")
            else:
                self._html(
                    401,
                    "<html><body>acesso negado</body></html>",
                    {"WWW-Authenticate": 'Basic realm="scrapy"'},
                )
            return

        if path.startswith("/profundo/"):
            nivel = int(path.rsplit("/", 1)[-1])
            self._html(
                200,
                f"""<html><body>
                    <h1>Nível {nivel}</h1>
                    <a href="/profundo/{nivel + 1}">mais fundo</a>
                </body></html>""",
            )
            return

        if path == "/produtos":
            self._html(
                200,
                """<html><body>
                    <div class="produto"><h2 class="nome">Cadeira</h2><span class="preco">199.90</span></div>
                    <div class="produto"><h2 class="nome">Mesa</h2><span class="preco">459.00</span></div>
                    <div class="produto"><h2 class="nome">Estante</h2><span class="preco">320.50</span></div>
                </body></html>""",
            )
            return

        self._html(404, "<html><body>não encontrado</body></html>")


@pytest.fixture(scope="session")
def html_server():
    """Sobe o servidor HTML local uma vez por sessão e devolve a base URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    yield base_url
    server.shutdown()
    server.server_close()
