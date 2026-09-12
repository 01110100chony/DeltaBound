# Angel Market — Plano de Implementação Coerente com o MVP

Versão: 1.0  
Status: **escopo de implementação proposto**  
Baseado em: `ESCOPO.md` v0.4 + decisões discutidas sobre o produto.

---

# 1. Objetivo do projeto

Construir uma plataforma de **Decision Intelligence quantitativa para startups early-stage e instituições que acompanham portfólios**, começando por uma capacidade simples, auditável e útil:

> **Avaliar se uma decisão financeira ou operacional é viável até determinado marco, sob diferentes premissas e condições adversas.**

O produto inicial NÃO deve tentar prever qual startup terá sucesso, nem recomendar decisões com alegações causais.

O MVP deve responder perguntas como:

- Podemos contratar agora sem comprometer o caixa?
- Até qual mês essa contratação pode ser adiada?
- Quanto podemos aumentar determinada despesa preservando uma reserva mínima?
- Quanto de deterioração em receita ou recebimentos o plano suporta?
- Qual cenário é mais robusto?
- Em que condição o plano deixa de ser viável?
- Quais premissas precisam ser confirmadas antes de assumir determinado compromisso?

A evolução desejada é:

```text
Financial Modeling
    ↓
Scenario Analysis
    ↓
Robust Decision Support
    ↓
Probabilistic Simulation
    ↓
Predictive Models
    ↓
Causal Inference
    ↓
Decision Optimization
```

O MVP deve implementar somente as três primeiras etapas.

---

# 2. Tese central do MVP

O diferencial inicial deve ser:

> **Limites de decisão + planejamento robusto até um marco.**

Não vender:

> “Prevemos o crescimento da sua startup.”

Vender:

> “Mostramos se uma decisão cabe no plano atual, quais condições precisam continuar verdadeiras e em qual ponto o plano deixa de ser financeiramente sustentável.”

Exemplo:

```text
Decisão:
Contratar 2 pessoas no mês 4.

Objetivo:
Chegar ao mês 12 mantendo pelo menos R$ 80 mil de caixa.

Resultado:
- Cenário central: viável.
- Com atraso de 1 mês nos recebimentos: viável.
- Com queda de 12% nos recebimentos: reserva violada no mês 10.
- Limite estimado antes da violação: -8,7% de recebimentos acumulados.
```

O produto deve expor:

- estado atual;
- ação simulada;
- hipóteses;
- restrições;
- resultado;
- limite de falha;
- limitações da análise.

---

# 3. ICP inicial

## Usuário

Founder, CEO, CFO ou responsável financeiro de startup SaaS B2B early-stage.

## Comprador prioritário

- incubadora;
- aceleradora;
- micro-VC;
- programa de acompanhamento;
- CVC pequeno;
- instituição com portfólio de startups.

Hipótese central:

```text
Startup = usuária + fonte permissionada de dados
Instituição = compradora / canal de distribuição
```

O primeiro piloto deve priorizar **3–5 startups SaaS B2B com receita recorrente**.

Evitar misturar empresas pré-receita, indústria, biotech, marketplaces e modelos muito distintos no primeiro experimento.

---

# 4. Princípios obrigatórios de implementação

1. **Engine financeira independente da interface.**
2. **Toda premissa deve ser explícita.**
3. **Observado, declarado, assumido e simulado devem ser diferentes.**
4. **MRR, receita e recebimento não podem ser tratados como equivalentes.**
5. **O sistema não deve inventar causalidade.**
6. **Toda execução deve ser reproduzível.**
7. **Cenários antigos não devem mudar quando os dados forem corrigidos posteriormente.**
8. **Dados ausentes são diferentes de zero.**
9. **Nenhum score opaco no MVP.**
10. **Não construir arquitetura enterprise antes do piloto.**
11. **Não usar LLM no núcleo quantitativo.**
12. **O produto deve gerar valor com poucos dados.**

---

# 5. Escopo congelado — V0

## 5.1 Inputs mínimos

Por empresa:

### Estado financeiro

- moeda;
- mês base;
- caixa inicial disponível;
- recebimentos operacionais;
- pagamentos operacionais;
- pessoal;
- marketing;
- outros OPEX;
- capex;
- serviço de dívida;
- financiamento;
- outros movimentos de caixa.

### SaaS

- MRR atual;
- hipótese de crescimento líquido de MRR;
- opcionalmente receita reconhecida.

### Planejamento

