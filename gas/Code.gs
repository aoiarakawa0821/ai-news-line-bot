const SHEET_NAME = 'users';
const STATUS_PENDING = 'pending';
const STATUS_APPROVED = 'approved';
const STATUS_REJECTED = 'rejected';
const DAILY_NEWS_DISPATCH_FUNCTION = 'dispatchDailyAiNewsWorkflow';
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
      console.warn('LINE signature verification failed.');
      return forbiddenResponse_();
    }

    const payload = JSON.parse(body || '{}');
    const events = payload.events || [];
    events.forEach(function(event) {
      handleEvent_(event);
    });
    return okResponse_();
  } catch (error) {
    console.error('doPost error: ' + safeError_(error));
    notifyAdmin_('GAS Webhookでエラーが発生しました。スプレッドシート設定とログを確認してください。');
    return okResponse_();
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
    if (parseAdminCommand_(text)) {
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
  const adminCommand = parseAdminCommand_(text);
  if (!adminCommand) {
    reply_(replyToken, '未対応のコマンドです。\n\n' + helpText_());
    return;
  }

  if (!isAdmin_(userId)) {
    reply_(replyToken, 'このコマンドは管理者だけが実行できます。');
    return;
  }

  if (adminCommand.name === 'approve') {
    approveOrReject_(STATUS_APPROVED, adminCommand.arg, replyToken);
  } else if (adminCommand.name === 'reject') {
    approveOrReject_(STATUS_REJECTED, adminCommand.arg, replyToken);
  } else if (adminCommand.name === 'list' && adminCommand.status === STATUS_PENDING) {
    listByStatus_(STATUS_PENDING, replyToken);
  } else if (adminCommand.name === 'list' && adminCommand.status === STATUS_APPROVED) {
    listByStatus_(STATUS_APPROVED, replyToken);
  } else if (adminCommand.name === 'help') {
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
    console.error('LINE profile API failed. status=' + response.getResponseCode());
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

function dispatchDailyAiNewsWorkflow() {
  try {
    const repository = getRequiredProperty_('GITHUB_REPOSITORY');
    const token = getRequiredProperty_('GITHUB_DISPATCH_TOKEN');
    const workflowFile = getProperty_('GITHUB_WORKFLOW_FILE') || 'daily_ai_news.yml';
    const ref = getProperty_('GITHUB_WORKFLOW_REF') || 'main';
    const url =
      'https://api.github.com/repos/' +
      encodeRepositoryPath_(repository) +
      '/actions/workflows/' +
      encodeURIComponent(workflowFile) +
      '/dispatches';

    const response = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
      },
      payload: JSON.stringify({
        ref: ref,
        inputs: {
          scheduled_dispatch: 'true',
        },
      }),
      muteHttpExceptions: true,
    });

    const status = response.getResponseCode();
    if (status !== 204) {
      const body = safeResponseBody_(response);
      console.error('GitHub workflow_dispatch failed. status=' + status + ' body=' + body);
      notifyAdmin_(
        'GitHub Actionsの起動に失敗しました。\n' +
        'status=' + status + '\n' +
        'GITHUB_DISPATCH_TOKEN、GITHUB_REPOSITORY、workflow名を確認してください。'
      );
      throw new Error('workflow_dispatch failed. status=' + status);
    }

    console.log('GitHub workflow_dispatch accepted. repository=' + repository + ' workflow=' + workflowFile);
  } catch (error) {
    console.error('dispatchDailyAiNewsWorkflow error: ' + safeError_(error));
    notifyAdmin_('GitHub Actionsの定期起動処理でエラーが発生しました。GASの実行ログを確認してください。');
    throw error;
  }
}

function setupDailyAiNewsWorkflowTriggers() {
  deleteDailyAiNewsWorkflowTriggers();
  ScriptApp.newTrigger(DAILY_NEWS_DISPATCH_FUNCTION)
    .timeBased()
    .inTimezone('Asia/Tokyo')
    .everyDays(1)
    .atHour(7)
    .nearMinute(7)
    .create();
  ScriptApp.newTrigger(DAILY_NEWS_DISPATCH_FUNCTION)
    .timeBased()
    .inTimezone('Asia/Tokyo')
    .everyDays(1)
    .atHour(7)
    .nearMinute(37)
    .create();
  console.log('Daily AI news workflow triggers created at around 07:07 and 07:37 JST.');
}

function deleteDailyAiNewsWorkflowTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === DAILY_NEWS_DISPATCH_FUNCTION) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  console.log('Daily AI news workflow triggers deleted.');
}

function testDispatchDailyAiNewsWorkflow() {
  dispatchDailyAiNewsWorkflow();
}

