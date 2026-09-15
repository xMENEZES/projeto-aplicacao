"""
Testes estruturais (caixa-branca) de conan/internal/model/version.py --
Version continua testada direto, por instanciação: é uma classe de valor
pura (compara/ordena strings de versão), sem depender de cache ou grafo,
exatamente como um teste unitário observaria de fora.

version_range.py (VersionRange) NÃO é mais testada por instanciação
direta -- é exercitada via TestClient/grafo real: a faixa expressa como
string no `requires` de um conanfile (`liba/[>=1.0 <2.0]`), resolvida
por `conan create`/`graph info` contra versões reais publicadas no
cache. É assim que uma faixa de versão é observável de fora: pela versão
que o grafo de fato escolhe, não pelo retorno de `.contains()` chamado
isoladamente.
"""

from __future__ import annotations

import json

import pytest

from conan.errors import ConanException
from conan.internal.model.version import Version
from conan.internal.model.version_range import VersionRange


# --------------------------------------------------------------------------
# Version -- parsing e componentes
# --------------------------------------------------------------------------


def test_version_major_minor_patch():
    v = Version("1.2.3")
    assert v.major == 1
    assert v.minor == 2
    assert v.patch == 3


def test_version_componente_ausente_devolve_none():
    v = Version("1.2")
    assert v.patch is None


def test_version_com_prerelease_e_build():
    v = Version("1.2.3-alpha+build5")
    assert str(v.pre) == "alpha"
    assert str(v.build) == "build5"


def test_version_str_preserva_a_string_original():
    """Mata mutante que troque self._value por uma reconstrução a partir das partes."""
    v = Version("1.02.3")  # zero à esquerda -- reconstruir perderia isso
    assert str(v) == "1.02.3"


# --------------------------------------------------------------------------
# Version -- igualdade (ACHADO: zeros à direita são insignificantes)
# --------------------------------------------------------------------------


def test_version_ignora_zeros_a_direita_na_igualdade():
    """ACHADO: Version compara por _nonzero_items (remove zeros à direita),
    então versões que "parecem" diferentes textualmente são iguais para
    fins de comparação -- 1.2 == 1.2.0 == 1.2.0.0. Isso é documentado no
    próprio docstring da classe ("not semver"), mas é fácil escrever um
    teste que assuma o contrário."""
    assert Version("1.2") == Version("1.2.0")
    assert Version("1.0.0") == Version("1")
    assert Version("2.0") != Version("2.0.1")


def test_version_diferentes_tipos_permanecem_comparaveis_com_string():
    assert Version("1.2.3") == "1.2.3"


# --------------------------------------------------------------------------
# Version -- ordenação, incluindo pré-releases
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "menor, maior",
    [
        ("1.0.0", "2.0.0"),
        ("1.9.0", "1.10.0"),  # numérico, não lexicográfico
        ("1.0.0-alpha", "1.0.0"),  # pre-release vem antes do release
        ("1.0.0-alpha", "1.0.0-beta"),
    ],
)
def test_version_ordenacao(menor, maior):
    assert Version(menor) < Version(maior)
    assert Version(maior) > Version(menor)


def test_version_comparacao_numerica_nao_lexicografica():
    """Mata mutante que troque a comparação de _VersionItem para string pura."""
    assert Version("1.9") < Version("1.10")


def test_version_none_nunca_e_maior_nem_igual():
    v = Version("1.0.0")
    assert (v == None) is False  # noqa: E711
    assert (v < None) is False


# --------------------------------------------------------------------------
# Version.bump / upper_bound
# --------------------------------------------------------------------------


def test_bump_incrementa_indice_e_zera_a_direita():
    assert str(Version("2.5").bump(1)) == "2.6"


def test_bump_na_pratica_trunca_em_vez_de_zerar_a_direita():
    """ACHADO: o docstring de Version.bump() promete '1.5.7 => bump(0) =>
    2.0.0' (incrementa o índice, ZERA os campos à direita), mas o código
    calcula o preenchimento de zeros como
    `[0] * (len(items) - index - 1)` -- e nesse ponto `items` já é a lista
    truncada em `:index` com o item incrementado ANEXADO, então
    `len(items)` é sempre `index + 1`, e `len(items) - index - 1` é
    sempre 0. Na prática, bump() nunca zera nada à direita: ele TRUNCA.
    `Version("1.5.7").bump(0)` devolve "2", não "2.0.0". Isso só aparece
    quando há mais de um campo à direita do índice bumpado -- com um único
    campo restante (ex.: bump(1) em "2.5") o truncamento e o zeramento
    dão o mesmo resultado, o que explica por que o exemplo mais simples
    do próprio docstring passa sem revelar o problema."""
    assert str(Version("1.5.7").bump(0)) == "2"  # e não "2.0.0", como o docstring promete
    assert str(Version("1.2.3.4").bump(1)) == "1.3"  # e não "1.3.0.0"


def test_bump_em_indice_nao_numerico_levanta_conan_exception():
    with pytest.raises(ConanException):
        Version("1.alpha.3").bump(1)


