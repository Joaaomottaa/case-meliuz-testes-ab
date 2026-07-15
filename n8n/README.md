# Registro automático no Google Sheets via n8n

O `analisar.py` sempre salva o resultado no CSV local (`planilha/acompanhamento_testes.csv`).
Este workflow é o passo além: ele recebe o resumo da análise por webhook e escreve a linha
direto na planilha compartilhada do Google Sheets — que é o cenário ideal pedido no case.

```
analisar.py ──POST──> Webhook n8n ──> valida payload ──> Google Sheets (append/update)
                                                    └──> (opcional) e-mail avisando o time
```

Escolhi centralizar a escrita no n8n em vez de usar a API do Google direto no script por três motivos:

1. **Credencial num lugar só.** Quem roda a análise não precisa de service account na máquina —
   a credencial do Google fica guardada no n8n.
2. **Idempotência.** O node usa *append or update* casando pela coluna `nome_teste`: rodar a mesma
   análise duas vezes atualiza a linha em vez de duplicar.
3. **Gancho de automação.** O mesmo webhook já serve pra avisar o time (e-mail/Slack) quando um
   teste é registrado — deixei um node de e-mail pronto, desativado.

## Como configurar (uma vez só)

1. No n8n (cloud ou self-hosted): **Workflows → Import from File** → `registro_testes_ab_sheets.json`.
2. Crie/abra sua planilha no Google Sheets com uma aba chamada `acompanhamento`.
   A primeira linha precisa ter os mesmos cabeçalhos do CSV — o jeito rápido é importar o
   `planilha/acompanhamento_testes.csv` deste repositório (Arquivo → Importar), que já cria tudo.
3. No node **Google Sheets (append/update)**: conecte sua credencial Google e cole o ID da
   planilha (o trecho entre `/d/` e `/edit` na URL).
4. Ative o workflow e copie a **URL de produção** do webhook.
5. Na raiz do projeto, crie um `.env` com:

   ```
   N8N_WEBHOOK_URL=https://SEU-N8N/webhook/registrar-teste-ab
   ```

Pronto — a partir daí todo `python analisar.py <arquivo>` registra no Sheets automaticamente.

## Teste rápido sem rodar a análise

```bash
curl -X POST "https://SEU-N8N/webhook/registrar-teste-ab" \
  -H "Content-Type: application/json" \
  -d '{"nome_teste":"Teste manual","parceiro":"Parceiro X","descricao":"teste do webhook","resultado":"ok","decisao":"nenhuma","grupos":{"Grupo 1":3}}'
```

Se aparecer `{"ok":true,...}` e a linha na planilha, está tudo ligado.

**Nota:** em produção eu colocaria autenticação no webhook (header auth do próprio n8n) —
não deixei ativo aqui pra facilitar a avaliação do case.
