"""
Diagnostic Middleware - автоматически логирует проблемы при старте
Встраивается в приложение и показывает, что потребляет память
"""

import os
import sys
import time
import logging
import socket

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[DIAGNOSTIC] %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

class StartupDiagnostics:
    """Класс для диагностики запуска приложения"""
    
    def __init__(self):
        self.start_time = time.time()
        self.checkpoints = []
        self.start_memory = self._get_memory_mb()
        
    def _get_memory_mb(self):
        """Получить использование памяти в MB"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # psutil не установлен
            return 0
    
    def checkpoint(self, name):
        """Записать контрольную точку"""
        elapsed = time.time() - self.start_time
        memory = self._get_memory_mb()
        memory_delta = memory - self.start_memory
        
        self.checkpoints.append({
            'name': name,
            'time': elapsed,
            'memory': memory,
            'delta': memory_delta
        })
        
        # Логируем сразу
        status = "OK"
        if elapsed > 10:
            status = "SLOW"
        if memory > 400:
            status = "HIGH_MEMORY"
            
        logger.info(f"[{status}] {name:40} | {elapsed:6.2f}s | {memory:7.1f} MB | +{memory_delta:6.1f} MB")
        
        # Предупреждения
        if elapsed > 20:
            logger.warning(f"⚠️  Checkpoint '{name}' took {elapsed:.1f}s - approaching timeout!")
        if memory > 400:
            logger.warning(f"⚠️  Memory usage {memory:.0f} MB - approaching 512 MB limit!")
    
    def print_summary(self):
        """Вывести итоговую сводку"""
        total_time = time.time() - self.start_time
        final_memory = self._get_memory_mb()
        
        logger.info("=" * 80)
        logger.info("DIAGNOSTIC SUMMARY:")
        logger.info(f"  Total startup time: {total_time:.2f}s")
        logger.info(f"  Final memory: {final_memory:.1f} MB")
        logger.info(f"  Memory growth: +{final_memory - self.start_memory:.1f} MB")
        logger.info("=" * 80)
        
        # Критические проблемы
        if total_time > 30:
            logger.error("🚨 CRITICAL: Startup time > 30s - will cause worker timeout!")
            logger.error("    Solution: Ensure gunicorn timeout is set to 300s")
        
        if final_memory > 450:
            logger.error("🚨 CRITICAL: Memory > 450 MB - may cause OOM on free tier!")
            logger.error("    Solution: Optimize imports or upgrade plan")

# Глобальный экземпляр
_diagnostics = None

def start_diagnostics():
    """Начать диагностику"""
    global _diagnostics
    if os.environ.get('RENDER') or os.environ.get('ENABLE_DIAGNOSTICS'):
        logger.info("=" * 80)
        logger.info("🔍 STARTUP DIAGNOSTICS ENABLED")
        logger.info(f"   Python: {sys.version}")
        logger.info(f"   Platform: {sys.platform}")
        logger.info(f"   PID: {os.getpid()}")
        logger.info(f"   DATABASE_URL: {'Set' if os.environ.get('DATABASE_URL') else 'Not Set'}")
        logger.info("=" * 80)
        _diagnostics = StartupDiagnostics()
        _diagnostics.checkpoint("Diagnostics initialized")
    return _diagnostics

def checkpoint(name):
    """Записать контрольную точку"""
    if _diagnostics:
        _diagnostics.checkpoint(name)

def finish_diagnostics():
    """Завершить диагностику"""
    if _diagnostics:
        _diagnostics.print_summary()

