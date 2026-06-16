/**
 * Сервис генерации BPMN диаграмм для бизнес-процессов 1C
 * Поддерживает создание диаграмм процессов 1C с типичными элементами
 */

// Генерация UUID с помощью Web Crypto API
const generateUUID = (): string => {
  return crypto.randomUUID();
};

export interface BPMNElement {
  id: string;
  type: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  properties?: Record<string, any>;
}

export interface BPMNSequenceFlow {
  id: string;
  from: string;
  to: string;
  condition?: string;
  name?: string;
}

export interface BPMNPool {
  id: string;
  name: string;
  elements: BPMNElement[];
  sequenceFlows: BPMNSequenceFlow[];
  y: number;
  height: number;
}

export interface BPMNDiagram {
  id: string;
  name: string;
  description?: string;
  pools: BPMNPool[];
  metadata: {
    version: string;
    createdAt: Date;
    modifiedAt: Date;
    author: string;
  };
}

// Константы для BPMN элементов
export const BPMN_ELEMENT_TYPES = {
  START_EVENT: 'startEvent',
  END_EVENT: 'endEvent',
  INTERMEDIATE_THROW_EVENT: 'intermediateThrowEvent',
  INTERMEDIATE_CATCH_EVENT: 'intermediateCatchEvent',
  
  TASK: 'task',
  USER_TASK: 'userTask',
  SERVICE_TASK: 'serviceTask',
  SCRIPT_TASK: 'scriptTask',
  CALL_ACTIVITY: 'callActivity',
  
  PARALLEL_GATEWAY: 'parallelGateway',
  EXCLUSIVE_GATEWAY: 'exclusiveGateway',
  INCLUSIVE_GATEWAY: 'inclusiveGateway',
  
  LANE: 'lane',
  SUB_PROCESS: 'subProcess',
  MESSAGE: 'message'
} as const;

// 1C специфичные типы задач
export const C1C_TASK_TYPES = {
  DOCUMENT_PROCESSING: 'c1cDocumentProcessing',
  REFERENCE_UPDATE: 'c1cReferenceUpdate',
  USER_FORM: 'c1cUserForm',
  USER_TASK: 'c1cUserTask',
  SERVICE_TASK: 'c1cServiceTask',
  CALCULATION: 'c1cCalculation',
  REPORT_GENERATION: 'c1cReportGeneration',
  INTEGRATION: 'c1cIntegration',
  VALIDATION: 'c1cValidation',
  NOTIFICATION: 'c1cNotification'
} as const;

export class BPMNDiagramService {
  private currentDiagram: BPMNDiagram | null = null;

  /**
   * Создать новую BPMN диаграмму
   */
  createDiagram(name: string, description?: string): BPMNDiagram {
    this.currentDiagram = {
      id: generateUUID(),
      name,
      description,
      pools: [],
      metadata: {
        version: '1.0.0',
        createdAt: new Date(),
        modifiedAt: new Date(),
        author: '1C AI Assistant'
      }
    };
    return this.currentDiagram;
  }

  /**
   * Загрузить существующую диаграмму
   */
  loadDiagram(diagram: BPMNDiagram): void {
    this.currentDiagram = diagram;
  }

  /**
   * Сохранить диаграмму
   */
  saveDiagram(): BPMNDiagram | null {
    if (this.currentDiagram) {
      this.currentDiagram.metadata.modifiedAt = new Date();
      return this.currentDiagram;
    }
    return null;
  }

  /**
   * Добавить пул (дорожку) в диаграмму
   */
  addPool(poolName: string): string {
    if (!this.currentDiagram) {
      throw new Error('Диаграмма не создана. Используйте createDiagram()');
    }

    const poolId = `pool_${generateUUID()}`;
    const pool: BPMNPool = {
      id: poolId,
      name: poolName,
      elements: [],
      sequenceFlows: [],
      y: this.currentDiagram.pools.length * 200,
      height: 200
    };

    this.currentDiagram.pools.push(pool);
    return poolId;
  }

  /**
   * Добавить элемент в пул
   */
  addElement(
    poolId: string,
    type: string,
    name: string,
    x: number,
    y: number,
    width: number = 120,
    height: number = 80,
    properties?: Record<string, any>
  ): string {
    if (!this.currentDiagram) {
      throw new Error('Диаграмма не создана');
    }

    const elementId = `element_${generateUUID()}`;
    const element: BPMNElement = {
      id: elementId,
      type,
      name,
      x,
      y,
      width,
      height,
      properties
    };

    const pool = this.currentDiagram.pools.find(p => p.id === poolId);
    if (!pool) {
      throw new Error(`Пул ${poolId} не найден`);
    }

    pool.elements.push(element);
    return elementId;
  }

