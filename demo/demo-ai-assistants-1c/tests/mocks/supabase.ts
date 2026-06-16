/**
 * Моки для Supabase клиента и сервисов
 * Используются для тестирования Edge Functions без реального подключения к БД
 */

// Типы для моков
export interface MockSupabaseClient {
  auth: MockAuth;
  from: (table: string) => MockQueryBuilder;
  storage: MockStorage;
  functions: MockFunctions;
  rpc: (fn: string, args?: any) => Promise<any>;
}

export interface MockAuth {
  signInWithPassword: (credentials: any) => Promise<any>;
  signUp: (credentials: any) => Promise<any>;
  signOut: () => Promise<any>;
  getUser: () => Promise<any>;
  getSession: () => Promise<any>;
}

export interface MockQueryBuilder {
  select: (columns?: string) => MockQueryBuilder;
  insert: (data: any) => MockQueryBuilder;
  update: (data: any) => MockQueryBuilder;
  delete: () => MockQueryBuilder;
  eq: (column: string, value: any) => MockQueryBuilder;
  neq: (column: string, value: any) => MockQueryBuilder;
  gt: (column: string, value: any) => MockQueryBuilder;
  gte: (column: string, value: any) => MockQueryBuilder;
  lt: (column: string, value: any) => MockQueryBuilder;
  lte: (column: string, value: any) => MockQueryBuilder;
  like: (column: string, pattern: string) => MockQueryBuilder;
  ilike: (column: string, pattern: string) => MockQueryBuilder;
  is: (column: string, value: any) => MockQueryBuilder;
  in: (column: string, values: any[]) => MockQueryBuilder;
  order: (column: string, options?: any) => MockQueryBuilder;
  limit: (count: number) => MockQueryBuilder;
  range: (from: number, to: number) => MockQueryBuilder;
  single: () => Promise<any>;
  maybeSingle: () => Promise<any>;
  then: (resolve: any) => any;
  catch: (reject: any) => any;
}

export interface MockStorage {
  from: (bucket: string) => MockStorageBucket;
}

export interface MockStorageBucket {
  upload: (path: string, file: File | Blob, options?: any) => Promise<any>;
  download: (path: string) => Promise<any>;
  remove: (paths: string[]) => Promise<any>;
  list: (path?: string, options?: any) => Promise<any>;
  getPublicUrl: (path: string) => any;
}

export interface MockFunctions {
  invoke: (functionName: string, options?: any) => Promise<any>;
}

// Класс мока для Supabase клиента
export class MockSupabaseService implements MockSupabaseClient {
  public auth: MockAuth;
  public storage: MockStorage;
  private data: Map<string, any[]> = new Map();
  private users: any[] = [];

  constructor() {
    this.auth = new MockAuthService(this.users);
    this.storage = new MockStorageService();
    this.initializeDefaultData();
  }

  from(table: string): MockQueryBuilder {
    return new MockQueryBuilderService(this.data, table);
  }

  functions: MockFunctions = {
    invoke: async (functionName: string, options?: any) => {
      return {
        data: { message: `Mock function ${functionName} called` },
        error: null
      };
    }
  };

  async rpc(fn: string, args?: any) {
    return { data: `Mock RPC ${fn}`, error: null };
  }

  private initializeDefaultData() {
    // Инициализация тестовых данных
    this.data.set('users', [
      { id: '1', email: 'test@example.com', role: 'admin' },
      { id: '2', email: 'user@example.com', role: 'user' }
    ]);
    this.data.set('products', [
      { id: '1', name: 'Test Product', price: 100 },
      { id: '2', name: 'Another Product', price: 200 }
    ]);
  }
}

// Сервис для мока аутентификации
class MockAuthService implements MockAuth {
  constructor(private users: any[]) {}

  async signInWithPassword(credentials: any) {
    const user = this.users.find(u => u.email === credentials.email);
    if (!user) {
      return { data: null, error: { message: 'Invalid credentials' } };
    }
    return {
      data: { user, session: { access_token: 'mock_token' } },
      error: null
    };
  }

  async signUp(credentials: any) {
    const newUser = {
      id: Date.now().toString(),
      email: credentials.email,
      role: 'user'
    };
    this.users.push(newUser);
    return {
      data: { user: newUser, session: null },
      error: null
    };
  }

  async signOut() {
    return { error: null };
  }

  async getUser() {
    return {
      data: { user: this.users[0] },
      error: null
    };
  }

  async getSession() {
    return {
      data: { session: { access_token: 'mock_token' } },
      error: null
    };
  }
}

