
"""
Легковесный stub для библиотеки `stripe`, используемый в тестах.

Реальная зависимость не входит в dev-окружение, поэтому предоставляем
минимальный интерфейс, который можно замокать или использовать как no-op.
"""

class _StubCustomer:
    @staticmethod
    def create(*args, **kwargs):
        raise NotImplementedError("Stripe SDK is not installed")


class _StubEvent:
    @staticmethod
    def retrieve(*args, **kwargs):
        raise NotImplementedError("Stripe SDK is not installed")


Customer = _StubCustomer
Event = _StubEvent

