# -*- coding: utf-8 -*-
"""
Motor de análise de testes A/B de cashback.

A lógica está separada em etapas pra ficar fácil de auditar:
  1. carregar()          -> lê o CSV e limpa (moeda BR, datas, duplicatas, nulos)
  2. detectar_regimes()  -> descobre o % de cashback praticado por grupo ao longo
                            do tempo e delimita a janela válida do teste
  3. calcular_metricas() -> KPIs por grupo dentro da janela válida
  4. teste_pareado()     -> significância da diferença (permutação pareada por dia)
  5. gerar_alertas()     -> checagens de sanidade sobre o desenho do teste
  6. decidir()           -> aplica as regras de decisão e monta a recomendação

Nenhuma etapa tem nada específico de um dataset: tudo é inferido dos dados.
"""

import os
import re
import unicodedata

import numpy as np
import pandas as pd

# tolerâncias usadas na detecção de regimes (em pontos percentuais de cashback)
TOL_REGIME = 0.6      # quanto o cb% diário pode oscilar sem contar como mudança
MIN_DIST_GRUPOS = 1.0 # distância mínima entre grupos pra considerar variantes distintas
DIAS_REF = 7          # dias iniciais usados pra estimar o % de referência de cada grupo
N_PERMUTACOES = 10000
SEMENTE = 42

# nomes canônicos das colunas -> variações aceitas (comparação sem acento/caixa)
MAPA_COLUNAS = {
    "data": ["data", "date", "dia"],
    "grupo": ["grupos de usuarios", "grupo de usuarios", "grupo", "variante"],
    "parceiro": ["parceiro", "partner", "loja"],
    "compradores": ["compradores", "buyers", "usuarios compradores"],
    "comissao": ["comissao", "comissão", "commission", "receita"],
    "cashback": ["cashback", "cash back"],
    "gmv": ["vendas totais", "gmv", "vendas", "valor total"],
}


def _normaliza(texto):
    """minúsculo e sem acento, pra comparar nomes de coluna."""
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return s.strip().lower()


def fmt_brl(v, centavos=False):
    """1234567.8 -> 'R$ 1.234.568' (padrão brasileiro)."""
    if pd.isna(v):
        return "—"
    s = f"{v:,.2f}" if centavos else f"{v:,.0f}"
    return "R$ " + s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_num(v, dec=1):
    """Número com vírgula decimal e ponto de milhar."""
    if pd.isna(v):
        return "—"
    return f"{v:,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_p(p):
    """p-valor legível: p<0,001 quando a permutação não acha nada mais extremo."""
    if pd.isna(p):
        return "p indisponível"
    if p < 0.001:
        return "p<0,001"
    return f"p={p:.3f}".replace(".", ",")


def parse_moeda(valor):
    """Converte 'R$ 1.234,56' / 'R$ 10.273' / '1234.56' em float. NaN se ilegível."""
    if pd.isna(valor):
        return np.nan
    s = str(valor).strip()
    if s == "":
        return np.nan
    negativo = s.startswith("-") or s.startswith("(")
    s = re.sub(r"[Rr]\$", "", s).replace("(", "").replace(")", "").replace(" ", "").lstrip("-")
    if "," in s:
        # formato brasileiro: ponto de milhar, vírgula decimal
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        # só pontos de milhar (caso dos datasets: "10.273")
        s = s.replace(".", "")
    try:
        v = float(s)
    except ValueError:
        return np.nan
    return -v if negativo else v


