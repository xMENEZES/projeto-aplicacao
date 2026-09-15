"""
Testes estruturais (caixa-branca) de requests/cookies.py, requests/hooks.py
e requests/structures.py.
"""

from __future__ import annotations

import pytest

from requests.cookies import (
    CookieConflictError,
    RequestsCookieJar,
    cookiejar_from_dict,
    create_cookie,
)
from requests.hooks import default_hooks, dispatch_hook
from requests.structures import CaseInsensitiveDict, LookupDict


# --------------------------------------------------------------------------
# hooks.py
# --------------------------------------------------------------------------


def test_default_hooks_contem_apenas_response():
    assert default_hooks() == {"response": []}


def test_default_hooks_gera_listas_independentes_por_chamada():
    """Mata mutante que faça default_hooks() reaproveitar a mesma lista mutável."""
    h1 = default_hooks()
    h2 = default_hooks()
    h1["response"].append("marcador")
    assert h2["response"] == []


def test_dispatch_hook_sem_hooks_devolve_dado_original():
    dado = object()
    resultado = dispatch_hook("response", None, dado)
    assert resultado is dado


def test_dispatch_hook_callable_unico_e_convertido_em_lista():
    chamadas = []

    def hook(dado, **kwargs):
        chamadas.append(dado)
        return dado

    resultado = dispatch_hook("response", {"response": hook}, "valor")
    assert resultado == "valor"
    assert chamadas == ["valor"]


def test_dispatch_hook_hook_que_retorna_none_preserva_dado_original():
    """Mata mutante que troque 'if _hook_data is not None' por checagem sempre verdadeira."""

    def hook_sem_retorno(dado, **kwargs):
        return None

    resultado = dispatch_hook("response", {"response": [hook_sem_retorno]}, "original")
    assert resultado == "original"


def test_dispatch_hook_hook_que_retorna_valor_substitui_dado():
    def hook_substitui(dado, **kwargs):
        return "substituido"

    resultado = dispatch_hook("response", {"response": [hook_substitui]}, "original")
    assert resultado == "substituido"


def test_dispatch_hook_encadeia_multiplos_hooks_em_ordem():
    def acrescenta_a(dado, **kwargs):
        return dado + "a"

    def acrescenta_b(dado, **kwargs):
        return dado + "b"

    resultado = dispatch_hook("response", {"response": [acrescenta_a, acrescenta_b]}, "")
    assert resultado == "ab"


# --------------------------------------------------------------------------
# structures.CaseInsensitiveDict
# --------------------------------------------------------------------------


def test_case_insensitive_dict_get_set_ignora_caixa():
    d = CaseInsensitiveDict()
    d["Content-Type"] = "text/html"
    assert d["content-type"] == "text/html"
    assert d["CONTENT-TYPE"] == "text/html"


def test_case_insensitive_dict_preserva_a_ultima_grafia_da_chave():
    """Mata mutante que faça o dict manter a primeira grafia em vez da última."""
    d = CaseInsensitiveDict()
    d["Accept"] = "1"
    d["ACCEPT"] = "2"
    ((chave_armazenada, _valor),) = d.lower_items()
    assert chave_armazenada == "accept"
    assert d["accept"] == "2"


def test_case_insensitive_dict_igualdade_ignora_caixa_de_ambos_os_lados():
    d1 = CaseInsensitiveDict({"A": "1"})
    d2 = CaseInsensitiveDict({"a": "1"})
    assert d1 == d2


def test_case_insensitive_dict_delitem_ignora_caixa():
    d = CaseInsensitiveDict({"X-Custom": "1"})
    del d["x-custom"]
    assert "X-Custom" not in d


def test_case_insensitive_dict_copy_e_independente():
    d1 = CaseInsensitiveDict({"a": "1"})
    d2 = d1.copy()
    d2["a"] = "2"
    assert d1["a"] == "1"


# --------------------------------------------------------------------------
# structures.LookupDict
# --------------------------------------------------------------------------


def test_lookup_dict_setattr_fica_visivel_por_atributo_e_por_colchetes():
    """LookupDict guarda seus valores em self.__dict__ (atributos de instância),
    não no armazenamento nativo de dict -- é assim que status_codes.py o
    povoa (setattr por código de status). __getattr__ e __getitem__ leem
    de __dict__; só __setitem__ (herdado de dict) não é sobrescrito."""
    ld = LookupDict("codes")
    ld.ok = 200
    assert ld.ok == 200
    assert ld["ok"] == 200


def test_lookup_dict_getattr_chave_ausente_levanta_attribute_error():
    """Mata mutante que faça __getattr__ engolir o AttributeError e devolver None
    direto, sem checar self.__dict__."""
    ld = LookupDict("codes")
    with pytest.raises(AttributeError):
        ld.chave_que_nao_existe


def test_lookup_dict_getitem_chave_ausente_retorna_none_por_fallback():
    """Diferente de __getattr__, __getitem__ nunca levanta -- cai para None."""
    ld = LookupDict("codes")
    assert ld.get("chave_ausente") is None
    assert ld["chave_ausente"] is None


