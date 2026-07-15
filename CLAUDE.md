# Instruções para o assistente (Claude Code / Cursor / similares)

Este repositório analisa testes A/B de % de cashback e recomenda qual variante escalar.
Quando o usuário pedir pra "analisar um teste", "rodar a análise de um parceiro" ou algo
parecido apontando um CSV, siga este fluxo:

## Fluxo padrão

1. Rode o pipeline (não reimplemente a análise por conta própria):

   ```
   python analisar.py <caminho-do-csv>
   ```

   - O CSV precisa do schema do case: `Data, Grupos de usuários, Parceiro, compradores, comissão, cashback, vendas totais`.
   - Pra rodar todos os arquivos de `dados/` de uma vez: `python analisar.py --todos`.
   - Se o usuário não quiser registrar na planilha: `--sem-registro`.

2. Leia o resumo gerado em `relatorios/<parceiro>.json` e responda pro usuário com:
   - a **decisão** e a **confiança**;
   - 2 ou 3 números que sustentam (margem líquida/dia do vencedor, diferença vs 2º colocado, p-valor);
   - os **alertas** de nível crítico/atenção, se houver — eles mudam a leitura do teste;
   - o caminho do relatório completo (`relatorios/<parceiro>.html`) pra abrir no navegador.

3. O registro na planilha acontece sozinho no passo 1 (CSV local sempre; Google Sheets se o
   webhook do n8n estiver configurado no `.env`). Se o console indicar que o Sheets não está
   configurado, avise o usuário e aponte o `n8n/README.md`.

## Regras

- **Não invente números.** Tudo que você reportar tem que vir do JSON/relatório gerado.
- Se o script falhar (coluna faltando, arquivo vazio), mostre a mensagem de erro e explique
  o que o arquivo precisa ter — não tente "consertar" o dataset silenciosamente.
- Se o usuário quiser explorar além do relatório (ex.: "e se olhar só o último mês?"),
  pode usar pandas livremente, mas deixe claro que é análise complementar, fora do pipeline.
- A metodologia (janela válida, margem líquida como métrica primária, permutação pareada)
  está documentada no README e nos relatórios — consulte antes de explicar.

## Exemplos de pedidos que este repo atende

- "Analisa o teste do Parceiro B" → `python analisar.py dados/dataset_02_parceiroB.csv`
- "Chegou o CSV de um teste novo do parceiro X, me diz qual variante escalar" → rodar com o arquivo indicado
- "Roda tudo de novo e atualiza a planilha" → `python analisar.py --todos`
