window.shareCardModule = (() => {
  "use strict";

  const DEFAULT_CARD = {
    title: "暮色巡游·第 12 场",
    time: "2026-06-18 19:30",
    location: "云岚公园东门集合",
    cover: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
    runner: "晨风跑团",
    route: "8.4km 夜跑环线",
  };

  const state = {
    card: { ...DEFAULT_CARD },
    previewUrl: "",
    copied: false,
    loading: false,
    error: "",
  };

  let refs = {};

  document.addEventListener('DOMContentLoaded', initShareCard);

  function initShareCard() {
    cacheRefs();
    bindEvents();
    syncFormToState();
    renderShareCard();
  }

  function cacheRefs() {
    refs.form = document.querySelector('[data-share-form]');
    refs.title = document.querySelector('[data-share-field="title"]');
    refs.time = document.querySelector('[data-share-field="time"]');
    refs.location = document.querySelector('[data-share-field="location"]');
    refs.cover = document.querySelector('[data-share-field="cover"]');
    refs.runner = document.querySelector('[data-share-field="runner"]');
    refs.route = document.querySelector('[data-share-field="route"]');
    refs.preview = document.querySelector('[data-share-preview]');
    refs.canvas = document.querySelector('[data-share-canvas]');
    refs.copy = document.querySelector('[data-share-copy]');
    refs.refresh = document.querySelector('[data-share-refresh]');
    refs.download = document.querySelector('[data-share-download]');
    refs.status = document.querySelector('[data-share-status]');
    refs.empty = document.querySelector('[data-share-empty]');
    refs.error = document.querySelector('[data-share-error]');
    refs.coverInput = document.querySelector('[data-share-cover-input]');
  }

  function bindEvents() {
    refs.form?.addEventListener('submit', handleSubmit);
    refs.copy?.addEventListener('click', handleCopyLink);
    refs.refresh?.addEventListener('click', handleRefreshPreview);
    refs.download?.addEventListener('click', handleDownloadPreview);
    refs.coverInput?.addEventListener('change', handleCoverUpload);
    [refs.title, refs.time, refs.location, refs.cover, refs.runner, refs.route].forEach((input) => {
      input?.addEventListener('input', handleFieldChange);
    });
  }

  function syncFormToState() {
    state.card.title = refs.title?.value.trim() || DEFAULT_CARD.title;
    state.card.time = refs.time?.value.trim() || DEFAULT_CARD.time;
    state.card.location = refs.location?.value.trim() || DEFAULT_CARD.location;
    state.card.cover = refs.cover?.value.trim() || DEFAULT_CARD.cover;
    state.card.runner = refs.runner?.value.trim() || DEFAULT_CARD.runner;
    state.card.route = refs.route?.value.trim() || DEFAULT_CARD.route;
  }

  function handleFieldChange() {
    syncFormToState();
    state.error = '';
    state.copied = false;
    renderShareCard();
  }

  function handleSubmit(event) {
    event.preventDefault();
    syncFormToState();
    drawPreview();
    renderShareCard();
  }

  function handleRefreshPreview() {
    state.loading = true;
    renderShareCard();
    window.requestAnimationFrame(() => {
      drawPreview();
      state.loading = false;
      renderShareCard();
    });
  }

  async function handleCopyLink() {
    try {
      const preview = await buildSharePreviewUrl();
      await navigator.clipboard.writeText(preview);
      state.copied = true;
      state.error = '';
    } catch (error) {
      state.error = '复制失败，请手动下载预览图后分享。';
      state.copied = false;
    }
    renderShareCard();
  }

  function handleDownloadPreview() {
    const canvas = refs.canvas;
    if (!canvas) return;
    const link = document.createElement('a');
    link.href = canvas.toDataURL('image/png');
    link.download = `share-card-${Date.now()}.png`;
    link.click();
  }

  function handleCoverUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      refs.cover.value = String(reader.result || DEFAULT_CARD.cover);
      syncFormToState();
      drawPreview();
      renderShareCard();
    };
    reader.readAsDataURL(file);
  }

  function drawPreview() {
    const canvas = refs.canvas;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = 1080;
    const height = 1920;
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.aspectRatio = `${width} / ${height}`;
    ctx.scale(ratio, ratio);

    drawBackdrop(ctx, width, height);
    drawCover(ctx, width, height, state.card.cover);
    drawOverlay(ctx, width, height);
    drawText(ctx, width, height);
  }

  function drawBackdrop(ctx, width, height) {
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, '#0b1728');
    gradient.addColorStop(0.5, '#08111d');
    gradient.addColorStop(1, '#13253f');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = 'rgba(56, 189, 248, 0.08)';
    ctx.beginPath();
    ctx.arc(width * 0.8, height * 0.18, 250, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = 'rgba(34, 197, 94, 0.08)';
    ctx.beginPath();
    ctx.arc(width * 0.18, height * 0.12, 220, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawCover(ctx, width, height, coverUrl) {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      ctx.save();
      ctx.globalAlpha = 0.92;
      ctx.drawImage(img, 120, 180, width - 240, 940);
      ctx.restore();
    };
    img.onerror = () => {
      ctx.fillStyle = 'rgba(255,255,255,0.06)';
      ctx.fillRect(120, 180, width - 240, 940);
    };
    img.src = coverUrl || DEFAULT_CARD.cover;
  }

  function drawOverlay(ctx, width, height) {
    const gradient = ctx.createLinearGradient(0, 1120, 0, height);
    gradient.addColorStop(0, 'rgba(8,17,29,0)');
    gradient.addColorStop(1, 'rgba(8,17,29,0.94)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 980, width, height - 980);
  }

  function drawText(ctx, width, height) {
    ctx.fillStyle = '#ecf4ff';
    ctx.font = '700 72px Inter, sans-serif';
    wrapText(ctx, state.card.title, 120, 1180, width - 240, 88);
    ctx.font = '500 38px Inter, sans-serif';
    ctx.fillStyle = '#9fb2ca';
    ctx.fillText(state.card.runner, 120, 1320);
    ctx.fillStyle = '#38bdf8';
    ctx.fillText(state.card.route, 120, 1380);
    ctx.fillStyle = '#ecf4ff';
    ctx.fillText(`时间：${state.card.time}`, 120, 1490);
    ctx.fillText(`地点：${state.card.location}`, 120, 1560);
    ctx.fillStyle = '#bdeaff';
    ctx.fillText('长按保存分享图 · 1034 跑团管理系统', 120, 1700);
  }

  function wrapText(ctx, text, x, y, maxWidth, lineHeight) {
    const words = String(text).split('');
    let line = '';
    let currentY = y;
    words.forEach((char) => {
      const testLine = line + char;
      const metrics = ctx.measureText(testLine);
      if (metrics.width > maxWidth && line) {
        ctx.fillText(line, x, currentY);
        line = char;
        currentY += lineHeight;
      } else {
        line = testLine;
      }
    });
    if (line) ctx.fillText(line, x, currentY);
  }

  async function buildSharePreviewUrl() {
    if (!refs.canvas) return '';
    if (!refs.canvas.width) drawPreview();
    return refs.canvas.toDataURL('image/png');
  }

  function renderShareCard() {
    if (refs.preview) {
      refs.preview.hidden = false;
      refs.preview.setAttribute('aria-busy', String(state.loading));
    }
    if (refs.status) {
      refs.status.textContent = state.copied ? '已复制分享预览图链接' : state.loading ? '正在生成分享预览图' : '可编辑后生成分享海报';
    }
    if (refs.error) {
      refs.error.hidden = !state.error;
      refs.error.textContent = state.error;
    }
    if (refs.empty) {
      refs.empty.hidden = !!state.card.title;
    }
    if (refs.copy) refs.copy.textContent = state.copied ? '已复制' : '复制预览图';
  }

  return { initShareCard, drawPreview };
})();
