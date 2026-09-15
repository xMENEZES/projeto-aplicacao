"""
Testes estruturais (caixa-branca) de requests/adapters.py e requests/auth.py.

adapters.py é testado no nível dos métodos auxiliares que não exigem uma
conexão de rede real (cert_verify, build_response, request_url,
proxy_headers, mapeamento de erros de proxy malformada). O caminho feliz
completo de HTTPAdapter.send() -- que de fato abre socket -- é coberto nos
testes de integração/aceitação, contra o servidor local.

auth.py é testado em Basic e Digest, incluindo o algoritmo de digest
RFC 2617 reimplementado em build_digest_header. HTTPProxyAuth não tem
teste aqui: zero evidência humana e, diferente de HTTPBasicAuth (que tem
uma via pública simples via `auth=(user, pass)`), não existe um jeito
igualmente direto de exercitá-la de ponta a ponta sem montar um proxy de
verdade -- mantê-la só como instanciação isolada da classe não teria
correspondente humano possível.

O "seta header Authorization" de HTTPBasicAuth também não está aqui:
foi para test_integracao.py, exercitado via `auth=(user, pass)` numa
chamada real (é assim que um usuário -- e a suíte humana -- de fato usa
essa classe; instanciá-la direto e chamar `auth(prepared_request)` é um
nível abaixo do que se observa na prática). A igualdade (`__eq__`) de
HTTPBasicAuth continua testada aqui direto: é comportamento de uma
classe pública e pequena, não um detalhe de implementação.
"""

from __future__ import annotations

import base64
import warnings
from types import SimpleNamespace

import pytest

from requests.adapters import HTTPAdapter
from requests.auth import AuthBase, HTTPBasicAuth, HTTPDigestAuth, _basic_auth_str
from requests.exceptions import InvalidProxyURL
from requests.models import PreparedRequest, Response


def _prepared_get(url="http://example.com/"):
    p = PreparedRequest()
    p.prepare(method="GET", url=url)
    return p


# --------------------------------------------------------------------------
# HTTPAdapter.cert_verify
# --------------------------------------------------------------------------


def test_cert_verify_https_com_verify_false_desativa_verificacao():
    adapter = HTTPAdapter()
    conn = SimpleNamespace()
    adapter.cert_verify(conn, "https://example.com/", verify=False, cert=None)
    assert conn.cert_reqs == "CERT_NONE"
    assert conn.ca_certs is None


def test_cert_verify_http_simples_ignora_verify_true():
    """Mata mutante que remova a condição 'url.lower().startswith(\"https\")'."""
    adapter = HTTPAdapter()
    conn = SimpleNamespace()
    adapter.cert_verify(conn, "http://example.com/", verify=True, cert=None)
    assert conn.cert_reqs == "CERT_NONE"


def test_cert_verify_https_com_verify_true_usa_bundle_padrao():
    adapter = HTTPAdapter()
    conn = SimpleNamespace()
    adapter.cert_verify(conn, "https://example.com/", verify=True, cert=None)
    assert conn.cert_reqs == "CERT_REQUIRED"
    assert conn.ca_certs is not None


def test_cert_verify_caminho_de_verify_inexistente_levanta_oserror():
    adapter = HTTPAdapter()
    conn = SimpleNamespace()
    with pytest.raises(OSError):
        adapter.cert_verify(
            conn, "https://example.com/", verify="/caminho/que/nao/existe.pem", cert=None
        )


def test_cert_verify_cert_tupla_define_cert_file_e_key_file_quando_existem(tmp_path):
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_text("dummy")
    key_file.write_text("dummy")
    adapter = HTTPAdapter()
    conn = SimpleNamespace()
    adapter.cert_verify(
        conn, "https://example.com/", verify=False, cert=(str(cert_file), str(key_file))
    )
    assert conn.cert_file == str(cert_file)
    assert conn.key_file == str(key_file)


def test_cert_verify_cert_file_inexistente_levanta_oserror():
    adapter = HTTPAdapter()
    conn = SimpleNamespace()
    with pytest.raises(OSError):
        adapter.cert_verify(
            conn, "https://example.com/", verify=False, cert="/nao/existe/cert.pem"
        )


# --------------------------------------------------------------------------
# HTTPAdapter.build_response
# --------------------------------------------------------------------------


class _RespostaUrllib3Falsa:
    def __init__(self, status, headers, reason):
        self.status = status
        self.headers = headers
        self.reason = reason


def test_build_response_mapeia_status_headers_e_reason():
    adapter = HTTPAdapter()
    req = _prepared_get()
    resp_falsa = _RespostaUrllib3Falsa(201, {"X-Teste": "1"}, "Created")
    resposta = adapter.build_response(req, resp_falsa)
    assert resposta.status_code == 201
    assert resposta.headers["x-teste"] == "1"  # case-insensitive
    assert resposta.reason == "Created"
    assert resposta.request is req
    assert resposta.connection is adapter


def test_build_response_status_ausente_cai_para_none():
    """Mata mutante que troque o getattr(resp, 'status', None) por acesso direto."""
    adapter = HTTPAdapter()
    req = _prepared_get()
    resp_falsa = SimpleNamespace(headers={}, reason="sem status")
    resposta = adapter.build_response(req, resp_falsa)
    assert resposta.status_code is None


# --------------------------------------------------------------------------
# HTTPAdapter.request_url
# --------------------------------------------------------------------------


def test_request_url_sem_proxy_retorna_apenas_path():
    adapter = HTTPAdapter()
    req = _prepared_get("http://example.com/caminho?x=1")
    assert adapter.request_url(req, None) == "/caminho?x=1"


