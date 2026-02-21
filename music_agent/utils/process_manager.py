"""
Process Manager - управление внешними процессами с поддержкой отмены
"""
import logging
import asyncio
import subprocess
import signal
import sys
import uuid
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProcessTask:
    """Задача процесса"""
    id: str
    command: list
    operation: str  # translate, cover, process, publish
    target_id: str  # album_id или song_id
    process: Optional[subprocess.Popen] = None
    status: str = "pending"  # pending, running, completed, cancelled, error
    progress: int = 0
    message: str = ""
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    callbacks: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "operation": self.operation,
            "target_id": self.target_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ProcessManager:
    """
    Менеджер процессов с поддержкой:
    - Запуска задач в фоне
    - Real-time прогресса
    - Отмены (cancellation)
    - Мониторинга статуса
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.tasks: Dict[str, ProcessTask] = {}
        self._progress_callbacks: Dict[str, list] = {}
        self._lock = asyncio.Lock()
        self._initialized = True
        
        logger.info("ProcessManager initialized")
    
    async def start_task(
        self,
        command: list,
        operation: str,
        target_id: str,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        on_progress: Optional[Callable[[ProcessTask], Any]] = None
    ) -> ProcessTask:
        """
        Запустить новую задачу
        
        Args:
            command: Команда для запуска ["python", "-m", ...]
            operation: Тип операции (translate, cover, process, publish)
            target_id: ID цели (album_id)
            cwd: Рабочая директория
            env: Переменные окружения
            on_progress: Callback для прогресса
        """
        task_id = f"{operation}_{target_id}_{uuid.uuid4().hex[:8]}"
        
        task = ProcessTask(
            id=task_id,
            command=command,
            operation=operation,
            target_id=target_id
        )
        
        if on_progress:
            task.callbacks.append(on_progress)
        
        async with self._lock:
            self.tasks[task_id] = task
        
        # Запускаем в фоне
        asyncio.create_task(self._run_task(task, cwd, env))
        
        logger.info(f"Started task {task_id}: {operation} for {target_id}")
        return task
    
    async def _run_task(
        self,
        task: ProcessTask,
        cwd: Optional[str] = None,
        env: Optional[dict] = None
    ):
        """Выполнить задачу с отслеживанием прогресса"""
        task.status = "running"
        task.message = "Starting..."
        await self._notify_progress(task)
        
        try:
            # Создаём процесс
            process = subprocess.Popen(
                task.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
                env={**dict(subprocess.os.environ), **(env or {})},
                # Для Windows нужен флаг CREATE_NEW_PROCESS_GROUP
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            
            task.process = process
            
            # Читаем вывод в реальном времени
            stdout_lines = []
            stderr_lines = []
            
            # Асинхронное чтение stdout
            async def read_stdout():
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line = line.strip()
                    stdout_lines.append(line)
                    await self._parse_progress(task, line)
            
            # Асинхронное чтение stderr
            async def read_stderr():
                while True:
                    line = process.stderr.readline()
                    if not line:
                        break
                    stderr_lines.append(line.strip())
            
            # Запускаем чтение
            await asyncio.gather(
                read_stdout(),
                read_stderr(),
                # Периодическая проверка статуса
                self._monitor_task(task)
            )
            
            # Ждём завершения
            return_code = process.wait()
            
            if task.status == "cancelled":
                task.message = "Cancelled by user"
            elif return_code == 0:
                task.status = "completed"
                task.progress = 100
                task.result = "\n".join(stdout_lines)
                task.message = "Completed successfully"
            else:
                task.status = "error"
                task.error = "\n".join(stderr_lines[-10:])  # Последние 10 строк ошибок
                task.message = f"Failed with code {return_code}"
            
        except Exception as e:
            logger.error(f"Task {task.id} error: {e}")
            task.status = "error"
            task.error = str(e)
            task.message = f"Error: {str(e)}"
        
        finally:
            task.completed_at = datetime.now()
            if task.process and task.process.poll() is None:
                task.process.kill()
            await self._notify_progress(task)
    
    async def _monitor_task(self, task: ProcessTask):
        """Мониторинг задачи с проверкой отмены"""
        while task.status == "running":
            await asyncio.sleep(0.5)
            
            # Проверяем, не отменена ли задача
            if task.status == "cancelled":
                break
            
            # Обновляем прогресс (симуляция если нет реального)
            if task.progress < 95:
                task.progress = min(95, task.progress + 5)
                await self._notify_progress(task)
    
    async def _parse_progress(self, task: ProcessTask, line: str):
        """Парсинг прогресса из вывода процесса"""
        # Паттерны для разных операций
        patterns = {
            "translate": ["Translating", "Processing", "Saving"],
            "cover": ["Analyzing", "Generating prompt", "Generating image", "Processing"],
            "process": ["Processing track", "Normalizing", "Applying fade", "Writing metadata"],
            "publish": ["Connecting", "Uploading", "Submitting"]
        }
        
        patterns_list = patterns.get(task.operation, [])
        
        for i, pattern in enumerate(patterns_list):
            if pattern.lower() in line.lower():
                task.progress = int((i / len(patterns_list)) * 100)
                task.message = line[:100]
                await self._notify_progress(task)
                break
    
    async def _notify_progress(self, task: ProcessTask):
        """Уведомить всех подписчиков о прогрессе"""
        for callback in task.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task)
                else:
                    callback(task)
            except Exception as e:
                logger.error(f"Callback error for task {task.id}: {e}")
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Отменить задачу
        
        Returns:
            True если задача была отменена, False если не найдена или уже завершена
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status in ["completed", "error", "cancelled"]:
            return False
        
        task.status = "cancelled"
        task.message = "Cancelling..."
        
        if task.process and task.process.poll() is None:
            try:
                # Отправляем сигнал прерывания
                if sys.platform == 'win32':
                    # Windows: CTRL_BREAK_EVENT
                    task.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    # Unix: SIGTERM, затем SIGKILL
                    task.process.terminate()
                
                # Даём время на graceful shutdown
                await asyncio.sleep(1)
                
                # Если всё ещё работает - убиваем
                if task.process.poll() is None:
                    task.process.kill()
                    
            except Exception as e:
                logger.error(f"Error cancelling task {task_id}: {e}")
        
        task.completed_at = datetime.now()
        await self._notify_progress(task)
        
        logger.info(f"Cancelled task {task_id}")
        return True
    
    def get_task(self, task_id: str) -> Optional[ProcessTask]:
        """Получить задачу по ID"""
        return self.tasks.get(task_id)
    
    def get_active_tasks(self) -> Dict[str, ProcessTask]:
        """Получить все активные задачи"""
        return {
            k: v for k, v in self.tasks.items()
            if v.status == "running"
        }
    
    def get_tasks_for_target(self, target_id: str) -> list:
        """Получить все задачи для конкретной цели"""
        return [
            task for task in self.tasks.values()
            if task.target_id == target_id
        ]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Очистить старые завершённые задачи"""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = [
            task_id for task_id, task in self.tasks.items()
            if task.status in ["completed", "error", "cancelled"]
            and task.completed_at
            and task.completed_at < cutoff
        ]
        
        for task_id in to_remove:
            del self.tasks[task_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")


# Глобальный экземпляр
process_manager = ProcessManager()
