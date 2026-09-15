"""
Testes estruturais (caixa-branca) de requests/sessions.py.

Foco nos métodos de SessionRedirectMixin (get_redirect_target,
should_strip_auth, rebuild_method) e no roteamento de adapters da
própria Session (mount/get_adapter). rebuild_method é exercitado através
de redirects reais contra o servidor local (conftest.py::live_server),
nunca chamado isoladamente -- é assim que o próprio requests o exercita
(dentro de resolve_redirects, disparado por uma requisição de alto
nível), então é nesse nível que o teste também deve viver.

merge_setting/merge_hooks (funções internas de composição de
configuração) não têm teste aqui: são detalhes de implementação que
nenhuma suíte, humana ou não, testaria isoladamente -- não há via
pública para observar o resultado da mesclagem sem já estar testando
outra coisa (a própria Session em uso).
"""

from __future__ import annotations

import pytest

from requests.adapters import HTTPAdapter
from requests.exceptions import InvalidSchema
from requests.models import Response
from requests.sessions import Session
from requests.status_codes import codes


# --------------------------------------------------------------------------
# SessionRedirectMixin.get_redirect_target
# --------------------------------------------------------------------------


def _resposta(status_code, headers=None):
    r = Response()
    r.status_code = status_code
    r.headers = headers or {}
    return r


def test_get_redirect_target_retorna_none_quando_nao_e_redirect():
    s = Session()
    resp = _resposta(200, {"location": "http://example.com/"})
    assert s.get_redirect_target(resp) is None


def test_get_redirect_target_extrai_location_quando_e_redirect():
    s = Session()
    resp = _resposta(codes.found, {"location": "http://example.com/novo"})
    assert s.get_redirect_target(resp) == "http://example.com/novo"


@pytest.mark.parametrize(
    "status_code", [codes.moved, codes.found, codes.other, codes.temporary_redirect, codes.permanent_redirect]
)
def test_get_redirect_target_reconhece_todos_os_status_de_redirect(status_code):
    s = Session()
    resp = _resposta(status_code, {"location": "http://example.com/x"})
    assert s.get_redirect_target(resp) == "http://example.com/x"


# --------------------------------------------------------------------------
# SessionRedirectMixin.should_strip_auth
# --------------------------------------------------------------------------


def test_should_strip_auth_mesmo_host_nao_remove():
    s = Session()
    assert s.should_strip_auth("http://example.com/a", "http://example.com/b") is False


def test_should_strip_auth_host_diferente_remove():
    """Mata mutante que troque '!=' por '==' na comparação de hostname."""
    s = Session()
    assert s.should_strip_auth("http://example.com/a", "http://outro.com/a") is True


def test_should_strip_auth_permite_upgrade_http_para_https_porta_padrao():
    """Caso especial documentado: http->https em portas padrão não remove auth."""
    s = Session()
    assert s.should_strip_auth("http://example.com/a", "https://example.com/a") is False


def test_should_strip_auth_remove_quando_porta_muda_com_mesmo_esquema():
    s = Session()
    assert (
        s.should_strip_auth("http://example.com:8080/a", "http://example.com:9090/a")
        is True
    )


def test_should_strip_auth_nao_remove_quando_apenas_porta_padrao_implicita():
    s = Session()
    assert s.should_strip_auth("http://example.com/a", "http://example.com:80/a") is False


# --------------------------------------------------------------------------
# SessionRedirectMixin.rebuild_method -- via redirects reais contra o
# servidor local, nunca chamando s.rebuild_method(p, resp) direto. O
# efeito é observado no método da requisição final (resp.request.method),
# do jeito que qualquer consumidor da biblioteca observaria.
# --------------------------------------------------------------------------


def test_rebuild_method_303_vira_get_exceto_head(live_server):
    with Session() as s:
        resp = s.post(f"{live_server}/redirect-303-see-other", data={"x": "1"})
    assert resp.request.method == "GET"


def test_rebuild_method_303_preserva_head(live_server):
    """Mata mutante que remova a exceção para HEAD em ambas as regras (303 e 302)."""
    with Session() as s:
        resp = s.head(f"{live_server}/redirect-303-see-other", allow_redirects=True)
    assert resp.request.method == "HEAD"


def test_rebuild_method_302_vira_get_para_post(live_server):
    with Session() as s:
        resp = s.post(f"{live_server}/redirect/1", data={"x": "1"})
    assert resp.request.method == "GET"


def test_rebuild_method_301_so_afeta_post(live_server):
    """Mata mutante que aplique a regra do 301 também a PUT/PATCH/DELETE."""
    with Session() as s:
        resp = s.put(f"{live_server}/redirect-301-permanent", data={"x": "1"})
    assert resp.request.method == "PUT"


def test_rebuild_method_301_post_vira_get(live_server):
    with Session() as s:
        resp = s.post(f"{live_server}/redirect-301-permanent", data={"x": "1"})
    assert resp.request.method == "GET"


def test_rebuild_method_get_permanece_get_em_qualquer_redirect(live_server):
    with Session() as s:
        resp = s.get(f"{live_server}/redirect/1")
    assert resp.request.method == "GET"


# --------------------------------------------------------------------------
# Session.mount / get_adapter -- roteamento por prefixo mais específico
# --------------------------------------------------------------------------


def test_get_adapter_escolhe_prefixo_mais_especifico():
    """Mata mutante que inverta a ordenação por tamanho de prefixo em mount()."""
    s = Session()
    generico = HTTPAdapter()
    especifico = HTTPAdapter()
    s.mount("http://", generico)
    s.mount("http://api.example.com", especifico)

    assert s.get_adapter("http://api.example.com/rota") is especifico
    assert s.get_adapter("http://outro.example.com/rota") is generico


def test_get_adapter_sem_prefixo_correspondente_levanta_invalid_schema():
    s = Session()
    s.adapters.clear()
    with pytest.raises(InvalidSchema):
        s.get_adapter("ftp://example.com/arquivo")


def test_mount_prefixo_case_insensitive():
    s = Session()
    s.adapters.clear()
    a = HTTPAdapter()
    s.mount("HTTP://", a)
    assert s.get_adapter("http://example.com/") is a


# --------------------------------------------------------------------------
# Session.merge_environment_settings
# --------------------------------------------------------------------------


def test_merge_environment_settings_mescla_proxies_padrao_da_sessao():
    s = Session()
    s.trust_env = False  # evita depender de variáveis de ambiente reais da máquina
    s.proxies = {"http": "http://proxy-da-sessao:8080"}
    settings = s.merge_environment_settings(
        "http://example.com/", proxies={}, stream=None, verify=None, cert=None
    )
    assert settings["proxies"]["http"] == "http://proxy-da-sessao:8080"


def test_merge_environment_settings_verify_explicito_da_requisicao_prevalece():
    s = Session()
    s.trust_env = False
    s.verify = True
    settings = s.merge_environment_settings(
        "http://example.com/", proxies={}, stream=None, verify=False, cert=None
    )
    assert settings["verify"] is False
