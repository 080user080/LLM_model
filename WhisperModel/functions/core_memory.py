# functions/core_memory.py
"""Менеджер довготривалої пам'яті для агента"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

class MemoryManager:
    """Зберігає та завантажує контекст виконання завдань."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path(__file__).parent / "agent_memory.json"
        self.storage_path = storage_path
        self.memory: Dict[str, Any] = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Завантажити пам'ять із файлу."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        # Базова структура
        return {
            "last_task": None,
            "last_plan": [],
            "last_results": [],
            "variables": {},          # змінні, збережені агентом
            "file_paths": [],         # шляхи до створених/редагованих файлів
            "history": []             # стисла історія дій
        }
    
    def save(self) -> None:
        """Зберегти поточний стан пам'яті."""
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)
    
    def update_task(self, task: str, plan: list, results: list) -> None:
        """Оновити інформацію про останнє виконане завдання."""
        self.memory["last_task"] = task
        self.memory["last_plan"] = plan
        self.memory["last_results"] = results
        self.memory["history"].append({
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "plan": plan,
            "results": results
        })
        # Обмежити історію 20 записами
        if len(self.memory["history"]) > 20:
            self.memory["history"] = self.memory["history"][-20:]
        self.save()
    
    def add_file_path(self, path: str) -> None:
        """Додати шлях до файлу в пам'ять."""
        if path not in self.memory["file_paths"]:
            self.memory["file_paths"].append(path)
            self.save()
    
    def set_variable(self, key: str, value: Any) -> None:
        """Зберегти змінну."""
        self.memory["variables"][key] = value
        self.save()
    
    def get_variable(self, key: str, default=None) -> Any:
        """Отримати збережену змінну."""
        return self.memory["variables"].get(key, default)
    
    def get_last_files(self, extension: Optional[str] = None) -> list:
        """Повернути список останніх файлів (опціонально фільтрувати за розширенням)."""
        files = self.memory["file_paths"]
        if extension:
            return [f for f in files if f.endswith(extension)]
        return files
    
    def clear_memory(self) -> None:
        """Очистити всю пам'ять (обережно)."""
        self.memory = {
            "last_task": None,
            "last_plan": [],
            "last_results": [],
            "variables": {},
            "file_paths": [],
            "history": []
        }
        self.save()