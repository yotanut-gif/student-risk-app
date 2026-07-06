from __future__ import annotations

from typing import Any

import pandas as pd
import requests
import streamlit as st


STUDENT_COLUMNS = ["no", "student_id", "fullname", "room"]
SAVE_COLUMNS = [
    "timestamp",
    "class",
    "subject_code",
    "subject_name",
    "student_id",
    "fullname",
    "absence_period",
]
EMPTY_STUDENTS_COLUMNS = ["no", "student_id", "fullname", "is_no_right", "absence_period"]


class GoogleSheetConnectionError(Exception):
    """ข้อผิดพลาดเมื่อเชื่อมต่อ Google Sheet ไม่สำเร็จ"""


def connect_sheet() -> str:
    """อ่าน Apps Script Web App URL จาก st.secrets"""
    try:
        return str(st.secrets["apps_script"]["url"]).strip()
    except Exception as exc:
        raise GoogleSheetConnectionError from exc


def _post_to_apps_script(payload: dict[str, Any]) -> dict[str, Any]:
    """ส่งคำสั่งไปยัง Apps Script Web App"""
    url = connect_sheet()
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise GoogleSheetConnectionError from exc

    if not data.get("ok"):
        raise GoogleSheetConnectionError(data.get("error", "Apps Script error"))

    return data


def load_students(grade: str, room: int) -> pd.DataFrame:
    """อ่านรายชื่อนักเรียนจาก Sheet student ผ่าน Apps Script"""
    data = _post_to_apps_script(
        {
            "action": "load_students",
            "grade": grade,
            "room": room,
        }
    )

    students_df = pd.DataFrame(data.get("students", []))
    if students_df.empty:
        return pd.DataFrame(columns=EMPTY_STUDENTS_COLUMNS)

    missing_columns = [column for column in STUDENT_COLUMNS if column not in students_df.columns]
    if missing_columns:
        return pd.DataFrame(columns=EMPTY_STUDENTS_COLUMNS)

    filtered_df = students_df[["no", "student_id", "fullname"]].copy()
    filtered_df["no"] = filtered_df["no"].astype(str)
    filtered_df["student_id"] = filtered_df["student_id"].astype(str)
    filtered_df["fullname"] = filtered_df["fullname"].astype(str)
    filtered_df["is_no_right"] = False
    filtered_df["absence_period"] = 0

    return filtered_df.reset_index(drop=True)


def save_to_sheet(df: pd.DataFrame) -> None:
    """บันทึกข้อมูลลง Sheet no_right ผ่าน Apps Script โดยไม่เขียนทับข้อมูลเดิม"""
    save_df = df[SAVE_COLUMNS].copy()
    save_df["absence_period"] = save_df["absence_period"].astype(int)

    _post_to_apps_script(
        {
            "action": "save_no_right",
            "rows": save_df.astype(str).to_dict(orient="records"),
        }
    )
