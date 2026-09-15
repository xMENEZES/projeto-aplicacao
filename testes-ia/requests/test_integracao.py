"""
Testes de integração: combinam Session + Adapter + Auth + Cookies + Hooks
funcionando juntos contra o servidor HTTP local, do jeito que um usuário
real do Requests os combina na prática. A diferença em relação aos testes
funcionais é o foco em como os COMPONENTES conversam entre si (ex.:
o hook registrado por HTTPDigestAuth disparando uma segunda requisição
sozinho, ou o cookie devolvido por um redirect sendo propagado para a
requisição seguinte), e não apenas o resultado final de uma chamada isolada.
"""

from __future__ import annotations

import base64

import pytest

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPDigestAuth
from requests.exceptions import TooManyRedirects


# --------------------------------------------------------------------------
# Session + Adapter customizado (mecanismo de extensão central do Requests)
# --------------------------------------------------------------------------


class _AdapterContador(HTTPAdapter):
    """Adapter que apenas conta quantas vezes send() foi chamado, delegando
    o trabalho real para HTTPAdapter. Usado para comprovar que o roteamento
    Session -> Adapter (via mount/get_adapter) está de fato entregando a
    requisição para o adapter escolhido, e não para outro."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chamadas = 0

    def send(self, *args, **kwargs):
        self.chamadas += 1
        return super().send(*args, **kwargs)


def test_session_encaminha_requisicoes_para_o_adapter_mais_especifico(live_server):
    adapter_especifico = _AdapterContador()
    with requests.Session() as s:
        s.mount(live_server, adapter_especifico)  # prefixo mais específico que "http://"
        s.get(f"{live_server}/echo")
        s.get(f"{live_server}/echo")
    assert adapter_especifico.chamadas == 2


# --------------------------------------------------------------------------
# Cookies: persistidos via redirect e reenviados na próxima requisição
# --------------------------------------------------------------------------


def test_cookie_definido_via_redirect_e_reenviado_na_proxima_chamada(live_server):
    with requests.Session() as s:
        resp = s.get(f"{live_server}/cookies/set", params={"sessao": "abc123"})
        # o servidor redireciona /cookies/set -> /cookies; a resposta final já
        # deve ter visto o cookie que a própria Session extraiu do redirect.
        assert "sessao=abc123" in resp.json()["cookie_header_received"]

        resp2 = s.get(f"{live_server}/echo")
        assert "sessao=abc123" in resp2.json()["headers"].get("Cookie", "")


# --------------------------------------------------------------------------
# Basic Auth de ponta a ponta -- via a tupla (user, pass) em auth=, que é
# como requests documenta e como a maioria do código real usa; a
# biblioteca converte a tupla em HTTPBasicAuth internamente, então isso
# já exercita a classe sem precisar instanciá-la explicitamente.
# --------------------------------------------------------------------------


def test_basic_auth_preemptivo_autentica_de_primeira(live_server):
    resp = requests.get(f"{live_server}/basic-auth/alice/segredo123", auth=("alice", "segredo123"))
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True
    esperado = "Basic " + base64.b64encode(b"alice:segredo123").decode()
    assert resp.request.headers["Authorization"] == esperado


def test_basic_auth_credenciais_erradas_recebe_401(live_server):
    resp = requests.get(f"{live_server}/basic-auth/alice/segredo123", auth=("alice", "errada"))
    assert resp.status_code == 401


# --------------------------------------------------------------------------
# Digest Auth de ponta a ponta: desafio 401 -> hook dispara retry -> 200
# --------------------------------------------------------------------------


def test_digest_auth_completa_o_desafio_via_hook_automaticamente(live_server):
    """Este é o teste que mais expõe a integração real: HTTPDigestAuth
    registra handle_401 como hook de 'response' (models.py), a Session
    dispatcha esse hook em send() (sessions.py), e o hook por sua vez
    chama r.connection.send(...) usando o MESMO adapter que originou a
    resposta -- três módulos diferentes cooperando numa única chamada
    de alto nível."""
    resp = requests.get(
        f"{live_server}/digest-auth/bob/senha-forte",
        auth=HTTPDigestAuth("bob", "senha-forte"),
    )
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True
    # a resposta 401 do desafio inicial deve estar registrada no histórico
    assert any(r.status_code == 401 for r in resp.history)


def test_digest_auth_senha_errada_nao_completa_o_desafio(live_server):
    resp = requests.get(
        f"{live_server}/digest-auth/bob/senha-forte",
        auth=HTTPDigestAuth("bob", "senha-errada"),
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------
# Redirecionamentos: cadeia, limite e conversão de método
# --------------------------------------------------------------------------


def test_cadeia_de_redirecionamentos_e_seguida_ate_o_destino_final(live_server):
    resp = requests.get(f"{live_server}/redirect/4")
    assert resp.status_code == 200
    assert resp.json()["path"] == "/echo"
    assert len(resp.history) == 4
    assert all(r.status_code == 302 for r in resp.history)


def test_limite_de_redirecionamentos_estoura_too_many_redirects(live_server):
    with requests.Session() as s:
        s.max_redirects = 2
        with pytest.raises(TooManyRedirects):
            s.get(f"{live_server}/redirect/5")


def test_redirect_303_converte_post_em_get_no_destino(live_server):
    """Integra PreparedRequest (método original POST) + SessionRedirectMixin
    (rebuild_method) + servidor real, confirmando que o efeito ponta a ponta
    é o método correto chegando no destino."""
    resp = requests.post(f"{live_server}/redirect-303-see-other", data={"x": "1"})
    assert resp.json()["method"] == "GET"


def test_allow_redirects_false_expoe_proxima_requisicao_via_response_next(live_server):
    resp = requests.get(f"{live_server}/redirect/1", allow_redirects=False)
    assert resp.status_code == 302
    assert resp.next is not None
    assert resp.next.url.endswith("/echo")


# --------------------------------------------------------------------------
# Hooks definidos pelo usuário, integrados ao ciclo de vida real de send()
# --------------------------------------------------------------------------


def test_hook_de_response_definido_pelo_usuario_e_chamado_com_a_resposta_real(live_server):
    respostas_vistas = []

    def registra(resp, **kwargs):
        respostas_vistas.append(resp.status_code)

    requests.get(f"{live_server}/echo", hooks={"response": registra})
    assert respostas_vistas == [200]


def test_hook_pode_substituir_a_resposta_entregue_ao_usuario(live_server):
    resposta_falsa = requests.models.Response()
    resposta_falsa.status_code = 599

    def substitui(resp, **kwargs):
        return resposta_falsa

    resultado = requests.get(f"{live_server}/echo", hooks={"response": substitui})
    assert resultado.status_code == 599
