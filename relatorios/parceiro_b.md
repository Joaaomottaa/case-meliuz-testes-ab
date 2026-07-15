# Cashback Parceiro B (05–06/2011)

**Decisão: ESCALAR Grupo 1 (4,0% de cashback) para 100% do tráfego** — confiança média

- Período do arquivo: 01/05/2011 a 30/06/2011 · Janela válida da análise: 01/05/2011 a 30/06/2011 (61 dias)
- Grupos: Grupo 1 (4,0% de cashback), Grupo 2 (6,0% de cashback), Grupo 3 (9,0% de cashback)
- Significância (margem, Grupo 1 vs Grupo 2): p<0,001, diferença média de R$ 2.351/dia (IC95%: R$ 2.064 a R$ 2.663)

## Por quê

- Grupo 1 (4,0% de cashback) entrega a maior margem líquida: R$ 4.698/dia (7,0% do GMV), +100% vs Grupo 2.
- Diferença consistente dia a dia: p<0,001 no teste de permutação pareado (61 dias), IC95% da diferença diária: R$ 2.064 a R$ 2.663.
- Grupo 1 é o grupo de menor cashback (tratei como controle provável): a recomendação na prática é não aumentar o benefício desse parceiro.

## Métricas por grupo (janela válida)

| Grupo | Cashback | Take | Compradores/dia | GMV/dia | Ticket | Margem/dia | Margem %GMV | Margem/comprador |
|---|---|---|---|---|---|---|---|---|
| Grupo 1 | 4,0% | 11,0% | 131 | R$ 67.112 | R$ 511 | **R$ 4.698** | 7,0% | R$ 36 |
| Grupo 2 | 6,0% | 11,0% | 89 | R$ 46.935 | R$ 535 | **R$ 2.347** | 5,0% | R$ 26 |
| Grupo 3 | 9,0% | 11,0% | 82 | R$ 43.114 | R$ 528 | **R$ 862** | 2,0% | R$ 10 |

## Alertas e qualidade dos dados

- **[Atenção] Volumes desiguais entre grupos** — Se o split fosse igualitário (33% cada), os volumes de compradores não deviam fugir tanto do esperado: Grupo 1 = 43%, Grupo 2 = 30%, Grupo 3 = 27%. O dataset não tem nº de usuários expostos, então não dá pra confirmar o split real. Comparações absolutas (total de compradores/GMV) ficam comprometidas — as métricas por comprador e por R$ de GMV seguem válidas.
- **[Atenção] Relação cashback × compradores invertida** — Os grupos com MAIS cashback têm MENOS compradores, o que não faz sentido econômico num split aleatório. Reforça a suspeita de alocação desigual ou públicos não comparáveis. Recomendo validar a instrumentação do teste antes de rodar outro com esse parceiro.
- **[Info] Picos de demanda coincidentes** — Dias com volume muito acima do normal em todos os grupos ao mesmo tempo (15/05, 22/05) — provável promoção ou data sazonal. Como afetam as variantes por igual, mantive na análise.
- **[Info] Estrutura dos dados ok** — Sem duplicatas, nulos, datas faltantes ou valores ilegíveis após a limpeza.

## Próximos passos

- Registrar usuários EXPOSTOS por grupo nos próximos testes (permite validar o split e calcular conversão).

## Metodologia (resumo)

1. Limpeza: parse de moeda BR, datas, duplicatas, nulos — tudo logado, nada descartado em silêncio.
2. Janela válida: o % efetivo de cashback (cashback/GMV) é reconstruído por grupo/dia; a comparação usa apenas o trecho em que cada grupo mantém o % original e as variantes são distintas entre si.
3. Métrica de decisão: margem líquida (comissão − cashback), que é o que sobra pro Méliuz. Compradores e GMV entram como guardrail de crescimento.
4. Significância: teste de permutação pareado por dia (10 mil permutações) — como os grupos vivem o mesmo calendário, comparar a diferença diária cancela sazonalidade e promoções comuns.

*Relatório gerado automaticamente pelo `analisar.py` em 14/07/2026 23:54. Arquivo de origem: `dataset_02_parceiroB.csv`.*