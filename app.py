from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


SHEET_ID = "1hDAtGtj4V31AuVLoiOPqFjq5LI3vXu6nUM48sJ6Lk8o"
STUDENT_SHEET_NAME = "Students"
ATTENDANCE_SHEET_NAME = "Attendance_Log"

REPORT_STATUSES = ["ขาด", "ลาป่วย", "ลากิจ", "มาสาย", "โดดเรียน"]
EXCLUDED_STATUSES = ["มา"]
LEVEL_OPTIONS = ["ทั้งหมด", "ม.1", "ม.2", "ม.3", "ม.4", "ม.5", "ม.6"]
MAX_ROOMS_BY_LEVEL = {
    "ม.1": 14,
    "ม.2": 13,
    "ม.3": 13,
    "ม.4": 14,
    "ม.5": 13,
    "ม.6": 13,
}
PERIOD_OPTIONS = ["ทั้งหมด", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
PUBLIC_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
    "?tqx=out:csv&sheet={sheet_name}"
)

STUDENT_REQUIRED_COLUMNS = ["ห้องเรียน", "เลขที่", "เลขประจำตัว", "ชื่อ-สกุล"]
ATTENDANCE_REQUIRED_COLUMNS = [
    "timestamp",
    "date",
    "day",
    "level",
    "classroom",
    "student_id",
    "student_name",
    "periods",
    "status",
    "teacher_username",
    "teacher_name",
    "note",
]

DISPLAY_COLUMNS = [
    "วันที่",
    "วัน",
    "คาบที่เลือก",
    "ระดับชั้น",
    "ห้องเรียน",
    "เลขที่",
    "เลขประจำตัว",
    "ชื่อ-สกุล",
    "สถานะ",
    "หมายเหตุ",
]


class SheetConfigurationError(Exception):
    """Raised when Google Sheets data is missing required structure."""


def normalize_id(value: Any) -> str:
    """Convert IDs from Sheets to stable string values without trailing .0."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        return text[:-2]
    return text


def validate_columns(df: pd.DataFrame, required: list[str], sheet_name: str) -> None:
    """Validate that a dataframe contains all required columns."""
    missing = [column for column in required if column not in df.columns]
    if missing:
        missing_text = ", ".join(missing)
        raise SheetConfigurationError(
            f"ชีต {sheet_name} ขาดคอลัมน์สำคัญ: {missing_text}"
        )


@st.cache_data(ttl=300, show_spinner="กำลังโหลดข้อมูลจาก Google Sheets...")
def load_google_sheet() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read Students and Attendance_Log sheets as pandas DataFrames.

    If service account secrets exist, the app uses them. Otherwise it reads from
    the public CSV endpoint, which works when the Google Sheet is shared as
    Anyone with the link can view.
    """
    if "gcp_service_account" not in st.secrets:
        students_url = PUBLIC_CSV_URL.format(
            sheet_id=SHEET_ID,
            sheet_name=STUDENT_SHEET_NAME,
        )
        attendance_url = PUBLIC_CSV_URL.format(
            sheet_id=SHEET_ID,
            sheet_name=ATTENDANCE_SHEET_NAME,
        )
        try:
            return pd.read_csv(students_url), pd.read_csv(attendance_url)
        except Exception as exc:
            raise SheetConfigurationError(
                "ไม่พบค่า [gcp_service_account] ใน .streamlit/secrets.toml "
                "และยังอ่าน Google Sheet แบบ public ไม่ได้ กรุณาแชร์ชีตเป็น "
                "'ทุกคนที่มีลิงก์ดูได้' หรือใส่ Service Account secrets"
            ) from exc

    credentials = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SCOPES,
    )
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(SHEET_ID)

    try:
        students_sheet = spreadsheet.worksheet(STUDENT_SHEET_NAME)
    except gspread.WorksheetNotFound as exc:
        raise SheetConfigurationError(
            f"ไม่พบชีต {STUDENT_SHEET_NAME}"
        ) from exc

    try:
        attendance_sheet = spreadsheet.worksheet(ATTENDANCE_SHEET_NAME)
    except gspread.WorksheetNotFound as exc:
        raise SheetConfigurationError(
            f"ไม่พบชีต {ATTENDANCE_SHEET_NAME}"
        ) from exc

    students_df = pd.DataFrame(students_sheet.get_all_records())
    attendance_df = pd.DataFrame(attendance_sheet.get_all_records())
    return students_df, attendance_df


