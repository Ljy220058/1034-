/* 新人欢迎引导模块 */
window.onboardingModule = (() => {
  'use strict';

  const state = {
    overview: {
      title: '欢迎加入 1034 跑团',
      subtitle: '按步骤完成资料补全、认领带跑人和待办事项。',
      progress: 0,
      stepIndex: 0,
      steps: [],
    },
    buddies: [],
    checklist: [],
    loading: true,
    error: '',
    updatingIds: new Set(),
  };

  function getProgressText() {
    const doneCount = state.checklist.filter((item) => item.done).length;
    return `${doneCount}/${state.checklist.length || 0}`;
  }

  function getCompletedCount() {
    return state.checklist.filter((item) => item.done).length;
  }

  function normalizeOverview(payload) {
    const steps = Array.isArray(payload.steps)
      ? payload.steps.map((item, index) => ({
          id: item.id || item.step_id || `step-${index + 1}`,
          title: item.title || item.label || `步骤 ${index + 1}`,
          description: item.description || item.detail || '',
          done: Boolean(item.done ?? item.completed ?? item.finished),
        }))
      : [];

    return {
      title: payload.title || '欢迎加入 1034 跑团',
      subtitle: payload.subtitle || payload.description || '按步骤完成资料补全、认领带跑人和待办事项。',
      stepIndex: Number(payload.step_index ?? payload.current_step ?? payload.currentStep ?? 0),
      progress: Number(payload.progress ?? payload.percent ?? 0),
      steps,
      summary: payload.summary || payload.note || '',
    };
  }

  function renderHero() {
    const completed = getCompletedCount();
    const total = state.checklist.length;
    const currentStep = state.overview.steps[state.overview.stepIndex] || state.overview.steps[0] || null;
    return `
      <section class="card section onboarding-hero" aria-labelledby="onboarding-title">
        <div class="section-header">
          <div>
            <p class="summary-chip">新手欢迎引导</p>
            <h2 id="onboarding-title">${escapeHtml(state.overview.title)}</h2>
            <p>${escapeHtml(state.overview.subtitle)}</p>
          </div>
          <div class="summary-chip"><strong>${completed}</strong> / ${total || 0} 项已完成</div>
        </div>
        <div class="onboarding-hero__layout">
          <article class="onboarding-steps card" aria-label="步骤引导">
            ${renderSteps()}
          </article>
          <article class="onboarding-profile card" aria-label="带跑人推荐">
            <div class="onboarding-profile__header">
              <h3>老带新配对</h3>
              <p>优先找与你配速接近的跑友，减少前期适应成本。</p>
            </div>
            <div class="onboarding-profile__list">
              ${state.buddies.length ? state.buddies.map(renderBuddy).join('') : renderEmpty('暂无带跑人数据')}
            </div>
          </article>
        </div>
        <div class="onboarding-hero__footer">
          <div>
            <strong>当前步骤</strong>
            <p>${currentStep ? escapeHtml(currentStep.title) : '等待加载'}</p>
          </div>
          <div>
            <strong>完成进度</strong>
            <p>${Math.round(state.overview.progress || (total ? (completed / total) * 100 : 0))}%</p>
          </div>
        </div>
      </section>
    `;
  }

  function renderSteps() {
    if (!state.overview.steps.length) {
      return renderEmpty('暂无步骤配置');
    }

    return `
      <ol class="onboarding-step-list">
        ${state.overview.steps.map((step, index) => `
          <li class="onboarding-step ${step.done ? 'is-done' : ''} ${index === state.overview.stepIndex ? 'is-current' : ''}">
            <span class="onboarding-step__marker" aria-hidden="true">${step.done ? '✓' : index + 1}</span>
            <div>
              <strong>${escapeHtml(step.title)}</strong>
              <p>${escapeHtml(step.description || '请完成本步骤。')}</p>
            </div>
          </li>
        `).join('')}
      </ol>
    `;
  }

  function renderBuddy(item) {
    return `
      <article class="onboarding-buddy">
        <div class="onboarding-buddy__avatar" aria-hidden="true">${escapeHtml((item.name || '成员').slice(0, 1))}</div>
        <div class="onboarding-buddy__body">
          <strong>${escapeHtml(item.name)}</strong>
          <p>配速 ${escapeHtml(item.pace || '--')} · 周里程 ${escapeHtml(String(item.mileage || 0))} km</p>
        </div>
      </article>
    `;
  }

  function renderChecklistItem(item) {
    const busy = state.updatingIds.has(item.id);
    return `
      <label class="onboarding-check">
        <span class="onboarding-check__left">
          <input type="checkbox" ${item.done ? 'checked' : ''} ${busy ? 'disabled' : ''} data-check-id="${escapeHtml(item.id)}" />
          <span>
            <strong>${escapeHtml(item.label)}</strong>
            <small>${item.done ? '已完成' : '待完成'}</small>
          </span>
        </span>
        <button class="btn btn-secondary" type="button" data-toggle-check="${escapeHtml(item.id)}" ${busy ? 'disabled' : ''}>${busy ? '保存中' : item.done ? '撤销' : '完成'}</button>
      </label>
    `;
  }

  function renderChecklist() {
    return `
      <section class="card section onboarding-checklist" aria-labelledby="checklist-title">
        <div class="section-header">
          <div>
            <p class="summary-chip">欢迎清单</p>
            <h2 id="checklist-title">待办列表</h2>
            <p>按顺序完成资料确认、跑友配对和训练准备。</p>
          </div>
          <div class="summary-chip">${getProgressText()}</div>
        </div>
        <div class="onboarding-checklist__body">
          ${state.checklist.length ? state.checklist.map(renderChecklistItem).join('') : renderEmpty('暂无数据')}
        </div>
      </section>
    `;
  }

  function renderState() {
    if (state.loading) {
      return `
        <section class="card section onboarding-shell onboarding-shell--loading" aria-live="polite">
          <div class="onboarding-skeleton"></div>
          <div class="onboarding-skeleton"></div>
          <div class="onboarding-skeleton"></div>
        </section>
      `;
    }

    if (state.error) {
      return `
        <section class="card section panel-state is-error" role="alert">
          <div>
            <h3>加载失败</h3>
            <p>${escapeHtml(state.error)}</p>
          </div>
          <button class="btn btn-primary" type="button" data-action="retry">重试</button>
        </section>
      `;
    }

    return `
      <div class="onboarding-shell">
        ${renderHero()}
        ${renderChecklist()}
      </div>
    `;
  }

  function renderEmpty(message) {
    return `<div class="panel-state"><p>${escapeHtml(message)}</p></div>`;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function mount(root) {
    root.innerHTML = renderState();
    root.querySelectorAll('[data-toggle-check]').forEach((button) => {
      button.addEventListener('click', handleToggleClick);
    });
    root.querySelectorAll('input[type="checkbox"][data-check-id]').forEach((input) => {
      input.addEventListener('change', handleToggleInput);
    });
    const retry = root.querySelector('[data-action="retry"]');
    if (retry) retry.addEventListener('click', handleRetry);
  }

  async function load() {
    state.loading = true;
    state.error = '';
    render();
    try {
      const [overviewPayload, buddiesPayload, checklistPayload] = await Promise.all([
        window.apiClient.fetchOnboardingOverview(),
        window.apiClient.fetchOnboardingBuddies(),
        window.apiClient.fetchOnboardingChecklist(),
      ]);
      state.overview = normalizeOverview(overviewPayload || {});
      state.buddies = Array.isArray(buddiesPayload) ? buddiesPayload : [];
      state.checklist = Array.isArray(checklistPayload) ? checklistPayload : [];
    } catch (error) {
      state.error = error?.message || '加载新人欢迎引导失败';
    } finally {
      state.loading = false;
      render();
    }
  }

  async function handleToggleInput(event) {
    const checkId = event.target.dataset.checkId;
    await setChecklistItem(checkId, event.target.checked);
  }

  async function handleToggleClick(event) {
    const checkId = event.currentTarget.dataset.toggleCheck;
    const item = state.checklist.find((entry) => entry.id === checkId);
    await setChecklistItem(checkId, !item?.done);
  }

  async function setChecklistItem(checkId, done) {
    if (!checkId || state.updatingIds.has(checkId)) return;
    state.updatingIds.add(checkId);
    render();
    try {
      await window.apiClient.updateOnboardingChecklistItem(checkId, done);
      state.checklist = state.checklist.map((item) => item.id === checkId ? { ...item, done } : item);
      const allDone = state.checklist.length > 0 && state.checklist.every((item) => item.done);
      if (allDone) {
        await window.apiClient.completeOnboarding();
      }
    } catch (error) {
      state.error = error?.message || '更新清单失败';
    } finally {
      state.updatingIds.delete(checkId);
      render();
    }
  }

  function handleRetry() {
    load();
  }

  function render() {
    const root = document.querySelector('[data-onboarding-root]');
    if (root) mount(root);
  }

  return {
    state,
    load,
    render,
  };
})();
