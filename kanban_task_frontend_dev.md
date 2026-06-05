# Kanban Task

- Assignee: frontend-dev
- Title: Add a readiness badge to the frontend header
- Description: Display the backend /health/readiness summary in the top status area of frontend/index.html, including the ready/not-ready state and a compact missing-env warning when the app is not ready.
- Acceptance Criteria:
  1. Frontend shows a visible readiness indicator in the header.
  2. The indicator reflects the /health/readiness JSON response.
  3. Missing environment variables are shown in a concise, user-friendly message.
  4. Existing layout remains responsive on mobile.
- Suggested Files: frontend/index.html, frontend/app.js (if needed)
