"""
v2 — técnica estrutural via tabela de decisão: _PackageOptions._set(),
duas tabelas independentes (congelamento e marcação "importante"). Casos
CT12-CT19 do PLANO_DE_TESTE.md (seção 3) -- agora exercitados via
TestClient/grafo real (perfil + `-o` da CLI + default_options de
receita), nunca instanciando _PackageOptions direto. É assim que essas
regras de composição de opções são observáveis de fora: pelo valor que
o grafo resolvido mostra para o pacote dependido, não por uma chamada
isolada a `_set()`.
"""

from __future__ import annotations

import json


def _lib_com_shared_e_fpic(nome="liba"):
    return f"""
from conan import ConanFile

class Pkg(ConanFile):
    name = "{nome}"
    version = "1.0"
    package_type = "header-library"
    options = {{"shared": ["True", "False"], "fpic": ["True", "False"]}}
    default_options = {{"shared": "False", "fpic": "True"}}

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
"""


def _shared_resolvido(client):
    grafo = json.loads(client.stdout)
    liba_node = next(n for n in grafo["graph"]["nodes"].values() if n.get("name") == "liba")
    return liba_node["options"]["shared"]


def _lib_config_options_shared(valor):
    """liba com config_options() (roda ANTES do congelamento das opções
    -- ao contrário de configure(), que roda DEPOIS) tentando definir a
    PRÓPRIA opção shared. Confirmado por execução direta: mudar
    self.options.shared dentro de configure() SEMPRE levanta se o valor
    for diferente do já resolvido (default_options conta como "já
    resolvido") -- mesmo sem nenhum -o externo -- porque o congelamento
    já aconteceu antes de configure() rodar. config_options() é o método
    que roda ainda sem esse congelamento."""
    return f"""
from conan import ConanFile

class Pkg(ConanFile):
    name = "liba"
    version = "1.0"
    package_type = "header-library"
    options = {{"shared": ["True", "False"], "fpic": ["True", "False"]}}
    default_options = {{"shared": "False", "fpic": "True"}}

    def config_options(self):
        self.options.shared = "{valor}"

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
"""


def _lib_configure_opcao_sem_default(valor):
    """liba declara 'extra' sem default_options -- seu valor está
    indefinido (None) no momento em que o congelamento acontece.
    configure() define 'extra' por conta própria: F2 diz que redefinir
    um valor ainda None (nunca definido) é permitido mesmo já congelado."""
    return f"""
from conan import ConanFile

class Pkg(ConanFile):
    name = "liba"
    version = "1.0"
    package_type = "header-library"
    options = {{"shared": ["True", "False"], "extra": ["True", "False"]}}
    default_options = {{"shared": "False"}}

    def configure(self):
        self.options.extra = "{valor}"

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
"""


def _extra_resolvido(client):
    grafo = json.loads(client.stdout)
    liba_node = next(n for n in grafo["graph"]["nodes"].values() if n.get("name") == "liba")
    return liba_node["options"]["extra"]


def _lib_configure_shared(valor):
    """liba com configure() (roda DEPOIS do congelamento) tentando
    (re)definir a PRÓPRIA opção shared, já com um default_options
    prévio -- é o cenário de F3/F4."""
    return f"""
from conan import ConanFile

class Pkg(ConanFile):
    name = "liba"
    version = "1.0"
    package_type = "header-library"
    options = {{"shared": ["True", "False"], "fpic": ["True", "False"]}}
    default_options = {{"shared": "False", "fpic": "True"}}

    def configure(self):
        self.options.shared = "{valor}"

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
"""


def _app_default_options_shared(valor):
    return f"""
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"
    requires = "liba/1.0"
    default_options = {{"liba/*:shared": "{valor}"}}

    def package(self):
        pass
"""


# ==========================================================================
# Tabela de congelamento (F1-F4)
# ==========================================================================


def test_ct12_regra_f1_sem_congelamento_ainda_permite_mudar(client):
    """F1 — config_options() roda ANTES do congelamento das opções
    (diferente de configure(), que roda depois) -- por isso pode definir
    o valor livremente, mesmo já existindo um default_options."""
    client.save({"conanfile.py": _lib_config_options_shared("True")})
    client.run("create . --format=json")
    assert _shared_resolvido(client) == "True"


