# -*- coding: utf-8 -*-
"""
Geração dos relatórios de cada teste: Markdown (pra leitura rápida no GitHub)
e HTML self-contained (pra apresentar pra gestor — abre em qualquer navegador,
sem dependência externa).

Os gráficos são SVG gerados aqui mesmo. Preferi isso a matplotlib porque o
resultado fica interativo (tooltip), leve e com a mesma cara dos dashboards
que já faço em HTML/CSS/JS puro.
"""

import json
import os
import re
from datetime import datetime

import numpy as np
import pandas as pd

from analise_ab import fmt_brl, fmt_num, fmt_p

# paleta categórica com contraste validado (claro/escuro) — 1 cor fixa por grupo
CORES_CLARO = ["#2a78d6", "#1baf7a", "#eda100", "#4a3aa7"]
CORES_ESCURO = ["#3987e5", "#199e70", "#c98500", "#9085e9"]

NIVEL_BADGE = {
    "critico": ("●", "Crítico", "badge-critico"),
    "atencao": ("▲", "Atenção", "badge-atencao"),
    "info": ("ℹ", "Info", "badge-info"),
}


def slug(texto):
    s = re.sub(r"[^a-z0-9]+", "_", str(texto).lower())
    return s.strip("_")


# ---------------------------------------------------------------- Markdown --

