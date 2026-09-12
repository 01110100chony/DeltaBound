REQUIRED_COLUMNS = (
    "month",
    "starting_cash",
    "operating_receipts",
    "personnel",
    "marketing",
    "other_opex",
    "capex",
    "debt_service",
    "financing_inflows",
    "mrr",
)

OPTIONAL_COLUMNS = (
    "revenue_recognized",
    "cash_cogs",
    "operating_taxes",
    "other_net_cash_movements",
    "net_mrr_growth",
    "origin",
)

MAX_CSV_BYTES = 2 * 1024 * 1024