def test_lookup_dict_atribuicao_via_colchetes_nao_aparece_por_atributo():
    """Quirk documentado da implementação: ld["x"] = v usa o dict.__setitem__
    padrão (armazenamento nativo do dict), mas __getattr__/__getitem__ só
    consultam self.__dict__ -- então esse valor nunca é lido de volta por
    nenhuma das duas formas de acesso, apesar de `"x" in ld` ser True."""
    ld = LookupDict("codes")
    ld["ok"] = 200
    assert "ok" in ld  # está no armazenamento nativo do dict
    assert ld["ok"] is None  # mas __getitem__ sobrescrito não olha para lá
    with pytest.raises(AttributeError):
        ld.ok


# --------------------------------------------------------------------------
# cookies.cookiejar_from_dict / RequestsCookieJar
# --------------------------------------------------------------------------


def test_cookiejar_from_dict_cria_um_cookie_por_chave():
    jar = cookiejar_from_dict({"a": "1", "b": "2"})
    assert isinstance(jar, RequestsCookieJar)
    assert jar.get_dict() == {"a": "1", "b": "2"}


def test_cookiejar_from_dict_none_gera_jar_vazio():
    jar = cookiejar_from_dict(None)
    assert jar.get_dict() == {}


def test_cookiejar_from_dict_reaproveita_jar_existente_quando_informado():
    """Mata mutante que ignore o parâmetro `cookiejar` e sempre crie um novo."""
    jar_original = RequestsCookieJar()
    resultado = cookiejar_from_dict({"a": "1"}, cookiejar=jar_original)
    assert resultado is jar_original


def test_requests_cookie_jar_set_e_get_simples():
    jar = RequestsCookieJar()
    jar.set("nome", "valor")
    assert jar.get("nome") == "valor"


def test_requests_cookie_jar_set_com_none_remove_cookie():
    """Mata mutante que remova o tratamento especial de value=None em set()."""
    jar = RequestsCookieJar()
    jar.set("nome", "valor")
    jar.set("nome", None)
    assert jar.get("nome") is None
    assert "nome" not in jar.keys()


def test_requests_cookie_jar_get_default_quando_ausente():
    jar = RequestsCookieJar()
    assert jar.get("nao-existe", default="default-valor") == "default-valor"


def test_requests_cookie_jar_getitem_levanta_key_error_quando_ausente():
    jar = RequestsCookieJar()
    with pytest.raises(KeyError):
        jar["nao-existe"]


def test_requests_cookie_jar_conflito_de_nome_entre_dominios_levanta_erro():
    """Duas cookies com o mesmo nome em domínios diferentes exigem domain= explícito."""
    jar = RequestsCookieJar()
    jar.set_cookie(create_cookie("sessao", "valor-a", domain="a.example.com"))
    jar.set_cookie(create_cookie("sessao", "valor-b", domain="b.example.com"))
    with pytest.raises(CookieConflictError):
        jar.get("sessao")
    # com domain explícito, resolve sem ambiguidade
    assert jar.get("sessao", domain="a.example.com") == "valor-a"
    assert jar.get("sessao", domain="b.example.com") == "valor-b"


def test_requests_cookie_jar_multiple_domains_falso_quando_cada_dominio_e_unico():
    """A implementação atual de multiple_domains() detecta domínio REPETIDO
    entre cookies (não "mais de um domínio distinto" como o nome sugere à
    primeira vista): duas cookies em domínios diferentes, um cookie por
    domínio, não disparam a condição -- o laço nunca encontra o mesmo
    domínio duas vezes."""
    jar = RequestsCookieJar()
    jar.set("a", "1", domain="x.example.com")
    jar.set("b", "2", domain="y.example.com")
    assert jar.multiple_domains() is False


def test_requests_cookie_jar_multiple_domains_verdadeiro_quando_dominio_se_repete():
    """Mata mutante que troque 'in domains' por outra checagem: aqui, duas
    cookies diferentes compartilhando o MESMO domínio é o caso que de fato
    faz multiple_domains() retornar True, dado como o laço está escrito."""
    jar = RequestsCookieJar()
    jar.set("a", "1", domain="x.example.com")
    jar.set("b", "2", domain="x.example.com")
    assert jar.multiple_domains() is True


def test_requests_cookie_jar_list_domains_e_list_paths():
    jar = RequestsCookieJar()
    jar.set("a", "1", domain="x.example.com", path="/um")
    jar.set("b", "2", domain="y.example.com", path="/dois")
    assert set(jar.list_domains()) == {"x.example.com", "y.example.com"}
    assert set(jar.list_paths()) == {"/um", "/dois"}


def test_requests_cookie_jar_get_dict_filtra_por_dominio():
    jar = RequestsCookieJar()
    jar.set("a", "1", domain="x.example.com")
    jar.set("b", "2", domain="y.example.com")
    assert jar.get_dict(domain="x.example.com") == {"a": "1"}


def test_requests_cookie_jar_copy_e_independente_do_original():
    jar = RequestsCookieJar()
    jar.set("a", "1")
    copia = jar.copy()
    copia.set("a", "2")
    assert jar.get("a") == "1"
    assert copia.get("a") == "2"
