# Suíte de testes — Scrapy (2º repositório)

Suíte escrita **sem consultar as pastas `tests/` e `tests_typing/` do
repositório oficial** — só o código de produção foi lido. Segue o mesmo
formato do piloto feito para o Requests: módulos centrais mapeados na
análise de arquitetura, quatro tipos de teste (estrutural, funcional,
integração, aceitação), tudo rodando contra código real, sem mocks
substituindo o comportamento que está sendo testado.

A diferença que mais pesou aqui em relação ao Requests: o Scrapy inteiro
gira em torno de um loop de eventos assíncrono (Twisted), então parte desta
suíte não é só "chamar uma função e verificar o retorno" — é rodar um
crawl de verdade, do início ao fim, contra um servidor HTTP local.

## Escopo — o que cada módulo-alvo faz

- **`http/request/__init__.py`** — define `Request`: o objeto que descreve
  *o que* buscar (URL, método, headers, corpo, callback) antes de qualquer
  coisa ser enviada. É o ponto de entrada de tudo que o spider pede para
  o Scrapy baixar.
- **`http/response/__init__.py` e `http/response/text.py`** — `Response` é
  o que volta do download; `TextResponse` (base de `HtmlResponse`) adiciona
  detecção de encoding (via header, BOM, `<meta charset>` ou heurística) e
  os atalhos `.css()`/`.xpath()`/`.follow()` que todo spider usa para
  extrair dados e gerar as próximas requisições.
- **`settings/__init__.py`** — `BaseSettings`/`Settings`: um dicionário com
  prioridades embutidas (default < command < addon < project < spider <
  cmdline), usado para decidir, em tempo de execução, quais middlewares,
  pipelines e extensões estão ativos e com que configuração.
- **`signalmanager.py`** — a camada de eventos: permite que qualquer
  componente (built-in ou de terceiros) reaja a um momento do ciclo de vida
  do crawl (spider aberto, engine iniciado, item raspado) sem que o núcleo
  precise conhecer quem está escutando.
- **`downloadermiddlewares/{redirect,retry,httpauth,offsite}.py`** — a
  corrente de responsabilidade que intercepta toda requisição/resposta
  antes e depois do download real: segue redirecionamentos, reenvia
  requisições que falharam, injeta autenticação HTTP básica e descarta
  requisições para domínios fora do permitido.
- **`spidermiddlewares/{depth,urllength}.py` (+ `base.py`)** — a mesma ideia
  de corrente, mas do lado da saída do spider: controlam profundidade de
  rastreamento e tamanho máximo de URL antes de uma nova requisição ser
  agendada. `base.py` fornece o Template Method (`get_processed_request`)
  que as duas reaproveitam.
- **`item.py`** — `Item`/`Field`: a forma estruturada (com validação de
  campos declarados) de representar um registro extraído, em contraste com
  devolver dicionários soltos sem type-checking nenhum.
- **`core/engine.py`, `crawler.py`, `core/scheduler.py`** — o motor que
  orquestra tudo acima. Não foram testados por chamada isolada de método
  (são fortemente acoplados ao reactor Twisted) — são exercitados de ponta
  a ponta pelos crawls reais das camadas de integração e aceitação.

`selector/`, `exporters.py`, `pipelines/`, `extensions/`, `mail.py`,
`robotstxt.py` e a maior parte de `utils/` não foram alvo direto.

## Código sob teste

`repositorios-originais/scrapy/scrapy/` é uma cópia exata do checkout clonado (`scrapy/scrapy`,
versão `2.17.0`). Neste caso a versão instalada via pip e a do clone
coincidem (ambas `2.17.0`), mas o `conftest.py` insere `repositorios-originais/scrapy/` no início
do `sys.path` e confere isso com um `assert` mesmo assim — garantia barata
contra o dia em que alguém atualizar uma das duas e não notar a outra.

## Como rodar

```bash
py -m pip install -r requirements-testes.txt
py -m pytest -q
py -m pytest -q --cov=scrapy --cov-report=term-missing
```

Nenhum teste depende de rede externa. `conftest.py` sobe um servidor HTML
local (`html_server`, um `http.server.ThreadingHTTPServer`) com páginas,
links, redirecionamentos, uma rota que falha duas vezes antes de responder
200, uma rota protegida por Basic Auth e uma listagem de "produtos" para
extração estruturada.

**Detalhe de infraestrutura que exigiu investigação:** o Scrapy 2.17 espera
por padrão o reactor `AsyncioSelectorReactor`, mas o plugin `pytest-twisted`
instala o `SelectReactor` clássico ao ser carregado — sem ajuste, o primeiro
crawl real de cada sessão falha com `RuntimeError: the installed reactor
does not match the requested one`. A correção usa
`scrapy.utils.test.get_reactor_settings()` (utilitário do próprio pacote,
não um arquivo de teste) para descobrir e aplicar a configuração de reactor
compatível com o que já está instalado — é a fixture `reactor_settings` em
`conftest.py`, usada em todo crawl real desta suíte.

