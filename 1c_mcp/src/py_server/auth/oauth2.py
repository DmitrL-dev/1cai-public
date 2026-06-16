
"""OAuth2 хранилище и сервис для авторизации."""

import asyncio
import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AuthCodeData:
	"""Данные authorization code."""
	login: str
	password: str
	redirect_uri: str
	code_challenge: str
	exp: datetime


@dataclass
class AccessTokenData:
	"""Данные access token."""
	login: str
	password: str
	exp: datetime


@dataclass
class RefreshTokenData:
	"""Данные refresh token."""
	login: str
	password: str
	exp: datetime
	rotation_counter: int = 0


class OAuth2Store:
	"""In-memory хранилище для OAuth2 токенов и кодов."""
	
	def __init__(self):
		"""Инициализация хранилища."""
		self.auth_codes: Dict[str, AuthCodeData] = {}
		self.access_tokens: Dict[str, AccessTokenData] = {}
		self.refresh_tokens: Dict[str, RefreshTokenData] = {}
		self._cleanup_task: Optional[asyncio.Task] = None
	
	async def start_cleanup_task(self, interval: int = 60):
		"""Запустить периодическую очистку устаревших токенов.
		
		Args:
			interval: Интервал очистки в секундах
		"""
		self._cleanup_task = asyncio.create_task(self._cleanup_loop(interval))
		logger.debug(f"Запущена задача очистки OAuth2 токенов (интервал: {interval}s)")
	
	async def stop_cleanup_task(self):
		"""Остановить задачу очистки."""
		if self._cleanup_task:
			self._cleanup_task.cancel()
			try:
				await self._cleanup_task
			except asyncio.CancelledError:
				pass
			logger.debug("Задача очистки OAuth2 токенов остановлена")
	
	async def _cleanup_loop(self, interval: int):
		"""Периодическая очистка устаревших токенов."""
		while True:
			try:
				await asyncio.sleep(interval)
				self._cleanup_expired()
			except asyncio.CancelledError:
				break
			except Exception as e:
				logger.error(f"Ошибка при очистке токенов: {e}")
	
	def _cleanup_expired(self):
		"""Удалить устаревшие токены и коды."""
		now = datetime.now()
		
		# Очистка authorization codes
		expired_codes = [code for code, data in self.auth_codes.items() if data.exp < now]
		for code in expired_codes:
			del self.auth_codes[code]
		
		# Очистка access tokens
		expired_access = [token for token, data in self.access_tokens.items() if data.exp < now]
		for token in expired_access:
			del self.access_tokens[token]
		
		# Очистка refresh tokens
		expired_refresh = [token for token, data in self.refresh_tokens.items() if data.exp < now]
		for token in expired_refresh:
			del self.refresh_tokens[token]
		
		if expired_codes or expired_access or expired_refresh:
			logger.debug(f"Очищено токенов: codes={len(expired_codes)}, access={len(expired_access)}, refresh={len(expired_refresh)}")
	
	def save_auth_code(self, code: str, data: AuthCodeData):
		"""Сохранить authorization code."""
		self.auth_codes[code] = data
		logger.debug(f"Сохранён authorization code для {data.login}, expires в {data.exp}")
	
	def get_auth_code(self, code: str) -> Optional[AuthCodeData]:
		"""Получить и удалить authorization code (одноразовый)."""
		data = self.auth_codes.pop(code, None)
		if data and data.exp < datetime.now():
			logger.debug(f"Authorization code истёк: {code}")
			return None
		return data
	
	def save_access_token(self, token: str, data: AccessTokenData):
		"""Сохранить access token."""
		self.access_tokens[token] = data
		logger.debug(f"Сохранён access token для {data.login}, expires в {data.exp}")
	
	def get_access_token(self, token: str) -> Optional[AccessTokenData]:
		"""Получить access token."""
		data = self.access_tokens.get(token)
		if data and data.exp < datetime.now():
			logger.debug(f"Access token истёк: {token[:16]}...")
			del self.access_tokens[token]
			return None
		return data
	
	def save_refresh_token(self, token: str, data: RefreshTokenData):
		"""Сохранить refresh token."""
		self.refresh_tokens[token] = data
		logger.debug(f"Сохранён refresh token для {data.login}, expires в {data.exp}")
	
	def get_refresh_token(self, token: str) -> Optional[RefreshTokenData]:
		"""Получить и удалить refresh token (ротация)."""
		data = self.refresh_tokens.pop(token, None)
		if data and data.exp < datetime.now():
			logger.debug(f"Refresh token истёк: {token[:16]}...")
			return None
		return data