def carregar(caminho):
    """Lê o CSV, normaliza colunas/tipos e devolve (df, log de qualidade)."""
    bruto = pd.read_csv(caminho, dtype=str)
    log = {"linhas_lidas": len(bruto), "problemas": []}

    # mapeia as colunas do arquivo pros nomes canônicos
    colunas = {}
    for canonico, aliases in MAPA_COLUNAS.items():
        for c in bruto.columns:
            if _normaliza(c) in aliases:
                colunas[c] = canonico
                break
    faltando = set(MAPA_COLUNAS) - set(colunas.values())
    if faltando:
        raise ValueError(f"Colunas obrigatórias não encontradas no CSV: {sorted(faltando)}")

    df = bruto.rename(columns=colunas)[list(MAPA_COLUNAS)]

    # tipos
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["grupo"] = df["grupo"].astype(str).str.strip().str.title()  # "grupo 1" -> "Grupo 1"
    df["parceiro"] = df["parceiro"].astype(str).str.strip()
    df["compradores"] = pd.to_numeric(df["compradores"], errors="coerce")
    for col in ["comissao", "cashback", "gmv"]:
        df[col] = df[col].map(parse_moeda)

    # linhas com problema estrutural saem da análise, mas ficam registradas
    invalidas = df["data"].isna()
    if invalidas.any():
        log["problemas"].append(f"{invalidas.sum()} linha(s) com data inválida (descartadas)")
    nulos = df[["compradores", "comissao", "cashback", "gmv"]].isna().any(axis=1) & ~invalidas
    if nulos.any():
        log["problemas"].append(f"{nulos.sum()} linha(s) com valor nulo/ilegível (descartadas)")
    df = df[~invalidas & ~nulos].copy()

    negativos = (df[["compradores", "comissao", "cashback", "gmv"]] < 0).any(axis=1)
    if negativos.any():
        log["problemas"].append(
            f"{negativos.sum()} linha(s) com valor negativo (mantidas — possível estorno, conferir na origem)"
        )

    dup_exata = df.duplicated()
    if dup_exata.any():
        log["problemas"].append(f"{dup_exata.sum()} linha(s) duplicadas idênticas (removidas)")
        df = df[~dup_exata]

    dup_chave = df.duplicated(subset=["data", "grupo"])
    if dup_chave.any():
        log["problemas"].append(
            f"{dup_chave.sum()} data(s) repetidas pro mesmo grupo com valores diferentes (mantive a primeira)"
        )
        df = df[~dup_chave]

    df = df.sort_values(["grupo", "data"]).reset_index(drop=True)

    # métricas derivadas por linha
    df["margem"] = df["comissao"] - df["cashback"]
    df["cb_pct"] = np.where(df["gmv"] > 0, df["cashback"] / df["gmv"] * 100, np.nan)
    df["take_pct"] = np.where(df["gmv"] > 0, df["comissao"] / df["gmv"] * 100, np.nan)
    df["ticket"] = np.where(df["compradores"] > 0, df["gmv"] / df["compradores"], np.nan)

    log["linhas_validas"] = len(df)
    log["grupos"] = sorted(df["grupo"].unique())
    if len(log["grupos"]) < 2:
        raise ValueError("O arquivo tem menos de 2 grupos — não há teste A/B pra analisar.")

    # cobertura de datas por grupo (buracos no meio do período)
    for grupo, sub in df.groupby("grupo"):
        faixa = pd.date_range(sub["data"].min(), sub["data"].max())
        buracos = len(faixa) - sub["data"].nunique()
        if buracos:
            log["problemas"].append(f"{grupo}: {buracos} dia(s) sem registro dentro do período")

    return df, log


def detectar_regimes(df):
    """
    Reconstrói o % de cashback praticado por grupo ao longo do tempo e delimita
    a janela válida: o trecho contíguo, desde o início, em que cada grupo mantém
    o % original e os grupos são de fato diferentes entre si.

    Isso protege a análise de dois problemas comuns: alguém mexer nos % no meio
    do teste, e promoções globais que alteram todos os grupos ao mesmo tempo.
    """
    pivo = df.pivot_table(index="data", columns="grupo", values="cb_pct")
    grupos = list(pivo.columns)

    # % de referência de cada grupo = mediana dos primeiros dias do teste
    referencia = pivo.head(DIAS_REF).median().round(2)

    dentro = (pivo - referencia).abs() <= TOL_REGIME
    dia_ok = dentro.all(axis=1)

    # janela válida: do primeiro dia até a véspera da primeira quebra sustentada
    # (2+ dias seguidos fora do regime; blip de 1 dia só gera aviso)
    fora_seguidos = 0
    fim_janela = pivo.index[-1]
    blips = []
    for dia, ok in dia_ok.items():
        if ok:
            fora_seguidos = 0
        else:
            fora_seguidos += 1
            if fora_seguidos == 1:
                candidato = dia
            if fora_seguidos >= 2:
                fim_janela = candidato - pd.Timedelta(days=1)
                break
            blips.append(dia)
    else:
        if fora_seguidos == 1:  # blip solto no último dia
            fim_janela = pivo.index[-1] - pd.Timedelta(days=1)

    inicio_janela = pivo.index[0]
    janela = (inicio_janela, fim_janela)

    distintos = (referencia.max() - referencia.min()) >= MIN_DIST_GRUPOS

    # tabela de regimes pro relatório: trechos em que o cb% mediano fica estável
    mudancas = pivo.round(1)
    marcos = [pivo.index[0]]
    anterior = mudancas.iloc[0]
    for dia, linha in mudancas.iloc[1:].iterrows():
        if ((linha - anterior).abs() > TOL_REGIME).any():
            marcos.append(dia)
        anterior = linha
    marcos.append(pivo.index[-1] + pd.Timedelta(days=1))
    trechos = []
    for ini, fim in zip(marcos, marcos[1:]):
        fatia = pivo.loc[ini : fim - pd.Timedelta(days=1)]
        if len(fatia) == 0:
            continue
        trechos.append({
            "inicio": ini,
            "fim": fim - pd.Timedelta(days=1),
            "dias": len(fatia),
            "cb_por_grupo": fatia.median().round(1).to_dict(),
        })
    # junta trechos consecutivos iguais (transições de 1-2 dias geram fatias soltas)
    consolidados = []
    for t in trechos:
        if consolidados and consolidados[-1]["cb_por_grupo"] == t["cb_por_grupo"]:
            consolidados[-1]["fim"] = t["fim"]
            consolidados[-1]["dias"] += t["dias"]
        else:
            consolidados.append(t)

    return {
        "referencia": referencia.to_dict(),
        "janela": janela,
        "dias_totais": len(pivo),
        "dias_validos": int(dia_ok.loc[inicio_janela:fim_janela].sum()),
        "dias_descartados": int(len(pivo) - len(pivo.loc[inicio_janela:fim_janela])),
        "grupos_distintos": bool(distintos),
        "blips": blips,
        "trechos": consolidados,
    }


