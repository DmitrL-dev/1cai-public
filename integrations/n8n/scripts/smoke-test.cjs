const http = require('http');
const https = require('https');
const { URL } = require('url');

const baseUrl = process.env.N8N_BASE_URL || 'http://localhost:5678';
const login = process.env.N8N_USER_EMAIL || process.env.N8N_EMAIL;
const password = process.env.N8N_USER_PASSWORD || process.env.N8N_PASSWORD;
const ignoreSsl = process.env.N8N_IGNORE_SSL === 'true';

if (!login || !password) {
  console.error('✖ Требуются переменные окружения N8N_USER_EMAIL и N8N_USER_PASSWORD');
  process.exit(1);
}

const base = new URL(baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`);
const isHttps = base.protocol === 'https:';
const agent = isHttps && ignoreSsl ? new https.Agent({ rejectUnauthorized: false }) : undefined;

async function request(method, path, body, headers = {}, cookies = '') {
  const payload = body ? JSON.stringify(body) : undefined;
  const options = {
    protocol: base.protocol,
    hostname: base.hostname,
    port: base.port || (isHttps ? 443 : 80),
    path: path.startsWith('/') ? path : `/${path}`,
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(payload ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
      ...headers,
    },
    agent,
  };

  if (cookies) {
    options.headers.Cookie = cookies;
  }

  const httpModule = isHttps ? https : http;

  return new Promise((resolve, reject) => {
    const req = httpModule.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        const { statusCode } = res;
        const headers = res.headers;
        let parsed;
        if (data) {
          try {
            parsed = JSON.parse(data);
          } catch (error) {
            return reject(new Error(`Ошибка разбора JSON: ${error.message}\nОтвет: ${data}`));
          }
        }
        resolve({ statusCode, headers, body: parsed });
      });
    });

    req.on('error', (error) => {
      reject(error);
    });

    if (payload) {
      req.write(payload);
    }
    req.end();
  });
}

async function loginAndGetCookies() {
  const loginBody = {
    emailOrLdapLoginId: login,
    password,
  };

  const response = await request('POST', '/rest/login', loginBody);

  if (response.statusCode !== 200) {
    throw new Error(`Не удалось авторизоваться (код ${response.statusCode}): ${JSON.stringify(response.body)}`);
  }

  const setCookieHeader = response.headers['set-cookie'];
  if (!setCookieHeader || !setCookieHeader.length) {
    throw new Error('Сервер не вернул cookie после входа');
  }

  const cookie = setCookieHeader.map((entry) => entry.split(';')[0]).join('; ');
  return cookie;
}

function buildWorkflowData() {
  return {
    nodes: [
      {
        parameters: {},
        id: 'ManualTrigger',
        name: 'Manual Trigger',
        type: 'n8n-nodes-base.manualTrigger',
        typeVersion: 1,
        position: [300, 300],
      },
      {
        parameters: {
          resource: 'custom',
          customMethod: 'GET',
          customEndpoint: 'https://httpbin.org/get',
        },
        id: 'OneCaiNode',
        name: '1C AI Custom Request',
        type: '@onecai/n8n-nodes-onec-ai.oneCai',
        typeVersion: 1,
        position: [520, 300],
      },
    ],
    connections: {
      'Manual Trigger': {
        main: [
          [
            {
              node: '1C AI Custom Request',
              type: 'main',
              index: 0,
            },
          ],
        ],
      },
    },
  };
}

async function createWorkflow(cookies) {
  const workflowData = buildWorkflowData();
  const body = {
    name: 'Smoke Test 1C AI Stack',
    nodes: workflowData.nodes,
    connections: workflowData.connections,
    active: false,
  };

  const response = await request('POST', '/rest/workflows', body, {}, cookies);
  if (response.statusCode !== 200) {
    throw new Error(`Не удалось создать workflow (код ${response.statusCode}): ${JSON.stringify(response.body)}`);
  }

  const workflowId = response.body?.id || response.body?.data?.id;
  if (!workflowId) {
    throw new Error(`Не удалось получить id созданного workflow: ${JSON.stringify(response.body)}`);
  }

  return {
    id: workflowId,
    name: body.name,
    nodes: workflowData.nodes,
    connections: workflowData.connections,
  };
}

async function runWorkflow(workflow, cookies) {
  const response = await request(
    'POST',
    `/rest/workflows/${workflow.id}/run`,
    {
      startNodes: ['Manual Trigger'],
      runData: {},
      workflowData: {
        id: workflow.id,
        name: workflow.name,
        active: false,
        nodes: workflow.nodes,
        connections: workflow.connections,
      },
    },
    {},
    cookies,
  );

  if (response.statusCode !== 200) {
    throw new Error(`Ошибка выполнения workflow (код ${response.statusCode}): ${JSON.stringify(response.body)}`);
  }

  return response.body;
}

async function deleteWorkflow(workflowId, cookies) {
  await request('DELETE', `/rest/workflows/${workflowId}`, undefined, {}, cookies);
}

(async () => {
  let workflow;
  try {
    console.log(`→ Авторизация на ${base.href} как ${login}`);
    const cookies = await loginAndGetCookies();
    console.log('✓ Авторизация успешна');

    console.log('→ Запуск smoke-теста ноды 1C AI Stack…');
    workflow = await createWorkflow(cookies);
    let result;
    try {
      result = await runWorkflow(workflow, cookies);
      console.log('✓ Workflow выполнен успешно');
      console.log('Результат:', JSON.stringify(result, null, 2));
    } finally {
      if (workflow?.id) {
        try {
          await deleteWorkflow(workflow.id, cookies);
        } catch (cleanupError) {
          console.error('⚠ Не удалось удалить временный workflow:', cleanupError.message);
        }
      }
    }
  } catch (error) {
    console.error('✖ Ошибка при выполнении smoke-теста:', error.message);
    process.exit(1);
  }
})();

