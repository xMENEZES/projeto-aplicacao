"""
v2 — técnica funcional (caixa-preta): classes de equivalência e valor
limite, derivadas do PLANO_DE_TESTE.md (seções 1, 3 e 6).

Cada teste está rotulado com o ID de caso (CTxx) do plano. Este arquivo
reaproveita o conftest.py da pasta-mãe (sys.path para repositorios-originais/requests/, fixture
live_server) -- pytest resolve conftest.py hierarquicamente, então nada
precisa ser duplicado aqui.
"""

from __future__ import annotations

import warnings

import pytest

from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from requests.exceptions import HTTPError, InvalidURL, MissingSchema
from requests.models import PreparedRequest, Response


# ==========================================================================
# Seção 1 do plano — PreparedRequest.prepare_url
# ==========================================================================


def test_ct01_esquema_ausente_e_classe_invalida():
    """CT01 — classe inválida: esquema ausente."""
    p = PreparedRequest()
    with pytest.raises(MissingSchema):
        p.prepare_url("example.com/x", None)


def test_ct02_host_ausente_e_classe_invalida():
    """CT02 — classe inválida: host ausente."""
    p = PreparedRequest()
    with pytest.raises(InvalidURL):
        p.prepare_url("http://", None)


def test_ct03_host_com_wildcard_e_classe_invalida():
    """CT03 — classe inválida: host começa com '*'."""
    p = PreparedRequest()
    with pytest.raises(InvalidURL):
        p.prepare_url("http://*.x.com/", None)


def test_ct04_host_nao_ascii_codificavel_e_classe_valida():
    """CT04 — classe válida: host não-ASCII, mas codificável via IDNA."""
    p = PreparedRequest()
    p.prepare_url("http://café.com/", None)  # não deve levantar
    assert p.url is not None
    assert "xn--" in p.url  # IDNA-encoded


def test_ct05_esquema_nao_http_e_passthrough_valido():
    """CT05 — classe válida: esquema não-HTTP passa direto (mailto:)."""
    p = PreparedRequest()
    p.prepare_url("mailto:a@b.com", None)
    assert p.url == "mailto:a@b.com"


def test_ct06_espacos_a_esquerda_sao_removidos_classe_valida():
    """CT06 — classe válida: espaços à esquerda são removidos antes do parsing."""
    p = PreparedRequest()
    p.prepare_url("   http://x.com/", None)
    assert p.url == "http://x.com/"


def test_ct07_tipo_bytes_e_classe_valida_de_entrada():
    """CT07 — classe válida: url como bytes é decodificado (UTF-8) e processado."""
    p = PreparedRequest()
    p.prepare_url(b"http://x.com/", None)
    assert p.url == "http://x.com/"


# ==========================================================================
# Seção 3 do plano — Response.raise_for_status (valor limite: 399/400/499/500/599/600)
# ==========================================================================


def _resposta_com_status(status_code):
    r = Response()
    r.status_code = status_code
    r.reason = "reason"
    r.url = "http://example.com/"
    return r


@pytest.mark.parametrize(
    "id_caso, status_code, deve_levantar, trecho_mensagem",
    [
        ("CT13", 399, False, None),
        ("CT14", 400, True, "Client Error"),
        ("CT15", 499, True, "Client Error"),
        ("CT16", 500, True, "Server Error"),
        ("CT17", 599, True, "Server Error"),
        ("CT18", 600, False, None),
    ],
)
def test_raise_for_status_valor_limite(id_caso, status_code, deve_levantar, trecho_mensagem):
    """CT13–CT18 — valor limite nas seis fronteiras da faixa dupla 400/500."""
    resposta = _resposta_com_status(status_code)
    if deve_levantar:
        with pytest.raises(HTTPError, match=trecho_mensagem):
            resposta.raise_for_status()
    else:
        resposta.raise_for_status()  # não deve levantar


# ==========================================================================
# Seção 6 do plano — HTTPBasicAuth / HTTPDigestAuth (classes de equivalência)
# ==========================================================================


def test_ct31_username_nao_string_e_classe_limitrofe_aceita_com_aviso():
    """CT31 — classe limítrofe: username int, funciona mas emite DeprecationWarning."""
    auth = HTTPBasicAuth(123, "senha")
    p = PreparedRequest()
    p.prepare(method="GET", url="http://example.com/")
    with pytest.warns(DeprecationWarning):
        resultado = auth(p)
    assert resultado.headers["Authorization"].startswith("Basic ")


def test_ct32_qop_auth_int_e_classe_invalida_nao_suportada():
    """CT32 — classe inválida: qop='auth-int' não é suportado, devolve None."""
    auth = HTTPDigestAuth("user", "pass")
    auth.init_per_thread_state()
    auth._thread_local.chal = {"realm": "r", "nonce": "n", "qop": "auth-int"}
    assert auth.build_digest_header("GET", "http://x.com/recurso") is None


def test_ct33_algoritmo_desconhecido_e_classe_invalida():
    """CT33 — classe inválida: algoritmo Digest desconhecido, devolve None."""
    auth = HTTPDigestAuth("user", "pass")
    auth.init_per_thread_state()
    auth._thread_local.chal = {
        "realm": "r", "nonce": "n", "qop": "auth", "algorithm": "INEXISTENTE",
    }
    assert auth.build_digest_header("GET", "http://x.com/recurso") is None
