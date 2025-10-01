"""
Circuit Breaker для qBittorrent подключений.
Предотвращает зависание сайта при недоступности qBittorrent сервера.
"""

import time
import logging
from threading import Lock
from enum import Enum
from typing import Optional, Callable, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Состояния Circuit Breaker"""
    CLOSED = "closed"      # Всё работает, запросы проходят
    OPEN = "open"          # Сервер недоступен, запросы блокируются
    HALF_OPEN = "half_open"  # Пробуем восстановить соединение


class QBittorrentCircuitBreaker:
    """
    Circuit Breaker для qBittorrent соединений.
    
    Состояния:
    - CLOSED: Нормальная работа, все запросы проходят
    - OPEN: После нескольких ошибок переходим в режим "недоступен"
    - HALF_OPEN: Периодически проверяем восстановление
    
    Параметры:
    - failure_threshold: Количество ошибок для открытия circuit (default: 3)
    - timeout: Время в секундах до попытки восстановления (default: 60)
    - success_threshold: Количество успехов для закрытия circuit (default: 2)
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        timeout: float = 60.0,
        success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.lock = Lock()
        
        logger.info(
            f"Circuit Breaker initialized: "
            f"failures={failure_threshold}, timeout={timeout}s, "
            f"successes={success_threshold}"
        )
    
    def is_available(self) -> bool:
        """Проверяет доступен ли qBittorrent для запросов"""
        with self.lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                # Проверяем не пора ли перейти в HALF_OPEN
                if self.last_failure_time and \
                   time.time() - self.last_failure_time >= self.timeout:
                    logger.info("Circuit Breaker: Переход в HALF_OPEN, пробуем восстановить")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    return True
                return False
            
            # HALF_OPEN - пропускаем запросы для проверки
            return True
    
    def record_success(self):
        """Записывает успешный запрос"""
        with self.lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.info(
                    f"Circuit Breaker: Успех в HALF_OPEN "
                    f"({self.success_count}/{self.success_threshold})"
                )
                
                if self.success_count >= self.success_threshold:
                    logger.info("Circuit Breaker: Переход в CLOSED, qBittorrent восстановлен!")
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
            elif self.state == CircuitState.OPEN:
                # Неожиданный успех в OPEN - закрываем сразу
                logger.info("Circuit Breaker: Неожиданный успех в OPEN, переход в CLOSED")
                self.state = CircuitState.CLOSED
    
    def record_failure(self):
        """Записывает неудачный запрос"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            self.success_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                logger.warning("Circuit Breaker: Ошибка в HALF_OPEN, переход в OPEN")
                self.state = CircuitState.OPEN
                self.failure_count = 0
            elif self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit Breaker: Достигнут порог ошибок "
                    f"({self.failure_count}), переход в OPEN"
                )
                self.state = CircuitState.OPEN
                self.failure_count = 0
    
    def get_state(self) -> dict:
        """Возвращает текущее состояние для API"""
        with self.lock:
            return {
                "state": self.state.value,
                "available": self.state != CircuitState.OPEN,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "last_failure_time": self.last_failure_time,
                "retry_in": (
                    max(0, self.timeout - (time.time() - self.last_failure_time))
                    if self.last_failure_time and self.state == CircuitState.OPEN
                    else 0
                )
            }
    
    def reset(self):
        """Сброс в исходное состояние"""
        with self.lock:
            logger.info("Circuit Breaker: Ручной сброс")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
    
    @contextmanager
    def call(self, fallback_value: Any = None):
        """
        Context manager для выполнения операций с qBittorrent.
        
        Usage:
            with circuit_breaker.call(fallback_value={}) as execute:
                if execute:
                    result = qbt_client.torrents_info()
                    yield result
                else:
                    yield fallback_value
        """
        if not self.is_available():
            logger.debug("Circuit Breaker: Запрос заблокирован (OPEN)")
            yield False
            return
        
        try:
            yield True
            self.record_success()
        except Exception as e:
            logger.error(f"Circuit Breaker: Ошибка запроса - {e}")
            self.record_failure()
            raise


# Глобальный экземпляр Circuit Breaker
_circuit_breaker: Optional[QBittorrentCircuitBreaker] = None
_breaker_lock = Lock()


def get_circuit_breaker() -> QBittorrentCircuitBreaker:
    """Получить глобальный экземпляр Circuit Breaker (singleton)"""
    global _circuit_breaker
    
    if _circuit_breaker is None:
        with _breaker_lock:
            if _circuit_breaker is None:
                _circuit_breaker = QBittorrentCircuitBreaker(
                    failure_threshold=2,    # 2 ошибки подряд
                    timeout=60.0,           # Проверка через 60 секунд
                    success_threshold=2     # 2 успеха для восстановления
                )
    
    return _circuit_breaker


def reset_circuit_breaker():
    """Сбросить Circuit Breaker (для тестирования или ручного управления)"""
    breaker = get_circuit_breaker()
    breaker.reset()

