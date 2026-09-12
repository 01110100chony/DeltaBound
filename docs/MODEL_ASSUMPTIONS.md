# Premissas e limitacoes V0

- A engine usa granularidade mensal e valores nominais na moeda da empresa.
- Caixa final segue somente a identidade documentada em `IMPLEMENTACAO_MVP_ANGEL_MARKET.md`.
- MRR, receita reconhecida e recebimentos permanecem independentes.
- Crescimento simples de MRR ja e liquido; churn nao entra novamente.
- Contratacao afeta pessoal; ajuste de OPEX afeta somente a categoria escolhida. Nenhuma acao altera receita sem premissa explicita.
- Viabilidade exige caixa mensal maior ou igual a reserva ate o marco e respeito aos custos protegidos/acoes permitidas.
- Runway estatico usa caixa inicial dividido pela media positiva do burn liquido dos ultimos ate tres periodos fornecidos. Com burn medio nao positivo, e nao aplicavel.
- Cash-out e o primeiro fim de mes com caixa menor ou igual a zero. O sistema nao detecta insuficiencia intrames.
- Caixa negativo representa capital necessario para sustentar o plano, nao continuidade garantida.
- Bissecao so e usada depois de uma verificacao explicita de monotonicidade no intervalo; fatores discretos usam grade declarada.
- Limites de stress nao sao probabilidades nem garantias fora do conjunto testado.

