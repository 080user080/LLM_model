# functions/logic_commands.py
"""Обробка команд та VoiceAssistant"""
import threading
import time
import threading
from colorama import Fore, Back, Style
from .config import LM_STUDIO_URL, TTS_ENABLED, TTS_SPEAK_PREFIXES
from .logic_audio import correct_whisper_text, check_activation_word, remove_activation_word
class VoiceAssistant:
    # ... (ініціалізація)
    def __init__(self, stt_engine, registry, system_prompt, listener=None, gui_log_callback=None):
        self.stt_engine = stt_engine
        self.registry = registry
        self.system_prompt = system_prompt
        self.conversation_history = []
        self.is_listening = True
        self.last_command_time = 0
        self.command_cooldown = 2
        self.listener = listener
        
        # GUI логування
        self.gui_log_callback = gui_log_callback
        
        self.planner = None  #GPT
        from .core_memory import MemoryManager
        self.memory = MemoryManager()  # довготривала пам'ять
        from .core_executor import TaskExecutor
        # Створюємо виконавець з колбеком для GUI
        self.executor = TaskExecutor(gui_callback=self.gui_log_callback)
        
        # TTS двигун
        self.tts_engine = None
        self.tts_enabled = TTS_ENABLED
        
        # Отримати core модулі
        self.dispatcher = None
        self.cache_manager = None
        self.streaming_handler = None
        
        dispatcher_module = registry.get_core_module('dispatcher')
        if dispatcher_module:
            self.dispatcher = dispatcher_module.Dispatcher(registry)
            print(f"{Fore.MAGENTA}⚡ Диспетчер активовано")
        # ... решта __init__
        cache_module = registry.get_core_module('cache')
        if cache_module:
            self.cache_manager = cache_module.CacheManager(registry)
            print(f"{Fore.MAGENTA}💾 Кеш активовано")
        
        streaming_module = registry.get_core_module('streaming')
        if streaming_module:
            self.streaming_handler = streaming_module.StreamingHandler(LM_STUDIO_URL)
            self.streaming_handler_enabled = True
            print(f"{Fore.MAGENTA}⚡ Стрімінг активовано")
        print(f"{Fore.CYAN}🔊 TTS статус: {'УВІМКНЕНО' if self.tts_enabled else 'ВИМКНЕНО'}")
    
    def log_to_gui(self, sender, message):
        """Відправити повідомлення в GUI"""
        if self.gui_log_callback:
            if sender == "assistant":
                from .config import TTS_SPEAK_PREFIXES, ASSISTANT_DISPLAY_NAME
                # Видаляємо будь-які префікси, якщо вони вже є
                for prefix in TTS_SPEAK_PREFIXES:
                    if message.strip().startswith(prefix):
                        message = message.strip()[len(prefix):].strip()
                        break
                # Додаємо стандартний префікс
                message = f"{ASSISTANT_DISPLAY_NAME}: {message}"
            
            self.gui_log_callback(sender, message)
        else:
            # Fallback до консолі
            if sender == "user":
                print(f"{Fore.CYAN}👑 ВИ: {Fore.WHITE}{message}")
            else:
                print(f"{Fore.GREEN}{ASSISTANT_DISPLAY_NAME}: {Fore.WHITE}{message}")
    
    def set_tts_engine(self, tts_engine):
        """Встановити TTS двигун"""
        self.tts_engine = tts_engine
        if tts_engine and self.tts_enabled:
            print(f"{Fore.GREEN}✅ TTS двигун встановлено")
        else:
            print(f"{Fore.YELLOW}⚠️  TTS двигун не встановлено або вимкнено")

    def ask_llm(self, prompt: str) -> str:
        """Обгортка для виклику LLM (для Planner)."""
        from .logic_llm import ask_llm
        return ask_llm(prompt, self.conversation_history, self.system_prompt)

    def execute_function(self, action: str, params: dict):
        """Виконати функцію через реєстр (для Planner)."""
        return self.registry.execute_function(action, params)
    
    def set_planner(self, planner):
        """Встановити планувальник"""
        self.planner = planner  #GPT
    
    def should_speak_response(self, response_text):
        """Перевірити, чи потрібно озвучувати відповідь"""
        if not self.tts_enabled or not self.tts_engine or not self.tts_engine.is_ready:
            return False
        
        if not response_text or len(response_text.strip()) == 0:
            return False
            
        return True
    
    def extract_speakable_text(self, response_text):
        """Витягнути текст для озвучення (без префіксів)"""
        clean_text = response_text.strip()
        for prefix in TTS_SPEAK_PREFIXES:
            if clean_text.startswith(prefix):
                clean_text = clean_text[len(prefix):].strip()
        return clean_text
    
    def speak_response(self, text):
        """Озвучити відповідь (викликається в окремому потоці)"""
        if not self.tts_enabled or not self.tts_engine:
            return
        
        if self.tts_engine.is_playing:
            print(f"{Fore.YELLOW}⚠️  TTS вже відтворює аудіо, пропускаю")
            return
        
        try:
            success = self.tts_engine.speak(text, wait=True)
            if not success:
                print(f"{Fore.RED}❌ Не вдалося озвучити відповідь")
        except Exception as e:
            print(f"{Fore.RED}❌ Помилка озвучення: {e}")
            import traceback
            traceback.print_exc()
    
    def process_command(self, command_text, from_gui=False):
        """Обробити команду"""
        try:
            # --- Planner branch --- #GPT
            if hasattr(self, "planner") and self.planner and len(command_text.split()) > 6:
                plan = self.planner.create_plan(command_text)
                if plan:
                    # --- ПЕРЕВІРКА БЕЗПЕКИ ПЛАНУ ---
                    is_safe, explanation = self.planner.validate_plan_safety(plan, command_text)
                    if not is_safe:
                        warning_msg = f"⚠️ План може бути небезпечним: {explanation}"
                        self.log_to_gui("assistant", warning_msg)
                        # Можна запитати підтвердження через GUI
                        # (тут можна додати виклик confirm_action)
                        print(f"{Fore.RED}{warning_msg}{Fore.RESET}")
                        # Поки що не виконуємо
                        return
                    # ---------------------------------
                    
                    print(f"{Fore.MAGENTA}📋 План: {plan}")
                    
                    # Функція для виконання одного кроку (викликається з Executor)
                    def execute_step(step):
                        action = step.get("action")
                        args = step.get("args", {})
                        return self.registry.execute_function(action, args)
                    
                    # Колбек після завершення всього плану
                    def on_plan_complete(results):
                        self.memory.update_task(command_text, plan, results)
                        self.log_to_gui("assistant", f"✅ Виконано план із {len(results)} кроків.")
                    
                    # Запускаємо у фоновому потоці з прогресом
                    self.executor.execute_plan_async(plan, execute_step, on_plan_complete)
                    return  # не повертаємо нічого, бо виконання асинхронне
            
            from .config import ASSISTANT_DISPLAY_NAME
            
            # Для GUI команди - пропускаємо перевірку активаційного слова
            if not from_gui:
                # 1. ПЕРЕВІРКА АКТИВАЦІЙНОГО СЛОВА (ТІЛЬКИ ДЛЯ АУДІО)
                if not check_activation_word(command_text):
                    print(f"{Fore.LIGHTBLACK_EX}zzz Ігнорую (немає звертання): '{command_text}'")
                    return
                
                # 2. ВИДАЛЕННЯ АКТИВАЦІЙНОГО СЛОВА (ТІЛЬКИ ДЛЯ АУДІО)
                clean_command = remove_activation_word(command_text)
                
                if not clean_command or len(clean_command.strip()) < 3:
                    print(f"{Fore.YELLOW}⚠️  Звертання є, але команди немає: '{command_text}'")
                    return
                
                command_text = clean_command
            
            # 3. Логуємо команду в GUI (для всіх типів)
            self.log_to_gui("user", command_text)
            
            print(f"{Fore.CYAN}🎯 {'[GUI] ' if from_gui else '[Аудіо] '}Команда: '{command_text}'")
            
            start_total = time.time()
            
            # Перевірка кешу
            if self.cache_manager:
                cached_response, action_info = self.cache_manager.get(command_text)
                if cached_response:
                    print(f"{Fore.YELLOW}⚡ [Кеш]")
                    self.log_to_gui("assistant", cached_response)
                    
                    if self.should_speak_response(cached_response):
                        speakable_text = self.extract_speakable_text(cached_response)
                        if speakable_text:
                            threading.Thread(
                                target=self.speak_response,
                                args=(speakable_text,),
                                daemon=True
                            ).start()
                    
                    if action_info:
                        print(f"{Fore.MAGENTA}🔄 Виконую дію з кешу...")
                        execution_result = self.cache_manager.execute_cached_action(action_info)
                        if execution_result:
                            print(f"{Fore.GREEN}✅ Дія виконана: {execution_result}")
                            self.log_to_gui("assistant", execution_result)
                        else:
                            print(f"{Fore.YELLOW}⚠️  Дію не виконано")
                    
                    print(f"{Fore.LIGHTBLACK_EX}⏱️  0.00с")
                    return
            
            # Швидкий маршрут
            if self.dispatcher:
                quick_result = self.dispatcher.try_quick_route(command_text)
                if quick_result:
                    elapsed = time.time() - start_total
                    print(f"{Fore.YELLOW}⚡ [Швидкий маршрут]")
                    self.log_to_gui("assistant", quick_result)
                    
                    if self.should_speak_response(quick_result):
                        speakable_text = self.extract_speakable_text(quick_result)
                        if speakable_text:
                            threading.Thread(
                                target=self.speak_response,
                                args=(speakable_text,),
                                daemon=True
                            ).start()
                    
                    print(f"{Fore.LIGHTBLACK_EX}⏱️  {elapsed:.2f}с")
                    
                    if self.cache_manager:
                        self.cache_manager.set(command_text, quick_result)
                    return
            
            # LLM маршрут
            from .logic_llm import ask_llm, process_llm_response
            from .core_streaming import StreamingHandler
            
            self.conversation_history.append({"role": "user", "content": command_text})
            
            # Підготовка повідомлень для LLM
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history)
            messages.append({"role": "user", "content": command_text})
            
            # Використовуємо стрімінг, якщо доступний
            full_response = ""
            if self.streaming_handler:
                try:
                    print(f"{Fore.MAGENTA}🤔 [Думаю (стрімінг)...]")
                    start_llm = time.time()
                    
                    # Функція для обробки чанків
                    def on_chunk(chunk_text: str):
                        nonlocal full_response
                        full_response += chunk_text
                        if self.gui_log_callback:
                            self.gui_log_callback("assistant_stream_chunk", chunk_text)
                            
                    # Сигнал початку стрімінгу в GUI
                    if self.gui_log_callback:
                        self.gui_log_callback("assistant_stream_start", None)
                        
                    self.streaming_handler.stream_response_with_callback(messages, on_chunk)
                    
                    # Сигнал завершення стрімінгу
                    if self.gui_log_callback:
                        self.gui_log_callback("assistant_stream_end", None)
                        
                    llm_time = time.time() - start_llm
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️ Стрімінг не вдався: {e}, використовую звичайний запит")
                    # Fallback на звичайний запит
                    answer = ask_llm(command_text, self.conversation_history, self.system_prompt)
                    full_response = answer
                    self.log_to_gui("assistant", answer)
            else:
                # Звичайний запит без стрімінгу
                print(f"{Fore.MAGENTA}🤔 [Думаю...]")
                start_llm = time.time()
                answer = ask_llm(command_text, self.conversation_history, self.system_prompt)
                full_response = answer
                llm_time = time.time() - start_llm
                self.log_to_gui("assistant", answer)
                
            # Обробка відповіді та виконання функцій
            final_answer = process_llm_response(full_response, self.registry)
            
            # Якщо результат відрізняється (виконана дія), логуємо його окремо
            if final_answer != full_response:
                self.log_to_gui("assistant", final_answer)
                
            # Додаємо відповідь до історії
            self.conversation_history.append({"role": "assistant", "content": full_response})
            
            # Озвучення
            if self.should_speak_response(final_answer):
                speakable_text = self.extract_speakable_text(final_answer)
                if speakable_text:
                    threading.Thread(
                        target=self.speak_response,
                        args=(speakable_text,),
                        daemon=True
                    ).start()
            
            # Зберегти в кеш
            if self.cache_manager:
                self.cache_manager.set(command_text, final_answer)
            
            elapsed = time.time() - start_total
            print(f"{Fore.LIGHTBLACK_EX}⏱️  {elapsed:.2f}с (LLM: {llm_time:.2f}с)")
            
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
                
        except Exception as e:
            error_msg = f"❌ Помилка: {e}"
            self.log_to_gui("assistant", error_msg)
            print(f"{Fore.RED}{error_msg}")
            import traceback
            traceback.print_exc()