def test_request_url_com_proxy_http_retorna_url_absoluta():
    """Mata mutante que remova a distinção entre requisição via proxy e direta."""
    adapter = HTTPAdapter()
    req = _prepared_get("http://example.com/caminho")
    url = adapter.request_url(req, {"http": "http://meu-proxy:8080"})
    assert url == "http://example.com/caminho"


def test_request_url_https_via_proxy_ainda_usa_apenas_path():
    """HTTPS tunelado por proxy usa CONNECT, então a URL enviada é só o path."""
    adapter = HTTPAdapter()
    req = _prepared_get("https://example.com/caminho")
    url = adapter.request_url(req, {"https": "http://meu-proxy:8080"})
    assert url == "/caminho"


# --------------------------------------------------------------------------
# HTTPAdapter.proxy_headers
# --------------------------------------------------------------------------


def test_proxy_headers_sem_credenciais_retorna_vazio():
    adapter = HTTPAdapter()
    assert adapter.proxy_headers("http://meu-proxy:8080") == {}


def test_proxy_headers_com_credenciais_gera_proxy_authorization():
    adapter = HTTPAdapter()
    headers = adapter.proxy_headers("http://usuario:senha@meu-proxy:8080")
    assert headers["Proxy-Authorization"].startswith("Basic ")
    decoded = base64.b64decode(headers["Proxy-Authorization"].split(" ", 1)[1]).decode()
    assert decoded == "usuario:senha"


# --------------------------------------------------------------------------
# HTTPAdapter -- mapeamento de proxy malformada (sem tocar rede)
# --------------------------------------------------------------------------


def test_get_connection_proxy_sem_host_levanta_invalid_proxy_url():
    adapter = HTTPAdapter()
    req = _prepared_get("http://example.com/")
    with pytest.raises(InvalidProxyURL):
        adapter.get_connection_with_tls_context(req, verify=True, proxies={"http": "http://"})


def test_get_connection_deprecated_emite_deprecation_warning():
    adapter = HTTPAdapter()
    with pytest.warns(DeprecationWarning):
        adapter.get_connection("http://example.com/", proxies=None)


# --------------------------------------------------------------------------
# auth.HTTPBasicAuth
# --------------------------------------------------------------------------


def test_basic_auth_str_formato_esperado():
    assert _basic_auth_str("user", "pass") == "Basic " + base64.b64encode(b"user:pass").decode()


def test_basic_auth_str_usuario_nao_string_emite_deprecation_warning():
    with pytest.warns(DeprecationWarning):
        _basic_auth_str(123, "pass")


def test_http_basic_auth_igualdade_por_usuario_e_senha():
    assert HTTPBasicAuth("a", "b") == HTTPBasicAuth("a", "b")
    assert HTTPBasicAuth("a", "b") != HTTPBasicAuth("a", "c")


def test_auth_base_call_levanta_not_implemented():
    with pytest.raises(NotImplementedError):
        AuthBase()(_prepared_get())


# --------------------------------------------------------------------------
# auth.HTTPDigestAuth
# --------------------------------------------------------------------------


def _digest_pronto_para_desafio(qop="auth", algorithm=None):
    auth = HTTPDigestAuth("user", "pass")
    auth.init_per_thread_state()
    auth._thread_local.chal = {
        "realm": "area-restrita",
        "nonce": "abc123nonce",
        "qop": qop,
    }
    if algorithm:
        auth._thread_local.chal["algorithm"] = algorithm
    return auth


def test_build_digest_header_formato_com_qop_auth():
    auth = _digest_pronto_para_desafio(qop="auth")
    header = auth.build_digest_header("GET", "http://example.com/recurso")
    assert header.startswith("Digest ")
    assert 'username="user"' in header
    assert 'realm="area-restrita"' in header
    assert 'nonce="abc123nonce"' in header
    assert 'uri="/recurso"' in header
    assert "nc=00000001" in header
    assert 'qop="auth"' in header


def test_build_digest_header_incrementa_nonce_count_em_chamadas_repetidas():
    """Mata mutante que remova o incremento de nonce_count para nonces repetidos."""
    auth = _digest_pronto_para_desafio(qop="auth")
    auth.build_digest_header("GET", "http://example.com/recurso")
    header2 = auth.build_digest_header("GET", "http://example.com/recurso")
    assert "nc=00000002" in header2


def test_build_digest_header_sem_qop_nao_inclui_campo_qop():
    auth = _digest_pronto_para_desafio(qop=None)
    header = auth.build_digest_header("GET", "http://example.com/recurso")
    assert "qop=" not in header


def test_build_digest_header_algoritmo_nao_suportado_retorna_none():
    auth = _digest_pronto_para_desafio(qop="auth", algorithm="ALGORITMO-INEXISTENTE")
    assert auth.build_digest_header("GET", "http://example.com/recurso") is None


def test_handle_401_ignora_resposta_que_nao_e_erro_cliente():
    """Mata mutante que troque a faixa 400<=status<500 na guarda de handle_401."""
    auth = HTTPDigestAuth("user", "pass")
    auth.init_per_thread_state()
    resp = Response()
    resp.status_code = 200
    resultado = auth.handle_401(resp)
    assert resultado is resp
    assert auth._thread_local.num_401_calls == 1


def test_call_registra_hooks_de_response():
    auth = HTTPDigestAuth("user", "pass")
    req = _prepared_get()
    resultado = auth(req)
    hook_names = [h.__name__ for h in resultado.hooks["response"]]
    assert "handle_401" in hook_names
    assert "handle_redirect" in hook_names


def test_digest_auth_igualdade_por_usuario_e_senha():
    assert HTTPDigestAuth("a", "b") == HTTPDigestAuth("a", "b")
    assert HTTPDigestAuth("a", "b") != HTTPDigestAuth("a", "c")
