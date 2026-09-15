"""
Configuração compartilhada da suíte de testes do Requests.

Este conftest faz duas coisas antes de qualquer teste rodar:

1. Garante que `import requests` resolva para a cópia exata do código-fonte
   clonado em `repositorios-originais/requests` (versão 2.34.2 do checkout usado na análise
   de arquitetura), e não para qualquer `requests` que já esteja instalado
   via pip no ambiente (há uma versão 2.32.4 instalada como dependência de
   outras ferramentas). Isso é essencial: o objetivo é testar exatamente o
   código que foi lido e mapeado, não uma versão qualquer da biblioteca.

2. Sobe um servidor HTTP local, em memória, que serve como "dublê" de
   servidor real para os testes funcionais, de integração e de aceitação.
   Nenhum teste desta suíte depende de rede externa — tudo roda contra
   127.0.0.1, o que torna os testes determinísticos e seguros de rodar
   em qualquer máquina, sem custo de rede e sem depender de terceiros
   (como o antigo httpbin.org, que o próprio projeto Requests usa nos
   docstrings, mas que não é confiável para uma suíte automatizada).
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

# --- 1. Garantir que estamos testando o código-fonte clonado ---------------

REPO_SRC = Path(__file__).parent.parent.parent / "repositorios-originais" / "requests"
sys.path.insert(0, str(REPO_SRC))

import requests  # noqa: E402  (import precisa vir depois do sys.path.insert)

assert requests.__version__ == "2.34.2", (
    f"Esperava testar requests 2.34.2 (o checkout clonado), mas "
    f"'import requests' resolveu para a versão {requests.__version__} em "
    f"{requests.__file__!r}. Verifique se algum outro 'requests' instalado "
    f"via pip está na frente do repo_src/ no sys.path."
)


# --- 2. Servidor HTTP local usado por todos os testes que fazem I/O real ---

DIGEST_REALM = "suite-de-testes"
DIGEST_NONCE = "d1e9a7c6b5f4e3d2c1b0a9988776655"


def _parse_authorization_pairs(header_value: str) -> dict[str, str]:
    """Extrai os pares key="value" de um cabeçalho Authorization/WWW-Authenticate."""
    pairs = {}
    # remove o esquema ("Digest " / "Basic ") antes do primeiro espaço
    _, _, rest = header_value.partition(" ")
    for item in rest.split(","):
        item = item.strip()
        if "=" not in item:
            continue
        key, _, value = item.partition("=")
        pairs[key.strip()] = value.strip().strip('"')
    return pairs


def _expected_digest_response(
    username: str, password: str, method: str, uri: str, nc: str, cnonce: str
) -> str:
    def md5(text: str) -> str:
        return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()

    ha1 = md5(f"{username}:{DIGEST_REALM}:{password}")
    ha2 = md5(f"{method}:{uri}")
    return md5(f"{ha1}:{DIGEST_NONCE}:{nc}:{cnonce}:auth:{ha2}")


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # silencia o log padrão no stdout
        pass

    # -- helpers de resposta -------------------------------------------------

    def _send_json(self, status: int, payload: dict, extra_headers: dict | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(length) if length else b""

    def _echo_payload(self, method: str) -> dict:
        parsed = urlsplit(self.path)
        body = self._read_body()
        try:
            decoded_body = body.decode("utf-8")
        except UnicodeDecodeError:
            decoded_body = base64.b64encode(body).decode("ascii")
        return {
            "method": method,
            "path": parsed.path,
            "args": {k: v[-1] for k, v in parse_qs(parsed.query).items()},
            "headers": {k: v for k, v in self.headers.items()},
            "body": decoded_body,
            "body_length": len(body),
        }

    # -- roteamento genérico ---------------------------------------------

    def _dispatch(self, method: str) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/echo":
            self._send_json(200, self._echo_payload(method))
            return

        if path.startswith("/status/"):
            code = int(path.rsplit("/", 1)[-1])
            self._read_body()
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path.startswith("/redirect/"):
            self._read_body()
            n = int(path.rsplit("/", 1)[-1])
            target = f"/redirect/{n - 1}" if n > 1 else "/echo"
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/redirect-303-see-other":
            self._read_body()
            self.send_response(303)
            self.send_header("Location", "/echo")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/redirect-301-permanent":
            self._read_body()
            self.send_response(301)
            self.send_header("Location", "/echo")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/redirect-cross-host":
            self._read_body()
            # redireciona para outra "origem" (porta diferente simulada por host distinto)
            self.send_response(302)
            self.send_header("Location", qs.get("to", ["/echo"])[0])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/cookies/set":
            self._read_body()
            self.send_response(302)
            self.send_header("Location", "/cookies")
            for name, values in qs.items():
                self.send_header("Set-Cookie", f"{name}={values[-1]}; Path=/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/cookies":
            cookie_header = self.headers.get("Cookie", "")
            self._send_json(200, {"cookie_header_received": cookie_header})
            return

        if path.startswith("/basic-auth/"):
            _, _, user, pwd = path.split("/")
            auth = self.headers.get("Authorization", "")
            expected = "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode()
            self._read_body()
            if auth == expected:
                self._send_json(200, {"authenticated": True, "user": user})
            else:
                self._send_json(
                    401,
                    {"authenticated": False},
                    {"WWW-Authenticate": 'Basic realm="fake"'},
                )
            return

        if path.startswith("/digest-auth/"):
            _, _, user, pwd = path.split("/")
            auth = self.headers.get("Authorization", "")
            self._read_body()
            if not auth.lower().startswith("digest "):
                self._send_json(
                    401,
                    {"authenticated": False},
                    {
                        "WWW-Authenticate": (
                            f'Digest realm="{DIGEST_REALM}", nonce="{DIGEST_NONCE}", qop="auth"'
                        )
                    },
                )
                return
            fields = _parse_authorization_pairs(auth)
            expected = _expected_digest_response(
                user, pwd, method, fields.get("uri", path), fields.get("nc", "0"), fields.get("cnonce", "")
            )
            if fields.get("response") == expected and fields.get("username") == user:
                self._send_json(200, {"authenticated": True, "user": user})
            else:
                self._send_json(401, {"authenticated": False})
            return

        if path == "/gzip":
            payload = json.dumps({"gzipped": True, "content": "conteudo-original"}).encode("utf-8")
            compressed = gzip.compress(payload)
            self._read_body()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(compressed)))
            self.end_headers()
            self.wfile.write(compressed)
            return

        if path.startswith("/delay/"):
            seconds = float(path.rsplit("/", 1)[-1])
            self._read_body()
            time.sleep(seconds)
            self._send_json(200, {"delayed_seconds": seconds})
            return

        if path == "/large":
            self._read_body()
            size = int(qs.get("bytes", ["20000"])[0])
            body = b"x" * size
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # rota desconhecida
        self._read_body()
        self._send_json(404, {"error": "rota nao mapeada no servidor de teste", "path": path})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self._dispatch("OPTIONS")

    def do_HEAD(self):
        self._dispatch("HEAD")


@pytest.fixture(scope="session")
def live_server():
    """Sobe o servidor de teste local uma única vez por sessão e devolve a base URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    yield base_url
    server.shutdown()
    server.server_close()
