# 🎭 Multi-Role AI Assistant System

## Enterprise 1C AI Development Stack - Расширенная архитектура

**Поддержка всех ролей в команде разработки 1С**

---

## 🎯 Концепция

Система теперь поддерживает **6 ролей**, каждая со своим специализированным AI-ассистентом:

1. **👨‍💻 Developer** - разработчик (уже реализовано)
2. **📊 Business Analyst** - бизнес-аналитик
3. **🧪 QA Engineer** - тестировщик
4. **🏗️ Architect** - архитектор
5. **⚙️ DevOps Engineer** - DevOps инженер
6. **📝 Technical Writer** - технический писатель

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│  EDT Plugin │ Cursor │ VSCode │ Web UI │ CLI             │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│               Role-Based AI Router                       │
│  - Определяет роль пользователя                         │
│  - Маршрутизирует запрос к специализированному агенту   │
│  - Объединяет результаты                                │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌─────────────────┐                    ┌─────────────────┐
│  Developer AI   │                    │ Business AI     │
│  - Qwen3-Coder  │                    │  - GigaChat     │
│  - Code gen     │                    │  - Requirements │
│  - Optimization │                    │  - Documentation│
└─────────────────┘                    └─────────────────┘
        │                                       │
        ▼                                       ▼
┌─────────────────┐                    ┌─────────────────┐
│   QA AI         │                    │  Architect AI   │
│  - Test gen     │                    │  - Architecture │
│  - Coverage     │                    │  - Patterns     │
│  - Bug analysis │                    │  - Best practices│
└─────────────────┘                    └─────────────────┘
        │                                       │
        ▼                                       ▼
┌─────────────────┐                    ┌─────────────────┐
│  DevOps AI      │                    │  TechWriter AI  │
│  - CI/CD        │                    │  - Docs         │
│  - Monitoring   │                    │  - Guides       │
│  - Performance  │                    │  - API docs     │
└─────────────────┘                    └─────────────────┘
```

---

## 👥 Роли и возможности

### 1. 👨‍💻 **Developer (Разработчик)**

**AI Agent:** Qwen3-Coder + 1С:Напарник

**Возможности:**
- ✅ Генерация BSL кода
- ✅ Оптимизация функций
- ✅ Рефакторинг
- ✅ Поиск похожего кода
- ✅ Анализ зависимостей
- ✅ Code review
- ✅ Исправление ошибок
- ✅ Генерация unit-тестов

**MCP Tools:**
- `generate_bsl_code`
- `optimize_function`
- `analyze_dependencies`
- `search_code_semantic`
- `refactor_code`
- `explain_code`

---

### 2. 📊 **Business Analyst (Бизнес-аналитик)**

**AI Agent:** GigaChat + YandexGPT (русский язык)  
**Рынок 2025 Q4:** см. `docs/research/job_market_business_analyst.md` (hh.ru / LinkedIn / Glassdoor: требования, зарплаты, компетенции)  
**Roadmap:** `docs/research/ba_agent_roadmap.md`

**Возможности (as-is):**
- Анализ требований (регексы)  
- Генерация технических заданий (шаблон)  
- Создание пользовательских сценариев  
- Анализ бизнес-процессов (упрощённый BPMN)  
- Генерация документации на русском  
- Извлечение требований из текста  
- Создание use-case диаграмм (PlantUML)  
- Анализ gap (текущие vs желаемые процессы)

**Пробелы (по исследованию рынка):**
- Нужны LLM/NLP для требований, user stories, acceptance criteria  
- CLI: `python -m scripts.ba.requirements_cli extract <файл>` (`make ba-extract`)  
- Расширенный BPMN/CJM/Service Blueprint + экспорт BPMN 2.0  
- Интеграции Jira/Confluence/ServiceNow, sync артефактов  
- SQL/BI, KPI/OKR, ROI/TCO, Risk & Compliance (GDPR/SOX)  
- Автогенерация roadmap, BRD/SRS, traceability ⇄ релизы/риски  
- Метрики эффективности, интеграция с DevOps/QA агентами

**MCP Tools:**
- `analyze_requirements`
- `generate_technical_spec`
- `extract_user_stories`
- `generate_use_cases`
- `analyze_business_process`
- `generate_documentation`

**EDT Views:**
- Requirements Analyzer
- Technical Spec Generator
- Business Process Viewer

---

### 3. 🧪 **QA Engineer (Тестировщик)**

**AI Agent:** Qwen3-Coder (для тестов) + специализированная модель

**Возможности:**
- Генерация smoke-тестов
- Генерация Vanessa BDD сценариев
- Анализ покрытия тестами
- Генерация тестовых данных
- Анализ багов и поиск причин
- Регрессионное тестирование
- Генерация чек-листов
- Автоматизация тестирования

**MCP Tools:**
- `generate_vanessa_tests`
- `generate_smoke_tests`
- `analyze_test_coverage`
- `generate_test_data`
- `analyze_bug`
- `generate_regression_tests`

**EDT Views:**
- Test Coverage Viewer
- Vanessa Test Generator
- Bug Analyzer

---

### 4. 🏗️ **Architect (Архитектор)**

**AI Agent:** GPT-4 / Claude (архитектурные паттерны)

**Возможности:**
- Анализ архитектуры конфигурации
- Рекомендации по паттернам
- Проверка best practices
- Анализ зависимостей модулей
- Выявление anti-patterns
- Генерация архитектурных диаграмм
- Code smell detection
- Технический долг (technical debt)

**MCP Tools:**
- `analyze_architecture`
- `check_best_practices`
- `detect_anti_patterns`
- `analyze_module_coupling`
- `calculate_technical_debt`
- `generate_architecture_diagram`

**EDT Views:**
- Architecture Analyzer
- Dependency Graph
- Technical Debt Dashboard
- Pattern Recommendations

---

### 5. ⚙️ **DevOps Engineer**

**AI Agent:** Специализированная модель для DevOps

**Возможности:**
- Оптимизация CI/CD pipeline
- Анализ производительности
- Рекомендации по мониторингу
- Генерация Docker/K8s манифестов
- Анализ логов
- Capacity planning
- Автоматизация deployment
- Infrastructure as Code

**MCP Tools:**
- `optimize_cicd`
- `analyze_performance`
- `analyze_logs`
- `generate_k8s_manifest`
- `recommend_monitoring`
- `capacity_planning`

**EDT Views:**
- Performance Dashboard
- CI/CD Pipeline Viewer
- Log Analyzer
- Monitoring Recommendations

---

### 6. 📝 **Technical Writer (Технический писатель)**

**AI Agent:** GPT-4 (документация) + русификация

**Возможности:**
- Генерация API документации
- Создание user guides
- Генерация README
- Документирование функций/модулей
- Генерация справки (CHM/HTML)
- Создание release notes
- Переводы (EN ↔ RU)
- Генерация диаграмм

**MCP Tools:**
- `generate_api_docs`
- `generate_user_guide`
- `document_function`
- `generate_release_notes`
- `translate_documentation`
- `generate_diagrams`

**EDT Views:**
- Documentation Generator
- API Explorer
- Release Notes Builder

---

## 🔄 Role-Based Routing

### Автоматическое определение роли:

```python
class RoleDetector:
    def detect_role(self, query: str, context: Dict) -> str:
        """Определяет роль по запросу и контексту"""
        
        # По keywords
        if any(kw in query for kw in ["сгенерируй код", "напиши функцию"]):
            return "developer"
        
        if any(kw in query for kw in ["требования", "ТЗ", "бизнес-процесс"]):
            return "business_analyst"
        
        if any(kw in query for kw in ["тест", "покрытие", "баг"]):
            return "qa_engineer"
        
        if any(kw in query for kw in ["архитектура", "паттерн", "зависимости"]):
            return "architect"
        
        if any(kw in query for kw in ["CI/CD", "deployment", "производительность"]):
            return "devops"
        
        if any(kw in query for kw in ["документация", "описание", "справка"]):
            return "technical_writer"
        
        # По контексту (открытый файл, текущая задача)
        if context.get("current_file", "").endswith(".bsl"):
            return "developer"
        
        # Default
        return "developer"
