/**
 * Integration тесты для проверки взаимодействия между модулями
 */

import { assertEquals, assert, assertExists } from "https://deno.land/std@0.224.0/assert/mod.ts";

// Mock для API вызовов
class MockSupabaseClient {
  private data: Record<string, any> = {};

  async from(table: string) {
    return {
      select: () => this,
      insert: (data: any) => {
        this.data[table] = this.data[table] || [];
        this.data[table].push({ id: Date.now(), ...data });
        return this;
      },
      update: (data: any) => {
        return this;
      },
      delete: () => this,
      eq: (column: string, value: any) => this,
      single: () => ({
        data: this.data[table]?.[0] || null,
        error: null
      }),
      data: this.data[table] || [],
      error: null
    };
  }

  storage() {
    return {
      from: () => ({
        upload: (path: string, file: File) => Promise.resolve({ data: { path }, error: null }),
        download: (path: string) => Promise.resolve({ data: null, error: null }),
        remove: (paths: string[]) => Promise.resolve({ data: [], error: null }),
        list: (path?: string) => Promise.resolve({ data: [], error: null })
      })
    };
  }
}

Deno.test("Integration Test: Взаимодействие компонента с API", async () => {
  const mockClient = new MockSupabaseClient();
  
  // Тест создания пользователя через API
  const createUser = async (userData: { name: string; email: string }) => {
    const { data, error } = await mockClient.from('users').insert(userData).select().single();
    return { data, error };
  };

  const userData = { name: "Тест Пользователь", email: "test@example.com" };
  const result = await createUser(userData);

  assertExists(result.data, "Данные пользователя должны быть созданы");
  assertEquals(result.data.name, userData.name, "Имя пользователя должно совпадать");
  assertEquals(result.data.email, userData.email, "Email пользователя должен совпадать");
  assertEquals(result.error, null, "Не должно быть ошибок при создании пользователя");
});

Deno.test("Integration Test: Генерация изображений с сохранением в storage", async () => {
  const mockClient = new MockSupabaseClient();
  
  const generateAndSaveImage = async (prompt: string) => {
    // Симулируем генерацию изображения
    const imageData = `data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==`;
    
    // Конвертируем base64 в Blob
    const response = await fetch(imageData);
    const blob = await response.blob();
    
    // Сохраняем в storage
    const fileName = `image-${Date.now()}.png`;
    const { data: uploadData, error: uploadError } = await mockClient.storage()
      .from('images')
      .upload(fileName, blob);

    if (uploadError) {
      throw new Error(`Upload failed: ${uploadError.message}`);
    }

    // Сохраняем метаданные в базу данных
    const { data: metadata, error: metadataError } = await mockClient.from('generated_images')
      .insert({
        prompt,
        file_path: uploadData.path,
        created_at: new Date().toISOString()
      })
      .select()
      .single();

    if (metadataError) {
      throw new Error(`Metadata save failed: ${metadataError.message}`);
    }

    return { image: imageData, metadata, uploadData };
  };

  const prompt = "Красивый закат над морем";
  const result = await generateAndSaveImage(prompt);

  assertExists(result.image, "Изображение должно быть сгенерировано");
  assertEquals(result.metadata.prompt, prompt, "Промпт должен быть сохранен");
  assertExists(result.uploadData.path, "Файл должен быть загружен в storage");
});

Deno.test("Integration Test: Комплексный workflow генерации контента", async () => {
  const mockClient = new MockSupabaseClient();
  
  const generateContentWorkflow = async (type: 'image' | 'video', prompt: string) => {
    // 1. Валидируем входные данные
    if (!prompt || prompt.length < 10) {
      throw new Error("Промпт должен содержать минимум 10 символов");
    }

    // 2. Создаем запись о задаче
    const { data: task, error: taskError } = await mockClient.from('generation_tasks')
      .insert({
        type,
        prompt,
        status: 'pending',
        created_at: new Date().toISOString()
      })
      .select()
      .single();

    if (taskError) {
      throw new Error(`Failed to create task: ${taskError.message}`);
    }

    // 3. Симулируем генерацию контента
    const isImage = type === 'image';
    const content = isImage 
      ? 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
      : 'data:video/mp4;base64,AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAEFNtaWQAAAA';

    // 4. Сохраняем результат
    const { data: result, error: resultError } = await mockClient.from('generation_results')
      .insert({
        task_id: task.id,
        content,
        content_type: type,
        created_at: new Date().toISOString()
      })
      .select()
      .single();

    if (resultError) {
      throw new Error(`Failed to save result: ${resultError.message}`);
    }

    // 5. Обновляем статус задачи
    await mockClient.from('generation_tasks')
      .update({ status: 'completed' })
      .eq('id', task.id);

    return { task, result, content };
  };

  // Тест генерации изображения
  const imageResult = await generateContentWorkflow('image', 'Красивый пейзаж с горами');
  assertEquals(imageResult.task.type, 'image', 'Тип задачи должен быть image');
  assertEquals(imageResult.task.status, 'completed', 'Статус задачи должен быть completed');
  assertExists(imageResult.result.content, 'Результат должен содержать контент');
  assert(imageResult.result.content.startsWith('data:image/'), 'Контент должен быть изображением');

  // Тест генерации видео
  const videoResult = await generateContentWorkflow('video', 'Замедленное видео дождя');
  assertEquals(videoResult.task.type, 'video', 'Тип задачи должен быть video');
  assertEquals(videoResult.result.content_type, 'video', 'Тип контента должен быть video');
  assert(videoResult.result.content.startsWith('data:video/'), 'Контент должен быть видео');
});

