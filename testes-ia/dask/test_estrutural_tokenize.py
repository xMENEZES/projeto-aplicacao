"""
Testes estruturais (caixa-branca) de dask/tokenize.py -- o hashing
determinístico usado para cache/identidade de tarefas (duas chamadas
"iguais" devem gerar o mesmo token, para o Dask saber que pode reaproveitar
o resultado em vez de recalcular).
"""

from __future__ import annotations

import pytest

from dask.tokenize import TokenizationError, normalize_token, tokenize


def test_tokenize_e_deterministico_para_o_mesmo_valor():
    assert tokenize(1, 2, "a") == tokenize(1, 2, "a")


def test_tokenize_diferencia_valores_diferentes():
    assert tokenize(1) != tokenize(2)
    assert tokenize("a") != tokenize("b")


def test_tokenize_diferencia_tipos_com_mesma_representacao_textual():
    """Mata mutante que normalize por str(x) em vez de considerar o tipo."""
    assert tokenize(1) != tokenize("1")
    assert tokenize([1, 2]) != tokenize((1, 2))


def test_tokenize_devolve_string_hexadecimal_de_hash_md5():
    token = tokenize(1, 2, 3)
    assert isinstance(token, str)
    assert len(token) == 32  # md5 hexdigest


def test_tokenize_dict_e_independente_da_ordem_das_chaves():
    """Mata mutante que remova o sorted() em normalize_dict."""
    a = tokenize({"x": 1, "y": 2})
    b = tokenize({"y": 2, "x": 1})
    assert a == b


def test_tokenize_lista_depende_da_ordem_dos_elementos():
    assert tokenize([1, 2, 3]) != tokenize([3, 2, 1])


def test_tokenize_kwargs_participam_do_token():
    assert tokenize(1, x=1) != tokenize(1, x=2)


def test_tokenize_instancia_comum_e_deterministica_via_pickle():
    """Uma instância de classe "comum" (sem __dask_tokenize__) não cai no
    fallback não-determinístico: normalize_object() tenta pickle.dumps()
    primeiro, e para um objeto simples (sem atributos com estado variável,
    como endereço de memória) isso É reproduzível entre chamadas --
    então duas instâncias com o mesmo estado tokenizam igual."""

    class ObjetoComum:
        def __init__(self, valor):
            self.valor = valor

    assert tokenize(ObjetoComum(1)) == tokenize(ObjetoComum(1))
    assert tokenize(ObjetoComum(1)) != tokenize(ObjetoComum(2))


def test_tokenize_ensure_deterministic_levanta_para_object_puro():
    """ACHADO: só uma instância do tipo `object` PURO (não de uma subclasse)
    cai no fallback baseado em id() -- normalize_object() checa
    especificamente `type(o) is object`, e não isinstance(). Sem
    ensure_deterministic, isso não levanta (só não é garantidamente
    estável entre chamadas); com ensure_deterministic=True, levanta
    TokenizationError."""
    obj = object()
    tokenize(obj)  # não levanta, mas o token não é reprodutível entre objetos

    with pytest.raises(TokenizationError):
        tokenize(object(), ensure_deterministic=True)


def test_tokenize_respeita_dunder_dask_tokenize_customizado():
    """Mata mutante que remova a checagem de __dask_tokenize__ em
    normalize_object -- é o ponto de extensão oficial para objetos
    customizados declararem sua própria identidade de tokenização."""

    class ComTokenCustomizado:
        def __dask_tokenize__(self):
            return "token-fixo-e-estavel"

    a = ComTokenCustomizado()
    b = ComTokenCustomizado()  # instância diferente, mesmo token declarado
    assert tokenize(a) == tokenize(b)


def test_normalize_token_dispatch_por_tipo_identidade():
    """int/str/float/None etc. são normalizados por identidade (idempotentes)."""
    assert normalize_token(42) == 42
    assert normalize_token("texto") == "texto"
    assert normalize_token(None) is None
