# Suíte de testes — Requests (piloto)

Suíte escrita **sem consultar a pasta `tests/` do repositório oficial** — só o
código de produção foi lido. O objetivo é servir de base de comparação
posterior contra a suíte de testes real, escrita por humanos, mantida pelo
projeto.

## Escopo

Cobertura profunda dos módulos centrais mapeados na análise de arquitetura
anterior, e não do repositório inteiro:

- **`models.py`** — o coração da biblioteca: define `Request` (o que o
  usuário monta), `PreparedRequest` (a versão já processada, com URL, headers,
  corpo e auth resolvidos, prestes a ser enviada) e `Response` (o que volta do
  servidor, com `.json()`, `.text`, `.content`, `raise_for_status()` etc.).
- **`sessions.py`** — a camada de orquestração: `Session` mantém estado entre
  requisições (cookies, headers, adapters montados) e contém a lógica de
  redirecionamento (`SessionRedirectMixin`). É quem decide qual `Adapter`
  usar e dispara os hooks. `merge_setting`/`merge_hooks` (funções internas
  de mesclagem de configuração) não são alvo de teste isolado -- ver
  "Ajustes consolidados" abaixo.
- **`adapters.py`** — a camada de transporte: `HTTPAdapter` é a
  implementação padrão, que traduz uma `PreparedRequest` numa chamada real ao
  `urllib3` (pooling de conexões, proxy, verificação de certificado TLS) e
  devolve um `Response`. `BaseAdapter` (a interface abstrata) não tem teste
  isolado -- não há o que testar numa classe cujos métodos só levantam
  `NotImplementedError`.
- **`auth.py`** — as estratégias de autenticação plugáveis: `HTTPBasicAuth`
  e `HTTPDigestAuth` (essa última implementa o desafio RFC 2617 completo,
  com nonce, hashes e reenvio automático da requisição). `HTTPProxyAuth`
  não tem teste isolado -- ver "Ajustes consolidados" abaixo.
- **`hooks.py`** — o mecanismo de extensão mais simples da biblioteca: um
  dicionário de callbacks por evento (hoje só existe o evento `"response"`)
  que permite interceptar/substituir a resposta antes de ela chegar ao
  usuário, sem alterar o núcleo.
- **`cookies.py`** — a ponte entre o `http.cookiejar` da biblioteca padrão do
  Python e uma interface de dicionário mais amigável (`RequestsCookieJar`),
  usada tanto pela `Session` quanto pelo `Response` para guardar cookies.
- **`structures.py`** — dois utilitários de baixo nível usados por todo o
  resto do pacote: `CaseInsensitiveDict` (headers HTTP não diferenciam
  maiúsculas/minúsculas) e `LookupDict` (base de `requests.codes`, o mapa de
  nomes para códigos de status HTTP).

`utils.py`, `help.py`, `certs.py`, `compat.py` e `packages.py` não foram alvo
direto — aparecem na cobertura só pelo tanto que os módulos acima já os
exercitam de passagem.

## Código sob teste

`repositorios-originais/requests/requests/` (ver `testes-ia/requests/conftest.py`) é uma cópia exata do checkout clonado do GitHub
(`psf/requests`, tag correspondente à versão `2.34.2`) no momento da análise
de arquitetura, e não a versão publicada no PyPI (o ambiente já tinha
`requests==2.32.4` instalado como dependência de outra
ferramenta). `conftest.py` insere `repositorios-originais/requests/` no início do `sys.path` e
confere, com um `assert` logo na importação, que `requests.__version__ ==
"2.34.2"` — se algum dia essa suíte for rodada num ambiente onde isso deixe
de ser verdade, ela falha alto e explicitamente, em vez de testar a versão
errada silenciosamente.

## Como rodar

```bash
py -m pip install pytest pytest-cov urllib3 charset_normalizer idna certifi
py -m pytest -q
py -m pytest -q --cov=requests --cov-report=term-missing
```

Nenhum teste depende de rede externa. Os testes funcionais, de integração e
de aceitação usam um servidor HTTP local (`conftest.py::live_server`, um
`http.server.ThreadingHTTPServer` de ~200 linhas) que simula rotas de eco,
redirecionamento, cookies, Basic/Digest Auth, gzip e delay — o equivalente a
um httpbin.org local, determinístico e sem custo de rede.

## Organização por tipo de teste

