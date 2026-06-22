# Enterprise 1C AI Development Stack
# Source Code Package

"""
Инициализация пакета `src`.

Тестовый контур подразумевает наличие `Mock` в глобальном пространстве имен,
однако не все тестовые модули явно импортируют его из `unittest.mock`.
Чтобы избежать `NameError` в подобных сценариях, аккуратно публикуем
`Mock` в builtins (если он там ещё не объявлен).
"""

import builtins
from unittest.mock import Mock  # noqa: F401

if not hasattr(builtins, "Mock"):
    builtins.Mock = Mock
