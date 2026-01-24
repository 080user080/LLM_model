# test_clipboard_methods.py
"""Тестовий скрипт для перевірки методів копіювання/вставки на Windows 10/11"""
import tkinter as tk
from tkinter import ttk
import pyperclip  # Необхідно встановити: pip install pyperclip

class ClipboardTestApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Тест методів копіювання/вставки - Windows")
        self.root.geometry("800x700")
        
        self.setup_styles()
        self.create_widgets()
        
    def setup_styles(self):
        """Налаштування стилів"""
        self.style = ttk.Style()
        self.style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'), padding=10)
        self.style.configure('Method.TLabel', font=('Segoe UI', 10, 'bold'), padding=5)
        
    def create_widgets(self):
        """Створення інтерфейсу"""
        # Заголовок
        title = ttk.Label(
            self.root, 
            text="Тестування методів копіювання/вставки на Windows",
            style='Title.TLabel'
        )
        title.pack(fill='x', padx=10, pady=5)
        
        # Інструкції
        instructions = tk.Text(
            self.root, 
            height=5,
            font=('Segoe UI', 9),
            bg='#f0f0f0',
            relief='flat'
        )
        instructions.pack(fill='x', padx=10, pady=(0, 10))
        instructions.insert('1.0', 
            "Інструкція:\n"
            "1. Введіть текст у будь-яке поле\n"
            "2. Спробуйте Ctrl+C, Ctrl+V, Ctrl+X\n"
            "3. Перевірте працездатність кнопок\n"
            "4. Перевірте чи працює між полями та зовнішніми додатками\n"
        )
        instructions.configure(state='disabled')
        
        # Створюємо контейнер для полів
        container = ttk.Frame(self.root)
        container.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Метод 1: Стандартні біндинги (з core_gui.py)
        self.create_method_frame(
            container, 
            1,
            "Метод 1: Стандартні біндинги (як в core_gui.py)",
            self.bind_method_1
        )
        
        # Метод 2: Використання event_generate
        self.create_method_frame(
            container, 
            2,
            "Метод 2: Використання event_generate",
            self.bind_method_2
        )
        
        # Метод 3: Використання pyperclip
        self.create_method_frame(
            container, 
            3,
            "Метод 3: Використання pyperclip",
            self.bind_method_3
        )
        
        # Метод 4: Низькорівневі Tk виклики
        self.create_method_frame(
            container, 
            4,
            "Метод 4: Низькорівневі Tk виклики",
            self.bind_method_4
        )
        
        # Метод 5: Комбінований підхід
        self.create_method_frame(
            container, 
            5,
            "Метод 5: Комбінований підхід",
            self.bind_method_5
        )
        
        # Метод 6: Використання меню контексту
        self.create_method_frame(
            container, 
            6,
            "Метод 6: Контекстне меню",
            self.bind_method_6
        )
        
        # Кнопка очищення всіх полів
        clear_btn = ttk.Button(
            container,
            text="Очистити всі поля",
            command=self.clear_all_fields
        )
        clear_btn.pack(pady=10)
        
        # Статус бар
        self.status_var = tk.StringVar(value="Готово до тестування")
        status_bar = ttk.Label(
            container,
            textvariable=self.status_var,
            relief='sunken',
            padding=5
        )
        status_bar.pack(fill='x', pady=(10, 0))
        
    def create_method_frame(self, parent, method_num, title, bind_func):
        """Створити фрейм для одного методу"""
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.pack(fill='x', pady=5)
        
        # Текстове поле
        text_widget = tk.Text(
            frame,
            height=4,
            width=60,
            font=('Consolas', 10),
            wrap='word',
            relief='solid',
            borderwidth=1
        )
        text_widget.pack(fill='x', pady=(0, 5))
        
        # Додати тестовий текст
        text_widget.insert('1.0', f"Тестовий текст для методу {method_num}.\nСпробуйте Ctrl+C/V/X.")
        
        # Застосувати метод прив'язки
        bind_func(text_widget)
        
        # Кнопки для ручного тестування
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')
        
        ttk.Button(
            btn_frame,
            text="Копіювати",
            command=lambda: self.copy_text(text_widget, method_num)
        ).pack(side='left', padx=2)
        
        ttk.Button(
            btn_frame,
            text="Вставити",
            command=lambda: self.paste_text(text_widget, method_num)
        ).pack(side='left', padx=2)
        
        ttk.Button(
            btn_frame,
            text="Вирізати",
            command=lambda: self.cut_text(text_widget, method_num)
        ).pack(side='left', padx=2)
        
        # Зберегти посилання на віджет
        setattr(self, f'text_{method_num}', text_widget)
        
    # Метод 1: Як в оригінальному core_gui.py
    def bind_method_1(self, widget):
        """Стандартні біндинги як в core_gui.py"""
        widget.bind('<Control-c>', lambda e: self.copy_method_1(e, widget))
        widget.bind('<Control-C>', lambda e: self.copy_method_1(e, widget))
        widget.bind('<Control-v>', lambda e: self.paste_method_1(e, widget))
        widget.bind('<Control-V>', lambda e: self.paste_method_1(e, widget))
        widget.bind('<Control-x>', lambda e: self.cut_method_1(e, widget))
        widget.bind('<Control-X>', lambda e: self.cut_method_1(e, widget))
        
    def copy_method_1(self, event, widget):
        """Метод копіювання 1"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.root.update()  # Оновлення для Windows
                self.status_var.set(f"Метод 1: Скопійовано {len(selected)} символів")
                return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 1 помилка: {e}")
        return None
    
    def paste_method_1(self, event, widget):
        """Метод вставки 1"""
        try:
            # Отримати з буфера обміну
            clipboard_text = self.root.clipboard_get()
            
            # Видалити виділений текст якщо є
            if widget.tag_ranges('sel'):
                widget.delete('sel.first', 'sel.last')
            
            # Вставити в позицію курсора
            widget.insert('insert', clipboard_text)
            self.status_var.set(f"Метод 1: Вставлено {len(clipboard_text)} символів")
            return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 1 помилка вставки: {e}")
        return None
    
    def cut_method_1(self, event, widget):
        """Метод вирізання 1"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.root.update()
                widget.delete('sel.first', 'sel.last')
                self.status_var.set(f"Метод 1: Вирізано {len(selected)} символів")
                return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 1 помилка вирізання: {e}")
        return None
    
    # Метод 2: Використання event_generate
    def bind_method_2(self, widget):
        """Використання стандартних подій Tk"""
        widget.bind('<Control-c>', lambda e: widget.event_generate('<<Copy>>'))
        widget.bind('<Control-v>', lambda e: widget.event_generate('<<Paste>>'))
        widget.bind('<Control-x>', lambda e: widget.event_generate('<<Cut>>'))
        
        # Додаткові обробники для логування
        widget.bind('<<Copy>>', lambda e: self.status_var.set("Метод 2: Copy event"))
        widget.bind('<<Paste>>', lambda e: self.status_var.set("Метод 2: Paste event"))
        widget.bind('<<Cut>>', lambda e: self.status_var.set("Метод 2: Cut event"))
    
    # Метод 3: Використання pyperclip
    def bind_method_3(self, widget):
        """Використання pyperclip для роботи з буфером"""
        widget.bind('<Control-c>', lambda e: self.copy_method_3(e, widget))
        widget.bind('<Control-v>', lambda e: self.paste_method_3(e, widget))
        widget.bind('<Control-x>', lambda e: self.cut_method_3(e, widget))
    
    def copy_method_3(self, event, widget):
        """Копіювання через pyperclip"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                pyperclip.copy(selected)
                self.status_var.set(f"Метод 3 (pyperclip): Скопійовано {len(selected)} символів")
                return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 3 помилка: {e}")
        return None
    
    def paste_method_3(self, event, widget):
        """Вставка через pyperclip"""
        try:
            clipboard_text = pyperclip.paste()
            
            if widget.tag_ranges('sel'):
                widget.delete('sel.first', 'sel.last')
            
            widget.insert('insert', clipboard_text)
            self.status_var.set(f"Метод 3 (pyperclip): Вставлено {len(clipboard_text)} символів")
            return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 3 помилка вставки: {e}")
        return None
    
    def cut_method_3(self, event, widget):
        """Вирізання через pyperclip"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                pyperclip.copy(selected)
                widget.delete('sel.first', 'sel.last')
                self.status_var.set(f"Метод 3 (pyperclip): Вирізано {len(selected)} символів")
                return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 3 помилка вирізання: {e}")
        return None
    
    # Метод 4: Низькорівневі Tk виклики
    def bind_method_4(self, widget):
        """Низькорівневі виклики Tk"""
        widget.bind('<Control-c>', lambda e: self.copy_method_4(e, widget))
        widget.bind('<Control-v>', lambda e: self.paste_method_4(e, widget))
        widget.bind('<Control-x>', lambda e: self.cut_method_4(e, widget))
    
    def copy_method_4(self, event, widget):
        """Низькорівневе копіювання"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                # Низькорівневий виклик Tk
                widget.tk.call('clipboard', 'append', selected)
                self.status_var.set(f"Метод 4 (tk.call): Скопійовано {len(selected)} символів")
                return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 4 помилка: {e}")
        return None
    
    def paste_method_4(self, event, widget):
        """Низькорівнева вставка"""
        try:
            # Отримати через tk.call
            clipboard_text = widget.tk.call('clipboard', 'get')
            
            if widget.tag_ranges('sel'):
                widget.delete('sel.first', 'sel.last')
            
            widget.insert('insert', clipboard_text)
            self.status_var.set(f"Метод 4 (tk.call): Вставлено {len(clipboard_text)} символів")
            return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 4 помилка вставки: {e}")
        return None
    
    def cut_method_4(self, event, widget):
        """Низькорівневе вирізання"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                widget.tk.call('clipboard', 'append', selected)
                widget.delete('sel.first', 'sel.last')
                self.status_var.set(f"Метод 4 (tk.call): Вирізано {len(selected)} символів")
                return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 4 помилка вирізання: {e}")
        return None
    
    # Метод 5: Комбінований підхід
    def bind_method_5(self, widget):
        """Комбінований підхід - кілька методів разом"""
        widget.bind('<Control-c>', lambda e: self.copy_method_5(e, widget))
        widget.bind('<Control-v>', lambda e: self.paste_method_5(e, widget))
        widget.bind('<Control-x>', lambda e: self.cut_method_5(e, widget))
    
    def copy_method_5(self, event, widget):
        """Комбіноване копіювання"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                
                # Спробувати кілька методів
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(selected)
                    self.root.update()
                except:
                    pass
                    
                try:
                    pyperclip.copy(selected)
                except:
                    pass
                    
                try:
                    widget.tk.call('clipboard', 'append', selected)
                except:
                    pass
                
                self.status_var.set(f"Метод 5 (комбінований): Скопійовано {len(selected)} символів")
                return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 5 помилка: {e}")
        return None
    
    def paste_method_5(self, event, widget):
        """Комбінована вставка"""
        try:
            clipboard_text = None
            
            # Спробувати отримати з різних джерел
            try:
                clipboard_text = self.root.clipboard_get()
            except:
                pass
                
            if not clipboard_text:
                try:
                    clipboard_text = pyperclip.paste()
                except:
                    pass
                    
            if not clipboard_text:
                try:
                    clipboard_text = widget.tk.call('clipboard', 'get')
                except:
                    pass
            
            if clipboard_text:
                if widget.tag_ranges('sel'):
                    widget.delete('sel.first', 'sel.last')
                
                widget.insert('insert', clipboard_text)
                self.status_var.set(f"Метод 5 (комбінований): Вставлено {len(clipboard_text)} символів")
                return 'break'
            else:
                self.status_var.set("Метод 5: Не вдалося отримати текст з буфера")
        except Exception as e:
            self.status_var.set(f"Метод 5 помилка вставки: {e}")
        return None
    
    def cut_method_5(self, event, widget):
        """Комбіноване вирізання"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                
                # Видалити спочатку
                widget.delete('sel.first', 'sel.last')
                
                # Потім скопіювати різними методами
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(selected)
                    self.root.update()
                except:
                    pass
                    
                try:
                    pyperclip.copy(selected)
                except:
                    pass
                    
                try:
                    widget.tk.call('clipboard', 'append', selected)
                except:
                    pass
                
                self.status_var.set(f"Метод 5 (комбінований): Вирізано {len(selected)} символів")
                return 'break'
        except Exception as e:
            self.status_var.set(f"Метод 5 помилка вирізання: {e}")
        return None
    
    # Метод 6: Контекстне меню
    def bind_method_6(self, widget):
        """Додати контекстне меню"""
        # Створити меню
        context_menu = tk.Menu(widget, tearoff=0)
        context_menu.add_command(label="Копіювати", 
                                command=lambda: self.copy_method_1(None, widget))
        context_menu.add_command(label="Вставити", 
                                command=lambda: self.paste_method_1(None, widget))
        context_menu.add_command(label="Вирізати", 
                                command=lambda: self.cut_method_1(None, widget))
        context_menu.add_separator()
        context_menu.add_command(label="Видалити", 
                                command=lambda: widget.delete('sel.first', 'sel.last') if widget.tag_ranges('sel') else None)
        
        # Прив'язати меню до правого кліку
        widget.bind('<Button-3>', lambda e: context_menu.tk_popup(e.x_root, e.y_root))
        
        # Також прив'язати стандартні комбінації
        widget.bind('<Control-c>', lambda e: self.copy_method_1(e, widget))
        widget.bind('<Control-v>', lambda e: self.paste_method_1(e, widget))
        widget.bind('<Control-x>', lambda e: self.cut_method_1(e, widget))
    
    # Допоміжні методи для кнопок
    def copy_text(self, widget, method_num):
        """Копіювати через кнопку"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.root.update()
                self.status_var.set(f"Кнопка: Метод {method_num} - скопійовано {len(selected)} символів")
            else:
                self.status_var.set(f"Кнопка: Метод {method_num} - нічого не виділено")
        except Exception as e:
            self.status_var.set(f"Кнопка помилка: {e}")
    
    def paste_text(self, widget, method_num):
        """Вставити через кнопку"""
        try:
            clipboard_text = self.root.clipboard_get()
            
            if widget.tag_ranges('sel'):
                widget.delete('sel.first', 'sel.last')
            
            widget.insert('insert', clipboard_text)
            self.status_var.set(f"Кнопка: Метод {method_num} - вставлено {len(clipboard_text)} символів")
        except Exception as e:
            self.status_var.set(f"Кнопка помилка вставки: {e}")
    
    def cut_text(self, widget, method_num):
        """Вирізати через кнопку"""
        try:
            if widget.tag_ranges('sel'):
                selected = widget.get('sel.first', 'sel.last')
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.root.update()
                widget.delete('sel.first', 'sel.last')
                self.status_var.set(f"Кнопка: Метод {method_num} - вирізано {len(selected)} символів")
            else:
                self.status_var.set(f"Кнопка: Метод {method_num} - нічого не виділено")
        except Exception as e:
            self.status_var.set(f"Кнопка помилка вирізання: {e}")
    
    def clear_all_fields(self):
        """Очистити всі поля"""
        for i in range(1, 7):
            widget = getattr(self, f'text_{i}', None)
            if widget:
                widget.delete('1.0', 'end')
        self.status_var.set("Всі поля очищено")
    
    def run(self):
        """Запустити додаток"""
        self.root.mainloop()

if __name__ == "__main__":
    print("Запуск тесту методів копіювання/вставки на Windows...")
    print("Перевіряйте кожне поле на працездатність Ctrl+C, Ctrl+V, Ctrl+X")
    print("Також перевіряйте копіювання між полями та зовнішніми додатками")
    
    app = ClipboardTestApp()
    app.run()