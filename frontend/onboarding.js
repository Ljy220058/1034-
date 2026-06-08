(()=>{
  "use strict";

  const STORAGE_KEY = "1034.onboarding.state.v1";
  const API_BASE = "/api/v1";

  const STEPS = [
    {
      id: "profile",
      title: "完善个人信息",
      detail: "确认头像、昵称与常用配速，方便系统快速识别你的跑团身份。",
      action: "查看个人资料",
    },
    {
      id: "buddy",
      title: "选择老带新搭档",
      detail: "从当前队伍里挑一个带跑搭档，协助你完成前几次训练和活动签到。",
      action: "选择搭档",
    },
    {
      id: "checklist",
      title: "完成欢迎清单",
      detail: "勾选待办事项，像设置通知、加入群组和确认首个目标训练。",
      action: "查看清单",
    },
  ];

  const FALLBACK_BUDDIES = [
    { id: "u-001", name: "林远", pace: "5'45\"/km", mileage: "累计 420 km", avatar: "LY" },
    { id: "u-002", name: "周岚", pace: "5'10\"/km", mileage: "累计 860 km", avatar: "ZL" },
    { id: "u-003", name: "陈洲", pace: "4'55\"/km", mileage: "累计 1280 km", avatar: "CZ" },
  ];

  const FALLBACK_CHECKLIST = [
    { id: "check-1", label: "完成昵称与头像设置", done: true },
    { id: "check-2", label: "选择一位老带新搭档", done: false },
    { id: "check-3", label: "加入首次训练提醒", done: false },
    { id: "check-4", label: "确认本周首个跑步目标", done: false },
  ];

  const state = {
    loading: true,
    error: "",
    stepIndex: 0,
    buddies: [],
    checklist: [],
    selectedBuddyId: "",
    checklistDone: new Set(),
    profileName: "晨跑小白",
  };

  const refs = {};

  document.addEventListener("DOMContentLoaded", initOnboarding);

  function initOnboarding() {
    cacheRefs();
    if (!refs.root) return;
    bindEvents();
    restoreState();
    loadOnboardingData();
  }

  function cacheRefs() {
    refs.root = document.querySelector("[data-onboarding]");
    refs.stepRail = document.querySelector("[data-onboarding-step-rail]");
    refs.stepTitle = document.querySelector("[data-onboarding-step-title]");
    refs.stepDetail = document.querySelector("[data-onboarding-step-detail]");
    refs.stepAction = document.querySelector("[data-onboarding-step-action]");
    refs.stepMeta = document.querySelector("[data-onboarding-step-meta]");
    refs.buddyGrid = document.querySelector("[data-onboarding-buddy-grid]");
    refs.buddySummary = document.querySelector("[data-onboarding-buddy-summary]");
    refs.checklist = document.querySelector("[data-onboarding-checklist]");
    refs.status = document.querySelector("[data-onboarding-status]");
    refs.retry = document.querySelector("[data-onboarding-retry]");
    refs.next = document.querySelector("[data-onboarding-next]");
    refs.prev = document.querySelector("[data-onboarding-prev]");
    refs.refresh = document.querySelector("[data-onboarding-refresh]");
    refs.profileName = document.querySelector("[data-onboarding-profile-name]");
    refs.profileAvatar = document.querySelector("[data-onboarding-profile-avatar]");
    refs.profileInput = document.querySelector("[data-onboarding-profile-input]");
  }

  function bindEvents() {
    refs.retry?.addEventListener("click", loadOnboardingData);
    refs.refresh?.addEventListener("click", loadOnboardingData);
    refs.next?.addEventListener("click", handleNextStep);
    refs.prev?.addEventListener("click", handlePrevStep);
    refs.profileInput?.addEventListener("input", handleProfileNameChange);
    refs.root?.addEventListener("click", handleRootClick);
  }

  function restoreState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (!saved) return;
      state.stepIndex = Number(saved.stepIndex ?? 0);
      state.selectedBuddyId = saved.selectedBuddyId || "";
      state.profileName = saved.profileName || state.profileName;
      state.checklistDone = new Set(Array.isArray(saved.checklistDone) ? saved.checklistDone : []);
      if (refs.profileInput) refs.profileInput.value = state.profileName;
    } catch {
      state.error = "本地进度恢复失败";
    }
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      stepIndex: state.stepIndex,
      selectedBuddyId: state.selectedBuddyId,
      profileName: state.profileName,
      checklistDone: Array.from(state.checklistDone),
    }));
  }

  async function loadOnboardingData() {
    state.loading = true;
    state.error = "";
    renderAll();
    try {
      const [buddies, checklist] = await Promise.all([fetchBuddies(), fetchWelcomeChecklist()]);
      state.buddies = buddies;
      state.checklist = checklist;
      if (!state.selectedBuddyId && state.buddies[0]) {
        state.selectedBuddyId = state.buddies[0].id;
      }
      if (state.checklistDone.size === 0) {
        state.checklistDone = new Set(state.checklist.filter((item) => item.done).map((item) => item.id));
      }
    } catch (error) {
      state.error = error?.message || "加载新手引导失败，已切换到本地示例。";
      state.buddies = FALLBACK_BUDDIES;
      state.checklist = FALLBACK_CHECKLIST;
      if (!state.selectedBuddyId && state.buddies[0]) {
        state.selectedBuddyId = state.buddies[0].id;
      }
      if (state.checklistDone.size === 0) {
        state.checklistDone = new Set(state.checklist.filter((item) => item.done).map((item) => item.id));
      }
    } finally {
      state.loading = false;
      renderAll();
      saveState();
    }
  }

  async function fetchBuddies() {
    const response = await fetch(`${API_BASE}/members?role=member`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("新手搭档接口请求失败");
    const payload = await response.json();
    const list = Array.isArray(payload) ? payload : payload?.data || payload?.items || payload?.members || [];
    return list.map((item, index) => ({
      id: item.id || item.member_id || `buddy-${index + 1}`,
      name: item.name || item.nickname || `成员 ${index + 1}`,
      pace: item.pace || item.avg_pace || "--",
      mileage: item.mileage || item.total_distance || item.running_years ? `累计 ${Number(item.total_distance || item.mileage || item.usual_distance_km || 0)} km` : "累计数据待补充",
      avatar: String(item.name || item.nickname || `成员${index + 1}`).slice(0, 2),
    }));
  }

  async function fetchWelcomeChecklist() {
    const response = await fetch(`${API_BASE}/members/onboarding-checklist`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("欢迎清单接口请求失败");
    const payload = await response.json();
    const list = Array.isArray(payload) ? payload : payload?.data || payload?.items || [];
    return list.map((item, index) => ({
      id: item.id || item.check_id || `check-${index + 1}`,
      label: item.label || item.title || item.name || `待办事项 ${index + 1}`,
      done: Boolean(item.done ?? item.completed ?? item.checked),
    }));
  }

  function renderAll() {
    renderStatus();
    renderStepRail();
    renderStepDetail();
    renderBuddies();
    renderChecklist();
  }

  function renderStatus() {
    if (!refs.status) return;
    const completeCount = state.checklist.filter((item) => state.checklistDone.has(item.id)).length;
    refs.status.innerHTML = `
      <div class="panel-state ${state.error ? "is-error" : state.loading ? "" : "is-success"}">
        <div class="state-inline">
          ${state.loading ? '<span class="spinner" aria-hidden="true"></span>' : ""}
          <h3>${state.loading ? "引导加载中" : state.error ? "加载异常" : "欢迎加入"}</h3>
        </div>
        <p>${escapeHtml(state.error || `已完成 ${completeCount}/${state.checklist.length || 0} 项欢迎清单。`)}</p>
        ${state.error ? '<button class="btn btn-primary" type="button" data-onboarding-retry>重试</button>' : ""}
      </div>
    `;
    refs.retry = document.querySelector("[data-onboarding-retry]");
    refs.retry?.addEventListener("click", loadOnboardingData);
  }

  function renderStepRail() {
    if (!refs.stepRail) return;
    refs.stepRail.innerHTML = STEPS.map((step, index) => `
      <button class="onboarding-step ${index === state.stepIndex ? "is-active" : ""} ${index < state.stepIndex ? "is-done" : ""}" type="button" data-onboarding-step="${index}">
        <span>${index < state.stepIndex ? "✓" : index + 1}</span>
        <strong>${escapeHtml(step.title)}</strong>
      </button>
    `).join("");
  }

  function renderStepDetail() {
    const current = STEPS[state.stepIndex] || STEPS[0];
    if (refs.stepTitle) refs.stepTitle.textContent = current.title;
    if (refs.stepDetail) refs.stepDetail.textContent = current.detail;
    if (refs.stepAction) refs.stepAction.textContent = current.action;
    if (refs.stepMeta) refs.stepMeta.textContent = `第 ${state.stepIndex + 1} 步 / 共 ${STEPS.length} 步`;
  }

  function renderBuddies() {
    if (!refs.buddyGrid) return;
    refs.buddyGrid.innerHTML = state.buddies.map((buddy) => `
      <button class="buddy-card ${buddy.id === state.selectedBuddyId ? "is-selected" : ""}" type="button" data-buddy-id="${escapeHtml(buddy.id)}">
        <span class="buddy-card__avatar" aria-hidden="true">${escapeHtml(buddy.avatar)}</span>
        <strong>${escapeHtml(buddy.name)}</strong>
        <span>${escapeHtml(buddy.pace)}</span>
        <small>${escapeHtml(buddy.mileage)}</small>
      </button>
    `).join("") || `<div class="panel-state"><h3>暂无搭档数据</h3><p>暂无数据</p></div>`;
    if (refs.buddySummary) {
      const selected = state.buddies.find((item) => item.id === state.selectedBuddyId) || state.buddies[0];
      refs.buddySummary.textContent = selected ? `当前选择：${selected.name}，配速 ${selected.pace}` : "暂无数据";
    }
  }

  function renderChecklist() {
    if (!refs.checklist) return;
    if (!state.checklist.length) {
      refs.checklist.innerHTML = '<div class="panel-state"><h3>暂无数据</h3><p>暂无数据</p></div>';
      return;
    }
    refs.checklist.innerHTML = state.checklist.map((item) => {
      const checked = state.checklistDone.has(item.id);
      return `
        <label class="check-item ${checked ? "is-done" : ""}">
          <input type="checkbox" data-checklist-id="${escapeHtml(item.id)}" ${checked ? "checked" : ""} />
          <span>
            <strong>${escapeHtml(item.label)}</strong>
            <small>${checked ? "已完成" : "待完成"}</small>
          </span>
        </label>
      `;
    }).join("");
  }

  function handleRootClick(event) {
    const stepButton = event.target.closest("[data-onboarding-step]");
    if (stepButton) {
      state.stepIndex = Number(stepButton.dataset.onboardingStep || 0);
      renderStepRail();
      renderStepDetail();
      saveState();
      return;
    }
    const buddyButton = event.target.closest("[data-buddy-id]");
    if (buddyButton) {
      state.selectedBuddyId = buddyButton.dataset.buddyId || "";
      renderBuddies();
      saveState();
      return;
    }
    const checkbox = event.target.closest("[data-checklist-id]");
    if (checkbox) {
      if (checkbox.checked) state.checklistDone.add(checkbox.dataset.checklistId || "");
      else state.checklistDone.delete(checkbox.dataset.checklistId || "");
      renderChecklist();
      renderStatus();
      saveState();
    }
  }

  function handleNextStep() {
    state.stepIndex = Math.min(state.stepIndex + 1, STEPS.length - 1);
    renderStepRail();
    renderStepDetail();
    saveState();
  }

  function handlePrevStep() {
    state.stepIndex = Math.max(state.stepIndex - 1, 0);
    renderStepRail();
    renderStepDetail();
    saveState();
  }

  function handleProfileNameChange(event) {
    state.profileName = event.target.value.trim() || "晨跑小白";
    if (refs.profileName) refs.profileName.textContent = state.profileName;
    if (refs.profileAvatar) refs.profileAvatar.textContent = String(state.profileName).slice(0, 2);
    saveState();
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
})();
