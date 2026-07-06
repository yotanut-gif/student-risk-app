from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from utils.google_sheet import GoogleSheetConnectionError, load_students, save_to_sheet
from utils.validation import validate


GRADES: list[str] = ["ม.1", "ม.2", "ม.3", "ม.4", "ม.5", "ม.6"]
ROOMS: list[int] = list(range(1, 21))


def setup_page() -> None:
    """ตั้งค่าหน้าเว็บให้เป็นหน้าเดียวและไม่มี Sidebar"""
    st.set_page_config(
        page_title="รายงานนักเรียนเสี่ยงติด มส.",
        page_icon="📋",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
            [data-testid="stSidebar"],
            [data-testid="collapsedControl"] {
                display: none;
            }
            .block-container {
                max-width: 980px;
                padding-top: 2rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_session_state() -> None:
    """เตรียมค่าเริ่มต้นใน session_state"""
    if "students_df" not in st.session_state:
        st.session_state.students_df = pd.DataFrame()
    if "loaded_grade" not in st.session_state:
        st.session_state.loaded_grade = None
    if "loaded_room" not in st.session_state:
        st.session_state.loaded_room = None
    if "save_success" not in st.session_state:
        st.session_state.save_success = False
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0


def build_editable_table(students_df: pd.DataFrame) -> pd.DataFrame:
    """สร้างตารางแก้ไขข้อมูล มส. และจำนวนคาบที่ขาด"""
    table_height = min(900, 38 + (len(students_df) + 1) * 35)

    display_df = students_df.rename(
        columns={
            "no": "เลขที่",
            "student_id": "เลขประจำตัว",
            "fullname": "ชื่อ-นามสกุล",
            "is_no_right": "มส.",
            "absence_period": "จำนวนคาบที่ขาด",
        }
    )

    edited_df = st.data_editor(
        display_df,
        key=f"student_editor_{st.session_state.editor_version}",
        use_container_width=True,
        hide_index=True,
        height=table_height,
        disabled=["เลขที่", "เลขประจำตัว", "ชื่อ-นามสกุล"],
        column_config={
            "เลขที่": st.column_config.TextColumn("เลขที่"),
            "เลขประจำตัว": st.column_config.TextColumn("เลขประจำตัว"),
            "ชื่อ-นามสกุล": st.column_config.TextColumn("ชื่อ-นามสกุล"),
            "มส.": st.column_config.CheckboxColumn("มส.", default=False),
            "จำนวนคาบที่ขาด": st.column_config.NumberColumn(
                "จำนวนคาบที่ขาด",
                min_value=0,
                step=1,
                format="%d",
            ),
        },
    )

    return edited_df.rename(
        columns={
            "เลขที่": "no",
            "เลขประจำตัว": "student_id",
            "ชื่อ-นามสกุล": "fullname",
            "มส.": "is_no_right",
            "จำนวนคาบที่ขาด": "absence_period",
        }
    )


def reload_students(grade: str, room: int) -> None:
    """โหลดรายชื่อนักเรียนจาก Google Sheet"""
    try:
        students_df = load_students(grade, room)
    except GoogleSheetConnectionError:
        st.error("ไม่สามารถเชื่อมต่อ Google Sheet ได้")
        return

    if students_df.empty:
        st.session_state.students_df = pd.DataFrame()
        st.session_state.editor_version += 1
        st.warning("ไม่พบข้อมูลนักเรียน")
        return

    st.session_state.students_df = students_df
    st.session_state.loaded_grade = grade
    st.session_state.loaded_room = room
    st.session_state.editor_version += 1


def main() -> None:
    setup_page()
    ensure_session_state()

    st.title("รายงานนักเรียนเสี่ยงติด มส.")
    if st.session_state.save_success:
        st.success("บันทึกข้อมูลสำเร็จ")
        st.session_state.save_success = False

    grade = st.selectbox("ระดับชั้น", GRADES)
    room = st.selectbox("ห้องเรียน", ROOMS)
    subject_code = st.text_input("รหัสวิชา", placeholder="ว21101")
    subject_name = st.text_input("ชื่อรายวิชา", placeholder="วิทยาศาสตร์1")
    teacher = st.text_input("ครูผู้สอน", placeholder="นายใจดี ดีใจ")

    if st.button("โหลดรายชื่อนักเรียน", type="primary"):
        reload_students(grade, room)

    if st.session_state.students_df.empty:
        return

    edited_df = build_editable_table(st.session_state.students_df)

    if st.button("บันทึกข้อมูล"):
        if st.session_state.loaded_grade != grade or st.session_state.loaded_room != room:
            st.warning("กรุณาโหลดรายชื่อนักเรียนใหม่")
            return

        error_message = validate(edited_df)
        if error_message:
            st.error(error_message)
            return

        selected_df = edited_df[edited_df["is_no_right"] == True].copy()
        if selected_df.empty:
            st.warning("กรุณาเลือกนักเรียนที่เสี่ยงติด มส.")
            return

        selected_df["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        selected_df["class"] = f"{grade}/{room}"
        selected_df["subject_code"] = subject_code.strip()
        selected_df["subject_name"] = subject_name.strip()
        selected_df["teacher"] = teacher.strip()

        try:
            save_to_sheet(selected_df)
        except GoogleSheetConnectionError:
            st.error("ไม่สามารถเชื่อมต่อ Google Sheet ได้")
            return

        st.session_state.save_success = True
        reload_students(grade, room)
        st.rerun()


if __name__ == "__main__":
    main()
