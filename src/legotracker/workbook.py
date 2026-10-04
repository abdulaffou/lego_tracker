"""The spreadsheet attached to every email.

Two sheets, meant to be opened and understood without reading anything
else: Today is what to do right now, History is every price we have
ever seen.
"""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

FONT = "Arial"
RUPEES = '"₹"#,##0'
PERCENT = '0.0%;[Red]-0.0%;-'

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=11)

# One colour per verdict, so the sheet reads at a glance.
VERDICT_FILL = {
    "BUY_NOW": PatternFill("solid", fgColor="C6EFCE"),   # green
    "GOOD": PatternFill("solid", fgColor="D9EAD3"),      # pale green
    "FAIR": PatternFill("solid", fgColor="FFF2CC"),      # amber
    "WAIT": PatternFill("solid", fgColor="F4CCCC"),      # red
    "NEVER_DISCOUNTS": PatternFill("solid", fgColor="EFEFEF"),
}
VERDICT_TEXT = {
    "BUY_NOW": "BUY NOW", "GOOD": "GOOD", "FAIR": "FAIR",
    "WAIT": "WAIT", "NEVER_DISCOUNTS": "never discounts",
}

TODAY_HEADERS = ["Set", "Name", "Verdict", "Best price", "Shop", "Off MRP",
                 "MRP", "Why", "In stock", "Shops", "Days tracked", "Link"]
HISTORY_HEADERS = ["Date", "Set", "Name", "Shop", "Price", "MRP",
                   "In stock", "Suspect", "Source", "Link"]


def _write_header(sheet, headers):
    for column, title in enumerate(headers, start=1):
        cell = sheet.cell(1, column, title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    sheet.row_dimensions[1].height = 22


def _fit_columns(sheet, headers, widths):
    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(column)].width = width


def _link(cell, url):
    if url:
        cell.hyperlink = url
        cell.font = Font(name=FONT, color="0563C1", underline="single")


def _build_today(sheet, items):
    _write_header(sheet, TODAY_HEADERS)
    for index, entry in enumerate(items):
        line = index + 2
        verdict = entry["verdict"]
        values = [
            entry["set_number"], entry["name"],
            VERDICT_TEXT.get(verdict.label, verdict.label),
            entry["price"], entry["shop"],
            None,                       # Off MRP: a formula, set below
            entry.get("mrp"), verdict.reason,
            "yes" if entry.get("in_stock", True) else "NO",
            entry.get("sources"), entry.get("history_days"), "open shop",
        ]
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(line, column, value)
            cell.font = Font(name=FONT)
            cell.alignment = Alignment(vertical="center")

        # A formula, not a computed number, so editing a price in column D
        # updates the saving straight away.
        sheet.cell(line, 6).value = (
            f'=IFERROR(IF(G{line}=0,"",(G{line}-D{line})/G{line}),"")')
        sheet.cell(line, 6).number_format = PERCENT
        for column in (4, 7):
            sheet.cell(line, column).number_format = RUPEES
        verdict_cell = sheet.cell(line, 3)
        verdict_cell.fill = VERDICT_FILL.get(verdict.label,
                                             VERDICT_FILL["NEVER_DISCOUNTS"])
        verdict_cell.font = Font(name=FONT, bold=True)
        sheet.cell(line, 8).alignment = Alignment(vertical="center",
                                                  wrap_text=True)
        _link(sheet.cell(line, 12), entry.get("url"))
    _fit_columns(sheet, TODAY_HEADERS,
                 [9, 22, 16, 13, 11, 9, 12, 46, 9, 7, 12, 11])


def _build_history(sheet, history, names):
    _write_header(sheet, HISTORY_HEADERS)
    # prices.csv holds the whole catalogue because the retirement signal
    # needs it. This sheet is for reading, so it holds only your sets.
    mine = [r for r in history if r.set_number in names]
    # One reading per shop per day; a later run supersedes an earlier one.
    deduped = {(r.date, r.shop, r.set_number): r for r in mine}
    ordered = sorted(deduped.values(),
                     key=lambda r: (r.date, r.set_number, r.shop),
                     reverse=True)
    for index, record in enumerate(ordered):
        line = index + 2
        values = [record.date, record.set_number,
                  names.get(record.set_number, ""), record.shop,
                  record.price, record.mrp,
                  "yes" if record.in_stock else "NO",
                  "YES" if record.suspect else "",
                  record.source, "open shop"]
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(line, column, value)
            cell.font = Font(name=FONT)
        for column in (5, 6):
            sheet.cell(line, column).number_format = RUPEES
        if record.suspect:
            # Recorded for the record, never trusted for a verdict.
            for column in range(1, len(HISTORY_HEADERS) + 1):
                sheet.cell(line, column).fill = VERDICT_FILL["WAIT"]
        _link(sheet.cell(line, 10), record.url)
    _fit_columns(sheet, HISTORY_HEADERS,
                 [12, 9, 22, 11, 12, 12, 9, 9, 9, 11])


def build_workbook(path, items, history, today) -> str:
    """Write the two-sheet workbook and return its path."""
    names = {i["set_number"]: i["name"] for i in items}
    book = Workbook()
    _build_today(book.active, items)
    book.active.title = "Today"
    _build_history(book.create_sheet("History"), history, names)
    book.save(path)
    return str(path)
