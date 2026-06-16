
#!/usr/bin/env python3
"""
Model Security Scanner
Сканирует AI модели на вредоносный код и уязвимости
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelSecurityScanner:
    """Сканер безопасности для AI моделей"""
    
    def __init__(self, output_dir: str = "./security-reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        self.scan_results = []
        self.issues_found = False
    
    def check_modelscan_installed(self) -> bool:
        """Проверка установки modelscan"""
        try:
            result = subprocess.run(
                ["modelscan", "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info(f"✓ modelscan installed: {result.stdout.strip()}")
                return True
            else:
                return False
                
        except FileNotFoundError:
            return False
    
    def install_modelscan(self):
        """Установка modelscan"""
        logger.info("Installing modelscan...")
        
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "modelscan"],
                check=True,
                capture_output=True
            )
            logger.info("✓ modelscan installed successfully")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install modelscan: {e}")
            raise
    
    def scan_model(self, model_path: Path) -> Dict:
        """
        Сканирование одной модели
        
        Args:
            model_path: Путь к файлу модели
        
        Returns:
            Dict с результатами сканирования
        """
        logger.info(f"Scanning: {model_path}")
        
        result = {
            "path": str(model_path),
            "filename": model_path.name,
            "size_mb": model_path.stat().st_size / (1024 * 1024),
            "scan_time": datetime.utcnow().isoformat(),
            "status": "unknown",
            "issues": [],
        }
        
        try:
            # Запускаем modelscan
            scan_output = subprocess.run(
                ["modelscan", "-p", str(model_path), "-o", "/dev/stdout"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if scan_output.returncode == 0:
                result["status"] = "safe"
                result["scan_output"] = scan_output.stdout
                logger.info(f"  ✓ Safe: {model_path.name}")
            else:
                result["status"] = "unsafe"
                result["issues"] = self._parse_issues(scan_output.stderr)
                self.issues_found = True
                logger.error(f"  ⚠️ UNSAFE: {model_path.name}")
                logger.error(f"  Issues: {result['issues']}")
        
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"  ❌ Error scanning {model_path.name}: {e}")
        
        self.scan_results.append(result)
        return result
    
    def _parse_issues(self, stderr: str) -> List[str]:
        """Парсинг issues из вывода modelscan"""
        issues = []
        
        # Modelscan выводит issues в stderr
        for line in stderr.split('\n'):
            if 'ISSUE' in line.upper() or 'WARNING' in line.upper():
                issues.append(line.strip())
        
        return issues if issues else ["Unknown security issue detected"]
    
    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Сканирование директории с моделями
        
        Args:
            directory: Директория для сканирования
            recursive: Рекурсивное сканирование
            extensions: Список расширений файлов для сканирования
        
        Returns:
            Список результатов сканирования
        """
        if extensions is None:
            extensions = ['.pt', '.pth', '.bin', '.safetensors', '.h5', '.pkl', '.joblib']
        
        logger.info(f"Scanning directory: {directory}")
        logger.info(f"  Recursive: {recursive}")
        logger.info(f"  Extensions: {extensions}")
        
        model_files = []
        
        # Поиск файлов моделей
        if recursive:
            for ext in extensions:
                model_files.extend(directory.rglob(f"*{ext}"))
        else:
            for ext in extensions:
                model_files.extend(directory.glob(f"*{ext}"))
        
        logger.info(f"Found {len(model_files)} model files")
        
        # Сканируем каждую модель
        results = []
        for model_file in model_files:
            result = self.scan_model(model_file)
            results.append(result)
        
        return results
    
    def generate_report(self) -> Dict:
        """Генерация итогового отчета"""
        
        total = len(self.scan_results)
        safe = sum(1 for r in self.scan_results if r['status'] == 'safe')
        unsafe = sum(1 for r in self.scan_results if r['status'] == 'unsafe')
        errors = sum(1 for r in self.scan_results if r['status'] == 'error')
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_scanned": total,
                "safe": safe,
                "unsafe": unsafe,
                "errors": errors,
                "overall_status": "PASS" if unsafe == 0 else "FAIL"
            },
            "results": self.scan_results
        }
        
        # Сохраняем JSON отчет
        report_file = self.output_dir / f"scan_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved: {report_file}")
        
        # Генерируем Markdown отчет
        self._generate_markdown_report(report)
        
        return report
    
    def _generate_markdown_report(self, report: Dict):
        """Генерация Markdown отчета"""
        
        md_file = self.output_dir / "SECURITY_REPORT.md"
        
        summary = report['summary']
        
        with open(md_file, 'w') as f:
            f.write("# Model Security Scan Report\n\n")
            f.write(f"**Date:** {report['timestamp']}\n\n")
            f.write(f"**Status:** {'✅ PASS' if summary['overall_status'] == 'PASS' else '⚠️ FAIL'}\n\n")
            
            f.write("## Summary\n\n")
            f.write(f"- **Total scanned:** {summary['total_scanned']}\n")
            f.write(f"- **Safe:** {summary['safe']} ✅\n")
            f.write(f"- **Unsafe:** {summary['unsafe']} ⚠️\n")
            f.write(f"- **Errors:** {summary['errors']} ❌\n\n")
            
            f.write("## Scan Results\n\n")
            
            for result in report['results']:
                status_icon = {
                    'safe': '✅',
                    'unsafe': '⚠️',
                    'error': '❌',
                    'unknown': '❓'
                }.get(result['status'], '❓')
                
                f.write(f"### {status_icon} {result['filename']}\n\n")
                f.write(f"- **Path:** `{result['path']}`\n")
                f.write(f"- **Size:** {result['size_mb']:.2f} MB\n")
                f.write(f"- **Status:** {result['status'].upper()}\n")
                
                if result.get('issues'):
                    f.write(f"- **Issues:**\n")
                    for issue in result['issues']:
                        f.write(f"  - {issue}\n")
                
                f.write("\n")
            
            f.write("## Recommendations\n\n")
            
            if summary['unsafe'] > 0:
                f.write("⚠️ **CRITICAL:** Unsafe models detected!\n\n")
                f.write("**Action required:**\n\n")
                f.write("1. Remove or quarantine unsafe model files\n")
                f.write("2. Verify model download sources\n")
                f.write("3. Check for unauthorized modifications\n")
                f.write("4. Re-scan after remediation\n\n")
            
            f.write("**General best practices:**\n\n")
            f.write("- ✅ Only download models from verified sources (HuggingFace verified, official repos)\n")
            f.write("- ✅ Verify model checksums/signatures before use\n")
            f.write("- ✅ Run models in isolated Docker containers\n")
            f.write("- ✅ Monitor outbound network connections from model processes\n")
            f.write("- ✅ Keep model scanning tools up to date\n")
            f.write("- ✅ Regularly scan models (weekly or on updates)\n")
        
        logger.info(f"Markdown report saved: {md_file}")


