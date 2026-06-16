# YAxUnit - Фреймворк для тестирования BSL кода

YAxUnit установлен в проекте для тестирования BSL кода и AI-сгенерированных модулей.

## 📜 Авторы и лицензия

**YAxUnit** разработан и поддерживается компанией **[BIA-Technologies Limited Liability Company](http://bia-tech.ru/)**.

- **Автор:** BIA-Technologies Limited Liability Company
- **Лицензия:** [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0.html)
- **Репозиторий:** [bia-technologies/yaxunit](https://github.com/bia-technologies/yaxunit)
- **Документация:** [https://bia-technologies.github.io/yaxunit/](https://bia-technologies.github.io/yaxunit/)
- **Copyright:** © 2021-2025 BIA-Technologies Limited Liability Company

### 🙏 Благодарности

Мы выражаем благодарность команде **BIA-Technologies** за создание и поддержку отличного фреймворка для тестирования BSL кода.

## Структура

```
tools/yaxunit/
├── src/                    # Исходный код расширения YAxUnit
│   └── CommonModules/      # Общие модули YAxUnit
├── README.md              # Этот файл
└── ...
```

## Использование

YAxUnit запускается через 1С:Предприятие с параметром `RunUnitTests` и JSON конфигурацией.

См. документацию:
- [Официальная документация YAxUnit](https://bia-technologies.github.io/yaxunit/)
- [Документация в проекте](../../docs/06-features/TESTING_GUIDE.md)
- [Примеры тестов](../../tests/bsl/)

## Запуск тестов

```bash
# Через Makefile
make test-bsl

# Напрямую через скрипт
python scripts/tests/run_bsl_tests.py
```

## Конфигурация

Конфигурация тестов находится в `tests/bsl/testplan.json`.

Пример конфигурации YAxUnit (JSON):
```json
{
    "filter": {
        "modules": ["МодульТестов"]
    },
    "reportPath": "output/bsl-tests/reports/report.xml",
    "reportFormat": "jUnit",
    "closeAfterTests": true,
    "logging": {
        "file": "output/bsl-tests/logs/tests.log",
        "level": "info"
    }
}
```

## Версия

Версия YAxUnit: последняя из `temp_repos/yaxunit/`

Источник: [bia-technologies/yaxunit](https://github.com/bia-technologies/yaxunit)

