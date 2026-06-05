import { bootstrap, bootstrapConnectionStatus, bootstrapTaskCreator, bootstrapTaskList, buildUrl, createApiClient, normalizeConnectionStatus, setConnectionStatusView } from './api.js';
import { createTaskPreviewState, escapeHtml, formatDependencyIds, renderAnnouncements, renderConnectionStatus, renderTaskPreview, validateTaskForm } from './utils.js';

export {
  buildUrl,
  bootstrap,
  bootstrapConnectionStatus,
  bootstrapTaskCreator,
  bootstrapTaskList,
  createApiClient,
  createTaskPreviewState,
  escapeHtml,
  formatDependencyIds,
  normalizeConnectionStatus,
  renderAnnouncements,
  renderConnectionStatus,
  renderTaskPreview,
  setConnectionStatusView,
  validateTaskForm,
};

if (typeof window !== 'undefined') {
  window.RunningClubApp = {
    buildUrl,
    bootstrap,
    bootstrapConnectionStatus,
    bootstrapTaskCreator,
    bootstrapTaskList,
    createApiClient,
    createTaskPreviewState,
    escapeHtml,
    formatDependencyIds,
    normalizeConnectionStatus,
    renderAnnouncements,
    renderConnectionStatus,
    renderTaskPreview,
    setConnectionStatusView,
    validateTaskForm,
  };
}