def calcular_metricas(df_janela):
    """KPIs por grupo, calculados só dentro da janela válida."""
    m = df_janela.groupby("grupo").agg(
        dias=("data", "nunique"),
        compradores_dia=("compradores", "mean"),
        gmv_dia=("gmv", "mean"),
        comissao_dia=("comissao", "mean"),
        cashback_dia=("cashback", "mean"),
        margem_dia=("margem", "mean"),
        compradores_total=("compradores", "sum"),
        gmv_total=("gmv", "sum"),
        margem_total=("margem", "sum"),
        cb_pct=("cb_pct", "median"),
        take_pct=("take_pct", "median"),
        ticket=("ticket", "median"),
    )
    m["margem_pct_gmv"] = m["margem_total"] / m["gmv_total"] * 100
    m["margem_por_comprador"] = m["margem_total"] / m["compradores_total"]

    # lifts contra o grupo de menor cashback (proxy de controle — hipótese documentada)
    base = m["cb_pct"].idxmin()
    for col in ["compradores_dia", "gmv_dia", "margem_dia"]:
        m[f"lift_{col}"] = (m[col] / m.loc[base, col] - 1) * 100
    m = m.sort_values("margem_dia", ascending=False)
    m.attrs["baseline"] = base
    return m


def teste_pareado(df_janela, grupo_a, grupo_b, metrica="margem"):
    """
    Teste de permutação pareado por dia (sign-flip) entre dois grupos.

    Os grupos vivem o mesmo calendário (promoções, fim de semana, sazonalidade),
    então comparo a DIFERENÇA diária entre eles — isso cancela o efeito do
    calendário e sobra o efeito da variante. Sob H0 (nenhuma diferença real),
    o sinal de cada diferença diária é aleatório; embaralhando os sinais 10 mil
    vezes dá pra ver o quão extrema é a diferença observada.
    """
    pivo = df_janela.pivot_table(index="data", columns="grupo", values=metrica)
    d = (pivo[grupo_a] - pivo[grupo_b]).dropna().to_numpy()
    if len(d) < 8:
        return {"n_dias": len(d), "p_valor": np.nan, "diff_media": float(np.mean(d)) if len(d) else np.nan,
                "ic95": (np.nan, np.nan), "obs": "poucos dias pareados pra testar"}

    rng = np.random.default_rng(SEMENTE)
    obs = d.mean()
    sinais = rng.choice([-1, 1], size=(N_PERMUTACOES, len(d)))
    medias_perm = (sinais * d).mean(axis=1)
    p = float((np.abs(medias_perm) >= abs(obs)).mean())

    # IC 95% da diferença média via bootstrap
    idx = rng.integers(0, len(d), size=(N_PERMUTACOES, len(d)))
    medias_boot = d[idx].mean(axis=1)
    ic = (float(np.percentile(medias_boot, 2.5)), float(np.percentile(medias_boot, 97.5)))

    return {"n_dias": len(d), "p_valor": p, "diff_media": float(obs), "ic95": ic, "obs": ""}