def test_ct13_regra_f2_valor_ainda_nunca_definido_permite_definir_mesmo_congelado(client):
    """F2 — 'extra' não tem default_options -- seu valor é None quando o
    congelamento acontece. configure() (já depois do congelamento)
    define 'extra' pela primeira vez -- permitido, porque não havia
    valor anterior para conflitar."""
    client.save({"conanfile.py": _lib_configure_opcao_sem_default("True")})
    client.run("create . --format=json")
    assert _extra_resolvido(client) == "True"


def test_ct14_regra_f3_redefinir_com_o_mesmo_valor_permite(client):
    """F3 — a linha de comando já fixou 'shared=True'; o configure() da
    própria receita redefine para o MESMO valor -- não deveria levantar."""
    client.save({"conanfile.py": _lib_configure_shared("True")})
    client.run("create . -o shared=True --format=json")
    assert _shared_resolvido(client) == "True"


def test_ct15_regra_f4_redefinir_com_valor_diferente_levanta(client):
    """F4 — a linha de comando já fixou 'shared=True'; o configure() da
    própria receita tenta mudar para 'False' -- deve levantar
    ConanException. Mata mutante que remova a comparação
    'current_value != value' na checagem de congelamento."""
    client.save({"conanfile.py": _lib_configure_shared("False")})
    client.run("create . -o shared=True", assert_error=True)
    assert "ERROR" in client.out


# ==========================================================================
# Tabela de marcação "importante" (I1-I4)
# ==========================================================================


def test_ct16_regra_i1_importante_da_linha_de_comando_sobrescreve_importante_do_perfil(client):
    """I1 — perfil marca 'shared' como importante=True; a linha de
    comando (composta depois do perfil) marca importante=False -- o
    importante mais recente vence."""
    client.save({"conanfile.py": _lib_com_shared_e_fpic()})
    client.run("create .")
    client.save(
        {
            "conanfile.py": _app_default_options_shared("True"),
            "perfil_importante": "[options]\nliba/*:shared!=True\n",
        },
        clean_first=True,
    )
    client.run(
        "graph info . -pr:h=./perfil_importante -o liba/*:shared!=False --format=json"
    )
    assert _shared_resolvido(client) == "False"


def test_ct17_regra_i2_importante_sobrescreve_default_options_normal_do_consumidor(client):
    """I2 — o consumidor pede 'shared=True' via default_options (normal);
    a linha de comando marca 'shared!=False' (importante) -- o
    importante vence, mesmo o normal aparecendo na própria receita."""
    client.save({"conanfile.py": _lib_com_shared_e_fpic()})
    client.run("create .")
    client.save({"conanfile.py": _app_default_options_shared("True")}, clean_first=True)
    client.run("graph info . -o liba/*:shared!=False --format=json")
    assert _shared_resolvido(client) == "False"


def test_ct18_regra_i3_normal_nao_sobrescreve_importante(client):
    """I3 — mata mutante que remova a checagem 'or not v.important' --
    sem ela, o default_options normal do consumidor (shared=True)
    conseguiria sobrescrever o valor marcado como importante pelo
    perfil (shared!=False)."""
    client.save({"conanfile.py": _lib_com_shared_e_fpic()})
    client.run("create .")
    client.save(
        {
            "conanfile.py": _app_default_options_shared("True"),
            "perfil_importante": "[options]\nliba/*:shared!=False\n",
        },
        clean_first=True,
    )
    client.run("graph info . -pr:h=./perfil_importante --format=json")
    assert _shared_resolvido(client) == "False"  # permanece o importante, não o normal


def test_ct19_regra_i4_normal_sobrescreve_normal(client):
    """I4 — sem nenhum marcador importante em jogo, o default_options do
    consumidor (camada mais externa) sobrescreve o default_options da
    própria receita de liba (camada mais interna) normalmente."""
    client.save({"conanfile.py": _lib_com_shared_e_fpic()})
    client.run("create .")  # liba's próprio default: shared=False
    client.save({"conanfile.py": _app_default_options_shared("True")}, clean_first=True)
    client.run("graph info . --format=json")
    assert _shared_resolvido(client) == "True"
