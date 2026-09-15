"""
Testes de aceitação: escritos como histórias de usuário, no vocabulário de
quem consome a biblioteca (não de quem a implementa). Cada teste corresponde
a uma promessa que a documentação oficial do Requests faz ao desenvolvedor
("HTTP for Humans") e verifica se essa promessa realmente se cumpre de
ponta a ponta contra um servidor real (local). Não há inspeção de estado
interno aqui -- só entrada e saída observável, como o usuário veria.
"""

from __future__ import annotations

import time

import pytest

import requests
from requests.auth import HTTPBasicAuth


def test_desenvolvedor_faz_get_simples_e_le_json_da_resposta(live_server):
    """Como desenvolvedor, quero fazer um GET e ler a resposta como JSON
    sem precisar lidar manualmente com decodificação de bytes."""
    resposta = requests.get(f"{live_server}/echo")
    assert resposta.status_code == 200
    assert isinstance(resposta.json(), dict)


def test_desenvolvedor_envia_formulario_via_post(live_server):
    """Como desenvolvedor, quero enviar dados de um formulário HTML via POST
    passando apenas um dicionário Python, sem montar a string codificada
    manualmente."""
    resposta = requests.post(
        f"{live_server}/echo", data={"nome": "Maria", "cidade": "São Paulo"}
    )
    corpo = resposta.json()["body"]
    assert "nome=Maria" in corpo
    assert "cidade=S" in corpo  # cidade urlencoded, checagem tolerante a acentuação


def test_desenvolvedor_se_autentica_com_usuario_e_senha(live_server):
    """Como desenvolvedor, quero me autenticar num endpoint protegido apenas
    passando auth=(usuario, senha), sem montar o cabeçalho Basic eu mesmo."""
    resposta = requests.get(
        f"{live_server}/basic-auth/carla/minhasenha", auth=("carla", "minhasenha")
    )
    assert resposta.status_code == 200
    assert resposta.json()["authenticated"] is True


def test_desenvolvedor_usa_sessao_para_manter_cookies_entre_chamadas(live_server):
    """Como desenvolvedor, quero abrir uma Session e ter os cookies do
    servidor automaticamente reaproveitados nas próximas chamadas, sem
    precisar copiar cabeçalhos manualmente entre uma requisição e outra."""
    with requests.Session() as sessao:
        sessao.get(f"{live_server}/cookies/set", params={"carrinho": "42"})
        resposta_seguinte = sessao.get(f"{live_server}/cookies")
    assert "carrinho=42" in resposta_seguinte.json()["cookie_header_received"]


def test_desenvolvedor_detecta_falha_com_raise_for_status(live_server):
    """Como desenvolvedor, quero um jeito simples de transformar uma resposta
    de erro HTTP numa exceção Python, para usar try/except no meu código."""
    resposta = requests.get(f"{live_server}/status/404")
    with pytest.raises(requests.exceptions.HTTPError):
        resposta.raise_for_status()


def test_desenvolvedor_define_timeout_e_e_avisado_se_o_servidor_demorar(live_server):
    """Como desenvolvedor, quero poder definir um tempo máximo de espera e
    receber uma exceção clara se o servidor não responder a tempo, em vez
    de o programa travar indefinidamente."""
    inicio = time.monotonic()
    with pytest.raises(requests.exceptions.Timeout):
        requests.get(f"{live_server}/delay/1", timeout=0.1)
    duracao = time.monotonic() - inicio
    assert duracao < 1.0  # não esperou o segundo inteiro do servidor


def test_desenvolvedor_define_cabecalho_padrao_para_toda_a_sessao(live_server):
    """Como desenvolvedor, quero definir um cabeçalho (ex.: um token de API)
    uma única vez na Session e tê-lo enviado automaticamente em toda
    requisição feita a partir dela."""
    with requests.Session() as sessao:
        sessao.headers["Authorization"] = "Bearer meu-token-fixo"
        r1 = sessao.get(f"{live_server}/echo")
        r2 = sessao.get(f"{live_server}/echo")
    assert r1.json()["headers"]["Authorization"] == "Bearer meu-token-fixo"
    assert r2.json()["headers"]["Authorization"] == "Bearer meu-token-fixo"


def test_desenvolvedor_acompanha_o_historico_de_redirecionamentos(live_server):
    """Como desenvolvedor, quero conseguir inspecionar por quantos
    redirecionamentos minha requisição passou antes de chegar ao destino
    final, para diagnosticar por que uma URL antiga ainda funciona."""
    resposta = requests.get(f"{live_server}/redirect/3")
    assert len(resposta.history) == 3
    assert resposta.url.endswith("/echo")


def test_desenvolvedor_sobrescreve_autenticacao_padrao_da_sessao_por_chamada(live_server):
    """Como desenvolvedor, quero poder definir uma autenticação padrão na
    Session mas trocá-la pontualmente numa chamada específica, sem afetar
    as chamadas seguintes feitas pela mesma sessão."""
    with requests.Session() as sessao:
        sessao.auth = HTTPBasicAuth("usuario-padrao", "senha-errada")
        resposta_com_override = sessao.get(
            f"{live_server}/basic-auth/outro-usuario/outra-senha",
            auth=HTTPBasicAuth("outro-usuario", "outra-senha"),
        )
    assert resposta_com_override.status_code == 200
