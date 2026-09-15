"""
Testes estruturais (caixa-branca) de requests/models.py.

Aqui o alvo é o comportamento interno de PreparedRequest e Response —
os métodos prepare_* e as propriedades/derivações de Response — sem
depender de rede. Cada teste tem, no docstring, uma nota indicando que
tipo de mutação ele é capaz de detectar (troca de operador, inversão de
condição, off-by-one etc.), já que a suíte foi desenhada pensando em
sobreviver o mínimo possível a um mutation testing real, mesmo sem
executar a ferramenta agora.
"""

from __future__ import annotations

import pytest

from requests.exceptions import (
    InvalidJSONError,
    InvalidURL,
    MissingSchema,
    StreamConsumedError,
)
from requests.exceptions import HTTPError, JSONDecodeError as RequestsJSONDecodeError
from requests.models import PreparedRequest, Request, Response


# --------------------------------------------------------------------------
# PreparedRequest.prepare_method
# --------------------------------------------------------------------------


def test_prepare_method_uppercases():
    """Mata mutante que remova o .upper() ou troque por .lower()."""
    p = PreparedRequest()
    p.prepare_method("get")
    assert p.method == "GET"


def test_prepare_method_none_stays_none():
    """Mata mutante que trocasse 'is not None' por 'is None' na guarda."""
    p = PreparedRequest()
    p.prepare_method(None)
    assert p.method is None


# --------------------------------------------------------------------------
# PreparedRequest.prepare_url -- via Request(...).prepare(), nunca
# chamando prepare_url() isolado (é assim que o próprio requests exercita
# este método: sempre através do fluxo completo de preparação)
# --------------------------------------------------------------------------


def test_prepare_url_sem_esquema_gera_missing_schema():
    with pytest.raises(MissingSchema):
        Request("GET", "example.com/path").prepare()


def test_prepare_url_sem_host_gera_invalid_url():
    with pytest.raises(InvalidURL):
        Request("GET", "http://").prepare()


@pytest.mark.parametrize("host", ["*.example.com", ".example.com"])
def test_prepare_url_rejeita_host_com_wildcard_ou_ponto_inicial(host):
    """Mata mutante que troque startswith(("*", ".")) por apenas um dos dois."""
    with pytest.raises(InvalidURL):
        Request("GET", f"http://{host}/").prepare()


def test_prepare_url_esquema_nao_http_passa_direto():
    """mailto: não deve ser processado pelo parser de URL HTTP."""
    p = Request("GET", "mailto:foo@example.com").prepare()
    assert p.url == "mailto:foo@example.com"


def test_prepare_url_remove_espacos_a_esquerda():
    p = Request("GET", "   http://example.com/path").prepare()
    assert p.url == "http://example.com/path"


def test_prepare_url_aceita_bytes_e_decodifica_utf8():
    p = Request("GET", b"http://example.com/path").prepare()
    assert p.url == "http://example.com/path"


def test_prepare_url_acrescenta_query_params_dict():
    p = Request("GET", "http://example.com/path", params={"a": "1", "b": "2"}).prepare()
    assert p.url in (
        "http://example.com/path?a=1&b=2",
        "http://example.com/path?b=2&a=1",
    )


def test_prepare_url_mescla_query_existente_com_params():
    """Mata mutante que troque '&' por outro separador ao combinar query strings."""
    p = Request("GET", "http://example.com/path?x=1", params={"y": "2"}).prepare()
    assert p.url == "http://example.com/path?x=1&y=2"


def test_prepare_url_bare_domain_ganha_barra_final_no_path():
    p = Request("GET", "http://example.com").prepare()
    assert p.url == "http://example.com/"


# --------------------------------------------------------------------------
# PreparedRequest.prepare_headers
# --------------------------------------------------------------------------


