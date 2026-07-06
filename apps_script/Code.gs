const SPREADSHEET_ID = '1MaAuR3nOa2405k5lRhnIe_vSes7GkGp4RY8yIamhVSg';

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);

    if (payload.action === 'load_students') {
      return jsonResponse(loadStudents(payload.grade, payload.room));
    }

    if (payload.action === 'save_no_right') {
      saveNoRight(payload.rows || []);
      return jsonResponse({ ok: true });
    }

    return jsonResponse({ ok: false, error: 'Unknown action' });
  } catch (error) {
    return jsonResponse({ ok: false, error: String(error) });
  }
}

function loadStudents(grade, room) {
  const sheet = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName('student');
  const values = sheet.getDataRange().getValues();

  if (values.length < 2) {
    return { ok: true, students: [] };
  }

  const headers = values[0].map(String);
  const rows = values.slice(1);
  const gradeNumber = String(grade).replace('ม.', '').trim();
  const roomValue = `${gradeNumber}/${room}`;

  const students = rows
    .map((row) => rowToObject(headers, row))
    .filter((student) => String(student.room).trim() === roomValue)
    .map((student) => ({
      no: student.no,
      student_id: student.student_id,
      fullname: student.fullname,
      room: student.room,
    }));

  return { ok: true, students };
}

function saveNoRight(rows) {
  if (!rows.length) {
    return;
  }

  const sheet = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName('no_right');
  const values = rows.map((row) => [
    row.timestamp,
    row.grade,
    row.room,
    row.subject_code,
    row.subject_name,
    row.student_id,
    row.fullname,
    row.absence_period,
  ]);

  sheet
    .getRange(sheet.getLastRow() + 1, 1, values.length, values[0].length)
    .setValues(values);
}

function rowToObject(headers, row) {
  return headers.reduce((result, header, index) => {
    result[header] = row[index];
    return result;
  }, {});
}

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
