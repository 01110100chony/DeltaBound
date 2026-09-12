# Dicionario de dados V0

Valores monetarios sao recebidos em unidades da moeda da empresa e persistidos em centavos inteiros. Taxas usam fracao decimal (`0.03` = 3%). Meses usam `YYYY-MM`.

| Campo | Obrigatorio | Semantica |
|---|---|---|
| `month` | sim | Mes do fluxo. Periodos devem ser unicos e contiguos. |
| `starting_cash` | primeiro mes | Caixa disponivel que inicia a projecao; vazio e diferente de zero. |
| `operating_receipts` | sim | Caixa recebido da operacao, nao receita reconhecida. |
| `personnel` | sim | Saida agregada de pessoal, registrada uma unica vez. |
| `marketing` | sim | Saida de marketing; nao altera receita automaticamente. |
| `other_opex` | sim | Outras saidas operacionais. |
| `capex` | sim | Investimentos pagos no mes. |
| `debt_service` | sim | Juros e amortizacoes pagos; nao e OPEX nem receita. |
| `financing_inflows` | sim | Entrada de capital/divida; nao e recebimento operacional. |
| `mrr` | primeiro mes | MRR de referencia, separado de receita e caixa. |
| `revenue_recognized` | nao | Receita por competencia; nunca movimenta caixa sozinha. |
| `cash_cogs` | nao | Custo de entrega pago, sem dupla contagem em pessoal. |
| `operating_taxes` | nao | Tributos operacionais pagos. |
| `other_net_cash_movements` | nao | Movimento liquido assinado e explicitamente justificado. |
| `net_mrr_growth` | nao | Crescimento liquido; churn nao e subtraido novamente. |
| `origin` | nao | `observed` ou `declared`; padrao `declared`. |

Premissas de cenario sao marcadas como `assumed`; resultados da engine sao `simulated`. Arquivos reais nao pertencem a `data/synthetic`.

