from __future__ import annotations

from pathlib import Path

import pytest

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.financial_compliance_scanner import (
    FinancialComplianceScanner,
    _normalize_stage,
    _stage_gte,
)


def _snapshot(*files: tuple[str, str], funding_round: str | None = None) -> tuple[RepositorySnapshot, FinancialComplianceScanner]:
    snap = RepositorySnapshot(
        source=RepositorySource(kind="local", location="fixture"),
        root=Path("/tmp/unused"),
        files=[
            FileSnapshot(
                path=path,
                size_bytes=len(text),
                extension=Path(path).suffix.lower(),
                text=text,
            )
            for path, text in files
        ],
    )
    return snap, FinancialComplianceScanner(funding_round=funding_round)


# ── Stage normalization ────────────────────────────────────────────────────────

def test_normalize_stage_aliases():
    assert _normalize_stage("Series A") == "series_a"
    assert _normalize_stage("series-b") == "series_b"
    assert _normalize_stage("pre-seed") == "pre_seed"
    assert _normalize_stage("growth") == "series_c_plus"
    assert _normalize_stage("pre-ipo") == "series_c_plus"
    assert _normalize_stage(None) == "seed"
    assert _normalize_stage("unknown-stage") == "seed"


def test_stage_gte():
    assert _stage_gte("series_b", "seed")
    assert _stage_gte("series_a", "series_a")
    assert not _stage_gte("seed", "series_a")
    assert not _stage_gte("pre_seed", "series_b")


# ── §83(b) election — Pre-seed / Seed ─────────────────────────────────────────

def test_restricted_stock_no_83b_flagged_at_pre_seed():
    snap, scanner = _snapshot(
        ("src/equity.py", "grant_restricted_stock(founder, shares=1000000, vesting_schedule=four_year)"),
        funding_round="pre-seed",
    )
    findings = scanner.scan(snap)
    assert any("restricted_stock_no_83b" in f.id for f in findings)


