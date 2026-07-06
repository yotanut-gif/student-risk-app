# Student At-Risk Reporting System

เว็บแอป Streamlit สำหรับรายงานนักเรียนที่เสี่ยงติด มส. โดยอ่านรายชื่อนักเรียนจาก Google Sheet และบันทึกข้อมูลลง Sheet `no_right` ผ่าน Google Apps Script Web App

วิธีนี้ไม่ต้องใช้ Google Cloud Billing, ไม่ต้องใช้ Service Account และไม่ต้องใช้ไฟล์ `credentials.json`

## โครงสร้างโปรเจกต์

```text
student-risk-app/
├── app.py
├── requirements.txt
├── README.md
├── .streamlit/
│   └── secrets.toml
├── apps_script/
│   └── Code.gs
└── utils/
    ├── google_sheet.py
    └── validation.py
```

## Google Sheet

Spreadsheet:

https://docs.google.com/spreadsheets/d/1MaAuR3nOa2405k5lRhnIe_vSes7GkGp4RY8yIamhVSg

ต้องมี Sheet อย่างน้อย:

- `student`
- `no_right`

Sheet `student` ต้องมี Columns:

```text
no, student_id, fullname, room
```

ค่าในคอลัมน์ `room` ใช้รูปแบบ `ระดับ/ห้อง` เช่น:

```text
1/1
1/2
2/3
```

Sheet `no_right` ควรมี Columns:

```text
timestamp, class, subject_code, subject_name, student_id, fullname, absence_period
```

## ตั้งค่า Google Apps Script

1. เปิด Google Sheet
2. ไปที่ `Extensions` > `Apps Script`
3. ลบโค้ดเดิมในไฟล์ `Code.gs`
4. คัดลอกโค้ดจากไฟล์ `apps_script/Code.gs` ไปวาง
5. กด Save
6. กด `Deploy` > `New deployment`
7. เลือก Type เป็น `Web app`
8. ตั้งค่า:

```text
Execute as: Me
Who has access: Anyone
```

9. กด `Deploy`
10. อนุญาตสิทธิ์ตามหน้าจอของ Google
11. คัดลอก `Web app URL`

## ตั้งค่า Streamlit Secrets

เปิดไฟล์:

```text
.streamlit/secrets.toml
```

ใส่ URL จาก Apps Script:

```toml
[apps_script]
url = "https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec"
```

เมื่อนำขึ้น Streamlit Community Cloud ให้เอาค่านี้ไปใส่ในหน้า Secrets ของแอปด้วย

## รันบนเครื่อง

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy บน Streamlit Community Cloud

1. Push โฟลเดอร์นี้ขึ้น GitHub
2. เข้า Streamlit Community Cloud แล้วเลือก repository
3. ตั้งค่า Main file path เป็น `app.py`
4. เพิ่มค่า Secrets:

```toml
[apps_script]
url = "https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec"
```

5. กด Deploy

## การทำงานของแอป

- เลือกระดับชั้นและห้องเรียน
- กรอกรหัสวิชาและชื่อรายวิชา
- กด `โหลดรายชื่อนักเรียน`
- ระบบจะค้นหา `room` เช่น เลือก `ม.1` ห้อง `1` จะค้นหา `1/1`
- เลือกนักเรียนที่เสี่ยงติด มส. และกรอกจำนวนคาบที่ขาด
- กด `บันทึกข้อมูล`

หากเลือก `มส.` แต่ไม่กรอกจำนวนคาบที่ขาดมากกว่า 0 ระบบจะแสดงข้อความ `กรุณาระบุจำนวนคาบที่ขาด`