def prepare_data(
    students_df: pd.DataFrame,
    attendance_df: pd.DataFrame,
) -> pd.DataFrame:
    """Clean, merge, and keep only abnormal attendance statuses."""
    validate_columns(students_df, STUDENT_REQUIRED_COLUMNS, STUDENT_SHEET_NAME)
    validate_columns(attendance_df, ATTENDANCE_REQUIRED_COLUMNS, ATTENDANCE_SHEET_NAME)

    students = students_df.copy()
    attendance = attendance_df.copy()

    students["เลขประจำตัว"] = students["เลขประจำตัว"].apply(normalize_id)
    students["ห้องเรียน"] = students["ห้องเรียน"].astype(str).str.strip()
    students["เลขที่"] = pd.to_numeric(students["เลขที่"], errors="coerce")

    attendance["student_id"] = attendance["student_id"].apply(normalize_id)
    attendance["classroom"] = attendance["classroom"].astype(str).str.strip()
    attendance["date"] = pd.to_datetime(
        attendance["date"],
        errors="coerce",
    ).dt.date
    attendance["status"] = attendance["status"].astype(str).str.strip()
    attendance["note"] = attendance["note"].replace("", pd.NA).fillna("-")

    merged = attendance.merge(
        students[["ห้องเรียน", "เลขที่", "เลขประจำตัว", "ชื่อ-สกุล"]],
        how="left",
        left_on=["student_id", "classroom"],
        right_on=["เลขประจำตัว", "ห้องเรียน"],
    )
    merged = merged.drop(columns=["ห้องเรียน"])

    merged = merged[merged["status"].isin(REPORT_STATUSES)].copy()
    merged = merged[~merged["status"].isin(EXCLUDED_STATUSES)].copy()
    return merged


def period_matches(periods: Any, selected_period: str) -> bool:
    """Return True when selected period exists as an exact comma-separated item."""
    if selected_period == "ทั้งหมด":
        return True
    period_items = str(periods).replace(" ", "").split(",")
    return selected_period in period_items


