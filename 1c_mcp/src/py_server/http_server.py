
"""HTTP-сервер с поддержкой SSE и Streamable HTTP для MCP."""

import logging
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlencode

import httpx
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (HTMLResponse, JSONResponse, RedirectResponse)
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from .auth import OAuth2Service, OAuth2Store
from .config import Config
from .mcp_server import MCPProxy, current_onec_credentials

logger = logging.getLogger(__name__)


class SSEAcceptHeaderMiddleware(BaseHTTPMiddleware):
	"""Middleware для автоматического добавления Accept: text/event-stream для SSE запросов."""
	
	async def dispatch(self, request, call_next):
		"""Добавляет Accept header если он отсутствует для SSE endpoints."""
		# Проверяем, является ли это SSE запросом
		if request.url.path.startswith("/sse") and request.method == "GET":
			# Проверяем наличие Accept header
			accept_header = request.headers.get("Accept", "")
			if "text/event-stream" not in accept_header:
				# Если Accept header отсутствует или не содержит text/event-stream,
				# добавляем его в scope заголовки
				# К сожалению, Starlette не позволяет напрямую изменять заголовки request,
				# но мы можем установить его в scope для использования транспортом
				request.scope["headers"] = [
					(key, value) if key != b"accept" else (b"accept", b"text/event-stream")
					for key, value in request.scope.get("headers", [])
				]
				# Если Accept header вообще отсутствовал, добавляем его
				if not any(key == b"accept" for key, _ in request.scope.get("headers", [])):
					request.scope.setdefault("headers", []).append((b"accept", b"text/event-stream"))
		
		return await call_next(request)


class OAuth2BearerMiddleware(BaseHTTPMiddleware):
	"""Middleware для проверки Bearer токенов в режиме OAuth2."""
	
	def __init__(self, app, oauth2_service: Optional[OAuth2Service], auth_mode: str):
		super().__init__(app)
		self.oauth2_service = oauth2_service
		self.auth_mode = auth_mode
		self.protected_paths = ["/mcp/", "/sse"]
	
	async def dispatch(self, request: Request, call_next):
		"""Проверка авторизации для защищённых путей."""
		# Пропускаем, если auth_mode != oauth2
		if self.auth_mode != "oauth2":
			return await call_next(request)
		
		# Проверяем, является ли путь защищённым
		path = request.url.path
		is_protected = any(path.startswith(protected) for protected in self.protected_paths)
		
		if not is_protected:
			return await call_next(request)
		
		# Извлекаем Bearer token
		auth_header = request.headers.get("Authorization", "")
		if not auth_header.startswith("Bearer "):
			return JSONResponse(
				status_code=401,
				content={"error": "invalid_token"},
				headers={"WWW-Authenticate": 'Bearer error="invalid_token"'}
			)
		
		token = auth_header[7:]  # Убираем "Bearer "
		
		# Валидируем токен (поддерживаем два формата)
		creds = None
		
		# 1. Простой формат: simple_base64(username:password)
		if token.startswith("simple_"):
			try:
				import base64
				creds_string = base64.b64decode(token[7:]).decode()
				username, password = creds_string.split(":", 1)
				creds = (username, password)
				logger.debug(f"Простой токен валидирован для пользователя: {username}")
			except Exception as e:
				logger.warning(f"Ошибка декодирования простого токена: {e}")
				creds = None
		
		# 2. OAuth2 формат: через хранилище
		if not creds:
			creds = self.oauth2_service.validate_access_token(token)
		
		if not creds:
			return JSONResponse(
				status_code=401,
				content={"error": "invalid_token"},
				headers={"WWW-Authenticate": 'Bearer error="invalid_token"'}
			)
		
		# Устанавливаем креденшилы в context var для этой сессии
		login, password = creds
		current_onec_credentials.set((login, password))
		
		# Передаём управление дальше
		response = await call_next(request)
		return response


