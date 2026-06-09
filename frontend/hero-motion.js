(()=>{
  "use strict";

  /**
 * 初始化首屏英雄区动效与交互状态。
 * @description 绑定按钮、可视区域观察器和计数器，驱动首屏卡片的轻量微交互。
 * @returns {void}
 */
function initHeroMotion() {
    const root = document.querySelector('[data-hero-motion]');
    if (!root) return;

    const title = root.querySelector('[data-hero-title]');
    const subtitle = root.querySelector('[data-hero-subtitle]');
    const status = root.querySelector('[data-hero-status]');
    const count = root.querySelector('[data-hero-count]');
    const primary = root.querySelector('[data-hero-primary]');
    const secondary = root.querySelector('[data-hero-secondary]');
    const chips = Array.from(root.querySelectorAll('[data-hero-chip]'));
    const lanes = Array.from(document.querySelectorAll('[data-hero-lane]'));

    let tick = 0;
    let chipIndex = 0;

    revealLanes(lanes);
    bindHeroButtons({ title, subtitle, status, count, primary, secondary, chips, lanes });
    updateHeroState({ title, subtitle, status, count, chips, tick });
    startHeroCounter({ count, lanes });
  }

  function revealLanes(lanes) {
    if (!('IntersectionObserver' in window)) {
      lanes.forEach((lane) => lane.setAttribute('data-in-view', 'true'));
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.setAttribute('data-in-view', 'true');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.18 });

    lanes.forEach((lane) => observer.observe(lane));
  }

  function bindHeroButtons(state) {
    state.primary?.addEventListener('click', () => {
      state.status.textContent = '正在播放';
      state.primary.disabled = true;
      state.secondary.disabled = true;
      animateHeroCards(state.chips, state.lanes);
      window.setTimeout(() => {
        state.primary.disabled = false;
        state.secondary.disabled = false;
        state.status.textContent = '播放完成';
      }, 760);
    });

    state.secondary?.addEventListener('click', () => {
      document.getElementById('卡片预览')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    state.chips.forEach((chip, index) => {
      chip.addEventListener('click', () => {
        state.chips.forEach((item) => item.setAttribute('data-active', 'false'));
        chip.setAttribute('data-active', 'true');
        state.status.textContent = index === 0 ? '悬停演示' : '点击演示';
      });
    });
  }

  function animateHeroCards(chips, lanes) {
    chips.forEach((chip, index) => {
      window.setTimeout(() => chip.setAttribute('data-active', String(index % 2 === 0)), index * 120);
    });
    lanes.forEach((lane, index) => {
      window.setTimeout(() => lane.classList.toggle('is-pulse', true), index * 100);
      window.setTimeout(() => lane.classList.toggle('is-pulse', false), 500 + index * 120);
    });
  }

  function updateHeroState(state) {
    if (state.title) state.title.textContent = '首屏进入动效方案';
    if (state.subtitle) state.subtitle.textContent = '首屏支持进入动画、按钮悬停反馈、滚动触发轻量微交互，保持暗色主题与大留白的视觉语言。';
    if (state.status) state.status.textContent = '等待交互';
    if (state.count) state.count.textContent = String(state.tick ?? 0);
  }

  function startHeroCounter(state) {
    if (!state.count) return;
    window.setInterval(() => {
      state.count.textContent = String((Number(state.count.textContent) + 1) % 99);
    }, 3200);
  }

  document.addEventListener('DOMContentLoaded', initHeroMotion);
})();
