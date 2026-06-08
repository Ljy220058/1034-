import { fetchActivityPhotos, uploadActivityPhotos } from './api.js';

const PHOTO_WALL_DEFAULTS = {
  activityId: '',
  title: '活动照片墙',
  subtitle: '上传活动现场照片，沉淀每一次相聚的精彩瞬间',
};

export function createPhotoWall(container, options = {}) {
  if (!container) {
    return null;
  }

  const settings = {
    ...PHOTO_WALL_DEFAULTS,
    ...options,
  };

  const state = {
    photos: [],
    loading: true,
    error: '',
    uploadError: '',
    uploadLoading: false,
    previewIndex: -1,
  };

  const refs = {};

  renderPhotoWall();
  bindPhotoWallEvents();
  loadPhotos();

  return {
    reload: loadPhotos,
  };

  async function loadPhotos() {
    state.loading = true;
    state.error = '';
    renderPhotoGrid();

    try {
      const payload = await fetchActivityPhotos(settings.activityId);
      state.photos = normalizePhotos(payload);
    } catch (error) {
      state.error = error.message || '照片加载失败，请稍后重试';
      state.photos = [];
    } finally {
      state.loading = false;
      renderPhotoGrid();
    }
  }

  async function handleUploadFiles(fileList) {
    const files = Array.from(fileList || []).filter((file) => file.type.startsWith('image/'));
    if (!files.length) {
      state.uploadError = '请选择图片文件后再上传';
      renderUploadStatus();
      return;
    }

    state.uploadLoading = true;
    state.uploadError = '';
    renderUploadStatus();

    try {
      await uploadActivityPhotos(settings.activityId, files);
      await loadPhotos();
      if (refs.fileInput) {
        refs.fileInput.value = '';
      }
    } catch (error) {
      state.uploadError = error.message || '上传失败，请稍后重试';
    } finally {
      state.uploadLoading = false;
      renderUploadStatus();
    }
  }

  function renderPhotoWall() {
    container.innerHTML = `
      <section class="photo-wall" aria-label="${settings.title}">
        <header class="photo-wall__header">
          <div>
            <p class="photo-wall__eyebrow">活动回顾</p>
            <h2>${settings.title}</h2>
            <p class="photo-wall__subtitle">${settings.subtitle}</p>
          </div>
          <button class="btn photo-wall__refresh" type="button" data-action="retry">刷新照片</button>
        </header>

        <section class="photo-wall__upload" aria-label="上传照片">
          <label class="photo-wall__dropzone" data-dropzone>
            <input class="photo-wall__input" type="file" accept="image/*" multiple data-file-input>
            <span class="photo-wall__dropicon">⇪</span>
            <strong>点击上传照片</strong>
            <span>或将图片拖拽到此处，支持多张同时上传</span>
          </label>
          <div class="photo-wall__actions">
            <button class="btn" type="button" data-action="trigger-upload">选择图片</button>
            <button class="btn btn--ghost" type="button" data-action="retry-upload" ${state.uploadLoading ? 'disabled' : ''}>重新上传</button>
          </div>
          <p class="photo-wall__hint" data-upload-status></p>
        </section>

        <section class="photo-wall__content">
          <div class="photo-wall__grid" data-photo-grid></div>
        </section>
      </section>

      <dialog class="photo-lightbox" data-lightbox>
        <article class="photo-lightbox__panel">
          <button class="photo-lightbox__close" type="button" aria-label="关闭预览" data-action="close-preview">×</button>
          <img class="photo-lightbox__image" alt="活动照片预览" data-preview-image>
          <footer class="photo-lightbox__footer">
            <p data-preview-caption>活动照片预览</p>
            <nav class="photo-lightbox__nav" aria-label="预览切换">
              <button class="btn btn--ghost" type="button" data-action="prev-photo">上一张</button>
              <button class="btn" type="button" data-action="next-photo">下一张</button>
            </nav>
          </footer>
        </article>
      </dialog>
    `;

    refs.grid = container.querySelector('[data-photo-grid]');
    refs.fileInput = container.querySelector('[data-file-input]');
    refs.dropzone = container.querySelector('[data-dropzone]');
    refs.uploadStatus = container.querySelector('[data-upload-status]');
    refs.lightbox = container.querySelector('[data-lightbox]');
    refs.previewImage = container.querySelector('[data-preview-image]');
    refs.previewCaption = container.querySelector('[data-preview-caption]');

    renderUploadStatus();
    renderPhotoGrid();
  }

  function bindPhotoWallEvents() {
    container.addEventListener('click', (event) => {
      const action = event.target.closest('[data-action]')?.dataset.action;
      if (!action) {
        return;
      }

      if (action === 'trigger-upload' || action === 'retry-upload') {
        refs.fileInput?.click();
      }

      if (action === 'retry') {
        loadPhotos();
      }

      if (action === 'close-preview') {
        closePreview();
      }

      if (action === 'prev-photo') {
        changePreview(-1);
      }

      if (action === 'next-photo') {
        changePreview(1);
      }
    });

    container.addEventListener('change', (event) => {
      if (event.target.matches('[data-file-input]')) {
        handleUploadFiles(event.target.files);
      }
    });

    refs.dropzone?.addEventListener('dragover', (event) => {
      event.preventDefault();
      refs.dropzone.classList.add('is-dragover');
    });

    refs.dropzone?.addEventListener('dragleave', () => {
      refs.dropzone.classList.remove('is-dragover');
    });

    refs.dropzone?.addEventListener('drop', (event) => {
      event.preventDefault();
      refs.dropzone.classList.remove('is-dragover');
      handleUploadFiles(event.dataTransfer?.files || []);
    });

    refs.lightbox?.addEventListener('close', () => {
      state.previewIndex = -1;
    });
  }

  function renderUploadStatus() {
    if (!refs.uploadStatus) {
      return;
    }

    if (state.uploadLoading) {
      refs.uploadStatus.textContent = '照片上传中，请稍候…';
      return;
    }

    if (state.uploadError) {
      refs.uploadStatus.textContent = state.uploadError;
      return;
    }

    refs.uploadStatus.textContent = '支持 JPG、PNG、WEBP 等常见图片格式';
  }

  function renderPhotoGrid() {
    if (!refs.grid) {
      return;
    }

    if (state.loading) {
      refs.grid.innerHTML = `
        <article class="photo-wall__state photo-wall__state--loading">
          <span class="spinner" aria-hidden="true"></span>
          <p>照片加载中…</p>
        </article>
      `;
      return;
    }

    if (state.error) {
      refs.grid.innerHTML = `
        <article class="photo-wall__state photo-wall__state--error">
          <p>${state.error}</p>
          <button class="btn" type="button" data-action="retry">重试</button>
        </article>
      `;
      return;
    }

    if (!state.photos.length) {
      refs.grid.innerHTML = `
        <article class="photo-wall__state photo-wall__state--empty">
          <p>暂无数据</p>
          <span>上传首张活动照片，补全本次活动回忆墙。</span>
        </article>
      `;
      return;
    }

    refs.grid.innerHTML = state.photos.map((photo, index) => `
      <button class="photo-card" type="button" data-photo-index="${index}">
        <img class="photo-card__image" src="${photo.url}" alt="${photo.alt}">
        <span class="photo-card__overlay">
          <strong>${photo.title}</strong>
          <small>${photo.caption}</small>
        </span>
      </button>
    `).join('');

    refs.grid.querySelectorAll('[data-photo-index]').forEach((button) => {
      button.addEventListener('click', () => {
        openPreview(Number(button.dataset.photoIndex || 0));
      });
    });
  }

  function openPreview(index) {
    state.previewIndex = index;
    syncPreview();
    refs.lightbox?.showModal();
  }

  function closePreview() {
    refs.lightbox?.close();
  }

  function changePreview(step) {
    if (!state.photos.length) {
      return;
    }
    state.previewIndex = (state.previewIndex + step + state.photos.length) % state.photos.length;
    syncPreview();
  }

  function syncPreview() {
    const photo = state.photos[state.previewIndex];
    if (!photo || !refs.previewImage || !refs.previewCaption) {
      return;
    }
    refs.previewImage.src = photo.url;
    refs.previewImage.alt = photo.alt;
    refs.previewCaption.textContent = `${photo.title} · ${photo.caption}`;
  }
}

function normalizePhotos(payload) {
  const list = Array.isArray(payload) ? payload : payload?.items || payload?.data || [];
  return list.map((item, index) => ({
    id: item.id || `photo-${index + 1}`,
    url: item.url || item.image_url || item.thumbnail_url || '',
    title: item.title || item.name || `活动照片 ${index + 1}`,
    caption: item.caption || item.description || '点击查看大图',
    alt: item.alt || item.title || item.name || `活动照片 ${index + 1}`,
  })).filter((item) => item.url);
}