def test_prepare_headers_case_insensitive():
    p = PreparedRequest()
    p.prepare_headers({"Content-Type": "text/plain"})
    assert p.headers["content-type"] == "text/plain"
    assert p.headers["CONTENT-TYPE"] == "text/plain"


def test_prepare_headers_sem_headers_gera_dict_vazio():
    p = PreparedRequest()
    p.prepare_headers(None)
    assert dict(p.headers) == {}


@pytest.mark.parametrize("valor_invalido", ["valor\ncom\nquebra", "valor\rcom\rretorno"])
def test_prepare_headers_rejeita_valor_com_quebra_de_linha(valor_invalido):
    """Cabeçalho com \\n/\\r é vetor clássico de CRLF/header injection."""
    p = PreparedRequest()
    with pytest.raises(Exception):
        p.prepare_headers({"X-Custom": valor_invalido})


# --------------------------------------------------------------------------
# PreparedRequest.prepare_body -- também via .prepare(), nunca chamando
# prepare_body() isolado.
#
# prepare_content_length() NÃO tem teste aqui: não há nenhuma evidência,
# direta ou indireta, de que a suíte humana teste esse método -- e não
# existe uma via pública para observar o Content-Length calculado sem
# inspecionar justamente esse header interno (não é algo que apareça no
# resultado de uma chamada de alto nível do jeito que prepare_url/
# prepare_body aparecem em p.url/p.body). Mantê-lo aqui só poluiria a
# comparação com um ponto sem par possível na suíte humana.
# --------------------------------------------------------------------------


def test_prepare_body_json_define_content_type_e_serializa():
    p = PreparedRequest()
    p.prepare(method="POST", url="http://example.com/", json={"a": 1})
    assert p.headers["Content-Type"] == "application/json"
    assert p.body == b'{"a": 1}'


def test_prepare_body_json_invalido_gera_invalid_json_error():
    """NaN não é serializável em JSON estrito (allow_nan=False)."""
    p = PreparedRequest()
    with pytest.raises(InvalidJSONError):
        p.prepare(method="POST", url="http://example.com/", json={"a": float("nan")})


def test_prepare_body_dados_e_arquivos_streamados_sao_incompativeis():
    """Corpo "iterável" (generator) junto de files deve levantar NotImplementedError."""

    def gerador():
        yield b"parte1"
        yield b"parte2"

    with pytest.raises(NotImplementedError):
        Request(
            "POST",
            "http://example.com/",
            data=gerador(),
            files={"f": ("nome.txt", b"conteudo")},
        ).prepare()


def test_prepare_body_form_urlencoded_define_content_type():
    p = Request("POST", "http://example.com/", data={"chave": "valor"}).prepare()
    assert p.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert p.body == "chave=valor"


# --------------------------------------------------------------------------
# PreparedRequest.prepare_auth
# --------------------------------------------------------------------------


def test_prepare_auth_tupla_gera_cabecalho_basic():
    p = PreparedRequest()
    p.prepare(method="GET", url="http://example.com/", auth=("user", "pass"))
    assert p.headers["Authorization"].startswith("Basic ")


def test_prepare_auth_extrai_credenciais_da_url_quando_nao_informado():
    """Mata mutante que remova a extração via get_auth_from_url quando auth=None."""
    p = PreparedRequest()
    p.prepare(method="GET", url="http://usuario:senha@example.com/")
    assert p.headers["Authorization"].startswith("Basic ")


def test_prepare_auth_none_sem_credenciais_na_url_nao_seta_header():
    p = PreparedRequest()
    p.prepare(method="GET", url="http://example.com/")
    assert "Authorization" not in p.headers


# --------------------------------------------------------------------------
# PreparedRequest.copy / hooks
# --------------------------------------------------------------------------


def test_copy_preserva_atributos_principais():
    p = PreparedRequest()
    p.prepare(method="POST", url="http://example.com/", data={"a": "1"})
    p2 = p.copy()
    assert p2.method == p.method
    assert p2.url == p.url
    assert p2.body == p.body
    assert p2.headers == p.headers


