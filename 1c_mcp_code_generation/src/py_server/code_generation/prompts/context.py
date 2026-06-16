
"""
Контекстуальный генератор промптов для адаптации под конкретные ситуации.

Создает оптимизированные промпты на основе контекста использования,
типа проекта, требований к качеству и других параметров.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ComplexityLevel(Enum):
    """Уровни сложности генерации."""
    SIMPLE = "simple"
    STANDARD = "standard"
    ADVANCED = "advanced"
    ENTERPRISE = "enterprise"


class QualityRequirement(Enum):
    """Требования к качеству."""
    HIGH_COVERAGE = "high_coverage"
    PERFORMANCE = "performance"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    COMPLIANCE = "compliance"
    OPTIMIZATION = "optimization"


class ProjectType(Enum):
    """Типы проектов."""
    SMALL_BUSINESS = "small_business"
    MEDIUM_ENTERPRISE = "medium_enterprise"
    LARGE_CORPORATION = "large_corporation"
    CUSTOM_SOLUTION = "custom_solution"
    MIGRATION = "migration"
    INTEGRATION = "integration"


@dataclass
class ContextData:
    """Контекстные данные для генерации промпта."""
    # Основные параметры
    object_type: str  # processing, report, catalog, document
    complexity_level: ComplexityLevel = ComplexityLevel.STANDARD
    quality_requirements: List[QualityRequirement] = field(default_factory=list)
    project_type: ProjectType = ProjectType.SMALL_BUSINESS
    
    # Параметры окружения
    platform_version: str = "8.3"
    database_type: str = "postgres"
    server_mode: bool = True
    client_type: str = "thick_client"  # thick_client, thin_client, web
    
    # Бизнес-контекст
    business_area: Optional[str] = None  # sales, accounting, hr, manufacturing
    data_sensitivity: str = "normal"  # public, internal, confidential, restricted
    audit_required: bool = False
    
    # Технический контекст
    code_style: str = "standard"  # standard, compact, verbose, functional
    include_tests: bool = False
    include_documentation: bool = True
    performance_critical: bool = False
    
    # Интеграционные требования
    external_integrations: List[str] = field(default_factory=list)
    api_requirements: List[str] = field(default_factory=list)
    
    # Кастомные параметры
    custom_parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedPrompt:
    """Сгенерированный контекстуальный промпт."""
    base_prompt: str
    context_adaptations: List[str]
    quality_enhancements: List[str]
    final_prompt: str
    optimization_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextualPromptBuilder:
    """Контекстуальный генератор промптов."""
    
    def __init__(self, prompt_manager, optimizer=None):
        """
        Инициализация генератора.
        
        Args:
            prompt_manager: Экземпляр PromptManager
            optimizer: Экземпляр PromptOptimizer (опционально)
        """
        self.prompt_manager = prompt_manager
        self.optimizer = optimizer
        self.logger = logging.getLogger(__name__)
        
        # Контекстуальные адаптации для разных сценариев
        self.context_adaptations = {
            'enterprise_security': self._enterprise_security_adaptation,
            'performance_optimization': self._performance_adaptation,
            'compliance_focus': self._compliance_adaptation,
            'integration_aware': self._integration_adaptation,
            'audit_trail': self._audit_trail_adaptation,
            'rapid_development': self._rapid_development_adaptation
        }
        
        # Модификаторы качества
        self.quality_modifiers = {
            'high_coverage': self._add_testing_requirements,
            'performance': self._add_performance_requirements,
            'security': self._add_security_requirements,
            'maintainability': self._add_maintainability_requirements,
            'compliance': self._add_compliance_requirements,
            'optimization': self._add_optimization_requirements
        }
    
    def build_prompt(self, 
                    base_template: str, 
                    context: ContextData,
                    custom_overrides: Dict[str, str] = None) -> GeneratedPrompt:
        """
        Создает контекстуальный промпт.
        
        Args:
            base_template: Базовый шаблон промпта
            context: Контекстные данные
            custom_overrides: Пользовательские переопределения
            
        Returns:
            GeneratedPrompt: Сгенерированный промпт
        """
        # Загружаем базовый промпт
        base_prompt = self.prompt_manager.get_template(base_template)
        if not base_prompt:
            raise ValueError(f"Базовый шаблон '{base_template}' не найден")
        
        # Применяем адаптации контекста
        adapted_prompt = self._apply_context_adaptations(base_prompt, context)
        context_adaptations = self._get_applied_adaptations(context)
        
        # Применяем модификаторы качества
        enhanced_prompt = self._apply_quality_modifiers(adapted_prompt, context)
        quality_enhancements = self._get_quality_modifications(context)
        
        # Применяем пользовательские переопределения
        if custom_overrides:
            enhanced_prompt = self._apply_custom_overrides(enhanced_prompt, custom_overrides)
        
        # Создаем финальный промпт
        final_prompt = self._compose_final_prompt(enhanced_prompt, context)
        
        # Оцениваем качество
        optimization_score = self._calculate_optimization_score(final_prompt, context)
        
        return GeneratedPrompt(
            base_prompt=base_prompt,
            context_adaptations=context_adaptations,
            quality_enhancements=quality_enhancements,
            final_prompt=final_prompt,
            optimization_score=optimization_score,
            metadata={
                'object_type': context.object_type,
                'complexity_level': context.complexity_level.value,
                'quality_requirements': [req.value for req in context.quality_requirements],
                'project_type': context.project_type.value,
                'generated_at': self._get_timestamp()
            }
        )
    
    def _apply_context_adaptations(self, prompt: str, context: ContextData) -> str:
        """Применяет адаптации под контекст."""
        adapted = prompt
        
        # Безопасность enterprise
        if context.project_type in [ProjectType.LARGE_CORPORATION, ProjectType.MEDIUM_ENTERPRISE]:
            adapted = self.context_adaptations['enterprise_security'](adapted)
        
        # Производительность для критичных операций
        if context.performance_critical or QualityRequirement.PERFORMANCE in context.quality_requirements:
            adapted = self.context_adaptations['performance_optimization'](adapted)
        
        # Комплаенс для регулируемых отраслей
        if context.business_area in ['banking', 'insurance', 'healthcare'] or QualityRequirement.COMPLIANCE in context.quality_requirements:
            adapted = self.context_adaptations['compliance_focus'](adapted)
        
        # Интеграции
        if context.external_integrations:
            adapted = self.context_adaptations['integration_aware'](adapted, context.external_integrations)
        
        # Аудит
        if context.audit_required or context.data_sensitivity in ['confidential', 'restricted']:
            adapted = self.context_adaptations['audit_trail'](adapted)
        
        # Быстрая разработка
        if context.project_type == ProjectType.SMALL_BUSINESS and not context.performance_critical:
            adapted = self.context_adaptations['rapid_development'](adapted)
        
        return adapted
    
    def _apply_quality_modifiers(self, prompt: str, context: ContextData) -> str:
        """Применяет модификаторы качества."""
        enhanced = prompt
        
        for requirement in context.quality_requirements:
            if requirement in self.quality_modifiers:
                enhanced = self.quality_modifiers[requirement](enhanced)
        
        return enhanced
    
    def _apply_custom_overrides(self, prompt: str, overrides: Dict[str, str]) -> str:
        """Применяет пользовательские переопределения."""
        result = prompt
        
        for key, value in overrides.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, value)
        
        return result
    
    def _compose_final_prompt(self, prompt: str, context: ContextData) -> str:
        """Составляет финальный промпт с заголовком и метаданными."""
        header = self._generate_prompt_header(context)
        footer = self._generate_prompt_footer(context)
        
        return f"{header}\n\n{prompt}\n\n{footer}"
    
    def _generate_prompt_header(self, context: ContextData) -> str:
        """Генерирует заголовок промпта."""
        header_parts = [
            "CONTEXT-AWARE PROMPT GENERATION",
            f"Object Type: {context.object_type.upper()}",
            f"Complexity: {context.complexity_level.value.upper()}",
            f"Project Type: {context.project_type.value.replace('_', ' ').title()}",
            f"Platform: 1С {context.platform_version}",
            f"Environment: {context.client_type.replace('_', ' ').title()}"
        ]
        
        if context.business_area:
            header_parts.append(f"Business Area: {context.business_area.title()}")
        
        if context.quality_requirements:
            header_parts.append(f"Quality Focus: {', '.join(req.value.replace('_', ' ').title() for req in context.quality_requirements)}")
        
        if context.performance_critical:
            header_parts.append("PERFORMANCE CRITICAL - Optimize for speed")
        
        return "\n".join(header_parts)
    
    def _generate_prompt_footer(self, context: ContextData) -> str:
        """Генерирует подвал промпта."""
        footer_parts = []
        
        footer_parts.append("GENERATION CONSTRAINTS:")
        
        # Контекстуальные ограничения
        if context.data_sensitivity == 'restricted':
            footer_parts.append("- MAXIMUM SECURITY REQUIRED - All data must be encrypted")
        elif context.data_sensitivity == 'confidential':
            footer_parts.append("- HIGH SECURITY - Implement access controls and logging")
        
        # Требования к производительности
        if context.performance_critical:
            footer_parts.append("- PERFORMANCE OPTIMIZATION MANDATORY")
            footer_parts.append("- Use efficient queries and caching")
            footer_parts.append("- Avoid unnecessary database round-trips")
        
        # Аудит
        if context.audit_required:
            footer_parts.append("- AUDIT TRAIL REQUIRED - Log all operations")
            footer_parts.append("- Implement comprehensive logging")
        
        # Интеграции
        if context.external_integrations:
            footer_parts.append(f"- INTEGRATION POINTS: {', '.join(context.external_integrations)}")
        
        # Тестирование
        if context.include_tests:
            footer_parts.append("- INCLUDE COMPREHENSIVE TESTS")
            footer_parts.append("- Add unit tests and integration tests")
        
        # Документация
        if context.include_documentation:
            footer_parts.append("- INCLUDE DETAILED DOCUMENTATION")
            footer_parts.append("- Add inline comments and XML documentation")
        
        return "\n".join(footer_parts)
    
    # Методы адаптации контекста
    
    def _enterprise_security_adaptation(self, prompt: str) -> str:
        """Адаптация для enterprise безопасности."""
        security_additions = """
