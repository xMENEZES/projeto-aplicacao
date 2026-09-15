"""
Testes funcionais (caixa-preta) da CLI do Conan -- comandos individuais,
chamados exatamente como um usuário chamaria no terminal, via TestClient
(que roda a CLI de verdade dentro do processo de teste, contra um cache e
uma pasta de trabalho isolados e temporários).
"""

from __future__ import annotations

import json

import pytest

from conan.errors import ConanException


def _receita_header_only(nome="hello", versao="1.0"):
    return f'''
from conan import ConanFile

class Pkg(ConanFile):
    name = "{nome}"
    version = "{versao}"
    package_type = "header-library"

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
'''


def test_conan_new_gera_um_template_de_receita(client):
    client.run("new cmake_lib -d name=mylib -d version=1.0")
    conanfile = client.load("conanfile.py")
    assert 'name = "mylib"' in conanfile
    assert 'version = "1.0"' in conanfile


def test_conan_create_empacota_uma_receita_header_only(client):
    client.save({"conanfile.py": _receita_header_only()})
    client.run("create .")
    assert "ERROR" not in client.out
    client.run("list hello/1.0")
    assert "hello/1.0" in client.out


def test_conan_create_com_receita_invalida_falha_com_mensagem_clara(client):
    client.save({"conanfile.py": "isto nao e python valido {{{"})
    client.run("create .", assert_error=True)
    assert "Unable to load conanfile" in client.out or "SyntaxError" in client.out


def test_conan_list_mostra_pacote_apos_create(client):
    client.save({"conanfile.py": _receita_header_only()})
    client.run("create .")
    client.run("list hello/1.0")
    assert "hello/1.0" in client.out


def test_conan_list_formato_json_e_valido_e_contem_o_pacote(client):
    client.save({"conanfile.py": _receita_header_only()})
    client.run("create .")
    client.run("list hello/1.0 --format=json")
    dados = json.loads(client.stdout)
    # a estrutura exata do json de list é aninhada por remoto/referência;
    # o essencial aqui é que "hello/1.0" apareça em algum lugar da saída.
    assert "hello/1.0" in json.dumps(dados)


def test_conan_remove_apaga_o_pacote_do_cache(client):
    client.save({"conanfile.py": _receita_header_only()})
    client.run("create .")
    client.run("remove hello/1.0 -c")  # -c: sem confirmação interativa
    client.run("list hello/1.0")
    assert "not found" in client.out


def test_conan_profile_show_nao_falha_e_lista_o_profile_default(client):
    client.run("profile show")
    assert "[settings]" in client.out


def test_conan_config_home_mostra_a_pasta_de_cache_correta(client):
    client.run("config home")
    assert client.cache_folder in client.out


def test_conan_graph_info_lista_o_pacote_sem_instalar_nada(client):
    """`conan graph info` faz a resolução completa do grafo sem
    efetivamente instalar/empacotar nada no cache -- útil para inspecionar
    antes de agir."""
    client.save({"conanfile.py": _receita_header_only()})
    client.run("export .")  # só exporta a receita, sem empacotar binário
    client.save({"conanfile.py": '''
from conan import ConanFile

class App(ConanFile):
    requires = "hello/1.0"
'''}, clean_first=True)
    client.run("graph info . --format=json")
    grafo = json.loads(client.stdout)
    nomes = {n["name"] for n in grafo["graph"]["nodes"].values() if n.get("name")}
    assert "hello" in nomes
