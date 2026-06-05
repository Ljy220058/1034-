function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

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

export { escapeHtml, validateTaskForm, renderConnectionStatus };
