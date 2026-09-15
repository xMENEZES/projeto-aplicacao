"""
Testes estruturais (caixa-branca) de dask/config.py -- a configuração em
camadas do Dask (default < arquivo YAML < variável de ambiente < contexto
em runtime via `with dask.config.set(...)`).
"""

from __future__ import annotations

import pytest

import dask
from dask.config import canonical_name, collect_env, get, merge, update


# --------------------------------------------------------------------------
# canonical_name -- normalização hífen/underscore
# --------------------------------------------------------------------------


def test_canonical_name_prefere_a_chave_ja_existente_com_hifen():
    config = {"my-key": 1}
    assert canonical_name("my_key", config) == "my-key"


def test_canonical_name_prefere_a_chave_ja_existente_com_underscore():
    """Mata mutante que só normalize num sentido (hífen -> underscore)."""
    config = {"my_key": 1}
    assert canonical_name("my-key", config) == "my_key"


def test_canonical_name_sem_chave_existente_devolve_a_original():
    assert canonical_name("nova-chave", {}) == "nova-chave"


def test_canonical_name_com_config_nao_mapeavel_devolve_a_chave_original():
    assert canonical_name("x", None) == "x"  # não levanta TypeError


# --------------------------------------------------------------------------
# update / merge -- prioridade
# --------------------------------------------------------------------------


def test_update_com_prioridade_new_sobrescreve_old():
    old = {"x": 1}
    update(old, {"x": 2}, priority="new")
    assert old["x"] == 2


def test_update_com_prioridade_old_preserva_old():
    """Mata mutante que ignore o parâmetro priority='old'."""
    old = {"x": 1}
    update(old, {"x": 2}, priority="old")
    assert old["x"] == 1


def test_update_mescla_dicionarios_aninhados_em_vez_de_substituir():
    old = {"y": {"a": 1}}
    update(old, {"y": {"b": 2}})
    assert old == {"y": {"a": 1, "b": 2}}


def test_update_new_defaults_so_atualiza_se_valor_atual_e_o_default():
    """priority='new-defaults': só sobrescreve se o valor em `old` ainda
    for igual ao default conhecido -- ou seja, o usuário nunca customizou."""
    defaults = {"x": 0}
    old_nao_customizado = {"x": 0}
    update(old_nao_customizado, {"x": 99}, priority="new-defaults", defaults=defaults)
    assert old_nao_customizado["x"] == 99

    old_customizado_pelo_usuario = {"x": 5}
    update(old_customizado_pelo_usuario, {"x": 99}, priority="new-defaults", defaults=defaults)
    assert old_customizado_pelo_usuario["x"] == 5  # preserva a customização


def test_merge_aplica_dicionarios_em_ordem_prevalecendo_o_ultimo():
    a = {"x": 1, "y": {"a": 1}}
    b = {"y": {"b": 2}}
    c = {"x": 99}
    resultado = merge(a, b, c)
    assert resultado == {"x": 99, "y": {"a": 1, "b": 2}}


# --------------------------------------------------------------------------
# get -- acesso com chave "." e override_with
# --------------------------------------------------------------------------


def test_get_acesso_aninhado_com_ponto():
    config = {"foo": {"x": 1, "y": 2}}
    assert get("foo.x", config=config) == 1


def test_get_default_quando_chave_ausente():
    assert get("nao.existe", default=123, config={}) == 123


def test_get_sem_default_e_sem_a_chave_levanta_key_error():
    with pytest.raises(KeyError):
        get("nao.existe", config={})


def test_get_override_with_ignora_o_config_e_devolve_o_valor_direto():
    """Mata mutante que remova a checagem 'override_with is not None'."""
    assert get("qualquer.coisa", config={}, override_with="valor-direto") == "valor-direto"


def test_get_override_with_none_nao_ativa_o_atalho():
    config = {"foo": 42}
    assert get("foo", config=config, override_with=None) == 42


# --------------------------------------------------------------------------
# dask.config.set -- context manager, reverte ao saír
# --------------------------------------------------------------------------


def test_config_set_como_context_manager_reverte_ao_final():
    valor_antes = dask.config.get("array.chunk-size", None)
    with dask.config.set({"array.chunk-size": "999MiB"}):
        assert dask.config.get("array.chunk-size") == "999MiB"
    assert dask.config.get("array.chunk-size", None) == valor_antes


def test_config_set_aceita_kwargs_com_underscore_em_vez_de_ponto():
    with dask.config.set(scheduler="synchronous"):
        assert dask.config.get("scheduler") == "synchronous"


def test_config_set_com_dict_aninhado_substitui_o_ramo_em_vez_de_mesclar():
    """ACHADO: diferente de dask.config.update()/merge() (que mesclam
    dicionários aninhados recursivamente), dask.config.set() NÃO mescla
    quando o valor passado é um dict -- set.__init__ faz
    `key.split(".")` só na CHAVE do argumento (ex.: "a" -> ["a"]), e
    atribui o VALOR inteiro como está naquele caminho. Passar
    {"a": {"y": 2}} depois de já existir {"a": {"x": 1}} SUBSTITUI o "a"
    inteiro por {"y": 2} -- "x" desaparece dentro do bloco `with`, não é
    preservado. Para mesclar de fato, a chave precisa ser o caminho
    completo com ponto: dask.config.set({"a.y": 2})."""
    with dask.config.set({"a": {"x": 1}}):
        with dask.config.set({"a": {"y": 2}}):
            assert dask.config.get("a") == {"y": 2}  # "x" foi substituído, não mesclado
        assert dask.config.get("a") == {"x": 1}  # o rollback devolve o valor de antes


def test_config_set_com_chave_pontilhada_faz_a_mesclagem_esperada():
    """Contraste com o achado acima: usando o caminho com ponto na CHAVE
    (não no valor), cada set() afeta só a folha específica, preservando
    os irmãos."""
    with dask.config.set({"a.x": 1}):
        with dask.config.set({"a.y": 2}):
            assert dask.config.get("a.x") == 1
            assert dask.config.get("a.y") == 2
        assert dask.config.get("a.x") == 1
        with pytest.raises(KeyError):
            dask.config.get("a.y")


# --------------------------------------------------------------------------
# collect_env -- variáveis de ambiente DASK_*
# --------------------------------------------------------------------------


def test_collect_env_converte_prefixo_dask_para_chave_minuscula():
    """__ (duplo underscore) marca aninhamento; um único underscore dentro
    do nome do segmento permanece underscore -- não é convertido para
    hífen aqui (essa normalização hífen/underscore só acontece depois,
    em canonical_name(), na hora de mesclar com o config já existente)."""
    env = {"DASK_ARRAY__CHUNK_SIZE": "128MiB"}
    resultado = collect_env(env)
    assert resultado == {"array": {"chunk_size": "128MiB"}}


def test_collect_env_faz_literal_eval_no_valor():
    """Mata mutante que remova o ast.literal_eval, tratando tudo como string."""
    env = {"DASK_NUM__WORKERS": "4"}
    resultado = collect_env(env)
    assert resultado["num"]["workers"] == 4
    assert isinstance(resultado["num"]["workers"], int)


def test_collect_env_ignora_variaveis_sem_prefixo_dask():
    env = {"OUTRA_VARIAVEL": "valor", "DASK_X": "1"}
    resultado = collect_env(env)
    assert "OUTRA_VARIAVEL" not in resultado
    assert "outra_variavel" not in resultado
    assert resultado["x"] == 1
