# Angel Market MVP

Aplicacao local e auditavel para avaliar se uma decisao financeira cabe ate um marco, quais premissas precisam permanecer verdadeiras e onde o plano viola a reserva. O escopo termina no piloto local H5: nao ha predicao, causalidade, score opaco, recomendacao automatica ou SaaS online.

## Executar

Requer Python 3.11 ou superior.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\streamlit run src/angel_market/ui/app.py
```

O banco local fica em `data/private/angel_market.db`, ignorado pelo Git. Para usar outro local, defina `ANGEL_MARKET_DB`.

## Validar

```powershell
pytest -q
python scripts/run_walkthrough.py
```

O walkthrough usa apenas [dados sinteticos](data/synthetic/saas_b2b_demo.csv), cria baseline + duas alternativas, calcula stress reverso, registra decisao/acao/realizado e gera um memo HTML em `data/private`.

Backup consistente do SQLite (o destino deve estar em armazenamento protegido e nao pode existir):

```powershell
python scripts/backup_local.py D:\backups-protegidos\angel-market.db
```

## Fluxo da demo

1. Cadastre uma empresa em **Company**.
2. Importe o CSV sintetico ou use o formulario em **Import**; confirme somente apos a previa.
3. Crie cenarios imutaveis em **Scenario Builder**.
4. Compare 2–3 cenarios com mesma base/horizonte.
5. Calcule limites em **Stress**; os resultados nao sao probabilidades.
6. Registre a escolha e baixe o HTML em **Decision Memo**.
7. Registre acao e realizado posterior em **History**.

Veja tambem [dicionario de dados](docs/DATA_DICTIONARY.md), [premissas do modelo](docs/MODEL_ASSUMPTIONS.md), [protocolo do piloto](docs/PILOT_PROTOCOL.md) e [notas de privacidade](docs/PRIVACY_NOTES.md).
O fechamento dos gates H0–H5 esta em [status de implementacao](docs/IMPLEMENTATION_STATUS.md).