- reserva mínima desejada;
- horizonte de análise;
- marco-alvo;
- despesas comprometidas;
- contratações planejadas.

---

## 5.2 Ações suportadas

V0 deve permitir somente:

### Hiring

- quantidade;
- mês de início;
- custo mensal por pessoa ou total;
- custo inicial opcional.

### Delay Hiring

- alteração da data de início da contratação.

### OPEX Adjustment

- aumento/redução de marketing;
- aumento/redução de outros custos;
- alteração pontual ou recorrente.

### Revenue / Receipts Assumption

- alteração explícita da hipótese de crescimento;
- atraso em recebimentos;
- choque negativo ou positivo definido pelo usuário.

Não implementar automaticamente relação entre:

```text
marketing → revenue
headcount → growth
cost cut → churn
```

Esses efeitos só entram como premissas explícitas.

---

# 6. Engine financeira determinística

Para cada mês `t`:

```text
cash_t =
    cash_(t-1)
    + operating_receipts_t
    - operating_payments_t
    - capex_t
    - debt_service_t
    + financing_inflows_t
    + other_net_cash_movements_t
```

Com:

```text
operating_payments_t =
    personnel_t
    + marketing_t
    + other_operating_t
    + cash_cogs_t
    + operating_taxes_t
```

Burn:

```text
net_operating_burn_t =
    operating_payments_t - operating_receipts_t
```

MRR simples:

```text
MRR_t = MRR_(t-1) * (1 + net_mrr_growth_t)
```

ARR run-rate:

```text
ARR_run_rate_t = 12 * MRR_t
```

ARR não deve ser tratado como receita realizada ou caixa.

---

# 7. Métricas V0

Obrigatórias:

- cash trajectory;
- cash minimum;
- gross operating burn;
- net operating burn;
- static runway;
- projected cash-out month;
- minimum reserve violation month;
- projected MRR;
- projected ARR run-rate;
- total incremental cost of action;
- cash required to sustain plan;
- delta versus baseline.

O sistema deve mostrar sempre:

```text
Data-base
Horizonte
Premissas
Ações
Restrições
Resultado
Limitações
```

---

# 8. Robust Decision Engine

Esse é o principal diferencial da V0.

O usuário define:

```text
milestone_date
minimum_cash_reserve
protected_costs
allowed_actions
```

Uma ação é financeiramente viável quando:

```text
feasible(action, future) =
    min(cash_t(action, future) - reserve_t) >= 0
```

e respeita restrições operacionais.

O sistema deve responder:

- ação é viável no cenário central?
- em quais cenários deixa de ser?
- qual a pior deterioração suportada?
- qual atraso máximo tolerado?
- qual custo máximo de contratação ainda é aceitável?
- qual o primeiro mês possível para contratar mantendo a reserva?
- quanto capital adicional seria necessário para sustentar o plano?

---

# 9. Reverse Stress Testing

Implementar antes de Monte Carlo.

Exemplos:

```text
Qual queda máxima em recebimentos mantém o plano viável?

Qual atraso máximo em meses mantém a reserva?

Qual custo máximo mensal da contratação cabe no plano?

Qual aumento máximo de OPEX preserva o caixa até o marco?
```

Para relações monotônicas:

- usar bisseção;
- retornar limite aproximado;
- registrar tolerância utilizada.

Para relações não monotônicas:

- usar grade explícita;
- não afirmar otimização contínua.

Resultado:

```text
Plano atual suporta:
- até 1 mês de atraso;
- até -7,8% em recebimentos;
- contratação máxima de R$ 9.400/mês;
antes de violar a reserva de R$ 50 mil.
```

Não interpretar esses limites como probabilidades.

---

# 10. Cenários

Cada empresa deve possuir pelo menos:

1. **Baseline**
2. **Alternative A**
3. **Alternative B**

Um cenário contém:

```text
scenario_id
company_id
baseline_version
created_at
horizon
actions
assumptions
constraints
engine_version
```

Comparar somente cenários com:

- mesma data-base;
- mesmo horizonte;
- mesma versão de baseline ou indicação explícita da diferença.

---

# 11. Decision Memo

O MVP deve gerar automaticamente um memo determinístico.

Estrutura:

```text
Empresa
Data-base
Objetivo
Restrição

Estado atual
- Caixa
- MRR
- Burn
- Runway

Decisão avaliada

Cenários

Resultado central

Limites / stress

Principais premissas

Condição que invalida o plano

Decisão escolhida

Data da próxima revisão

Limitações
```