function logLineApiFailure_(response, label) {
  const status = response.getResponseCode();
  if (status >= 400) {
    console.error('LINE ' + label + ' API failed. status=' + status);
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

function isAdmin_(sourceUserId) {
  const adminUserId = getProperty_('ADMIN_LINE_USER_ID');
  return !!adminUserId && sourceUserId === adminUserId;
}

function isAdminCommand_(text) {
  return !!parseAdminCommand_(text);
}

function parseAdminCommand_(text) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return null;
  }

  let match = normalized.match(/^approve(?: ([^\s]+))?$/i);
  if (match) {
    return { name: 'approve', arg: match[1] || '' };
  }

  match = normalized.match(/^reject(?: ([^\s]+))?$/i);
  if (match) {
    return { name: 'reject', arg: match[1] || '' };
  }

  match = normalized.match(/^list (pending|approved)$/i);
  if (match) {
    return { name: 'list', status: match[1].toLowerCase() };
  }

  if (normalized.toLowerCase() === 'help') {
    return { name: 'help' };
  }

  return null;
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

function getRequiredProperty_(name) {
  const value = getProperty_(name);
  if (!value) {
    throw new Error(name + ' is not set');
  }
  return value;
}

function encodeRepositoryPath_(repository) {
  return String(repository || '')
    .split('/')
    .map(function(part) {
      return encodeURIComponent(part);
    })
    .join('/');
}

function safeResponseBody_(response) {
  try {
    return String(response.getContentText() || '').slice(0, 1000);
  } catch (error) {
    return '(body unavailable)';
  }
}

function now_() {
  return Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm:ss');
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function okResponse_() {
  return HtmlService.createHtmlOutput('OK');
}

function forbiddenResponse_() {
  return HtmlService.createHtmlOutput('Forbidden');
}

function safeError_(error) {
  return error && error.message ? error.message : String(error);
}

function runAdminSecurityTests() {
  testNonAdminCannotSelfApprove_();
  testNonAdminCannotApproveOtherUser_();
  testNonAdminCannotReject_();
  testNonAdminCannotList_();
  testAdminCommandsDeniedWhenAdminUnset_();
  testParseAdminCommandStrict_();
}

function testNonAdminCannotSelfApprove_() {
  assertAdminCommandDeniedBeforeMutation_('U_non_admin', 'approve U_non_admin', 'U_admin');
}

function testNonAdminCannotApproveOtherUser_() {
  assertAdminCommandDeniedBeforeMutation_('U_non_admin', 'approve U_other_user', 'U_admin');
}

function testNonAdminCannotReject_() {
  assertAdminCommandDeniedBeforeMutation_('U_non_admin', 'reject U_other_user', 'U_admin');
}

function testNonAdminCannotList_() {
  assertAdminCommandDeniedBeforeMutation_('U_non_admin', 'list pending', 'U_admin');
  assertAdminCommandDeniedBeforeMutation_('U_non_admin', 'list approved', 'U_admin');
}

function testAdminCommandsDeniedWhenAdminUnset_() {
  assertAdminCommandDeniedBeforeMutation_('U_non_admin', 'approve U_non_admin', '');
  assertAdminCommandDeniedBeforeMutation_('U_non_admin', 'reject U_other_user', '');
  assertAdminCommandDeniedBeforeMutation_('U_non_admin', 'list pending', '');
  assertAdminCommandDeniedBeforeMutation_('U_non_admin', 'list approved', '');
}

function testParseAdminCommandStrict_() {
  const approveCommand = parseAdminCommand_('approve U_Target');
  assertTruthy_(approveCommand, 'approve with one userId should be parsed');
  assertEqual_(approveCommand.arg, 'U_Target', 'approve userId casing must be preserved');
  assertTruthy_(parseAdminCommand_('reject U_target'), 'reject with one userId should be parsed');
  assertTruthy_(parseAdminCommand_('list pending'), 'list pending should be parsed');
  assertTruthy_(parseAdminCommand_('list approved'), 'list approved should be parsed');
  assertFalsy_(parseAdminCommand_('please approve U_target'), 'prefix text must not be parsed');
  assertFalsy_(parseAdminCommand_('approve U_target now'), 'extra approve arguments must not be parsed');
  assertFalsy_(parseAdminCommand_('approved'), 'partial approve word must not be parsed');
  assertFalsy_(parseAdminCommand_('list'), 'incomplete list must not be parsed');
}

function assertAdminCommandDeniedBeforeMutation_(sourceUserId, text, adminUserId) {
  const originalGetProperty = getProperty_;
  const originalReply = reply_;
  const originalApproveOrReject = approveOrReject_;
  const originalListByStatus = listByStatus_;
  let mutationReached = false;
  let listReached = false;
  let replyText = '';

  try {
    getProperty_ = function(name) {
      return name === 'ADMIN_LINE_USER_ID' ? adminUserId : '';
    };
    reply_ = function(replyToken, text) {
      replyText = text;
    };
    approveOrReject_ = function() {
      mutationReached = true;
    };
    listByStatus_ = function() {
      listReached = true;
    };

    handleAdminCommand_(sourceUserId, text, 'test-reply-token');

    assertFalsy_(mutationReached, text + ' must not reach approve/reject mutation');
    assertFalsy_(listReached, text + ' must not reach spreadsheet list read');
    assertTruthy_(replyText.indexOf('管理者だけ') >= 0, text + ' should reply with admin-only message');
  } finally {
    getProperty_ = originalGetProperty;
    reply_ = originalReply;
    approveOrReject_ = originalApproveOrReject;
    listByStatus_ = originalListByStatus;
  }
}

function assertTruthy_(value, message) {
  if (!value) {
    throw new Error(message);
  }
}

function assertFalsy_(value, message) {
  if (value) {
    throw new Error(message);
  }
}

function assertEqual_(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(message + ' actual=' + actual + ' expected=' + expected);
  }
}
