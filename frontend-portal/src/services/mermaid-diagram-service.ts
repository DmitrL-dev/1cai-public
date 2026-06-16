export interface MermaidDiagram {
  id: string;
  title: string;
  type: 'flowchart' | 'sequence' | 'class' | 'state' | 'er' | 'gantt' | 'pie';
  content: string;
  metadata: {
    createdAt: Date;
    updatedAt: Date;
    version: string;
  };
}

export interface DiagramTheme {
  name: string;
  background: string;
  primaryColor: string;
  secondaryColor: string;
  textColor: string;
  lineColor: string;
  fontFamily: string;
}

export interface DiagramTemplate {
  id: string;
  name: string;
  description: string;
  category: 'flowchart' | 'sequence' | 'class' | 'state' | 'er' | 'gantt' | 'pie';
  content: string;
  variables: Record<string, string>;
}

export class MermaidDiagramService {
  private diagrams: Map<string, MermaidDiagram> = new Map();
  private themes: DiagramTheme[] = [];
  private templates: DiagramTemplate[] = [];
  private currentTheme: DiagramTheme = this.getDefaultTheme();

  constructor() {
    this.initializeDefaultThemes();
    this.initializeDefaultTemplates();
  }

  private initializeDefaultThemes(): void {
    this.themes = [
      {
        name: 'default',
        background: '#ffffff',
        primaryColor: '#1976d2',
        secondaryColor: '#dc004e',
        textColor: '#333333',
        lineColor: '#666666',
        fontFamily: 'Arial, sans-serif'
      },
      {
        name: 'dark',
        background: '#2d3748',
        primaryColor: '#4299e1',
        secondaryColor: '#f56565',
        textColor: '#f7fafc',
        lineColor: '#4a5568',
        fontFamily: 'Arial, sans-serif'
      },
      {
        name: 'forest',
        background: '#f0fff4',
        primaryColor: '#38a169',
        secondaryColor: '#d69e2e',
        textColor: '#1a202c',
        lineColor: '#68d391',
        fontFamily: 'Georgia, serif'
      },
      {
        name: 'neutral',
        background: '#fafafa',
        primaryColor: '#4a5568',
        secondaryColor: '#e53e3e',
        textColor: '#2d3748',
        lineColor: '#a0aec0',
        fontFamily: 'Helvetica, sans-serif'
      }
    ];
  }

  private getDefaultTheme(): DiagramTheme {
    return this.themes.find(t => t.name === 'default')!;
  }

  private initializeDefaultTemplates(): void {
    this.templates = [
      {
        id: 'simple-flowchart',
        name: 'Простая блок-схема',
        description: 'Базовая схема с несколькими узлами',
        category: 'flowchart',
        content: `flowchart TD
    A[Начало] --> B{Проверка}
    B -->|Да| C[Действие 1]
    B -->|Нет| D[Действие 2]
    C --> E[Конец]
    D --> E`,
        variables: {
          startText: 'Начало',
          conditionText: 'Проверка',
          yesText: 'Да',
          noText: 'Нет',
          action1Text: 'Действие 1',
          action2Text: 'Действие 2',
          endText: 'Конец'
        }
      },
      {
        id: 'user-auth-sequence',
        name: 'Последовательность аутентификации',
        description: 'Схема процесса входа пользователя',
        category: 'sequence',
        content: `sequenceDiagram
    participant User
    participant App
    participant Auth
    participant Database
    
    User->>App: Вход в систему
    App->>Auth: Проверка данных
    Auth->>Database: Поиск пользователя
    Database-->>Auth: Данные пользователя
    Auth-->>App: Подтверждение
    App-->>User: Доступ разрешен`,
        variables: {}
      },
      {
        id: '1c-system-architecture',
        name: 'Архитектура 1C системы',
        description: 'Схема компонентов 1C системы',
        category: 'class',
        content: `classDiagram
    class UserInterface {
      +String name
      +String role
      +login()
      +logout()
    }
    
    class BusinessLogic {
      +String data
      +processRequest()
      +validateData()
    }
    
    class Database {
      +Connection connection
      +query()
      +save()
    }
    
    UserInterface --> BusinessLogic
    BusinessLogic --> Database`,
        variables: {
          systemName: '1C:Enterprise'
        }
      }
    ];
  }

  async createDiagram(
    title: string,
    type: MermaidDiagram['type'],
    content: string
  ): Promise<MermaidDiagram> {
    const diagram: MermaidDiagram = {
      id: this.generateDiagramId(),
      title,
      type,
      content,
      metadata: {
        createdAt: new Date(),
        updatedAt: new Date(),
        version: '1.0'
      }
    };

    this.diagrams.set(diagram.id, diagram);
    return diagram;
  }

  async updateDiagram(
    id: string,
    updates: Partial<Pick<MermaidDiagram, 'title' | 'content'>>
  ): Promise<MermaidDiagram> {
    const diagram = this.diagrams.get(id);
    if (!diagram) {
      throw new Error(`Diagram with id ${id} not found`);
    }

    const updatedDiagram = {
      ...diagram,
      ...updates,
      metadata: {
        ...diagram.metadata,
        updatedAt: new Date(),
        version: this.incrementVersion(diagram.metadata.version)
      }
    };

    this.diagrams.set(id, updatedDiagram);
    return updatedDiagram;
  }

  private incrementVersion(version: string): string {
    const parts = version.split('.');
    const minor = parseInt(parts[1] || '0') + 1;
    return `${parts[0]}.${minor}`;
  }

