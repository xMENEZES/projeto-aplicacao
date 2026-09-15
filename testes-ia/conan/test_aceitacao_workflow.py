"""
Testes de aceitação: histórias de usuário, no vocabulário de quem usa o
Conan para gerenciar dependências C/C++ -- não de quem implementa o
gerenciador de pacotes. Todos rodam contra o cache local real via
TestClient, com pacotes "header-only" fictícios (sem precisar de nenhum
compilador C/C++ instalado).
"""

from __future__ import annotations

import json


def _lib(nome, versao, requires=None, options=None, default_options=None):
    linha_requires = f'    requires = "{requires}"\n' if requires else ""
    linha_options = f"    options = {options}\n" if options else ""
    linha_defaults = f"    default_options = {default_options}\n" if default_options else ""
    return f'''
from conan import ConanFile

class Pkg(ConanFile):
    name = "{nome}"
    version = "{versao}"
    package_type = "header-library"
{linha_requires}{linha_options}{linha_defaults}
    def package(self):
        pass

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
'''


def test_desenvolvedor_cria_uma_lib_e_reutiliza_em_outro_pacote_sem_servidor_remoto(client):
    """Como desenvolvedor, quero empacotar uma biblioteca localmente e
    consumi-la de outro projeto meu, sem precisar publicar em nenhum
    servidor Artifactory/remoto antes -- só para experimentar localmente."""
    client.save({"conanfile.py": _lib("minha_lib", "1.0")})
    client.run("create .")

    client.save({"conanfile.py": _lib("meu_app", "1.0", requires="minha_lib/1.0")},
                clean_first=True)
    client.run("create .")
    assert "ERROR" not in client.out


def test_desenvolvedor_deixa_o_conan_escolher_a_versao_mais_recente_compativel(client):
    """Como desenvolvedor, quero declarar uma faixa de versões aceitável
    (ex.: '>=1.0 <2.0') e deixar o Conan escolher a melhor opção
    disponível, em vez de fixar manualmente qual versão exata usar."""
    client.save({"conanfile.py": _lib("motor_grafico", "1.0")})
    client.run("create .")
    client.save({"conanfile.py": _lib("motor_grafico", "1.4")}, clean_first=True)
    client.run("create .")

    client.save({"conanfile.py": _lib("jogo", "1.0", requires="motor_grafico/[>=1.0 <2.0]")},
                clean_first=True)
    client.run("install . --format=json", redirect_stdout="grafo.json")
    grafo = json.loads(client.load("grafo.json"))
    versao_escolhida = next(
        n["version"] for n in grafo["graph"]["nodes"].values() if n.get("name") == "motor_grafico"
    )
    assert versao_escolhida == "1.4"


def test_desenvolvedor_troca_uma_opcao_so_na_instalacao_sem_editar_a_receita(client):
    """Como desenvolvedor, quero poder pedir uma variante diferente de uma
    dependência (ex.: a versão compartilhada em vez da estática) só
    passando -o na linha de comando, sem editar o conanfile de ninguém."""
    client.save({"conanfile.py": _lib(
        "compressor", "1.0",
        options='{"shared": [True, False]}',
        default_options='{"shared": False}',
    )})
    client.run("create .")

    client.save({"conanfile.py": _lib("arquivador", "1.0", requires="compressor/1.0")},
                clean_first=True)
    client.run("graph info . -o compressor/*:shared=True --format=json")
    grafo = json.loads(client.stdout)
    node = next(n for n in grafo["graph"]["nodes"].values() if n.get("name") == "compressor")
    assert node["options"]["shared"] == "True"


def test_desenvolvedor_inspeciona_o_grafo_antes_de_instalar_qualquer_coisa(client):
    """Como desenvolvedor, quero ver quais pacotes seriam necessários para
    o meu projeto ANTES de efetivamente baixar/compilar nada -- um
    'dry run' da resolução de dependências."""
    client.save({"conanfile.py": _lib("base", "1.0")})
    client.run("create .")

    client.save({"conanfile.py": _lib("cliente", "1.0", requires="base/1.0")}, clean_first=True)
    client.run("graph info . --format=json")
    grafo = json.loads(client.stdout)
    nomes = {n.get("name") for n in grafo["graph"]["nodes"].values()}
    assert "base" in nomes
    assert "cliente" in nomes


def test_desenvolvedor_congela_as_versoes_de_hoje_para_builds_reproduziveis(client):
    """Como desenvolvedor, quero poder gerar um lockfile com as versões
    resolvidas hoje, e usá-lo depois para garantir que um build futuro
    (em outra máquina, ou meses depois) resolva exatamente as mesmas
    versões, mesmo que versões mais novas das dependências já existam."""
    client.save({"conanfile.py": _lib("nucleo", "1.0")})
    client.run("create .")

    client.save({"conanfile.py": _lib("servico", "1.0", requires="nucleo/[>=1.0]")},
                clean_first=True)
    client.run("lock create . --lockfile-out=servico.lock")
    conteudo_lock = client.load("servico.lock")
    assert "nucleo/1.0" in conteudo_lock