ENTERPRISE SECURITY REQUIREMENTS:
- Implement Role-Based Access Control (RBAC)
- Add comprehensive input validation and sanitization
- Use parameterized queries to prevent SQL injection
- Implement session management and timeout handling
- Add data encryption for sensitive information
- Include security logging and monitoring
- Follow OWASP Top 10 guidelines
- Implement proper error handling without information disclosure

COMPLIANCE REQUIREMENTS:
- GDPR compliance for personal data handling
- SOX compliance for financial data
- Industry-specific regulations as applicable
"""
        return prompt + security_additions
    
    def _performance_adaptation(self, prompt: str) -> str:
        """Адаптация для производительности."""
        performance_additions = """
PERFORMANCE OPTIMIZATION REQUIREMENTS:
- Use efficient data structures and algorithms
- Implement query optimization and indexing strategies
- Add caching for frequently accessed data
- Minimize database round-trips using bulk operations
- Use asynchronous processing for long-running operations
- Implement pagination for large datasets
- Add performance monitoring and metrics collection
- Profile and optimize critical code paths

OPTIMIZATION TECHNIQUES:
- Use batch processing where possible
- Implement lazy loading for related objects
- Add connection pooling for database access
- Use appropriate data types and constraints
"""
        return prompt + performance_additions
    
    def _compliance_adaptation(self, prompt: str) -> str:
        """Адаптация для комплаенса."""
        compliance_additions = """
