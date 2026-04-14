# functions/core_executor.py
"""Менеджер виконання завдань у фоновому потоці з оновленням GUI"""
import threading
import time
from typing import Callable, Optional

class TaskExecutor:
    """Керує виконанням тривалих завдань (планів) у фоновому режимі."""
    
    def __init__(self, gui_callback: Optional[Callable] = None):
        self.gui_callback = gui_callback
        self.current_task_thread = None
        self.is_running = False
        self.progress = 0  # 0-100
        self.status = "Готовий"
        self._stop_requested = False
    
    def execute_plan_async(self, plan: list, execute_fn: Callable, on_complete: Optional[Callable] = None):
        """Запустити виконання плану в окремому потоці."""
        if self.is_running:
            if self.gui_callback:
                self.gui_callback('update_status', '⚠️ Вже виконується завдання')
            return
        
        self.is_running = True
        self._stop_requested = False
        self.progress = 0
        self.status = "Виконання плану..."
        self._notify_progress()
        self._notify_execution_started()
        
        def task_wrapper():
            results = []
            total_steps = len(plan)
            for i, step in enumerate(plan, 1):
                if self._stop_requested:
                    break
                self.progress = int((i / total_steps) * 100)
                self.status = f"Крок {i}/{total_steps}: {step.get('action', '')}"
                self._notify_progress()
                
                try:
                    # Виконання окремого кроку
                    # execute_fn очікує (action, args) або словник
                    result = execute_fn(step)
                    results.append(result)
                except Exception as e:
                    results.append((step.get('action'), 'error', str(e)))
                    self.status = f"Помилка на кроці {i}"
                    self._notify_progress()
                    break
                time.sleep(0.2)  # невелика пауза між кроками для стабільності GUI
            
            self.is_running = False
            self.status = "Виконано"
            self._notify_progress()
            self._notify_execution_finished()
            if on_complete:
                on_complete(results)
        
        self.current_task_thread = threading.Thread(target=task_wrapper, daemon=True)
        self.current_task_thread.start()
    
    def _notify_progress(self):
        """Відправити оновлення прогресу в GUI."""
        if self.gui_callback:
            self.gui_callback('update_progress', (self.progress, self.status))
    
    def _notify_execution_started(self):
        if self.gui_callback:
            self.gui_callback('execution_started', None)
    
    def _notify_execution_finished(self):
        if self.gui_callback:
            self.gui_callback('execution_finished', None)
    
    def stop(self):
        """Запросить остановку текущего выполнения."""
        self._stop_requested = True