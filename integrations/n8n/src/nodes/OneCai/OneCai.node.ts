import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	IDataObject,
	JsonObject,
} from 'n8n-workflow';
import { NodeApiError, NodeOperationError } from 'n8n-workflow';

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

const DEFAULT_ENDPOINTS = {
	semanticSearch: '/api/search/semantic',
	graphQuery: '/api/graph/query',
	graphDependencies: '/api/graph/dependencies',
	graphConfigurations: '/api/graph/configurations',
	graphObjects: '/api/graph/objects',
	codeReviewAnalyze: '/api/code-review/analyze',
	testGeneration: '/api/test-generation/generate',
	statsOverview: '/api/stats/overview',
	health: '/health',
};

interface AdditionalFields extends IDataObject {
	endpoint?: string;
	headers?: IDataObject;
}

const ensureTrailingSlashRemoved = (url: string): string => url.replace(/\/+$/, '');

async function oneCaiApiRequest(
	this: IExecuteFunctions,
	method: HttpMethod,
	path: string,
	body: IDataObject = {},
	qs: IDataObject = {},
	additionalFields: AdditionalFields = {},
): Promise<IDataObject | IDataObject[]> {
	const credentials = await this.getCredentials('oneCaiApi');

	if (!credentials) {
		throw new NodeOperationError(this.getNode(), 'Credentials are not set for 1C AI Stack API');
	}

	const { baseUrl } = credentials as IDataObject;

	if (!baseUrl) {
		throw new NodeOperationError(this.getNode(), 'Base URL is required in credentials');
	}

	const sanitizedBaseUrl = ensureTrailingSlashRemoved(baseUrl as string);
	const sanitizedPath = path.startsWith('/') ? path : `/${path}`;

	const options: IDataObject = {
		method,
		url: `${sanitizedBaseUrl}${sanitizedPath}`,
		json: true,
		qs: Object.keys(qs).length ? qs : undefined,
		body: Object.keys(body).length ? body : undefined,
		headers: {
			'Content-Type': 'application/json',
			Accept: 'application/json',
			...(additionalFields.headers ?? {}),
		},
	};

	if (credentials.ignoreSslIssues === true) {
		options.rejectUnauthorized = false;
	}

	try {
		return await this.helpers.requestWithAuthentication.call(this, 'oneCaiApi', options);
	} catch (error) {
		const err = error as JsonObject;
		const responseBody = err?.response?.body;
		if (responseBody) {
			err.message = `${err.message} - ${JSON.stringify(responseBody)}`;
		}
		throw new NodeApiError(this.getNode(), err);
	}
}

