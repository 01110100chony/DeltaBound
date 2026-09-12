from angel_market.ingestion.csv_parser import parse_financial_csv


HEADER = (
    "month,starting_cash,operating_receipts,personnel,marketing,other_opex,"
    "capex,debt_service,financing_inflows,mrr\n"
)


def test_zero_is_valid_but_missing_required_value_is_not():
    valid = parse_financial_csv((HEADER + "2026-01,0,0,0,0,0,0,0,0,0\n").encode())
    missing = parse_financial_csv((HEADER + "2026-01,0,,0,0,0,0,0,0,0\n").encode())

    assert valid.valid
    assert valid.parsed.initial_cash_cents == 0
    assert not missing.valid
    assert missing.issues[0].field == "operating_receipts"


def test_errors_identify_line_and_reject_formula():
    result = parse_financial_csv(
        (HEADER + "2026-01,100000,=20000,25000,5000,0,0,0,0,20000\n").encode()
    )
    assert not result.valid
    assert result.issues[0].row == 2
    assert "formula" in result.issues[0].message


def test_months_must_be_unique_and_contiguous():
    duplicate = parse_financial_csv(
        (
            HEADER
            + "2026-01,100000,0,0,0,0,0,0,0,1000\n"
            + "2026-01,,0,0,0,0,0,0,0,\n"
        ).encode()
    )
    gap = parse_financial_csv(
        (
            HEADER
            + "2026-01,100000,0,0,0,0,0,0,0,1000\n"
            + "2026-03,,0,0,0,0,0,0,0,\n"
        ).encode()
    )
    assert any("duplicado" in issue.message for issue in duplicate.issues)
    assert any("lacuna" in issue.message for issue in gap.issues)