  /**
   * Добавить последовательный поток между элементами
   */
  addSequenceFlow(
    poolId: string,
    fromElementId: string,
    toElementId: string,
    condition?: string,
    name?: string
  ): string {
    if (!this.currentDiagram) {
      throw new Error('Диаграмма не создана');
    }

    const flowId = `flow_${generateUUID()}`;
    const sequenceFlow: BPMNSequenceFlow = {
      id: flowId,
      from: fromElementId,
      to: toElementId,
      condition,
      name
    };

    const pool = this.currentDiagram.pools.find(p => p.id === poolId);
    if (!pool) {
      throw new Error(`Пул ${poolId} не найден`);
    }

    pool.sequenceFlows.push(sequenceFlow);
    return flowId;
  }

  /**
   * Создать стандартные шаблоны BPMN процессов для 1C
   */
  
  /**
   * Шаблон процесса обработки документа
   */
  createDocumentProcessingTemplate(poolName: string = 'Обработка документа'): string {
    if (!this.currentDiagram) {
      this.createDiagram('Процесс обработки документа');
    }

    const poolId = this.addPool(poolName);
    
    // События
    const startEventId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.START_EVENT,
      'Начало',
      100,
      100
    );

    const validationTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.VALIDATION,
      'Проверка данных',
      250,
      100,
      140,
      80,
      {
        validationRules: ['Проверка заполненности', 'Валидация форматов'],
        errorHandling: true
      }
    );

    const decisionGatewayId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.EXCLUSIVE_GATEWAY,
      'Данные корректны?',
      430,
      100
    );

    const userTaskId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.USER_TASK,
      'Редактирование документа',
      600,
      50,
      150,
      80,
      {
        formName: 'ФормаРедактирования',
        userRole: 'Пользователь'
      }
    );

    const processingTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.DOCUMENT_PROCESSING,
      'Обработка документа',
      600,
      150,
      150,
      80,
      {
        operation: 'Запись',
        registerChanges: true
      }
    );

    const reportTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.REPORT_GENERATION,
      'Генерация отчета',
      800,
      150,
      140,
      80,
      {
        reportTemplate: 'ДвиженияДокумента',
        outputFormat: 'PDF'
      }
    );

    const endEventId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.END_EVENT,
      'Завершение',
      980,
      150
    );

    // Потоки
    this.addSequenceFlow(poolId, startEventId, validationTaskId, undefined, 'Старт процесса');
    this.addSequenceFlow(poolId, validationTaskId, decisionGatewayId, undefined, 'Проверка выполнена');
    this.addSequenceFlow(poolId, decisionGatewayId, userTaskId, 'Данные не корректны', 'Возврат на редактирование');
    this.addSequenceFlow(poolId, decisionGatewayId, processingTaskId, 'Данные корректны', 'Продолжение обработки');
    this.addSequenceFlow(poolId, userTaskId, validationTaskId, undefined, 'Возврат после редактирования');
    this.addSequenceFlow(poolId, processingTaskId, reportTaskId, undefined, 'Документ обработан');
    this.addSequenceFlow(poolId, reportTaskId, endEventId, undefined, 'Отчет сформирован');

    return poolId;
  }

  /**
   * Шаблон процесса обновления справочника
   */
  createReferenceUpdateTemplate(poolName: string = 'Обновление справочника'): string {
    if (!this.currentDiagram) {
      this.createDiagram('Процесс обновления справочника');
    }

    const poolId = this.addPool(poolName);

    // События
    const startEventId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.START_EVENT,
      'Запрос на обновление',
      100,
      100
    );

    const loadTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.SERVICE_TASK,
      'Загрузка данных',
      250,
      100,
      120,
      80,
      {
        source: 'Внешняя система',
        dataFormat: 'XML'
      }
    );

    const transformTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.CALCULATION,
      'Преобразование данных',
      400,
      100,
      140,
      80,
      {
        mapping: 'справочник_маппинг',
        validation: true
      }
    );

    const parallelGatewayId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.PARALLEL_GATEWAY,
      'Разделение',
      580,
      100
    );

    const insertTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.REFERENCE_UPDATE,
      'Добавление новых',
      750,
      50,
      130,
      80,
      {
        operation: 'insert',
        conflictResolution: 'skip'
      }
    );

    const updateTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.REFERENCE_UPDATE,
      'Обновление существующих',
      750,
      150,
      130,
      80,
      {
        operation: 'update',
        conflictResolution: 'overwrite'
      }
    );

    const syncGatewayId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.PARALLEL_GATEWAY,
      'Синхронизация',
      920,
      100
    );

    const endEventId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.END_EVENT,
      'Синхронизация завершена',
      1100,
      100
    );

    // Потоки
    this.addSequenceFlow(poolId, startEventId, loadTaskId, undefined, 'Получен запрос');
    this.addSequenceFlow(poolId, loadTaskId, transformTaskId, undefined, 'Данные загружены');
    this.addSequenceFlow(poolId, transformTaskId, parallelGatewayId, undefined, 'Данные готовы');
    this.addSequenceFlow(poolId, parallelGatewayId, insertTaskId, undefined, 'Параллельная обработка');
    this.addSequenceFlow(poolId, parallelGatewayId, updateTaskId, undefined, 'Параллельная обработка');
    this.addSequenceFlow(poolId, insertTaskId, syncGatewayId, undefined, 'Добавление завершено');
    this.addSequenceFlow(poolId, updateTaskId, syncGatewayId, undefined, 'Обновление завершено');
    this.addSequenceFlow(poolId, syncGatewayId, endEventId, undefined, 'Процесс завершен');

    return poolId;
  }

  /**
   * Шаблон интеграционного процесса
   */
  createIntegrationProcessTemplate(poolName: string = 'Интеграция с внешней системой'): string {
    if (!this.currentDiagram) {
      this.createDiagram('Интеграционный процесс');
    }

    const poolId = this.addPool(poolName);

    // События
    const startEventId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.INTERMEDIATE_CATCH_EVENT,
      'Получение сообщения',
      100,
      100
    );

    const validationTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.VALIDATION,
      'Валидация сообщения',
      250,
      100,
      140,
      80,
      {
        schema: 'Сообщение.xsd',
        strictValidation: true
      }
    );

    const transformationTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.CALCULATION,
      'Трансформация данных',
      430,
      100,
      140,
      80,
        {
        xsltTemplate: 'преобразование.xslt',
        outputFormat: '1C_JSON'
      }
    );

    const decisionGatewayId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.EXCLUSIVE_GATEWAY,
      'Тип операции',
      610,
      100
    );

    const createTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.DOCUMENT_PROCESSING,
      'Создание документа',
      800,
      50,
      140,
      80,
      {
        documentType: 'ПоступлениеТоваров',
        autoNumbering: true
      }
    );

    const updateTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.DOCUMENT_PROCESSING,
      'Обновление данных',
      800,
      150,
      140,
      80,
      {
        operation: 'update',
        auditTrail: true
      }
    );

    const notificationTaskId = this.addElement(
      poolId,
      C1C_TASK_TYPES.NOTIFICATION,
      'Уведомление об успехе',
      980,
      100,
      150,
      80,
      {
        recipients: ['администратор@company.ru'],
        subject: 'Интеграция успешна',
        template: 'integration_success.html'
      }
    );

    const endEventId = this.addElement(
      poolId,
      BPMN_ELEMENT_TYPES.INTERMEDIATE_THROW_EVENT,
      'Отправка ответа',
      1170,
      100
    );

    // Потоки
    this.addSequenceFlow(poolId, startEventId, validationTaskId, undefined, 'Сообщение получено');
    this.addSequenceFlow(poolId, validationTaskId, transformationTaskId, undefined, 'Валидация пройдена');
    this.addSequenceFlow(poolId, transformationTaskId, decisionGatewayId, undefined, 'Данные трансформированы');
    this.addSequenceFlow(poolId, decisionGatewayId, createTaskId, 'type = "create"', 'Создание');
    this.addSequenceFlow(poolId, decisionGatewayId, updateTaskId, 'type = "update"', 'Обновление');
    this.addSequenceFlow(poolId, createTaskId, notificationTaskId, undefined, 'Документ создан');
    this.addSequenceFlow(poolId, updateTaskId, notificationTaskId, undefined, 'Данные обновлены');
    this.addSequenceFlow(poolId, notificationTaskId, endEventId, undefined, 'Уведомление отправлено');

    return poolId;
  }

  /**
   * Экспорт диаграммы в различные форматы
   */

  /**
   * Экспорт в BPMN 2.0 XML
   */
  exportToBPMN(): string {
    if (!this.currentDiagram) {
      throw new Error('Диаграмма не создана');
    }

    const diagram = this.currentDiagram;
    let xml = `<?xml version="1.0" encoding="UTF-8"?>\n`;
    xml += `<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" \n`;
    xml += `             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" \n`;
    xml += `             xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" \n`;
    xml += `             id="Definitions_${diagram.id}" \n`;
    xml += `             targetNamespace="http://www.omg.org/bpmn20">\n`;

    xml += `  <process id="Process_${diagram.id}" name="${diagram.name}" isExecutable="true">\n`;

    // Добавляем элементы
    diagram.pools.forEach(pool => {
      pool.elements.forEach(element => {
        xml += `    <${element.type} id="${element.id}" name="${element.name}">\n`;
        if (element.properties) {
          xml += `      <documentation>${JSON.stringify(element.properties)}</documentation>\n`;
        }
        xml += `    </${element.type}>\n`;
      });

      // Добавляем потоки
      pool.sequenceFlows.forEach(flow => {
        xml += `    <sequenceFlow id="${flow.id}" sourceRef="${flow.from}" targetRef="${flow.to}"`;
        if (flow.name) {
          xml += ` name="${flow.name}"`;
        }
        if (flow.condition) {
          xml += `>\n      <conditionExpression xsi:type="tFormalExpression"><![CDATA[${flow.condition}]]></conditionExpression>\n    </sequenceFlow>\n`;
        } else {
          xml += ` />\n`;
        }
      });
    });

    xml += `  </process>\n`;
    xml += `</definitions>`;

    return xml;
  }

  /**
   * Экспорт в JSON формат
   */
  exportToJSON(): string {
    if (!this.currentDiagram) {
      throw new Error('Диаграмма не создана');
    }
    return JSON.stringify(this.currentDiagram, null, 2);
  }

  /**
   * Экспорт в GraphML (для yEd, draw.io)
   */
  exportToGraphML(): string {
    if (!this.currentDiagram) {
      throw new Error('Диаграмма не создана');
    }

    let graphML = `<?xml version="1.0" encoding="UTF-8"?>\n`;
    graphML += `<graphml xmlns="http://graphml.graphdrawing.org/xmlns" \n`;
    graphML += `    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \n`;
    graphML += `    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns \n`;
    graphML += `     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">\n`;

    graphML += `  <key id="label" for="node" attr.name="label" attr.type="string"/>\n`;
    graphML += `  <key id="type" for="node" attr.name="type" attr.type="string"/>\n`;
    graphML += `  <key id="x" for="node" attr.name="x" attr.type="double"/>\n`;
    graphML += `  <key id="y" for="node" attr.name="y" attr.type="double"/>\n`;
    graphML += `  <key id="width" for="node" attr.name="width" attr.type="double"/>\n`;
    graphML += `  <key id="height" for="node" attr.name="height" attr.type="double"/>\n`;

    graphML += `  <graph id="G" edgedefault="directed">\n`;

    this.currentDiagram.pools.forEach(pool => {
      pool.elements.forEach(element => {
        graphML += `    <node id="${element.id}">\n`;
        graphML += `      <data key="label">${element.name}</data>\n`;
        graphML += `      <data key="type">${element.type}</data>\n`;
        graphML += `      <data key="x">${element.x}</data>\n`;
        graphML += `      <data key="y">${element.y}</data>\n`;
        graphML += `      <data key="width">${element.width}</data>\n`;
        graphML += `      <data key="height">${element.height}</data>\n`;
        graphML += `    </node>\n`;
      });

      pool.sequenceFlows.forEach(flow => {
        graphML += `    <edge id="${flow.id}" source="${flow.from}" target="${flow.to}">\n`;
        graphML += `      <data key="label">${flow.name || ''}</data>\n`;
        graphML += `    </edge>\n`;
      });
    });

    graphML += `  </graph>\n`;
    graphML += `</graphml>`;

    return graphML;
  }

  /**
   * Генерация кода 1C для реализации процесса
   */
  generate1CCode(): string {
    if (!this.currentDiagram) {
      throw new Error('Диаграмма не создана');
    }

    let code = `// Автогенерированный код 1C для процесса "${this.currentDiagram.name}"\n`;
    code += `// Сгенерировано: ${new Date().toLocaleString()}\n\n`;

    this.currentDiagram.pools.forEach((pool, poolIndex) => {
      code += `// Пул: ${pool.name}\n`;
      
      // Генерируем код для элементов
      pool.elements.forEach(element => {
        switch (element.type) {
          case BPMN_ELEMENT_TYPES.START_EVENT:
            code += `// Событие начала: ${element.name}\n`;
            code += `Процедура НачатьПроцесс_${poolIndex}_${element.id}()\n`;
            code += `  // Логика запуска процесса\n`;
            code += `КонецПроцедуры\n\n`;
            break;
            
          case C1C_TASK_TYPES.DOCUMENT_PROCESSING:
            code += `// Задача обработки документа: ${element.name}\n`;
            code += `Процедура ОбработатьДокумент_${poolIndex}_${element.id}()\n`;
            if (element.properties?.documentType) {
              code += `  // Тип документа: ${element.properties.documentType}\n`;
            }
            code += `  // Логика обработки документа\n`;
            code += `КонецПроцедуры\n\n`;
            break;
            
          case C1C_TASK_TYPES.REFERENCE_UPDATE:
            code += `// Задача обновления справочника: ${element.name}\n`;
            code += `Процедура ОбновитьСправочник_${poolIndex}_${element.id}()\n`;
            code += `  // Логика обновления справочника\n`;
            code += `КонецПроцедуры\n\n`;
            break;
            
          case C1C_TASK_TYPES.USER_TASK:
            code += `// Пользовательская задача: ${element.name}\n`;
            code += `Процедура ПоказатьФорму_${poolIndex}_${element.id}()\n`;
            if (element.properties?.formName) {
              code += `  // Форма: ${element.properties.formName}\n`;
            }
            code += `  // Открытие пользовательской формы\n`;
            code += `КонецПроцедуры\n\n`;
            break;
        }
      });

      // Генерируем основную процедуру выполнения
      code += `// Основная процедура выполнения пула: ${pool.name}\n`;
      code += `Процедура ВыполнитьПроцесс_${poolIndex}()\n`;
      pool.sequenceFlows.forEach(flow => {
        code += `  // Поток: ${flow.name || flow.id}\n`;
        code += `  // ${flow.from} -> ${flow.to}\n`;
        if (flow.condition) {
          code += `  // Условие: ${flow.condition}\n`;
        }
      });
      code += `КонецПроцедуры\n\n`;
    });

    return code;
  }

  /**
   * Валидация диаграммы
   */
  validateDiagram(): { isValid: boolean; errors: string[]; warnings: string[] } {
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!this.currentDiagram) {
      errors.push('Диаграмма не создана');
      return { isValid: false, errors, warnings };
    }

    if (this.currentDiagram.pools.length === 0) {
      warnings.push('Диаграмма не содержит пулов');
    }

    this.currentDiagram.pools.forEach((pool, poolIndex) => {
      if (pool.elements.length === 0) {
        warnings.push(`Пул ${poolIndex} (${pool.name}) не содержит элементов`);
      }

      // Проверяем наличие начального события
      const hasStartEvent = pool.elements.some(el => el.type === BPMN_ELEMENT_TYPES.START_EVENT);
      if (!hasStartEvent) {
        warnings.push(`Пул ${poolIndex} (${pool.name}) не содержит начального события`);
      }

      // Проверяем наличие конечного события
      const hasEndEvent = pool.elements.some(el => el.type === BPMN_ELEMENT_TYPES.END_EVENT);
      if (!hasEndEvent) {
        warnings.push(`Пул ${poolIndex} (${pool.name}) не содержит конечного события`);
      }

      // Проверяем потоки
      pool.sequenceFlows.forEach(flow => {
        const fromExists = pool.elements.some(el => el.id === flow.from);
        const toExists = pool.elements.some(el => el.id === flow.to);
        
        if (!fromExists) {
          errors.push(`Поток ${flow.id} ссылается на несуществующий элемент ${flow.from}`);
        }
        if (!toExists) {
          errors.push(`Поток ${flow.id} ссылается на несуществующий элемент ${flow.to}`);
        }
      });
    });

    return {
      isValid: errors.length === 0,
      errors,
      warnings
    };
  }

  /**
   * Получить текущую диаграмму
   */
  getCurrentDiagram(): BPMNDiagram | null {
    return this.currentDiagram;
  }

  /**
   * Получить статистику диаграммы
   */
  getDiagramStatistics(): {
    totalElements: number;
    elementsByType: Record<string, number>;
    totalPools: number;
    totalSequenceFlows: number;
  } {
    if (!this.currentDiagram) {
      return {
        totalElements: 0,
        elementsByType: {},
        totalPools: 0,
        totalSequenceFlows: 0
      };
    }

    const stats = {
      totalElements: 0,
      elementsByType: {} as Record<string, number>,
      totalPools: this.currentDiagram.pools.length,
      totalSequenceFlows: 0
    };

    this.currentDiagram.pools.forEach(pool => {
      stats.totalElements += pool.elements.length;
      stats.totalSequenceFlows += pool.sequenceFlows.length;

      pool.elements.forEach(element => {
        stats.elementsByType[element.type] = (stats.elementsByType[element.type] || 0) + 1;
      });
    });

    return stats;
  }
}

// Экспортируем экземпляр сервиса
export const bpmnDiagramService = new BPMNDiagramService();