def test_upper_bound_exclui_prereleases():
    """upper_bound acrescenta um '-' ao final para que pré-releases da
    própria versão-limite não sejam incluídos no range calculado."""
    limite = Version("2.0").upper_bound(0)
    assert VersionRange(f"<{limite}").contains(Version("2.0.0-alpha"), resolve_prerelease=None) is False
    assert VersionRange(f"<{limite}").contains(Version("1.9.9"), resolve_prerelease=None) is True


# --------------------------------------------------------------------------
# VersionRange -- operadores básicos, via requires="liba/[<faixa>]" real,
# resolvido por graph info contra versões publicadas de fato no cache
# --------------------------------------------------------------------------


def _lib(versao):
    return f"""
from conan import ConanFile

class Pkg(ConanFile):
    name = "liba"
    version = "{versao}"
    package_type = "header-library"

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []
"""


def _app_com_faixa(expressao):
    return f"""
from conan import ConanFile

class App(ConanFile):
    name = "app"
    version = "1.0"
    requires = "liba/[{expressao}]"

    def package(self):
        pass
"""


def _versao_resolvida(client):
    grafo = json.loads(client.stdout)
    liba_node = next(n for n in grafo["graph"]["nodes"].values() if n.get("name") == "liba")
    return liba_node["version"]


@pytest.mark.parametrize(
    "expressao, versao_publicada, deve_resolver",
    [
        (">=1.0", "1.5.0", True),
        (">=1.0", "0.9.0", False),
        ("<2.0", "1.9.9", True),
        ("<2.0", "2.0.0", False),
        (">=1.0 <2.0", "1.5.0", True),
        (">=1.0 <2.0", "2.0.0", False),
        ("=1.2.3", "1.2.3", True),
        ("=1.2.3", "1.2.4", False),
        ("1.2.3", "1.2.3", True),  # sem operador == "="
    ],
)
def test_version_range_operadores_basicos(client, expressao, versao_publicada, deve_resolver):
    client.save({"conanfile.py": _lib(versao_publicada)})
    client.run("create .")
    client.save({"conanfile.py": _app_com_faixa(expressao)}, clean_first=True)
    if deve_resolver:
        client.run("graph info . --format=json")
        assert _versao_resolvida(client) == versao_publicada
    else:
        client.run("graph info .", assert_error=True)
        assert "ERROR" in client.out


def test_version_range_operador_or_aceita_qualquer_alternativa(client):
    """Mata mutante que troque '||' por outro separador na divisão de alternativas."""
    client.save({"conanfile.py": _lib("1.0.0")})
    client.run("create .")
    client.save({"conanfile.py": _lib("2.0.0")}, clean_first=True)
    client.run("create .")

    client.save({"conanfile.py": _app_com_faixa("1.0 || 2.0")}, clean_first=True)
    client.run("graph info . --format=json")
    assert _versao_resolvida(client) in ("1.0.0", "2.0.0")

    client.save({"conanfile.py": _app_com_faixa("1.5")}, clean_first=True)
    client.run("graph info .", assert_error=True)  # nem 1.0.0 nem 2.0.0 satisfazem "1.5"


def test_version_range_wildcard_final(client):
    client.save({"conanfile.py": _lib("1.2.9")})
    client.run("create .")
    client.save({"conanfile.py": _lib("1.3.0")}, clean_first=True)
    client.run("create .")

    client.save({"conanfile.py": _app_com_faixa("1.2.*")}, clean_first=True)
    client.run("graph info . --format=json")
    assert _versao_resolvida(client) == "1.2.9"  # 1.3.0 existe no cache, mas 1.2.* não a aceita


def test_version_range_tilde_permite_apenas_patch(client):
    """~1.2.3 permite qualquer patch dentro de 1.2.x, mas não 1.3.0."""
    client.save({"conanfile.py": _lib("1.2.9")})
    client.run("create .")
    client.save({"conanfile.py": _lib("1.3.0")}, clean_first=True)
    client.run("create .")

    client.save({"conanfile.py": _app_com_faixa("~1.2.3")}, clean_first=True)
    client.run("graph info . --format=json")
    assert _versao_resolvida(client) == "1.2.9"


def test_version_range_prerelease_exigido_explicitamente_via_include_prerelease(client):
    """Sem o marcador, uma pré-release não é resolvida por uma faixa comum."""
    client.save({"conanfile.py": _lib("1.5.0-alpha")})
    client.run("create .")

    client.save({"conanfile.py": _app_com_faixa(">=1.0")}, clean_first=True)
    client.run("graph info .", assert_error=True)  # só existe uma pré-release publicada

    client.save({"conanfile.py": _app_com_faixa(">=1.0,include_prerelease")}, clean_first=True)
    client.run("graph info . --format=json")
    assert _versao_resolvida(client) == "1.5.0-alpha"


def test_version_range_vazio_levanta_erro(client):
    client.save({"conanfile.py": _app_com_faixa("")})
    client.run("create .", assert_error=True)
    assert "ERROR" in client.out
