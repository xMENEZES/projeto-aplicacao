"""
Mini ferramenta de teste de mutacao -- alternativa ao mutmut, que nao roda
nativamente no Windows (pede WSL). Usa somente a biblioteca padrao do Python
(ast, subprocess, copy, shutil) -- sem nenhuma dependencia externa.

Operadores implementados (os mesmos documentados na skill gerador-de-testes,
em references/teste-mutacao.md):
  ROR - Relational Operator Replacement (<  <=  >  >=  ==  !=)
  AOR - Arithmetic Operator Replacement (+  -  *  /  //  %)
  COR - Conditional Operator Replacement (and / or)

Nao implementado nesta versao leve: SDL (Statement Deletion) e os operadores
especificos de OO (AMC/IOD/PCI) -- os 3 acima ja cobrem a maior parte dos
defeitos tipicos e sao suficientes para comparar a "força" de duas suites.

Uso:
    py mutation_test.py <arquivo_fonte.py> --test-cmd "<comando de teste>" [--cwd <dir>] [--max-mutants N] [--timeout N]

O <arquivo_fonte.py> é mutado UM MUTANTE POR VEZ, no proprio lugar (com backup
e restauracao automatica -- mesmo se o script for interrompido no meio, o
arquivo original e restaurado antes de sair). O <comando de teste> roda via
shell, a partir de --cwd (padrao: diretorio atual), e deve retornar codigo 0
quando os testes passam.

Saida: um resumo por mutante (morto/vivo) e o escore de mutacao final,
impresso no console e tambem salvo como JSON ao lado do arquivo fonte
(<arquivo_fonte>.mutation_report.json).
"""
from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REL_CYCLE = [ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq]
ARITH_CYCLE = [ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod]


def _op_name(op_type):
    return op_type.__name__


class SiteCollector(ast.NodeVisitor):
    """Primeira passada: so enumera os pontos mutaveis, na ordem de travessia."""

    def __init__(self):
        self.sites = []  # (kind, node_index_within_kind_irrelevant, lineno, description)

    def visit_Compare(self, node):
        for i, op in enumerate(node.ops):
            if type(op) in REL_CYCLE:
                idx = REL_CYCLE.index(type(op))
                new_type = REL_CYCLE[(idx + 1) % len(REL_CYCLE)]
                self.sites.append(("ROR", node.lineno,
                                    f"linha {node.lineno}: {_op_name(type(op))} -> {_op_name(new_type)}"))
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if type(node.op) in ARITH_CYCLE:
            idx = ARITH_CYCLE.index(type(node.op))
            new_type = ARITH_CYCLE[(idx + 1) % len(ARITH_CYCLE)]
            self.sites.append(("AOR", node.lineno,
                                f"linha {node.lineno}: {_op_name(type(node.op))} -> {_op_name(new_type)}"))
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        new_type = ast.Or if isinstance(node.op, ast.And) else ast.And
        self.sites.append(("COR", node.lineno,
                            f"linha {node.lineno}: {_op_name(type(node.op))} -> {_op_name(new_type)}"))
        self.generic_visit(node)


class MutationApplier(ast.NodeTransformer):
    """Segunda passada: reconta os sites na MESMA ordem de travessia e aplica
    a mutação só no site de índice `target_index` (0-based, contando todos os
    tipos juntos, na ordem em que aparecem no arquivo)."""

    def __init__(self, target_index):
        self.target_index = target_index
        self.counter = -1
        self.applied = False
        self.description = None

    def _is_target(self):
        self.counter += 1
        return self.counter == self.target_index

    def visit_Compare(self, node):
        # IMPORTANTE: checar/aplicar ANTES do generic_visit, para casar com a
        # ordem "pai antes dos filhos" usada pelo SiteCollector (senão o
        # indice fica apontando para o no errado em expressoes aninhadas).
        for i, op in enumerate(node.ops):
            if type(op) in REL_CYCLE:
                if self._is_target():
                    idx = REL_CYCLE.index(type(op))
                    new_type = REL_CYCLE[(idx + 1) % len(REL_CYCLE)]
                    self.description = f"linha {node.lineno}: ROR {_op_name(type(op))} -> {_op_name(new_type)}"
                    node.ops[i] = new_type()
                    self.applied = True
        self.generic_visit(node)
        return node

    def visit_BinOp(self, node):
        if type(node.op) in ARITH_CYCLE:
            if self._is_target():
                idx = ARITH_CYCLE.index(type(node.op))
                new_type = ARITH_CYCLE[(idx + 1) % len(ARITH_CYCLE)]
                self.description = f"linha {node.lineno}: AOR {_op_name(type(node.op))} -> {_op_name(new_type)}"
                node.op = new_type()
                self.applied = True
        self.generic_visit(node)
        return node

    def visit_BoolOp(self, node):
        if self._is_target():
            new_type = ast.Or if isinstance(node.op, ast.And) else ast.And
            self.description = f"linha {node.lineno}: COR {_op_name(type(node.op))} -> {_op_name(new_type)}"
            node.op = new_type()
            self.applied = True
        self.generic_visit(node)
        return node


def collect_sites(source: str):
    tree = ast.parse(source)
    collector = SiteCollector()
    collector.visit(tree)
    return collector.sites


def make_mutant_source(source: str, target_index: int):
    tree = ast.parse(source)
    applier = MutationApplier(target_index)
    new_tree = applier.visit(tree)
    if not applier.applied:
        return None, None
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree), applier.description


