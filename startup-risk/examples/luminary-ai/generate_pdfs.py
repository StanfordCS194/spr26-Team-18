"""
Generate synthetic financial documents for Luminary AI, Inc. (Series A demo).
Run: python3 generate_pdfs.py
"""
from __future__ import annotations
from fpdf import FPDF
from pathlib import Path

OUT = Path(__file__).parent / "docs"
OUT.mkdir(exist_ok=True)

COMPANY = "Luminary AI, Inc."
ADDR    = "548 Market St, Suite 910, San Francisco, CA 94104"
EIN     = "47-3821059"
PERIOD  = "Q1 2025 (January 1 - March 31, 2025)"

NAVY  = (15,  40,  80)
GOLD  = (180, 140,  40)
LIGHT = (245, 246, 248)
BLACK = (30,  30,  30)
GRAY  = (120, 120, 120)


# ── PDF base class ─────────────────────────────────────────────────────────────

class Doc(FPDF):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self._title    = title
        self._subtitle = subtitle
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=20)
        self.add_page()
        self._header_block()

    def _header_block(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 36, "F")
        self.set_xy(18, 7)
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, COMPANY, ln=True)
        self.set_x(18)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(200, 210, 230)
        self.cell(0, 5, ADDR + f"   |   EIN {EIN}", ln=True)
        self.ln(14)
        self.set_text_color(*BLACK)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, self._title, ln=True)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*GRAY)
        self.cell(0, 5, self._subtitle, ln=True)
        self.set_draw_color(*GOLD)
        self.set_line_width(0.5)
        self.line(18, self.get_y() + 2, 192, self.get_y() + 2)
        self.ln(6)
        self.set_text_color(*BLACK)

    def section(self, label: str):
        self.ln(4)
        self.set_fill_color(*LIGHT)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*NAVY)
        self.cell(0, 6, f"  {label.upper()}", ln=True, fill=True)
        self.ln(2)
        self.set_text_color(*BLACK)

    def th(self, cols: list[tuple[str, int]], align: str = "L"):
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(*NAVY)
        self.set_text_color(255, 255, 255)
        for label, w in cols:
            self.cell(w, 6, label, border=0, fill=True, align=align)
        self.ln()
        self.set_text_color(*BLACK)

    def tr(self, vals: list[tuple[str, int]], shade: bool = False, align: str = "L"):
        self.set_font("Helvetica", "", 8)
        if shade:
            self.set_fill_color(*LIGHT)
        for val, w in vals:
            self.cell(w, 6, str(val), border=0, fill=shade, align=align)
        self.ln()

    def note(self, text: str):
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*GRAY)
        self.multi_cell(0, 5, text)
        self.set_text_color(*BLACK)
        self.ln(2)

    def kv(self, label: str, value: str):
        self.set_font("Helvetica", "B", 8)
        self.cell(55, 6, label + ":", align="L")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 6, value, ln=True)

    def save(self, name: str) -> Path:
        p = OUT / name
        self.output(str(p))
        print(f"  wrote {p.name}")
        return p


# ── 1. Payroll Register ────────────────────────────────────────────────────────