def gerar_markdown(r):
    m = r["metricas"]
    v = r["veredito"]
    sig = r["significancia"]
    ini, fim = r["regimes"]["janela"]
    d0, d1 = r["periodo_total"]

    linhas = [
        f"# {r['nome_teste']}",
        "",
        f"**Decisão: {v['decisao']}** — confiança {v['confianca']}",
        "",
        f"- Período do arquivo: {d0:%d/%m/%Y} a {d1:%d/%m/%Y} · "
        f"Janela válida da análise: {ini:%d/%m/%Y} a {fim:%d/%m/%Y} ({r['regimes']['dias_validos']} dias)",
        f"- Grupos: " + ", ".join(f"{g} ({fmt_num(m.loc[g, 'cb_pct'])}% de cashback)" for g in sorted(m.index)),
        f"- Significância (margem, {m.index[0]} vs {m.index[1]}): {fmt_p(sig['p_valor'])}, "
        f"diferença média de {fmt_brl(sig['diff_media'])}/dia (IC95%: {fmt_brl(sig['ic95'][0])} a {fmt_brl(sig['ic95'][1])})",
        "",
        "## Por quê",
        "",
    ]
    linhas += [f"- {j}" for j in v["justificativa"]]

    linhas += [
        "",
        "## Métricas por grupo (janela válida)",
        "",
        "| Grupo | Cashback | Take | Compradores/dia | GMV/dia | Ticket | Margem/dia | Margem %GMV | Margem/comprador |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for g in sorted(m.index):
        x = m.loc[g]
        linhas.append(
            f"| {g} | {fmt_num(x['cb_pct'])}% | {fmt_num(x['take_pct'])}% | {fmt_num(x['compradores_dia'], 0)} "
            f"| {fmt_brl(x['gmv_dia'])} | {fmt_brl(x['ticket'])} | **{fmt_brl(x['margem_dia'])}** "
            f"| {fmt_num(x['margem_pct_gmv'])}% | {fmt_brl(x['margem_por_comprador'])} |"
        )

    if len(r["regimes"]["trechos"]) > 1:
        linhas += [
            "",
            "## Regimes de cashback detectados",
            "",
            "O teste não manteve os tratamentos estáveis do início ao fim — a análise usa só a primeira janela:",
            "",
            "| Período | Dias | " + " | ".join(sorted(m.index)) + " |",
            "|---|---|" + "---|" * len(m.index),
        ]
        for t in r["regimes"]["trechos"]:
            cbs = " | ".join(f"{fmt_num(t['cb_por_grupo'].get(g, np.nan))}%" for g in sorted(m.index))
            linhas.append(f"| {t['inicio']:%d/%m} a {t['fim']:%d/%m} | {t['dias']} | {cbs} |")

    linhas += ["", "## Alertas e qualidade dos dados", ""]
    for a in r["alertas"]:
        icone, rotulo, _ = NIVEL_BADGE[a["nivel"]]
        linhas.append(f"- **[{rotulo}] {a['titulo']}** — {a['texto']}")

    if v["proximos_passos"]:
        linhas += ["", "## Próximos passos", ""]
        linhas += [f"- {p}" for p in v["proximos_passos"]]

    linhas += [
        "",
        "## Metodologia (resumo)",
        "",
        "1. Limpeza: parse de moeda BR, datas, duplicatas, nulos — tudo logado, nada descartado em silêncio.",
        "2. Janela válida: o % efetivo de cashback (cashback/GMV) é reconstruído por grupo/dia; a comparação "
        "usa apenas o trecho em que cada grupo mantém o % original e as variantes são distintas entre si.",
        "3. Métrica de decisão: margem líquida (comissão − cashback), que é o que sobra pro Méliuz. "
        "Compradores e GMV entram como guardrail de crescimento.",
        "4. Significância: teste de permutação pareado por dia (10 mil permutações) — como os grupos vivem o "
        "mesmo calendário, comparar a diferença diária cancela sazonalidade e promoções comuns.",
        "",
        f"*Relatório gerado automaticamente pelo `analisar.py` em {datetime.now():%d/%m/%Y %H:%M}. "
        f"Arquivo de origem: `{r['arquivo']}`.*",
    ]
    return "\n".join(linhas)


# ------------------------------------------------------------- SVG helpers --

def _ticks(vmax, vmin=0.0, n=4):
    """Escolhe ~n valores redondos entre vmin e vmax."""
    if vmax <= vmin:
        vmax = vmin + 1
    bruto = (vmax - vmin) / n
    mag = 10 ** np.floor(np.log10(bruto))
    for mult in (1, 2, 2.5, 5, 10):
        passo = mult * mag
        if passo >= bruto:
            break
    t0 = np.floor(vmin / passo) * passo
    ticks = []
    t = t0
    while t <= vmax * 1.001:
        if t >= vmin - 1e-9:
            ticks.append(round(t, 6))
        t += passo
    return ticks


def _fmt_tick(v, unidade):
    if unidade == "pct":
        return fmt_num(v, 0) + "%"
    if abs(v) >= 1000:
        return fmt_num(v / 1000, 0) + " mil"
    return fmt_num(v, 0)


def _svg_linhas(pivo, unidade, cores, janela=None, altura=300, chart_id="c"):
    """
    Gráfico de linhas (datas x grupos). Se `janela` for passada e terminar antes
    do fim da série, a região descartada ganha um sombreado com rótulo.
    Devolve (svg, json_dados) — o JSON alimenta o tooltip em JS.
    """
    L, R, T, B = 62, 118, 14, 30
    W, H = 860, altura
    pw, ph = W - L - R, H - T - B

    datas = list(pivo.index)
    grupos = list(pivo.columns)
    n = len(datas)
    vmax = float(np.nanmax(pivo.to_numpy())) * 1.06
    vmin = min(0.0, float(np.nanmin(pivo.to_numpy())))
    ticks = _ticks(vmax, vmin)

    def x(i):
        return L + (i / max(n - 1, 1)) * pw

    def y(v):
        return T + ph - (v - vmin) / (vmax - vmin) * ph

    p = [f'<svg viewBox="0 0 {W} {H}" class="grafico" data-chart="{chart_id}" role="img">']

    # sombreado do trecho fora da janela válida
    if janela is not None and janela[1] < datas[-1]:
        corte = next(i for i, d in enumerate(datas) if d > janela[1])
        x0 = x(corte) - (x(1) - x(0)) / 2
        p.append(f'<rect x="{x0:.1f}" y="{T}" width="{L + pw - x0:.1f}" height="{ph}" class="fora-janela"/>')
        p.append(f'<text x="{(x0 + L + pw) / 2:.1f}" y="{T + 14}" class="rotulo-fora">fora da janela válida</text>')

    # grade e eixo y
    for t in ticks:
        p.append(f'<line x1="{L}" y1="{y(t):.1f}" x2="{L + pw}" y2="{y(t):.1f}" class="grade"/>')
        p.append(f'<text x="{L - 8}" y="{y(t) + 4:.1f}" text-anchor="end" class="tick">{_fmt_tick(t, unidade)}</text>')
    p.append(f'<line x1="{L}" y1="{y(max(vmin, 0)):.1f}" x2="{L + pw}" y2="{y(max(vmin, 0)):.1f}" class="eixo"/>')

    # eixo x: ~6 datas
    passo_x = max(1, (n - 1) // 5)
    for i in range(0, n, passo_x):
        p.append(f'<text x="{x(i):.1f}" y="{T + ph + 20}" text-anchor="middle" class="tick">{datas[i]:%d/%m}</text>')

    # linhas
    for gi, g in enumerate(grupos):
        pts = " ".join(
            f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(pivo[g]) if not pd.isna(v)
        )
        p.append(f'<polyline points="{pts}" fill="none" stroke="var(--s{gi + 1})" stroke-width="2" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')

    # rótulos diretos no fim de cada linha (com anti-colisão simples)
    finais = sorted(
        [(float(pivo[g].dropna().iloc[-1]), gi, g) for gi, g in enumerate(grupos)], key=lambda t: y(t[0])
    )
    ys_rotulo = []
    for vf, gi, g in finais:
        yy = y(vf)
        while any(abs(yy - o) < 15 for o in ys_rotulo):
            yy += 15
        ys_rotulo.append(yy)
        p.append(f'<circle cx="{L + pw + 6}" cy="{yy:.1f}" r="4" fill="var(--s{gi + 1})"/>')
        p.append(f'<text x="{L + pw + 14}" y="{yy + 4:.1f}" class="rotulo-serie">{g}</text>')

    # camada de hover: uma coluna invisível por data + linha-guia + ponto
    p.append(f'<line class="guia" x1="0" x2="0" y1="{T}" y2="{T + ph}" style="display:none"/>')
    for gi, _ in enumerate(grupos):
        p.append(f'<circle class="ponto-hover ph-{gi}" r="4.5" style="display:none"/>')
    passo_w = pw / max(n - 1, 1)
    for i in range(n):
        p.append(f'<rect class="hit" data-i="{i}" x="{x(i) - passo_w / 2:.1f}" y="{T}" '
                 f'width="{passo_w:.1f}" height="{ph}" fill="transparent"/>')

    p.append("</svg>")

    dados = {
        "datas": [d.strftime("%d/%m/%Y") for d in datas],
        "series": {g: [None if pd.isna(v) else round(float(v), 2) for v in pivo[g]] for g in grupos},
        "unidade": unidade,
        "T": T, "ph": ph, "L": L, "pw": pw, "n": n, "vmin": vmin, "vmax": vmax,
    }
    return "\n".join(p), json.dumps(dados, ensure_ascii=False)


def _svg_barras(metricas, coluna, unidade, titulo):
    """Barras horizontais — uma métrica, um grupo por linha, rótulo no fim."""
    grupos = sorted(metricas.index)
    W, alt_barra, gap = 280, 26, 10
    L = 8
    T = 6
    H = T + len(grupos) * (alt_barra + gap) + 6
    vmax = max(float(metricas[coluna].max()), 1e-9)
    p = [f'<svg viewBox="0 0 {W} {H}" class="mini-barras" role="img" aria-label="{titulo}">']
    for i, g in enumerate(grupos):
        v = float(metricas.loc[g, coluna])
        yy = T + i * (alt_barra + gap)
        largura = max((W - L - 96) * v / vmax, 2)
        rotulo = fmt_brl(v) if unidade == "brl" else fmt_num(v, 0)
        p.append(f'<rect x="{L}" y="{yy}" width="{largura:.1f}" height="{alt_barra}" rx="4" fill="var(--s{i + 1})">'
                 f'<title>{g}: {rotulo}</title></rect>')
        p.append(f'<text x="{L + largura + 8:.1f}" y="{yy + alt_barra / 2 + 4}" class="valor-barra">{rotulo}</text>')
    p.append("</svg>")
    return "\n".join(p)


# ----------------------------------------------------------------- HTML ----

def gerar_html(r):
    m = r["metricas"]
    v = r["veredito"]
    sig = r["significancia"]
    ini, fim = r["regimes"]["janela"]
    d0, d1 = r["periodo_total"]
    grupos = sorted(m.index)

    pivo_margem = r["df"].pivot_table(index="data", columns="grupo", values="margem")[grupos]
    pivo_comp = r["df"].pivot_table(index="data", columns="grupo", values="compradores")[grupos]
    pivo_cb = r["df"].pivot_table(index="data", columns="grupo", values="cb_pct")[grupos]

    svg_cb, dados_cb = _svg_linhas(pivo_cb, "pct", CORES_CLARO, r["regimes"]["janela"], 240, "cb")
    svg_margem, dados_margem = _svg_linhas(pivo_margem, "brl", CORES_CLARO, r["regimes"]["janela"], 300, "margem")
    svg_comp, dados_comp = _svg_linhas(pivo_comp, "int", CORES_CLARO, r["regimes"]["janela"], 300, "comp")

    vars_claro = "".join(f"--s{i + 1}:{c};" for i, c in enumerate(CORES_CLARO[: len(grupos)]))
    vars_escuro = "".join(f"--s{i + 1}:{c};" for i, c in enumerate(CORES_ESCURO[: len(grupos)]))

    legenda = "".join(
        f'<span class="chip"><i style="background:var(--s{i + 1})"></i>{g} · {fmt_num(m.loc[g, "cb_pct"])}%</span>'
        for i, g in enumerate(grupos)
    )

    linhas_tabela = ""
    for i, g in enumerate(grupos):
        x = m.loc[g]
        destaque = ' class="linha-vencedor"' if g == v["vencedor"] else ""
        linhas_tabela += f"""<tr{destaque}>
<td><span class="chip"><i style="background:var(--s{i + 1})"></i>{g}</span></td>
<td>{fmt_num(x['cb_pct'])}%</td><td>{fmt_num(x['take_pct'])}%</td>
<td>{fmt_num(x['compradores_dia'], 0)}</td><td>{fmt_brl(x['gmv_dia'])}</td><td>{fmt_brl(x['ticket'])}</td>
<td>{fmt_brl(x['comissao_dia'])}</td><td>{fmt_brl(x['cashback_dia'])}</td>
<td><b>{fmt_brl(x['margem_dia'])}</b></td><td>{fmt_num(x['margem_pct_gmv'])}%</td>
<td>{fmt_brl(x['margem_por_comprador'])}</td>
</tr>"""

    tabela_regimes = ""
    if len(r["regimes"]["trechos"]) > 1:
        linhas_reg = ""
        for t in r["regimes"]["trechos"]:
            cbs = "".join(f"<td>{fmt_num(t['cb_por_grupo'].get(g, np.nan))}%</td>" for g in grupos)
            dentro = t["fim"] <= fim
            tag = '<span class="tag-ok">usado</span>' if dentro else '<span class="tag-fora">descartado</span>'
            linhas_reg += f"<tr><td>{t['inicio']:%d/%m} a {t['fim']:%d/%m}</td><td>{t['dias']}</td>{cbs}<td>{tag}</td></tr>"
        tabela_regimes = f"""
<section>
<h2>Regimes de cashback detectados</h2>
<p class="nota">O teste não manteve os tratamentos estáveis até o fim. A ferramenta reconstruiu o % efetivo
(cashback ÷ GMV) por grupo/dia e limitou a comparação à janela em que as variantes originais estavam valendo.</p>
<div class="scroll"><table>
<thead><tr><th>Período</th><th>Dias</th>{"".join(f"<th>{g}</th>" for g in grupos)}<th>Status</th></tr></thead>
<tbody>{linhas_reg}</tbody></table></div>
</section>"""

    alertas_html = ""
    for a in r["alertas"]:
        icone, rotulo, classe = NIVEL_BADGE[a["nivel"]]
        alertas_html += f"""<li class="alerta">
<span class="badge {classe}">{icone} {rotulo}</span>
<div><b>{a['titulo']}.</b> {a['texto']}</div></li>"""

    proximos_html = "".join(f"<li>{p}</li>" for p in v["proximos_passos"]) or "<li>Sem pendências além do rollout.</li>"
    justificativa_html = "".join(f"<li>{j}</li>" for j in v["justificativa"])

    conf_classe = {"alta": "conf-alta", "média": "conf-media", "baixa": "conf-baixa"}[v["confianca"]]

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{r['nome_teste']} — análise A/B</title>
<style>
:root {{
  color-scheme: light dark;
  --fundo:#f9f9f7; --superficie:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --mudo:#898781;
  --grade:#e1e0d9; --eixo:#c3c2b7; --borda:rgba(11,11,11,.10);
  --ok:#0ca30c; --critico:#d03b3b; --atencao:#b45309; --acento:#f5286e;
  {vars_claro}
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --fundo:#0d0d0d; --superficie:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --mudo:#898781;
    --grade:#2c2c2a; --eixo:#383835; --borda:rgba(255,255,255,.10);
    {vars_escuro}
  }}
}}
* {{ box-sizing:border-box; margin:0; }}
body {{ background:var(--fundo); color:var(--ink); font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; padding:28px 20px 60px; }}
main {{ max-width:980px; margin:0 auto; }}
header {{ border-top:3px solid var(--acento); background:var(--superficie); border-radius:0 0 12px 12px;
  border:1px solid var(--borda); border-top:3px solid var(--acento); padding:22px 26px; margin-bottom:18px; }}
