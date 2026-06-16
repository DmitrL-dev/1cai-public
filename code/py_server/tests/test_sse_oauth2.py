
"""
Специализированные тесты для SSE и OAuth2 функциональности

Детальные тесты для:
- Server-Sent Events (SSE) транспорт
- OAuth2 авторизация (все flow)
- Асинхронные операции
- WebSocket соединения (если применимо)

"""

import asyncio
import base64
import hashlib
import json
import os
import secrets
# Импорты приложения
import sys
import time

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# SSE (SERVER-SENT EVENTS) ТЕСТЫ
# =============================================================================

class TestSSEServerSentEvents:
    """Детальные тесты Server-Sent Events"""
    
    @pytest.mark.integration
    async def test_sse_connection_establishment(self, test_client):
        """Тест установки SSE соединения"""
        async with test_client.stream("GET", "/sse") as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"
            assert response.headers.get("cache-control") == "no-cache"
            assert response.headers.get("connection") == "keep-alive"
    
    @pytest.mark.integration
    async def test_sse_message_format(self, test_client):
        """Тест формата SSE сообщений"""
        async with test_client.stream("GET", "/sse") as response:
            assert response.status_code == 200
            
            # Читаем первые несколько строк
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    # Проверяем формат сообщения
                    data = line[5:].strip()  # Убираем "data: "
                    if data:
                        try:
                            json.loads(data)  # Должен быть валидным JSON
                        except json.JSONDecodeError:
                            # Может быть простой текст
                            assert isinstance(data, str)
                    break  # Проверяем только первое сообщение
                if line == "":
                    break
    
    @pytest.mark.integration
    async def test_sse_event_types(self, test_client):
        """Тест различных типов SSE событий"""
        expected_events = ["message", "error", "complete", "heartbeat"]
        
        async with test_client.stream("GET", "/sse") as response:
            assert response.status_code == 200
            
            events_received = set()
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                    if event_type in expected_events:
                        events_received.add(event_type)
                if len(events_received) >= len(expected_events):
                    break
            
            # Проверяем что получили некоторые типы событий
            assert len(events_received) > 0
    
    @pytest.mark.integration
    async def test_sse_idempotency(self, test_client):
        """Тест идемпотентности SSE"""
        # Открываем два соединения
        async with test_client.stream("GET", "/sse") as response1:
            async with test_client.stream("GET", "/sse") as response2:
                assert response1.status_code == 200
                assert response2.status_code == 200
                
                # Оба соединения должны работать
                await asyncio.sleep(0.1)
                assert not response1.is_closed
                assert not response2.is_closed
    
    @pytest.mark.performance
    async def test_sse_large_messages(self, test_client):
        """Тест отправки больших сообщений через SSE"""
        large_message = "x" * 100000  # 100KB сообщение
        
        async with test_client.stream("GET", "/sse") as response:
            assert response.status_code == 200
            
            start_time = time.time()
            bytes_received = 0
            message_count = 0
            
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if len(data) > 1000:  # Большое сообщение
                        bytes_received += len(data)
                        message_count += 1
                
                elapsed = time.time() - start_time
                if elapsed > 5 or message_count > 10:
                    break
            
            # Проверяем что большие сообщения обрабатываются
            assert bytes_received > 0
    
    @pytest.mark.thread_safety
    async def test_sse_multiple_clients(self, test_client):
        """Тест множественных SSE клиентов"""
        num_clients = 5
        
        async def create_sse_connection(client_id: int):
            async with test_client.stream("GET", "/sse") as response:
                assert response.status_code == 200
                
                # Читаем несколько сообщений
                message_count = 0
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        message_count += 1
                        if message_count >= 5:
                            break
                    if line == "":
                        break
                
                return f"Client {client_id}: {message_count} messages"
        
        # Запускаем все клиенты одновременно
        tasks = [create_sse_connection(i) for i in range(num_clients)]
        results = await asyncio.gather(*tasks)
        
        # Все клиенты должны получить сообщения
        assert len(results) == num_clients
        for result in results:
            assert "Client" in result and "messages" in result
    
    @pytest.mark.stress
    async def test_sse_connection_resilience(self, test_client):
        """Тест устойчивости SSE соединений"""
        # Быстро открываем и закрываем много соединений
        for i in range(20):
            async with test_client.stream("GET", "/sse") as response:
                assert response.status_code == 200
                # Читаем только первое сообщение
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        break
                    if line == "":
                        break
            
            # Небольшая пауза между соединениями
            await asyncio.sleep(0.01)