REGULATORY COMPLIANCE REQUIREMENTS:
- Implement data lineage tracking
- Add audit logging for all data modifications
- Ensure data retention policy compliance
- Implement data anonymization/pseudonymization where required
- Add compliance reporting capabilities
- Ensure proper data classification and handling
- Implement change management procedures
- Add automated compliance checking

INDUSTRY-SPECIFIC REQUIREMENTS:
- Healthcare: HIPAA compliance, patient data protection
- Finance: PCI DSS compliance, anti-money laundering
- Banking: Basel III compliance, stress testing
- Insurance: Solvency II compliance, actuarial calculations
"""
        return prompt + compliance_additions
    
    def _integration_adaptation(self, prompt: str, integrations: List[str]) -> str:
        """Адаптация для интеграций."""
        integration_additions = f"""
INTEGRATION REQUIREMENTS:
- API Design: RESTful, versioned, well-documented APIs
- Message Queues: Implement reliable message delivery
- Event-Driven Architecture: Support async event processing
- Data Synchronization: Handle eventual consistency
- Error Handling: Robust error handling and retry logic
- Security: OAuth 2.0, JWT tokens, API rate limiting
- Monitoring: Comprehensive integration monitoring
- Testing: Mock services and integration test suites

INTEGRATION POINTS:
{chr(10).join(f"- {integration}: Implement proper interface and error handling" for integration in integrations)}
"""
        return prompt + integration_additions
    
    def _audit_trail_adaptation(self, prompt: str) -> str:
        """Адаптация для аудита."""
        audit_additions = """
AUDIT TRAIL REQUIREMENTS:
- Log all user actions with timestamp and user context
- Track all data modifications with before/after values
- Implement immutable audit logs
- Add data change reason tracking
- Include IP address and session information
- Ensure audit log integrity and tamper-evidence
- Implement audit log retention policies
- Add audit log search and reporting capabilities