def run_tests(test_cmd: str, cwd: str, timeout: int, extra_env: dict) -> tuple[bool, str]:
    """Retorna (passou, motivo). passou=True significa que os testes passaram
    (logo o mutante SOBREVIVEU).

    Usa Popen + taskkill /T em vez de subprocess.run(timeout=...) porque, no
    Windows, com shell=True o processo direto e o cmd.exe -- matar so ele (o
    que o timeout do subprocess.run faz por padrao) deixa o python/pytest de
    verdade orfao e travado por baixo, segurando os pipes de saida para
    sempre. taskkill /F /T mata a arvore inteira (cmd.exe + todos os filhos)."""
    import os
    env = os.environ.copy()
    env.update(extra_env)
    proc = subprocess.Popen(test_cmd, shell=True, cwd=cwd, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        proc.communicate(timeout=timeout)
        return proc.returncode == 0, f"exit={proc.returncode}"
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True)
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
        return False, "timeout (arvore de processos finalizada; tratado como morto)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source_file", help="Arquivo .py a ser mutado (caminho relativo ou absoluto)")
    ap.add_argument("--test-cmd", required=True, help="Comando de teste completo, roda via shell")
    ap.add_argument("--cwd", default=".", help="Diretorio de onde rodar --test-cmd (default: atual)")
    ap.add_argument("--max-mutants", type=int, default=40, help="Limite de mutantes a gerar (default 40)")
    ap.add_argument("--timeout", type=int, default=90, help="Timeout por mutante em segundos (default 90)")
    ap.add_argument("--start-at", type=int, default=0,
                     help="Pula os primeiros N mutantes da lista (para retomar uma rodada "
                          "que travou/foi interrompida sem repetir os que ja rodaram)")
    ap.add_argument("--disable-pytest-plugin-autoload", action="store_true",
                     help="Seta PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 no subprocesso. "
                          "Use isso quando o venv tiver mais de um checkout do mesmo pacote "
                          "instalado (ex.: 'pip install -e .' de outro clone) -- senao o pytest "
                          "pode autocarregar o plugin do pacote errado e mascarar a mutacao. "
                          "Ver nota no relatorio sobre o incidente do Celery.")
    args = ap.parse_args()
    extra_env = {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"} if args.disable_pytest_plugin_autoload else {}

    source_path = Path(args.source_file).resolve()
    original = source_path.read_text(encoding="utf-8")
    backup_path = source_path.with_suffix(source_path.suffix + ".mutation_backup")
    shutil.copy2(source_path, backup_path)

    sites = collect_sites(original)
    total_sites = len(sites)
    if total_sites == 0:
        print(f"Nenhum ponto mutavel (ROR/AOR/COR) encontrado em {source_path}.")
        backup_path.unlink(missing_ok=True)
        return

    if total_sites > args.max_mutants:
        step = total_sites / args.max_mutants
        indices = sorted({int(i * step) for i in range(args.max_mutants)})
    else:
        indices = list(range(total_sites))

    if args.start_at:
        print(f"Retomando a partir do mutante {args.start_at + 1} (pulando os {args.start_at} primeiros).")
        indices = indices[args.start_at:]

    print(f"Arquivo: {source_path}")
    print(f"Pontos mutaveis encontrados: {total_sites} | Mutantes a rodar: {len(indices)}")
    print(f"Comando de teste: {args.test_cmd}")
    print(f"Diretorio de execucao: {Path(args.cwd).resolve()}")
    print("-" * 70)

    results = []
    try:
        for n, idx in enumerate(indices, 1):
            mutant_source, description = make_mutant_source(original, idx)
            if mutant_source is None:
                continue
            source_path.write_text(mutant_source, encoding="utf-8")
            t0 = time.time()
            survived, reason = run_tests(args.test_cmd, args.cwd, args.timeout, extra_env)
            elapsed = time.time() - t0
            status = "VIVO" if survived else "morto"
            print(f"[{n}/{len(indices)}] {description}  ->  {status}  ({reason}, {elapsed:.1f}s)")
            results.append({"index": idx, "description": description, "survived": survived, "reason": reason})
            # restaura antes do proximo mutante
            source_path.write_text(original, encoding="utf-8")
    finally:
        # garante que o arquivo original volta, aconteca o que acontecer
        shutil.copy2(backup_path, source_path)
        backup_path.unlink(missing_ok=True)

    mortos = sum(1 for r in results if not r["survived"])
    vivos = sum(1 for r in results if r["survived"])
    gerados = len(results)
    score = (mortos / gerados * 100) if gerados else 0.0

    print("-" * 70)
    print(f"Mutantes gerados: {gerados} | Mortos: {mortos} | Vivos: {vivos}")
    print(f"Escore de mutacao: {score:.1f}%")
    if vivos:
        print("\nMutantes VIVOS (a suite nao percebeu estas mudancas):")
        for r in results:
            if r["survived"]:
                print(f"  - {r['description']}")

    report_path = source_path.with_suffix(source_path.suffix + ".mutation_report.json")
    report_path.write_text(json.dumps({
        "arquivo": str(source_path),
        "total_sites_no_arquivo": total_sites,
        "mutantes_gerados": gerados,
        "mortos": mortos,
        "vivos": vivos,
        "escore_mutacao_pct": round(score, 1),
        "detalhes": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRelatorio salvo em: {report_path}")


if __name__ == "__main__":
    main()
