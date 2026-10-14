// Read-only exact-path inventory of three user-assigned archives. Never an apply plan.
const ID = /^[0-9a-f]{32}$/;
const SHA = /^[0-9a-f]{64}$/;
const ROLES = ['base', 'current', 'upstream'];
export const THREEWAY_ACTIONS = ['unchanged', 'same_change', 'keep_current', 'take_upstream', 'conflict'];
const FILTERS = ['all', 'changes', ...THREEWAY_ACTIONS];
const ACTION_LABELS = {
  unchanged: 'Без изменений относительно Base',
  same_change: 'Одинаковое отличие от Base',
  keep_current: 'Отличается только Current',
  take_upstream: 'Отличается только Upstream',
  conflict: 'Разные отличия Current и Upstream',
};
const ROLE_LABELS = {base: 'Base', current: 'Current', upstream: 'Upstream'};
const MAX_SIDE_ENTRIES = 4096, MAX_FILE = 4 * 1024 * 1024, MAX_DECODED = 32 * 1024 * 1024;
const integer = (n, max) => Number.isInteger(n) && n >= 0 && n <= max;
const protocol = () => { throw {code: 'PROTOCOL_ERROR'}; };
const equal = (left, right) => left === null || right === null ? left === right : left.raw_sha256 === right.raw_sha256 && left.size_bytes === right.size_bytes;
const sameBinding = (left, right) => !!left && !!right && left.job === right.job && left.input_sha256 === right.input_sha256;
const terminal = status => ['ready', 'error', 'cancelled'].includes(status);