MONITORING AND ALERTING:
- Real-time monitoring of critical operations
- Automated alerts for suspicious activities
- Performance monitoring and SLA tracking
- Error rate monitoring and alerting
- Security incident detection and response
"""
        return prompt + audit_additions
    
    def _rapid_development_adaptation(self, prompt: str) -> str:
        """Адаптация для быстрой разработки."""
        rapid_additions = """
RAPID DEVELOPMENT GUIDELINES:
- Focus on core functionality first
- Use standard 1С patterns and components
- Minimize custom development
- Implement MVP (Minimum Viable Product) approach
- Use templates and code generation where possible
- Prioritize simplicity over complexity
- Implement basic error handling
- Use proven design patterns

SIMPLIFICATION RULES:
- Avoid over-engineering
- Use default 1С components when possible
- Implement basic validation only
- Use standard UI components
- Minimize integration complexity
"""
        return prompt + rapid_additions
    
    # Методы модификации качества
    
    def _add_testing_requirements(self, prompt: str) -> str:
        """Добавляет требования к тестированию."""
        testing_additions = """
TESTING REQUIREMENTS:
- Unit tests with 90%+ code coverage
- Integration tests for all external interfaces
- Performance tests for critical functions
- Security tests for authentication and authorization
- UI tests for user interface interactions
- Regression tests for bug fixes
- Load tests for high-traffic scenarios

TESTING STANDARDS:
- Use Given-When-Then pattern for test descriptions
- Mock external dependencies in unit tests
- Use test data factories for consistent test data
- Implement test parallelization for faster execution
- Add test reporting and coverage analysis
"""
        return prompt + testing_additions
    
    def _add_performance_requirements(self, prompt: str) -> str:
        """Добавляет требования к производительности."""
        performance_additions = """
PERFORMANCE REQUIREMENTS:
- Page load times < 2 seconds for standard operations
- Database query execution < 500ms for 95th percentile
- Memory usage optimization and garbage collection tuning
- CPU utilization monitoring and optimization
- Network latency minimization
- Caching strategy implementation
- Database connection pooling
- Asynchronous processing for long operations

PERFORMANCE METRICS:
- Response time SLAs: 99th percentile < 5 seconds
- Throughput requirements: X requests per second
- Concurrent user support: Y simultaneous users
- Data processing capacity: Z records per minute
"""
        return prompt + performance_additions
    
    def _add_security_requirements(self, prompt: str) -> str:
        """Добавляет требования безопасности."""
        security_additions = """
SECURITY REQUIREMENTS:
- Input validation and sanitization for all user inputs
- SQL injection prevention through parameterized queries
- Cross-site scripting (XSS) prevention
- Cross-site request forgery (CSRF) protection
- Secure session management and timeout handling
- Password hashing using strong algorithms (bcrypt, scrypt)
- Secure API key and token management
- Regular security audits and penetration testing

SECURITY MONITORING:
- Failed authentication attempt monitoring
- Suspicious activity detection and alerting
- Security event logging and analysis
- Vulnerability scanning integration
- Incident response procedures
"""
        return prompt + security_additions
    
    def _add_maintainability_requirements(self, prompt: str) -> str:
        """Добавляет требования к поддерживаемости."""
        maintainability_additions = """
MAINTAINABILITY REQUIREMENTS:
- Clean code principles: meaningful names, small functions, DRY
- Comprehensive documentation and inline comments
- Code review process and peer review requirements
- Automated code formatting and style checking
- Dependency management and vulnerability scanning
- Version control best practices and branching strategies
- Refactoring guidelines and technical debt tracking
- Knowledge sharing and documentation maintenance

CODE QUALITY METRICS:
- Code complexity: Cyclomatic complexity < 10
- Code duplication: < 5% duplicate code
- Technical debt ratio: < 10%
- Maintainability index: > 80
"""
        return prompt + maintainability_additions
    
    def _add_compliance_requirements(self, prompt: str) -> str:
        """Добавляет требования комплаенса."""
        compliance_additions = """
COMPLIANCE REQUIREMENTS:
- Data governance and data quality management
- Privacy by design principles implementation
- Regulatory reporting and audit capabilities
- Data retention and archival procedures
- Change management and version control
- Risk assessment and mitigation strategies
- Business continuity and disaster recovery planning
- Third-party vendor risk management

COMPLIANCE MONITORING:
- Automated compliance checking tools
- Regular compliance assessments and audits
- Compliance dashboard and reporting
- Regulatory change management process
- Compliance training and awareness programs
"""
        return prompt + compliance_additions
    
    def _add_optimization_requirements(self, prompt: str) -> str:
        """Добавляет требования оптимизации."""
        optimization_additions = """