class MCPHttpServer:
	"""HTTP-сервер для MCP с поддержкой SSE и Streamable HTTP."""
	
	def __init__(self, config: Config):
		"""Инициализация HTTP-сервера.
		
		Args:
			config: Конфигурация сервера
		"""
		self.config = config
		self.mcp_proxy = MCPProxy(config)
		
		# Создаем session manager для Streamable HTTP после создания MCP прокси
		self.streamable_session_manager = StreamableHTTPSessionManager(self.mcp_proxy.server)
		
		# Инициализация OAuth2 (если включено)
		self.oauth2_store: Optional[OAuth2Store] = None
		self.oauth2_service: Optional[OAuth2Service] = None
		if config.auth_mode == "oauth2":
			self.oauth2_store = OAuth2Store()
			self.oauth2_service = OAuth2Service(
				self.oauth2_store,
				code_ttl=config.oauth2_code_ttl,
				access_ttl=config.oauth2_access_ttl,
				refresh_ttl=config.oauth2_refresh_ttl
			)
			logger.info("OAuth2 авторизация включена")
		
		self.app = FastAPI(
			title="1C MCP Proxy",
			description="MCP-прокси для взаимодействия с 1С",
			version=config.server_version,
			lifespan=self._lifespan
		)
		
		# Настройка CORS
		self.app.add_middleware(
			CORSMiddleware,
			allow_origins=config.cors_origins,
			allow_credentials=True,
			allow_methods=["*"],
			allow_headers=["*"],
		)
		
		# Добавляем OAuth2 middleware
		self.app.add_middleware(
			OAuth2BearerMiddleware,
			oauth2_service=self.oauth2_service,
			auth_mode=config.auth_mode
		)
		
		# Монтируем транспорты
		self._mount_transports()
		
		# Регистрация основных маршрутов
		self._register_routes()
	
	@asynccontextmanager
	async def _lifespan(self, app: FastAPI):
		"""Управление жизненным циклом приложения."""
		logger.debug("Запуск HTTP-сервера MCP")
		
		# Запускаем задачу очистки OAuth2 токенов (если включено)
		if self.oauth2_store:
			await self.oauth2_store.start_cleanup_task(interval=60)
		
		# Запускаем session manager для Streamable HTTP
		async with self.streamable_session_manager.run():
			yield
		
		# Останавливаем задачу очистки OAuth2
		if self.oauth2_store:
			await self.oauth2_store.stop_cleanup_task()
		
		logger.debug("Остановка HTTP-сервера MCP")
	
	def _create_sse_starlette_app(self) -> Starlette:
		"""Создание Starlette приложения для обработки SSE."""
		# Создаем SSE транспорт для обработки сообщений
		sse_transport = SseServerTransport("/messages/")
		
		async def handle_sse(request):
			"""Обработчик SSE подключений."""
			logger.debug("Новое SSE подключение")
			
			# Убеждаемся, что Accept header установлен в text/event-stream
			# Это требуется библиотекой MCP для SSE соединений
			accept_header = request.headers.get("Accept", "")
			if "text/event-stream" not in accept_header:
				# Обновляем заголовки в scope для передачи в транспорт
				headers = list(request.scope.get("headers", []))
				# Удаляем старый Accept если есть
				headers = [(k, v) for k, v in headers if k.lower() != b"accept"]
				# Добавляем правильный Accept header
				headers.append((b"accept", b"text/event-stream"))
				request.scope["headers"] = headers
				logger.debug("Добавлен Accept: text/event-stream заголовок для SSE запроса")
			
			try:
				# Подключаем SSE с использованием транспорта
				async with sse_transport.connect_sse(
					request.scope, 
					request.receive, 
					request._send
				) as streams:
					# Запускаем MCP сервер с потоками
					await self.mcp_proxy.server.run(
						streams[0], 
						streams[1], 
						self.mcp_proxy.get_initialization_options()
					)
			except Exception as e:
				logger.error(f"Ошибка в SSE обработчике: {e}")
				raise
			finally:
				logger.debug("SSE подключение закрыто")
		
		# Создаем маршруты для Starlette приложения
		# Когда это приложение монтируется на /sse:
		# - Route("/", ...) становится GET /sse (SSE подключение)
		# - Mount("/messages/", ...) становится POST /sse/messages/ (отправка сообщений)
		routes = [
			Route("/", endpoint=handle_sse),  # SSE endpoint: GET /sse
			Mount("/messages/", app=sse_transport.handle_post_message),  # Messages: POST /sse/messages/
		]
		
		# Создаем Starlette приложение с middleware для автоматического добавления Accept header
		sse_app = Starlette(routes=routes)
		sse_app.add_middleware(SSEAcceptHeaderMiddleware)
		
		return sse_app
	
	def _create_streamable_http_asgi(self):
		"""Создание ASGI обработчика для Streamable HTTP."""
		
		async def asgi(scope: Scope, receive: Receive, send: Send) -> None:
			"""ASGI обработчик для Streamable HTTP соединений."""
			logger.debug("Новое Streamable HTTP подключение")
			
			try:
				# Используем правильный API handle_request для ASGI
				await self.streamable_session_manager.handle_request(scope, receive, send)
			except Exception as e:
				logger.error(f"Ошибка в Streamable HTTP обработчике: {e}")
				raise
			finally:
				logger.debug("Streamable HTTP подключение закрыто")
		
		return asgi
	
	def _mount_transports(self):
		"""Монтирование транспортов MCP."""
		
		# Монтируем SSE транспорт на /sse
		sse_app = self._create_sse_starlette_app()
		self.app.mount("/sse", sse_app)
		
		# Монтируем Streamable HTTP транспорт на /mcp/ (с trailing slash для устранения 307 редиректов)
		streamable_app = self._create_streamable_http_asgi()
		self.app.mount("/mcp/", streamable_app)
	
	def _register_routes(self):
		"""Регистрация основных маршрутов."""
		
		@self.app.get("/")
		async def root():
			"""Корневой маршрут - перенаправляет на info."""
			endpoints = {
					"info": "/info",
					"health": "/health",
					"sse": "/sse",
					"streamable_http": "/mcp/"
				}
			if self.config.auth_mode == "oauth2":
				endpoints["oauth2"] = {
					"well_known_prm": "/.well-known/oauth-protected-resource",
					"well_known_as": "/.well-known/oauth-authorization-server",
					"register": "/register",
					"authorize": "/authorize",
					"token": "/token"
				}
			return {
				"message": "1C MCP Proxy Server",
				"endpoints": endpoints
			}
		
		@self.app.get("/info")
		async def info():
			"""Информационный маршрут."""
			return {
				"name": self.config.server_name,
				"version": self.config.server_version,
				"description": "MCP-прокси для взаимодействия с 1С",
				"endpoints": {
					"sse": "/sse",
					"messages": "/sse/messages/",
					"streamable_http": "/mcp/",
					"health": "/health",
					"info": "/info"
				},
				"transports": {
					"sse": {
						"endpoint": "/sse",
						"messages": "/sse/messages/"
					},
					"streamable_http": {
						"endpoint": "/mcp/"
					}
				}
			}
		
		@self.app.get("/health")
		async def health():
			"""Проверка здоровья сервера."""
			try:
				# Проверяем подключение к 1С через прокси
				if hasattr(self.mcp_proxy, 'onec_client') and self.mcp_proxy.onec_client:
					await self.mcp_proxy.onec_client.check_health()
					result = {"status": "healthy", "onec_connection": "ok"}
				else:
					result = {"status": "starting", "onec_connection": "not_initialized"}
				
				# Добавляем информацию об авторизации
				result["auth"] = {"mode": self.config.auth_mode}
				return result
			except Exception as e:
				logger.error(f"Ошибка проверки здоровья: {e}")
				return {
					"status": "unhealthy",
					"onec_connection": "error",
					"error_details": str(e),
					"auth": {"mode": self.config.auth_mode}
				}
		
		# OAuth2 endpoints (если включено)
		if self.config.auth_mode == "oauth2":
			self._register_oauth2_routes()
	
	def _register_oauth2_routes(self):
		"""Регистрация OAuth2 маршрутов."""
		
		@self.app.get("/.well-known/oauth-protected-resource")
		async def well_known_prm(request: Request):
			"""Protected Resource Metadata (RFC 9728)."""
			# Определяем публичный URL
			if self.config.public_url:
				public_url = self.config.public_url
			else:
				# Формируем из текущего запроса
				scheme = request.url.scheme
				netloc = request.headers.get("host", f"{request.client.host}:{request.url.port}")
				public_url = f"{scheme}://{netloc}"
			
			return self.oauth2_service.generate_prm_document(public_url)
		
		@self.app.get("/.well-known/oauth-authorization-server")
		async def well_known_as_metadata(request: Request):
			"""Authorization Server Metadata (RFC 8414)."""
			# Определяем публичный URL
			if self.config.public_url:
				base_url = self.config.public_url
			else:
				# Формируем из текущего запроса
				scheme = request.url.scheme
				netloc = request.headers.get("host", f"{request.client.host}:{request.url.port}")
				base_url = f"{scheme}://{netloc}"
			
			return {
				"issuer": base_url,
				"authorization_endpoint": f"{base_url}/authorize",
				"token_endpoint": f"{base_url}/token",
				"registration_endpoint": f"{base_url}/register",  # Добавляем registration endpoint
				"grant_types_supported": [
					"authorization_code",
					"refresh_token",
					"password"  # Добавляем Password Grant для простоты
				],
				"response_types_supported": ["code"],
				"code_challenge_methods_supported": ["S256"],
				"token_endpoint_auth_methods_supported": ["none"],  # Публичный клиент, без client_secret
				"revocation_endpoint_auth_methods_supported": ["none"]
			}
		
		@self.app.post("/register")
		async def register_client(request: Request):
			"""Dynamic Client Registration (RFC 7591) - упрощённая версия.
			
			Всегда возвращает фиксированный client_id для публичного клиента.
			Игнорирует параметры регистрации, т.к. у нас нет реальной БД клиентов.
			"""
			# Читаем тело запроса (но не используем, т.к. всё равно вернём фиксированные данные)
			try:
				body = await request.json()
				logger.debug(f"Client registration request: {body}")
			except:
				body = {}
			
			# Определяем публичный URL для redirect_uris
			if self.config.public_url:
				base_url = self.config.public_url
			else:
				scheme = request.url.scheme
				netloc = request.headers.get("host", f"{request.client.host}:{request.url.port}")
				base_url = f"{scheme}://{netloc}"
			
			# Возвращаем фиксированные данные публичного клиента
			client_data = {
				"client_id": "mcp-public-client",
				"client_secret": "",  # Пустой для публичного клиента
				"client_id_issued_at": 1640000000,  # Фиксированная дата
				"grant_types": ["authorization_code", "refresh_token", "password"],
				"response_types": ["code"],
				"redirect_uris": [
					f"{base_url}/callback",
					"http://localhost/callback",
					"http://127.0.0.1/callback"
				],
				"token_endpoint_auth_method": "none",  # Публичный клиент
				"application_type": "web"
			}
			
			# Если клиент передал свои redirect_uris, добавляем их
			if "redirect_uris" in body:
				for uri in body.get("redirect_uris", []):
					if uri not in client_data["redirect_uris"]:
						client_data["redirect_uris"].append(uri)
			
			logger.info(f"Client registration: вернули фиксированный client_id='mcp-public-client'")
			
			return client_data
		
		@self.app.get("/authorize")
		async def authorize_get(
			request: Request,
			response_type: str = None,
			client_id: str = None,
			redirect_uri: str = None,
			state: str = None,
			code_challenge: str = None,
			code_challenge_method: str = None
		):
			"""Authorization endpoint - показывает форму логина."""
			# Валидация параметров
			if not all([response_type, client_id, redirect_uri, code_challenge, code_challenge_method]):
				return HTMLResponse(
					content="<html><body><h1>Ошибка</h1><p>Отсутствуют обязательные параметры OAuth2</p></body></html>",
					status_code=400
				)
			
			if response_type != "code":
				return HTMLResponse(
					content="<html><body><h1>Ошибка</h1><p>Поддерживается только response_type=code</p></body></html>",
					status_code=400
				)
			
			if code_challenge_method != "S256":
				return HTMLResponse(
					content="<html><body><h1>Ошибка</h1><p>Поддерживается только code_challenge_method=S256</p></body></html>",
					status_code=400
				)
			
			# Сохраняем параметры в query для формы
			query_params = urlencode({
				"redirect_uri": redirect_uri,
				"state": state or "",
				"code_challenge": code_challenge
			})
			
			# HTML форма для ввода креденшилов 1С
			html_content = f"""
			<!DOCTYPE html>
			<html>
			<head>
				<meta charset="utf-8">
				<title>Авторизация 1С MCP</title>
				<style>
					body {{ font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }}
					h1 {{ color: #333; }}
					form {{ display: flex; flex-direction: column; }}
					label {{ margin-top: 10px; color: #666; }}
					input {{ padding: 8px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; }}
					button {{ margin-top: 20px; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }}
					button:hover {{ background: #0056b3; }}
					.error {{ color: red; margin-top: 10px; }}
				</style>
			</head>
			<body>
				<h1>Вход в 1С</h1>
				<p>Введите учётные данные пользователя 1С:</p>
				<form method="post" action="/authorize?{query_params}">
					<label for="username">Логин:</label>
					<input type="text" id="username" name="username" required autofocus>
					
					<label for="password">Пароль:</label>
					<input type="password" id="password" name="password" required>
					
					<button type="submit">Войти</button>
				</form>
			</body>
			</html>
			"""
			return HTMLResponse(content=html_content)
		
		@self.app.post("/authorize")
		async def authorize_post(
			request: Request,
			username: str = Form(...),
			password: str = Form(...),
			redirect_uri: str = None,
			state: str = None,
			code_challenge: str = None
		):
			"""Обработка формы логина и выдача authorization code."""
			if not all([redirect_uri, code_challenge]):
				return HTMLResponse(
					content="<html><body><h1>Ошибка</h1><p>Отсутствуют обязательные параметры</p></body></html>",
					status_code=400
				)
			
			# Валидация креденшилов через вызов к 1С health endpoint
			try:
				async with httpx.AsyncClient(timeout=10.0) as client:
					health_url = f"{self.config.onec_url}/hs/{self.config.onec_service_root}/health"
					response = await client.get(
						health_url,
						auth=httpx.BasicAuth(username, password)
					)
					
					if response.status_code != 200:
						# Неверные креденшилы
						error_html = f"""
						<!DOCTYPE html>
						<html>
						<head>
							<meta charset="utf-8">
							<title>Ошибка авторизации</title>
							<style>
								body {{ font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }}
								.error {{ color: red; }}
								a {{ color: #007bff; text-decoration: none; }}
							</style>
						</head>
						<body>
							<h1>Ошибка авторизации</h1>
							<p class="error">Неверный логин или пароль 1С</p>
							<p><a href="javascript:history.back()">← Вернуться назад</a></p>
						</body>
						</html>
						"""
						return HTMLResponse(content=error_html, status_code=401)
			except Exception as e:
				logger.error(f"Ошибка проверки креденшилов 1С: {e}")
				return HTMLResponse(
					content=f"<html><body><h1>Ошибка</h1><p>Не удалось подключиться к 1С: {e}</p></body></html>",
					status_code=503
				)
			
			# Генерируем authorization code
			code = self.oauth2_service.generate_authorization_code(
				login=username,
				password=password,
				redirect_uri=redirect_uri,
				code_challenge=code_challenge
			)
			
			# Формируем redirect URL
			params = {"code": code}
			if state:
				params["state"] = state
			
			redirect_url = f"{redirect_uri}?{urlencode(params)}"
			
			logger.info(f"Authorization code выдан для пользователя {username}, redirect: {redirect_uri}")
			return RedirectResponse(url=redirect_url, status_code=302)
		
		@self.app.post("/token")
		async def token_endpoint(
			request: Request,
			grant_type: str = Form(...),
			code: str = Form(None),
			redirect_uri: str = Form(None),
			code_verifier: str = Form(None),
			refresh_token: str = Form(None),
			username: str = Form(None),
			password: str = Form(None)
		):
			"""Token endpoint для обмена code на токены, refresh или password grant."""
			
			# Password Grant - самый простой вариант
			if grant_type == "password":
				if not username or not password:
					return JSONResponse(
						status_code=400,
						content={"error": "invalid_request", "error_description": "Missing username or password"}
					)
				
				# Валидация креденшилов через 1С
				try:
					async with httpx.AsyncClient(timeout=10.0) as client:
						health_url = f"{self.config.onec_url}/hs/{self.config.onec_service_root}/health"
						response = await client.get(
							health_url,
							auth=httpx.BasicAuth(username, password)
						)
						
						if response.status_code != 200:
							return JSONResponse(
								status_code=400,
								content={"error": "invalid_grant", "error_description": "Invalid username or password"}
							)
				except Exception as e:
					logger.error(f"Ошибка проверки креденшилов 1С для password grant: {e}")
					return JSONResponse(
						status_code=503,
						content={"error": "server_error", "error_description": "Unable to validate credentials"}
					)
				
				# Генерируем простой токен (base64 от username:password с префиксом)
				import base64
				creds_string = f"{username}:{password}"
				simple_token = "simple_" + base64.b64encode(creds_string.encode()).decode()
				
				logger.info(f"Password grant выдан для пользователя {username}")
				
				return {
					"access_token": simple_token,
					"token_type": "Bearer",
					"expires_in": 86400,  # 24 часа (для простоты)
					"scope": "mcp"
				}
			
			# Authorization Code Grant
			if grant_type == "authorization_code":
				# Обмен code на токены
				if not all([code, redirect_uri, code_verifier]):
					return JSONResponse(
						status_code=400,
						content={"error": "invalid_request", "error_description": "Missing required parameters"}
					)
				
				result = self.oauth2_service.exchange_code_for_tokens(code, redirect_uri, code_verifier)
				if not result:
					return JSONResponse(
						status_code=400,
						content={"error": "invalid_grant", "error_description": "Invalid or expired authorization code"}
					)
				
				access_token, token_type, expires_in, refresh = result
				return {
					"access_token": access_token,
					"token_type": token_type,
					"expires_in": expires_in,
					"refresh_token": refresh,
					"scope": "mcp"
				}
			
			elif grant_type == "refresh_token":
				# Обновление токенов
				if not refresh_token:
					return JSONResponse(
						status_code=400,
						content={"error": "invalid_request", "error_description": "Missing refresh_token"}
					)
				
				result = self.oauth2_service.refresh_tokens(refresh_token)
				if not result:
					return JSONResponse(
						status_code=400,
						content={"error": "invalid_grant", "error_description": "Invalid or expired refresh token"}
					)
				
				access_token, token_type, expires_in, new_refresh = result
				return {
					"access_token": access_token,
					"token_type": token_type,
					"expires_in": expires_in,
					"refresh_token": new_refresh,
					"scope": "mcp"
				}
			
			else:
				return JSONResponse(
					status_code=400,
					content={"error": "unsupported_grant_type", "error_description": f"Grant type '{grant_type}' not supported"}
				)
	
	async def start(self):
		"""Запуск HTTP-сервера."""
		config = uvicorn.Config(
			app=self.app,
			host=self.config.host,
			port=self.config.port,
			log_level=self.config.log_level.lower(),
			access_log=True
		)
		
		server = uvicorn.Server(config)
		logger.debug(f"Запуск HTTP-сервера на {self.config.host}:{self.config.port}")
		await server.serve()


async def run_http_server(config: Config):
	"""Запуск HTTP-сервера.
	
	Args:
		config: Конфигурация сервера
	"""
	server = MCPHttpServer(config)
	await server.start() 