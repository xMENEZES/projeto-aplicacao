"""
Testes estruturais (caixa-branca) de conan/internal/model/requires.py --
Requirement e Requirements -- exercitados via TestClient/grafo real
(requires="pkg/1.0" declarado num conanfile, resolvido por `conan
create`/`graph info`), nunca instanciando Requirement/Requirements
isolados. É este nível -- o que uma receita real declara e o grafo
resolve -- que tem correspondente humano possível.

Duas coisas que a v1 testava diretamente contra o construtor de
Requirement não têm teste aqui:

- A validação cruzada visible/consistent no `__init__`: self.requires()/
  self.tool_requires() (a única via pública para criar um Requirement)
  não expõem 'consistent' como parâmetro independente de 'visible' --
  não há caminho público para montar essa combinação, em nenhum nível.
- Os defaults finos de headers/libs/visible/run por tipo de requires
  (normal/build/test/tool): não há garantia de que esses flags por-aresta
  fiquem expostos de forma estável no `graph info --format=json`, então
  testá-los "no mesmo nível" arriscaria um teste frágil por motivo
  errado. O que sobra abaixo -- deduplicação e separação de contexto
  build/host -- é o comportamento que de fato se observa de fora, via
  grafo resolvido ou erro da CLI.
"""

from __future__ import annotations

import json


def _pkg(nome, versao="1.0"):
    return f"""
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
"""


# --------------------------------------------------------------------------
# Deduplicação / conflito -- baseada em (nome, build), não na versão inteira
# --------------------------------------------------------------------------


def test_requires_duplicado_pelo_mesmo_nome_levanta_mesmo_com_versoes_diferentes(client):
    """ACHADO preservado da v1: Requirement.__hash__ é (ref.name, build) --
    duas versões diferentes do MESMO pacote, ambas como requires()
    normais no mesmo conanfile, são consideradas o MESMO requirement
    para fins de deduplicação. Chamar requires() duas vezes para "zlib",
    em versões diferentes, levanta ConanException por "Duplicated
    requirement" -- não é a versão que conflita, é o nome."""
    client.save({"conanfile.py": _pkg("zlib", "1.2.11")})
    client.run("create .")
    client.save({"conanfile.py": _pkg("zlib", "1.3.1")}, clean_first=True)
    client.run("create .")

    conanfile_app = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"

    def requirements(self):
        self.requires("zlib/1.2.11")
        self.requires("zlib/1.3.1")

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile_app}, clean_first=True)
    client.run("create .", assert_error=True)
    assert "Duplicated requirement" in client.out


def test_require_normal_e_tool_require_do_mesmo_nome_nao_conflitam(client):
    """Mata mutante que remova 'self.build' do hash/eq de Requirement --
    sem isso, um requires() e um tool_requires() do mesmo nome
    colidiriam. Observável no grafo: dois nós "cmake" distintos, um em
    cada contexto, em vez de um erro de duplicidade."""
    client.save({"conanfile.py": _pkg("cmake", "1.0")})
    client.run("create .")

    conanfile_app = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"

    def requirements(self):
        self.requires("cmake/1.0")

    def build_requirements(self):
        self.tool_requires("cmake/1.0")

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile_app}, clean_first=True)
    client.run("graph info . --format=json")
    grafo = json.loads(client.stdout)
    nos_cmake = [n for n in grafo["graph"]["nodes"].values() if n.get("name") == "cmake"]
    assert len(nos_cmake) == 2  # host (requires) + build (tool_requires), não colidem


def test_requires_de_nomes_diferentes_nunca_conflitam(client):
    client.save({"conanfile.py": _pkg("zlib", "1.0")})
    client.run("create .")
    client.save({"conanfile.py": _pkg("openssl", "1.0")}, clean_first=True)
    client.run("create .")

    conanfile_app = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"
    requires = "zlib/1.0", "openssl/1.0"

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile_app}, clean_first=True)
    client.run("create .")  # não deve levantar


# --------------------------------------------------------------------------
# tool_requires() -- contexto de build, não de host
# --------------------------------------------------------------------------


def test_tool_require_aparece_no_contexto_de_build(client):
    """Mata mutante que remova a separação de contexto build/host na
    montagem do grafo para tool_requires."""
    client.save({"conanfile.py": _pkg("mytool", "1.0")})
    client.run("create .")

    conanfile_app = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"

    def build_requirements(self):
        self.tool_requires("mytool/1.0")

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile_app}, clean_first=True)
    client.run("graph info . --format=json")
    grafo = json.loads(client.stdout)
    mytool_node = next(n for n in grafo["graph"]["nodes"].values() if n.get("name") == "mytool")
    assert mytool_node["context"] == "build"


# --------------------------------------------------------------------------
# Requirements() -- construção a partir de `requires = [...]` malformado
# --------------------------------------------------------------------------


def test_requires_como_tupla_em_vez_de_string_levanta_erro(client):
    """Um `requires = [("zlib", "1.2.11")]` (tupla, não string) é um erro
    comum de quem confunde a sintaxe -- deve falhar de forma clara, não
    silenciosamente ou com um traceback interno confuso."""
    conanfile = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"
    requires = [("zlib", "1.2.11")]

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile})
    client.run("create .", assert_error=True)
    assert "ERROR" in client.out


def test_requires_nao_iteravel_levanta_erro(client):
    """`requires = 123` nem é iterável -- outro erro comum, caminho de
    validação diferente do caso da tupla acima (aqui nem chega a montar
    uma lista de itens para validar um por um)."""
    conanfile = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"
    requires = 123

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile})
    client.run("create .", assert_error=True)
    assert "ERROR" in client.out
