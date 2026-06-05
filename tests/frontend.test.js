import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';

const apiModule = await import(pathToFileURL('/root/autodl-tmp/projects/hermes-swarm-lab/frontend/api.js'));
const utilsModule = await import(pathToFileURL('/root/autodl-tmp/projects/hermes-swarm-lab/frontend/utils.js'));
const {
  buildUrl,
  createApiClient,
  bootstrapTaskList,
} = apiModule;
const {
  escapeHtml,
  validateTaskForm,
  renderConnectionStatus,
} = utilsModule;

function test(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (error) {
    console.error(`not ok - ${name}`);
    throw error;
  }
}

function createForm(values) {
  return {
    title: { value: values.title ?? '' },
    assignee: { value: values.assignee ?? '' },
    status: { value: values.status ?? '' },
    priority: { value: values.priority ?? '' },
    dependencies: { value: values.dependencies ?? '' },
  };
}

function createTarget() {
  return {
    innerHTML: '',
  };
}

function createDocument(nodes) {
  return {
    querySelector(selector) {
      return nodes[selector] || null;
    },
  };
}

test('buildUrl trims base and appends query parameters', () => {
  assert.equal(
    buildUrl('https://example.com/api/', 'status', { page: 2, search: 'summer run', empty: '', ignored: null }),
    'https://example.com/api/status?page=2&search=summer+run',
  );
  assert.equal(buildUrl('', 'status'), '/status');
});

test('createApiClient serializes requests and returns data payloads', async () => {
  const calls = [];
  const client = createApiClient({
    baseUrl: '/api/v1/',
    fetchImpl: async (input, init = {}) => {
      calls.push({ input, init });
      return {
        ok: true,
        status: 200,
        async json() {
          return { data: { status: 'connected' } };
        },
      };
    },
  });

  const result = await client.getConnectionStatus();
  assert.deepEqual(result, { status: 'connected' });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].input, '/api/v1/status');
  assert.equal(calls[0].init.method, 'GET');
  assert.equal(calls[0].init.headers.Accept, 'application/json');
});

test('createApiClient surfaces backend errors with status and payload', async () => {
  const client = createApiClient({
    fetchImpl: async () => ({
      ok: false,
      status: 503,
      async json() {
        return { message: 'Service unavailable' };
      },
    }),
  });

  await assert.rejects(client.listActivities(), (error) => {
    assert.equal(error.message, 'Service unavailable');
    assert.equal(error.status, 503);
    assert.deepEqual(error.payload, { message: 'Service unavailable' });
    return true;
  });
});

test('escapeHtml encodes markup and quote characters', () => {
  assert.equal(
    escapeHtml(`5 < 7 & "run" 'club'`),
    '5 &lt; 7 &amp; &quot;run&quot; &#39;club&#39;',
  );
});

test('validateTaskForm reports missing and malformed fields', () => {
  const errors = validateTaskForm(createForm({
    title: '  ',
    assignee: '',
    status: '',
    priority: '',
    dependencies: '#t_bad123',
  }));

  assert.deepEqual(errors, [
    { field: 'title', message: '请输入任务标题。' },
    { field: 'assignee', message: '请选择负责人。' },
    { field: 'status', message: '请选择任务状态。' },
    { field: 'priority', message: '请选择优先级。' },
    { field: 'dependencies', message: '依赖项格式不正确，请使用 #t_xxxxxxxx 形式。' },
  ]);
});

test('validateTaskForm accepts a complete task draft', () => {
  assert.deepEqual(validateTaskForm(createForm({
    title: 'Track intervals',
    assignee: 'frontend-dev',
    status: 'todo',
    priority: 'high',
    dependencies: '#t_1234abcd, #t_9f8e7d6c',
  })), []);
});

test('renderConnectionStatus renders the badge, copy, and retry state', () => {
  const target = createTarget();
  renderConnectionStatus({ status: 'connected', message: 'All good', retryLabel: 'Refresh', canRetry: false }, target);

  assert.match(target.innerHTML, /data-connection-badge/);
  assert.match(target.innerHTML, /已连接/);
  assert.match(target.innerHTML, /All good/);
  assert.match(target.innerHTML, /disabled/);
});

test('bootstrapTaskList renders filtered tasks and action buttons', async () => {
  const nodes = {
    '[data-task-board]': { dataset: {}, addEventListener() {} },
    '[data-task-summary]': { innerHTML: '' },
    '[data-task-filter="assignee"]': { value: 'frontend-dev', addEventListener() {} },
    '[data-task-filter="status"]': { value: 'running', addEventListener() {} },
    '[data-task-refresh]': { addEventListener() {} },
    '[data-task-list]': { innerHTML: '' },
    '[data-task-state]': { innerHTML: '' },
  };
  const document = createDocument(nodes);
  const client = {
    async listTaskQueueTasks() {
      return {
        items: [
          {
            id: 't_1',
            title: 'Ship filters',
            status: 'running',
            assignee: 'frontend-dev',
            priority: 'high',
            workspace_path: '/root/autodl-tmp/projects/hermes-swarm-lab',
            body: 'Board filters and states',
            actions: [{ label: 'Open', tone: 'primary' }],
          },
          {
            id: 't_2',
            title: 'Other task',
            status: 'done',
            assignee: 'backend-dev',
          },
        ],
      };
    },
  };

  await bootstrapTaskList({ document, client });
  assert.match(nodes['[data-task-list]'].innerHTML, /Ship filters/);
  assert.match(nodes['[data-task-list]'].innerHTML, /Open/);
  assert.doesNotMatch(nodes['[data-task-list]'].innerHTML, /Other task/);
  assert.match(nodes['[data-task-summary]'].innerHTML, /总计 1/);
});

test('bootstrapTaskList falls back to empty state when no task list node is present', async () => {
  const nodes = {
    '[data-task-board]': { dataset: {}, addEventListener() {} },
  };
  const document = createDocument(nodes);
  const client = {
    async listTaskQueueTasks() {
      return [];
    },
  };

  const result = await bootstrapTaskList({ document, client });
  assert.deepEqual(result, []);
});

console.log('frontend helper tests complete');
