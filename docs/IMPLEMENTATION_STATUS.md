# Status de implementacao V0

| Milestone | Criterio verificado | Estado |
|---|---|---|
| H0 — dominio/engine | Identidades e casos financeiros independentes em testes | concluido |
| H1 — cenarios | Baseline + alternativas serializaveis; acoes e snapshots imutaveis | concluido |
| H2 — robustez | Reserva/marco, bissecao monotona e grades discretas reproduziveis | concluido |
| H3 — demo local | Sete telas Streamlit percorrem o fluxo sem editar codigo | concluido |
| H4 — historico | SQLite guarda revisoes, inputs, runs, decisoes, acoes e outcomes | concluido |
| H5 — piloto | Template sintetico, onboarding, privacidade, backup, memo e walkthrough | concluido |

O projeto para aqui. React, API online, multi-tenancy, Monte Carlo, ML, inferencia causal e otimizacao permanecem fora do escopo.

## Sanidade sintetica

Para caixa inicial de BRL 300 mil, burn liquido de BRL 25 mil/mes, marco M9 e reserva de BRL 50 mil:

| Alternativa | Caixa M9 | Resultado central |
|---|---:|---|
| Baseline | BRL 75 mil | viavel |
| Contratar por BRL 12 mil/mes desde M1 | BRL -33 mil | inviavel |
| Contratar por BRL 12 mil/mes desde M8 | BRL 51 mil | viavel, margem de BRL 1 mil |

Esses numeros sao identidades condicionais ao plano sintetico, nao previsoes.
