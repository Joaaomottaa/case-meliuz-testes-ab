# Cashback Parceiro C (07–08/2011)

**Decisão: ESCALAR Grupo 1 (5,0% de cashback) para 100% do tráfego** — confiança alta

- Período do arquivo: 01/07/2011 a 14/08/2011 · Janela válida da análise: 01/07/2011 a 14/08/2011 (45 dias)
- Grupos: Grupo 1 (5,0% de cashback), Grupo 2 (7,0% de cashback)
- Significância (margem, Grupo 1 vs Grupo 2): p<0,001, diferença média de R$ 773/dia (IC95%: R$ 715 a R$ 829)

## Por quê

- Grupo 1 (5,0% de cashback) entrega a maior margem líquida: R$ 773/dia (2,0% do GMV), enquanto Grupo 2 zera o resultado.
- Diferença consistente dia a dia: p<0,001 no teste de permutação pareado (45 dias), IC95% da diferença diária: R$ 715 a R$ 829.
- Grupo 1 é o grupo de menor cashback (tratei como controle provável): a recomendação na prática é não aumentar o benefício desse parceiro.

## Métricas por grupo (janela válida)

| Grupo | Cashback | Take | Compradores/dia | GMV/dia | Ticket | Margem/dia | Margem %GMV | Margem/comprador |
|---|---|---|---|---|---|---|---|---|
| Grupo 1 | 5,0% | 7,0% | 101 | R$ 38.632 | R$ 387 | **R$ 773** | 2,0% | R$ 8 |
| Grupo 2 | 7,0% | 7,0% | 100 | R$ 37.450 | R$ 374 | **R$ 0** | 0,0% | R$ 0 |

## Alertas e qualidade dos dados

- **[Crítico] Grupo 2 com margem zero ou negativa** — Grupo 2 repassa 7% de cashback com take de 7% — ou seja, devolve ~100% da comissão. Cada venda incremental dessa variante não deixa nada de resultado.
- **[Atenção] Queda abrupta no fim do período (Grupo 2)** — Nos últimos 5 dias, Grupo 2 caiu pra 37% do volume típico enquanto Grupo 1 seguiu estável — cheira a problema de tracking ou oferta fora do ar, não a comportamento de usuário. Conferir com o parceiro.
- **[Info] Estrutura dos dados ok** — Sem duplicatas, nulos, datas faltantes ou valores ilegíveis após a limpeza.

## Próximos passos

- Antes de testar cashback mais alto nesse parceiro, renegociar a comissão — no take atual não existe margem pra repassar.
- Checar com o parceiro/tracking o que houve nos últimos dias do teste.

## Metodologia (resumo)

1. Limpeza: parse de moeda BR, datas, duplicatas, nulos — tudo logado, nada descartado em silêncio.
2. Janela válida: o % efetivo de cashback (cashback/GMV) é reconstruído por grupo/dia; a comparação usa apenas o trecho em que cada grupo mantém o % original e as variantes são distintas entre si.
3. Métrica de decisão: margem líquida (comissão − cashback), que é o que sobra pro Méliuz. Compradores e GMV entram como guardrail de crescimento.
4. Significância: teste de permutação pareado por dia (10 mil permutações) — como os grupos vivem o mesmo calendário, comparar a diferença diária cancela sazonalidade e promoções comuns.

*Relatório gerado automaticamente pelo `analisar.py` em 14/07/2026 23:54. Arquivo de origem: `dataset_03_parceiroC.csv`.*