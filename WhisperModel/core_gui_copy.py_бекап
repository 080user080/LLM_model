# core_gui.py
"""Графічний інтерфейс голосового асистента"""
import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import queue
import time
from datetime import datetime
import sys
import os

# Додаємо шлях до functions для імпорту конфігурації
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Імпортуємо конфігурацію
try:
    from functions.config import ASSISTANT_NAME, ASSISTANT_EMOJI
    ASSISTANT_TITLE = f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}"
except ImportError:
    ASSISTANT_NAME = "МАРК"
    ASSISTANT_EMOJI = "⚡"
    ASSISTANT_TITLE = f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}"

class AssistantGUI:
    """Головне вікно асистента"""
    
    def __init__(self, assistant_callback):
        self.root = tk.Tk()
        self.root.title(f"Асистент {ASSISTANT_NAME}")
        self.assistant_callback = assistant_callback
        self.message_queue = queue.Queue()
        self.confirmation_callback = None
        self.awaiting_confirmation = False
        self.input_active = False
        self.idle_timeout = 300  # 5 хвилин
        self.last_input_time = time.time()
        
        # Налаштування вікна
        self.root.geometry("600x700")
        self.root.configure(bg='#f0f0f0')
        self.root.resizable(True, True)
        self.root.attributes('-alpha', 0.95)  # Напівпрозорість
        self.root.minsize(450, 550)  # Мінімальний розмір
        
        # Стилі
        self.setup_styles()
        
        # Створення інтерфейсу
        self.create_widgets()
        self.setup_window()
        
        # Запуск обробки черги повідомлень
        self.process_queue()
        
        # Слідкування за активністю
        self.check_idle()
    
    def setup_styles(self):
        """Налаштування стилів"""
        self.style = ttk.Style()
        
        # Темна тема для заголовка
        self.style.configure(
            'Title.TLabel',
            background='#3c3c3c',
            foreground='white',
            font=('Segoe UI', 12, 'bold'),
            padding=10
        )
        
        # Стиль для кнопок
        self.style.configure(
            'Confirm.TButton',
            background='#4CAF50',
            foreground='white',
            font=('Segoe UI', 10, 'bold'),
            padding=10
        )
        
        self.style.configure(
            'Cancel.TButton',
            background='#f44336',
            foreground='white',
            font=('Segoe UI', 10, 'bold'),
            padding=10
        )
        
        self.style.configure(
            'Send.TButton',
            background='#2196F3',
            foreground='white',
            font=('Segoe UI', 12, 'bold'),
            padding=(15, 10)
        )
    
    def create_widgets(self):
        """Створення віджетів інтерфейсу"""
        # Заголовок
        title_frame = ttk.Frame(self.root, style='Title.TLabel')
        title_frame.pack(fill='x', side='top', pady=(0, 5))
        
        title_label = ttk.Label(
            title_frame,
            text=ASSISTANT_TITLE,
            style='Title.TLabel'
        )
        title_label.pack()
        
        # Головний контейнер з прокруткою
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Контейнер для чату
        chat_frame = ttk.Frame(main_container)
        chat_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Історія чату з прокруткою
        self.chat_history = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg='#fafafa',
            fg='#333333',
            state='disabled',
            relief='flat',
            borderwidth=1,
            height=20
        )
        self.chat_history.pack(fill='both', expand=True)
        
        # Фрейм для підтвердження (прихований за замовчуванням)
        self.confirmation_frame = ttk.Frame(main_container)
        
        self.confirmation_label = ttk.Label(
            self.confirmation_frame,
            text="",
            font=('Segoe UI', 10, 'bold'),
            foreground='#d32f2f',
            wraplength=400
        )
        self.confirmation_label.pack(pady=(10, 5))
        
        button_frame = ttk.Frame(self.confirmation_frame)
        button_frame.pack(pady=5)
        
        self.yes_button = ttk.Button(
            button_frame,
            text="ТАК",
            style='Confirm.TButton',
            command=self.on_yes_clicked
        )
        self.yes_button.pack(side='left', padx=10)
        
        self.no_button = ttk.Button(
            button_frame,
            text="НІ",
            style='Cancel.TButton',
            command=self.on_no_clicked
        )
        self.no_button.pack(side='left', padx=10)
        
        # 🔥 ВИПРАВЛЕННЯ: Контейнер для поля вводу
        self.input_container = ttk.Frame(main_container)
        self.input_container.pack(fill='x', side='bottom', pady=(5, 0))
        
        # Фрейм для вводу з grid менеджером
        input_frame = ttk.Frame(self.input_container)
        input_frame.pack(fill='x', expand=True)
        
        # Налаштування grid
        input_frame.columnconfigure(0, weight=1)  # Поле вводу розтягується
        input_frame.columnconfigure(1, weight=0)  # Кнопка фіксована
        
        # Поле вводу
        self.input_text = tk.Text(
            input_frame,
            height=3,
            font=('Segoe UI', 10),
            wrap=tk.WORD,
            bg='white',
            fg='#333333',
            relief='solid',
            borderwidth=1
        )
        self.input_text.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        
        # 🔥 ВИПРАВЛЕННЯ: Збільшена кнопка з іконкою
        self.send_button = ttk.Button(
            input_frame,
            text="➤",  # Символ стрілки вправо
            width=3,
            command=self.send_text_command,
            style='Send.TButton'
        )
        self.send_button.grid(row=0, column=1, sticky='ns')
        
        # Підказка
        self.input_text.insert(1.0, "Введіть команду...")
        self.input_text.configure(fg='#999999')
        
        # 🔥 ВИПРАВЛЕННЯ: Покращена обробка Enter
        self.input_text.bind('<Return>', self.on_enter_pressed)
        self.input_text.bind('<Shift-Return>', self.on_shift_enter)
        self.input_text.bind('<FocusIn>', self.on_input_focus)
        self.input_text.bind('<FocusOut>', self.on_input_blur)
        self.input_text.bind('<Key>', self.on_input_key)
        
        # Статус бар
        self.status_var = tk.StringVar()
        self.status_var.set("✅ Готовий до роботи")
        
        status_bar = ttk.Label(
            main_container,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=('Segoe UI', 9),
            padding=5
        )
        status_bar.pack(fill='x', side='bottom', pady=(5, 0))
    
    def setup_window(self):
        """Налаштування поведінки вікна"""
        # Обробка зміни розміру
        self.root.bind('<Configure>', self.on_resize)
        
        # Встановлюємо фокус на поле вводу
        self.root.after(100, self.focus_input)
    
    def on_resize(self, event=None):
        """Обробка зміни розміру вікна"""
        # Оновлюємо геометрію при зміні розміру
        self.root.update_idletasks()
    
    def focus_input(self):
        """Встановити фокус на поле вводу"""
        self.input_text.focus_set()
    
    def add_message(self, sender, message):
        """Додати повідомлення до чату"""
        self.chat_history.configure(state='normal')
        
        # Додаємо роздільник, якщо це не перше повідомлення
        current_text = self.chat_history.get(1.0, tk.END).strip()
        if current_text:
            self.chat_history.insert(tk.END, "\n" + "-"*50 + "\n")
        
        # Відправник
        if sender == "user":
            prefix = "👑 ВИ: "
            text_color = "#2c3e50"
        else:  # assistant
            prefix = f"{ASSISTANT_TITLE}: "
            text_color = "#2980b9"
        
        # Додаємо повідомлення
        self.chat_history.insert(tk.END, prefix, ('bold',))
        self.chat_history.insert(tk.END, message + "\n")
        
        # Форматування
        self.chat_history.tag_configure('bold', font=('Segoe UI', 10, 'bold'))
        self.chat_history.tag_configure('normal', font=('Segoe UI', 10))
        
        # Прокручуємо до кінця
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')
    
    def on_input_focus(self, event=None):
        """Коли поле вводу отримує фокус"""
        current_text = self.input_text.get(1.0, tk.END).strip()
        if current_text == "Введіть команду...":
            self.input_text.delete(1.0, tk.END)
            self.input_text.configure(fg='#333333')
        
        self.input_active = True
        self.status_var.set("⌨️  Режим вводу тексту - аудіо призупинено")
        
        # Повідомляємо асистента про паузу запису
        if self.assistant_callback:
            self.assistant_callback('pause_listening')
    
    def on_input_blur(self, event=None):
        """Коли поле вводу втрачає фокус"""
        current_text = self.input_text.get(1.0, tk.END).strip()
        if not current_text:
            self.input_text.insert(1.0, "Введіть команду...")
            self.input_text.configure(fg='#999999')
        
        self.input_active = False
        self.last_input_time = time.time()
        
        # Повідомляємо асистента про відновлення запису
        if self.assistant_callback:
            self.assistant_callback('resume_listening')
    
    def on_input_key(self, event=None):
        """Коли натискається клавіша в полі вводу"""
        self.last_input_time = time.time()
    
    def on_enter_pressed(self, event=None):
        """Коли натискається Enter (відправка)"""
        if not self.awaiting_confirmation:
            self.send_text_command()
            return 'break'  # Запобігаємо стандартній поведінці Enter
        return None
    
    def on_shift_enter(self, event=None):
        """Обробка Shift+Enter (новий рядок)"""
        # Вставляємо новий рядок
        self.input_text.insert(tk.INSERT, '\n')
        return 'break'
    
    def send_text_command(self):
        """Відправити текстову команду"""
        command = self.input_text.get(1.0, tk.END).strip()
        
        if not command or command == "Введіть команду...":
            return
        
        # Додаємо команду до чату
        self.add_message("user", command)
        
        # Очищуємо поле вводу
        self.input_text.delete(1.0, tk.END)
        
        # Відправляємо команду асистенту
        if self.assistant_callback:
            self.assistant_callback('process_text', command)
    
    def show_confirmation(self, question, callback):
        """Показати діалог підтвердження"""
        self.awaiting_confirmation = True
        self.confirmation_callback = callback
        
        # Оновлюємо текст питання
        self.confirmation_label.config(text=f"{ASSISTANT_TITLE}: {question}")
        
        # Ховаємо поле вводу, показуємо підтвердження
        self.input_container.pack_forget()
        self.confirmation_frame.pack(fill='x', side='bottom', pady=(5, 0))
        
        # Запускаємо таймер відміни (30 секунд)
        self.confirmation_timer = threading.Timer(30.0, self.on_confirmation_timeout)
        self.confirmation_timer.start()
        
        self.status_var.set("❓ Очікую підтвердження...")
    
    def hide_confirmation(self):
        """Приховати діалог підтвердження"""
        if hasattr(self, 'confirmation_timer'):
            self.confirmation_timer.cancel()
        
        self.awaiting_confirmation = False
        self.confirmation_callback = None
        
        # Ховаємо підтвердження, показуємо поле вводу
        self.confirmation_frame.pack_forget()
        self.input_container.pack(fill='x', side='bottom', pady=(5, 0))
        
        self.status_var.set("✅ Готовий до роботи")
    
    def on_yes_clicked(self):
        """Коли натиснуто ТАК"""
        if self.confirmation_callback:
            self.confirmation_callback(True)
        self.hide_confirmation()
    
    def on_no_clicked(self):
        """Коли натиснуто НІ"""
        if self.confirmation_callback:
            self.confirmation_callback(False)
        self.hide_confirmation()
    
    def on_confirmation_timeout(self):
        """Таймаут підтвердження"""
        if self.awaiting_confirmation:
            self.root.after(0, self.timeout_confirmation)
    
    def timeout_confirmation(self):
        """Обробка таймауту в головному потоці"""
        if self.awaiting_confirmation:
            self.add_message("assistant", "⏰ Час очікування вийшов. Дію скасовано.")
            if self.confirmation_callback:
                self.confirmation_callback(False)
            self.hide_confirmation()
    
    def check_idle(self):
        """Перевірка простою"""
        if self.input_active:
            idle_time = time.time() - self.last_input_time
            if idle_time > self.idle_timeout:
                self.on_input_blur()  # Автоматично втрачаємо фокус
                self.add_message("system", f"⏳ Автоматичне відновлення аудіо через {self.idle_timeout//60} хв бездіяльності")
        
        # Перевіряємо кожну секунду
        self.root.after(1000, self.check_idle)
    
    def process_queue(self):
        """Обробка черги повідомлень з іншого потоку"""
        try:
            while True:
                message = self.message_queue.get_nowait()
                msg_type, data = message
                
                if msg_type == 'add_message':
                    sender, text = data
                    self.root.after(0, self.add_message, sender, text)
                
                elif msg_type == 'show_confirmation':
                    question, callback = data
                    self.root.after(0, self.show_confirmation, question, callback)
                
                elif msg_type == 'update_status':
                    status = data
                    self.root.after(0, self.status_var.set, status)
                
        except queue.Empty:
            pass
        
        # Перевіряємо знову через 100мс
        self.root.after(100, self.process_queue)
    
    def queue_message(self, msg_type, data):
        """Додати повідомлення до черги"""
        self.message_queue.put((msg_type, data))
    
    def run(self):
        """Запустити GUI"""
        self.root.mainloop()

# Функція для запуску в окремому потоці
def run_gui(assistant_callback):
    """Запуск GUI"""
    gui = AssistantGUI(assistant_callback)
    gui.run()