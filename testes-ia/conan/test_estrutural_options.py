"""
Testes estruturais (caixa-branca) de conan/internal/model/options.py --
_PackageOption, _PackageOptions e Options -- agora exercitados via
TestClient com receitas reais declarando `options`/`default_options`,
nunca instanciando as classes internas do modelo direto. É assim que
qualquer receita Conan observa esse comportamento: através de
`self.options.<nome>` dentro de um conanfile real e das flags `-o` da
CLI, não construindo um `_PackageOption`/`_PackageOptions` isolado.
"""

from __future__ import annotations

import json

import pytest

_CONANFILE_BOOL = """
from conan import ConanFile

class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
    options = {"ligado": ["True", "False", "1", "0", "off", "qualquer-coisa", "FALSE"]}
    default_options = {"ligado": "True"}

    def package_info(self):
        self.output.info(f"LIGADO_BOOL={bool(self.options.ligado)}")

    def package(self):
        pass
"""


def _lib_com_shared(nome, versao="1.0"):
    return f"""
from conan import ConanFile

class Pkg(ConanFile):
    name = "{nome}"
    version = "{versao}"
    package_type = "header-library"
    options = {{"shared": ["True", "False"]}}
    default_options = {{"shared": "False"}}

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
"""


# --------------------------------------------------------------------------
# _PackageOption.__bool__ -- convenção de valores falsos (case-insensitive)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valor, esperado",
    [
        ("True", "True"),
        ("1", "True"),
        ("qualquer-coisa", "True"),
        ("False", "False"),
        ("0", "False"),
        ("off", "False"),
        ("FALSE", "False"),  # case-insensitive
    ],
)
def test_option_bool_segue_convencao_de_valores_falsos(client, valor, esperado):
    """Mata mutante que remova algum item de _falsey_options ou troque o
    'not in' -- observado via bool(self.options.<opt>) em package_info(),
    exatamente como uma receita real decidiria remover libdirs/bindirs
    para uma opção 'header_only', por exemplo."""
    client.save({"conanfile.py": _CONANFILE_BOOL})
    client.run(f"create . -o ligado={valor}")
    assert f"LIGADO_BOOL={esperado}" in client.out


# --------------------------------------------------------------------------
# _PackageOptions -- validação (opção desconhecida / valor fora da lista)
# --------------------------------------------------------------------------


def test_option_desconhecida_na_linha_de_comando_levanta_erro(client):
    """Mata mutante que remova a checagem de _constrained em
    _ensure_exists -- passar -o para uma opção que a receita não declara
    deve falhar, não ser silenciosamente ignorado."""
    client.save({"conanfile.py": _lib_com_shared("pkg")})
    client.run("create . -o opcao_que_nao_existe=1", assert_error=True)
    assert "ERROR" in client.out


def test_option_valor_fora_da_lista_de_possiveis_levanta_erro(client):
    client.save({"conanfile.py": _lib_com_shared("pkg")})
    client.run("create . -o shared=Talvez", assert_error=True)
    assert "ERROR" in client.out


def test_option_any_aceita_qualquer_valor(client):
    conanfile = """
from conan import ConanFile

class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
    options = {"versao_customizada": ["ANY"]}
    default_options = {"versao_customizada": "1.2.3"}

    def package_info(self):
        self.output.info(f"VALOR={self.options.versao_customizada}")

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile})
    client.run("create . -o versao_customizada=qualquer-coisa-mesmo")
    assert "VALOR=qualquer-coisa-mesmo" in client.out


def test_option_comparar_com_valor_fora_dos_possiveis_levanta_erro(client):
    """ACHADO preservado da v1: comparar uma opção restrita (possible_values
    definido) contra um valor que não está entre os possíveis não devolve
    False -- quebra com ConanException. Uma receita real que faça
    `if self.options.shared == "Talvez":` num método como validate()
    quebra o build inteiro em vez de simplesmente ser falso."""
    conanfile = """
from conan import ConanFile