def apply_selected_filters(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Filter data with all saved filter conditions."""
    result_frames: list[pd.DataFrame] = []
    no_data_messages: list[str] = []

    for condition in st.session_state.filters:
        selected_date = condition["date"]
        selected_level = condition.get("level", "ทั้งหมด")
        selected_classroom = condition.get("classroom", "ทั้งหมด")
        selected_period = condition["period"]

        condition_data = data[
            data["date"] == selected_date
        ].copy()

        if selected_level != "ทั้งหมด":
            condition_data = condition_data[
                condition_data["level"].astype(str).str.strip() == selected_level
            ].copy()

        if selected_classroom != "ทั้งหมด":
            condition_data = condition_data[
                condition_data["classroom"].astype(str).str.strip() == selected_classroom
            ].copy()

        if selected_period != "ทั้งหมด":
            condition_data = condition_data[
                condition_data["periods"].apply(
                    lambda value: period_matches(value, selected_period)
                )
            ].copy()

        if condition_data.empty:
            no_data_messages.append(
                f"วันที่ {selected_date.strftime('%d/%m/%Y')} ไม่มีการบันทึกข้อมูล"
            )
            continue

        condition_data["selected_period"] = selected_period
        result_frames.append(condition_data)

    if not result_frames:
        return pd.DataFrame(), no_data_messages

    return pd.concat(result_frames, ignore_index=True), no_data_messages


def to_display_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """Convert internal columns to Thai report columns."""
    if data.empty:
        return pd.DataFrame(columns=DISPLAY_COLUMNS)

    report = data.copy()
    report = report.sort_values(
        by=["level", "classroom", "เลขที่"],
        na_position="last",
        kind="stable",
    )
    report["วันที่"] = report["date"].apply(
        lambda value: value.strftime("%d/%m/%Y") if pd.notna(value) else "-"
    )
    report["หมายเหตุ"] = report["note"].replace("", pd.NA).fillna("-")
    report["เลขที่"] = report["เลขที่"].apply(
        lambda value: str(int(value)) if pd.notna(value) else "-"
    )

    renamed = report.rename(
        columns={
            "day": "วัน",
            "selected_period": "คาบที่เลือก",
            "level": "ระดับชั้น",
            "classroom": "ห้องเรียน",
            "เลขที่": "เลขที่",
            "เลขประจำตัว": "เลขประจำตัว",
            "ชื่อ-สกุล": "ชื่อ-สกุล",
            "status": "สถานะ",
        }
    )
    return renamed[DISPLAY_COLUMNS]


def filter_by_search(data: pd.DataFrame, search_text: str) -> pd.DataFrame:
    """Search by student name, student ID, or classroom."""
    if not search_text.strip() or data.empty:
        return data

    keyword = search_text.strip()
    mask = (
        data["ชื่อ-สกุล"].astype(str).str.contains(keyword, case=False, na=False)
        | data["เลขประจำตัว"].astype(str).str.contains(keyword, case=False, na=False)
        | data["ห้องเรียน"].astype(str).str.contains(keyword, case=False, na=False)
    )
    return data[mask].copy()


def style_status(data: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Apply background colors to attendance status cells."""
    colors = {
        "ขาด": "background-color: #ffd6d6",
        "ลาป่วย": "background-color: #fff3bf",
        "ลากิจ": "background-color: #fff3bf",
        "มาสาย": "background-color: #ffd8a8",
        "โดดเรียน": "background-color: #f783ac; color: #4a001f",
    }

    def apply_color(value: str) -> str:
        return colors.get(value, "")

    return data.style.map(apply_color, subset=["สถานะ"])


def build_excel(data: pd.DataFrame) -> bytes:
    """Build an Excel file in memory for download."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name="Attendance Report")
    return output.getvalue()


def get_classroom_options(selected_level: str) -> list[str]:
    """Build fixed classroom choices for the selected level."""
    if selected_level == "ทั้งหมด":
        classrooms = [
            f"{level}/{room}"
            for level, max_room in MAX_ROOMS_BY_LEVEL.items()
            for room in range(1, max_room + 1)
        ]
        return ["ทั้งหมด", *classrooms]

    max_room = MAX_ROOMS_BY_LEVEL[selected_level]
    classrooms = [f"{selected_level}/{room}" for room in range(1, max_room + 1)]
    return ["ทั้งหมด", *classrooms]


def render_sidebar() -> None:
    """Render filter controls and refresh actions."""
    st.sidebar.header("ตัวกรองรายงาน")

    if "filters" not in st.session_state:
        st.session_state.filters = []

    selected_date = st.sidebar.date_input("วันที่", value=date.today())
    selected_level = st.sidebar.selectbox("ระดับชั้น", LEVEL_OPTIONS)
    classroom_options = get_classroom_options(selected_level)
    selected_classroom = st.sidebar.selectbox("ห้องเรียน", classroom_options)
    selected_period = st.sidebar.selectbox("คาบเรียน", PERIOD_OPTIONS)

    if st.sidebar.button("เพิ่มรายการ", type="primary", use_container_width=True):
        st.session_state.filters.append(
            {
                "date": selected_date,
                "level": selected_level,
                "classroom": selected_classroom,
                "period": selected_period,
            }
        )
        st.rerun()

    if st.sidebar.button("ล้างรายการทั้งหมด", use_container_width=True):
        st.session_state.filters = []
        st.rerun()

    st.sidebar.divider()

    if st.sidebar.button("โหลดข้อมูลล่าสุด", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


def render_selected_conditions() -> None:
    """Display all selected filter conditions."""
    st.subheader("รายการเงื่อนไขที่เลือก")
    if not st.session_state.filters:
        st.info("ยังไม่มีรายการ กรุณาเลือกวันที่ ระดับชั้น ห้องเรียน และคาบ แล้วกดเพิ่มรายการ")
        return

    conditions = pd.DataFrame(
        [
            {
                "วันที่": item["date"].strftime("%d/%m/%Y"),
                "ระดับชั้น": item.get("level", "ทั้งหมด"),
                "ห้องเรียน": item.get("classroom", "ทั้งหมด"),
                "คาบ": item["period"],
            }
            for item in st.session_state.filters
        ]
    )
    st.dataframe(conditions, use_container_width=True, hide_index=True)


def render_kpis(report: pd.DataFrame) -> None:
    """Render KPI metrics above the report table."""
    unique_students = int(report["เลขประจำตัว"].nunique()) if not report.empty else 0
    unique_classrooms = int(report["ห้องเรียน"].nunique()) if not report.empty else 0
    unique_levels = int(report["ระดับชั้น"].nunique()) if not report.empty else 0

    metric_values = [
        ("จำนวนรายการค้นหา", int(len(st.session_state.filters))),
        ("จำนวนนักเรียนในรายงาน", unique_students),
        ("จำนวนห้องเรียน", unique_classrooms),
        ("จำนวนระดับชั้น", unique_levels),
        ("จำนวนขาด", int((report["สถานะ"] == "ขาด").sum()) if not report.empty else 0),
        (
            "จำนวนลาป่วย",
            int((report["สถานะ"] == "ลาป่วย").sum()) if not report.empty else 0,
        ),
        (
            "จำนวนลากิจ",
            int((report["สถานะ"] == "ลากิจ").sum()) if not report.empty else 0,
        ),
        (
            "จำนวนมาสาย",
            int((report["สถานะ"] == "มาสาย").sum()) if not report.empty else 0,
        ),
        (
            "จำนวนโดดเรียน",
            int((report["สถานะ"] == "โดดเรียน").sum()) if not report.empty else 0,
        ),
    ]

    for row_start in range(0, len(metric_values), 5):
        columns = st.columns(5)
        for column, (label, value) in zip(columns, metric_values[row_start:row_start + 5]):
            column.metric(label, int(value))


def render_grouped_view(report: pd.DataFrame) -> None:
    """Render grouped view by date and classroom."""
    with st.expander("มุมมองจัดกลุ่มตามวันที่และห้องเรียน"):
        if report.empty:
            st.info("ไม่มีข้อมูลสำหรับแสดงแบบจัดกลุ่ม")
            return

        for report_date, date_group in report.groupby("วันที่", sort=False):
            st.markdown(f"**วันที่ {report_date}**")
            for classroom, room_group in date_group.groupby("ห้องเรียน", sort=False):
                st.markdown(f"**{classroom}**")
                sorted_room = room_group.sort_values("เลขที่", na_position="last")
                for _, row in sorted_room.iterrows():
                    st.write(
                        f"เลขที่ {row['เลขที่']} {row['ชื่อ-สกุล']} "
                        f"({row['สถานะ']})"
                    )


def render_downloads(report: pd.DataFrame) -> None:
    """Render CSV and Excel download buttons."""
    csv_data = report.to_csv(index=False).encode("utf-8-sig")
    excel_data = build_excel(report)

    left, right = st.columns(2)
    left.download_button(
        "ดาวน์โหลด CSV",
        data=csv_data,
        file_name="attendance_report.csv",
        mime="text/csv",
        use_container_width=True,
    )
    right.download_button(
        "ดาวน์โหลด Excel (.xlsx)",
        data=excel_data,
        file_name="attendance_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def main() -> None:
    """Run the Streamlit attendance report app."""
    st.set_page_config(
        page_title="ระบบรายงานขาด ลา มาสาย และโดดเรียนของนักเรียน",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("ระบบรายงานขาด ลา มาสาย และโดดเรียนของนักเรียน")

    try:
        students_df, attendance_df = load_google_sheet()
        prepared_data = prepare_data(students_df, attendance_df)
    except SheetConfigurationError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error("ไม่สามารถเชื่อมต่อ Google Sheets ได้")
        st.exception(exc)
        return

    render_sidebar()
    render_selected_conditions()

    if not st.session_state.filters:
        return

    filtered_data, no_data_messages = apply_selected_filters(prepared_data)
    for message in no_data_messages:
        st.warning(message)

    search_text = st.text_input("ค้นหา", placeholder="ชื่อ-สกุล, เลขประจำตัว, ห้องเรียน")
    report = to_display_dataframe(filtered_data)
    report = filter_by_search(report, search_text)

    st.subheader("สรุปรายงาน")
    render_kpis(report)

    if report.empty:
        st.info("ไม่พบข้อมูลตามเงื่อนไขที่เลือก")
        return

    st.subheader("ตารางผลลัพธ์")
    st.dataframe(style_status(report), use_container_width=True, hide_index=True)
    render_grouped_view(report)
    render_downloads(report)


if __name__ == "__main__":
    main()