Exportação inicial:

- HTML;
- impressão para PDF pelo navegador.

Evitar dependência de LLM.

---

# 12. Persistência mínima

Usar **SQLite** no MVP local.

Entidades mínimas:

```text
companies
financial_periods
scenarios
scenario_actions
scenario_assumptions
simulation_runs
decision_records
action_events
outcome_observations
```

Cada execução deve guardar:

```text
input_snapshot
engine_version
created_at
scenario_id
result_summary
```

Dados reais do piloto:

- nunca entram no Git;
- devem ficar fora de `data/synthetic`;
- devem ter storage separado e backup protegido.

---

# 13. Interface

## V0

Usar:

```text
Python
Streamlit
SQLite
Pandas
NumPy
```

Objetivo: velocidade e auditabilidade.

Telas:

### 1. Company

- seleção/cadastro;
- mês base;
- resumo financeiro.

### 2. Import

- formulário;
- CSV;
- validação;
- preview;
- confirmação.

### 3. Scenario Builder

- selecionar baseline;
- adicionar ação;
- editar hipótese;
- escolher marco;
- escolher reserva.

### 4. Compare

Tabela:

```text
Baseline
Scenario A
Scenario B
```

Com:

- caixa final;
- caixa mínimo;
- cash-out;
- runway;
- custo incremental;
- reserva;
- fragilidade.

### 5. Stress

Sliders/inputs para:

- atraso;
- queda de recebimento;
- custo;
- data da contratação.

### 6. Decision Memo

- resumo;
- decisão registrada;
- exportação.

### 7. History

- decisões;
- cenários;
- realizado posterior.

---

# 14. Importação CSV

Formato inicial simples:

```text
month,
starting_cash,
operating_receipts,
personnel,
marketing,
other_opex,
capex,
debt_service,
financing_inflows,
mrr
```

Requisitos:

- mês `YYYY-MM`;
- moeda definida por empresa;
- zero diferente de ausente;
- erros por linha;
- preview antes de persistir;
- importação repetida não pode duplicar o período;
- correção cria revisão.

Não tentar importar qualquer planilha arbitrária.

---

# 15. Validação financeira obrigatória

Casos de teste mínimos:

1. caixa sem movimentação;
2. receita sem recebimento;
3. recebimento sem receita;
4. gasto único;
5. contratação no mês 1;
6. contratação atrasada;
7. burn negativo;
8. caixa inicial zero;
9. cash-out dentro do horizonte;
10. ausência de cash-out;
11. reserva violada antes de caixa zero;
12. zero versus missing;
13. financing inflow;
14. churn não contado duas vezes;
15. folha não contada duas vezes;
16. cenário alterado não modifica baseline congelado.

Exemplo de referência:

```text
Caixa inicial: 100.000
Recebimentos mensais: 20.000
Saídas mensais: 30.000
```

Resultado:

```text
mês 1 = 90.000
mês 10 = 0
```

Com gasto adicional de R$ 5.000/mês:

```text
cash-out ocorre antes.
```

Os testes devem conter cálculos independentes da implementação.

---

# 16. Milestones de implementação

## H0 — Domain + Financial Engine

Implementar:

- tipos monetários;
- períodos;
- baseline;
- cash-flow engine;
- MRR engine;
- métricas;
- validação.

Gate:

- testes financeiros passam;
- resultados conferidos manualmente.

---

## H1 — Scenario Engine

Implementar:

- cenário;
- ações;
- hiring;
- OPEX;
- delay;
- comparação baseline vs alternativas.

Gate:

- três cenários reproduzíveis;
- mudanças não alteram histórico.

---

## H2 — Robustness / Reverse Stress

Implementar:

- reserva;
- milestone;
- feasible();
- atraso máximo;
- perda máxima de recebimento;
- custo máximo;
- contratação mais cedo possível.

Gate:

- limites reproduzíveis;
- monotonicidade verificada nos casos onde bisseção for usada.

---

## H3 — Local Product Demo

Implementar:

- Streamlit;
- formulário;
- CSV;
- dashboard;
- scenario builder;
- compare;
- stress;
- memo.

Gate:

- empresa sintética percorre fluxo inteiro sem editar código.

---

## H4 — Decision History

Implementar:

- SQLite;
- snapshots;
- decisão escolhida;
- ação executada;
- outcome posterior;
- history.

Gate:

- decisão antiga continua reproduzível após nova importação.

---

## H5 — Pilot Candidate