## Organização por tipo de teste

| Arquivo | Tipo | O que valida |
|---|---|---|
| `test_estrutural_http.py` | Estrutural | `Request`/`Response`/`TextResponse`: validação, encoding, seletores, `follow()` |
| `test_estrutural_settings_signals.py` | Estrutural | `BaseSettings` (prioridades, conversões) e `SignalManager` |
| `test_estrutural_downloadermiddlewares.py` | Estrutural | `RedirectMiddleware`, `RetryMiddleware`, `HttpAuthMiddleware`, `OffsiteMiddleware`, isolados |
| `test_estrutural_spidermiddlewares_item.py` | Estrutural | `DepthMiddleware`, `UrlLengthMiddleware`, `Item`/`Field` |
| `test_integracao_crawl.py` | Integração | Crawls reais: links, redirect, retry, depth, auth, dupefilter, pipeline — engine+reactor de verdade |
| `test_aceitacao_crawl.py` | Aceitação | Histórias de usuário, também com crawls reais |

**144 testes, todos passando** (rodados juntos, sem interferência entre
arquivos). Cobertura de linha medida via `pytest-cov` nos módulos-alvo:
`offsite.py` 98%, `item.py` 93%, `retry.py` 91%, `text.py` (TextResponse)
90%, `response/__init__.py` 91%, `request/__init__.py` 87%,
`httpauth.py` 85%, `signalmanager.py` 82%, `redirect.py` 80%,
`depth.py` 96%, `settings/__init__.py` 71%. `crawler.py` chega a 45% só de
incidência dos crawls reais, sem ter sido alvo direto de teste estrutural.

## Sobre os testes de mutação

Mesma decisão do piloto: a suíte não executa uma ferramenta de mutação —
os casos foram desenhados para matar mutações específicas, documentadas no
docstring/comentário de cada teste onde o alvo não é óbvio. Padrões mais
comuns aqui:

- **Fronteiras de comparação numérica** (`priority >= self.priority` em
  `SettingsAttribute.set`; `redirects <= max_redirect_times`;
  `len(url) <= maxlength`; `depth > maxdepth`)
- **Condições compostas em cadeia** (`should_strip_auth`-like: mudança de
  host/porta/esquema no redirect que decide remover `Cookie`/`Authorization`)
- **Valores default mutáveis compartilhados** (garantir que `meta`,
  `cb_kwargs`, `flags`, `cookies` de duas instâncias de `Request` nunca
  apontam para o mesmo dict/lista)
- **Troca de verbo HTTP condicional** (301/302 + POST → GET; 303 + não
  GET/HEAD → GET; 307/308 preservam o verbo)

## Achados durante a escrita (relevantes para a comparação com testes humanos)

1. **`SignalManager.disconnect_all()` pode deixar um receptor conectado.**
   `scrapy/utils/signal.py::disconnect_all` itera
   `liveReceivers(getAllReceivers(...))` e desconecta cada item *dentro do
   mesmo laço que está iterando essa lista* — um "mutar a lista enquanto
   itera" clássico. Com exatamente dois receptores no mesmo sinal, o
   segundo sobrevive de forma reprodutível (confirmado em execuções
   repetidas). Ver `test_disconnect_all_com_dois_receptores_deixa_um_conectado`
   em `test_estrutural_settings_signals.py`. Vale conferir se a suíte
   oficial testa `disconnect_all()` com mais de um receptor por sinal — é
   o tipo de caso que só aparece com múltiplos receptores.
2. **Charset `iso-8859-1` declarado no header nunca aparece como tal em
   `TextResponse.encoding`.** `w3lib.encoding.resolve_encoding` remapeia
   `iso-8859-1` para `cp1252`, seguindo o mesmo comportamento legado que
   navegadores adotam (WHATWG encoding spec). Não é um bug do Scrapy — é
   uma decisão deliberada de uma dependência — mas quebra qualquer teste
   escrito assumindo que o nome do encoding declarado é o nome do encoding
   resolvido. Ver `test_text_response_deteta_encoding_via_header_content_type`.
3. **Requisições de `start_urls` não entram no dupefilter.** Elas nascem
   com `dont_filter=True` (é assim que `Spider.start()` as cria por
   padrão), e o scheduler só registra uma requisição como "vista" quando
   `dont_filter` é `False`. Isso significa que um spider que aponta de
   volta para sua própria start URL a visita de novo — o `RFPDupeFilter`
   não protege contra esse caso especificamente. Ver o comentário longo em
   `test_dupefilter_real_evita_visitar_a_mesma_url_duas_vezes`, que documenta
   como o teste original (sem essa ressalva) falhou e por quê.