export function threewayAction(base, current, upstream) {
  if (equal(base, current) && equal(base, upstream)) return 'unchanged';
  if (equal(current, upstream)) return 'same_change';
  if (equal(base, upstream)) return 'keep_current';
  if (equal(base, current)) return 'take_upstream';
  return 'conflict';
}
export function threewayCountsMatch(counts, coverage) {
  if (!counts || !['total', 'files', 'changes', ...THREEWAY_ACTIONS].every(k => integer(counts[k], 3 * MAX_SIDE_ENTRIES))) return false;
  if (counts.total !== counts.files || counts.total !== THREEWAY_ACTIONS.reduce((n, key) => n + counts[key], 0) || counts.changes !== counts.total - counts.unchanged) return false;
  if (!coverage || coverage.scope !== 'exact_path_inventory' || coverage.comparison !== 'raw_sha256_and_size' || coverage.complete !== true || coverage.union_paths !== counts.total) return false;
  if (!integer(coverage.entry_records, 3 * MAX_SIDE_ENTRIES) || !integer(coverage.decoded_bytes, 3 * MAX_DECODED)) return false;
  if (!ROLES.every(role => integer(coverage.side_entries?.[role], MAX_SIDE_ENTRIES) && integer(coverage.side_decoded_bytes?.[role], MAX_DECODED))) return false;
  return coverage.entry_records === ROLES.reduce((n, role) => n + coverage.side_entries[role], 0) && coverage.decoded_bytes === ROLES.reduce((n, role) => n + coverage.side_decoded_bytes[role], 0) && counts.total <= coverage.entry_records && counts.total >= Math.max(...ROLES.map(role => coverage.side_entries[role]));
}
export function threewayStatusMatches(binding, reply, plan = null) {
  if (!binding || !reply || !ID.test(reply.plan) || (plan && reply.plan !== plan) || reply.job !== binding.job || reply.current_sha256 !== binding.input_sha256 || !['awaiting_inputs', 'uploading', 'analyzing', 'ready', 'error', 'cancelled'].includes(reply.status)) return false;
  if (!ROLES.every(role => {
    const value = reply.roles?.[role];
    if (!value || !['missing', 'awaiting_upload', 'uploading', 'analyzing', 'ready', 'error', 'cancelled'].includes(value.status)) return false;
    if (!(value.upload === null || ID.test(value.upload)) || (role === 'current' && value.upload !== null)) return false;
    if (value.status === 'missing') return role !== 'current' && value.filename === null && value.sha256 === null && value.upload === null;
    if (role !== 'current' && !ID.test(value.upload)) return false;
    return typeof value.filename === 'string' && value.filename.length > 0 && value.filename.length <= 240 && (value.sha256 === null || SHA.test(value.sha256)) && (value.status !== 'ready' || SHA.test(value.sha256));
  })) return false;
  if (reply.roles.current.status !== 'ready' || reply.roles.current.sha256 !== binding.input_sha256) return false;
  return reply.status === 'ready' ? ROLES.every(role => reply.roles[role].status === 'ready') && threewayCountsMatch(reply.counts, reply.coverage) : reply.counts == null && reply.coverage == null;
}
export function threewayUploadMatches(plan, role, reply, upload = null) {
  return !!reply && reply.plan === plan && reply.role === role && ['base', 'upstream'].includes(role) && ID.test(reply.upload) && (!upload || reply.upload === upload);
}
export function threewayPageMatches(result, reply, offset, action) {
  if (!result || !reply || !FILTERS.includes(action) || !integer(offset, 3 * MAX_SIDE_ENTRIES) || offset % 200 !== 0 || reply.plan !== result.plan || reply.job !== result.job || reply.action !== action) return false;
  if (!ROLES.every(role => reply[role + '_sha256'] === result.roles?.[role]?.sha256 && SHA.test(reply[role + '_sha256']))) return false;
  if (!threewayCountsMatch(reply.counts, reply.coverage) || !threewayCountsMatch(result.counts, result.coverage)) return false;
  if (['total', 'files', 'changes', ...THREEWAY_ACTIONS].some(key => reply.counts[key] !== result.counts[key])) return false;
  for (const key of ['scope', 'comparison', 'complete', 'entry_records', 'decoded_bytes', 'union_paths']) if (reply.coverage[key] !== result.coverage[key]) return false;
  if (ROLES.some(role => reply.coverage.side_entries[role] !== result.coverage.side_entries[role] || reply.coverage.side_decoded_bytes[role] !== result.coverage.side_decoded_bytes[role])) return false;
  const page = reply.page, rows = reply.rows, total = action === 'all' ? result.counts.total : result.counts[action];
  if (!page || !ID.test(page.id) || page.offset !== offset || page.limit !== 200 || page.total !== total || !Array.isArray(rows) || rows.length > 200 || page.returned !== rows.length || page.returned !== Math.min(200, Math.max(0, total - offset)) || page.has_previous !== (offset > 0) || page.has_next !== (offset + rows.length < total)) return false;
  const paths = new Set();
  return rows.every(row => {
    if (!row || typeof row.path !== 'string' || !row.path || row.path.length > 4096 || paths.has(row.path) || !THREEWAY_ACTIONS.includes(row.action) || (action === 'changes' && row.action === 'unchanged') || (!['all', 'changes'].includes(action) && row.action !== action)) return false;
    paths.add(row.path);
    if (!ROLES.every(role => row[role] === null || (!!row[role] && SHA.test(row[role].raw_sha256) && integer(row[role].size_bytes, MAX_FILE)))) return false;
    return ROLES.some(role => row[role] !== null) && row.action === threewayAction(row.base, row.current, row.upstream);
  });
}