Preparar:

- dataset template;
- instruções;
- política básica de dados;
- backup;
- dados sintéticos;
- roteiro de onboarding;
- demo;
- memo;
- sanity check.

Gate:

- pronto para uso assistido com até 5 empresas.

**STOP após H5.**

Não avançar automaticamente para SaaS online.

---

# 17. O que NÃO implementar antes do piloto

Explicitamente fora:

- React;
- Next.js;
- FastAPI;
- PostgreSQL;
- Supabase;
- multi-tenancy online;
- billing;
- marketplace;
- investor matching;
- scraping;
- LLM em produção;
- vector database;
- data lake;
- microservices;
- Kubernetes;
- feature store;
- real-time streaming;
- causal ML;
- XGBoost;
- survival model;
- portfolio optimization;
- auto-investment;
- score universal;
- recommendation engine baseado em ML.

Essas tecnologias só entram quando existe problema real exigindo-as.

---

# 18. Piloto

Primeiro grupo:

```text
3–5 startups
SaaS B2B
receita recorrente
mínimo de um fechamento financeiro utilizável
```

Duração:

```text
6–8 semanas
```

Objetivo:

avaliar se o sistema melhora a qualidade e a velocidade de uma decisão real.

Fluxo:

### Semana 1

- onboarding;
- baseline;
- conciliação.

### Semana 2

- escolher uma decisão real;
- construir baseline + 2 alternativas;
- stress test;
- gerar memo.

### Semanas 3–4

- registrar ação tomada;
- observar problemas de uso.

### Semanas 5–6

- novo fechamento;
- comparar realizado versus cenário congelado.

### Semanas 7–8

- entrevista;
- decisão de continuar;
- proposta comercial.

---

# 19. Critérios de sucesso do piloto

Para 5 startups:

### Ativação

```text
>= 4/5 completam baseline + cenário
```

### Utilidade

```text
>= 3/5 usam a análise em decisão real
```

### Retorno

```text
>= 3/5 voltam no fechamento seguinte
```

### Compreensão

```text
>= 4/5 distinguem:
dado
premissa
simulação
```

### Carga operacional

```text
<= 20 min por startup na atualização recorrente,
depois do onboarding
```

### Comercial

- comprador institucional identificado;
- proposta concreta apresentada;
- decisão real de continuidade obtida.

Não exigir prova de:

- aumento de crescimento;
- redução de falência;
- causalidade;
- ROI estatisticamente significativo.

O piloto mede utilidade e processo.

---

# 20. Dados e privacidade

Para piloto institucional:

Preferência:

```text
startup → fornece dados diretamente
```

em vez de:

```text
instituição → entrega base inteira
```

Solicitar somente métricas empresariais necessárias.

Evitar:

- CPF;
- nomes de funcionários;
- salário individual;
- clientes identificados;
- contatos pessoais;
- informação irrelevante.

Se houver instituição:

- cada startup deve saber o que é compartilhado;
- acesso institucional deve ser explícito;
- pesquisa, benchmark e treinamento são finalidades separadas;
- pseudonimização não deve ser chamada de anonimização.

---

# 21. Evolução após o piloto

Somente após evidência de uso.

## Fase 1 — Probabilistic Simulation

Adicionar:

- Monte Carlo;
- P10/P50/P90;
- chance condicional de cash-out;
- sensibilidade.

Importante:

essas probabilidades são condicionais às distribuições utilizadas.

---

## Fase 2 — Portfolio View

Após parceiro com várias empresas:

- lista de portfólio;
- recência;
- runway;
- cash risk;
- burn trend;
- alerts;
- companies requiring attention.

Sem score opaco.

---

## Fase 3 — SaaS Online

Somente quando acesso independente for necessário.

Stack candidata:

```text
FastAPI
PostgreSQL
managed auth
React/TypeScript
```

---

## Fase 4 — Predictive ML

Somente com dados históricos suficientes.

Targets possíveis:

- receipts next month;
- cash shortfall;
- distress;
- fundraising need;
- growth acceleration.

Modelo só entra se superar baseline simples fora da amostra.

---

## Fase 5 — Causal Inference

Pré-requisitos:

```text
state
action proposed
action executed
timing
dose
outcome
confounders
comparison group
```

Perguntas:

```text
Qual foi o efeito de determinada ação?
Para quais empresas?
Em qual regime?
```

Sem desenho de identificação defensável, não usar claim causal.

---

## Fase 6 — Decision Optimization