OPTIMIZATION REQUIREMENTS:
- Database query optimization and indexing
- Algorithm efficiency and complexity analysis
- Memory usage optimization and leak prevention
- CPU utilization optimization and parallel processing
- Network optimization and compression
- Caching strategies and cache invalidation
- Resource pooling and connection management
- Performance profiling and bottleneck identification

OPTIMIZATION TECHNIQUES:
- Lazy loading and eager loading strategies
- Bulk operations vs. batch processing
- Data structure optimization
- Algorithm complexity analysis
- Hardware utilization optimization
"""
        return prompt + optimization_additions
    
    def _get_applied_adaptations(self, context: ContextData) -> List[str]:
        """Возвращает список примененных адаптаций."""
        adaptations = []
        
        if context.project_type in [ProjectType.LARGE_CORPORATION, ProjectType.MEDIUM_ENTERPRISE]:
            adaptations.append("Enterprise Security")
        
        if context.performance_critical or QualityRequirement.PERFORMANCE in context.quality_requirements:
            adaptations.append("Performance Optimization")
        
        if context.business_area in ['banking', 'insurance', 'healthcare'] or QualityRequirement.COMPLIANCE in context.quality_requirements:
            adaptations.append("Compliance Focus")
        
        if context.external_integrations:
            adaptations.append("Integration Aware")
        
        if context.audit_required or context.data_sensitivity in ['confidential', 'restricted']:
            adaptations.append("Audit Trail")
        
        if context.project_type == ProjectType.SMALL_BUSINESS and not context.performance_critical:
            adaptations.append("Rapid Development")
        
        return adaptations
    
    def _get_quality_modifications(self, context: ContextData) -> List[str]:
        """Возвращает список примененных модификаций качества."""
        modifications = []
        
        for requirement in context.quality_requirements:
            modification_map = {
                QualityRequirement.HIGH_COVERAGE: "High Test Coverage",
                QualityRequirement.PERFORMANCE: "Performance Optimization",
                QualityRequirement.SECURITY: "Security Enhancement",
                QualityRequirement.MAINTAINABILITY: "Maintainability Focus",
                QualityRequirement.COMPLIANCE: "Compliance Requirements",
                QualityRequirement.OPTIMIZATION: "Code Optimization"
            }
            if requirement in modification_map:
                modifications.append(modification_map[requirement])
        
        return modifications
    
    def _calculate_optimization_score(self, prompt: str, context: ContextData) -> float:
        """Вычисляет скор оптимизации промпта."""
        base_score = 0.5
        
        # Бонусы за контекстуальные адаптации
        if context.project_type == ProjectType.LARGE_CORPORATION:
            base_score += 0.1
        if context.performance_critical:
            base_score += 0.15
        if context.audit_required:
            base_score += 0.1
        if len(context.quality_requirements) > 3:
            base_score += 0.1
        
        # Бонусы за качество
        if QualityRequirement.SECURITY in context.quality_requirements:
            base_score += 0.05
        if QualityRequirement.PERFORMANCE in context.quality_requirements:
            base_score += 0.05
        if QualityRequirement.HIGH_COVERAGE in context.quality_requirements:
            base_score += 0.05
        
        return min(base_score, 1.0)
    
    def _get_timestamp(self) -> str:
        """Возвращает текущую метку времени."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'
    
    def get_preset_contexts(self) -> Dict[str, ContextData]:
        """Возвращает предустановленные контексты."""
        return {
            'simple_processing': ContextData(
                object_type='processing',
                complexity_level=ComplexityLevel.SIMPLE,
                quality_requirements=[QualityRequirement.MAINTAINABILITY]
            ),
            'enterprise_report': ContextData(
                object_type='report',
                complexity_level=ComplexityLevel.ENTERPRISE,
                quality_requirements=[QualityRequirement.SECURITY, QualityRequirement.COMPLIANCE],
                project_type=ProjectType.LARGE_CORPORATION,
                audit_required=True,
                data_sensitivity='confidential'
            ),
            'performance_critical_catalog': ContextData(
                object_type='catalog',
                complexity_level=ComplexityLevel.ADVANCED,
                quality_requirements=[QualityRequirement.PERFORMANCE, QualityRequirement.OPTIMIZATION],
                performance_critical=True,
                project_type=ProjectType.MEDIUM_ENTERPRISE
            ),
            'compliant_document': ContextData(
                object_type='document',
                complexity_level=ComplexityLevel.ENTERPRISE,
                quality_requirements=[QualityRequirement.COMPLIANCE, QualityRequirement.SECURITY, QualityRequirement.HIGH_COVERAGE],
                project_type=ProjectType.LARGE_CORPORATION,
                business_area='banking',
                audit_required=True,
                data_sensitivity='restricted'
            )
        }