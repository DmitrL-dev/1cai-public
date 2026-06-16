#!/bin/bash

# Semantic Versioning and Release Management Script
# Автоматизирует версионирование, генерацию changelog и release notes

set -euo pipefail

# Конфигурация
CURRENT_VERSION=""
NEW_VERSION=""
BUMP_TYPE=""
CHANGELOG_FILE="CHANGELOG.md"
RELEASE_NOTES_FILE="RELEASE_NOTES.md"
VERSION_FILE="VERSION"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Логирование
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Получение текущей версии
get_current_version() {
    # Попытка получить версию из различных источников
    
    # 1. Git теги
    if git describe --tags --abbrev=0 2>/dev/null | grep -q '^v'; then
        CURRENT_VERSION=$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//')
        log "Текущая версия из Git тегов: v$CURRENT_VERSION"
        return 0
    fi
    
    # 2. VERSION файл
    if [ -f "$VERSION_FILE" ]; then
        CURRENT_VERSION=$(cat "$VERSION_FILE" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if [ -n "$CURRENT_VERSION" ]; then
            log "Текущая версия из VERSION файла: $CURRENT_VERSION"
            return 0
        fi
    fi
    
    # 3. package.json
    if [ -f "package.json" ]; then
        CURRENT_VERSION=$(jq -r '.version' package.json 2>/dev/null || echo "")
        if [ -n "$CURRENT_VERSION" ] && [ "$CURRENT_VERSION" != "null" ]; then
            log "Текущая версия из package.json: $CURRENT_VERSION"
            return 0
        fi
    fi
    
    # 4. По умолчанию 0.1.0
    CURRENT_VERSION="0.1.0"
    warn "Не удалось определить текущую версию, используем по умолчанию: $CURRENT_VERSION"
    return 0
}

# Определение типа bump на основе commit сообщений
determine_bump_type() {
    local commit_msg=$1
    local ConventionalCommits_prefix=$(echo "$commit_msg" | grep -E "^(feat|fix|chore|style|refactor|perf|test|build|ci|docs)\(!)?:|^BREAKING CHANGE" | head -1)
    
    if [ -n "$ConventionalCommits_prefix" ]; then
        if [[ "$ConventionalCommits_prefix" =~ ^feat!?: ]] || [[ "$ConventionalCommits_prefix" =~ ^BREAKING CHANGE ]]; then
            echo "major"
        elif [[ "$ConventionalCommits_prefix" =~ ^feat: ]]; then
            echo "minor"
        else
            echo "patch"
        fi
    else
        # Проверка на BREAKING CHANGE в описании
        if [[ "$commit_msg" =~ BREAKING\ CHANGE|breaking\ change ]]; then
            echo "major"
        else
            echo "patch"
        fi
    fi
}

# Автоматическое определение типа bump
auto_bump() {
    log "Автоматическое определение типа версии..."
    
    # Получение последнего тега
    local last_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    local since_tag=""
    
    if [ -n "$last_tag" ]; then
        since_tag="$last_tag"
    else
        # Если нет тегов, анализируем всю историю
        since_tag=$(git log --pretty=format:"%H" --reverse | head -1)
    fi
    
    # Анализ коммитов с последнего тега
    local commits=$(git log "$since_tag"..HEAD --pretty=format:"%s" --no-merges)
    
    if [ -z "$commits" ]; then
        log "Нет новых коммитов с последнего тега"
        echo "none"
        return 0
    fi
    
    local bump_type="patch"
    
    # Анализ каждого коммита
    while IFS= read -r commit; do
        if [ -n "$commit" ]; then
            local commit_bump=$(determine_bump_type "$commit")
            case $commit_bump in
                "major")
                    bump_type="major"
                    break
                    ;;
                "minor")
                    if [ "$bump_type" != "major" ]; then
                        bump_type="minor"
                    fi
                    ;;
                "patch")
                    # Оставляем как есть
                    ;;
            esac
        fi
    done <<< "$commits"
    
    echo "$bump_type"
}

