#!/bin/bash

# 🔒 СКРИПТ РАЗВЕРТЫВАНИЯ БЕЗОПАСНЫХ EDGE FUNCTIONS
# Этот скрипт заменяет небезопасные функции на защищенные версии

set -e

echo "🔒 Starting secure deployment of AI Assistant functions..."

# Проверка наличия Supabase CLI
if ! command -v supabase &> /dev/null; then
    echo "❌ Supabase CLI не найден. Установите его с помощью: npm install -g supabase"
    exit 1
fi

# Проверка аутентификации Supabase
if ! supabase projects list &> /dev/null; then
    echo "❌ Необходимо войти в Supabase. Выполните: supabase login"
    exit 1
fi

# Переход в директорию проекта
cd "$(dirname "$0")"

echo "📁 Current directory: $(pwd)"

# Создание резервной копии оригинальных функций
echo "💾 Creating backup of original functions..."
BACKUP_DIR="functions_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -d "functions" ]; then
    cp -r functions/* "$BACKUP_DIR/" 2>/dev/null || true
    echo "✅ Backup created in: $BACKUP_DIR"
else
    echo "⚠️  Functions directory not found, skipping backup"
fi

# Список функций для обновления
FUNCTIONS=(
    "developer-demo"
    "architect-demo"
    "pm-demo"
    "tester-demo"
    "ba-demo"
)

# Развертывание безопасных функций
echo "🚀 Deploying secure functions..."
for func in "${FUNCTIONS[@]}"; do
    if [ -f "${func}/index-secure.ts" ]; then
        echo "📦 Deploying secure ${func}..."
        
        # Замена оригинального файла на безопасный
        cp "${func}/index-secure.ts" "${func}/index.ts"
        
        # Развертывание функции
        supabase functions deploy "$func" --project-ref "$(supabase projects list --output json | jq -r '.[0].id')"
        
        if [ $? -eq 0 ]; then
            echo "✅ Successfully deployed secure $func"
        else
            echo "❌ Failed to deploy $func"
            exit 1
        fi
    else
        echo "⚠️  Secure version of $func not found, skipping"
    fi
done

echo ""
echo "🎉 Secure deployment completed successfully!"
echo ""
echo "🔒 Security improvements applied:"
echo "   • CORS protection (no more wildcard origins)"
echo "   • JWT authentication"
echo "   • Rate limiting"
echo "   • Input validation"
echo "   • Security headers"
echo "   • Audit logging"
echo ""
echo "📋 Next steps:"
echo "   1. Update environment variables with secure values"
echo "   2. Test all endpoints with the new security measures"
echo "   3. Monitor logs for any security-related events"
echo "   4. Run security audit to verify compliance"
echo ""
echo "⚠️  Remember to:"
echo "   • Update all secrets in your environment"
echo "   • Test rate limiting doesn't break legitimate usage"
echo "   • Verify CORS settings allow only required origins"
echo "   • Enable monitoring and alerting for security events"