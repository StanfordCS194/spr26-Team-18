from io import BytesIO, StringIO

import pandas as pd
from pypdf import PdfReader


def extract_text(uploaded_file) -> str:
    name = (getattr(uploaded_file, "name", "") or "").lower()
    data = uploaded_file.read()

    if name.endswith(".txt"):
        return data.decode("utf-8", errors="replace")

    if name.endswith(".csv"):
        df = pd.read_csv(StringIO(data.decode("utf-8", errors="replace")))
        return _dataframe_to_text(df, name)

    if name.endswith((".xlsx", ".xls")):
        excel = pd.ExcelFile(BytesIO(data))
        parts = []
        for sheet in excel.sheet_names:
            df = excel.parse(sheet)
            parts.append(f"Sheet: {sheet}\n{_dataframe_to_text(df, name)}")
        return "\n\n".join(parts)

    reader = PdfReader(BytesIO(data))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _dataframe_to_text(df: pd.DataFrame, source_name: str) -> str:
    """Convert a DataFrame to a readable text representation for LLM analysis."""
    df = df.dropna(how="all").dropna(axis=1, how="all")
    lines = [f"Columns: {', '.join(str(c) for c in df.columns)}"]
    for _, row in df.iterrows():
        pairs = [f"{col}: {val}" for col, val in row.items() if pd.notna(val)]
        if pairs:
            lines.append(" | ".join(pairs))
    return "\n".join(lines)