def main():
    """Главная функция"""
    
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║  Model Security Scanner                                    ║
    ║  Сканирование AI моделей на безопасность                   ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    scanner = ModelSecurityScanner()
    
    # Проверяем/устанавливаем modelscan
    if not scanner.check_modelscan_installed():
        logger.info("modelscan not found, installing...")
        scanner.install_modelscan()
    
    # Директории для сканирования
    directories_to_scan = [
        Path("./models"),
        Path.home() / ".cache" / "huggingface" / "hub",
    ]
    
    # Сканируем каждую директорию
    for directory in directories_to_scan:
        if directory.exists():
            logger.info(f"\nScanning directory: {directory}")
            scanner.scan_directory(directory, recursive=True)
        else:
            logger.warning(f"Directory not found: {directory}")
    
    # Генерируем отчет
    report = scanner.generate_report()
    
    # Выводим summary
    print("\n" + "="*60)
    print("SCAN COMPLETE")
    print("="*60)
    print(f"Total scanned: {report['summary']['total_scanned']}")
    print(f"Safe: {report['summary']['safe']} ✅")
    print(f"Unsafe: {report['summary']['unsafe']} ⚠️")
    print(f"Errors: {report['summary']['errors']} ❌")
    print(f"\nOverall status: {report['summary']['overall_status']}")
    print("="*60)
    
    # Exit code
    if scanner.issues_found:
        logger.error("⚠️ Security issues found!")
        sys.exit(1)
    else:
        logger.info("✅ All models are safe")
        sys.exit(0)


if __name__ == "__main__":
    main()