export function createThreeway({api, errorText, getBinding}) {
  const $ = id => document.getElementById(id);
  const state = {active: false, generation: 0, binding: null, plan: null, status: null, ready: null, page: null, offset: 0, busy: false, cancelling: false, uncertain: false, upload: null, cleanup: Promise.resolve(), startWork: null, roleAttempt: null};
  const owns = generation => state.active && state.generation === generation && sameBinding(state.binding, getBinding());
  const post = (path, body) => api(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), signal: AbortSignal.timeout(5000)});
  const message = text => { $('threeway-message').textContent = text; };
  const statusURL = plan => '/api/threeway?' + new URLSearchParams({plan});
  function controls() {
    $('threeway-confirm').disabled = state.busy || !!state.plan;
    $('threeway-check').disabled = state.busy || !state.plan;
    $('threeway-cancel').hidden = !state.plan;
    $('threeway-cancel').disabled = state.cancelling;
    for (const role of ['base', 'upstream']) $('threeway-' + role + '-file').disabled = state.busy || state.uncertain || !state.plan || ['error', 'cancelled'].includes(state.status);
    $('threeway-filter').disabled = state.busy || !state.ready;
    $('threeway-previous').disabled = state.busy || !state.page?.has_previous;
    $('threeway-next').disabled = state.busy || !state.page?.has_next;
  }
  function clearPage() {
    state.page = null;
    $('threeway-list').replaceChildren();
    $('threeway-range').textContent = '';
    controls();
  }
  function clearResult() {
    state.ready = null;
    clearPage();
    $('threeway-result').hidden = true;
    $('threeway-counts').textContent = '';
    $('threeway-coverage').textContent = '';
    controls();
  }
  function showRoles(roles = null) {
    for (const role of ROLES) {
      const value = roles?.[role];
      const node = $('threeway-' + role);
      if (value) node.textContent = `${ROLE_LABELS[role]}: ${value.filename || 'не выбран'} · SHA-256 ZIP: ${value.sha256 || 'ещё не подтверждён'} · ${value.status === 'ready' ? 'байты прочитаны' : value.status === 'missing' ? 'ожидается ZIP' : 'результат роли ещё не подтверждён'}`;
      else if (role === 'current' && state.binding) node.textContent = `Current: ${state.binding.filename} · SHA-256 ZIP: ${state.binding.input_sha256} · подтвердите эту роль`;
      else node.textContent = `${ROLE_LABELS[role]}: не выбран`;
    }
  }
  function checked(reply, plan = state.plan, checkUpload = true) {
    if (!threewayStatusMatches(state.binding, reply, plan)) protocol();
    if (checkUpload && !['error', 'cancelled'].includes(reply.status)) {
      for (const role of ['base', 'upstream']) {
        const previous = state.roles?.[role], next = reply.roles[role];
        if (previous?.status === 'ready' && role !== state.roleAttempt?.role && (next.status !== 'ready' || previous.upload !== next.upload || previous.sha256 !== next.sha256 || previous.filename !== next.filename)) protocol();
      }
    }
    if (checkUpload && state.roleAttempt && !['error', 'cancelled'].includes(reply.status)) {
      const attempt = state.roleAttempt, token = reply.roles[attempt.role].upload;
      if (!ID.test(token) || (attempt.upload ? token !== attempt.upload : token === attempt.previousUpload)) protocol();
      attempt.upload = token;
    }
    return reply;
  }
  async function loadPage(offset = 0, focus = null) {
    if (!state.ready || !state.active || state.busy) return;
    const result = state.ready, generation = ++state.generation, action = $('threeway-filter').value;
    state.busy = true;
    clearPage();
    message('Читаем страницу инвентаря трёх ZIP…');
    try {
      const query = {plan: result.plan, offset, action};
      for (const role of ROLES) query[role + '_sha256'] = result.roles[role].sha256;
      const reply = await api('/api/threeway-page?' + new URLSearchParams(query), {signal: AbortSignal.timeout(5000)});
      if (!owns(generation)) return;
      if (!threewayPageMatches(result, reply, offset, action)) protocol();
      state.page = reply.page;
      state.offset = offset;
      $('threeway-range').textContent = reply.page.total ? `Пути ${offset + 1}–${offset + reply.rows.length} из ${reply.page.total}` : 'Нет путей в выбранной категории';
      for (const row of reply.rows) {
        const item = document.createElement('li');
        const heading = document.createElement('h3');
        heading.textContent = `${ACTION_LABELS[row.action]} · ${row.path}`;
        item.append(heading);
        for (const role of ROLES) {
          const side = document.createElement('p');
          side.textContent = row[role] ? `${ROLE_LABELS[role]}: ${row[role].size_bytes} байт · SHA-256 файла: ${row[role].raw_sha256}` : `${ROLE_LABELS[role]}: файл отсутствует`;
          item.append(side);
        }
        $('threeway-list').append(item);
      }
      message('Категории описывают только наличие файлов и совпадение байтов по точному пути.');
    } catch (error) {
      if (owns(generation)) { clearPage(); message('Страница не подтверждена. ' + errorText(error) + ' Нажмите «Проверить результат».'); }
    } finally {
      if (owns(generation)) {
        state.busy = false;
        controls();
        if (focus) {
          const target = $(focus), fallback = $('threeway-filter');
          (target.disabled ? fallback : target).focus();
        }
      }
    }
  }
  async function accept(reply, generation) {
    if (!owns(generation)) return;
    checked(reply);
    if (reply.status === 'cancelled') {
      state.plan = null;
      state.roles = null;
      state.roleAttempt = null;
      state.status = null;
      state.uncertain = false;
      clearResult();
      showRoles();
      message('Набор трёх ZIP отменён. Для нового набора подтвердите Current.');
      return;
    }
    state.status = reply.status;
    state.roles = reply.roles;
    showRoles(reply.roles);
    if (reply.status === 'ready') {
      state.uncertain = false;
      state.upload = null;
      state.roleAttempt = null;
      state.ready = reply;
      state.busy = false;
      const counts = reply.counts;
      $('threeway-counts').textContent = `Всего путей: ${counts.total} · С отличиями: ${counts.changes} · ` + THREEWAY_ACTIONS.map(action => `${ACTION_LABELS[action]}: ${counts[action]}`).join(' · ');
      $('threeway-coverage').textContent = `Полный инвентарь по точным путям: ${reply.coverage.union_paths} · Записей файлов в трёх ZIP: ${reply.coverage.entry_records} · Прочитано после распаковки: ${reply.coverage.decoded_bytes} байт. Формат конфигурации и смысл файлов не проверены.`;
      $('threeway-result').hidden = false;
      controls();
      await loadPage(0);
      return;
    }
    clearResult();
    state.uncertain = ['uploading', 'analyzing'].includes(reply.status) || ['base', 'upstream'].some(role => ['awaiting_upload', 'uploading', 'analyzing'].includes(reply.roles[role].status));
    if (!state.uncertain) state.roleAttempt = null;
    if (reply.status === 'error') message('Инвентарь не получен. ' + errorText({code: reply.error}) + ' Отмените набор и подтвердите Current заново.');
    else if (state.uncertain) message('Чтение ZIP ещё не завершено. Проверьте результат или отмените набор.');
    else message('Current подтверждён. Загрузите Base и Upstream отдельно; названия ролей задаёте вы.');
    controls();
  }
  async function start() {
    if (!state.active || state.busy || state.plan || !getBinding()) return;
    state.binding = getBinding();
    const binding = {...state.binding}, generation = ++state.generation, previousCleanup = state.cleanup;
    state.busy = true;
    state.uncertain = false;
    state.roleAttempt = null;
    clearResult();
    message('Подтверждаем открытую выгрузку как Current…');
    async function receive(reply) {
      if (!threewayStatusMatches(binding, reply)) protocol();
      if (!owns(generation)) {
        await post('/api/threeway-cancel', {plan: reply.plan}).catch(() => {});
        return;
      }
      state.plan = reply.plan;
      await accept(reply, generation);
    }
    const work = (async () => {
      try {
        await previousCleanup;
        if (!owns(generation)) return;
        try {
          await receive(await post('/api/threeway-start', {job: binding.job, input_sha256: binding.input_sha256}));
        } catch (error) {
          if (!['CONNECTION_LOST', 'PROTOCOL_ERROR'].includes(error.code)) throw error;
          // The only recovery is read-only and tied to the exact confirmed Current.
          const reply = await api('/api/threeway-current?' + new URLSearchParams({job: binding.job, input_sha256: binding.input_sha256}), {signal: AbortSignal.timeout(5000)});
          if (reply?.plan === null && reply.job === binding.job && reply.current_sha256 === binding.input_sha256 && reply.status === 'none') {
            if (owns(generation)) message('Набор трёх ZIP не создан. Подтвердите Current ещё раз.');
          } else await receive(reply);
        }
      } catch (error) {
        if (owns(generation)) message('Подтверждение Current не получено. ' + errorText(error) + ' Загрузка ZIP не выполнялась.');
      } finally {
        if (owns(generation)) { state.busy = false; controls(); }
      }
    })();
    state.startWork = work;
    await work;
    if (state.startWork === work) state.startWork = null;
  }
  async function refresh() {
    if (!state.active || state.busy || !state.plan) return;
    const generation = ++state.generation, plan = state.plan;
    state.busy = true;
    clearResult();
    message('Проверяем этот набор трёх ZIP…');
    try {
      const reply = await api(statusURL(plan), {signal: AbortSignal.timeout(5000)});
      if (owns(generation)) await accept(checked(reply, plan), generation);
    } catch (error) {
      if (owns(generation)) { state.uncertain = true; message('Результат пока не подтверждён. ' + errorText(error) + ' Проверьте ещё раз или отмените набор.'); }
    } finally {
      if (owns(generation)) { state.busy = false; controls(); }
    }
  }
  async function upload(role, file) {
    if (!state.active || state.busy || state.uncertain || !state.plan || ['error', 'cancelled'].includes(state.status)) return;
    if (!/\.zip$/i.test(file.name) || !file.size || file.size > 16 * 1024 * 1024) { message(errorText({code: 'INVALID_UPLOAD'})); return; }
    const generation = ++state.generation, plan = state.plan;
    state.busy = true;
    state.roleAttempt = {role, previousUpload: state.roles?.[role]?.upload || null, upload: null};
    state.upload = new AbortController();
    clearResult();
    // A role change clears every old row before the first request, even if it fails.
    $('threeway-' + role).textContent = `${ROLE_LABELS[role]}: ${file.name} · SHA-256 ZIP: ещё не подтверждён`;
    message(`Передаём и читаем ${ROLE_LABELS[role]}…`);
    let uploadId = null;
    try {
      const started = await post('/api/threeway-upload-start', {plan, role, filename: file.name.slice(0, 240)});
      if (!owns(generation)) return;
      if (!threewayUploadMatches(plan, role, started) || started.status !== 'awaiting_upload') protocol();
      uploadId = started.upload;
      state.roleAttempt.upload = uploadId;
      const sent = await api('/api/threeway-upload?' + new URLSearchParams({plan, upload: uploadId}), {method: 'PUT', headers: {'Content-Type': 'application/zip'}, body: file, signal: AbortSignal.any([state.upload.signal, AbortSignal.timeout(35000)])});
      if (!owns(generation)) return;
      if (!threewayUploadMatches(plan, role, sent, uploadId)) protocol();
      const deadline = Date.now() + 75000;
      while (owns(generation) && Date.now() < deadline) {
        const reply = await api(statusURL(plan), {signal: AbortSignal.timeout(5000)});
        if (!owns(generation)) return;
        checked(reply, plan);
        if (terminal(reply.status) || reply.status === 'awaiting_inputs') { await accept(reply, generation); return; }
        await new Promise(resolve => setTimeout(resolve, 350));
      }
      if (owns(generation)) { state.uncertain = true; message('Чтение ZIP ещё не подтверждено. Проверьте результат или отмените набор.'); }
    } catch (error) {
      if (!owns(generation)) return;
      state.uncertain = true;
      // Never replay an uncertain upload. Read back only this exact known plan.
      if (['CONNECTION_LOST', 'PROTOCOL_ERROR'].includes(error.code)) {
        for (let attempt = 0; attempt < 3 && owns(generation); attempt++) {
          try {
            const reply = await api(statusURL(plan), {signal: AbortSignal.timeout(3000)});
            if (!owns(generation)) return;
            checked(reply, plan);
            if (terminal(reply.status) || (reply.status === 'awaiting_inputs' && reply.roles[role].status === 'ready')) { await accept(reply, generation); return; }
          } catch { /* A failed read-back cannot authorize replay or display old rows. */ }
          if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 250));
        }
      }
      if (owns(generation)) message('Результат загрузки не подтверждён. ' + errorText(error) + ' Проверьте результат или отмените набор; повторная загрузка не выполняется.');
    } finally {
      if (owns(generation)) { state.busy = false; state.upload = null; controls(); }
    }
  }
  async function cancel() {
    if (!state.plan || state.cancelling) return;
    const plan = state.plan, generation = ++state.generation;
    state.cancelling = true;
    state.upload?.abort();
    state.upload = null;
    state.busy = true;
    state.uncertain = true;
    clearResult();
    message('Отменяем набор трёх ZIP…');
    try {
      try {
        const response = await post('/api/threeway-cancel', {plan});
        if (response?.plan !== plan || response.status !== 'cancelled' || response.cancel_requested !== true) protocol();
      } catch (error) {
        if (!['CONNECTION_LOST', 'PROTOCOL_ERROR'].includes(error.code)) throw error;
        // Cancellation acknowledgement can be lost; read back, never replay it.
      }
      if (!owns(generation)) return;
      const reply = checked(await api(statusURL(plan), {signal: AbortSignal.timeout(5000)}), plan, false);
      if (!owns(generation)) return;
      if (reply.status !== 'cancelled') { message('Отмена ещё не подтверждена. Проверьте результат или отмените набор ещё раз.'); return; }
      await accept(reply, generation);
    } catch (error) {
      if (owns(generation)) message('Отмена не подтверждена. ' + errorText(error) + ' Старые строки скрыты. Проверьте результат или повторите отмену.');
    } finally {
      if (owns(generation)) { state.busy = false; state.cancelling = false; controls(); }
    }
  }
  function leave() {
    state.active = false;
    state.generation++;
    state.upload?.abort();
    state.upload = null;
    const plan = state.plan;
    const cancellation = plan ? post('/api/threeway-cancel', {plan}).catch(() => {}) : Promise.resolve();
    state.cleanup = Promise.all([state.cleanup, state.startWork, cancellation]).then(() => {}, () => {});
    state.plan = null;
    state.roles = null;
    state.roleAttempt = null;
    state.status = null;
    state.busy = false;
    state.cancelling = false;
    state.uncertain = false;
    clearResult();
    showRoles();
  }
  function enter() {
    const binding = getBinding();
    if (!binding) return;
    if (state.active && sameBinding(binding, state.binding)) return;
    if (state.active) leave();
    state.active = true;
    state.binding = binding;
    $('threeway-filter').value = 'changes';
    showRoles();
    message('Подтвердите, что открытая выгрузка будет Current в этом наборе.');
    controls();
  }
  $('threeway-confirm').addEventListener('click', () => void start());
  $('threeway-check').addEventListener('click', () => void refresh());
  $('threeway-cancel').addEventListener('click', () => void cancel());
  for (const role of ['base', 'upstream']) $('threeway-' + role + '-file').addEventListener('change', () => {
    const file = $('threeway-' + role + '-file').files[0];
    $('threeway-' + role + '-file').value = '';
    if (file) void upload(role, file);
  });
  $('threeway-filter').addEventListener('change', () => void loadPage(0, 'threeway-filter'));
  $('threeway-previous').addEventListener('click', () => void loadPage(state.offset - 200, 'threeway-previous'));
  $('threeway-next').addEventListener('click', () => void loadPage(state.offset + 200, 'threeway-next'));
  controls();
  return {enter, leave, get busy() { return state.busy || state.uncertain; }};
}
