# -*- coding: utf-8 -*-
"""
Analisador de testes A/B de cashback — ponto de entrada.

Uso:
    python analisar.py dados/dataset_01_parceiroA.csv
    python analisar.py --todos                # roda todos os CSVs de dados/
    python analisar.py <arquivo> --sem-registro

Pra cada teste, o script:
  1. limpa e valida o dataset
  2. detecta a janela válida do teste (tratamentos estáveis e distintos)
  3. calcula as métricas por grupo e testa a significância da diferença
  4. gera relatório .html (pra apresentar) e .md (pra ler no GitHub)
  5. registra o resultado na planilha de acompanhamento (CSV + Google Sheets via n8n)
"""

import argparse
import glob
import os
import sys

from analise_ab import analisar_arquivo, fmt_brl, fmt_p
from relatorio import salvar_relatorios, gerar_resumo
from registro import registrar_csv, registrar_sheets

RAIZ = os.path.dirname(os.path.abspath(__file__))


def rodar(caminho_csv, args):
    print(f"\n>> Analisando {os.path.basename(caminho_csv)} ...")
    r = analisar_arquivo(caminho_csv)
    caminhos = salvar_relatorios(r, os.path.join(RAIZ, args.pasta_relatorios))
    resumo = gerar_resumo(r)

    m = r["metricas"]
    v = r["veredito"]
    n_criticos = sum(1 for a in r["alertas"] if a["nivel"] == "critico")
    n_atencao = sum(1 for a in r["alertas"] if a["nivel"] == "atencao")

    print(f"   {r['nome_teste']}")
    print(f"   Decisão : {v['decisao']}  [confiança {v['confianca']}]")
    print(f"   Margem  : {fmt_brl(m.loc[v['vencedor'], 'margem_dia'])}/dia no vencedor · "
          f"{fmt_p(r['significancia']['p_valor'])} vs 2º colocado")
    print(f"   Alertas : {n_criticos} crítico(s), {n_atencao} de atenção — detalhes no relatório")
    print(f"   Saída   : {os.path.relpath(caminhos['html'], RAIZ)} | .md | .json")

    if not args.sem_registro:
        rel = os.path.relpath(caminhos["html"], RAIZ)
        csv_path = registrar_csv(resumo, rel, os.path.join(RAIZ, "planilha", "acompanhamento_testes.csv"))
        print(f"   Planilha: linha registrada em {os.path.relpath(csv_path, RAIZ)}")
        print(f"   Sheets  : {registrar_sheets(resumo, rel)}")
    return r


def main():
    parser = argparse.ArgumentParser(
        description="Analisa um teste A/B de cashback e recomenda qual variante escalar."
    )
    parser.add_argument("arquivo", nargs="?", help="caminho do CSV do teste (schema do case)")
    parser.add_argument("--todos", action="store_true", help="analisa todos os CSVs da pasta dados/")
    parser.add_argument("--sem-registro", action="store_true", help="não escreve na planilha nem chama o n8n")
    parser.add_argument("--pasta-relatorios", default="relatorios", help="pasta de saída dos relatórios")
    args = parser.parse_args()

    if args.todos:
        arquivos = sorted(glob.glob(os.path.join(RAIZ, "dados", "*.csv")))
        if not arquivos:
            sys.exit("Nenhum CSV encontrado em dados/.")
    elif args.arquivo:
        if not os.path.exists(args.arquivo):
            sys.exit(f"Arquivo não encontrado: {args.arquivo}")
        arquivos = [args.arquivo]
    else:
        parser.print_help()
        sys.exit(1)

    for caminho in arquivos:
        try:
            rodar(caminho, args)
        except Exception as e:
            print(f"   ERRO ao analisar {os.path.basename(caminho)}: {e}")
            if len(arquivos) == 1:
                raise

    print("\nPronto.")


if __name__ == "__main__":
    main()