def test_restricted_stock_no_83b_flagged_at_seed():
    snap, scanner = _snapshot(
        ("src/equity.py", "issue_founder_shares(employee, restricted_stock=True, cliff_vest=True)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert any("restricted_stock_no_83b" in f.id for f in findings)


def test_restricted_stock_with_83b_not_flagged():
    snap, scanner = _snapshot(
        ("src/equity.py", "# 83(b) election required — send template on grant\ngrant_restricted_stock(founder, vesting_schedule=four_year)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert not any("restricted_stock_no_83b" in f.id for f in findings)


def test_restricted_stock_no_83b_not_flagged_at_series_a():
    # §83(b) advisory only applies at pre_seed / seed
    snap, scanner = _snapshot(
        ("src/equity.py", "grant_restricted_stock(founder, vesting_schedule=four_year)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("restricted_stock_no_83b" in f.id for f in findings)


# ── §409A valuation — Seed+ ───────────────────────────────────────────────────

def test_equity_grant_no_409a_flagged_at_seed():
    snap, scanner = _snapshot(
        ("src/options.py", "create_option_grant(employee, strike_price=0.01, vesting_schedule=four_year)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert any("equity_grant_no_409a" in f.id for f in findings)


def test_equity_grant_no_409a_flagged_at_series_a():
    snap, scanner = _snapshot(
        ("src/options.py", "grant_iso(employee, exercise_price=2.50, cliff_vest=True)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert any("equity_grant_no_409a" in f.id for f in findings)


def test_equity_grant_with_409a_not_flagged():
    snap, scanner = _snapshot(
        ("src/options.py", "# 409A valuation completed 2024-01-15, FMV=$2.50\ngrant_iso(employee, exercise_price=2.50)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("equity_grant_no_409a" in f.id for f in findings)


def test_equity_grant_no_409a_not_flagged_before_seed():
    snap, scanner = _snapshot(
        ("src/options.py", "create_option_grant(employee, strike_price=0.01, vesting_schedule=four_year)"),
        funding_round="pre-seed",
    )
    findings = scanner.scan(snap)
    assert not any("equity_grant_no_409a" in f.id for f in findings)


def test_409a_severity_higher_at_series_a_than_seed():
    snap_seed, scanner_seed = _snapshot(
        ("src/options.py", "grant_iso(employee, exercise_price=2.50, cliff_vest=True)"),
        funding_round="seed",
    )
    snap_a, scanner_a = _snapshot(
        ("src/options.py", "grant_iso(employee, exercise_price=2.50, cliff_vest=True)"),
        funding_round="series-a",
    )
    findings_seed = [f for f in scanner_seed.scan(snap_seed) if "equity_grant_no_409a" in f.id]
    findings_a = [f for f in scanner_a.scan(snap_a) if "equity_grant_no_409a" in f.id]
    assert findings_seed[0].severity == "medium"
    assert findings_a[0].severity == "high"


# ── Form 1099-NEC / W-9 — All stages ─────────────────────────────────────────

def test_contractor_payment_no_1099_flagged():
    snap, scanner = _snapshot(
        ("src/payments.py", "pay_contractor(vendor_id, amount=5000)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert any("contractor_payment_no_1099" in f.id for f in findings)


def test_contractor_payment_with_1099_not_flagged():
    snap, scanner = _snapshot(
        ("src/payments.py", "# collect W-9 before first payment; generate 1099-NEC in January\npay_contractor(vendor_id, amount=5000)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert not any("contractor_payment_no_1099" in f.id for f in findings)


def test_contractor_payment_flagged_at_all_stages():
    for stage in ("pre-seed", "seed", "series-a", "series-b", "series-c"):
        snap, scanner = _snapshot(
            ("src/vendor.py", "pay_independent_contractor(amount=1000)"),
            funding_round=stage,
        )
        findings = scanner.scan(snap)
        assert any("contractor_payment_no_1099" in f.id for f in findings), f"not flagged at {stage}"


# ── Payroll tax withholding — All stages ──────────────────────────────────────

def test_payroll_no_withholding_flagged():
    snap, scanner = _snapshot(
        ("src/payroll.py", "process_payroll(employee_salary=120000, direct_deposit_amount=True)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert any("payroll_no_withholding" in f.id for f in findings)


def test_payroll_with_withholding_not_flagged():
    snap, scanner = _snapshot(
        ("src/payroll.py", "# FICA withholding and state withholding handled via Gusto\nprocess_payroll(employee_salary=120000)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("payroll_no_withholding" in f.id for f in findings)


# ── Form 3921 / AMT — Series A+ ───────────────────────────────────────────────

def test_iso_exercise_no_3921_flagged_at_series_a():
    snap, scanner = _snapshot(
        ("src/equity.py", "record_iso_exercise(employee_id, option_exercise=500, price=2.50)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert any("iso_exercise_no_form_3921" in f.id for f in findings)


def test_iso_exercise_with_3921_not_flagged():
    snap, scanner = _snapshot(
        ("src/equity.py", "# Form 3921 generated for each ISO exercise; AMT disclosed to employee\nrecord_iso_exercise(employee_id, option_exercise=500)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("iso_exercise_no_form_3921" in f.id for f in findings)


def test_iso_exercise_not_flagged_before_series_a():
    snap, scanner = _snapshot(
        ("src/equity.py", "record_iso_exercise(employee_id, option_exercise=500)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert not any("iso_exercise_no_form_3921" in f.id for f in findings)


# ── Wayfair sales tax — Series B+ ────────────────────────────────────────────

def test_payment_processing_no_sales_tax_flagged_at_series_b():
    snap, scanner = _snapshot(
        ("src/billing.py", "stripe.PaymentIntent.create(amount=9900, currency='usd')"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert any("payment_processing_no_sales_tax" in f.id for f in findings)


def test_payment_processing_with_sales_tax_not_flagged():
    snap, scanner = _snapshot(
        ("src/billing.py", "# tax_rate calculated via Avalara AvaTax; tax_code SY010000\nstripe.PaymentIntent.create(amount=9900)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert not any("payment_processing_no_sales_tax" in f.id for f in findings)


def test_payment_processing_not_flagged_before_series_b():
    snap, scanner = _snapshot(
        ("src/billing.py", "stripe.PaymentIntent.create(amount=9900, currency='usd')"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("payment_processing_no_sales_tax" in f.id for f in findings)


# ── FBAR / FATCA — Series B+ ─────────────────────────────────────────────────

def test_intl_transfer_no_fbar_flagged_at_series_b():
    snap, scanner = _snapshot(
        ("src/payments.py", "initiate_wire_transfer(iban='DE89370400440532013000', amount=50000)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert any("intl_transfer_no_fbar" in f.id for f in findings)


def test_intl_transfer_with_fbar_not_flagged():
    snap, scanner = _snapshot(
        ("src/payments.py", "# OFAC sanctions screening applied; FBAR tracked in compliance register\ninitiate_wire_transfer(iban='DE89370400440532013000', amount=50000)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert not any("intl_transfer_no_fbar" in f.id for f in findings)


def test_intl_transfer_not_flagged_before_series_b():
    snap, scanner = _snapshot(
        ("src/payments.py", "initiate_wire_transfer(iban='DE89370400440532013000', amount=50000)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("intl_transfer_no_fbar" in f.id for f in findings)


# ── IRC §382 NOL limitation — Series B+ ──────────────────────────────────────

def test_nol_no_382_flagged_at_series_b():
    snap, scanner = _snapshot(
        ("src/tax.py", "nol_balance = net_operating_loss_carryforward(prior_years=3)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert any("nol_no_382_limit" in f.id for f in findings)


def test_nol_with_382_not_flagged():
    snap, scanner = _snapshot(
        ("src/tax.py", "# section 382 limitation study completed post-Series B\nnol_balance = net_operating_loss_carryforward(prior_years=3)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert not any("nol_no_382_limit" in f.id for f in findings)


def test_nol_not_flagged_before_series_b():
    snap, scanner = _snapshot(
        ("src/tax.py", "nol_balance = net_operating_loss_carryforward(prior_years=3)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("nol_no_382_limit" in f.id for f in findings)


# ── §41 R&D credit — Series B+ ───────────────────────────────────────────────

def test_rd_expense_no_credit_flagged_at_series_b():
    snap, scanner = _snapshot(
        ("src/accounting.py", "log_rd_expense(category='research_expense', amount=250000)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert any("rd_expense_no_credit_tracking" in f.id for f in findings)


def test_rd_expense_with_credit_not_flagged():
    snap, scanner = _snapshot(
        ("src/accounting.py", "# section 41 R&D credit tracking; form 6765 filed\nlog_rd_expense(category='research_expense', amount=250000)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert not any("rd_expense_no_credit_tracking" in f.id for f in findings)


def test_rd_expense_not_flagged_before_series_b():
    snap, scanner = _snapshot(
        ("src/accounting.py", "log_rd_expense(category='research_expense', amount=250000)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("rd_expense_no_credit_tracking" in f.id for f in findings)


# ── §162(m) executive comp — Series C+ ───────────────────────────────────────

def test_exec_comp_no_162m_flagged_at_series_c():
    snap, scanner = _snapshot(
        ("src/hr.py", "set_executive_compensation(ceo_salary=1500000, exec_bonus=500000)"),
        funding_round="series-c",
    )
    findings = scanner.scan(snap)
    assert any("exec_comp_no_162m" in f.id for f in findings)


def test_exec_comp_with_162m_not_flagged():
    snap, scanner = _snapshot(
        ("src/hr.py", "# 162(m) deduction limit analysis completed; covered employee list reviewed\nset_executive_compensation(ceo_salary=1500000)"),
        funding_round="series-c",
    )
    findings = scanner.scan(snap)
    assert not any("exec_comp_no_162m" in f.id for f in findings)


def test_exec_comp_not_flagged_before_series_c():
    snap, scanner = _snapshot(
        ("src/hr.py", "set_executive_compensation(ceo_salary=1500000, exec_bonus=500000)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert not any("exec_comp_no_162m" in f.id for f in findings)


# ── File type filtering ────────────────────────────────────────────────────────

def test_skips_test_directory():
    snap, scanner = _snapshot(
        ("tests/test_payments.py", "pay_contractor(vendor_id, amount=5000)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert not findings


def test_scans_config_files():
    snap, scanner = _snapshot(
        ("config/payroll.json", '{"process_payroll": true, "employee_salary": 120000}'),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert any("payroll_no_withholding" in f.id for f in findings)


def test_skips_unknown_extension():
    snap, scanner = _snapshot(
        ("src/equity.md", "grant_restricted_stock(founder, vesting_schedule=four_year)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert not findings


# ── Finding metadata ──────────────────────────────────────────────────────────

def test_finding_category_is_financial_compliance():
    snap, scanner = _snapshot(
        ("src/options.py", "create_option_grant(employee, strike_price=0.01, vesting_schedule=four_year)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    for f in findings:
        assert f.category == "financial_compliance"


def test_finding_scanner_id():
    snap, scanner = _snapshot(
        ("src/options.py", "create_option_grant(employee, strike_price=0.01, cliff_vest=True)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert any(f.scanner_id == "financial_compliance" for f in findings)


def test_deduplication_across_files():
    # Same rule triggered in two different files should produce two findings
    snap, scanner = _snapshot(
        ("src/options.py", "create_option_grant(employee, strike_price=0.01)"),
        ("src/grants.py", "grant_iso(employee2, exercise_price=3.00)"),
        funding_round="seed",
    )
    findings = [f for f in scanner.scan(snap) if "equity_grant_no_409a" in f.id]
    assert len(findings) == 2


def test_stage_stored_on_scanner():
    scanner = FinancialComplianceScanner(funding_round="Series B")
    assert scanner.stage == "series_b"


# ── IRC §1202 QSBS — Seed+ ────────────────────────────────────────────────────

def test_stock_issuance_no_qsbs_flagged_at_seed():
    snap, scanner = _snapshot(
        ("src/cap_table.py", "issue_shares(investor='Acme Ventures', share_issuance=1000000, price=1.00)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert any("stock_issuance_no_qsbs" in f.id for f in findings)


def test_stock_issuance_no_qsbs_flagged_at_series_a():
    snap, scanner = _snapshot(
        ("src/equity.py", "record_stock_issuance(round='Series A', new_shares_issued=5000000)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert any("stock_issuance_no_qsbs" in f.id for f in findings)


def test_stock_issuance_with_qsbs_not_flagged():
    snap, scanner = _snapshot(
        ("src/cap_table.py", "# QSBS §1202 eligibility confirmed; gross assets < $50M at issuance\nissue_shares(investor='Acme Ventures', share_issuance=1000000)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert not any("stock_issuance_no_qsbs" in f.id for f in findings)


def test_stock_issuance_not_flagged_before_seed():
    snap, scanner = _snapshot(
        ("src/cap_table.py", "issue_shares(founder='Alice', share_issuance=10000000)"),
        funding_round="pre-seed",
    )
    findings = scanner.scan(snap)
    assert not any("stock_issuance_no_qsbs" in f.id for f in findings)


# ── ISO $100K annual limit §422(d) — Series A+ ────────────────────────────────

def test_iso_grant_no_100k_limit_flagged_at_series_a():
    snap, scanner = _snapshot(
        ("src/options.py", "create_iso_grant(employee_id=42, shares=200000, exercise_price=2.50)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert any("iso_grant_no_100k_limit" in f.id for f in findings)


def test_iso_grant_with_100k_limit_not_flagged():
    snap, scanner = _snapshot(
        ("src/options.py", "# Check §422(d): cumulative ISO FMV vesting this year must not exceed $100,000\ncreate_iso_grant(employee_id=42, shares=200000, exercise_price=2.50)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("iso_grant_no_100k_limit" in f.id for f in findings)


def test_iso_grant_not_flagged_before_series_a():
    snap, scanner = _snapshot(
        ("src/options.py", "grant_iso(employee, exercise_price=1.00, incentive_stock_option=True)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert not any("iso_grant_no_100k_limit" in f.id for f in findings)


def test_iso_grant_flagged_at_series_b():
    snap, scanner = _snapshot(
        ("src/options.py", "issue_iso_award(employee_id=99, fmv=5.00, incentive_stock_option=True)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert any("iso_grant_no_100k_limit" in f.id for f in findings)


# ── §409A on severance / deferred comp — Series A+ ───────────────────────────

def test_severance_no_409a_flagged_at_series_a():
    snap, scanner = _snapshot(
        ("src/hr.py", "create_severance_agreement(employee_id=7, severance_pay=months_6)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert any("deferred_comp_no_409a" in f.id for f in findings)


def test_deferred_bonus_no_409a_flagged():
    snap, scanner = _snapshot(
        ("src/compensation.py", "set_bonus_deferral(employee_id=3, deferred_compensation=50000)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert any("deferred_comp_no_409a" in f.id for f in findings)


def test_severance_with_409a_not_flagged():
    snap, scanner = _snapshot(
        ("src/hr.py", "# 409A compliant: separation from service trigger; short-term deferral exception applies\ncreate_severance_agreement(employee_id=7, severance_pay=months_6)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("deferred_comp_no_409a" in f.id for f in findings)


def test_severance_not_flagged_before_series_a():
    snap, scanner = _snapshot(
        ("src/hr.py", "create_severance_agreement(employee_id=7, severance_pay=months_6)"),
        funding_round="seed",
    )
    findings = scanner.scan(snap)
    assert not any("deferred_comp_no_409a" in f.id for f in findings)


# ── §280G golden parachute — Series B+ ───────────────────────────────────────

def test_change_of_control_no_280g_flagged_at_series_b():
    snap, scanner = _snapshot(
        ("src/equity.py", "if change_of_control: accelerate_vesting(employee, double_trigger=True)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert any("change_of_control_no_280g" in f.id for f in findings)


def test_single_trigger_acceleration_flagged():
    snap, scanner = _snapshot(
        ("src/options.py", "handle_coc_event(single_trigger=True, severance_acceleration=True)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert any("change_of_control_no_280g" in f.id for f in findings)


def test_change_of_control_with_280g_not_flagged():
    snap, scanner = _snapshot(
        ("src/equity.py", "# 280G analysis completed; safe harbor vote passed at 75% threshold\nif change_of_control: accelerate_vesting(employee, double_trigger=True)"),
        funding_round="series-b",
    )
    findings = scanner.scan(snap)
    assert not any("change_of_control_no_280g" in f.id for f in findings)


def test_change_of_control_not_flagged_before_series_b():
    snap, scanner = _snapshot(
        ("src/equity.py", "if change_of_control: accelerate_vesting(employee, double_trigger=True)"),
        funding_round="series-a",
    )
    findings = scanner.scan(snap)
    assert not any("change_of_control_no_280g" in f.id for f in findings)


def test_change_of_control_flagged_at_series_c():
    snap, scanner = _snapshot(
        ("src/equity.py", "process_acquisition_trigger(change_in_control=True, single_trigger=True)"),
        funding_round="series-c",
    )
    findings = scanner.scan(snap)
    assert any("change_of_control_no_280g" in f.id for f in findings)