h1 {{ font-size:22px; }}
.sub {{ color:var(--ink2); margin-top:4px; font-size:14px; }}
.decisao {{ display:flex; gap:14px; align-items:center; flex-wrap:wrap; margin-top:16px; }}
.selo {{ background:color-mix(in srgb, var(--ok) 12%, transparent); border:1px solid var(--ok);
  color:var(--ink); padding:10px 16px; border-radius:10px; font-weight:600; font-size:16px; }}
.conf {{ font-size:13px; color:var(--ink2); }}
.conf b.conf-alta {{ color:var(--ok); }} .conf b.conf-media {{ color:var(--atencao); }} .conf b.conf-baixa {{ color:var(--critico); }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin-bottom:18px; }}
.card {{ background:var(--superficie); border:1px solid var(--borda); border-radius:12px; padding:14px 16px; }}
.card .k {{ font-size:12.5px; color:var(--ink2); }}
.card .v {{ font-size:22px; font-weight:650; margin-top:2px; }}
.card .d {{ font-size:12.5px; color:var(--mudo); margin-top:2px; }}
section {{ background:var(--superficie); border:1px solid var(--borda); border-radius:12px; padding:20px 24px; margin-bottom:18px; }}
h2 {{ font-size:16px; margin-bottom:10px; }}
.nota {{ color:var(--ink2); font-size:13.5px; margin-bottom:12px; }}
.legenda {{ display:flex; gap:14px; flex-wrap:wrap; margin-bottom:8px; }}
.chip {{ display:inline-flex; align-items:center; gap:6px; font-size:13px; color:var(--ink2); white-space:nowrap; }}
.chip i {{ width:10px; height:10px; border-radius:3px; display:inline-block; }}
.grafico {{ width:100%; height:auto; display:block; }}
.grafico .grade {{ stroke:var(--grade); stroke-width:1; }}
.grafico .eixo {{ stroke:var(--eixo); stroke-width:1; }}
.grafico .tick {{ fill:var(--mudo); font-size:11px; }}
.grafico .rotulo-serie {{ fill:var(--ink2); font-size:12px; }}
.grafico .fora-janela {{ fill:var(--ink); opacity:.05; }}
.grafico .rotulo-fora {{ fill:var(--mudo); font-size:11px; text-anchor:middle; }}
.grafico .guia {{ stroke:var(--eixo); stroke-dasharray:3 3; }}
.grafico .ponto-hover {{ stroke:var(--superficie); stroke-width:2; }}
.mini-barras {{ width:100%; height:auto; }}
.mini-barras .valor-barra {{ fill:var(--ink); font-size:13px; font-weight:600; }}
.tres-colunas {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:18px; }}
.tres-colunas h3 {{ font-size:13px; color:var(--ink2); font-weight:600; margin-bottom:6px; }}
.scroll {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:13.5px; }}
th, td {{ padding:8px 10px; text-align:right; border-bottom:1px solid var(--grade); white-space:nowrap;
  font-variant-numeric:tabular-nums; }}
