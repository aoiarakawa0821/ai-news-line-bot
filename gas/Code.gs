const SHEET_NAME = 'users';
const STATUS_PENDING = 'pending';
const STATUS_APPROVED = 'approved';
const STATUS_REJECTED = 'rejected';
const HEADERS = [
  'userId',
  'displayName',
  'status',
  'createdAt',
  'updatedAt',
  'approvedAt',
  'rejectedAt',
  'note',
];

function doPost(e) {
  try {
    const body = e && e.postData && e.postData.contents ? e.postData.contents : '';
    if (!verifyLineSignature_(body, e)) {
      return json_({ ok: false, error: 'invalid_signature' });
    }

    const payload = JSON.parse(body || '{}');
    const events = payload.events || [];
    events.forEach(function(event) {
      handleEvent_(event);
    });
    return json_({ ok: true });
  } catch (error) {
    console.error('doPost error: ' + safeError_(error));
    notifyAdmin_('GAS Webhookでエラーが発生しました。スプレッドシート設定とログを確認してください。');
    return json_({ ok: false, error: 'internal_error' });
  }
}

function doGet(e) {
  try {
    const params = e && e.parameter ? e.parameter : {};
    if (params.action !== 'approved') {
      return json_({ ok: false, error: 'unknown_action' });
    }
    const expectedKey = getProperty_('APPROVED_USERS_API_KEY');
    if (!expectedKey || params.key !== expectedKey) {
      return json_({ ok: false, status: 403, error: 'forbidden' });
    }

    const rows = getRows_();
    const users = rows
      .filter(function(row) {
        return row.status === STATUS_APPROVED && row.userId;
      })
      .map(function(row) {
        return {
          userId: row.userId,
          displayName: row.displayName || '',
        };
      });
    return json_({ users: users });
  } catch (error) {
    console.error('doGet error: ' + safeError_(error));
    return json_({ ok: false, error: 'internal_error' });
  }
}

function handleEvent_(event) {
  const source = event.source || {};
  const userId = source.userId || '';
  if (!userId) {
    return;
  }

  if (event.type === 'message' && event.message && event.message.type === 'text') {
    const text = (event.message.text || '').trim();
    if (isAdminCommand_(text)) {
      handleAdminCommand_(userId, text, event.replyToken);
      return;
    }
  }

  if (event.type === 'follow' || event.type === 'message') {
    handleRegistration_(userId, event.replyToken);
  }
}

function handleRegistration_(userId, replyToken) {
  const sheet = getSheet_();
  const rowNumber = findRowNumberByUserId_(sheet, userId);
  const now = now_();

  if (!rowNumber) {
    const profile = getLineProfile_(userId);
    sheet.appendRow([
      userId,
      profile.displayName || '',
      STATUS_PENDING,
      now,
      now,
      '',
      '',
      'registered_by_webhook',
    ]);
    reply_(replyToken, '登録申請を受け付けました。管理者の承認をお待ちください。');
    notifyAdmin_(
      '登録申請が来ました。\n' +
      'displayName: ' + (profile.displayName || '(取得できませんでした)') + '\n' +
      'userId: ' + userId + '\n\n' +
      '承認: approve\n' +
      '拒否: reject\n' +
      '一覧: list pending'
    );
    return;
  }

  const row = rowToObject_(sheet.getRange(rowNumber, 1, 1, HEADERS.length).getValues()[0]);
  updateDisplayNameIfNeeded_(sheet, rowNumber, userId, row.displayName);

  if (row.status === STATUS_APPROVED) {
    reply_(replyToken, 'すでに登録済みです。毎朝のAIニュース配信対象です。');
  } else if (row.status === STATUS_PENDING) {
    reply_(replyToken, '現在、承認待ちです。管理者の承認をお待ちください。');
  } else if (row.status === STATUS_REJECTED) {
    reply_(replyToken, '現在このアカウントでは登録できません。');
  } else {
    setStatus_(sheet, rowNumber, STATUS_PENDING, 'status_reset_to_pending');
    reply_(replyToken, '登録申請を受け付けました。管理者の承認をお待ちください。');
  }
}