def payroll_register():
    d = Doc("Payroll Disbursement Register", f"Period: {PERIOD}   |   Pay Frequency: Bi-weekly")
    d.kv("Processor", "Gusto Payroll Services")
    d.kv("Pay Dates", "Jan 10, Jan 24, Feb 7, Feb 21, Mar 7, Mar 21")
    d.kv("Total Employees", "28")
    d.ln(4)

    d.section("Employee Salary Disbursements -- Q1 2025")
    cols = [("Employee", 52), ("Dept", 28), ("Annual Salary", 28),
            ("Gross (Q1)", 28), ("Net Pay (Q1)", 28), ("State", 10)]
    d.th(cols)
    rows = [
        ("Aria Chen",        "Engineering",  "$195,000", "$48,750",  "$38,102",  "CA"),
        ("Marcus Webb",      "Engineering",  "$185,000", "$46,250",  "$36,280",  "TX"),
        ("Priya Nair",       "Product",      "$175,000", "$43,750",  "$34,508",  "NY"),
        ("Jordan Ellis",     "Engineering",  "$180,000", "$45,000",  "$35,400",  "CA"),
        ("Sam Okafor",       "Sales",        "$140,000", "$35,000",  "$28,175",  "FL"),
        ("Taylor Kim",       "Engineering",  "$190,000", "$47,500",  "$37,190",  "CO"),
        ("Riley Patel",      "Design",       "$155,000", "$38,750",  "$30,622",  "WA"),
        ("Devon Larson",     "Engineering",  "$185,000", "$46,250",  "$36,280",  "CA"),
        ("Morgan Singh",     "Marketing",    "$130,000", "$32,500",  "$26,265",  "NY"),
        ("Casey Thompson",   "Engineering",  "$175,000", "$43,750",  "$34,508",  "TX"),
        ("Avery Williams",   "Sales",        "$135,000", "$33,750",  "$27,220",  "CA"),
        ("Quinn Johnson",    "Operations",   "$120,000", "$30,000",  "$24,450",  "CA"),
        ("Blake Martinez",   "Engineering",  "$188,000", "$47,000",  "$36,836",  "WA"),
        ("Skylar Brown",     "Data Science", "$192,000", "$48,000",  "$37,574",  "CO"),
        ("Reese Garcia",     "Engineering",  "$178,000", "$44,500",  "$34,900",  "TX"),
        ("[13 additional employees]", "Various", "--", "$412,875", "$328,640", "Multi"),
    ]
    for i, r in enumerate(rows):
        d.tr(list(zip(r, [52, 28, 28, 28, 28, 10])), shade=(i % 2 == 0))

    d.ln(4)
    d.section("Q1 Summary Totals")
    d.kv("Total Gross Payroll",      "$939,375.00")
    d.kv("Total Net Disbursed",      "$742,190.00")
    d.kv("Benefits Deductions",      "$73,248.00")
    d.kv("401(k) Employee Contrib.", "$47,520.00")
    d.kv("Health/Dental/Vision",     "$25,728.00")
    d.ln(4)

    d.section("Direct Deposit Summary")
    d.kv("Payment Method",  "ACH Direct Deposit via Gusto")
    d.kv("Bank",            "Mercury Business Checking -- ****4821")
    d.kv("Run Payroll Dates", "6 pay runs completed; 0 corrections")
    d.ln(4)

    d.note(
        "Net pay reflects deductions for health, dental, and vision premiums and 401(k) "
        "contributions. Gross-to-net calculation performed by Gusto. "
        "This register is for internal record-keeping only."
    )
    d.save("payroll_register_q1_2025.pdf")


# ── 2. Equity Grant Log ────────────────────────────────────────────────────────

