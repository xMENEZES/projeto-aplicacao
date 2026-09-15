"""
Testes funcionais (caixa-preta) da API pública do Requests.

Diferente dos testes estruturais, aqui não olhamos para dentro dos métodos:
chamamos requests.get/post/... e requests.Session().request(...) como um
usuário real chamaria, e verificamos o resultado observável através do
servidor HTTP local (fixture `live_server`, em conftest.py). Nenhuma
requisição sai para a internet.
"""

from __future__ import annotations

import json

import pytest

import requests


def test_get_simples_retorna_200_e_echoa_metodo(live_server):
    resp = requests.get(f"{live_server}/echo")
    assert resp.status_code == 200
    assert resp.json()["method"] == "GET"


def test_get_com_params_monta_query_string(live_server):
    resp = requests.get(f"{live_server}/echo", params={"busca": "café com leite"})
    dados = resp.json()
    assert dados["args"]["busca"] == "café com leite"


def test_post_com_json_define_content_type_e_corpo(live_server):
    resp = requests.post(f"{live_server}/echo", json={"chave": "valor"})
    dados = resp.json()
    assert dados["method"] == "POST"
    assert dados["headers"]["Content-Type"] == "application/json"
    assert json.loads(dados["body"]) == {"chave": "valor"}


def test_post_com_data_dict_gera_form_urlencoded(live_server):
    resp = requests.post(f"{live_server}/echo", data={"campo": "valor com espaço"})
    dados = resp.json()
    assert dados["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert "campo=valor" in dados["body"]


def test_headers_customizados_chegam_ao_servidor(live_server):
    resp = requests.get(f"{live_server}/echo", headers={"X-Meu-Header": "abc123"})
    assert resp.json()["headers"]["X-Meu-Header"] == "abc123"


@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_metodos_http_diversos_chegam_com_verbo_correto(live_server, metodo):
    resp = getattr(requests, metodo)(f"{live_server}/echo")
    assert resp.json()["method"] == metodo.upper()


def test_head_nao_segue_redirecionamento_por_padrao(live_server):
    """Mata mutante que troque o default de allow_redirects em Session.head()."""
    resp = requests.head(f"{live_server}/redirect/1")
    assert resp.status_code == 302
    assert resp.is_redirect is True


@pytest.mark.parametrize(
    "codigo, esperado_ok", [(200, True), (201, True), (399, True), (400, False), (500, False)]
)
def test_status_code_reflete_no_atributo_ok(live_server, codigo, esperado_ok):
    resp = requests.get(f"{live_server}/status/{codigo}")
    assert resp.status_code == codigo
    assert resp.ok is esperado_ok


def test_raise_for_status_levanta_para_erro_do_servidor_real(live_server):
    resp = requests.get(f"{live_server}/status/500")
    with pytest.raises(requests.exceptions.HTTPError):
        resp.raise_for_status()


def test_gzip_e_descomprimido_de_forma_transparente(live_server):
    resp = requests.get(f"{live_server}/gzip")
    assert resp.headers["Content-Encoding"] == "gzip"
    assert resp.json() == {"gzipped": True, "content": "conteudo-original"}


def test_conteudo_grande_e_lido_integralmente_via_content(live_server):
    resp = requests.get(f"{live_server}/large", params={"bytes": 50_000})
    assert len(resp.content) == 50_000


def test_iter_content_em_stream_reconstroi_o_corpo_completo(live_server):
    resp = requests.get(f"{live_server}/large", params={"bytes": 33_333}, stream=True)
    pedacos = list(resp.iter_content(chunk_size=4096))
    corpo_reconstruido = b"".join(pedacos)
    assert len(corpo_reconstruido) == 33_333


def test_session_reaproveita_headers_padrao_entre_chamadas(live_server):
    with requests.Session() as s:
        s.headers.update({"X-Sessao": "presente"})
        r1 = s.get(f"{live_server}/echo")
        r2 = s.get(f"{live_server}/echo")
    assert r1.json()["headers"]["X-Sessao"] == "presente"
    assert r2.json()["headers"]["X-Sessao"] == "presente"


def test_timeout_muito_curto_levanta_read_timeout(live_server):
    """Servidor demora 0.3s para responder; timeout de leitura de 0.05s deve expirar."""
    with pytest.raises(requests.exceptions.ReadTimeout):
        requests.get(f"{live_server}/delay/0.3", timeout=0.05)