export class OneCai implements INodeType {
	description: INodeTypeDescription = {
		displayName: '1C AI Stack',
		name: 'oneCai',
	icon: 'file:icons/onecai.svg',
		group: ['transform'],
		inputs: ['main'],
		outputs: ['main'],
		version: 1,
		defaults: {
			name: '1C AI Stack',
		},
		description: 'Взаимодействие с API Enterprise 1C AI Stack из n8n',
		subtitle: '={{$parameter["resource"] + ": " + $parameter["operation"]}}',
	documentationUrl: 'https://github.com/DmitrL-dev/1cai-public',
	codex: {
		categories: ['AI', '1C'],
	},
		properties: [
			{
				displayName: 'Resource',
				name: 'resource',
				type: 'options',
				noDataExpression: true,
			options: [
				{
					name: '🔍 Semantic Search',
						value: 'semanticSearch',
						description: 'Поиск по базе знаний с помощью Qdrant',
					},
					{
					name: '🕸️ Graph',
						value: 'graph',
						description: 'Neo4j граф зависимостей конфигураций 1С',
					},
					{
					name: '🛡️ Code Review',
						value: 'codeReview',
						description: 'Анализ кода и автоисправление',
					},
					{
					name: '🧪 Test Generation',
						value: 'testGeneration',
						description: 'Генерация тестов и метрики покрытия',
					},
					{
					name: '📊 Statistics',
						value: 'stats',
						description: 'Статистика и health-check сервисов',
					},
					{
					name: '⚙️ Custom Request',
						value: 'custom',
						description: 'Произвольный HTTP запрос к API',
					},
				],
				default: 'semanticSearch',
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				displayOptions: {
					show: {
						resource: ['semanticSearch'],
					},
				},
			options: [
				{
					name: '🔎 Run Semantic Search',
					value: 'search',
					action: 'Run semantic search',
					description: 'Семантический поиск по базе знаний',
				},
				],
				default: 'search',
			},
			{
				displayName: 'Query',
				name: 'query',
				type: 'string',
				required: true,
				displayOptions: {
					show: {
						resource: ['semanticSearch'],
						operation: ['search'],
					},
				},
				default: '',
				placeholder: 'например, расчет НДС в УТ 11',
				description: 'Поисковый запрос на естественном языке',
			},
			{
				displayName: 'Configuration',
				name: 'configuration',
				type: 'string',
				displayOptions: {
					show: {
						resource: ['semanticSearch'],
						operation: ['search'],
					},
				},
				default: '',
				description: 'Опциональный фильтр по конфигурации (например, ERP, УТ, ЗУП)',
			},
			{
				displayName: 'Limit',
				name: 'limit',
				type: 'number',
				typeOptions: {
					minValue: 1,
					maxValue: 50,
				},
				displayOptions: {
					show: {
						resource: ['semanticSearch'],
						operation: ['search'],
					},
				},
				default: 10,
				description: 'Количество результатов поиска',
			},
			{
				displayName: 'Additional Fields',
				name: 'searchAdditionalFields',
				type: 'collection',
				placeholder: 'Добавить поле',
				displayOptions: {
					show: {
						resource: ['semanticSearch'],
						operation: ['search'],
					},
				},
				default: {},
				options: [
					{
						displayName: 'Endpoint Override',
						name: 'endpoint',
						type: 'string',
						default: '',
						description: 'Путь до эндпоинта (по умолчанию /api/search/semantic)',
					},
					{
						displayName: 'Custom Headers (JSON)',
						name: 'headers',
						type: 'json',
						default: {},
						description: 'Дополнительные заголовки запроса',
					},
				],
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				displayOptions: {
					show: {
						resource: ['graph'],
					},
				},
			options: [
				{
					name: '🧠 Custom Cypher Query',
					value: 'query',
					action: 'Run custom Cypher query',
					description: 'Выполнить произвольный Cypher запрос',
				},
				{
					name: '🔗 Function Dependencies',
					value: 'dependencies',
					action: 'Trace function dependencies',
					description: 'Получить граф вызовов функции',
				},
				{
					name: '📚 List Configurations',
					value: 'configurations',
					action: 'List configurations',
					description: 'Получить список доступных конфигураций',
				},
				{
					name: '🧱 List Objects',
					value: 'objects',
					action: 'List configuration objects',
					description: 'Получить список объектов конфигурации',
				},
				],
				default: 'configurations',
			},
			{
				displayName: 'Cypher Query',
				name: 'cypherQuery',
				type: 'string',
				typeOptions: {
					rows: 5,
				},
				displayOptions: {
					show: {
						resource: ['graph'],
						operation: ['query'],
					},
				},
				default: 'MATCH (c:Configuration) RETURN c LIMIT 10',
				description: 'Cypher запрос к Neo4j графу',
			},
			{
				displayName: 'Query Parameters (JSON)',
				name: 'queryParameters',
				type: 'json',
				displayOptions: {
					show: {
						resource: ['graph'],
						operation: ['query'],
					},
				},
				default: '',
				description: 'Параметры запроса в формате JSON',
			},
			{
				displayName: 'Module Name',
				name: 'moduleName',
				type: 'string',
				displayOptions: {
					show: {
						resource: ['graph'],
						operation: ['dependencies'],
					},
				},
				required: true,
				default: '',
				description: 'Имя модуля, например, Документ.РеализацияТоваровУслуг.МодульОбъекта',
			},
			{
				displayName: 'Function Name',
				name: 'functionName',
				type: 'string',
				displayOptions: {
					show: {
						resource: ['graph'],
						operation: ['dependencies'],
					},
				},
				required: true,
				default: '',
				description: 'Имя функции, например, РассчитатьНДС',
			},
			{
				displayName: 'Configuration Name',
				name: 'configurationName',
				type: 'string',
				displayOptions: {
					show: {
						resource: ['graph'],
						operation: ['objects'],
					},
				},
				required: true,
				default: '',
				description: 'Имя конфигурации (например, ERP, УТ, ЗУП)',
			},
			{
				displayName: 'Object Type',
				name: 'objectType',
				type: 'string',
				displayOptions: {
					show: {
						resource: ['graph'],
						operation: ['objects'],
					},
				},
				default: '',
				description: 'Фильтр по типу объекта (Документ, Справочник, ПланВидовРасчета и т.д.)',
			},
			{
				displayName: 'Additional Fields',
				name: 'graphAdditionalFields',
				type: 'collection',
				placeholder: 'Добавить поле',
				displayOptions: {
					show: {
						resource: ['graph'],
					},
				},
				default: {},
				options: [
					{
						displayName: 'Endpoint Override',
						name: 'endpoint',
						type: 'string',
						default: '',
						description: 'Переопределить путь эндпоинта (например, /api/graph/query)',
					},
					{
						displayName: 'Custom Headers (JSON)',
						name: 'headers',
						type: 'json',
						default: {},
						description: 'Дополнительные заголовки запроса',
					},
				],
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				displayOptions: {
					show: {
						resource: ['codeReview'],
					},
				},
			options: [
				{
					name: '🛠️ Analyze Code',
					value: 'analyze',
					action: 'Analyze code quality',
					description: 'Получить рекомендации по коду',
				},
				],
				default: 'analyze',
			},
			{
				displayName: 'Code',
				name: 'code',
				type: 'string',
				typeOptions: {
					rows: 6,
				},
				displayOptions: {
					show: {
						resource: ['codeReview'],
						operation: ['analyze'],
					},
				},
				required: true,
				default: '',
				description: 'Фрагмент кода для анализа',
			},
			{
				displayName: 'Language',
				name: 'language',
				type: 'options',
				options: [
					{ name: 'BSL', value: 'bsl' },
					{ name: 'TypeScript', value: 'typescript' },
					{ name: 'JavaScript', value: 'javascript' },
					{ name: 'Python', value: 'python' },
					{ name: 'Java', value: 'java' },
					{ name: 'C#', value: 'csharp' },
				],
				displayOptions: {
					show: {
						resource: ['codeReview'],
						operation: ['analyze'],
					},
				},
				default: 'bsl',
			},
			{
				displayName: 'File Name',
				name: 'fileName',
				type: 'string',
				displayOptions: {
					show: {
						resource: ['codeReview'],
						operation: ['analyze'],
					},
				},
				default: '',
			},
			{
				displayName: 'Project Context (JSON)',
				name: 'projectContext',
				type: 'json',
				displayOptions: {
					show: {
						resource: ['codeReview'],
						operation: ['analyze'],
					},
				},
				default: '',
			},
			{
				displayName: 'Additional Fields',
				name: 'codeReviewAdditionalFields',
				type: 'collection',
				displayOptions: {
					show: {
						resource: ['codeReview'],
						operation: ['analyze'],
					},
				},
				default: {},
				options: [
					{
						displayName: 'Recent Changes (JSON Array)',
						name: 'recentChanges',
						type: 'json',
						default: '',
						description: 'Список последних изменений (строки кода)',
					},
					{
						displayName: 'Cursor Position (JSON)',
						name: 'cursorPosition',
						type: 'json',
						default: '',
					},
					{
						displayName: 'Endpoint Override',
						name: 'endpoint',
						type: 'string',
						default: '',
						description: 'Путь до эндпоинта (по умолчанию /api/code-review/analyze)',
					},
					{
						displayName: 'Custom Headers (JSON)',
						name: 'headers',
						type: 'json',
						default: {},
					},
				],
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				displayOptions: {
					show: {
						resource: ['testGeneration'],
					},
				},
			options: [
				{
					name: '🧪 Generate Tests',
					value: 'generate',
					action: 'Generate tests',
					description: 'Создать тесты для кода',
				},
				],
				default: 'generate',
			},
			{
				displayName: 'Code',
				name: 'testCode',
				type: 'string',
				typeOptions: {
					rows: 6,
				},
				displayOptions: {
					show: {
						resource: ['testGeneration'],
						operation: ['generate'],
					},
				},
				required: true,
				default: '',
				description: 'Исходный код для генерации тестов',
			},
			{
				displayName: 'Language',
				name: 'testLanguage',
				type: 'options',
				options: [
					{ name: 'BSL', value: 'bsl' },
					{ name: 'TypeScript', value: 'typescript' },
					{ name: 'python', value: 'python' },
					{ name: 'javascript', value: 'javascript' },
				],
				displayOptions: {
					show: {
						resource: ['testGeneration'],
						operation: ['generate'],
					},
				},
				default: 'bsl',
			},
			{
				displayName: 'Test Type',
				name: 'testType',
				type: 'options',
				options: [
					{ name: 'Unit', value: 'unit' },
					{ name: 'Integration', value: 'integration' },
					{ name: 'End-to-End', value: 'e2e' },
					{ name: 'All', value: 'all' },
				],
				displayOptions: {
					show: {
						resource: ['testGeneration'],
						operation: ['generate'],
					},
				},
				default: 'unit',
			},
			{
				displayName: 'Include Edge Cases',
				name: 'includeEdgeCases',
				type: 'boolean',
				displayOptions: {
					show: {
						resource: ['testGeneration'],
						operation: ['generate'],
					},
				},
				default: true,
			},
			{
				displayName: 'Framework',
				name: 'framework',
				type: 'string',
				displayOptions: {
					show: {
						resource: ['testGeneration'],
						operation: ['generate'],
					},
				},
				default: '',
				description: 'Опционально: указать фреймворк тестирования',
			},
			{
				displayName: 'Additional Fields',
				name: 'testAdditionalFields',
				type: 'collection',
				displayOptions: {
					show: {
						resource: ['testGeneration'],
						operation: ['generate'],
					},
				},
				default: {},
				options: [
					{
						displayName: 'Endpoint Override',
						name: 'endpoint',
						type: 'string',
						default: '',
						description: 'Путь до эндпоинта (по умолчанию /api/test-generation/generate)',
					},
					{
						displayName: 'Custom Headers (JSON)',
						name: 'headers',
						type: 'json',
						default: {},
					},
				],
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				displayOptions: {
					show: {
						resource: ['stats'],
					},
				},
			options: [
				{
					name: '📊 Overview',
					value: 'overview',
					action: 'Fetch service overview',
					description: 'Общая статистика сервисов',
				},
				{
					name: '🩺 Health Check',
					value: 'health',
					action: 'Check service health',
					description: 'Проверка доступности API',
				},
				],
				default: 'overview',
			},
			{
				displayName: 'Additional Fields',
				name: 'statsAdditionalFields',
				type: 'collection',
				displayOptions: {
					show: {
						resource: ['stats'],
					},
				},
				default: {},
				options: [
					{
						displayName: 'Endpoint Override',
						name: 'endpoint',
						type: 'string',
						default: '',
						description: 'Переопределить путь (по умолчанию /api/stats/overview или /health)',
					},
					{
						displayName: 'Custom Headers (JSON)',
						name: 'headers',
						type: 'json',
						default: {},
					},
				],
			},
			{
				displayName: 'HTTP Method',
				name: 'customMethod',
				type: 'options',
				options: [
					{ name: 'GET', value: 'GET' },
					{ name: 'POST', value: 'POST' },
					{ name: 'PUT', value: 'PUT' },
					{ name: 'PATCH', value: 'PATCH' },
					{ name: 'DELETE', value: 'DELETE' },
				],
				displayOptions: {
					show: {
						resource: ['custom'],
					},
				},
				default: 'GET',
			},
			{
				displayName: 'Endpoint',
				name: 'customEndpoint',
				type: 'string',
				displayOptions: {
					show: {
						resource: ['custom'],
					},
				},
				required: true,
				default: '/api',
				description: 'Путь или полный URL (если начинается с http)',
			},
			{
				displayName: 'Query Parameters (JSON)',
				name: 'customQuery',
				type: 'json',
				displayOptions: {
					show: {
						resource: ['custom'],
					},
				},
				default: '',
			},
			{
				displayName: 'Body (JSON)',
				name: 'customBody',
				type: 'json',
				displayOptions: {
					show: {
						resource: ['custom'],
						customMethod: ['POST', 'PUT', 'PATCH'],
					},
				},
				default: '',
			},
			{
				displayName: 'Headers (JSON)',
				name: 'customHeaders',
				type: 'json',
				displayOptions: {
					show: {
						resource: ['custom'],
					},
				},
				default: '',
			},
		],
		credentials: [
			{
				name: 'oneCaiApi',
				required: true,
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: IDataObject[] = [];

		for (let i = 0; i < items.length; i++) {
			const resource = this.getNodeParameter('resource', i) as string;
			const operation = this.getNodeParameter('operation', i) as string;
			let response: IDataObject | IDataObject[] | undefined;

			if (resource === 'semanticSearch') {
				const query = this.getNodeParameter('query', i) as string;
				const configuration = this.getNodeParameter('configuration', i, '') as string;
				const limit = this.getNodeParameter('limit', i) as number;
				const additionalFields = this.getNodeParameter('searchAdditionalFields', i, {}) as AdditionalFields;
				const endpoint = additionalFields.endpoint || DEFAULT_ENDPOINTS.semanticSearch;

				const body: IDataObject = {
					query,
					limit,
				};
				if (configuration) {
					body.configuration = configuration;
				}

				response = await oneCaiApiRequest.call(
					this,
					'POST',
					endpoint as string,
					body,
					{},
					additionalFields,
				);
			} else if (resource === 'graph') {
				const additionalFields = this.getNodeParameter('graphAdditionalFields', i, {}) as AdditionalFields;

				if (operation === 'query') {
					const cypherQuery = this.getNodeParameter('cypherQuery', i) as string;
					const parameters = (this.getNodeParameter('queryParameters', i, {}) as IDataObject) || {};

					const endpoint = additionalFields.endpoint || DEFAULT_ENDPOINTS.graphQuery;
					const body: IDataObject = {
						query: cypherQuery,
						parameters,
					};

					response = await oneCaiApiRequest.call(
						this,
						'POST',
						endpoint as string,
						body,
						{},
						additionalFields,
					);
				} else if (operation === 'dependencies') {
					const moduleName = this.getNodeParameter('moduleName', i) as string;
					const functionName = this.getNodeParameter('functionName', i) as string;
					const endpoint = additionalFields.endpoint || DEFAULT_ENDPOINTS.graphDependencies;

					const body: IDataObject = {
						module_name: moduleName,
						function_name: functionName,
					};

					response = await oneCaiApiRequest.call(
						this,
						'POST',
						endpoint as string,
						body,
						{},
						additionalFields,
					);
				} else if (operation === 'configurations') {
					const endpoint = additionalFields.endpoint || DEFAULT_ENDPOINTS.graphConfigurations;
					response = await oneCaiApiRequest.call(this, 'GET', endpoint as string, {}, {}, additionalFields);
				} else if (operation === 'objects') {
					const configurationName = this.getNodeParameter('configurationName', i) as string;
					const objectType = this.getNodeParameter('objectType', i, '') as string;

					let endpoint = (additionalFields.endpoint as string) || DEFAULT_ENDPOINTS.graphObjects;
					if (!additionalFields.endpoint) {
						// Compose default path: /api/graph/objects/{config}
						endpoint = `${endpoint}/${encodeURIComponent(configurationName)}`;
					}

					const qs: IDataObject = {};
					if (objectType) {
						qs.object_type = objectType;
					}

					response = await oneCaiApiRequest.call(this, 'GET', endpoint, {}, qs, additionalFields);
				}
			} else if (resource === 'codeReview') {
				const code = this.getNodeParameter('code', i) as string;
				const language = this.getNodeParameter('language', i) as string;
				const fileName = this.getNodeParameter('fileName', i, '') as string;
				const projectContext = (this.getNodeParameter('projectContext', i, {}) as IDataObject) || {};
				const additionalFields = this.getNodeParameter(
					'codeReviewAdditionalFields',
					i,
					{},
				) as AdditionalFields;
				const recentChanges =
					(additionalFields.recentChanges as IDataObject[] | string[] | undefined) || [];
				const cursorPosition = (additionalFields.cursorPosition as IDataObject | undefined) || {};
				const endpoint = additionalFields.endpoint || DEFAULT_ENDPOINTS.codeReviewAnalyze;

				const body: IDataObject = {
					content: code,
					language,
				};
				if (fileName) {
					body.fileName = fileName;
				}
				if (projectContext && Object.keys(projectContext).length) {
					body.projectContext = projectContext;
				}
				if (Array.isArray(recentChanges) && recentChanges.length) {
					body.recentChanges = recentChanges;
				}
				if (cursorPosition && Object.keys(cursorPosition).length) {
					body.cursorPosition = cursorPosition;
				}

				response = await oneCaiApiRequest.call(
					this,
					'POST',
					endpoint as string,
					body,
					{},
					additionalFields,
				);
			} else if (resource === 'testGeneration') {
				const code = this.getNodeParameter('testCode', i) as string;
				const language = this.getNodeParameter('testLanguage', i) as string;
				const testType = this.getNodeParameter('testType', i) as string;
				const includeEdgeCases = this.getNodeParameter('includeEdgeCases', i) as boolean;
				const framework = this.getNodeParameter('framework', i, '') as string;
				const additionalFields = this.getNodeParameter('testAdditionalFields', i, {}) as AdditionalFields;
				const endpoint = additionalFields.endpoint || DEFAULT_ENDPOINTS.testGeneration;

				const body: IDataObject = {
					code,
					language,
					testType,
					includeEdgeCases,
				};

				if (framework) {
					body.framework = framework;
				}

				response = await oneCaiApiRequest.call(
					this,
					'POST',
					endpoint as string,
					body,
					{},
					additionalFields,
				);
			} else if (resource === 'stats') {
				const additionalFields = this.getNodeParameter('statsAdditionalFields', i, {}) as AdditionalFields;
				let endpoint: string;
				let method: HttpMethod = 'GET';

				if (operation === 'overview') {
					endpoint = (additionalFields.endpoint as string) || DEFAULT_ENDPOINTS.statsOverview;
					response = await oneCaiApiRequest.call(this, method, endpoint, {}, {}, additionalFields);
				} else if (operation === 'health') {
					endpoint = (additionalFields.endpoint as string) || DEFAULT_ENDPOINTS.health;
					response = await oneCaiApiRequest.call(this, method, endpoint, {}, {}, additionalFields);
				}
			} else if (resource === 'custom') {
				const method = this.getNodeParameter('customMethod', i) as HttpMethod;
				let endpoint = this.getNodeParameter('customEndpoint', i) as string;
				const customQuery = (this.getNodeParameter('customQuery', i, {}) as IDataObject) || {};
				const customBody = (this.getNodeParameter('customBody', i, {}) as IDataObject) || {};
				const customHeaders = (this.getNodeParameter('customHeaders', i, {}) as IDataObject) || {};

				const additionalFields: AdditionalFields = {};
				if (customHeaders && Object.keys(customHeaders).length) {
					additionalFields.headers = customHeaders;
				}

				// Allow full URLs in custom endpoint
				if (endpoint.startsWith('http')) {
					const requestBody = method === 'GET' || method === 'DELETE' ? undefined : customBody;

					const options: IDataObject = {
						method,
						uri: endpoint,
						headers: customHeaders,
						json: true,
						body:
							requestBody && Object.keys(requestBody).length ? (requestBody as IDataObject) : undefined,
						qs: customQuery && Object.keys(customQuery).length ? customQuery : undefined,
					};

					try {
						const directRequest = this.helpers.request as unknown as (
							opts: IDataObject,
						) => Promise<any>;
						response = (await directRequest(options)) as IDataObject;
					} catch (error) {
						throw new NodeApiError(this.getNode(), error as JsonObject);
					}
				} else {
					response = await oneCaiApiRequest.call(
						this,
						method,
						endpoint,
						customBody,
						customQuery,
						additionalFields,
					);
				}
			} else {
				throw new NodeOperationError(this.getNode(), `Unsupported resource: ${resource}`);
			}

			if (Array.isArray(response)) {
				for (const item of response) {
					returnData.push(item);
				}
			} else if (response) {
				returnData.push(response);
			}
		}

		return [this.helpers.returnJsonArray(returnData)];
	}
}

