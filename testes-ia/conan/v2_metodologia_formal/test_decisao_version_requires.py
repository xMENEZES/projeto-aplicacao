"""
v2 — técnica estrutural via tabela de decisão: Version.__lt__ (seção 1,
continua por instanciação direta -- é uma classe de valor pura) e
deduplicação de Requirement via __eq__/__hash__ (seção 2, agora via
TestClient/grafo real -- self.requires()/self.build_requires()/
self.tool_requires() num conanfile de verdade, nunca chamando
Requirements() diretamente). Casos CT01-CT11 do PLANO_DE_TESTE.md.
"""

from __future__ import annotations

import pytest

from conan.internal.model.version import Version


# ==========================================================================
# Seção 1 — Version.__lt__
# ==========================================================================


@pytest.mark.parametrize(
    "id_caso, regra, menor, maior, resultado_esperado",
    [
        ("CT01", "V1", "1.0-alpha", "1.0-beta", True),
        ("CT02", "V2", "1.0-alpha", "1.0", True),
        ("CT03", "V3", "2.0-alpha", "1.0", False),
        ("CT04", "V4", "1.0", "1.0-alpha", False),
        ("CT05", "V5", "1.0", "2.0-alpha", True),
        ("CT06", "V6", "1.0", "2.0", True),
    ],
)
def test_version_lt_tabela_de_decisao(id_caso, regra, menor, maior, resultado_esperado):
    """CT01-CT06 — as 6 regras da tabela de decisão de ordenação com
    pré-release. V2/V4 são o par que garante que uma pré-release só é
    "menor" quando comparada com a MESMA versão base -- não com qualquer
    versão maior/menor que por acaso também seja pré-release."""
    assert (Version(menor) < Version(maior)) is resultado_esperado


# ==========================================================================
# Seção 2 — deduplicação de Requirement (__eq__/__hash__), via
# self.requires()/self.build_requires()/self.tool_requires() num
# conanfile real, resolvido por `conan create`
# ==========================================================================


def _publicar(client, nome, versao):
    conanfile = f"""
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
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create .")


def test_ct07_regra_r1_dois_requires_normais_mesmo_nome_colidem(client):
    _publicar(client, "zlib", "1.0")
    _publicar(client, "zlib", "2.0")
    conanfile_app = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"

    def requirements(self):
        self.requires("zlib/1.0")
        self.requires("zlib/2.0")

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile_app}, clean_first=True)
    client.run("create .", assert_error=True)
    assert "Duplicated requirement" in client.out


def test_ct08_regra_r2_dois_tool_require_mesmo_nome_colidem(client):
    """tool_requires() tem run=True por padrão -- é essa sobreposição de
    'run' que causa a colisão, não o nome sozinho."""
    _publicar(client, "cmake", "1.0")
    _publicar(client, "cmake", "2.0")
    conanfile_app = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"

    def build_requirements(self):
        self.tool_requires("cmake/1.0")
        self.tool_requires("cmake/2.0")

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile_app}, clean_first=True)
    client.run("create .", assert_error=True)
    assert "Duplicated requirement" in client.out


def test_ct09_regra_r3_dois_build_require_puros_mesmo_nome_nao_colidem(client):
    """ACHADO confirmado antes de escrever o teste: build_requires() usa
    run=None (equivalente a False) por padrão -- diferente de
    tool_requires() -- sem headers, libs OU run sobrepondo, duas versões
    diferentes do mesmo nome não são consideradas o mesmo Requirement."""
    _publicar(client, "cmake", "1.0")
    _publicar(client, "cmake", "2.0")
    conanfile_app = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"

    def build_requirements(self):
        self.build_requires("cmake/1.0")
        self.build_requires("cmake/2.0")

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile_app}, clean_first=True)
    client.run("create .")  # não deve levantar


def test_ct10_regra_r4_requires_normal_e_build_require_mesmo_nome_nao_colidem(client):
    """Mata mutante que remova 'self.build' do hash/eq -- sem isso, um
    requires() e um build_requires() do mesmo nome colidiriam."""
    _publicar(client, "cmake", "1.0")
    conanfile_app = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"

    def requirements(self):
        self.requires("cmake/1.0")

    def build_requirements(self):
        self.build_requires("cmake/1.0")

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile_app}, clean_first=True)
    client.run("create .")  # não deve levantar


def test_ct11_regra_r5_nomes_diferentes_nunca_colidem(client):
    _publicar(client, "zlib", "1.0")
    _publicar(client, "openssl", "1.0")
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