class OAuth2Service:
	"""Сервис OAuth2 для авторизации."""
	
	def __init__(self, store: OAuth2Store, code_ttl: int = 120, access_ttl: int = 3600, refresh_ttl: int = 1209600):
		"""Инициализация сервиса.
		
		Args:
			store: Хранилище токенов
			code_ttl: TTL authorization code в секундах
			access_ttl: TTL access token в секундах
			refresh_ttl: TTL refresh token в секундах
		"""
		self.store = store
		self.code_ttl = code_ttl
		self.access_ttl = access_ttl
		self.refresh_ttl = refresh_ttl
	
	def generate_prm_document(self, public_url: str) -> dict:
		"""Сгенерировать Protected Resource Metadata документ (RFC 9728).
		
		Args:
			public_url: Публичный URL прокси
			
		Returns:
			PRM документ
		"""
		public_url = public_url.rstrip('/')
		return {
			"resource": public_url,
			"authorization_servers": [public_url],
			"authorization_endpoint": f"{public_url}/authorize",
			"token_endpoint": f"{public_url}/token",
			"code_challenge_methods_supported": ["S256"]
		}
	
	def generate_authorization_code(self, login: str, password: str, redirect_uri: str, code_challenge: str) -> str:
		"""Сгенерировать authorization code.
		
		Args:
			login: Логин пользователя 1С
			password: Пароль пользователя 1С
			redirect_uri: URI для редиректа
			code_challenge: PKCE challenge
			
		Returns:
			Authorization code
		"""
		code = secrets.token_urlsafe(32)
		exp = datetime.now() + timedelta(seconds=self.code_ttl)
		
		self.store.save_auth_code(code, AuthCodeData(
			login=login,
			password=password,
			redirect_uri=redirect_uri,
			code_challenge=code_challenge,
			exp=exp
		))
		
		return code
	
	def validate_pkce(self, code_verifier: str, code_challenge: str) -> bool:
		"""Валидировать PKCE S256.
		
		Args:
			code_verifier: Verifier от клиента
			code_challenge: Challenge из authorization code
			
		Returns:
			True если валидно
		"""
		# Вычисляем SHA256 от verifier
		verifier_hash = hashlib.sha256(code_verifier.encode('ascii')).digest()
		# Base64url encoding (без padding)
		computed_challenge = base64.urlsafe_b64encode(verifier_hash).decode('ascii').rstrip('=')
		
		return computed_challenge == code_challenge
	
	def exchange_code_for_tokens(self, code: str, redirect_uri: str, code_verifier: str) -> Optional[Tuple[str, str, int, str]]:
		"""Обменять authorization code на токены.
		
		Args:
			code: Authorization code
			redirect_uri: Redirect URI (должен совпадать)
			code_verifier: PKCE verifier
			
		Returns:
			Tuple (access_token, token_type, expires_in, refresh_token) или None
		"""
		# Получаем код (одноразовый)
		code_data = self.store.get_auth_code(code)
		if not code_data:
			logger.warning("Недействительный или истёкший authorization code")
			return None
		
		# Проверяем redirect_uri
		if code_data.redirect_uri != redirect_uri:
			logger.warning(f"Несовпадение redirect_uri: ожидался {code_data.redirect_uri}, получен {redirect_uri}")
			return None
		
		# Валидируем PKCE
		if not self.validate_pkce(code_verifier, code_data.code_challenge):
			logger.warning("PKCE валидация не прошла")
			return None
		
		# Генерируем токены
		access_token = secrets.token_urlsafe(32)
		refresh_token = secrets.token_urlsafe(32)
		
		access_exp = datetime.now() + timedelta(seconds=self.access_ttl)
		refresh_exp = datetime.now() + timedelta(seconds=self.refresh_ttl)
		
		self.store.save_access_token(access_token, AccessTokenData(
			login=code_data.login,
			password=code_data.password,
			exp=access_exp
		))
		
		self.store.save_refresh_token(refresh_token, RefreshTokenData(
			login=code_data.login,
			password=code_data.password,
			exp=refresh_exp,
			rotation_counter=0
		))
		
		logger.debug(f"Выданы токены для пользователя {code_data.login}")
		return (access_token, "Bearer", self.access_ttl, refresh_token)
	
	def refresh_tokens(self, refresh_token: str) -> Optional[Tuple[str, str, int, str]]:
		"""Обновить токены по refresh token.
		
		Args:
			refresh_token: Refresh token
			
		Returns:
			Tuple (access_token, token_type, expires_in, new_refresh_token) или None
		"""
		# Получаем refresh token (с ротацией - удаляется)
		refresh_data = self.store.get_refresh_token(refresh_token)
		if not refresh_data:
			logger.warning("Недействительный или истёкший refresh token")
			return None
		
		# Генерируем новые токены
		new_access_token = secrets.token_urlsafe(32)
		new_refresh_token = secrets.token_urlsafe(32)
		
		access_exp = datetime.now() + timedelta(seconds=self.access_ttl)
		refresh_exp = datetime.now() + timedelta(seconds=self.refresh_ttl)
		
		self.store.save_access_token(new_access_token, AccessTokenData(
			login=refresh_data.login,
			password=refresh_data.password,
			exp=access_exp
		))
		
		self.store.save_refresh_token(new_refresh_token, RefreshTokenData(
			login=refresh_data.login,
			password=refresh_data.password,
			exp=refresh_exp,
			rotation_counter=refresh_data.rotation_counter + 1
		))
		
		logger.debug(f"Обновлены токены для пользователя {refresh_data.login} (rotation #{refresh_data.rotation_counter + 1})")
		return (new_access_token, "Bearer", self.access_ttl, new_refresh_token)
	
	def validate_access_token(self, token: str) -> Optional[Tuple[str, str]]:
		"""Валидировать access token и получить креды 1С.
		
		Args:
			token: Access token
			
		Returns:
			Tuple (login, password) или None
		"""
		token_data = self.store.get_access_token(token)
		if not token_data:
			return None
		
		return (token_data.login, token_data.password)