Deno.test("Integration Test: Компонент с использованием множественных хуков", () => {
  // Симуляция состояния компонента
  interface ComponentState {
    isLoading: boolean;
    error: string | null;
    data: any[];
    pagination: {
      page: number;
      limit: number;
      total: number;
    };
  }

  const initialState: ComponentState = {
    isLoading: false,
    error: null,
    data: [],
    pagination: { page: 1, limit: 10, total: 0 }
  };

  // Симуляция действий компонента
  const actions = {
    setLoading: (state: ComponentState, loading: boolean): ComponentState => ({
      ...state,
      isLoading: loading
    }),

    setError: (state: ComponentState, error: string | null): ComponentState => ({
      ...state,
      error,
      isLoading: false
    }),

    setData: (state: ComponentState, data: any[]): ComponentState => ({
      ...state,
      data,
      isLoading: false,
      error: null,
      pagination: { ...state.pagination, total: data.length }
    }),

    nextPage: (state: ComponentState): ComponentState => ({
      ...state,
      pagination: { ...state.pagination, page: state.pagination.page + 1 }
    })
  };

  // Тест последовательности действий
  let state = initialState;

  // Начинаем загрузку
  state = actions.setLoading(state, true);
  assertEquals(state.isLoading, true, 'Состояние загрузки должно быть true');
  assertEquals(state.error, null, 'Не должно быть ошибок');

  // Симулируем ошибку
  state = actions.setError(state, "Ошибка загрузки данных");
  assertEquals(state.error, "Ошибка загрузки данных", 'Должна быть ошибка');
  assertEquals(state.isLoading, false, 'Загрузка должна быть остановлена');

  // Восстанавливаемся после ошибки
  state = actions.setLoading(state, true);
  state = actions.setData(state, ['item1', 'item2', 'item3']);

  assertEquals(state.data.length, 3, 'Должно быть 3 элемента данных');
  assertEquals(state.pagination.total, 3, 'Общее количество должно быть 3');
  assertEquals(state.isLoading, false, 'Загрузка должна завершиться');
  assertEquals(state.error, null, 'Ошибка должна быть очищена');

  // Переходим на следующую страницу
  state = actions.nextPage(state);
  assertEquals(state.pagination.page, 2, 'Страница должна быть 2');
});

Deno.test("Integration Test: Интеграция с внешними API", async () => {
  // Мок для внешнего API
  const mockExternalAPI = {
    async generateImage(prompt: string): Promise<string> {
      // Симулируем задержку API
      await new Promise(resolve => setTimeout(resolve, 100));
      return `generated-image-${Date.now()}.png`;
    },

    async validateCredits(userId: string): Promise<boolean> {
      await new Promise(resolve => setTimeout(resolve, 50));
      return userId.startsWith('valid_');
    },

    async deductCredits(userId: string, amount: number): Promise<boolean> {
      await new Promise(resolve => setTimeout(resolve, 75));
      return true;
    }
  };

  // Комплексная функция с использованием внешних API
  const processImageGeneration = async (userId: string, prompt: string) => {
    // 1. Проверяем кредиты
    const hasCredits = await mockExternalAPI.validateCredits(userId);
    if (!hasCredits) {
      throw new Error("Недостаточно кредитов");
    }

    // 2. Генерируем изображение
    const imageUrl = await mockExternalAPI.generateImage(prompt);

    // 3. Списываем кредиты
    const creditsDeducted = await mockExternalAPI.deductCredits(userId, 1);
    if (!creditsDeducted) {
      throw new Error("Не удалось списать кредиты");
    }

    return {
      imageUrl,
      creditsUsed: 1,
      status: 'success'
    };
  };

  // Тест успешного процесса
  const successResult = await processImageGeneration('valid_user_123', 'Красивый закат');
  assert(successResult.imageUrl.startsWith('generated-image-'), 'URL изображения должен быть сгенерирован');
  assertEquals(successResult.creditsUsed, 1, 'Должно быть списано 1 кредит');
  assertEquals(successResult.status, 'success', 'Статус должен быть success');

  // Тест с недостаточными кредитами
  try {
    await processImageGeneration('invalid_user', 'Красивый закат');
    assert(false, 'Должна быть ошибка с недостаточными кредитами');
  } catch (error) {
    assertEquals(error.message, "Недостаточно кредитов", 'Сообщение об ошибке должно быть корректным');
  }
});