def equity_grant_log():
    d = Doc("Equity & Stock Option Grant Log", f"As of March 31, 2025   |   Administered via Carta")
    d.kv("Option Pool",        "10,000,000 shares authorized")
    d.kv("Pool Utilized",      "6,842,500 shares (68.4%)")
    d.kv("Board Approval",     "February 12, 2025 (Board Resolution #2025-04)")
    d.ln(4)

    d.section("New Grants -- Q1 2025")
    cols = [("Recipient", 48), ("Type", 14), ("Shares", 22),
            ("Strike Price", 22), ("Grant Date", 22), ("Vesting", 46)]
    d.th(cols)
    rows = [
        ("Aria Chen",       "ISO", "120,000", "$0.82", "Jan 15, 2025", "4yr / 1yr cliff"),
        ("Taylor Kim",      "ISO", "100,000", "$0.82", "Jan 15, 2025", "4yr / 1yr cliff"),
        ("Skylar Brown",    "ISO", "150,000", "$0.82", "Jan 15, 2025", "4yr / 1yr cliff"),
        ("Blake Martinez",  "ISO",  "90,000", "$0.82", "Feb 1,  2025", "4yr / 1yr cliff"),
        ("Priya Nair",      "ISO",  "80,000", "$0.82", "Feb 1,  2025", "4yr / 1yr cliff"),
        ("New Hire (×3)",   "ISO", "240,000", "$0.82", "Mar 3,  2025", "4yr / 1yr cliff"),
    ]
    for i, r in enumerate(rows):
        d.tr(list(zip(r, [48, 14, 22, 22, 22, 46])), shade=(i % 2 == 0))

    d.ln(4)
    d.section("Cumulative Grant Summary")
    cols2 = [("Class", 40), ("Shares Granted", 35), ("Shares Outstanding", 35),
             ("Avg Strike", 30), ("Status", 34)]
    d.th(cols2)
    rows2 = [
        ("Incentive Stock Options (ISO)", "5,230,000", "4,890,000", "$0.61", "Active"),
        ("Non-Qualified Stock Options",    "1,612,500", "1,400,000", "$0.44", "Active"),
        ("Restricted Stock Units (RSU)",           "0",         "0",    "--",  "--"),
    ]
    for i, r in enumerate(rows2):
        d.tr(list(zip(r, [40, 35, 35, 30, 34])), shade=(i % 2 == 0))

    d.ln(4)
    d.section("Vesting Events -- Q1 2025")
    d.kv("Shares Vested Q1",    "284,375")
    d.kv("Employees Vesting",   "19")
    d.kv("Early Exercises",     "0")
    d.kv("Cancellations",       "45,000 (1 departure)")
    d.ln(4)

    d.note(
        "All grants issued under the 2022 Equity Incentive Plan. Strike prices reflect the "
        "board-approved exercise price at time of grant. Grant administration handled through "
        "Carta; all certificates issued electronically."
    )
    d.save("equity_grant_log_q1_2025.pdf")


# ── 3. ISO Exercise Log ───────────────────────────────────────────────────────

def iso_exercise_log():
    d = Doc("ISO Exercise & Early Exercise Log", f"Period: {PERIOD}")
    d.kv("Plan", "2022 Equity Incentive Plan")
    d.kv("Administrator", "Carta")
    d.ln(4)

    d.section("ISO Exercise Transactions -- Q1 2025")
    cols = [("Employee", 46), ("Grant Date", 24), ("Exercise Date", 24),
            ("Shares", 22), ("Strike", 18), ("Total Paid", 24), ("Method", 36)]
    d.th(cols)
    rows = [
        ("Jordan Ellis",   "Mar 14, 2022", "Jan 22, 2025", "50,000",  "$0.34", "$17,000", "Cash"),
        ("Sam Okafor",     "Sep 1,  2022", "Feb 5,  2025", "30,000",  "$0.34",  "$10,200", "Cash"),
        ("Avery Williams", "Mar 14, 2022", "Feb 19, 2025", "25,000",  "$0.34",   "$8,500", "Cash"),
        ("Quinn Johnson",  "Jan 10, 2023", "Mar 12, 2025", "20,000",  "$0.52",  "$10,400", "Cash"),
    ]
    for i, r in enumerate(rows):
        d.tr(list(zip(r, [46, 24, 24, 22, 18, 24, 36])), shade=(i % 2 == 0))

    d.ln(4)
    d.kv("Total Shares Exercised Q1", "125,000")
    d.kv("Total Exercise Proceeds",   "$46,100.00")
    d.ln(6)

    d.section("Early Exercise Activity")
    d.set_font("Helvetica", "", 9)
    d.cell(0, 6, "No early exercises recorded in Q1 2025.", ln=True)
    d.ln(4)

    d.section("Outstanding Vested-but-Unexercised Options")
    d.kv("Total Vested Unexercised",   "1,204,375 shares")
    d.kv("Intrinsic Value (@ $2.14)",  "$2,577,362.50 (estimated)")
    d.ln(4)

    d.note(
        "Exercise transactions processed and settled through Carta. Proceeds deposited to "
        "company operating account at Mercury. Exercise confirmations sent to each "
        "optionholder upon completion."
    )
    d.save("iso_exercise_log_q1_2025.pdf")


