# Owned runtime register fixture v1

`owner-indicators.json` — синтетический retained export одного регистра
`InformationRegister.OwnerIndicators` для проверки offline runtime producer.
Файл не получен из рабочей базы 1С; 42 заказа и 1250.5 RUB иллюстрируют контракт,
а project/snapshot/commit служат тестовыми идентичностями.

Trusted pins в `tests/unit/test_runtime_producer.py` заданы независимо от JSON:

- период: `2026-09-01T00:00:00Z` — `2026-09-07T23:59:59Z`;
- часы проверки: `2026-09-08T00:00:00Z`;
- ожидаемые показатели: `orders_count`, `revenue_amount`;
- canonical rows SHA-256: `448d67f970911ba5bfb53a595730b61538a3fe0d3169031d6baab16eb164e496`.

Запуск из корня репозитория на поддерживаемой Windows-платформе:

```powershell
python -m pytest tests/unit/test_runtime_producer.py -q
```

Тесты копируют fixture в отдельный временный каталог, инициализируют owned
receipt store и проверяют публичную цепочку producer → source loader → owner
report → immutable receipt. Для отказов изменяются только временные копии.
Требуются те же no-follow retained handles и fixed local volume, что у source
adapter. Процессы 1С, SQL, подключения к сети и секреты не используются.