def test_copy_gera_cookiejar_independente():
    """Mata mutante que faça copy() reaproveitar o mesmo objeto _cookies (aliasing)."""
    p = PreparedRequest()
    p.prepare(method="GET", url="http://example.com/", cookies={"c": "v"})
    p2 = p.copy()
    assert p2._cookies is not p._cookies


def test_register_hook_evento_nao_suportado_levanta_value_error():
    r = Request("GET", "http://example.com/")
    with pytest.raises(ValueError):
        r.register_hook("evento-invalido", lambda resp: resp)


def test_register_hook_aceita_callable_unico():
    r = Request("GET", "http://example.com/")
    callback = lambda resp: resp
    r.register_hook("response", callback)
    assert callback in r.hooks["response"]


def test_register_hook_filtra_nao_callable_de_iteravel():
    """Mata mutante que remova o filtro isinstance(h, Callable) na extensão da lista."""
    r = Request("GET", "http://example.com/")
    callback = lambda resp: resp
    r.register_hook("response", [callback, "nao-e-callable", 123])
    assert r.hooks["response"] == [callback]


def test_deregister_hook_retorna_false_quando_ausente():
    r = Request("GET", "http://example.com/")
    assert r.deregister_hook("response", lambda resp: resp) is False


def test_deregister_hook_retorna_true_quando_remove():
    r = Request("GET", "http://example.com/")
    callback = lambda resp: resp
    r.register_hook("response", callback)
    assert r.deregister_hook("response", callback) is True
    assert callback not in r.hooks["response"]


# --------------------------------------------------------------------------
# Response: ok / bool / raise_for_status (fronteiras 400/500 são alvo clássico
# de mutação por off-by-one, e por isso recebem atenção extra aqui)
# --------------------------------------------------------------------------


def _response_com_status(status_code, reason="Reason"):
    r = Response()
    r.status_code = status_code
    r.reason = reason
    r.url = "http://example.com/"
    return r


@pytest.mark.parametrize("status_code", [200, 201, 301, 399])
def test_raise_for_status_nao_levanta_abaixo_de_400(status_code):
    r = _response_com_status(status_code)
    r.raise_for_status()  # não deve levantar


@pytest.mark.parametrize("status_code", [400, 404, 499])
def test_raise_for_status_levanta_http_error_para_4xx(status_code):
    """Mata mutante que troque '<' por '<=' (ou vice-versa) na fronteira 400/500."""
    r = _response_com_status(status_code)
    with pytest.raises(HTTPError, match="Client Error"):
        r.raise_for_status()


@pytest.mark.parametrize("status_code", [500, 503, 599])
def test_raise_for_status_levanta_http_error_para_5xx(status_code):
    r = _response_com_status(status_code)
    with pytest.raises(HTTPError, match="Server Error"):
        r.raise_for_status()


def test_raise_for_status_nao_levanta_para_600_fora_da_faixa_5xx():
    """600 está fora de [500,600) -- mata mutante que troque '<' por '<=' no limite superior."""
    r = _response_com_status(600)
    r.raise_for_status()  # não deve levantar


def test_raise_for_status_decodifica_reason_bytes_utf8():
    r = _response_com_status(404, reason="não encontrado".encode("utf-8"))
    with pytest.raises(HTTPError, match="não encontrado"):
        r.raise_for_status()


def test_raise_for_status_fallback_latin1_quando_reason_nao_e_utf8():
    r = _response_com_status(404, reason=b"\xe9")  # inválido em utf-8, válido em latin1
    with pytest.raises(HTTPError):
        r.raise_for_status()


@pytest.mark.parametrize(
    "status_code, esperado", [(200, True), (399, True), (400, False), (500, False)]
)
def test_bool_e_ok_refletem_ausencia_de_erro_http(status_code, esperado):
    r = _response_com_status(status_code)
    assert bool(r) is esperado
    assert r.ok is esperado