# ── 4. Contractor Payment Ledger ──────────────────────────────────────────────

def contractor_ledger():
    d = Doc("Independent Contractor Payment Ledger", f"Period: {PERIOD}")
    d.kv("Payment Processor", "Mercury ACH / Bill.com")
    d.kv("Active Contractors", "4")
    d.ln(4)

    d.section("Contractor Payments -- Q1 2025")
    cols = [("Contractor", 46), ("Service", 36), ("Jan", 20),
            ("Feb", 20), ("Mar", 20), ("Q1 Total", 22), ("State", 10)]
    d.th(cols)
    rows = [
        ("Vance Studio LLC",    "UI/UX Design",         "$8,400",  "$8,400",  "$9,600",  "$26,400", "NY"),
        ("Data Forge Partners", "ML Data Labeling",     "$12,000", "$12,000", "$15,000", "$39,000", "WA"),
        ("SecureOps Inc.",      "Security Consulting",  "$6,000",  "$6,000",  "$6,000",  "$18,000", "TX"),
        ("Brendan Walsh",       "Backend Dev (Freelancer)", "$9,600", "$9,600", "$9,600", "$28,800", "CO"),
    ]
    for i, r in enumerate(rows):
        d.tr(list(zip(r, [46, 36, 20, 20, 20, 22, 10])), shade=(i % 2 == 0))

    d.ln(4)
    d.section("Q1 Totals")
    d.kv("Total Vendor Payments Q1",  "$112,200.00")
    d.kv("YTD Payments (Jan-Mar)",    "$112,200.00")
    d.kv("Avg Monthly Spend",         "$37,400.00")
    d.ln(4)

    d.section("Contractor Agreements on File")
    cols2 = [("Contractor", 60), ("Agreement Date", 35), ("Rate", 30), ("Term", 49)]
    d.th(cols2)
    rows2 = [
        ("Vance Studio LLC",    "Nov 12, 2024", "$2,100/wk",   "Nov 2024 - Jun 2025"),
        ("Data Forge Partners", "Oct 3,  2024", "$4,000/mo",   "Oct 2024 - ongoing"),
        ("SecureOps Inc.",      "Jan 6,  2025", "$6,000/mo",   "Jan 2025 - Dec 2025"),
        ("Brendan Walsh",       "Aug 15, 2024", "$120/hr",     "Aug 2024 - ongoing"),
    ]
    for i, r in enumerate(rows2):
        d.tr(list(zip(r, [60, 35, 30, 49])), shade=(i % 2 == 0))

    d.ln(4)
    d.note(
        "All payments made via ACH. Independent contractor agreements on file confirm "
        "services rendered. Invoices retained in Bill.com. Contractor classification "
        "reviewed annually by outside counsel."
    )
    d.save("contractor_payment_ledger_q1_2025.pdf")


# ── 5. R&D Expense Report ─────────────────────────────────────────────────────