th:first-child, td:first-child {{ text-align:left; }}
th {{ color:var(--ink2); font-weight:600; font-size:12.5px; }}
.linha-vencedor {{ background:color-mix(in srgb, var(--ok) 7%, transparent); }}
.tag-ok {{ color:var(--ok); font-weight:600; font-size:12px; }}
.tag-fora {{ color:var(--mudo); font-size:12px; }}
ul.limpa {{ list-style:none; display:flex; flex-direction:column; gap:10px; }}
.alerta {{ display:flex; gap:12px; align-items:flex-start; font-size:14px; }}
.alerta .badge {{ flex:0 0 auto; font-size:12px; font-weight:650; padding:3px 9px; border-radius:99px; border:1px solid; }}
.badge-critico {{ color:var(--critico); border-color:var(--critico); }}
.badge-atencao {{ color:var(--atencao); border-color:var(--atencao); }}
.badge-info {{ color:var(--ink2); border-color:var(--eixo); }}
ol, section ul {{ padding-left:20px; }} section li {{ margin-bottom:6px; }}
details {{ margin-top:6px; }} summary {{ cursor:pointer; color:var(--ink2); font-weight:600; font-size:14px; }}
details p {{ margin:8px 0; font-size:13.5px; color:var(--ink2); }}
footer {{ text-align:center; color:var(--mudo); font-size:12.5px; margin-top:24px; }}
#tooltip {{ position:fixed; display:none; background:var(--superficie); border:1px solid var(--borda);
  border-radius:8px; padding:8px 12px; font-size:12.5px; pointer-events:none; box-shadow:0 4px 14px rgba(0,0,0,.12);
  z-index:10; min-width:150px; }}