```

### Ручной выбор роли:

```python
# В EDT плагине
role_selector = RoleSelector()
role = role_selector.select()  # "Developer", "QA", "Architect", ...

# В Cursor/VSCode через команду
# /role switch qa
```

---

## 📊 Примеры использования

### Developer:
```
User: "Создай функцию проверки ИНН физического лица"
AI (Qwen3-Coder): [генерирует BSL код с валидацией]
```

### Business Analyst:
```
User: "Проанализируй требования из документа ТЗ.docx и создай user stories"
AI (GigaChat): [извлекает требования, генерирует user stories на русском]
```

### QA Engineer:
```
User: "Сгенерируй Vanessa BDD тесты для модуля ПродажиСервер"
AI: [генерирует .feature файлы с Given/When/Then сценариями]
```

### Architect:
```
User: "Проанализируй архитектуру конфигурации и найди циклические зависимости"
AI: [анализирует граф Neo4j, выявляет проблемы, предлагает решения]
```

### DevOps:
```
User: "Оптимизируй производительность запросов к БД"
AI: [анализирует логи, SQL, предлагает индексы и оптимизации]
```

### Technical Writer:
```
User: "Сгенерируй API документацию для всех экспортных функций модуля"
AI: [создает markdown/HTML с описанием параметров, возвращаемых значений, примерами]
```

---

## 🎨 UI для разных ролей

### EDT Plugin - Role Switcher:

```
┌─────────────────────────────────────────┐
│  1C AI Assistant                   [▼] │  ← Role selector
├─────────────────────────────────────────┤
│  Current Role: 👨‍💻 Developer           │
│                                         │
│  Quick Actions:                         │
│  • Generate Code                        │
│  • Optimize Function                    │
│  • Find Similar Code                    │
│  • Analyze Dependencies                 │
│                                         │
│  [Switch Role ▼]                        │
│    👨‍💻 Developer                        │
│    📊 Business Analyst                  │
│    🧪 QA Engineer                       │
│    🏗️ Architect                         │
│    ⚙️ DevOps                            │
│    📝 Technical Writer                  │
└─────────────────────────────────────────┘
```

### Cursor/VSCode MCP:

```json
{
  "tools": [
    // Developer
    {"name": "dev:generate_code"},
    {"name": "dev:optimize"},
    
    // Business Analyst
    {"name": "ba:analyze_requirements"},
    {"name": "ba:generate_spec"},
    
    // QA
    {"name": "qa:generate_tests"},
    {"name": "qa:analyze_coverage"},
    
    // Architect
    {"name": "arch:analyze_architecture"},
    {"name": "arch:check_patterns"},
    
    // DevOps
    {"name": "devops:optimize_cicd"},
    {"name": "devops:analyze_performance"},
    
    // Technical Writer
    {"name": "tw:generate_docs"},
    {"name": "tw:generate_api_docs"}
  ]
}
```

---

## 💾 Database Schema Extension

### Новая таблица: user_roles

```sql
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    username VARCHAR(255) NOT NULL,
    primary_role VARCHAR(50) NOT NULL,
    secondary_roles JSONB,
    preferences JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_user_roles_username ON user_roles(username);