class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
    options = {"shared": ["True", "False"]}
    default_options = {"shared": "True"}

    def validate(self):
        if self.options.shared == "Talvez":
            pass

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile})
    client.run("create .", assert_error=True)
    assert "ERROR" in client.out


# --------------------------------------------------------------------------
# _PackageOptions -- congelamento (uma vez fixada pela linha de comando,
# a própria receita dependente não pode forçar outro valor)
# --------------------------------------------------------------------------


def test_option_ja_fixada_na_linha_de_comando_nao_pode_ser_mudada_pelo_configure_da_propria_receita(client):
    """Mata mutante que remova a comparação 'current_value != value' na
    checagem de freeze -- uma vez que o grafo já fixou o valor de uma
    opção da PRÓPRIA receita (aqui, via -o explícito), o configure()
    dessa mesma receita não pode forçar um valor diferente.
    Confirmado por execução direta antes de escrever o teste: a
    tentativa de sobrescrever via configure() de um CONSUMIDOR (em vez
    do próprio pacote) não levanta -- é silenciosamente ignorada, o
    valor da linha de comando prevalece; só o configure() DO PRÓPRIO nó
    dispara o freeze."""
    conanfile = """
from conan import ConanFile

class Pkg(ConanFile):
    name = "liba"
    version = "1.0"
    package_type = "header-library"
    options = {"shared": ["True", "False"]}
    default_options = {"shared": "False"}

    def configure(self):
        self.options.shared = "False"

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile})
    client.run("create . -o shared=True", assert_error=True)
    assert "ERROR" in client.out


def test_option_redefinir_com_o_mesmo_valor_no_configure_da_propria_receita_nao_levanta(client):
    conanfile = """
from conan import ConanFile

class Pkg(ConanFile):
    name = "liba"
    version = "1.0"
    package_type = "header-library"
    options = {"shared": ["True", "False"]}
    default_options = {"shared": "False"}

    def configure(self):
        self.options.shared = "True"

    def package(self):
        pass

    def package_info(self):
        self.output.info(f"SHARED={self.options.shared}")
"""
    client.save({"conanfile.py": conanfile})
    client.run("create . -o shared=True")
    assert "SHARED=True" in client.out


# --------------------------------------------------------------------------
# _PackageOptions -- marcação "importante" (!): vence default_options de
# um consumidor, mesmo declarado depois
# --------------------------------------------------------------------------


def test_option_marcada_importante_na_linha_de_comando_vence_default_options_do_consumidor(client):
    """Mata mutante que remova a lógica de 'important' -- um valor
    marcado com '!' na linha de comando não pode ser sobrescrito pelos
    default_options que o app declara para essa mesma dependência."""
    client.save({"conanfile.py": _lib_com_shared("liba")})
    client.run("create .")

    conanfile_app = """
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"
    requires = "liba/1.0"
    default_options = {"liba/*:shared": "True"}

    def package(self):
        pass
"""
    client.save({"conanfile.py": conanfile_app}, clean_first=True)
    client.run('graph info . -o liba/*:shared!=False --format=json')
    grafo = json.loads(client.stdout)
    liba_node = next(n for n in grafo["graph"]["nodes"].values() if n.get("name") == "liba")
    assert liba_node["options"]["shared"] == "False"


# --------------------------------------------------------------------------
# Options -- dump/load via o formato texto que a própria CLI usa
# --------------------------------------------------------------------------


def test_options_resolvidas_aparecem_no_dump_de_graph_info(client):
    """Cobre Options.dumps()/loads() indiretamente: o formato texto
    'nome=valor' que options.dumps() produz é exatamente o que a CLI
    usa para relatar/reconstruir opções resolvidas em graph info."""
    client.save({"conanfile.py": _lib_com_shared("liba")})
    client.run("create . -o shared=True")
    client.run("graph info --requires=liba/1.0 -o liba/*:shared=True --format=json")
    grafo = json.loads(client.stdout)
    liba_node = next(n for n in grafo["graph"]["nodes"].values() if n.get("name") == "liba")
    assert liba_node["options"]["shared"] == "True"