#tooltip .t-data {{ color:var(--ink2); font-weight:600; margin-bottom:4px; }}
#tooltip .t-linha {{ display:flex; justify-content:space-between; gap:14px; }}
#tooltip .t-linha b {{ font-variant-numeric:tabular-nums; }}
</style>
</head>
<body>
<main>

<header>
  <h1>{r['nome_teste']}</h1>
  <div class="sub">Teste A/B de % de cashback · {d0:%d/%m/%Y} a {d1:%d/%m/%Y} ·
  janela válida: {ini:%d/%m/%Y} a {fim:%d/%m/%Y} ({r['regimes']['dias_validos']} dias) ·
  fonte: {r['arquivo']}</div>
  <div class="decisao">
    <div class="selo">✔ {v['decisao']}</div>
    <div class="conf">confiança <b class="{conf_classe}">{v['confianca']}</b></div>
  </div>
</header>

<div class="cards">
  <div class="card"><div class="k">Margem líquida do vencedor</div>
    <div class="v">{fmt_brl(m.loc[v['vencedor'], 'margem_dia'])}/dia</div>
    <div class="d">{fmt_num(m.loc[v['vencedor'], 'margem_pct_gmv'])}% do GMV</div></div>
  <div class="card"><div class="k">Vantagem sobre o 2º colocado</div>
    <div class="v">{fmt_brl(sig['diff_media'])}/dia</div>
    <div class="d">IC95%: {fmt_brl(sig['ic95'][0])} a {fmt_brl(sig['ic95'][1])}</div></div>
  <div class="card"><div class="k">Significância (pareado por dia)</div>
    <div class="v">{fmt_p(sig['p_valor'])}</div>
    <div class="d">permutação, {sig['n_dias']} dias</div></div>
  <div class="card"><div class="k">Dados aproveitados</div>
    <div class="v">{r['regimes']['dias_validos']} dias</div>
    <div class="d">{r['regimes']['dias_descartados']} dia(s) descartado(s)</div></div>
