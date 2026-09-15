"""
Testes de integração: grafos de dependência REAIS, com dois ou três
pacotes de verdade passando por export/create/install no cache local
(via TestClient) -- não é uma simulação do resolvedor, é o
internal/graph/* completo (grafo, binários, instalador) resolvendo
pacotes que realmente existem no cache, exatamente como resolveria
pacotes publicados num servidor remoto.
"""

from __future__ import annotations

import json


def _lib_header_only(nome, versao, requires=None, shared_option=False):
    linha_requires = f'    requires = "{requires}"\n' if requires else ""
    linha_options = '    options = {"shared": [True, False]}\n    default_options = {"shared": False}\n' \
        if shared_option else ""
    return f'''
from conan import ConanFile

class Pkg(ConanFile):
    name = "{nome}"
    version = "{versao}"
    package_type = "header-library"
{linha_requires}{linha_options}
    def package(self):
        pass

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
'''


def test_grafo_transitivo_de_tres_pacotes_resolve_e_cria_todos(client):
    client.save({"conanfile.py": _lib_header_only("liba", "1.0")})
    client.run("create .")

    client.save({"conanfile.py": _lib_header_only("libb", "1.0", requires="liba/1.0")}, clean_first=True)
    client.run("create .")

    client.save({"conanfile.py": _lib_header_only("app", "1.0", requires="libb/1.0")}, clean_first=True)
    client.run("create .")

    client.run("list app/1.0 --format=json")
    assert "app/1.0" in client.stdout


def test_version_range_resolve_para_a_versao_maxima_compativel(client):
    """Mata mutante que troque a ordenação de candidatos na resolução de
    range para pegar a mínima em vez da máxima compatível."""
    client.save({"conanfile.py": _lib_header_only("liba", "1.0")})
    client.run("create .")
    client.save({"conanfile.py": _lib_header_only("liba", "1.5")}, clean_first=True)
    client.run("create .")
    client.save({"conanfile.py": _lib_header_only("liba", "2.0")}, clean_first=True)
    client.run("create .")

    client.save({"conanfile.py": _lib_header_only("app", "1.0", requires="liba/[>=1.0 <2.0]")},
                clean_first=True)
    client.run("graph info . --format=json")
    grafo = json.loads(client.stdout)
    versoes = {n.get("version") for n in grafo["graph"]["nodes"].values() if n.get("name") == "liba"}
    assert versoes == {"1.5"}  # a maior dentro de [>=1.0 <2.0], excluindo a 2.0


def test_opcao_definida_na_linha_de_comando_se_propaga_para_a_dependencia(client):
    client.save({"conanfile.py": _lib_header_only("liba", "1.0", shared_option=True)})
    client.run("create .")

    client.save({"conanfile.py": _lib_header_only("app", "1.0", requires="liba/1.0")}, clean_first=True)
    client.run("graph info . -o liba/*:shared=True --format=json")
    grafo = json.loads(client.stdout)
    liba_node = next(n for n in grafo["graph"]["nodes"].values() if n.get("name") == "liba")
    assert liba_node["options"]["shared"] == "True"


def test_tool_requires_aparece_no_contexto_de_build_nao_no_de_host(client):
    """Mata mutante que remova a separação de contexto build/host na
    montagem do grafo para tool_requires."""
    client.save({"conanfile.py": _lib_header_only("mytool", "1.0")})
    client.run("create .")

    client.save({"conanfile.py": '''
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"

    def build_requirements(self):
        self.tool_requires("mytool/1.0")

    def package(self):
        pass
'''}, clean_first=True)
    client.run("graph info . --format=json")
    grafo = json.loads(client.stdout)
    mytool_node = next(n for n in grafo["graph"]["nodes"].values() if n.get("name") == "mytool")
    assert mytool_node["context"] == "build"


def test_lockfile_congela_a_versao_mesmo_apos_publicar_uma_mais_nova(client):
    """Como um build reprodutível: o lockfile fixa a resolução de hoje, e
    builds futuros usam a mesma versão mesmo que uma mais nova já exista
    no cache/remoto."""
    client.save({"conanfile.py": _lib_header_only("liba", "1.0")})
    client.run("create .")

    client.save({"conanfile.py": _lib_header_only("app", "1.0", requires="liba/[>=1.0]")},
                clean_first=True)
    client.run("lock create . --lockfile-out=app.lock")

    # agora uma versão mais nova de liba aparece, criada numa subpasta
    # separada -- sem tocar na pasta de "app", onde o lockfile acabou de
    # ser gravado (clean_first ali apagaria o próprio app.lock).
    client.save({"liba2/conanfile.py": _lib_header_only("liba", "2.0")})
    client.run("create liba2")

    client.run("graph info . --lockfile=app.lock --format=json")
    grafo = json.loads(client.stdout)
    versoes = {n.get("version") for n in grafo["graph"]["nodes"].values() if n.get("name") == "liba"}
    assert versoes == {"1.0"}  # o lockfile evitou pegar a 2.0
