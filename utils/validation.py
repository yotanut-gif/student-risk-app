from __future__ import annotations

import pandas as pd


def validate(df: pd.DataFrame) -> str | None:
    """ตรวจว่ารายการที่เลือก มส. ต้องมีจำนวนคาบที่ขาดมากกว่า 0"""
    if df.empty:
        return "ไม่พบข้อมูลนักเรียน"

    working_df = df.copy()
    working_df["absence_period"] = pd.to_numeric(
        working_df["absence_period"],
        errors="coerce",
    ).fillna(0)

    invalid_df = working_df[
        (working_df["is_no_right"] == True)
        & (working_df["absence_period"] <= 0)
    ]

    if not invalid_df.empty:
        return "กรุณาระบุจำนวนคาบที่ขาด"

    return None