</div>

<section>
  <h2>Por que essa decisão</h2>
  <ul>{justificativa_html}</ul>
</section>

<section>
  <h2>Comparativo por grupo — janela válida</h2>
  <div class="tres-colunas">
    <div><h3>Margem líquida (R$/dia)</h3>{_svg_barras(m, 'margem_dia', 'brl', 'Margem líquida por dia')}</div>
    <div><h3>Compradores/dia</h3>{_svg_barras(m, 'compradores_dia', 'int', 'Compradores por dia')}</div>
    <div><h3>GMV (R$/dia)</h3>{_svg_barras(m, 'gmv_dia', 'brl', 'GMV por dia')}</div>
  </div>
</section>

<section>
  <h2>% de cashback efetivo por dia</h2>
  <p class="nota">É daqui que a ferramenta reconstrói os tratamentos reais (cashback ÷ GMV). Mudança de linha = alguém mexeu no teste.</p>
  <div class="legenda">{legenda}</div>
  {svg_cb}
</section>

<section>
  <h2>Margem líquida diária (comissão − cashback)</h2>
  <div class="legenda">{legenda}</div>
  {svg_margem}
</section>

<section>
  <h2>Compradores por dia</h2>
  <div class="legenda">{legenda}</div>
  {svg_comp}
</section>