def gerar_alertas(df, df_janela, metricas, regimes, log):
    """Checagens de sanidade sobre o desenho e a saúde do teste."""
    alertas = []
    grupos = list(metricas.index)

    # problemas estruturais vindos da carga
    for p in log["problemas"]:
        alertas.append({"nivel": "atencao", "titulo": "Qualidade dos dados", "texto": p})

    # teste alterado no meio do caminho
    if regimes["dias_descartados"] > 0:
        ini, fim = regimes["janela"]
        alertas.append({
            "nivel": "critico",
            "titulo": "Tratamentos alterados durante o teste",
            "texto": (
                f"Os % de cashback dos grupos mudaram ao longo do período. A comparação usa apenas "
                f"a janela em que as variantes originais ficaram estáveis "
                f"({ini:%d/%m/%Y} a {fim:%d/%m/%Y}); {regimes['dias_descartados']} dia(s) posteriores foram excluídos. "
                f"Vale investigar com o time por que o teste foi mexido antes de encerrar."
            ),
        })

    if not regimes["grupos_distintos"]:
        alertas.append({
            "nivel": "critico",
            "titulo": "Variantes praticamente iguais",
            "texto": "A diferença de cashback entre os grupos é menor que 1 p.p. — o teste não separa as variantes.",
        })

    if regimes["dias_validos"] < 14:
        alertas.append({
            "nivel": "atencao",
            "titulo": "Janela curta",
            "texto": f"Só {regimes['dias_validos']} dias válidos — pouco pra capturar sazonalidade semanal. Tratar como direcional.",
        })

    # volumes muito desiguais entre grupos (sem dado de exposição não dá pra saber o split real)
    shares = metricas["compradores_total"] / metricas["compradores_total"].sum()
    esperado = 1 / len(grupos)
    desvio = (shares / esperado - 1).abs().max()
    if desvio > 0.20:
        alertas.append({
            "nivel": "atencao",
            "titulo": "Volumes desiguais entre grupos",
            "texto": (
                f"Se o split fosse igualitário ({100 / len(grupos):.0f}% cada), os volumes de compradores "
                f"não deviam fugir tanto do esperado: {', '.join(f'{g} = {s * 100:.0f}%' for g, s in shares.items())}. "
                f"O dataset não tem nº de usuários expostos, então não dá pra confirmar o split real. "
                f"Comparações absolutas (total de compradores/GMV) ficam comprometidas — as métricas por "
                f"comprador e por R$ de GMV seguem válidas."
            ),
        })

    # relação economicamente implausível: mais cashback deveria puxar mais compradores
    cb = metricas["cb_pct"]
    comp = metricas["compradores_dia"]
    if len(grupos) >= 3:
        correl = cb.rank().corr(comp.rank(), method="spearman")
        if pd.notna(correl) and correl < 0:
            alertas.append({
                "nivel": "atencao",
                "titulo": "Relação cashback × compradores invertida",
                "texto": (
                    "Os grupos com MAIS cashback têm MENOS compradores, o que não faz sentido econômico "
                    "num split aleatório. Reforça a suspeita de alocação desigual ou públicos não comparáveis. "
                    "Recomendo validar a instrumentação do teste antes de rodar outro com esse parceiro."
                ),
            })

    # variante que devolve toda a comissão
    for g in grupos:
        if metricas.loc[g, "margem_dia"] <= 1:
            alertas.append({
                "nivel": "critico",
                "titulo": f"{g} com margem zero ou negativa",
                "texto": (
                    f"{g} repassa {metricas.loc[g, 'cb_pct']:.0f}% de cashback com take de "
                    f"{metricas.loc[g, 'take_pct']:.0f}% — ou seja, devolve ~100% da comissão. "
                    f"Cada venda incremental dessa variante não deixa nada de resultado."
                ),
            })

    # queda abrupta no fim do período (tracking quebrado, oferta fora do ar etc.)
    ultimos = df["data"].max() - pd.Timedelta(days=4)
    for g in grupos:
        serie = df[df["grupo"] == g]
        fim = serie[serie["data"] >= ultimos]["compradores"].mean()
        antes = serie[serie["data"] < ultimos]["compradores"].median()
        if antes and fim / antes < 0.60:
            outros = [o for o in grupos if o != g]
            estaveis = []
            for o in outros:
                so = df[df["grupo"] == o]
                fo = so[so["data"] >= ultimos]["compradores"].mean()
                ao = so[so["data"] < ultimos]["compradores"].median()
                if ao and fo / ao >= 0.80:
                    estaveis.append(o)
            if estaveis:
                alertas.append({
                    "nivel": "atencao",
                    "titulo": f"Queda abrupta no fim do período ({g})",
                    "texto": (
                        f"Nos últimos 5 dias, {g} caiu pra {fim / antes * 100:.0f}% do volume típico "
                        f"enquanto {' e '.join(estaveis)} seguiu estável — cheira a problema de tracking "
                        f"ou oferta fora do ar, não a comportamento de usuário. Conferir com o parceiro."
                    ),
                })

    # picos coincidentes entre grupos (promoção/sazonalidade que afeta todo mundo)
    pivo = df_janela.pivot_table(index="data", columns="grupo", values="compradores")
    zmods = {}
    for g in grupos:
        s = pivo[g].dropna()
        mad = (s - s.median()).abs().median()
        zmods[g] = 0.6745 * (s - s.median()) / mad if mad else s * 0
    z = pd.DataFrame(zmods)
    picos = z[(z > 3.5).sum(axis=1) >= max(2, len(grupos) // 2 + 1)].index
    if len(picos):
        dias_str = ", ".join(d.strftime("%d/%m") for d in picos[:6])
        alertas.append({
            "nivel": "info",
            "titulo": "Picos de demanda coincidentes",
            "texto": (
                f"Dias com volume muito acima do normal em todos os grupos ao mesmo tempo ({dias_str}) — "
                f"provável promoção ou data sazonal. Como afetam as variantes por igual, mantive na análise."
            ),
        })

    if not log["problemas"]:
        alertas.append({
            "nivel": "info",
            "titulo": "Estrutura dos dados ok",
            "texto": "Sem duplicatas, nulos, datas faltantes ou valores ilegíveis após a limpeza.",
        })

    return alertas


def decidir(metricas, regimes, alertas, sig):
    """
    Regras de decisão (nessa ordem):
      1. A métrica que manda é margem líquida/dia (comissão - cashback): é o que
         sobra pro Méliuz. GMV e compradores entram como guardrail de crescimento.
      2. O vencedor precisa de diferença estatisticamente significativa vs o vice
         (permutação pareada por dia). Sem significância -> continuar o teste,
         a não ser que o vencedor domine em tudo.
      3. Alertas críticos derrubam a confiança e entram na justificativa.
    """
    vencedor = metricas.index[0]
    vice = metricas.index[1]
    baseline = metricas.attrs["baseline"]
    justificativa = []
    proximos = []

    v = metricas.loc[vencedor]
    margem_vice = metricas["margem_dia"].iloc[1]
    if margem_vice > 1:
        comparacao = f"{(v['margem_dia'] / margem_vice - 1) * 100:+.0f}% vs {vice}"
    else:
        comparacao = f"enquanto {vice} zera o resultado"
    justificativa.append(
        f"{vencedor} ({fmt_num(v['cb_pct'])}% de cashback) entrega a maior margem líquida: "
        f"{fmt_brl(v['margem_dia'])}/dia ({fmt_num(v['margem_pct_gmv'])}% do GMV), {comparacao}."
    )

    significativo = not np.isnan(sig["p_valor"]) and sig["p_valor"] < 0.05
    if significativo:
        justificativa.append(
            f"Diferença consistente dia a dia: {fmt_p(sig['p_valor'])} no teste de permutação pareado "
            f"({sig['n_dias']} dias), IC95% da diferença diária: {fmt_brl(sig['ic95'][0])} a {fmt_brl(sig['ic95'][1])}."
        )
    else:
        justificativa.append(
            f"A diferença vs {vice} NÃO é estatisticamente significativa ({fmt_p(sig['p_valor'])}) — "
            f"os dados não bastam pra cravar vencedor só pela margem."
        )

    # guardrail de crescimento: quem mais traz comprador, e a que custo
    mais_crescimento = metricas["compradores_dia"].idxmax()
    if mais_crescimento != vencedor:
        c = metricas.loc[mais_crescimento]
        d_comp = c["compradores_dia"] - v["compradores_dia"]
        d_cb = c["cashback_dia"] - v["cashback_dia"]
        d_com = c["comissao_dia"] - v["comissao_dia"]
        if d_comp > 0:
            custo = d_cb / d_comp
            retorno = d_com / d_comp
            justificativa.append(
                f"Trade-off de crescimento: {mais_crescimento} traz {d_comp:+.0f} compradores/dia "
                f"({c['lift_compradores_dia'] - v['lift_compradores_dia']:+.0f}p.p.), mas cada comprador "
                f"incremental custa {fmt_brl(custo)} de cashback e devolve {fmt_brl(retorno)} de comissão — "
                f"{'se paga' if retorno > custo else 'não se paga sem considerar recompra/LTV'}."
            )
            if retorno <= custo:
                proximos.append(
                    f"Se a estratégia com esse parceiro for base ativa (e não margem), medir retenção/recompra "
                    f"dos compradores de {mais_crescimento} antes de descartar a variante."
                )

    criticos = [a for a in alertas if a["nivel"] == "critico" and "margem zero" not in a["titulo"].lower()]
    atencoes = [a for a in alertas if a["nivel"] == "atencao"]

    # decisão final
    domina_tudo = all(
        metricas.loc[vencedor, col] >= metricas[col].max() * 0.999
        for col in ["margem_dia", "compradores_dia", "gmv_dia"]
    )
    if significativo or domina_tudo:
        decisao = f"ESCALAR {vencedor} ({fmt_num(v['cb_pct'])}% de cashback) para 100% do tráfego"
        confianca = "alta"
        if criticos or len(atencoes) >= 2:
            confianca = "média"
    else:
        decisao = f"MANTER {vencedor} ({fmt_num(v['cb_pct'])}%) e ESTENDER o teste por mais 4 semanas"
        confianca = "baixa"
        proximos.append("Reavaliar com mais dados antes de qualquer rollout definitivo.")

    if vencedor == baseline:
        justificativa.append(
            f"{vencedor} é o grupo de menor cashback (tratei como controle provável): a recomendação "
            f"na prática é não aumentar o benefício desse parceiro."
        )

    # próximos passos padrão conforme os alertas
    for a in alertas:
        if a["titulo"].startswith("Tratamentos alterados"):
            proximos.append("Alinhar governança de testes: variante não pode mudar no meio do experimento.")
        if a["titulo"].startswith("Volumes desiguais"):
            proximos.append("Registrar usuários EXPOSTOS por grupo nos próximos testes (permite validar o split e calcular conversão).")
        if "margem zero" in a["titulo"].lower():
            proximos.append("Antes de testar cashback mais alto nesse parceiro, renegociar a comissão — no take atual não existe margem pra repassar.")
        if a["titulo"].startswith("Queda abrupta"):
            proximos.append("Checar com o parceiro/tracking o que houve nos últimos dias do teste.")

    return {
        "decisao": decisao,
        "vencedor": vencedor,
        "confianca": confianca,
        "justificativa": justificativa,
        "proximos_passos": proximos,
    }


def analisar_arquivo(caminho):
    """Roda o pipeline completo e devolve um dicionário com tudo que os relatórios usam."""
    df, log = carregar(caminho)
    regimes = detectar_regimes(df)

    ini, fim = regimes["janela"]
    df_janela = df[(df["data"] >= ini) & (df["data"] <= fim)].copy()
    metricas = calcular_metricas(df_janela)

    sig = teste_pareado(df_janela, metricas.index[0], metricas.index[1], "margem")
    alertas = gerar_alertas(df, df_janela, metricas, regimes, log)
    veredito = decidir(metricas, regimes, alertas, sig)

    parceiro = df["parceiro"].mode()[0]
    d0, d1 = df["data"].min(), df["data"].max()
    if d0.year == d1.year:
        periodo_str = f"{d0:%m}–{d1:%m}/{d1:%Y}"
    else:
        periodo_str = f"{d0:%m/%Y}–{d1:%m/%Y}"
    nome_teste = f"Cashback {parceiro} ({periodo_str})"

    return {
        "arquivo": os.path.basename(caminho),
        "parceiro": parceiro,
        "nome_teste": nome_teste,
        "periodo_total": (df["data"].min(), df["data"].max()),
        "df": df,
        "df_janela": df_janela,
        "log": log,
        "regimes": regimes,
        "metricas": metricas,
        "significancia": sig,
        "alertas": alertas,
        "veredito": veredito,
    }
