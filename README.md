# Testes de IA vs. Testes Humanos — 5 repositórios Python

Projeto de comparação entre uma suíte de testes escrita por IA (Claude,
sem acesso aos testes humanos durante a escrita) e a suíte de testes já
existente, escrita por humanos, em 5 repositórios open source Python:
**Requests, Scrapy, Celery, Conan e Dask**.

## Estrutura

```
repositorios-originais/   Código-fonte de produção de cada projeto (SEM nenhum teste,
                           nem humano nem de IA) — o alvo comum que as duas suítes exercitam.
testes-humanos/            Só a pasta de testes original de cada projeto, como veio do
                           repositório oficial (nunca lida durante a escrita da suíte de IA).
testes-ia/                 A suíte de testes escrita por IA para cada projeto: v1 (ad-hoc,
                           por tipo: estrutural/funcional/integração/aceitação) e v2
                           (metodologia formal: classes de equivalência, valor limite,
                           tabela de decisão).
documentos/                READMEs por repositório, planos de teste (v2), o resumo geral
                           dos testes criados e o relatório de comparação (cobertura +
                           teste de mutação).
```

Cada pasta em `testes-ia/<repositório>/` roda de forma independente
(`conftest.py` próprio, `requirements-testes.txt` próprio) e importa o
código de `repositorios-originais/<repositório>/` via `sys.path`, nunca
via instalação (`pip install`)  garante que os testes sempre rodam
contra o checkout exato documentado em cada
`documentos/<repositório>/README.md`, não contra qualquer versão do
pacote que porventura já esteja instalada no ambiente.

## Metodologia

Nenhum teste da suíte de IA (`testes-ia/`) foi escrito olhando a pasta
de testes humana (`testes-humanos/`) do projeto correspondente — só o
código de produção foi lido  para que a comparação depois seja justa
(duas suítes independentes sobre o mesmo código). Ver
`documentos/RESUMO_TESTES_CRIADOS.md` para uma descrição completa dos
testes criados, classe por classe, e `documentos/RELATORIO_COMPARACAO_TESTES_IA_HUMANOS.md`
para os resultados da comparação (cobertura de linha/branch via
`pytest-cov` e escore de teste de mutação).

## Como rodar os testes de IA de um repositório

```bash
cd testes-ia/<repositorio>
py -m pip install -r requirements-testes.txt
py -m pytest -q
```

## Outras pastas na raiz (fora do esquema acima)

- `comparativo-tests/` — saída da análise de cobertura/mutação (relatórios HTML, dados brutos), por repositório.
- `mutation_test.py` — script próprio de teste de mutação (ROR/AOR/COR), usado por `comparativo-tests/`.
- `<repositorio>/human_original/` (ex.: `celery/human_original/`) — clone completo (com histórico git) de cada
  repositório, mantido fora da estrutura principal: usado ativamente para medir cobertura/mutação da suíte
  humana lado a lado com a de IA. Ignorado pelo git (ver `.gitignore`) — não é conteúdo do repositório, é
  ambiente de trabalho local.