  async deleteDiagram(id: string): Promise<boolean> {
    return this.diagrams.delete(id);
  }

  getDiagram(id: string): MermaidDiagram | null {
    return this.diagrams.get(id) || null;
  }

  getAllDiagrams(): MermaidDiagram[] {
    return Array.from(this.diagrams.values());
  }

  getDiagramsByType(type: MermaidDiagram['type']): MermaidDiagram[] {
    return this.getAllDiagrams().filter(diagram => diagram.type === type);
  }

  async duplicateDiagram(id: string, newTitle?: string): Promise<MermaidDiagram> {
    const original = this.getDiagram(id);
    if (!original) {
      throw new Error(`Diagram with id ${id} not found`);
    }

    const duplicate: MermaidDiagram = {
      ...original,
      id: this.generateDiagramId(),
      title: newTitle || `${original.title} (копия)`,
      metadata: {
        createdAt: new Date(),
        updatedAt: new Date(),
        version: '1.0'
      }
    };

    this.diagrams.set(duplicate.id, duplicate);
    return duplicate;
  }

  async exportDiagram(id: string, format: 'svg' | 'png' | 'pdf' = 'svg'): Promise<string> {
    const diagram = this.getDiagram(id);
    if (!diagram) {
      throw new Error(`Diagram with id ${id} not found`);
    }

    // In a real implementation, this would use mermaid.render or similar
    // For now, return a mock result
    switch (format) {
      case 'svg':
        return `<svg>/* SVG representation of ${diagram.title} */</svg>`;
      case 'png':
        return 'data:image/png;base64,...'; // Mock base64 PNG
      case 'pdf':
        return '%PDF-1.4\n% Mock PDF content\n'; // Mock PDF content
      default:
        throw new Error(`Unsupported export format: ${format}`);
    }
  }

  async validateDiagramContent(content: string): Promise<{ isValid: boolean; errors: string[] }> {
    const errors: string[] = [];
    
    try {
      // Basic syntax validation
      if (!content.trim()) {
        errors.push('Content cannot be empty');
      }

      // Check for common Mermaid syntax errors
      if (content.includes('[') && !content.includes(']')) {
        errors.push('Unclosed bracket found');
      }

      if (content.includes('(') && !content.includes(')')) {
        errors.push('Unclosed parenthesis found');
      }

      return {
        isValid: errors.length === 0,
        errors
      };
    } catch (error) {
      return {
        isValid: false,
        errors: [error instanceof Error ? error.message : 'Unknown validation error']
      };
    }
  }

  async generateFromTemplate(templateId: string, variables: Record<string, string>): Promise<string> {
    const template = this.templates.find(t => t.id === templateId);
    if (!template) {
      throw new Error(`Template with id ${templateId} not found`);
    }

    let content = template.content;
    
    // Replace variables in template
    Object.entries(variables).forEach(([key, value]) => {
      const placeholder = `{{${key}}}`;
      content = content.replace(new RegExp(placeholder, 'g'), value);
    });

    return content;
  }

  setTheme(themeName: string): void {
    const theme = this.themes.find(t => t.name === themeName);
    if (!theme) {
      throw new Error(`Theme with name ${themeName} not found`);
    }
    this.currentTheme = theme;
  }

  getCurrentTheme(): DiagramTheme {
    return this.currentTheme;
  }

  getAvailableThemes(): DiagramTheme[] {
    return [...this.themes];
  }

  getTemplates(): DiagramTemplate[] {
    return [...this.templates];
  }

  getTemplatesByCategory(category: DiagramTemplate['category']): DiagramTemplate[] {
    return this.templates.filter(template => template.category === category);
  }

  async createTemplate(
    name: string,
    description: string,
    category: DiagramTemplate['category'],
    content: string,
    variables: Record<string, string> = {}
  ): Promise<string> {
    const template: DiagramTemplate = {
      id: this.generateTemplateId(),
      name,
      description,
      category,
      content,
      variables
    };

    this.templates.push(template);
    return template.id;
  }

  private generateDiagramId(): string {
    return `diagram_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateTemplateId(): string {
    return `template_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  getStatistics() {
    const diagrams = this.getAllDiagrams();
    return {
      total: diagrams.length,
      byType: diagrams.reduce((acc, diagram) => {
        acc[diagram.type] = (acc[diagram.type] || 0) + 1;
        return acc;
      }, {} as Record<string, number>),
      lastCreated: diagrams.length > 0 ? 
        diagrams.sort((a, b) => b.metadata.createdAt.getTime() - a.metadata.createdAt.getTime())[0].metadata.createdAt 
        : null
    };
  }
}

// Additional types for architecture diagrams
export interface SystemComponent {
  id: string;
  name: string;
  type: string;
  description?: string;
  dependencies?: string[];
  properties?: Record<string, any>;
}

export interface IntegrationPoint {
  id: string;
  sourceComponent: string;
  targetComponent: string;
  type: 'sync' | 'async' | 'event';
  protocol?: string;
  description?: string;
}

export interface ArchitectureDiagram extends Omit<MermaidDiagram, 'content' | 'metadata'> {
  components?: SystemComponent[];
  integrations?: IntegrationPoint[];
  architectureType?: 'layered' | 'microservices' | 'monolith' | 'event-driven';
  mermaidCode?: string;
  complexity?: 'simple' | 'moderate' | 'complex' | 'very-complex';
  tags?: string[];
  description?: string;
  content?: string;
  metadata?: {
    createdAt: Date;
    updatedAt: Date;
    version: string;
  };
}