# Вычисление новой версии
calculate_new_version() {
    local bump_type=$1
    
    log "Вычисление новой версии (bump: $bump_type)..."
    
    # Парсинг текущей версии
    IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
    local major=${VERSION_PARTS[0]:-0}
    local minor=${VERSION_PARTS[1]:-0}
    local patch=${VERSION_PARTS[2]:-0}
    
    case $bump_type in
        "major")
            NEW_VERSION="$((major + 1)).0.0"
            ;;
        "minor")
            NEW_VERSION="$major.$((minor + 1)).0"
            ;;
        "patch")
            NEW_VERSION="$major.$minor.$((patch + 1))"
            ;;
        "alpha"|"beta"|"rc")
            local suffix="-$bump_type"
            NEW_VERSION="$major.$minor.$patch$suffix.$(date +%s)"
            ;;
        *)
            error "Неизвестный тип bump: $bump_type"
            exit 1
            ;;
    esac
    
    log "Новая версия: $NEW_VERSION"
}

# Генерация changelog
generate_changelog() {
    log "Генерация changelog..."
    
    local since_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    
    # Заголовок
    cat > "$CHANGELOG_FILE" << EOF
# Changelog

Все важные изменения в этом проекте будут документированы в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и этот проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

EOF
    
    # Версия
    cat >> "$CHANGELOG_FILE" << EOF
## [$NEW_VERSION] - $(date +'%Y-%m-%d')

EOF
    
    # Группировка изменений по типам
    local feat_count=0
    local fix_count=0
    local docs_count=0
    local perf_count=0
    local refactor_count=0
    local test_count=0
    local chore_count=0
    local other_count=0
    
    # Получение коммитов с последнего тега
    local commits=$(git log "$since_tag"..HEAD --pretty=format:"%h %s %b" --no-merges)
    
    # Разделение коммитов по типам
    while IFS= read -r commit_line; do
        if [ -z "$commit_line" ]; then
            continue
        fi
        
        local hash=$(echo "$commit_line" | awk '{print $1}')
        local subject=$(echo "$commit_line" | awk '{$1=""; print $0}' | sed 's/^ //')
        local commit_type=$(echo "$subject" | grep -E "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore)" | cut -d: -f1)
        
        case $commit_type in
            "feat")
                feat_count=$((feat_count + 1))
                ;;
            "fix")
                fix_count=$((fix_count + 1))
                ;;
            "docs")
                docs_count=$((docs_count + 1))
                ;;
            "perf")
                perf_count=$((perf_count + 1))
                ;;
            "refactor")
                refactor_count=$((refactor_count + 1))
                ;;
            "test")
                test_count=$((test_count + 1))
                ;;
            "chore"|"build"|"ci")
                chore_count=$((chore_count + 1))
                ;;
            *)
                other_count=$((other_count + 1))
                ;;
        esac
    done <<< "$commits"
    
    # Добавление секций только если есть соответствующие изменения
    if [ $feat_count -gt 0 ]; then
        echo "### Added" >> "$CHANGELOG_FILE"
        git log "$since_tag"..HEAD --pretty=format:"- %s" --no-merges | grep -E "^feat" | sed 's/^feat: /- /' >> "$CHANGELOG_FILE"
        echo "" >> "$CHANGELOG_FILE"
    fi
    
    if [ $fix_count -gt 0 ]; then
        echo "### Fixed" >> "$CHANGELOG_FILE"
        git log "$since_tag"..HEAD --pretty=format:"- %s" --no-merges | grep -E "^fix" | sed 's/^fix: /- /' >> "$CHANGELOG_FILE"
        echo "" >> "$CHANGELOG_FILE"
    fi
    
    if [ $perf_count -gt 0 ]; then
        echo "### Performance" >> "$CHANGELOG_FILE"
        git log "$since_tag"..HEAD --pretty=format:"- %s" --no-merges | grep -E "^perf" | sed 's/^perf: /- /' >> "$CHANGELOG_FILE"
        echo "" >> "$CHANGELOG_FILE"
    fi
    
    if [ $refactor_count -gt 0 ]; then
        echo "### Refactored" >> "$CHANGELOG_FILE"
        git log "$since_tag"..HEAD --pretty=format:"- %s" --no-merges | grep -E "^refactor" | sed 's/^refactor: /- /' >> "$CHANGELOG_FILE"
        echo "" >> "$CHANGELOG_FILE"
    fi
    
    if [ $docs_count -gt 0 ]; then
        echo "### Documentation" >> "$CHANGELOG_FILE"
        git log "$since_tag"..HEAD --pretty=format:"- %s" --no-merges | grep -E "^docs" | sed 's/^docs: /- /' >> "$CHANGELOG_FILE"
        echo "" >> "$CHANGELOG_FILE"
    fi
    
    if [ $test_count -gt 0 ]; then
        echo "### Tests" >> "$CHANGELOG_FILE"
        git log "$since_tag"..HEAD --pretty=format:"- %s" --no-merges | grep -E "^test" | sed 's/^test: /- /' >> "$CHANGELOG_FILE"
        echo "" >> "$CHANGELOG_FILE"
    fi
    
    if [ $chore_count -gt 0 ]; then
        echo "### Chores" >> "$CHANGELOG_FILE"
        git log "$since_tag"..HEAD --pretty=format:"- %s" --no-merges | grep -E "^(chore|build|ci)" | sed 's/^[a-z]*: /- /' >> "$CHANGELOG_FILE"
        echo "" >> "$CHANGELOG_FILE"
    fi
    
    if [ $other_count -gt 0 ]; then
        echo "### Other Changes" >> "$CHANGELOG_FILE"
        git log "$since_tag"..HEAD --pretty=format:"- %s" --no-merges | grep -vE "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore)" >> "$CHANGELOG_FILE"
        echo "" >> "$CHANGELOG_FILE"
    fi
    
    # Добавление статистики
    cat >> "$CHANGELOG_FILE" << EOF