function handleAdminCommand_(userId, text, replyToken) {
  const adminUserId = getProperty_('ADMIN_LINE_USER_ID');
  if (!adminUserId || userId !== adminUserId) {
    reply_(replyToken, 'このコマンドは管理者だけが実行できます。');
    return;
  }

  const normalized = text.replace(/\s+/g, ' ').trim();
  const parts = normalized.split(' ');
  const command = parts[0].toLowerCase();
  const arg = parts.length > 1 ? parts[1] : '';

  if (command === 'approve') {
    approveOrReject_(STATUS_APPROVED, arg, replyToken);
  } else if (command === 'reject') {
    approveOrReject_(STATUS_REJECTED, arg, replyToken);
  } else if (normalized.toLowerCase() === 'list pending') {
    listByStatus_(STATUS_PENDING, replyToken);
  } else if (normalized.toLowerCase() === 'list approved') {
    listByStatus_(STATUS_APPROVED, replyToken);
  } else if (command === 'help') {
    reply_(replyToken, helpText_());
  } else {
    reply_(replyToken, '未対応のコマンドです。\n\n' + helpText_());
  }
}

function approveOrReject_(nextStatus, userIdOrEmpty, replyToken) {
  const sheet = getSheet_();
  const targetRowNumber = userIdOrEmpty
    ? findRowNumberByUserId_(sheet, userIdOrEmpty)
    : findOldestPendingRowNumber_(sheet);

  if (!targetRowNumber) {
    reply_(replyToken, '対象ユーザーが見つかりません。list pendingで確認してください。');
    return;
  }

  const row = rowToObject_(sheet.getRange(targetRowNumber, 1, 1, HEADERS.length).getValues()[0]);
  setStatus_(sheet, targetRowNumber, nextStatus, nextStatus + '_by_admin');

  if (nextStatus === STATUS_APPROVED) {
    push_(row.userId, '承認されました。明日からAIニュースが届きます。');
    reply_(replyToken, '承認しました。\n' + formatUserLine_(row));
  } else {
    push_(row.userId, '今回は承認されませんでした。');
    reply_(replyToken, '拒否しました。\n' + formatUserLine_(row));
  }
}

function listByStatus_(status, replyToken) {
  const rows = getRows_().filter(function(row) {
    return row.status === status;
  });

  if (rows.length === 0) {
    reply_(replyToken, status + ' のユーザーはいません。');
    return;
  }

  const lines = rows.slice(0, 20).map(formatUserLine_);
  const suffix = rows.length > 20 ? '\nほか ' + (rows.length - 20) + ' 件' : '';
  reply_(replyToken, status + ' 一覧（' + rows.length + '件）\n' + lines.join('\n') + suffix);
}

function getSheet_() {
  const spreadsheetId = getProperty_('SPREADSHEET_ID');
  if (!spreadsheetId) {
    throw new Error('SPREADSHEET_ID is not set');
  }

  let spreadsheet;
  try {
    spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  } catch (error) {
    notifyAdmin_('GASでスプレッドシートを開けません。SPREADSHEET_IDを確認してください。');
    throw error;
  }

  let sheet = spreadsheet.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(SHEET_NAME);
  }
  ensureHeader_(sheet);
  return sheet;
}

function ensureHeader_(sheet) {
  const firstRow = sheet.getRange(1, 1, 1, HEADERS.length).getValues()[0];
  const ok = HEADERS.every(function(header, index) {
    return firstRow[index] === header;
  });
  if (!ok) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  }
}

function getRows_() {
  const sheet = getSheet_();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    return [];
  }
  return sheet.getRange(2, 1, lastRow - 1, HEADERS.length).getValues().map(rowToObject_);
}

function rowToObject_(values) {
  const obj = {};
  HEADERS.forEach(function(header, index) {
    obj[header] = values[index] || '';
  });
  return obj;
}

function findRowNumberByUserId_(sheet, userId) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    return 0;
  }
  const values = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
  for (let index = 0; index < values.length; index++) {
    if (values[index][0] === userId) {
      return index + 2;
    }
  }
  return 0;
}

function findOldestPendingRowNumber_(sheet) {
  const rows = getRows_();
  for (let index = 0; index < rows.length; index++) {
    if (rows[index].status === STATUS_PENDING) {
      return index + 2;
    }
  }
  return 0;
}

function setStatus_(sheet, rowNumber, status, note) {
  const now = now_();
  sheet.getRange(rowNumber, 3).setValue(status);
  sheet.getRange(rowNumber, 5).setValue(now);
  sheet.getRange(rowNumber, 8).setValue(note || '');
  if (status === STATUS_APPROVED) {
    sheet.getRange(rowNumber, 6).setValue(now);
  }
  if (status === STATUS_REJECTED) {
    sheet.getRange(rowNumber, 7).setValue(now);
  }
}

