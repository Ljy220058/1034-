/**
 * Escape HTML special characters for safe text rendering.
 * @param {string} value - Raw text that may contain HTML-sensitive characters.
 * @returns {string} Escaped HTML-safe string.
 */
function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

/**
 * Validate the task creation form fields.
 * @param {HTMLFormElement|Object} form - Form-like object containing title, assignee, status, priority, and dependencies fields.
 * @returns {Array<{field: string, message: string}>} Validation errors for missing or malformed inputs.
 * @description Ensures required task fields are present and dependency IDs follow the expected Hermes task format.
 */
function validateTaskForm(form) {
  const errors = [];
  const title = String(form?.title?.value || '').trim();
  const assignee = String(form?.assignee?.value || '').trim();
  const status = String(form?.status?.value || '').trim();
  const priority = String(form?.priority?.value || '').trim();
  const dependencies = String(form?.dependencies?.value || '').trim();

  if (!title) {
    errors.push({ field: 'title', message: '请输入任务标题。' });
  }
  if (!assignee) {
    errors.push({ field: 'assignee', message: '请选择负责人。' });
  }
  if (!status) {
    errors.push({ field: 'status', message: '请选择任务状态。' });
  }
  if (!priority) {
    errors.push({ field: 'priority', message: '请选择优先级。' });
  }
  if (dependencies && !/^#t_[a-f0-9]{8}(?:\s*,\s*#t_[a-f0-9]{8})*$/i.test(dependencies)) {
    errors.push({ field: 'dependencies', message: '依赖项格式不正确，请使用 #t_xxxxxxxx 形式。' });
  }

  return errors;
}

/**
 * Normalize a worker availability payload for UI rendering.
 * @param {Object} view - Raw worker availability data.
 * @returns {{status: string, label: string, tone: string, message: string, canAssign: boolean}} Normalized availability view model.
 * @description Converts backend-style availability payloads into a stable object for badges and buttons.
 */
function normalizeWorkerAvailability(view) {
  const status = String(view?.status || '').toLowerCase();
  return {
    status,
    label: view?.label || '未知',
    tone: view?.tone || 'amber',
    message: view?.message || '',
    canAssign: Boolean(view?.available),
  };
}

function renderConnectionStatus(view, target) {
  if (!target) return;
  const badgeClass = view.tone || 'amber';
  const retryDisabled = view.canRetry ? '' : 'disabled';
  target.innerHTML = `
    <div class="connection-status ${badgeClass}">
      <div class="connection-status__badge" data-connection-badge data-state="${escapeHtml(view.status || 'unknown')}">${escapeHtml(view.label || '连接状态未知')}</div>
      <p class="connection-status__message" data-connection-message>${escapeHtml(view.message || '')}</p>
      <button class="button ghost" type="button" data-connection-retry ${retryDisabled}>${escapeHtml(view.retryLabel || '重试连接')}</button>
    </div>
  `;
}

function renderWorkerAvailability(view, target) {
  if (!target) return;
  const badgeClass = view.tone || 'amber';
  target.innerHTML = `
    <div class="worker-availability ${badgeClass}">
      <div class="worker-availability__badge" data-worker-availability data-state="${escapeHtml(view.label || '未知')}">${escapeHtml(view.label || '未知')}</div>
      <p class="worker-availability__message">${escapeHtml(view.message || '')}</p>
    </div>
  `;
}

function applyWorkerAvailabilityBadge(element, view) {
  if (!element) return;
  element.classList.remove('is-available', 'is-busy', 'is-offline', 'is-paused');
  if (view.status === 'idle' || view.status === 'available') {
    element.classList.add('is-available');
  } else if (view.status === 'busy' || view.status === 'running' || view.status === 'working') {
    element.classList.add('is-busy');
  } else if (view.status === 'paused') {
    element.classList.add('is-paused');
  } else {
    element.classList.add('is-offline');
  }
  element.dataset.state = view.status || 'unknown';
  element.textContent = view.label || '未知';
}

function renderWorkerAssignmentList(workers, target, onSelect) {
  if (!target) return;
  target.innerHTML = (Array.isArray(workers) ? workers : []).map((worker) => {
    const view = normalizeWorkerAvailability(worker);
    return `
      <button class="worker-row ${view.canAssign ? 'is-available' : 'is-unavailable'}" type="button" data-worker-id="${escapeHtml(String(worker.worker_key || worker.task_id || worker.id || ''))}">
        <strong>${escapeHtml(worker.name || worker.title || worker.worker_key || worker.task_id || '未命名 worker')}</strong>
        <span>${escapeHtml(view.label)}</span>
      </button>
    `;
  }).join('');
  target.querySelectorAll('[data-worker-id]').forEach((button) => {
    button.addEventListener('click', () => onSelect?.(button.dataset.workerId));
  });
}

export { escapeHtml, validateTaskForm, renderConnectionStatus, normalizeWorkerAvailability, renderWorkerAvailability, applyWorkerAvailabilityBadge, renderWorkerAssignmentList };
