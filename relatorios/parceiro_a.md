# Cashback Parceiro A (01–04/2011)

**Decisão: ESCALAR Grupo 1 (3,0% de cashback) para 100% do tráfego** — confiança média

- Período do arquivo: 01/01/2011 a 02/04/2011 · Janela válida da análise: 01/01/2011 a 22/02/2011 (53 dias)
- Grupos: Grupo 1 (3,0% de cashback), Grupo 2 (5,5% de cashback), Grupo 3 (8,0% de cashback)
- Significância (margem, Grupo 1 vs Grupo 2): p<0,001, diferença média de R$ 781/dia (IC95%: R$ 452 a R$ 1.114)

## Por quê

- Grupo 1 (3,0% de cashback) entrega a maior margem líquida: R$ 5.420/dia (8,0% do GMV), +17% vs Grupo 2.
- Diferença consistente dia a dia: p<0,001 no teste de permutação pareado (53 dias), IC95% da diferença diária: R$ 452 a R$ 1.114.
- Trade-off de crescimento: Grupo 3 traz +33 compradores/dia (+28p.p.), mas cada comprador incremental custa R$ 160 de cashback e devolve R$ 80 de comissão — não se paga sem considerar recompra/LTV.
- Grupo 1 é o grupo de menor cashback (tratei como controle provável): a recomendação na prática é não aumentar o benefício desse parceiro.

## Métricas por grupo (janela válida)

| Grupo | Cashback | Take | Compradores/dia | GMV/dia | Ticket | Margem/dia | Margem %GMV | Margem/comprador |
|---|---|---|---|---|---|---|---|---|
| Grupo 1 | 3,0% | 11,0% | 118 | R$ 68.043 | R$ 584 | **R$ 5.420** | 8,0% | R$ 46 |
| Grupo 2 | 5,5% | 11,0% | 139 | R$ 84.346 | R$ 614 | **R$ 4.639** | 5,5% | R$ 33 |
| Grupo 3 | 8,0% | 11,0% | 151 | R$ 91.801 | R$ 614 | **R$ 2.781** | 3,0% | R$ 18 |

## Regimes de cashback detectados

O teste não manteve os tratamentos estáveis do início ao fim — a análise usa só a primeira janela:

| Período | Dias | Grupo 1 | Grupo 2 | Grupo 3 |
|---|---|---|---|---|
| 01/01 a 22/02 | 53 | 3,0% | 5,5% | 8,0% |
| 23/02 a 23/02 | 1 | 5,0% | 5,5% | 6,7% |
| 24/02 a 10/03 | 15 | 5,0% | 5,5% | 4,0% |
| 11/03 a 14/03 | 4 | 10,0% | 10,0% | 10,0% |
| 15/03 a 02/04 | 19 | 5,0% | 5,0% | 5,0% |

## Alertas e qualidade dos dados

- **[Crítico] Tratamentos alterados durante o teste** — Os % de cashback dos grupos mudaram ao longo do período. A comparação usa apenas a janela em que as variantes originais ficaram estáveis (01/01/2011 a 22/02/2011); 39 dia(s) posteriores foram excluídos. Vale investigar com o time por que o teste foi mexido antes de encerrar.
- **[Info] Picos de demanda coincidentes** — Dias com volume muito acima do normal em todos os grupos ao mesmo tempo (08/01, 11/01, 13/01) — provável promoção ou data sazonal. Como afetam as variantes por igual, mantive na análise.
- **[Info] Estrutura dos dados ok** — Sem duplicatas, nulos, datas faltantes ou valores ilegíveis após a limpeza.

## Próximos passos

- Se a estratégia com esse parceiro for base ativa (e não margem), medir retenção/recompra dos compradores de Grupo 3 antes de descartar a variante.
- Alinhar governança de testes: variante não pode mudar no meio do experimento.

## Metodologia (resumo)

1. Limpeza: parse de moeda BR, datas, duplicatas, nulos — tudo logado, nada descartado em silêncio.
2. Janela válida: o % efetivo de cashback (cashback/GMV) é reconstruído por grupo/dia; a comparação usa apenas o trecho em que cada grupo mantém o % original e as variantes são distintas entre si.
3. Métrica de decisão: margem líquida (comissão − cashback), que é o que sobra pro Méliuz. Compradores e GMV entram como guardrail de crescimento.
4. Significância: teste de permutação pareado por dia (10 mil permutações) — como os grupos vivem o mesmo calendário, comparar a diferença diária cancela sazonalidade e promoções comuns.

*Relatório gerado automaticamente pelo `analisar.py` em 19/07/2026 23:10. Arquivo de origem: `dataset_01_parceiroA.csv`.*