function updateDisplayNameIfNeeded_(sheet, rowNumber, userId, currentDisplayName) {
  if (currentDisplayName) {
    return;
  }
  const profile = getLineProfile_(userId);
  if (profile.displayName) {
    sheet.getRange(rowNumber, 2).setValue(profile.displayName);
    sheet.getRange(rowNumber, 5).setValue(now_());
  }
}

function getLineProfile_(userId) {
  const token = getProperty_('LINE_CHANNEL_ACCESS_TOKEN');
  const response = UrlFetchApp.fetch('https://api.line.me/v2/bot/profile/' + encodeURIComponent(userId), {
    method: 'get',
    headers: { Authorization: 'Bearer ' + token },
    muteHttpExceptions: true,
  });
  if (response.getResponseCode() >= 400) {
    console.error('LINE profile API failed. status=' + response.getResponseCode() + ' body=' + response.getContentText());
    return {};
  }
  return JSON.parse(response.getContentText() || '{}');
}

function reply_(replyToken, text) {
  if (!replyToken) {
    return;
  }
  const token = getProperty_('LINE_CHANNEL_ACCESS_TOKEN');
  const response = UrlFetchApp.fetch('https://api.line.me/v2/bot/message/reply', {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token },
    payload: JSON.stringify({
      replyToken: replyToken,
      messages: [{ type: 'text', text: String(text).slice(0, 4900) }],
    }),
    muteHttpExceptions: true,
  });
  logLineApiFailure_(response, 'reply');
}

function push_(to, text) {
  const token = getProperty_('LINE_CHANNEL_ACCESS_TOKEN');
  const response = UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token },
    payload: JSON.stringify({
      to: to,
      messages: [{ type: 'text', text: String(text).slice(0, 4900) }],
    }),
    muteHttpExceptions: true,
  });
  logLineApiFailure_(response, 'push');
}

function notifyAdmin_(text) {
  const adminUserId = getProperty_('ADMIN_LINE_USER_ID');
  if (!adminUserId) {
    return;
  }
  push_(adminUserId, text);
}

function logLineApiFailure_(response, label) {
  const status = response.getResponseCode();
  if (status >= 400) {
    console.error('LINE ' + label + ' API failed. status=' + status + ' body=' + response.getContentText());
  }
}

function verifyLineSignature_(body, e) {
  const secret = getProperty_('LINE_CHANNEL_SECRET');
  if (!secret) {
    console.warn('LINE_CHANNEL_SECRET is not set. Signature verification skipped.');
    return true;
  }
  const signature = getHeader_(e, 'x-line-signature');
  if (!signature) {
    console.warn('x-line-signature header is unavailable in this Apps Script runtime. Signature verification skipped.');
    return true;
  }
  const bytes = Utilities.computeHmacSha256Signature(body, secret);
  const expected = Utilities.base64Encode(bytes);
  return signature === expected;
}

function getHeader_(e, name) {
  const headers = e && (e.headers || e.parameter && e.parameter.headers) ? e.headers || {} : {};
  const lowerName = name.toLowerCase();
  for (const key in headers) {
    if (String(key).toLowerCase() === lowerName) {
      return headers[key];
    }
  }
  return '';
}

function isAdminCommand_(text) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim().toLowerCase();
  return normalized === 'approve' ||
    normalized.indexOf('approve ') === 0 ||
    normalized === 'reject' ||
    normalized.indexOf('reject ') === 0 ||
    normalized === 'list pending' ||
    normalized === 'list approved' ||
    normalized === 'help';
}

function helpText_() {
  return [
    '管理者コマンド',
    'approve : 一番古いpendingユーザーを承認',
    'approve Uxxxx : 指定userIdを承認',
    'reject : 一番古いpendingユーザーを拒否',
    'reject Uxxxx : 指定userIdを拒否',
    'list pending : 承認待ち一覧',
    'list approved : 承認済み一覧',
    'help : このヘルプ',
  ].join('\n');
}

function formatUserLine_(row) {
  return '- ' + (row.displayName || '(名前なし)') + ' / ' + row.userId;
}

function getProperty_(name) {
  return PropertiesService.getScriptProperties().getProperty(name) || '';
}

function now_() {
  return Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm:ss');
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function safeError_(error) {
  return error && error.message ? error.message : String(error);
}
