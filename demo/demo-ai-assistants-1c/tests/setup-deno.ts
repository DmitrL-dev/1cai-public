/**
 * Настройка для совместимости с Deno в тестовом окружении Node.js
 */

// Имитация глобальных объектов Deno
if (typeof globalThis.Deno === 'undefined') {
  globalThis.Deno = {
    serve: jest.fn().mockImplementation((handler) => {
      // Сохраняем обработчик для использования в тестах
      (globalThis as any).__denoHandler = handler;
      return Promise.resolve();
    }),
    build: {
      os: 'linux',
      arch: 'x86_64',
      vendor: 'unknown',
      version: '1.0.0'
    },
    version: {
      deno: '1.0.0',
      v8: '9.0.0',
      typescript: '4.0.0'
    },
    eval: jest.fn(),
    emit: jest.fn(),
    readTextFile: jest.fn().mockResolvedValue(''),
    writeTextFile: jest.fn().mockResolvedValue(undefined),
    readFile: jest.fn().mockResolvedValue(new Uint8Array()),
    writeFile: jest.fn().mockResolvedValue(undefined),
    mkdir: jest.fn().mockResolvedValue(undefined),
    remove: jest.fn().mockResolvedValue(undefined),
    copy: jest.fn().mockResolvedValue(undefined),
    rename: jest.fn().mockResolvedValue(undefined),
    makeTempDir: jest.fn().mockResolvedValue('/tmp/test'),
    stat: jest.fn().mockResolvedValue({
      isFile: () => false,
      isDirectory: () => false,
      size: 0,
      mtime: new Date()
    }),
    realPath: jest.fn().mockResolvedValue('/test/path'),
    readDir: jest.fn().mockResolvedValue([]),
    chmod: jest.fn().mockResolvedValue(undefined),
    chown: jest.fn().mockResolvedValue(undefined),
    exit: jest.fn(),
    run: jest.fn().mockReturnValue({
      status: Promise.resolve({ code: 0, success: true }),
      output: Promise.resolve(new Uint8Array()),
      stderr: Promise.resolve(new Uint8Array())
    }),
    kill: jest.fn().mockResolvedValue(undefined),
    env: {
      get: jest.fn((key: string) => process.env[key]),
      set: jest.fn(),
      delete: jest.fn(),
      toObject: jest.fn(() => process.env)
    },
    expandGlob: jest.fn().mockResolvedValue([]),
   资源和s: {
      load: jest.fn().mockResolvedValue(undefined),
      get: jest.fn().mockReturnValue(undefined),
      set: jest.fn(),
      delete: jest.fn(),
      query: jest.fn().mockReturnValue([]),
      close: jest.fn(),
      revoke: jest.fn()
    },
   .permissions: {
      request: jest.fn().mockResolvedValue({ state: 'granted' }),
      revoke: jest.fn().mockResolvedValue(undefined),
      query: jest.fn().mockResolvedValue({ state: 'granted' })
    },
    buildInfo: jest.fn().mockReturnValue({
      target: 'x86_64-unknown-linux-gnu',
     arch: 'x86_64',
      os: 'linux',
      vendor: 'unknown',
      prettyName: 'Deno Test Environment'
    }),
    connect: jest.fn(),
    listen: jest.fn().mockReturnValue({
      addr: { hostname: 'localhost', port: 8000 },
      close: jest.fn()
    }),
    start: jest.fn(),
    loadavg: jest.fn().mockReturnValue([0.1, 0.2, 0.3]),
    systemMemoryInfo: jest.fn().mockReturnValue({
      total: 8 * 1024 * 1024 * 1024,
      free: 4 * 1024 * 1024 * 1024,
      available: 4 * 1024 * 1024 * 1024
    }),
    hostname: jest.fn().mockReturnValue('test-host'),
    gid: jest.fn().mockReturnValue(1000),
    uid: jest.fn().mockReturnValue(1000),
    permissions: {
      request: jest.fn(),
      query: jest.fn(),
      revoke: jest.fn()
    },
    PropertyDescriptorMap: new Map(),
    formatError: jest.fn((error: Error) => error.stack || error.message),
    write: jest.fn(),
    read: jest.fn(),
    seek: jest.fn(),
    statSync: jest.fn().mockReturnValue({
      isFile: () => false,
      isDirectory: () => false,
      size: 0,
      mtime: new Date()
    }),
    readTextFileSync: jest.fn().mockReturnValue(''),
    readFileSync: jest.fn().mockReturnValue(new Uint8Array()),
    writeTextFileSync: jest.fn(),
    writeFileSync: jest.fn(),
    mkdirSync: jest.fn(),
    removeSync: jest.fn(),
    copyFileSync: jest.fn(),
    renameSync: jest.fn(),
    makeTempDirSync: jest.fn().mockReturnValue('/tmp/test'),
    readDirSync: jest.fn().mockReturnValue([]),
    chmodSync: jest.fn(),
    chownSync: jest.fn(),
    runSync: jest.fn().mockReturnValue({
      status: { code: 0, success: true },
      output: new Uint8Array(),
      stderr: new Uint8Array()
    }),
   资源s: {
      loadSync: jest.fn(),
      get: jest.fn().mockReturnValue(undefined),
      set: jest.fn(),
      delete: jest.fn()
    }
  } as any;
}

// Имитация Deno.serve для тестирования
if (typeof globalThis.Deno?.serve === 'function') {
  const originalServe = globalThis.Deno.serve;
  
  globalThis.Deno.serve = jest.fn().mockImplementation((handler: (req: Request) => Response | Promise<Response>) => {
    // Сохраняем обработчик для вызовов в тестах
    (globalThis as any).__denoHandler = handler;
    
    // Возвращаем промис, который разрешается сразу (как в реальном Deno)
    return Promise.resolve({
      close: jest.fn(),
      finished: Promise.resolve()
    });
  });
}

// Утилиты для тестирования Deno функций
(globalThis as any).__testDenoHandler = (request: Request): Response => {
  const handler = (globalThis as any).__denoHandler;
  if (handler) {
    return handler(request);
  }
  throw new Error('No Deno handler registered');
};

// Mock для crypto API, который используется в Deno
if (typeof globalThis.crypto === 'undefined') {
  globalThis.crypto = {
    randomUUID: jest.fn(() => 'test-uuid-' + Math.random()),
    getRandomValues: jest.fn((arr: Uint8Array) => {
      for (let i = 0; i < arr.length; i++) {
        arr[i] = Math.floor(Math.random() * 256);
      }
      return arr;
    }),
    subtle: {
      digest: jest.fn().mockResolvedValue(new Uint8Array(32)),
      encrypt: jest.fn().mockResolvedValue(new Uint8Array()),
      decrypt: jest.fn().mockResolvedValue(new Uint8Array()),
      generateKey: jest.fn().mockResolvedValue({}),
      importKey: jest.fn().mockResolvedValue({}),
      exportKey: jest.fn().mockResolvedValue(new ArrayBuffer())
    },
    webcrypto: {
      subtle: {
        digest: jest.fn().mockResolvedValue(new Uint8Array(32)),
        encrypt: jest.fn().mockResolvedValue(new Uint8Array()),
        decrypt: jest.fn().mockResolvedValue(new Uint8Array()),
        generateKey: jest.fn().mockResolvedValue({}),
        importKey: jest.fn().mockResolvedValue({}),
        exportKey: jest.fn().mockResolvedValue(new ArrayBuffer())
      }
    }
  };
}

// Импорт Jest globals для TypeScript
import '@jest/globals';

export {};