CREATE INDEX idx_user_roles_primary_role ON user_roles(primary_role);
```

### Новая таблица: role_interactions

```sql
CREATE TABLE role_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL,
    query TEXT NOT NULL,
    ai_agent VARCHAR(100),
    response_summary TEXT,
    satisfaction_score INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Аналитика по ролям
CREATE INDEX idx_interactions_role ON role_interactions(role);
CREATE INDEX idx_interactions_created_at ON role_interactions(created_at);
```

---

## 🔧 Конфигурация AI агентов

### config/role_agents.yaml:

```yaml
roles:
  developer:
    primary_agent: qwen3-coder
    fallback_agents:
      - 1c-naparnik
      - openai-gpt4
    specializations:
      - code_generation
      - optimization
      - refactoring
    temperature: 0.2
    max_tokens: 2000
  
  business_analyst:
    primary_agent: gigachat
    fallback_agents:
      - yandex-gpt
      - openai-gpt4
    specializations:
      - requirements_analysis
      - documentation
      - business_process
    temperature: 0.5
    max_tokens: 4000
    language: ru
  
  qa_engineer:
    primary_agent: qwen3-coder
    fallback_agents:
      - openai-gpt4
    specializations:
      - test_generation
      - bug_analysis
      - coverage_analysis
    temperature: 0.3
    max_tokens: 2000
  
  architect:
    primary_agent: openai-gpt4
    fallback_agents:
      - claude-3-opus
    specializations:
      - architecture_analysis
      - pattern_detection
      - best_practices
    temperature: 0.4
    max_tokens: 3000
  
  devops:
    primary_agent: openai-gpt4
    fallback_agents:
      - qwen3-coder
    specializations:
      - cicd_optimization
      - performance_analysis
      - infrastructure
    temperature: 0.3
    max_tokens: 2000
  
  technical_writer:
    primary_agent: openai-gpt4
    fallback_agents:
      - gigachat
    specializations:
      - documentation_generation
      - api_docs
      - translations
    temperature: 0.6
    max_tokens: 4000
```

---

## 📈 Метрики по ролям

### Grafana Dashboard - Role-based metrics:

```
┌────────────────────────────────────────────────┐
│  AI Assistant Usage by Role                    │
├────────────────────────────────────────────────┤
│  👨‍💻 Developer:        1,250 requests (45%)    │
│  📊 Business Analyst:   400 requests (14%)     │
│  🧪 QA Engineer:        650 requests (23%)     │
│  🏗️ Architect:         280 requests (10%)     │
│  ⚙️ DevOps:            150 requests (5%)      │
│  📝 Technical Writer:    70 requests (3%)      │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  Satisfaction Score by Role                    │
├────────────────────────────────────────────────┤
│  Developer:        ★★★★★ 4.8/5.0              │
│  Business Analyst: ★★★★☆ 4.5/5.0              │
│  QA Engineer:      ★★★★★ 4.9/5.0              │
│  Architect:        ★★★★☆ 4.6/5.0              │
│  DevOps:           ★★★★☆ 4.7/5.0              │
│  Technical Writer: ★★★★★ 4.8/5.0              │
└────────────────────────────────────────────────┘
```

---

## 🎯 Roadmap

**Phase 1 (Week 1-2):** ✅ Developer (done)  
**Phase 2 (Week 3-4):** Business Analyst + QA Engineer  
**Phase 3 (Week 5-6):** Architect + DevOps  
**Phase 4 (Week 7-8):** Technical Writer + polish  

---

## 💰 Ценность для бизнеса

**До:**
- Developer AI: $15,000/год экономии

**После (Multi-Role):**
- Developer AI: $15,000/год
- Business Analyst AI: $10,000/год
- QA Engineer AI: $12,000/год
- Architect AI: $8,000/год
- DevOps AI: $7,000/год
- Technical Writer AI: $5,000/год

**TOTAL: $57,000/год экономии!** 💰

---

## 📚 См. также

-  - базовая маршрутизация
-  - интеграция с IDE
-  - протокол интеграции