| Arquivo | Tipo | O que valida |
|---|---|---|
| `test_estrutural_models.py` | Estrutural (caixa-branca) | Ramos internos de `PreparedRequest`/`Response`: `prepare_url`, `prepare_body`, `raise_for_status`, `iter_content` etc. |
| `test_estrutural_sessions.py` | Estrutural | `SessionRedirectMixin` (via redirects reais contra o servidor local), roteamento de adapters |
| `test_estrutural_adapters_auth.py` | Estrutural | `HTTPAdapter` (cert, proxy, build_response) e Basic/Digest Auth |
| `test_estrutural_cookies_hooks.py` | Estrutural | `RequestsCookieJar`, `dispatch_hook`, `CaseInsensitiveDict`, `LookupDict` |
| `test_funcional_api.py` | Funcional (caixa-preta) | API pública (`requests.get/post/...`) contra o servidor local |
| `test_integracao.py` | Integração | Session+Adapter, Session+Auth (Basic via tupla, Digest ponta a ponta), redirects+cookies |
| `test_aceitacao.py` | Aceitação | Histórias de usuário, no vocabulário de quem consome a biblioteca |

**181 testes, todos passando** (revisão de 2026-09-14 -- ver "Ajustes
consolidados" abaixo; eram 200 antes dela). As percentuais de cobertura de
linha abaixo foram medidas ANTES dessa revisão e não foram re-medidas
depois -- ficaram aqui só como referência histórica de intenção, não como
número atual: `sessions.py` 90%, `auth.py` 83%, `cookies.py` 76%,
`models.py` 74%, `adapters.py` 73%. `hooks.py` e `api.py` ficavam perto de
100%.

## Ajustes consolidados (2026-09-14) — correspondência com testes humanos

Revisão feita sob o critério "um teste da IA só sobrevive se existir, ou
puder existir reescrito no mesmo nível de abstração, um teste humano
equivalente" -- sem nenhum contato com a suíte humana real, só raciocínio
sobre o que é observável publicamente.

**Removido (sem correspondente humano possível, em nenhum nível):**
`PreparedRequest.prepare_content_length` (não há via pública para observar
o header calculado fora de si mesmo), `merge_setting`/`merge_hooks`
(funções internas de composição, sem via pública para observar o
resultado isoladamente), `BaseAdapter` (interface abstrata, nada para
testar), `HTTPProxyAuth` (zero evidência humana e sem via pública simples
de exercitá-la, ao contrário de `HTTPBasicAuth`).

**Reescrito para o mesmo nível de abstração que um consumidor da
biblioteca observaria:** `prepare_url`/`prepare_body` passaram a ser
exercitados via `Request(...).prepare()` (nunca chamando os métodos
`prepare_*` isolados); `rebuild_method` passou a ser exercitado via
redirects reais contra `conftest.py::live_server` (`session.get/post/...`),
nunca chamado direto; o teste de "seta header Authorization" do
`HTTPBasicAuth` foi movido para `test_integracao.py`, via `auth=(user,
pass)` — a forma pública real de usá-lo.

## Sobre os testes de mutação

Por decisão explícita para este projeto, a suíte **não executa** uma
ferramenta de mutation testing (ex. `mutmut`) — os casos foram escritos
*pensando* em matar mutações comuns, e cada teste estrutural que tem um
alvo de mutação claro carrega um comentário/docstring dizendo qual mutação
ele mata. Os alvos mais recorrentes:

- **Fronteiras numéricas** (`raise_for_status`: 400/500)
- **Inversão/troca de operador lógico** (`should_strip_auth`)
- **Off-by-one em contagem** (`nonce_count` do Digest Auth, `max_redirects`)
- **Remoção de guarda condicional** (filtro de hooks não-`callable`, checagem
  `isinstance(..., bool)` em `iter_content`)
- **Troca de tupla/conjunto de valores aceitos** (`(301, 308)` em
  `is_permanent_redirect`)

Quando (e se) uma ferramenta de mutação real for rodada sobre este mesmo
código, o `mutation score` resultante é o critério objetivo para saber se
essa intenção realmente se traduziu em testes eficazes — este documento
registra a intenção de design, não o resultado medido.

## Achados durante a escrita (relevantes para a comparação com testes humanos)

Dois comportamentos do código de produção não são o que o nome do método
sugere à primeira leitura, e a suíte testa o comportamento *real*, não o
que pareceria "óbvio":

1. **`RequestsCookieJar.multiple_domains()`** não detecta "existe mais de um
   domínio distinto no jar" — detecta "algum domínio aparece mais de uma
   vez na iteração". Duas cookies em domínios diferentes (um cookie por
   domínio) retornam `False`. Ver `test_requests_cookie_jar_multiple_domains_*`.
2. **`LookupDict.__getattr__`/`__getitem__`** leem de `self.__dict__`
   (atributos de instância), não do armazenamento nativo do `dict`. Definir
   um valor via `ld["x"] = 1` (a forma "óbvia", herdada de `dict`) nunca
   aparece de volta por `ld.x` nem por `ld["x"]` — só `setattr(ld, "x", 1)`
   funciona, que é como `status_codes.py` de fato povoa a classe. Ver
   `test_lookup_dict_*`.

Vale conferir, na comparação, se a suíte oficial testa esses dois pontos
explicitamente ou se também os trata como comportamento incidental.
