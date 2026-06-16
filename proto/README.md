# gRPC Services for 1C AI Stack

Этот каталог содержит Protocol Buffers определения для gRPC сервисов.

## Структура

- `ai_service.proto` - Основные сервисы AI интеграции

## Генерация кода

### Python

```bash
python -m grpc_tools.protoc -I. --python_out=../src/grpc_server --grpc_python_out=../src/grpc_server ai_service.proto
```

### C# (для Everywhere)

```bash
protoc -I. --csharp_out=../external/everywhere/src/Everywhere/Generated --grpc_out=../external/everywhere/src/Everywhere/Generated --plugin=protoc-gen-grpc=grpc_csharp_plugin ai_service.proto
```

## Сервисы

### AIOrchestrator

- `ProcessQuery` - Обработка AI запросов
- `StreamQuery` - Стриминг длинных ответов
- `StreamScreenContext` - Анализ экрана в реальном времени

### CodeGraphService

- `SearchCode` - Поиск по коду
- `AnalyzeDependencies` - Анализ зависимостей
- `GetMetadata` - Получение метаданных объектов 1С

### ScenarioService

- `GetRecommendations` - Рекомендации сценариев
- `ExecuteScenario` - Выполнение сценариев