<section>
  <h2>Tabela completa</h2>
  <div class="scroll"><table>
    <thead><tr><th>Grupo</th><th>Cashback</th><th>Take</th><th>Compr./dia</th><th>GMV/dia</th><th>Ticket</th>
    <th>Comissão/dia</th><th>Cashback/dia</th><th>Margem/dia</th><th>Margem %GMV</th><th>Margem/compr.</th></tr></thead>
    <tbody>{linhas_tabela}</tbody>
  </table></div>
</section>

{tabela_regimes}

<section>
  <h2>Alertas e qualidade dos dados</h2>
  <ul class="limpa">{alertas_html}</ul>
</section>

<section>
  <h2>Próximos passos</h2>
  <ul>{proximos_html}</ul>
  <details>
    <summary>Metodologia</summary>
    <p>1. <b>Limpeza:</b> conversão de moeda BR, validação de datas, remoção de duplicatas e nulos — cada problema
    encontrado vira um alerta, nada é descartado em silêncio.</p>
    <p>2. <b>Janela válida:</b> o % efetivo de cashback é reconstruído por grupo/dia (cashback ÷ GMV). A comparação
    usa apenas o trecho contíguo em que cada grupo mantém o % com que o teste começou e as variantes diferem entre si —
    isso protege contra testes alterados no meio e promoções globais.</p>
    <p>3. <b>Decisão:</b> a métrica primária é a margem líquida diária (comissão − cashback). Compradores e GMV são
    guardrails: quando o grupo que mais cresce não é o que mais deixa margem, o relatório calcula quanto custa cada
    comprador incremental e quanto ele devolve de comissão.</p>
    <p>4. <b>Significância:</b> teste de permutação pareado por dia (10 mil permutações de sinal) + IC95% via bootstrap.
    Comparar diferenças diárias entre grupos cancela o efeito do calendário (fins de semana, promoções que atingem todos).</p>
  </details>
</section>

<footer>Gerado automaticamente por <code>analisar.py</code> em {datetime.now():%d/%m/%Y %H:%M} · case técnico Méliuz — João Paulo Motta</footer>
</main>

