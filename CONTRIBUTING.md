# Contributing to Enterprise 1C AI Development Stack

Thank you for your interest in contributing! 🎉

## How to Contribute

### Reporting Issues

- Use GitHub Issues
- Provide detailed description
- Include steps to reproduce
- Attach logs if applicable

### Code Contributions

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow code style guidelines
   - Add tests for new features
   - Update documentation

4. **Run tests**
   ```bash
   pytest
   ```

5. **Commit your changes**
   ```bash
   git commit -m "feat: add amazing feature"
   ```
   
   Follow [Conventional Commits](https://www.conventionalcommits.org/)

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request**

## Development Setup

```bash
# Clone repository
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public

# Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh

# Activate virtual environment
source venv/bin/activate

# Install dev dependencies
pip install -r requirements-dev.txt
```

## Code Style

### Python
- **Black** for formatting
- **isort** for imports
- **flake8** for linting
- **mypy** for type checking

```bash
# Format code
black .
isort .

# Check
flake8
mypy .
```

### Java (EDT Plugin)
- Follow Google Java Style Guide
- Use meaningful variable names
- Add JavaDoc comments

### Commit Messages

Format: `<type>(<scope>): <subject>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

Example:
```
feat(parser): add support for BUH configuration
```

## Testing

### Unit Tests
```bash
pytest tests/unit/
```

### Integration Tests
```bash
pytest tests/integration/
```

### Coverage
```bash
pytest --cov=src --cov-report=html
```

## Documentation

- Update README.md if needed
- Add docstrings to functions
- Update architecture.yaml for architectural changes
- Create/update docs in `docs/` folder

### Audit Tooling

Before отправкой изменений, прогоняйте автоматические проверки:

```bash
# Проверка ссылок во всех .md файлах
python check_all_links.py

# Полный аудит (структура, security, README vs code)
python comprehensive_project_audit_final.py
python check_security_comprehensive.py
python check_readme_vs_code.py
```

Отчёты сохраняются в корне проекта (например, `BROKEN_LINKS_REPORT.txt`).

## Pull Request Process

1. Update CHANGELOG.md
2. Ensure all tests pass
3. Update documentation
4. Request review from maintainers
5. Address review comments
6. Merge after approval

## Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Commits follow convention
- [ ] PR description is clear

## Community

- Be respectful
- Be constructive
- Help others
- Share knowledge

## License

By contributing, you agree that your contributions will be licensed under the MIT License.





