# 1C:EDT Integration Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - интеграция с EDT уникальна

---

## Обзор

**1C:EDT Integration Standard** — формальная спецификация для интеграции с 1C:EDT (Eclipse Development Tools). Определяет визуализацию Unified Change Graph в EDT, real-time code review в IDE, AI suggestions во время написания кода и интеграцию с AI агентами.

---

## 1. Интеграция с EDT Plugin

### 1.1 Views (Представления)

**Типы представлений:**

```java
public interface EDTView {
    String getId();                              // ID представления
    String getName();                            // Имя представления
    void initialize(IWorkbenchPartSite site);    // Инициализация
    void update(GraphData data);                 // Обновление данных
    void dispose();                              // Очистка ресурсов
}
```

**Доступные представления:**

1. **AI Assistant** — Chat interface с AI о конфигурации 1C
2. **Metadata Graph** — Визуализация графа метаданных из Neo4j
3. **Semantic Search** — Поиск кода по смыслу через векторный поиск
4. **Code Optimizer** — AI-оптимизация кода
5. **Analysis Dashboard** — Отображение результатов анализа конфигурации

### 1.2 Actions (Действия)

**Context Menu Actions:**

```java
public interface EDTAction {
    String getId();                              // ID действия
    String getName();                            // Имя действия
    void execute(BSLFunction function);          // Выполнение действия
    boolean isEnabled(BSLFunction function);     // Проверка доступности
}
```

**Доступные действия:**

- **Quick Analysis** — Быстрый анализ функции (метрики, зависимости, проблемы)
- **Analyze with AI** — AI анализ функции
- **Optimize Function** — AI предложения по оптимизации
- **Find Similar Code** — Поиск семантически похожего кода
- **Show Call Graph** — Визуализация зависимостей функций

---

## 2. Визуализация Unified Change Graph в EDT

### 2.1 Граф метаданных

```java
public class MetadataGraphView extends ViewPart {
    
    private GraphViewer graphViewer;
    
    @Override
    public void createPartControl(Composite parent) {
        // Создание визуализатора графа
        graphViewer = new GraphViewer(parent, SWT.NONE);
        
        // Загрузка графа из backend
        loadGraphFromBackend();
    }
    
    private void loadGraphFromBackend() {
        // Подключение к Graph API
        GraphAPIClient client = new GraphAPIClient("http://localhost:8080");
        
        // Получение графа
        GraphData graph = client.getGraph("metadata");
        
        // Отображение графа
        graphViewer.setGraph(graph);
    }
}
```

### 2.2 Call Graph

```java
public class CallGraphView extends ViewPart {
    
    public void showFunctionCallGraph(BSLFunction function) {
        // Получение графа вызовов из backend
        GraphAPIClient client = new GraphAPIClient("http://localhost:8080");
        
        // Поиск узла функции в графе
        GraphNode node = client.findNode("function", function.getFullName());
        
        // Получение зависимостей
        List<GraphNode> dependencies = client.getNeighbors(
            node.getId(),
            EdgeKind.BSL_CALLS
        );
        
        // Визуализация графа
        visualizeCallGraph(node, dependencies);
    }
}
```

---

## 3. Real-time Code Review в IDE

### 3.1 Интеграция с BSL Parser

```java
public class RealtimeCodeReviewer {
    
    private BSLParser parser;
    private AIReviewer aiReviewer;
    
    public void analyzeCode(BSLModule module) {
        // Парсинг BSL кода
        ParseResult parsed = parser.parse(module.getContent());
        
        // AI анализ
        ReviewResult review = aiReviewer.review(parsed);
        
        // Отображение проблем в IDE
        displayIssues(review.getIssues());
    }
    
    private void displayIssues(List<Issue> issues) {
        for (Issue issue : issues) {
            // Создание маркера в IDE
            IMarker marker = createMarker(issue);
            
            // Отображение проблемы в редакторе
            displayInEditor(marker, issue);
        }
    }
}
```

### 3.2 Отображение проблем

```java
public class IssueMarker {
    
    public static IMarker createMarker(
        IResource resource,
        Issue issue
    ) throws CoreException {
        IMarker marker = resource.createMarker(MARKER_TYPE);
        
        marker.setAttribute(IMarker.SEVERITY, mapSeverity(issue.getSeverity()));
        marker.setAttribute(IMarker.MESSAGE, issue.getMessage());
        marker.setAttribute(IMarker.LINE_NUMBER, issue.getLine());
        marker.setAttribute(IMarker.LOCATION, issue.getSuggestion());
        
        return marker;
    }
    
    private static int mapSeverity(String severity) {
        switch (severity) {
            case "critical": return IMarker.SEVERITY_ERROR;
            case "high": return IMarker.SEVERITY_WARNING;
            case "medium": return IMarker.SEVERITY_WARNING;
            case "low": return IMarker.SEVERITY_INFO;
            default: return IMarker.SEVERITY_INFO;
        }
    }
}
```