Objetivo futuro:

```text
a* = argmax ExpectedUtility(a) - λ Risk(a)
```

Sujeito a:

```text
runway >= X
cash_out_probability <= Y
budget <= B
operational_constraints
```

Só permitir ações dentro da região suportada pelos dados/modelos.

---

# 22. Dataset estratégico de longo prazo

A arquitetura deve favorecer a coleta de:

```text
company_id
state_at_decision
market_context
proposed_actions
chosen_action
actual_action
dose
decision_time
effective_time
constraints
rationale
outcome_3m
outcome_6m
outcome_12m
```

Separar:

```text
proposed action
chosen action
executed action
```

Registrar também:

```text
no_action
cancelled_action
```

Objetivo:

```text
State + Action + Regime → Outcome
```

Esse dataset é potencialmente o principal moat do negócio.

---

# 23. Definição do endgame

O produto pode evoluir de:

```text
“What happens if...?”
```

para:

```text
“What is likely to happen?”
```

depois:

```text
“What would happen if we intervene?”
```

e finalmente:

```text
“What should we do?”
```

Visão final:

> **Decision Intelligence Infrastructure for private companies and private capital.**

Possíveis verticais futuras:

- startup decision support;
- portfolio intelligence;
- follow-on decisions;
- capital allocation;
- underwriting;
- venture debt;
- benchmarks;
- private-company risk API;
- decision intelligence API.

Mas nenhuma dessas expansões deve contaminar o MVP.

---

# 24. Sequência recomendada para o Codex

O Codex deve executar nesta ordem:

```text
1. Congelar schema V0
2. Criar domínio financeiro
3. Implementar engine
4. Testar invariantes
5. Implementar scenarios
6. Implementar reverse stress
7. Implementar persistência
8. Construir demo Streamlit
9. Criar memo
10. Executar walkthrough sintético
11. Preparar pilot package
12. STOP
```

Antes de cada milestone:

- definir critério de aceite;
- implementar;
- rodar testes;
- revisar outputs;
- atualizar documentação.

Não fazer refactors arquiteturais preventivos sem necessidade observada.

---

# 25. Estrutura de repositório recomendada

```text
angel_market/
├── README.md
├── ESCOPO.md
├── IMPLEMENTACAO_MVP.md
├── pyproject.toml
│
├── src/
│   └── angel_market/
│       ├── domain/
│       │   ├── money.py
│       │   ├── periods.py
│       │   ├── company.py
│       │   └── scenario.py
│       │
│       ├── ingestion/
│       │   ├── csv_parser.py
│       │   ├── validation.py
│       │   └── schema.py
│       │
│       ├── engine/
│       │   ├── cashflow.py
│       │   ├── revenue.py
│       │   ├── metrics.py
│       │   ├── scenarios.py
│       │   ├── constraints.py
│       │   └── reverse_stress.py
│       │
│       ├── storage/
│       │   ├── sqlite.py
│       │   └── snapshots.py
│       │
│       ├── reports/
│       │   ├── memo.py
│       │   └── templates/
│       │
│       └── ui/
│           └── app.py
│
├── tests/
│   ├── financial/
│   ├── scenarios/
│   ├── stress/
│   ├── ingestion/
│   └── persistence/
│
├── data/
│   └── synthetic/
│
└── docs/
    ├── DATA_DICTIONARY.md
    ├── PILOT_PROTOCOL.md
    ├── PRIVACY_NOTES.md
    └── MODEL_ASSUMPTIONS.md
```

---

# 26. Critério final de V0 pronta

A V0 está pronta quando uma empresa fictícia consegue:

```text
1. importar dados;
2. reconciliar baseline;
3. criar cenário;
4. adicionar contratação;
5. definir marco;
6. definir reserva;
7. comparar alternativas;
8. rodar reverse stress;
9. identificar limite de falha;
10. registrar decisão;
11. gerar memo;
12. voltar depois e comparar realizado.
```

Tudo isso deve ocorrer:

- sem editar código;
- com resultados reproduzíveis;
- com premissas visíveis;
- sem claims preditivos ou causais indevidos.

---

# 27. Regra de decisão do projeto

Sempre que surgir uma feature nova, perguntar:

> **Isso melhora diretamente uma decisão real de uma startup no piloto ou melhora a coleta do dataset State → Action → Outcome?**

Se a resposta for **não**, adiar.

Essa regra deve prevalecer sobre desejo de adicionar tecnologia, IA ou complexidade.
