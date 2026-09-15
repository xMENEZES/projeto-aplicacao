"""
Traduz para portugues (pt-BR) apenas a "moldura" (textos de interface) dos
relatorios HTML gerados pelo coverage.py -- titulos, cabecalhos de coluna,
legendas de atalhos, textos de navegacao. NAO mexe no codigo-fonte Python
exibido dentro de cada pagina (nomes de variaveis, palavras-chave, comentarios
e docstrings continuam exatamente como estavam).

Uso:
    py translate_coverage_html.py <diretorio_com_os_html_do_coverage.py>
"""
import re
import sys
from pathlib import Path

# Pares (procurar, substituir) -- todos amarrados a marcacao HTML especifica
# do template do coverage.py, para nao arriscar trocar uma palavra igual que
# apareca dentro do codigo-fonte mostrado no relatorio.
REPLACEMENTS = [
    ('<title>Coverage report</title>', '<title>Relatório de cobertura</title>'),
    ('<title>Coverage for ', '<title>Cobertura de '),
    ('<h1>Coverage report:', '<h1>Relatório de cobertura:'),
    ('<span class="text">Coverage for </span>', '<span class="text">Cobertura de </span>'),
    ('alt="Show/hide keyboard shortcuts"', 'alt="Mostrar/ocultar atalhos de teclado"'),
    ('<p class="legend">Shortcuts on this page</p>', '<p class="legend">Atalhos desta página</p>'),
    ('&nbsp; change column sorting', '&nbsp; mudar ordenação da coluna'),
    ('&nbsp; prev/next file', '&nbsp; arquivo anterior/próximo'),
    ('show/hide this help', 'mostrar/ocultar esta ajuda'),
    ('&nbsp; toggle line displays', '&nbsp; alternar exibição de linhas'),
    ('&nbsp; next/prev highlighted chunk', '&nbsp; próximo/anterior trecho destacado'),
    ('&nbsp; (zero) top of page', '&nbsp; (zero) topo da página'),
    ('&nbsp; (one) first highlighted chunk', '&nbsp; (um) primeiro trecho destacado'),
    ('&nbsp; up to the index', '&nbsp; subir para o índice'),
    ('placeholder="filter..."', 'placeholder="filtrar..."'),
    ('<label for="hide100">hide covered</label>', '<label for="hide100">ocultar cobertos</label>'),
    ('>File<span class="arrows">', '>Arquivo<span class="arrows">'),
    ('>class<span class="arrows">', '>classe<span class="arrows">'),
    ('>function<span class="arrows">', '>função<span class="arrows">'),
    ('>statements<span class="arrows">', '>instruções<span class="arrows">'),
    ('>missing<span class="arrows">', '>faltando<span class="arrows">'),
    ('>excluded<span class="arrows">', '>excluído<span class="arrows">'),
    ('>branches<span class="arrows">', '>desvios<span class="arrows">'),
    ('>partial<span class="arrows">', '>parcial<span class="arrows">'),
    ('>coverage<span class="arrows">', '>cobertura<span class="arrows">'),
    ('<th class="left" colspan="4">Statements</th>', '<th class="left" colspan="4">Instruções</th>'),
    ('<th class="left" colspan="3">Branches</th>', '<th class="left" colspan="3">Desvios</th>'),
    ('>&#xab; prev</a>', '>&#xab; anterior</a>'),
    ('>&#xbb; next</a>', '>&#xbb; próximo</a>'),
    ('&Hat; index</a>', '&Hat; índice</a>'),
    ('No items found using the specified filter.', 'Nenhum item encontrado com o filtro especificado.'),
    ('created at ', 'criado em '),
    ('>Files<', '>Arquivos<'),
    ('>Functions<', '>Funções<'),
    ('<span class="text"> run</span>', '<span class="text"> executadas</span>'),
    ('<span class="text"> missing</span>', '<span class="text"> faltando</span>'),
    ('<span class="text"> excluded</span>', '<span class="text"> excluídas</span>'),
    ('<span class="text"> partial</span>', '<span class="text"> parciais</span>'),
    ('title="Toggle lines run"', 'title="Alternar linhas executadas"'),
    ('title="Toggle lines missing"', 'title="Alternar linhas faltando"'),
    ('title="Toggle lines excluded"', 'title="Alternar linhas excluídas"'),
    ('title="Toggle lines partially run"', 'title="Alternar linhas parcialmente executadas"'),
    ('title="Click to sort"', 'title="Clique para ordenar"'),
]

STATEMENTS_RE = re.compile(r'(\d+) statements &nbsp;')


def translate_file(path: Path):
    text = path.read_text(encoding="utf-8")
    original = text
    for search, replace in REPLACEMENTS:
        text = text.replace(search, replace)
    text = STATEMENTS_RE.sub(r'\1 instruções &nbsp;', text)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    root = Path(sys.argv[1])
    changed = 0
    total = 0
    for html_file in root.glob("*.html"):
        total += 1
        if translate_file(html_file):
            changed += 1
    print(f"{root}: {changed}/{total} arquivos HTML traduzidos.")


if __name__ == "__main__":
    main()