---

## 4. AI Suggestions во время написания кода

### 4.1 Content Assist

```java
public class AIContentAssistProcessor implements IContentAssistProcessor {
    
    private AIOrchestrator orchestrator;
    
    @Override
    public ICompletionProposal[] computeCompletionProposals(
        ITextViewer viewer,
        int offset
    ) {
        // Получение контекста кода
        String code = getCodeContext(viewer, offset);
        
        // Генерация предложений через AI
        List<Suggestion> suggestions = orchestrator.generateSuggestions(code);
        
        // Преобразование в предложения IDE
        return suggestions.stream()
            .map(this::createProposal)
            .toArray(ICompletionProposal[]::new);
    }
}
```

### 4.2 Quick Fix

```java
public class AIQuickFixProcessor implements IQuickFixProcessor {
    
    @Override
    public IQuickFixProcessor[] getQuickFixProcessors(
        String markerType
    ) {
        return new IQuickFixProcessor[] {
            new SecurityQuickFix(),
            new PerformanceQuickFix(),
            new BestPracticesQuickFix(),
        };
    }
    
    @Override
    public void applyQuickFix(
        IMarker marker,
        IQuickFix fix
    ) {
        // Применение исправления через AI
        String fixedCode = aiFixer.fix(marker);
        
        // Обновление кода в редакторе
        updateCodeInEditor(marker, fixedCode);
    }
}
```

---

## 5. Интеграция с AI агентами

### 5.1 Вызов агентов из EDT

```java
public class AIAgentIntegration {
    
    private MCPClient mcpClient;
    
    public String generateCode(String prompt) {
        // Вызов AI агента через MCP
        MCPRequest request = new MCPRequest(
            "generate_bsl_code",
            Map.of("prompt", prompt)
        );
        
        MCPResponse response = mcpClient.call(request);
        
        return response.getResult().get("code");
    }
    
    public ReviewResult reviewCode(String code) {
        // Вызов AI ревьюера через MCP
        MCPRequest request = new MCPRequest(
            "review_bsl_code",
            Map.of("code", code)
        );
        
        MCPResponse response = mcpClient.call(request);
        
        return parseReviewResult(response);
    }
}
```

### 5.2 Интеграция с Orchestrator

```java
public class OrchestratorIntegration {
    
    private OrchestratorClient client;
    
    public void runFullAnalysis(EDTProject project) {
        // Запуск полного анализа через Orchestrator
        AnalysisRequest request = new AnalysisRequest(
            project.getConfigurationName(),
            project.getProjectPath()
        );
        
        AnalysisJob job = client.startAnalysis(request);
        
        // Отслеживание прогресса
        monitorAnalysisProgress(job);
    }
    
    private void monitorAnalysisProgress(AnalysisJob job) {
        // Обновление UI при изменении статуса
        job.onStatusChange(status -> {
            updateProgressBar(status.getProgress());
            if (status.isComplete()) {
                displayResults(status.getResults());
            }
        });
    }
}
```

---

## 6. JSON Schema для EDT интеграции

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/edt-integration/v1",
  "title": "EDTIntegrationMessage",
  "type": "object",
  "required": ["type", "data"],
  "properties": {
    "type": {
      "type": "string",
      "enum": ["analyze", "generate", "review", "optimize", "search"]
    },
    "data": {"type": "object"},
    "response": {"type": "object"}
  }
}
```

---

## 7. Примеры использования

### 7.1 Анализ функции

```java
// В EDT Plugin
BSLFunction function = getSelectedFunction();

// Вызов AI анализатора
AIAgentIntegration integration = new AIAgentIntegration();
ReviewResult result = integration.reviewCode(function.getCode());

// Отображение результатов
displayIssues(result.getIssues());
```

### 7.2 Генерация кода

```java
// В EDT Plugin
String prompt = getUserPrompt();

// Вызов генератора
AIAgentIntegration integration = new AIAgentIntegration();
String generatedCode = integration.generateCode(prompt);

// Вставка кода в редактор
insertCodeAtCursor(generatedCode);
```

---

## 8. Следующие шаги

1. **Реализация EDT Plugin** — завершение реализации всех views и actions
2. **Интеграция с backend** — подключение к Graph API и MCP Server
3. **Тестирование** — создание тестовых случаев для различных сценариев использования

---

**Примечание:** Этот стандарт обеспечивает полную интеграцию 1C:EDT с платформой 1C AI Stack, делая AI возможности доступными прямо в IDE.

