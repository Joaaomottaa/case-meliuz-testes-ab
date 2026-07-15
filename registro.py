# -*- coding: utf-8 -*-
"""
Registro do teste na planilha de acompanhamento.

Dois caminhos, nessa ordem:
  1. CSV local (planilha/acompanhamento_testes.csv) — sempre. É a fonte de verdade
     e o formato mínimo pedido no case.
  2. Google Sheets via webhook do n8n — se N8N_WEBHOOK_URL estiver configurada
     (variável de ambiente ou arquivo .env). O workflow está em n8n/ e faz o
     append/update na planilha compartilhada.

Por que Sheets via n8n e não direto por API? A credencial do Google fica num
lugar só (o n8n), quem roda a análise não precisa de service account na máquina,
e o mesmo webhook já serve de gancho pra avisar o time (e-mail/Slack) quando
um teste é registrado. É o mesmo padrão que uso no trabalho.
"""

import csv
import os

import requests

COLUNAS = [
    "registrado_em", "nome_teste", "parceiro", "periodo", "janela_valida",
    "dias_validos", "grupos_cashback", "descricao", "metrica_primaria",
    "resultado", "decisao", "confianca", "p_valor", "alertas", "relatorio",
]


def _linha_da_planilha(resumo, caminho_relatorio):
    return {
        "registrado_em": resumo["gerado_em"],
        "nome_teste": resumo["nome_teste"],
        "parceiro": resumo["parceiro"],
        "periodo": resumo["periodo"],
        "janela_valida": resumo["janela_valida"],
        "dias_validos": resumo["dias_validos"],
        "grupos_cashback": "; ".join(f"{g}: {v:g}%".replace(".", ",") for g, v in resumo["grupos"].items()),
        "descricao": resumo["descricao"],
        "metrica_primaria": resumo["metrica_primaria"],
        "resultado": resumo["resultado"],
        "decisao": resumo["decisao"],
        "confianca": resumo["confianca"],
        "p_valor": "<0,001" if (resumo["p_valor"] is not None and resumo["p_valor"] < 0.001) else resumo["p_valor"],
        "alertas": "; ".join(resumo["alertas"]) or "nenhum",
        "relatorio": caminho_relatorio.replace("\\", "/"),
    }


def registrar_csv(resumo, caminho_relatorio, caminho_csv="planilha/acompanhamento_testes.csv"):
    """Insere (ou atualiza, se o teste já existe) a linha do teste no CSV."""
    os.makedirs(os.path.dirname(caminho_csv), exist_ok=True)
    linhas = []
    if os.path.exists(caminho_csv):
        with open(caminho_csv, encoding="utf-8-sig", newline="") as f:
            linhas = [l for l in csv.DictReader(f)]

    nova = _linha_da_planilha(resumo, caminho_relatorio)
    linhas = [l for l in linhas if l.get("nome_teste") != nova["nome_teste"]]
    linhas.append(nova)
    linhas.sort(key=lambda l: l.get("registrado_em", ""))

    # utf-8 com BOM pro Excel/Sheets abrirem com acento certo
    with open(caminho_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    return caminho_csv


def _carregar_env():
    """Lê variáveis de um .env simples na raiz do projeto, se existir."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(caminho):
        return
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                chave, valor = linha.split("=", 1)
                os.environ.setdefault(chave.strip(), valor.strip())


def registrar_sheets(resumo, caminho_relatorio):
    """
    Envia o resumo pro webhook do n8n, que registra na planilha do Google Sheets.
    Devolve uma mensagem de status pro console — falha aqui não derruba a análise,
    porque o CSV local já foi salvo.
    """
    _carregar_env()
    url = os.environ.get("N8N_WEBHOOK_URL", "").strip()
    if not url:
        return "não configurado (defina N8N_WEBHOOK_URL no .env pra registrar direto no Sheets)"

    payload = dict(resumo)
    payload["relatorio"] = caminho_relatorio.replace("\\", "/")
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.ok:
            return f"registrado no Google Sheets via n8n (HTTP {resp.status_code})"
        return f"webhook respondeu HTTP {resp.status_code} — confira o workflow no n8n (o CSV local está salvo)"
    except requests.RequestException as e:
        return f"não consegui falar com o n8n ({e.__class__.__name__}) — o CSV local está salvo"
