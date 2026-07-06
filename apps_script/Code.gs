const SPREADSHEET_ID = '1MaAuR3nOa2405k5lRhnIe_vSes7GkGp4RY8yIamhVSg';

function doGet() {
  try {
    return jsonResponse({
      ok: true,
      debug: getDebugInfo(),
    });
  } catch (error) {
    return jsonResponse({ ok: false, error: String(error) });
  }
}

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
  const sheet = getSpreadsheet().getSheetByName('student');
  const values = sheet.getDataRange().getDisplayValues();

  if (values.length < 2) {
    return { ok: true, students: [] };
  }

  const headers = values[0].map(String);
  const rows = values.slice(1);
  const gradeNumber = String(grade).replace('ม.', '').trim();
  const roomValue = normalizeRoom(`${gradeNumber}/${room}`);

  const students = rows
    .map((row) => rowToObject(headers, row))
    .filter((student) => normalizeRoom(student.room) === roomValue)
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

  const sheet = getSpreadsheet().getSheetByName('no_right');
  const values = rows.map((row) => [
    row.timestamp,
    row.class || `${row.grade || ''}/${row.room || ''}`.replace(/\/$/, ''),
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

function getSpreadsheet() {
  return SpreadsheetApp.openById(SPREADSHEET_ID);
}

function normalizeRoom(value) {
  return String(value)
    .trim()
    .replace(/\s+/g, '')
    .replace(/\\/g, '/')
    .replace('／', '/');
}

function getDebugInfo() {
  const spreadsheet = getSpreadsheet();
  const sheet = spreadsheet.getSheetByName('student');
  const values = sheet.getDataRange().getDisplayValues();
  const headers = values.length ? values[0].map(String) : [];
  const firstDataRow = values.length > 1 ? values[1].map(String) : [];

  return {
    spreadsheetName: spreadsheet.getName(),
    sheetNames: spreadsheet.getSheets().map((sheetItem) => sheetItem.getName()),
    headers,
    firstDataRow,
    totalRows: Math.max(values.length - 1, 0),
    sampleRoomRaw: firstDataRow[3] || '',
    sampleRoomNormalized: normalizeRoom(firstDataRow[3] || ''),
    expectedRoomForM1Room1: normalizeRoom('1/1'),
  };
}

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