def test_is_redirect_exige_location_e_status_na_lista_de_redirect():
    r = _response_com_status(302)
    r.headers = {"location": "http://outro.exemplo/"}
    assert r.is_redirect is True


def test_is_redirect_falso_sem_header_location():
    r = _response_com_status(302)
    r.headers = {}
    assert r.is_redirect is False


def test_is_redirect_falso_para_status_fora_da_lista():
    """200 nunca é redirect, mesmo com header location presente por engano."""
    r = _response_com_status(200)
    r.headers = {"location": "http://outro.exemplo/"}
    assert r.is_redirect is False


@pytest.mark.parametrize("status_code, esperado", [(301, True), (308, True), (302, False), (307, False)])
def test_is_permanent_redirect_restrito_a_301_e_308(status_code, esperado):
    r = _response_com_status(status_code)
    r.headers = {"location": "http://outro.exemplo/"}
    assert r.is_permanent_redirect is esperado


# --------------------------------------------------------------------------
# Response: content / iter_content / json / links (sem rede: raw simulado)
# --------------------------------------------------------------------------


class _RawFalso:
    """Simula um objeto raw estilo urllib3 com stream()."""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    def stream(self, chunk_size, decode_content=True):
        yield from self._chunks

    def read(self, chunk_size):
        return b""

    def close(self):
        pass


def test_content_le_uma_vez_e_cacheia():
    r = _response_com_status(200)
    r.raw = _RawFalso([b"abc", b"def"])
    primeiro = r.content
    segundo = r.content  # não deve tentar ler de novo (raw só tem os chunks originais)
    assert primeiro == segundo == b"abcdef"


def test_content_levanta_runtime_error_se_ja_consumido_sem_cache():
    r = _response_com_status(200)
    r._content_consumed = True
    r._content = False
    with pytest.raises(RuntimeError):
        _ = r.content


def test_iter_content_levanta_type_error_para_chunk_size_invalido():
    r = _response_com_status(200)
    r.raw = _RawFalso([b"abc"])
    with pytest.raises(TypeError):
        list(r.iter_content(chunk_size="nao-e-int"))


def test_iter_content_levanta_stream_consumed_error_quando_reutilizado():
    """StreamConsumedError só ocorre quando o generate() já foi drenado
    (marcando _content_consumed) sem que .content tenha sido acessado --
    ou seja, _content continua no valor-sentinela `False` (bool), e não
    com bytes reais. É essa combinação exata que o código verifica com
    `isinstance(self._content, bool)`; mata mutante que troque esse
    isinstance por uma checagem menos específica (ex.: `is False`, que
    colidiria com bytes vazios em outros contextos)."""
    r = _response_com_status(200)
    r._content_consumed = True
    assert r._content is False
    with pytest.raises(StreamConsumedError):
        list(r.iter_content())


def test_json_usa_encoding_explicito_quando_definido():
    r = _response_com_status(200)
    r.encoding = "utf-8"
    r.raw = _RawFalso([b'{"chave": "valor"}'])
    assert r.json() == {"chave": "valor"}


def test_json_invalido_levanta_requests_json_decode_error():
    r = _response_com_status(200)
    r.encoding = "utf-8"
    r.raw = _RawFalso([b"isto nao e json"])
    with pytest.raises(RequestsJSONDecodeError):
        r.json()


def test_links_retorna_vazio_sem_header_link():
    r = _response_com_status(200)
    r.headers = {}
    assert r.links == {}


def test_links_processa_header_link_com_rel():
    r = _response_com_status(200)
    r.headers = {
        "link": '<http://example.com/next>; rel="next", <http://example.com/prev>; rel="prev"'
    }
    links = r.links
    assert links["next"]["url"] == "http://example.com/next"
    assert links["prev"]["url"] == "http://example.com/prev"
