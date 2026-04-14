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
        self.root.geometry("500x400")
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
        
        # Стиль для кнопок подтверждения
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
            background='#000000',
            foreground='white',
            font=('Segoe UI', 12, 'bold'),
            padding=(15, 10)
        )
        
        self.style.configure(
            'Stop.TButton',
            background='#000000',
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
        
        # Включаємо стандартне копіювання Ctrl+C - ВИПРАВЛЕНО
        self.chat_history.bind('<Control-c>', self.copy_chat_selection)
        self.chat_history.bind('<Control-C>', self.copy_chat_selection)
        
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
        
        # Контейнер для поля вводу
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
        
        # Кнопка відправки
        self.send_button = ttk.Button(
            input_frame,
            text="➤",
            width=3,
            command=self.send_text_command,
            style='Send.TButton'
        )
        self.send_button.grid(row=0, column=1, sticky='ns')
        
        # Кнопка «Стоп» (изначально скрыта)
        self.stop_button = ttk.Button(
            input_frame,
            text="⬛ СТОП",
            command=self.stop_execution,
            style='Stop.TButton'
        )
        # Будет показана при выполнении задачи
        
        # Підказка
        self.input_text.insert(1.0, "Введіть команду...")
        self.input_text.configure(fg='#999999')
        
        # Обробка клавіш
        self.input_text.bind('<Return>', self.on_enter_pressed)
        self.input_text.bind('<Shift-Return>', self.on_shift_enter)
        self.input_text.bind('<FocusIn>', self.on_input_focus)
        self.input_text.bind('<FocusOut>', self.on_input_blur)
        self.input_text.bind('<Key>', self.on_input_key)
        # Привязка для остановки (Esc)
        self.root.bind('<Escape>', lambda e: self.stop_execution())
        self.root.bind('<Control-c>', lambda e: self.stop_execution())
        
        # Копіювання/вставка для поля вводу - ВИПРАВЛЕНО
        self.input_text.bind('<Control-c>', self.copy_input_text)
        self.input_text.bind('<Control-C>', self.copy_input_text)
        self.input_text.bind('<Control-v>', self.paste_input_text)
        self.input_text.bind('<Control-V>', self.paste_input_text)
        self.input_text.bind('<<Paste>>', self.paste_input_text)
        self.input_text.bind('<Control-x>', self.cut_input_text)
        self.input_text.bind('<Control-X>', self.cut_input_text)
        
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
        
        # Прогрес-бар (прихований за замовчуванням)
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(
            main_container,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill='x', side='bottom', pady=(2, 0))
        self.progress_bar.pack_forget()  # приховати спочатку
        
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
        
        # Прогрес-бар (прихований за замовчуванням)
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(
            main_container,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill='x', side='bottom', pady=(2, 0))
        self.progress_bar.pack_forget()  # приховати спочатку
    
    def setup_window(self):
        """Налаштування поведінки вікна"""
        self.root.bind('<Configure>', self.on_resize)
        self.root.after(100, self.focus_input)
    
    def on_resize(self, event=None):
        """Обробка зміни розміру вікна"""
        self.root.update_idletasks()
    
    def focus_input(self):
        """Встановити фокус на поле вводу"""
        self.input_text.focus_set()
    
    def add_message(self, sender, message):
        """Додати повідомлення до чату"""
        # Захист від None
        if message is None:
            message = ""
        # Захист від випадкової передачі кортежу
        if isinstance(message, (tuple, list)):
            message = " ".join(str(item) for item in message)
        
        self.chat_history.configure(state='normal')
        
        # Очищаємо подвійні префікси
        if sender == "assistant":
            prefixes_to_remove = [
                f"{ASSISTANT_TITLE}: ",
                f"{ASSISTANT_EMOJI} {ASSISTANT_NAME}: ",
                "⚡ МАРК: ",
                "МАРК: "
            ]
            for prefix in prefixes_to_remove:
                if message.startswith(prefix):
                    message = message[len(prefix):].strip()
                    break
        
        # Додаємо роздільник
        current_text = self.chat_history.get(1.0, tk.END).strip()
        if current_text:
            self.chat_history.insert(tk.END, "\n" + "-"*50 + "\n")
        
        # Відправник
        if sender == "user":
            prefix = "👑 ВИ: "
        else:
            prefix = f"{ASSISTANT_TITLE}: "
        
        self.chat_history.insert(tk.END, prefix, ('bold',))
        self.chat_history.insert(tk.END, message + "\n")
        
        # Форматування
        self.chat_history.tag_configure('bold', font=('Segoe UI', 10, 'bold'))
        
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
        
        if self.assistant_callback:
            self.assistant_callback('resume_listening')
    
    def on_input_key(self, event=None):
        """Коли натискається клавіша"""
        self.last_input_time = time.time()
    
    def on_enter_pressed(self, event=None):
        """Обробка Enter"""
        if not self.awaiting_confirmation:
            self.send_text_command()
            return 'break'
        return None
    
    def on_shift_enter(self, event=None):
        """Обробка Shift+Enter"""
        self.input_text.insert(tk.INSERT, '\n')
        return 'break'
    
    def copy_chat_selection(self, event=None):
        """Копіювати виділений текст з історії чату - ВИПРАВЛЕНО"""
        try:
            # Отримуємо виділений текст
            selected_text = self.chat_history.get(tk.SEL_FIRST, tk.SEL_LAST)
            
            if selected_text:
                # Очищаємо буфер обміну
                self.root.clipboard_clear()
                
                # Додаємо текст до буфера
                self.root.clipboard_append(selected_text)
                
                # Додатково використовуємо низькорівневий метод для Windows
                try:
                    self.root.tk.call('clipboard', 'append', selected_text)
                except:
                    pass
                
                # Оновлюємо буфер обміну
                self.root.update()
                
                # Статус для налагодження
                print(f"📋 Скопійовано з чату: {len(selected_text)} символів")
                return 'break'
        except (tk.TclError, AttributeError):
            # Якщо нічого не виділено або інша помилка
            pass
        return None
    
    def copy_input_text(self, event=None):
        """Копіювати текст з поля вводу - ВИПРАВЛЕНО"""
        try:
            # Перевіряємо, чи є виділений текст
            if self.input_text.tag_ranges(tk.SEL):
                # Отримуємо виділений текст
                selected_text = self.input_text.get(tk.SEL_FIRST, tk.SEL_LAST)
                
                if selected_text:
                    # Очищаємо буфер обміну
                    self.root.clipboard_clear()
                    
                    # Додаємо текст до буфера
                    self.root.clipboard_append(selected_text)
                    
                    # Додатково використовуємо низькорівневий метод для Windows
                    try:
                        self.root.tk.call('clipboard', 'append', selected_text)
                    except:
                        pass
                    
                    # Оновлюємо буфер обміну
                    self.root.update()
                    
                    print(f"📋 Скопійовано з вводу: {len(selected_text)} символів")
                    return 'break'
        except (tk.TclError, AttributeError):
            # Якщо нічого не виділено або інша помилка
            pass
        return None
    
    def cut_input_text(self, event=None):
        """Вирізати текст з поля вводу - ВИПРАВЛЕНО"""
        try:
            # Перевіряємо, чи є виділений текст
            if self.input_text.tag_ranges(tk.SEL):
                # Отримуємо виділений текст
                selected_text = self.input_text.get(tk.SEL_FIRST, tk.SEL_LAST)
                
                if selected_text:
                    # Очищаємо буфер обміну
                    self.root.clipboard_clear()
                    
                    # Додаємо текст до буфера
                    self.root.clipboard_append(selected_text)
                    
                    # Додатково використовуємо низькорівневий метод для Windows
                    try:
                        self.root.tk.call('clipboard', 'append', selected_text)
                    except:
                        pass
                    
                    # Оновлюємо буфер обміну
                    self.root.update()
                    
                    # Видаляємо виділений текст з поля вводу
                    self.input_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
                    
                    print(f"✂️ Вирізано з вводу: {len(selected_text)} символів")
                    return 'break'
        except (tk.TclError, AttributeError):
            # Якщо нічого не виділено або інша помилка
            pass
        return None
    
    def paste_input_text(self, event=None):
        """Вставити текст у поле вводу - ВИПРАВЛЕНО"""
        try:
            # Отримуємо текст з буфера обміну (перша спроба)
            try:
                clipboard_text = self.root.clipboard_get()
            except:
                clipboard_text = ""
            # Якщо не вийшло — пробуємо через tk.call
            if not clipboard_text.strip():
                try:
                    clipboard_text = self.root.tk.call('clipboard', 'get')
                except:
                    clipboard_text = ""
            # Якщо є текст — вставляємо
            if clipboard_text.strip():
                # Видаляємо виділене, якщо є
                if self.input_text.tag_ranges(tk.SEL):
                    self.input_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
                # Вставка на позицію курсора
                self.input_text.insert(tk.INSERT, clipboard_text.strip('\n'))
                
                print(f"📎 Вставлено в ввід: {len(clipboard_text)} символів")
                return 'break'
        except (tk.TclError, AttributeError) as e:
            print(f"Помилка вставки: {e}")
            pass
        return None
    
    def send_text_command(self):
        """Відправити текстову команду"""
        command = self.input_text.get(1.0, tk.END).strip()
        
        if not command or command == "Введіть команду...":
            return
        
        self.input_text.delete(1.0, tk.END)
        
        if self.assistant_callback:
            self.assistant_callback('process_text', command)
    
    def show_confirmation(self, question, callback):
        """Показати діалог підтвердження"""
        self.awaiting_confirmation = True
        self.confirmation_callback = callback
        
        self.confirmation_label.config(text=f"{ASSISTANT_TITLE}: {question}")
        
        self.input_container.pack_forget()
        self.confirmation_frame.pack(fill='x', side='bottom', pady=(5, 0))
        
        self.confirmation_timer = threading.Timer(30.0, self.on_confirmation_timeout)
        self.confirmation_timer.start()
        
        self.status_var.set("❓ Очікую підтвердження...")
    
    def hide_confirmation(self):
        """Приховати діалог підтвердження"""
        if hasattr(self, 'confirmation_timer'):
            self.confirmation_timer.cancel()
        
        self.awaiting_confirmation = False
        self.confirmation_callback = None
        
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
                self.on_input_blur()
                self.add_message("system", f"⏳ Автоматичне відновлення аудіо")
        
        self.root.after(1000, self.check_idle)
    
    def process_queue(self):
        """Обробка черги повідомлень"""
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
                elif msg_type == 'stream_start':
                    self.root.after(0, self.start_stream_message)
                elif msg_type == 'stream_chunk':
                    self.root.after(0, self.append_stream_chunk, data)
                elif msg_type == 'stream_end':
                    self.root.after(0, self.end_stream_message)
                elif msg_type == 'update_status':
                    status = data
                    self.root.after(0, self.status_var.set, status)
                elif msg_type == 'update_progress':
                    progress, status_text = data
                    self.root.after(0, self.update_progress, progress, status_text)
                elif msg_type == 'execution_started':
                    self.root.after(0, self.show_stop_button)
                elif msg_type == 'execution_finished':
                    self.root.after(0, self.hide_stop_button)
                
        except queue.Empty:
            pass
        
        self.root.after(100, self.process_queue)
    
    def start_stream_message(self):
        """Почати нове повідомлення асистента для стрімінгу."""
        self.chat_history.configure(state='normal')
        current_text = self.chat_history.get(1.0, tk.END).strip()
        if current_text:
            self.chat_history.insert(tk.END, "\n" + "-"*50 + "\n")
        prefix = f"{ASSISTANT_TITLE}: "
        self.chat_history.insert(tk.END, prefix, ('bold',))
        self.stream_insert_pos = self.chat_history.index(tk.INSERT)
        self.chat_history.configure(state='disabled')

    def append_stream_chunk(self, text):
        """Додати фрагмент тексту до стрімінгового повідомлення."""
        self.chat_history.configure(state='normal')
        self.chat_history.mark_set(tk.INSERT, self.stream_insert_pos)
        self.chat_history.insert(tk.INSERT, text)
        self.stream_insert_pos = self.chat_history.index(tk.INSERT)
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')

    def end_stream_message(self):
        """Завершити стрімінг (додати новий рядок)."""
        self.chat_history.configure(state='normal')
        self.chat_history.insert(self.stream_insert_pos, "\n")
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')

    def update_progress(self, progress: int, status_text: str):
        """Оновити прогрес-бар і статус."""
        if progress >= 100 or progress <= 0:
            self.progress_bar.pack_forget()
            self.progress_var.set(0)
        else:
            self.progress_bar.pack(fill='x', side='bottom', pady=(2, 0))
            self.progress_var.set(progress)
        self.status_var.set(status_text)
        self.root.update_idletasks()

    def show_stop_button(self):
        """Показать кнопку «Стоп» и скрыть кнопку отправки."""
        self.send_button.grid_remove()
        self.stop_button.grid(row=0, column=1, sticky='ns')
        self.status_var.set("⏳ Виконання... (Esc або Стоп для переривання)")

    def hide_stop_button(self):
        """Скрыть кнопку «Стоп» и показать кнопку отправки."""
        self.stop_button.grid_remove()
        self.send_button.grid(row=0, column=1, sticky='ns')
        self.progress_bar.pack_forget()
        self.status_var.set("✅ Готовий до роботи")

    def stop_execution(self):
        """Обработчик нажатия кнопки «Стоп»."""
        if self.assistant_callback:
            self.assistant_callback('stop_execution', None)
        # Визуально вернём кнопку отправки
        self.hide_stop_button()

    def queue_message(self, msg_type, data):
        """Додати повідомлення до черги"""
        self.message_queue.put((msg_type, data))
    
    def run(self):
        """Запустити GUI"""
        self.root.mainloop()

def run_gui(assistant_callback):
    """Запуск GUI"""
    gui = AssistantGUI(assistant_callback)
    gui.run()