def rd_expense_report():
    d = Doc("Research & Development Expense Report", f"Period: {PERIOD}   |   ASC 730 Treatment")
    d.kv("Accounting Treatment", "Research costs expensed as incurred (ASC 730)")
    d.kv("Book Treatment",       "Full expensing on P&L")
    d.kv("Approver",             "CFO -- Dana Reeves")
    d.ln(4)

    d.section("R&D Spend by Category -- Q1 2025")
    cols = [("Category", 60), ("Jan", 24), ("Feb", 24), ("Mar", 24), ("Q1 Total", 28), ("% of Total", 14)]
    d.th(cols)
    rows = [
        ("Model Training (GPU compute)",    "$48,200",  "$51,400",  "$54,800",  "$154,400",  "38.1%"),
        ("Engineering Labor -- R&D",         "$42,500",  "$42,500",  "$45,000",  "$130,000",  "32.1%"),
        ("Data Acquisition & Licensing",    "$18,000",  "$18,000",  "$20,000",   "$56,000",  "13.8%"),
        ("Software Dev Cost expensed",      "$10,200",  "$10,200",  "$11,400",   "$31,800",   "7.8%"),
        ("Research Contractors",            "$12,000",  "$12,000",  "$12,000",   "$36,000",   "8.9%"),
        ("Prototyping & Lab Materials",      "$1,200",   "$1,400",   "$1,600",    "$4,200",   "1.0%"),
    ]
    for i, r in enumerate(rows):
        d.tr(list(zip(r, [60, 24, 24, 24, 28, 14])), shade=(i % 2 == 0))
    d.set_font("Helvetica", "B", 8)
    d.cell(60, 6, "  TOTAL R&D SPEND")
    d.set_font("Helvetica", "B", 8)
    for v, w in [("$132,100", 24), ("$135,500", 24), ("$144,800", 24), ("$412,400", 28), ("100%", 14)]:
        d.cell(w, 6, v, align="L")
    d.ln()

    d.ln(4)
    d.section("R&D as % of Revenue")
    d.kv("Q1 2025 Revenue",         "$452,000")
    d.kv("R&D / Revenue",           "91.2%  (stage-appropriate for Series A AI company)")
    d.kv("Headcount in R&D",        "18 of 28 FTEs")
    d.ln(4)

    d.section("Accounting Notes")
    d.note(
        "All research and development costs are expensed as incurred in accordance with ASC 730. "
        "Development costs expensed include labor, cloud compute, and third-party data. "
        "Internal-use software costs under ASC 350-40 are evaluated separately; no "
        "capitalization threshold has been met in Q1 2025. R&D expenditure documentation "
        "maintained in Notion and Ramp expense system."
    )
    d.save("rd_expense_report_q1_2025.pdf")


# ── 6. SAFE Note Summary ──────────────────────────────────────────────────────

def safe_note_summary():
    d = Doc("SAFE Note & Convertible Instrument Summary", "As of March 31, 2025")
    d.kv("Legal Counsel",   "Gunderson Dettmer LLP")
    d.kv("Administrator",   "Carta")
    d.kv("Entity",          "Luminary AI, Inc. (Delaware C-Corp)")
    d.ln(4)

    d.section("Outstanding SAFE Notes -- Pre-Series A Seed Round")
    cols = [("Investor", 50), ("Principal", 24), ("Val. Cap", 24),
            ("Discount", 18), ("Date Signed", 24), ("Status", 34)]
    d.th(cols)
    rows = [
        ("Sequoia Scout Fund",      "$250,000",  "$8,000,000",  "20%", "Mar 14, 2023", "Converted -- Series A"),
        ("Y Combinator (SAFE)",     "$125,000",  "$8,000,000",  "20%", "Mar 14, 2023", "Converted -- Series A"),
        ("Pioneer Fund I",          "$200,000",  "$9,000,000",  "20%", "Jul 22, 2023", "Converted -- Series A"),
        ("Hustle Fund",             "$100,000",  "$8,500,000",  "20%", "Jul 22, 2023", "Converted -- Series A"),
        ("Angel -- K. Ramirez",       "$50,000",  "$8,000,000",  "20%", "Aug 3,  2023", "Converted -- Series A"),
        ("Angel -- T. Osei",          "$50,000",  "$8,000,000",  "20%", "Sep 18, 2023", "Converted -- Series A"),
    ]
    for i, r in enumerate(rows):
        d.tr(list(zip(r, [50, 24, 24, 18, 24, 34])), shade=(i % 2 == 0))

    d.ln(4)
    d.kv("Total SAFE Principal",      "$775,000")
    d.kv("Conversion Event",          "Series A Priced Round -- March 4, 2025")
    d.kv("Conversion Price",          "$1.82/share (post-discount)")
    d.kv("Shares Issued on Convert",  "425,824 shares of Series A Preferred")
    d.ln(4)

    d.section("Series A Priced Round Summary")
    d.kv("Lead Investor",         "Sequoia Capital (Series A)")
    d.kv("Round Size",            "$12,000,000")
    d.kv("Pre-Money Valuation",   "$40,000,000")
    d.kv("Price Per Share",       "$2.14 (Series A Preferred)")
    d.kv("New Shares Issued",     "5,607,476 shares of Series A Preferred")
    d.kv("Participating Investors", "Sequoia, Pioneer, Hustle, 3 angels")
    d.kv("Close Date",            "March 4, 2025")
    d.ln(4)

    d.section("Simple Agreement for Future Equity -- Accounting Notes")
    d.note(
        "All SAFE notes have been converted to Series A Preferred Stock as of the March 4, 2025 "
        "priced round closing. No SAFE instruments remain outstanding as of March 31, 2025. "
        "SAFE note agreements available via Carta. Conversion calculations reviewed by "
        "Gunderson Dettmer LLP prior to closing."
    )
    d.save("safe_note_summary.pdf")