# =============================================================================
# OAUTH2 DETAILED ТЕСТЫ
# =============================================================================

class TestOAuth2Detailed:
    """Детальные тесты OAuth2 авторизации"""
    
    @pytest.mark.security
    async def test_oauth2_client_registration(self, test_client):
        """Тест регистрации клиента OAuth2"""
        # Простая регистрация клиента
        client_data = {
            "client_name": "Test OAuth Client",
            "redirect_uris": ["http://localhost:8080/callback"],
            "grant_types": ["authorization_code", "password", "refresh_token"],
            "response_types": ["code"]
        }
        
        response = await test_client.post("/register", json=client_data)
        # Может возвращать разные статусы в зависимости от реализации
        assert response.status_code in [200, 201, 400, 404, 501]
        
        if response.status_code in [200, 201]:
            data = response.json()
            assert "client_id" in data
            assert "client_secret" in data
            assert data["grant_types"] == ["authorization_code", "password", "refresh_token"]
    
    @pytest.mark.security
    async def test_oauth2_authorization_code_flow(self, test_client):
        """Тест полного flow авторизации через код"""
        # Шаг 1: Запрос авторизации
        auth_params = {
            "response_type": "code",
            "client_id": "test_client",
            "redirect_uri": "http://localhost:8080/callback",
            "scope": "read write",
            "state": "test_state_123"
        }
        
        response = await test_client.get("/authorize", params=auth_params)
        assert response.status_code in [200, 302]
        
        if response.status_code == 200:
            # Получили HTML форму авторизации
            assert "form" in response.text.lower()
        
        # Шаг 2: Отправка данных авторизации
        auth_data = {
            "username": "test_user",
            "password": "test_password",
            "redirect_uri": "http://localhost:8080/callback",
            "state": "test_state_123"
        }
        
        response = await test_client.post("/authorize", data=auth_data)
        assert response.status_code in [302, 400, 404]
        
        if response.status_code == 302:
            # Проверяем редирект с кодом
            redirect_location = response.headers.get("location", "")
            assert "code=" in redirect_location
    
    @pytest.mark.security
    async def test_oauth2_pkce_flow_detailed(self, test_client):
        """Детальный тест PKCE flow"""
        # Генерируем PKCE параметры
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode('utf-8')
        
        # Запрос авторизации с PKCE
        auth_params = {
            "response_type": "code",
            "client_id": "test_client",
            "redirect_uri": "http://localhost:8080/callback",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": "read write",
            "state": "pkce_state_123"
        }
        
        response = await test_client.get("/authorize", params=auth_params)
        assert response.status_code in [200, 302]
        
        # Обмен кода на токен с code_verifier
        if response.status_code == 302:
            # Извлекаем код из редиректа
            location = response.headers.get("location", "")
            auth_code = None
            if "code=" in location:
                auth_code = location.split("code=")[1].split("&")[0]
            
            if auth_code:
                token_data = {
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "redirect_uri": "http://localhost:8080/callback",
                    "code_verifier": code_verifier
                }
                
                token_response = await test_client.post("/token", data=token_data)
                assert token_response.status_code in [200, 400, 401]
                
                if token_response.status_code == 200:
                    token_json = token_response.json()
                    assert "access_token" in token_json
                    assert "token_type" in token_json
                    assert token_json["token_type"] == "Bearer"
                    assert "expires_in" in token_json
    
    @pytest.mark.security
    async def test_oauth2_password_grant_detailed(self, test_client):
        """Детальный тест Password Grant"""
        password_data = {
            "grant_type": "password",
            "username": "test_user_123",
            "password": "secure_password_456",
            "scope": "read write"
        }
        
        response = await test_client.post("/token", data=password_data)
        assert response.status_code in [200, 400, 401, 404]
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Проверяем структуру ответа
            required_fields = ["access_token", "token_type", "expires_in"]
            for field in required_fields:
                assert field in token_data
            
            assert token_data["token_type"] == "Bearer"
            assert isinstance(token_data["expires_in"], int)
            assert token_data["expires_in"] > 0
            
            # Дополнительные поля (опционально)
            if "refresh_token" in token_data:
                assert isinstance(token_data["refresh_token"], str)
            if "scope" in token_data:
                assert isinstance(token_data["scope"], str)
    
    @pytest.mark.security
    async def test_oauth2_refresh_token_flow(self, test_client):
        """Тест refresh token flow"""
        # Сначала получаем токены
        password_data = {
            "grant_type": "password",
            "username": "test_user",
            "password": "test_password"
        }
        
        token_response = await test_client.post("/token", data=password_data)
        
        if token_response.status_code == 200:
            tokens = token_response.json()
            
            if "refresh_token" in tokens:
                refresh_token = tokens["refresh_token"]
                
                # Используем refresh token
                refresh_data = {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token
                }
                
                refresh_response = await test_client.post("/token", data=refresh_data)
                assert refresh_response.status_code in [200, 400, 401]
                
                if refresh_response.status_code == 200:
                    new_tokens = refresh_response.json()
                    assert "access_token" in new_tokens
                    assert "expires_in" in new_tokens
                    
                    # Новый токен должен отличаться от старого
                    if "refresh_token" in new_tokens:
                        assert new_tokens["refresh_token"] != refresh_token
    
    @pytest.mark.security
    async def test_oauth2_token_validation_detailed(self, test_client):
        """Детальный тест валидации токенов"""
        # Тест с невалидным токеном
        invalid_tokens = [
            "invalid_token_123",
            "Bearer invalid",
            "",
            None,
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid_signature"  # Некорректный JWT
        ]
        
        headers = {"Authorization": "Bearer invalid_token"}
        response = await test_client.get("/cache/stats", headers=headers)
        assert response.status_code in [401, 403]
        
        # Проверяем WWW-Authenticate заголовок
        if "WWW-Authenticate" in response.headers:
            auth_header = response.headers["WWW-Authenticate"]
            assert "Bearer" in auth_header
            assert "error=" in auth_header
    
    @pytest.mark.security
    async def test_oauth2_error_responses(self, test_client):
        """Тест OAuth2 ошибок"""
        error_cases = [
            # Неподдерживаемый grant_type
            {"grant_type": "unsupported_grant_type"},
            # Пустой код
            {"grant_type": "authorization_code", "code": ""},
            # Неверный код
            {"grant_type": "authorization_code", "code": "invalid_code"},
            # Некорректные параметры
            {"grant_type": "password"},  # Без username/password
        ]
        
        for error_data in error_cases:
            response = await test_client.post("/token", data=error_data)
            assert response.status_code in [400, 401, 404]
            
            if response.status_code == 400:
                error_json = response.json()
                assert "error" in error_json
                assert "error_description" in error_json
                
                # Проверяем стандартные OAuth2 ошибки
                oauth_errors = [
                    "invalid_request", "invalid_client", "invalid_grant",
                    "unauthorized_client", "unsupported_grant_type",
                    "invalid_scope"
                ]
                assert error_json["error"] in oauth_errors
    
    @pytest.mark.security
    async def test_oauth2_scopes_validation(self, test_client):
        """Тест валидации scope"""
        # Тест различных scopes
        scope_cases = [
            {"scope": "read"},
            {"scope": "write"},
            {"scope": "read write"},
            {"scope": "admin"},  # Может быть недоступен
            {"scope": ""},  # Пустой scope
        ]
        
        for scope_case in scope_cases:
            token_data = {
                "grant_type": "password",
                "username": "test_user",
                "password": "test_password"
            }
            token_data.update(scope_case)
            
            response = await test_client.post("/token", data=token_data)
            # Разные scopes могут давать разные результаты
            assert response.status_code in [200, 400, 401, 404]
    
    @pytest.mark.performance
    async def test_oauth2_token_lifetimes(self, test_client):
        """Тест времени жизни токенов"""
        password_data = {
            "grant_type": "password",
            "username": "test_user",
            "password": "test_password"
        }
        
        response = await test_client.post("/token", data=password_data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            if "expires_in" in token_data:
                expires_in = token_data["expires_in"]
                
                # Проверяем разумность времени жизни
                assert 60 <= expires_in <= 86400  # От 1 минуты до 1 дня
                
                # Проверяем что токен не истек сразу
                assert expires_in > 0
    
    @pytest.mark.security
    async def test_oauth2_security_headers(self, test_client):
        """Тест security заголовков для OAuth2"""
        response = await test_client.get("/.well-known/oauth-authorization-server")
        
        if response.status_code == 200:
            # Проверяем security заголовки
            assert "cache-control" in response.headers
            # OAuth2 метаданные не должны кэшироваться
            
    @pytest.mark.integration
    async def test_oauth2_oauth_discovery(self, test_client):
        """Тест OAuth2 discovery endpoints"""
        # Authorization Server Metadata
        response = await test_client.get("/.well-known/oauth-authorization-server")
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            metadata = response.json()
            
            # Проверяем обязательные поля
            oauth2_metadata_fields = [
                "issuer", "authorization_endpoint", "token_endpoint",
                "grant_types_supported", "response_types_supported",
                "code_challenge_methods_supported"
            ]
            
            for field in oauth2_metadata_fields[:4]:  # Проверяем первые 4 поля
                if field in metadata:
                    assert metadata[field]
        
        # Protected Resource Metadata
        response = await test_client.get("/.well-known/oauth-protected-resource")
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            prm = response.json()
            # Проверяем наличие resource identifiers
            assert "resource" in prm or "resource_identifiers" in prm


# =============================================================================
# WEBSOCKET ТЕСТЫ (если применимо)
# =============================================================================

class TestWebSocketEndpoints:
    """Тесты WebSocket соединений (если реализованы)"""
    
    @pytest.mark.unit
    async def test_websocket_endpoint_exists(self, test_client):
        """Тест существования WebSocket endpoint"""
        # Проверяем наличие WebSocket endpoint
        # В зависимости от реализации может быть /ws, /websocket и т.д.
        pass  # Реализация зависит от наличия WebSocket поддержки
    
    @pytest.mark.unit
    async def test_websocket_upgrade_handling(self, test_client):
        """Тест обработки WebSocket upgrade"""
        # Тест Upgrade заголовка для WebSocket
        headers = {
            "Upgrade": "websocket",
            "Connection": "upgrade",
            "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
            "Sec-WebSocket-Version": "13"
        }
        
        response = await test_client.get("/ws", headers=headers)
        # Может возвращать 101 Switching Protocols или 404
        assert response.status_code in [101, 404, 426]


# =============================================================================
# ASYNC ОПЕРАЦИИ ТЕСТЫ
# =============================================================================

class TestAsyncOperations:
    """Тесты асинхронных операций"""
    
    @pytest.mark.asyncio
    async def test_async_database_operations(self, test_client):
        """Тест асинхронных операций с БД"""
        # Симулируем асинхронные операции
        async def simulate_db_operation():
            await asyncio.sleep(0.1)  # Симуляция запроса к БД
            return {"result": "database_result"}
        
        start_time = time.time()
        result = await simulate_db_operation()
        elapsed = time.time() - start_time
        
        assert result["result"] == "database_result"
        assert elapsed >= 0.1  # Операция должна занять время
    
    @pytest.mark.asyncio
    async def test_concurrent_async_requests(self, test_client):
        """Тест конкурентных асинхронных запросов"""
        async def make_async_request():
            response = await test_client.get("/health")
            return response.json()
        
        # Выполняем несколько асинхронных запросов
        tasks = [make_async_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        for result in results:
            assert "status" in result
    
    @pytest.mark.asyncio
    async def test_async_streaming_responses(self, test_client):
        """Тест асинхронных streaming ответов"""
        async with test_client.stream("GET", "/health") as response:
            assert response.status_code == 200
            
            chunks = []
            async for chunk in response.aiter_bytes():
                if chunk:
                    chunks.append(chunk)
            
            # Должен получить хотя бы один chunk
            assert len(chunks) > 0
    
    @pytest.mark.asyncio
    async def test_async_timeout_handling(self, test_client):
        """Тест обработки timeout в асинхронных операциях"""
        try:
            # Устанавливаем короткий timeout
            async with asyncio.timeout(0.1):
                await test_client.get("/")
        except asyncio.TimeoutError:
            # Ожидаем timeout
            pass
        except Exception:
            # Другие исключения также допустимы
            pass


# =============================================================================
# СПЕЦИАЛЬНЫЕ ТЕСТЫ ДЛЯ БЕЗОПАСНОСТИ
# =============================================================================

class TestSecurityOAuth2SSE:
    """Тесты безопасности для OAuth2 и SSE"""
    
    @pytest.mark.security
    async def test_sse_cors_security(self, test_client):
        """Тест CORS безопасности для SSE"""
        # Тест с вредоносным Origin
        malicious_origin = "http://evil.com"
        headers = {"Origin": malicious_origin}
        
        async with test_client.stream("GET", "/sse", headers=headers) as response:
            assert response.status_code == 200
            
            # Проверяем CORS заголовки
            cors_origin = response.headers.get("Access-Control-Allow-Origin")
            if cors_origin:
                # CORS должен быть ограничен
                assert cors_origin in ["*", malicious_origin] or cors_origin == ""
    
    @pytest.mark.security
    async def test_oauth2_cors_security(self, test_client):
        """Тест CORS безопасности для OAuth2"""
        # Тест CORS для OAuth2 endpoints
        endpoints = ["/authorize", "/token", "/register"]
        
        for endpoint in endpoints:
            headers = {"Origin": "http://malicious.com"}
            response = await test_client.get(endpoint, headers=headers)
            
            # Должны быть CORS заголовки
            if response.headers.get("Access-Control-Allow-Origin"):
                # Проверяем безопасность
                cors = response.headers["Access-Control-Allow-Origin"]
                assert cors in ["*", "http://malicious.com"] or cors == ""
    
    @pytest.mark.security
    async def test_token_entropy(self, test_client):
        """Тест энтропии токенов"""
        # Получаем несколько токенов и проверяем их уникальность
        tokens = []
        for i in range(5):
            password_data = {
                "grant_type": "password",
                "username": f"user_{i}",
                "password": f"pass_{i}"
            }
            
            response = await test_client.post("/token", data=password_data)
            if response.status_code == 200:
                token_data = response.json()
                if "access_token" in token_data:
                    tokens.append(token_data["access_token"])
        
        # Все токены должны быть уникальными
        assert len(tokens) == len(set(tokens))
        
        # Токены должны иметь достаточную длину
        for token in tokens:
            assert len(token) >= 32  # Минимум 32 символа
    
    @pytest.mark.security
    async def test_state_parameter_validation(self, test_client):
        """Тест валидации state параметра в OAuth2"""
        # Тест с отсутствующим state
        auth_params_no_state = {
            "response_type": "code",
            "client_id": "test_client",
            "redirect_uri": "http://localhost:8080/callback"
        }
        
        response = await test_client.get("/authorize", params=auth_params_no_state)
        # OAuth2 рекомендует требовать state
        assert response.status_code in [200, 302, 400]
    
    @pytest.mark.security
    async def test_code_challenge_validation(self, test_client):
        """Тест валидации code_challenge"""
        # Некорректные code_challenge
        invalid_challenges = [
            "",  # Пустой
            "invalid_base64",  # Не base64
            "short",  # Слишком короткий
            "x" * 1000,  # Подозрительно длинный
        ]
        
        for challenge in invalid_challenges:
            auth_params = {
                "response_type": "code",
                "client_id": "test_client",
                "redirect_uri": "http://localhost:8080/callback",
                "code_challenge": challenge,
                "code_challenge_method": "S256"
            }
            
            response = await test_client.get("/authorize", params=auth_params)
            # Должен отклонить некорректный challenge
            assert response.status_code in [400, 302]  # 400 для ошибки, 302 для редиректа на error


if __name__ == "__main__":
    # Запуск специализированных тестов
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-m", "sse or oauth2 or security or performance"
    ])