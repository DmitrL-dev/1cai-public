/**
 * Internationalization (i18n)
 * Multi-language support for global reach
 * 
 * Supported: EN, RU, ES, DE, FR, ZH, JA
 */

export const translations = {
  en: {
    // Navigation
    nav: {
      dashboard: "Dashboard",
      customers: "Customers",
      reports: "Reports",
      billing: "Billing",
      support: "Support",
      settings: "Settings"
    },
    
    // Owner Dashboard
    owner: {
      greeting: "Good Morning, Boss!",
      subtitle: "Here's your business in 30 seconds",
      revenue: "You Made This Month:",
      everything_ok: "Everything is OK",
      customers: "Happy customers",
      growth: "Business growth",
      new_this_month: "new this month!",
      you_are_growing: "You're growing!",
      recent_activity: "Recent Activity",
      see_full_report: "See Full Report",
      my_customers: "My Customers",
      get_paid: "Get Paid",
      customer_support: "Customer Support",
      help: "HELP"
    },
    
    // Common
    common: {
      loading: "Loading...",
      error: "Error",
      success: "Success",
      save: "Save",
      cancel: "Cancel",
      delete: "Delete",
      edit: "Edit",
      create: "Create",
      search: "Search",
      filter: "Filter",
      export: "Export",
      import: "Import",
      refresh: "Refresh",
      back: "Back"
    },
    
    // Errors
    errors: {
      network_error: "Network error. Check your connection.",
      server_error: "Server error. Please try again.",
      not_found: "Not found",
      unauthorized: "Please log in to continue",
      forbidden: "Access denied",
      validation_error: "Please check your input"
    }
  },
  
  ru: {
    // Навигация
    nav: {
      dashboard: "Дашборд",
      customers: "Клиенты",
      reports: "Отчёты",
      billing: "Оплата",
      support: "Поддержка",
      settings: "Настройки"
    },
    
    // Дашборд Владельца
    owner: {
      greeting: "Доброе утро, Босс!",
      subtitle: "Ваш бизнес за 30 секунд",
      revenue: "Вы заработали в этом месяце:",
      everything_ok: "Всё в порядке",
      customers: "Довольных клиентов",
      growth: "Рост бизнеса",
      new_this_month: "новых в этом месяце!",
      you_are_growing: "Вы растёте!",
      recent_activity: "Последняя активность",
      see_full_report: "Полный отчёт",
      my_customers: "Мои клиенты",
      get_paid: "Получить оплату",
      customer_support: "Поддержка клиентов",
      help: "ПОМОЩЬ"
    },
    
    // Общее
    common: {
      loading: "Загрузка...",
      error: "Ошибка",
      success: "Успех",
      save: "Сохранить",
      cancel: "Отмена",
      delete: "Удалить",
      edit: "Редактировать",
      create: "Создать",
      search: "Поиск",
      filter: "Фильтр",
      export: "Экспорт",
      import: "Импорт",
      refresh: "Обновить",
      back: "Назад"
    },
    
    // Ошибки
    errors: {
      network_error: "Ошибка сети. Проверьте подключение.",
      server_error: "Ошибка сервера. Попробуйте снова.",
      not_found: "Не найдено",
      unauthorized: "Войдите для продолжения",
      forbidden: "Доступ запрещён",
      validation_error: "Проверьте введённые данные"
    }
  },
  
  es: {
    // Spanish
    nav: {
      dashboard: "Tablero",
      customers: "Clientes",
      reports: "Informes",
      billing: "Facturación",
      support: "Soporte",
      settings: "Configuración"
    },
    owner: {
      greeting: "¡Buenos días, Jefe!",
      subtitle: "Su negocio en 30 segundos",
      revenue: "Ganó este mes:",
      everything_ok: "Todo está bien",
      customers: "Clientes felices",
      growth: "Crecimiento empresarial"
    }
  },
  
  de: {
    // German
    nav: {
      dashboard: "Dashboard",
      customers: "Kunden",
      reports: "Berichte",
      billing: "Abrechnung",
      support: "Support",
      settings: "Einstellungen"
    },
    owner: {
      greeting: "Guten Morgen, Chef!",
      subtitle: "Ihr Geschäft in 30 Sekunden",
      revenue: "Sie haben diesen Monat verdient:",
      everything_ok: "Alles ist in Ordnung",
      customers: "Zufriedene Kunden",
      growth: "Geschäftswachstum"
    }
  },
  
  fr: {
    // French
    nav: {
      dashboard: "Tableau de bord",
      customers: "Clients",
      reports: "Rapports",
      billing: "Facturation",
      support: "Support",
      settings: "Paramètres"
    },
    owner: {
      greeting: "Bonjour, Patron!",
      subtitle: "Votre entreprise en 30 secondes",
      revenue: "Vous avez gagné ce mois-ci:",
      everything_ok: "Tout va bien",
      customers: "Clients satisfaits",
      growth: "Croissance de l'entreprise"
    }
  },
  
  zh: {
    // Chinese
    nav: {
      dashboard: "仪表板",
      customers: "客户",
      reports: "报告",
      billing: "账单",
      support: "支持",
      settings: "设置"
    },
    owner: {
      greeting: "早上好，老板！",
      subtitle: "30秒了解您的业务",
      revenue: "本月收入:",
      everything_ok: "一切正常",
      customers: "满意客户",
      growth: "业务增长"
    }
  },
  
  ja: {
    // Japanese
    nav: {
      dashboard: "ダッシュボード",
      customers: "顧客",
      reports: "レポート",
      billing: "請求",
      support: "サポート",
      settings: "設定"
    },
    owner: {
      greeting: "おはようございます、ボス！",
      subtitle: "30秒でビジネスを確認",
      revenue: "今月の収益:",
      everything_ok: "すべて正常",
      customers: "満足している顧客",
      growth: "ビジネスの成長"
    }
  }
};

export type Language = keyof typeof translations;
export type TranslationKey = keyof typeof translations.en;

// i18n hook
export function useTranslation(language: Language = 'en') {
  const t = (key: string): string => {
    const keys = key.split('.');
    let value: any = translations[language];
    
    for (const k of keys) {
      value = value?.[k];
    }
    
    return value || key;
  };
  
  return { t, language };
}


