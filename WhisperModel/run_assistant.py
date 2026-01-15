# run_assistant.py
"""Запуск асистента з GUI"""
import threading
import time
import queue
import sys
import os
from pathlib import Path

# Додаємо шляхи для імпорту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Імпортуємо GUI
from core_gui import AssistantGUI
from main import AssistantCore

class AssistantApp:
    def __init__(self):
        self.gui_queue = queue.Queue()
        self.core = None
        self.gui = None
        self.is_running = True
        
    def gui_callback(self, action, data=None):
        """Callback для GUI"""
        if not self.core:
            return
        
        if action == 'pause_listening':
            self.core.pause_listening()
        elif action == 'resume_listening':
            self.core.resume_listening()
        elif action == 'process_text':
            self.core.process_text_command(data)
        elif action == 'add_message':
            sender, text = data
            # Це повідомлення вже обробляється в core
            pass
    
    def run_gui(self):
        """Запустити GUI"""
        self.gui = AssistantGUI(self.gui_callback)
        
        # Передаємо чергу в GUI для отримання повідомлень від core
        self.gui.message_queue = self.gui_queue
        self.gui.run()
    
    def process_gui_queue(self):
        """Обробляти повідомлення з черги GUI"""
        try:
            while True:
                msg_type, data = self.gui_queue.get_nowait()
                
                if self.gui:
                    # Передаємо повідомлення в GUI
                    if msg_type == 'add_message':
                        self.gui.queue_message('add_message', data)
                    elif msg_type == 'show_confirmation':
                        self.gui.queue_message('show_confirmation', data)
                    elif msg_type == 'update_status':
                        self.gui.queue_message('update_status', data)
                    
        except queue.Empty:
            pass
        
        # Перевіряємо знову через 100мс
        threading.Timer(0.1, self.process_gui_queue).start()
    
    def start(self):
        """Запустити додаток"""
        print("🚀 Запуск асистента МАРК з GUI...")
        
        # Створюємо ядро асистента
        self.core = AssistantCore(gui_queue=self.gui_queue)
        
        # Запускаємо потік для обробки черги GUI
        threading.Thread(target=self.process_gui_queue, daemon=True).start()
        
        # Даємо трохи часу на ініціалізацію
        time.sleep(1)
        
        # Запускаємо GUI в окремому потоці
        gui_thread = threading.Thread(target=self.run_gui, daemon=True)
        gui_thread.start()
        
        # Чекаємо, поки GUI запуститься
        time.sleep(2)
        
        print("✅ GUI запущено. Запускаю ядро асистента...")
        
        try:
            # Запускаємо ядро асистента в головному потоці
            self.core.run()
            
        except KeyboardInterrupt:
            print("\n👋 Завершення роботи...")
            self.is_running = False
            
        except Exception as e:
            print(f"❌ Помилка: {e}")
            import traceback
            traceback.print_exc()
            self.is_running = False
    
    def stop(self):
        """Зупинити додаток"""
        self.is_running = False
        if self.core:
            self.core.stop()
        print("👋 Додаток зупинено")

if __name__ == "__main__":
    app = AssistantApp()
    
    try:
        app.start()
    except KeyboardInterrupt:
        print("\n\n👋 Завершення роботи...")
        app.stop()
    except Exception as e:
        print(f"\n\n❌ Критична помилка: {e}")
        import traceback
        traceback.print_exc()
        app.stop()