// Сервис для мока хранилища
class MockStorageService implements MockStorage {
  from(bucket: string): MockStorageBucket {
    return new MockStorageBucketService(bucket);
  }
}

// Сервис для мока корзины хранилища
class MockStorageBucketService implements MockStorageBucket {
  constructor(private bucket: string) {}

  async upload(path: string, file: File | Blob, options?: any) {
    return {
      data: { path, url: `https://mock-storage.com/${path}` },
      error: null
    };
  }

  async download(path: string) {
    return { data: new Blob(['mock content']), error: null };
  }

  async remove(paths: string[]) {
    return { data: paths, error: null };
  }

  async list(path?: string, options?: any) {
    return { data: [{ name: 'mock-file.txt' }], error: null };
  }

  getPublicUrl(path: string) {
    return { data: { publicUrl: `https://mock-storage.com/${path}` } };
  }
}

// Сервис для мока запросов к БД
class MockQueryBuilderService implements MockQueryBuilder {
  private table: string;
  private data: Map<string, any[]>;
  private currentData: any[] = [];
  private selectColumns: string = '*';
  private operations: string[] = [];

  constructor(data: Map<string, any[]>, table: string) {
    this.data = data;
    this.table = table;
    this.currentData = [...(data.get(table) || [])];
  }

  select(columns: string = '*') {
    this.selectColumns = columns;
    return this;
  }

  insert(data: any) {
    if (Array.isArray(data)) {
      this.currentData.push(...data);
    } else {
      this.currentData.push({ ...data, id: Date.now().toString() });
    }
    this.data.set(this.table, this.currentData);
    return this;
  }

  update(data: any) {
    return this;
  }

  delete() {
    return this;
  }

  eq(column: string, value: any) {
    this.currentData = this.currentData.filter(item => item[column] === value);
    return this;
  }

  neq(column: string, value: any) {
    this.currentData = this.currentData.filter(item => item[column] !== value);
    return this;
  }

  gt(column: string, value: any) {
    this.currentData = this.currentData.filter(item => item[column] > value);
    return this;
  }

  gte(column: string, value: any) {
    this.currentData = this.currentData.filter(item => item[column] >= value);
    return this;
  }

  lt(column: string, value: any) {
    this.currentData = this.currentData.filter(item => item[column] < value);
    return this;
  }

  lte(column: string, value: any) {
    this.currentData = this.currentData.filter(item => item[column] <= value);
    return this;
  }

  like(column: string, pattern: string) {
    this.currentData = this.currentData.filter(item => 
      item[column]?.includes(pattern.replace('%', ''))
    );
    return this;
  }

  ilike(column: string, pattern: string) {
    return this.like(column, pattern);
  }

  is(column: string, value: any) {
    return this.eq(column, value);
  }

  in(column: string, values: any[]) {
    this.currentData = this.currentData.filter(item => 
      values.includes(item[column])
    );
    return this;
  }

  order(column: string, options?: any) {
    this.currentData.sort((a, b) => {
      if (options?.ascending === false) {
        return b[column] - a[column];
      }
      return a[column] - b[column];
    });
    return this;
  }

  limit(count: number) {
    this.currentData = this.currentData.slice(0, count);
    return this;
  }

  range(from: number, to: number) {
    this.currentData = this.currentData.slice(from, to + 1);
    return this;
  }

  async single() {
    if (this.currentData.length === 0) {
      throw new Error('No rows returned');
    }
    return { data: this.currentData[0], error: null };
  }

  async maybeSingle() {
    if (this.currentData.length === 0) {
      return { data: null, error: null };
    }
    return { data: this.currentData[0], error: null };
  }

  then(resolve: any) {
    return resolve({ data: this.currentData, error: null });
  }

  catch(reject: any) {
    return {
      then: (resolve: any) => resolve({ data: this.currentData, error: null }),
      catch: reject
    };
  }
}

// Фабрика для создания мок-клиента
export function createMockSupabaseClient(): MockSupabaseClient {
  return new MockSupabaseService();
}

// Утилиты для тестирования
export function createTestUser(overrides: any = {}) {
  return {
    id: 'test-user-id',
    email: 'test@example.com',
    role: 'user',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides
  };
}

export function createTestProduct(overrides: any = {}) {
  return {
    id: 'test-product-id',
    name: 'Test Product',
    price: 100,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides
  };
}

export function createTestFile(name: string = 'test.txt', content: string = 'test content') {
  return new File([content], name, { type: 'text/plain' });
}