<div id="tooltip"></div>
<script type="application/json" id="dados-cb">{dados_cb}</script>
<script type="application/json" id="dados-margem">{dados_margem}</script>
<script type="application/json" id="dados-comp">{dados_comp}</script>
<script>
// tooltip compartilhado dos gráficos de linha
(function () {{
  var tt = document.getElementById('tooltip');
  var fmt = {{
    brl: function (v) {{ return 'R$ ' + v.toLocaleString('pt-BR', {{maximumFractionDigits: 0}}); }},
    pct: function (v) {{ return v.toLocaleString('pt-BR', {{maximumFractionDigits: 2}}) + '%'; }},
    int: function (v) {{ return v.toLocaleString('pt-BR', {{maximumFractionDigits: 0}}); }}
  }};
  document.querySelectorAll('svg.grafico').forEach(function (svg) {{
    var dados = JSON.parse(document.getElementById('dados-' + svg.dataset.chart).textContent);
    var grupos = Object.keys(dados.series);
    var guia = svg.querySelector('.guia');
    var pontos = svg.querySelectorAll('.ponto-hover');
    svg.querySelectorAll('.hit').forEach(function (hit) {{
      hit.addEventListener('mousemove', function (ev) {{
        var i = +hit.dataset.i;
        var cx = dados.L + (i / Math.max(dados.n - 1, 1)) * dados.pw;
        guia.style.display = '';
        guia.setAttribute('x1', cx); guia.setAttribute('x2', cx);
        var html = '<div class="t-data">' + dados.datas[i] + '</div>';
        grupos.forEach(function (g, gi) {{
          var v = dados.series[g][i];
          if (v === null) return;
          var cy = dados.T + dados.ph - (v - dados.vmin) / (dados.vmax - dados.vmin) * dados.ph;
          pontos[gi].style.display = '';
          pontos[gi].setAttribute('cx', cx); pontos[gi].setAttribute('cy', cy);
          pontos[gi].setAttribute('fill', 'var(--s' + (gi + 1) + ')');
          html += '<div class="t-linha"><span>' + g + '</span><b>' + fmt[dados.unidade](v) + '</b></div>';
        }});
        tt.innerHTML = html;
        tt.style.display = 'block';
        var tw = tt.offsetWidth;
        tt.style.left = Math.min(ev.clientX + 14, window.innerWidth - tw - 8) + 'px';
        tt.style.top = (ev.clientY + 14) + 'px';
      }});
    }});
    svg.addEventListener('mouseleave', function () {{
      tt.style.display = 'none';
      guia.style.display = 'none';
      pontos.forEach(function (pt) {{ pt.style.display = 'none'; }});
    }});
  }});
}})();
</script>
</body>
</html>"""
    return html


# ------------------------------------------------------------- resumo/salvar

def gerar_resumo(r):
    """Resumo estruturado do teste — vai pro JSON, pra planilha e pro webhook do n8n."""
    m = r["metricas"]
    v = r["veredito"]
    sig = r["significancia"]
    ini, fim = r["regimes"]["janela"]
    d0, d1 = r["periodo_total"]
    vice = m.index[1]

    grupos_desc = ", ".join(f"{g}: {fmt_num(m.loc[g, 'cb_pct'])}%" for g in sorted(m.index))
    resultado = (
        f"{v['vencedor']} venceu em margem líquida ({fmt_brl(m.loc[v['vencedor'], 'margem_dia'])}/dia "
        f"vs {fmt_brl(m.loc[vice, 'margem_dia'])}/dia do {vice}; {fmt_p(sig['p_valor'])})"
    )
    descricao = (
        f"Teste de % de cashback do {r['parceiro']} com {len(m)} variantes ({grupos_desc}), "
        f"{d0:%d/%m/%Y} a {d1:%d/%m/%Y}. Janela válida: {ini:%d/%m/%Y} a {fim:%d/%m/%Y} "
        f"({r['regimes']['dias_validos']} dias)."
    )

    return {
        "nome_teste": r["nome_teste"],
        "parceiro": r["parceiro"],
        "arquivo": r["arquivo"],
        "periodo": f"{d0:%d/%m/%Y} a {d1:%d/%m/%Y}",
        "janela_valida": f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}",
        "dias_validos": int(r["regimes"]["dias_validos"]),
        "grupos": {g: round(float(m.loc[g, "cb_pct"]), 1) for g in sorted(m.index)},
        "metrica_primaria": "margem líquida diária (comissão − cashback)",
        "descricao": descricao,
        "resultado": resultado,
        "decisao": v["decisao"],
        "confianca": v["confianca"],
        "p_valor": None if pd.isna(sig["p_valor"]) else round(float(sig["p_valor"]), 5),
        "alertas": [f"[{a['nivel']}] {a['titulo']}" for a in r["alertas"] if a["nivel"] != "info"],
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
    }


def salvar_relatorios(r, pasta="relatorios"):
    os.makedirs(pasta, exist_ok=True)
    base = slug(r["parceiro"])
    caminhos = {}

    caminhos["md"] = os.path.join(pasta, f"{base}.md")
    with open(caminhos["md"], "w", encoding="utf-8") as f:
        f.write(gerar_markdown(r))

    caminhos["html"] = os.path.join(pasta, f"{base}.html")
    with open(caminhos["html"], "w", encoding="utf-8") as f:
        f.write(gerar_html(r))

    caminhos["json"] = os.path.join(pasta, f"{base}.json")
    with open(caminhos["json"], "w", encoding="utf-8") as f:
        json.dump(gerar_resumo(r), f, ensure_ascii=False, indent=2)

    return caminhos