# ── 7. Remote Employee Roster ─────────────────────────────────────────────────

def remote_employee_roster():
    d = Doc("Remote Employee Roster & State Summary", f"As of March 31, 2025")
    d.kv("Total Headcount",        "28 FTEs + 4 contractors")
    d.kv("Work Model",             "Remote-first (no physical office)")
    d.kv("PEO / Payroll",          "Gusto")
    d.ln(4)

    d.section("Employees by Home State")
    cols = [("State", 30), ("Headcount", 22), ("Departments", 60), ("Since", 30), ("Monthly Payroll", 32)]
    d.th(cols)
    rows = [
        ("California (CA)",     "10", "Eng, Sales, Ops, Mktg",   "Jan 2022", "$162,500"),
        ("Texas (TX)",           "6", "Eng, Sales, Data Science", "Mar 2022",  "$89,750"),
        ("New York (NY)",        "5", "Product, Marketing, Eng",  "Jun 2022",  "$77,500"),
        ("Florida (FL)",         "3", "Sales, Customer Success",  "Jan 2023",  "$37,083"),
        ("Colorado (CO)",        "2", "Eng, Data Science",        "Apr 2023",  "$46,167"),
        ("Washington (WA)",      "2", "Eng, Design",              "Sep 2023",  "$43,583"),
    ]
    for i, r in enumerate(rows):
        d.tr(list(zip(r, [30, 22, 60, 30, 32])), shade=(i % 2 == 0))

    d.ln(4)
    d.section("Headcount by Department")
    cols2 = [("Department", 50), ("Headcount", 22), ("Avg Salary", 28), ("Locations", 74)]
    d.th(cols2)
    rows2 = [
        ("Engineering",        "16", "$184,250", "CA, TX, NY, CO, WA"),
        ("Sales",               "5", "$137,000", "CA, TX, FL"),
        ("Product",             "2", "$175,000", "NY"),
        ("Marketing",           "2", "$130,000", "CA, NY"),
        ("Data Science",        "2", "$190,000", "TX, CO"),
        ("Design",              "1", "$155,000", "WA"),
    ]
    for i, r in enumerate(rows2):
        d.tr(list(zip(r, [50, 22, 28, 74])), shade=(i % 2 == 0))

    d.ln(4)
    d.section("Q1 Hiring Activity")
    d.kv("New Hires Q1",    "3 (2 engineers, 1 data scientist)")
    d.kv("Departures Q1",   "1 (voluntary)")
    d.kv("Net Headcount Change", "+2")
    d.ln(4)

    d.note(
        "All employees classified as W-2 employees. Home state determines payroll registration "
        "state. Employee moves tracked via Rippling HRIS; payroll state updated with each "
        "move. Contractor locations listed separately in Contractor Ledger."
    )
    d.save("remote_employee_roster_q1_2025.pdf")


# ── Run all ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Generating PDFs → {OUT}/")
    payroll_register()
    equity_grant_log()
    iso_exercise_log()
    contractor_ledger()
    rd_expense_report()
    safe_note_summary()
    remote_employee_roster()
    print("Done.")
