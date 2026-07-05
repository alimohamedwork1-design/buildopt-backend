from __future__ import annotations

import re
from io import BytesIO
from typing import Any, Dict, List, Tuple

import pandas as pd

HEADER_ALIASES: Dict[str, List[str]] = {
    "point_name": ["point name", "point_name", "tag", "point_tag", "point", "name", "tag name"],
    "point_type": ["type", "point type", "point_type", "object type", "equipment type"],
    "unit": ["unit", "units", "engineering unit", "eu"],
    "protocol_address": ["address", "bacnet", "modbus", "bacnet address", "modbus address", "object id", "instance"],
    "zone": ["zone", "area", "space"],
    "floor": ["floor", "level", "storey"],
    "name": ["building name", "name", "site name", "property name"],
    "address": ["address", "street", "location address"],
    "city": ["city", "emirate"],
    "country": ["country", "nation"],
    "total_area_sqm": ["area", "total area", "area sqm", "area_m2", "gfa", "total_area_sqm"],
    "floors": ["floors", "floor count", "number of floors", "levels"],
    "year_built": ["year built", "year_built", "construction year", "built"],
}


def _normalize_header(value: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(value).strip().lower())


def _match_column(columns: List[str], field: str) -> Tuple[str | None, str | None]:
    aliases = HEADER_ALIASES.get(field, [field])
    normalized = {_normalize_header(c): c for c in columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias], None
    for col in columns:
        ncol = _normalize_header(col)
        for alias in aliases:
            if alias in ncol or ncol in alias:
                return col, f"Fuzzy matched '{col}' → {field}"
    return None, None


def parse_building_excel(content: bytes) -> Dict[str, Any]:
    xl = pd.ExcelFile(BytesIO(content))
    sheet_names = xl.sheet_names

    building_meta: Dict[str, Any] = {}
    points: List[Dict[str, Any]] = []
    review: List[Dict[str, Any]] = []
    unmapped_columns: List[str] = []
    rows_processed = 0
    rows_imported = 0

    for sheet in sheet_names:
        df = xl.parse(sheet)
        if df.empty:
            continue
        df.columns = [str(c) for c in df.columns]
        rows_processed += len(df)

        sheet_lower = sheet.lower()
        is_points_sheet = any(k in sheet_lower for k in ("point", "tag", "equipment", "bms"))
        is_meta_sheet = any(k in sheet_lower for k in ("building", "site", "metadata", "property"))
        point_col, _ = _match_column(list(df.columns), "point_name")

        if is_meta_sheet or (not is_points_sheet and len(df) <= 3 and not point_col):
            for field in ("name", "address", "city", "country", "total_area_sqm", "floors", "year_built"):
                col, note = _match_column(list(df.columns), field)
                if col and not df[col].dropna().empty:
                    val = df[col].dropna().iloc[0]
                    building_meta[field if field != "name" else "name"] = val
                    if note:
                        review.append({"sheet": sheet, "note": note})
                elif col is None and field in ("name", "address"):
                    pass
            for col in df.columns:
                matched = any(_match_column([col], f)[0] for f in HEADER_ALIASES)
                if not matched:
                    unmapped_columns.append(f"{sheet}.{col}")

        if is_points_sheet or (point_col and not is_meta_sheet):
            col_map: Dict[str, str] = {}
            for field in ("point_name", "point_type", "unit", "protocol_address", "zone", "floor"):
                col, note = _match_column(list(df.columns), field)
                if col:
                    col_map[field] = col
                    if note:
                        review.append({"sheet": sheet, "note": note})
                elif field == "point_name":
                    review.append({"sheet": sheet, "note": f"Could not map point_name column in sheet '{sheet}'"})

            for col in df.columns:
                if col not in col_map.values():
                    unmapped_columns.append(f"{sheet}.{col}")

            if "point_name" not in col_map:
                continue

            for _, row in df.iterrows():
                pname = row.get(col_map["point_name"])
                if pd.isna(pname) or str(pname).strip() == "":
                    review.append({"sheet": sheet, "row": int(row.name) if hasattr(row, "name") else None, "note": "Skipped empty point_name"})
                    continue
                point: Dict[str, Any] = {
                    "point_name": str(pname).strip(),
                    "import_status": "imported",
                }
                for field, col in col_map.items():
                    if field == "point_name":
                        continue
                    val = row.get(col)
                    if not pd.isna(val):
                        point[field] = str(val).strip() if field != "point_type" else str(val).strip()
                points.append(point)
                rows_imported += 1

    return {
        "building_metadata": building_meta,
        "points": points,
        "summary": {
            "sheets": sheet_names,
            "rows_processed": rows_processed,
            "rows_imported": rows_imported,
            "points_count": len(points),
            "needs_review": review,
            "unmapped_columns": sorted(set(unmapped_columns)),
        },
    }