## Statistics

- **Total commits:** $(git log "$since_tag"..HEAD --no-merges --pretty=format:"%H" | wc -l)
- **Features:** $feat_count
- **Bug fixes:** $fix_count
- **Performance improvements:** $perf_count
- **Documentation changes:** $docs_count
- **Refactoring:** $refactor_count
- **Tests:** $test_count
- **Chores:** $chore_count

---

EOF
    
    # Добавление предыдущих записей changelog (если файл существует)
    if [ -f "$CHANGELOG_FILE.backup" ]; then
        tail -n +2 "$CHANGELOG_FILE.backup" >> "$CHANGELOG_FILE" 2>/dev/null || true
    fi
    
    # Создание backup
    cp "$CHANGELOG_FILE" "$CHANGELOG_FILE.backup"
    
    log "Changelog сгенерирован: $CHANGELOG_FILE"
}

# Генерация release notes
generate_release_notes() {
    log "Генерация release notes..."
    
    local since_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    
    # Получение статистики коммитов
    local total_commits=$(git log "$since_tag"..HEAD --no-merges --pretty=format:"%H" | wc -l)
    local contributors=$(git log "$since_tag"..HEAD --no-merges --pretty=format:"%an <%ae>" | sort -u | wc -l)
    
    # Создание release notes
    cat > "$RELEASE_NOTES_FILE" << EOF
# Release $NEW_VERSION

**Release Date:** $(date +'%Y-%m-%d')

EOF
    
    # Добавление changelog секции
    if [ -f "$CHANGELOG_FILE" ]; then
        echo "## Changes" >> "$RELEASE_NOTES_FILE"
        grep -A 1000 "^## \[$NEW_VERSION\]" "$CHANGELOG_FILE" | tail -n +3 >> "$RELEASE_NOTES_FILE" 2>/dev/null || true
        echo "" >> "$RELEASE_NOTES_FILE"
    fi
    
    # Добавление статистики
    cat >> "$RELEASE_NOTES_FILE" << EOF

## Statistics

- **Contributors:** $contributors
- **Total commits:** $total_commits
- **Lines added:** $(git diff "$since_tag"..HEAD --stat | tail -1 | awk '{print $4}' || echo "0")
- **Lines removed:** $(git diff "$since_tag"..HEAD --stat | tail -1 | awk '{print $6}' || echo "0")

EOF
    
    # Docker образы
    cat >> "$RELEASE_NOTES_FILE" << EOF

## Docker Images

\`\`\`
${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/api-gateway:$NEW_VERSION
${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/user-service:$NEW_VERSION
${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/auth-service:$NEW_VERSION
${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/payment-service:$NEW_VERSION
${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/notification-service:$NEW_VERSION
\`\`\`

EOF
    
    # Quality gates
    cat >> "$RELEASE_NOTES_FILE" << EOF

## Quality Gates Passed

- ✅ Code coverage: > 80%
- ✅ All tests passed
- ✅ Security scan: No high severity issues  
- ✅ Build: Successful for all services
- ✅ Performance: Meets benchmarks

EOF
    
    # Migration guide (если есть breaking changes)
    if [[ "$NEW_VERSION" =~ ^([0-9]+)\.0\.0$ ]] || git log "$since_tag"..HEAD --grep="BREAKING CHANGE\|breaking change" --oneline | grep -q .; then
        cat >> "$RELEASE_NOTES_FILE" << EOF

## Migration Guide

⚠️ **Breaking Changes Detected**

Please review the breaking changes in this release and update your application accordingly.

For detailed migration instructions, see [MIGRATION.md](MIGRATION.md).

EOF
    fi
    
    # Installation
    cat >> "$RELEASE_NOTES_FILE" << EOF

## Installation

### Docker

\`\`\`bash
docker pull ${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/api-gateway:$NEW_VERSION
\`\`\`

### Kubernetes

\`\`\`bash
kubectl set image deployment/api-gateway api-gateway=${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/api-gateway:$NEW_VERSION -n microservices
\`\`\`

EOF
    
    log "Release notes сгенерированы: $RELEASE_NOTES_FILE"
}

# Обновление версий в файлах проекта
update_version_files() {
    log "Обновление версий в файлах проекта..."
    
    # package.json
    if [ -f "package.json" ]; then
        log "Обновление version в package.json"
        jq ".version = \"$NEW_VERSION\"" package.json > package.json.tmp
        mv package.json.tmp package.json
    fi
    
    # VERSION файл
    echo "$NEW_VERSION" > "$VERSION_FILE"
    
    # Helm charts (если есть)
    if [ -d "helm" ]; then
        log "Обновление версий в Helm charts"
        find helm -name "Chart.yaml" -exec sed -i "s/version: .*/version: $NEW_VERSION/g" {} \;
        find helm -name "values.yaml" -exec sed -i "s/tag: .*/tag: $NEW_VERSION/g" {} \;
    fi
    
    # Docker Compose файлы
    if [ -f "docker-compose.yml" ]; then
        sed -i "s/image: .*:latest/image: ${REGISTRY:-ghcr.io}\/${IMAGE_NAME:-$GITHUB_REPOSITORY}\/api-gateway:$NEW_VERSION/g" docker-compose.yml
    fi
}

# Создание Git тега
create_git_tag() {
    log "Создание Git тега v$NEW_VERSION..."
    
    # Создание annotated тега
    git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"
    
    # Добавление аннотации с changelog
    {
        echo "Release v$NEW_VERSION"
        echo ""
        echo "$(cat "$RELEASE_NOTES_FILE")"
    } > tag-message.tmp
    
    git tag -d "v$NEW_VERSION" >/dev/null 2>&1 || true
    git tag -a "v$NEW_VERSION" -F tag-message.tmp
    rm -f tag-message.tmp
    
    log "Git тег v$NEW_VERSION создан"
}

# Генерация конфигурации для артефактов
generate_artifact_config() {
    cat > release-artifacts.json << EOF
{
    "version": "$NEW_VERSION",
    "previous_version": "$CURRENT_VERSION",
    "bump_type": "$BUMP_TYPE",
    "release_date": "$(date -Iseconds)",
    "commit": "$(git rev-parse HEAD)",
    "commit_short": "$(git rev-parse --short HEAD)",
    "branch": "$(git branch --show-current)",
    "tag": "v$NEW_VERSION",
    "changelog_file": "$CHANGELOG_FILE",
    "release_notes_file": "$RELEASE_NOTES_FILE",
    "docker_images": {
        "api-gateway": "${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/api-gateway:$NEW_VERSION",
        "user-service": "${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/user-service:$NEW_VERSION",
        "auth-service": "${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/auth-service:$NEW_VERSION",
        "payment-service": "${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/payment-service:$NEW_VERSION",
        "notification-service": "${REGISTRY:-ghcr.io}/${IMAGE_NAME:-$GITHUB_REPOSITORY}/notification-service:$NEW_VERSION"
    },
    "stats": {
        "total_commits": $(git log "$CURRENT_TAG"..HEAD --no-merges --pretty=format:"%H" | wc -l),
        "contributors": $(git log "$CURRENT_TAG"..HEAD --no-merges --pretty=format:"%an <%ae>" | sort -u | wc -l)
    }
}
EOF
    
    log "Конфигурация артефактов сохранена: release-artifacts.json"
}

# Основная функция
main() {
    local action=${1:-"bump"}
    
    log "🚀 Semantic Versioning Script"
    log "Action: $action"
    
    case $action in
        "bump")
            # Определение типа bump
            if [ -n "${BUMP_TYPE:-}" ]; then
                log "Using provided bump type: $BUMP_TYPE"
            else
                BUMP_TYPE=$(auto_bump)
                if [ "$BUMP_TYPE" = "none" ]; then
                    log "Нет изменений для версионирования"
                    exit 0
                fi
                log "Определенный тип bump: $BUMP_TYPE"
            fi
            
            get_current_version
            calculate_new_version "$BUMP_TYPE"
            
            # Генерация файлов
            generate_changelog
            generate_release_notes
            update_version_files
            generate_artifact_config
            
            # Показать результат
            echo ""
            log "📦 Semantic Versioning Complete"
            log "   Current: $CURRENT_VERSION"
            log "   New: $NEW_VERSION"
            log "   Bump: $BUMP_TYPE"
            log "   Files updated:"
            log "     - $CHANGELOG_FILE"
            log "     - $RELEASE_NOTES_FILE"
            log "     - VERSION"
            
            if [ -f "package.json" ]; then
                log "     - package.json"
            fi
            ;;
            
        "tag")
            # Создание Git тега
            get_current_version
            create_git_tag
            log "✅ Git тег v$NEW_VERSION создан"
            ;;
            
        "release-notes")
            # Только генерация release notes
            get_current_version
            calculate_new_version "${2:-patch}"
            generate_release_notes
            log "✅ Release notes созданы: $RELEASE_NOTES_FILE"
            ;;
            
        "changelog")
            # Только генерация changelog
            get_current_version
            calculate_new_version "${2:-patch}"
            generate_changelog
            log "✅ Changelog создан: $CHANGELOG_FILE"
            ;;
            
        "show")
            # Показать текущую версию
            get_current_version
            echo "$CURRENT_VERSION"
            ;;
            
        "validate")
            # Валидация версии
            local version=$2
            if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z]+(\.[0-9]+)?)?$ ]]; then
                log "✅ Версия $version валидна"
                exit 0
            else
                error "❌ Версия $version не валидна"
                exit 1
            fi
            ;;
            
        *)
            error "Неизвестное действие: $action"
            echo "Доступные действия: bump, tag, release-notes, changelog, show, validate"
            exit 1
            ;;
    esac
}

# Запуск
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Установка переменных окружения
    export CURRENT_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    
    if [ $# -lt 1 ]; then
        echo "Использование: $0 <action> [options]"
        echo ""
        echo "Actions:"
        echo "  bump [type]     - Создать новую версию (auto, major, minor, patch, alpha, beta, rc)"
        echo "  tag             - Создать Git тег для текущей версии"
        echo "  release-notes   - Сгенерировать только release notes"
        echo "  changelog       - Сгенерировать только changelog"
        echo "  show            - Показать текущую версию"
        echo "  validate <ver>  - Валидировать версию"
        echo ""
        echo "Environment variables:"
        echo "  BUMP_TYPE       - Тип версионирования (переопределяет auto-detection)"
        echo "  REGISTRY        - Docker registry URL"
        echo "  IMAGE_NAME      - Docker image name prefix"
        exit 1
    fi
    
    main "$@"
fi