
"""
Load Tests для системы Rate Limiting с использованием Locust

Запуск:
    locust -f tests/loadtest_ratelimit.py --host=http://localhost:8000
    
Для distributed тестирования:
    locust -f tests/loadtest_ratelimit.py --master
    locust -f tests/loadtest_ratelimit.py --slave --master-host=192.168.1.100

Версия: 1.0.0
"""

import random
import time

from locust import HttpUser, between, events, task


class RateLimitLoadTestUser(HttpUser):
    """Пользователь для нагрузочного тестирования rate limiting"""
    
    wait_time = between(0.1, 0.5)  # Быстрые запросы для нагрузки
    weight = 3  # Высокий вес для максимальной нагрузки
    
    def on_start(self):
        """Инициализация при старте пользователя"""
        self.user_id = f"load_test_user_{random.randint(1000, 9999)}"
        self.headers = {
            "Content-Type": "application/json",
            "X-User-ID": self.user_id
        }
    
    @task(5)
    def test_public_endpoint(self):
        """Тест публичного endpoint с лимитами"""
        with self.client.get(
            "/public",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure(f"Rate limited on public endpoint: {response.text}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(3)
    def test_api_endpoint(self):
        """Тест API endpoint"""
        with self.client.get(
            "/api/data",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure(f"Rate limited on API endpoint: {response.text}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def test_admin_endpoint(self):
        """Тест admin endpoint (более строгие лимиты)"""
        with self.client.get(
            "/admin",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # Для admin endpoint это ожидаемо при высокой нагрузке
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def test_process_endpoint(self):
        """Тест endpoint с обработкой"""
        data = {
            "action": "process_data",
            "user_id": self.user_id,
            "timestamp": int(time.time())
        }
        
        with self.client.post(
            "/process",
            headers=self.headers,
            json=data,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure(f"Rate limited on process endpoint: {response.text}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class BurstAttackUser(HttpUser):
    """Пользователь для симуляции burst атак"""
    
    wait_time = between(0.01, 0.05)  # Очень быстрые запросы
    weight = 1  # Низкий вес, запускается реже
    
    def on_start(self):
        """Инициализация burst атаки"""
        self.attacker_id = f"burst_attacker_{random.randint(100, 999)}"
        self.headers = {
            "Content-Type": "application/json",
            "X-Attacker-ID": self.attacker_id,
            "User-Agent": f"BurstBot/1.0 ({random.choice(['Chrome', 'Firefox', 'Safari'])})"
        }
    
    @task(10)
    def burst_attack_public(self):
        """Burst атака на публичный endpoint"""
        # Быстрая последовательность запросов
        with self.client.get(
            "/public",
            headers=self.headers,
            catch_response=True,
            name="burst_public"
        ) as response:
            if response.status_code == 200:
                # Некоторые запросы могут пройти
                pass
            elif response.status_code == 429:
                # Большинство должно быть заблокировано
                pass
            else:
                response.failure(f"Burst attack failed: {response.status_code}")


class DistributedAttackUser(HttpUser):
    """Пользователь для симуляции распределенных атак"""
    
    wait_time = between(0.1, 0.3)
    weight = 1
    
    def on_start(self):
        """Инициализация распределенной атаки"""
        # Различные IP адреса для симуляции распределенной атаки
        self.ip_ranges = [
            "192.168.1.{}".format(random.randint(1, 254)),
            "10.0.0.{}".format(random.randint(1, 254)),
            "172.16.0.{}".format(random.randint(1, 254)),
            "203.0.113.{}".format(random.randint(1, 254))  # TEST-NET-3
        ]
        
        self.attacker_id = f"dist_attacker_{random.randint(1000, 9999)}"
    
    @task(1)
    def distributed_attack_varied_ips(self):
        """Атака с вариацией IP адресов"""
        for ip in random.sample(self.ip_ranges, random.randint(2, 4)):
            headers = {
                "Content-Type": "application/json",
                "X-Forwarded-For": ip,
                "X-Real-IP": ip,
                "X-Attacker-ID": self.attacker_id
            }
            
            with self.client.get(
                "/api/data",
                headers=headers,
                catch_response=True,
                name=f"distributed_{ip}"
            ) as response:
                if response.status_code == 429:
                    # Атака заблокирована
                    pass
                elif response.status_code == 200:
                    # Некоторые запросы могут пройти
                    pass


class PremiumUser(HttpUser):
    """Пользователь с премиум доступом (более высокие лимиты)"""
    
    wait_time = between(0.05, 0.2)
    weight = 2
    
    def on_start(self):
        """Инициализация премиум пользователя"""
        self.user_id = f"premium_user_{random.randint(10000, 99999)}"
        self.headers = {
            "Content-Type": "application/json",
            "X-User-ID": self.user_id,
            "X-User-Type": "premium",
            "Authorization": f"Bearer premium_token_{self.user_id}"
        }
    
    @task(3)
    def premium_api_access(self):
        """Доступ к API для премиум пользователей"""
        with self.client.get(
            "/api/data",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # Премиум пользователи должны иметь более высокие лимиты
                response.failure(f"Premium user rate limited: {response.text}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def premium_admin_access(self):
        """Доступ к admin функциям для премиум пользователей"""
        with self.client.get(
            "/admin",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.success()  # Допустимо при высокой нагрузке
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class AdaptiveLoadTestUser(HttpUser):
    """Пользователь с адаптивной нагрузкой"""
    
    wait_time = between(0.1, 0.5)
    weight = 2
    
    def on_start(self):
        """Инициализация адаптивного тестирования"""
        self.request_count = 0
        self.error_count = 0
        self.user_id = f"adaptive_user_{random.randint(1000, 9999)}"
        self.headers = {
            "Content-Type": "application/json",
            "X-User-ID": self.user_id
        }
    
    @task(5)
    def adaptive_load_test(self):
        """Адаптивный тест нагрузки"""
        self.request_count += 1
        
        endpoint = random.choice(["/public", "/api/data"])
        
        with self.client.get(
            endpoint,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                if self.error_count > 0:
                    self.error_count -= 1  # Восстановление после ошибок
            elif response.status_code == 429:
                self.error_count += 1
                
                # Если слишком много ошибок, замедляемся
                if self.error_count > 10:
                    self.wait_time = between(0.5, 1.0)
            else:
                response.failure(f"Unexpected status: {response.status_code}")
                self.error_count += 2


# =============================================================================
# EVENT HANDLERS ДЛЯ СБОРА МЕТРИК
# =============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Обработчик начала тестирования"""
    print("=== Rate Limiting Load Test Starting ===")
    print(f"Target host: {environment.host}")
    print(f"Run time: {environment.runner.target_time}s" if hasattr(environment.runner, 'target_time') else "Unlimited")
    print("Users will be spawned according to the defined load shape")
    print("=" * 50)


@events.test_stop.add_listener  
def on_test_stop(environment, **kwargs):
    """Обработчик окончания тестирования"""
    print("\n=== Rate Limiting Load Test Completed ===")
    
    # Статистика по типам запросов
    stats = environment.stats
    print(f"\nTotal requests: {stats.total.num_requests}")
    print(f"Failures: {stats.total.num_failures}")
    print(f"Fail rate: {stats.total.num_failures / max(stats.total.num_requests, 1) * 100:.1f}%")
    
    # Детальная статистика по endpoint'ам
    print("\n=== Endpoint Statistics ===")
    for name, stat in stats.entries.items():
        if stat.num_requests > 0:
            avg_response_time = stat.avg_response_time
            median = stat.median_response_time  
            requests_per_sec = stat.num_requests / max(stat.total_time, 0.001)
            failure_rate = stat.num_failures / max(stat.num_requests, 1) * 100
            
            print(f"{name}:")
            print(f"  Requests: {stat.num_requests}")
            print(f"  Avg Response Time: {avg_response_time:.2f}ms")
            print(f"  Median Response Time: {median:.2f}ms")
            print(f"  Requests/sec: {requests_per_sec:.1f}")
            print(f"  Failure rate: {failure_rate:.1f}%")
    
    print("=" * 50)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Обработчик каждого запроса для дополнительного логирования"""
    if exception:
        print(f"REQUEST FAILED: {request_type} {name} - {exception}")


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Обработчик завершения тестирования"""
    if environment.stats.total.num_failures > 0:
        print(f"\n⚠️  Test completed with {environment.stats.total.num_failures} failures")
        return False  # Не останавливать locust при ошибках
    else:
        print("\n✅ Test completed successfully with no failures")
        return True


# =============================================================================
# MASTER/SLAVE EVENT HANDLERS
# =============================================================================

@events.master_quitting.add_listener
def on_master_quitting(environment, **kwargs):
    """Обработчик завершения master узла"""
    print("Master node is quitting. Slave nodes will be stopped.")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_load_test_scenarios():
    """Создать различные сценарии нагрузочного тестирования"""
    scenarios = {
        "normal_load": {
            "users": 100,
            "spawn_rate": 5,
            "duration": "5m",
            "description": "Нормальная нагрузка"
        },
        "high_load": {
            "users": 500,
            "spawn_rate": 10,
            "duration": "10m", 
            "description": "Высокая нагрузка"
        },
        "stress_test": {
            "users": 1000,
            "spawn_rate": 20,
            "duration": "15m",
            "description": "Стресс тест"
        },
        "burst_test": {
            "users": 50,
            "spawn_rate": 50,  # Быстрый запуск
            "duration": "2m",
            "description": "Burst атака"
        },
        "distributed_test": {
            "users": 200,
            "spawn_rate": 8,
            "duration": "8m",
            "description": "Распределенная атака"
        }
    }
    return scenarios


def get_endpoint_weights():
    """Получить веса для различных endpoint'ов"""
    return {
        "/public": 5,      # Самый доступный endpoint
        "/api/data": 3,    # Основной API endpoint
        "/process": 2,     # Endpoint с обработкой
        "/admin": 1        # Наиболее ограниченный endpoint
    }


# =============================================================================
# CONFIGURATION CLASS
# =============================================================================

class LoadTestConfig:
    """Конфигурация для нагрузочного тестирования"""
    
    # Настройки по умолчанию
    BASE_URL = "http://localhost:8000"
    DEFAULT_HEADERS = {
        "Content-Type": "application/json",
        "User-Agent": "LocustRateLimitTest/1.0"
    }
    
    # Параметры тестирования
    MIN_WAIT = 0.1
    MAX_WAIT = 0.5
    
    # Лимиты для тестирования
    REQUESTS_PER_SECOND_LIMIT = 1000
    CONCURRENT_USERS_LIMIT = 1000
    
    @classmethod
    def get_user_classes(cls):
        """Получить классы пользователей для тестирования"""
        return [
            RateLimitLoadTestUser,
            BurstAttackUser, 
            DistributedAttackUser,
            PremiumUser,
            AdaptiveLoadTestUser
        ]


if __name__ == "__main__":
    # Для автономного запуска
    import argparse
    
    parser = argparse.ArgumentParser(description="Rate Limiting Load Test")
    parser.add_argument("--host", default="http://localhost:8000", help="Target host")
    parser.add_argument("--users", type=int, default=100, help="Number of concurrent users")
    parser.add_argument("--spawn-rate", type=int, default=5, help="User spawn rate")
    parser.add_argument("--duration", default="5m", help="Test duration")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    
    args = parser.parse_args()
    
    print(f"Starting load test against {args.host}")
    print(f"Users: {args.users}, Spawn rate: {args.spawn_rate}, Duration: {args.duration}")
    
    # В production здесь был бы запуск locust programmatically
    print("Use: locust -f tests/loadtest_ratelimit.py --host={}".format(args.host))