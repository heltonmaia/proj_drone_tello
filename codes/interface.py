import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

import cv2
import numpy as np
from PIL import Image, ImageTk
import sounddevice as sd
import io
import speech_recognition as sr
from scipy.io.wavfile import write

import modules.chatbot as chatbot
import modules.tello_control as tello_control
from tello_zune import TelloZune

BG_COLOR = "#262626"
TEXT_COLOR = "#FFFFFF"
LBF_COLOR = "#3c3c3c"
SAMPLE_RATE = 44100
AUDIO_DURATION = 5

class TelloGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tello Drone Control")

        # Configurações de estilo
        self.root.configure(bg=BG_COLOR)
        self.root.geometry("1300x1000")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure('TFrame', background=BG_COLOR)
        style.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=('Ubuntu', 12))
        style.configure('Bold.TLabel', background=BG_COLOR, foreground='white', font=('Ubuntu', 12, 'bold')) # Um estilo customizado para negrito
        style.configure('TButton', background='#555555', foreground='white', borderwidth=1, focusthickness=3, focuscolor='none')
        style.map('TButton', background=[('active', "#939393")]) # Cor quando o mouse está sobre
        style.configure('TLabelframe', background=LBF_COLOR, bordercolor=TEXT_COLOR)
        style.configure('TLabelframe.Label', background=LBF_COLOR, foreground=TEXT_COLOR, font=('Ubuntu', 12))

        # Inicializa o Tello e outros componentes
        self.tello = TelloZune()
        connected = self.tello.start_tello()

        if not connected:
            messagebox.showerror("Erro de Conexão", "Não foi possível conectar ao drone Tello.")
            self.root.destroy()
            return

        self.command_log = tello_control.log_messages
        self.webcam = cv2.VideoCapture(0) # Inicializa a webcam
        self.video_frame = None
        self.fps_counter = 0
        self.video_size = (800, 600)
        self.tello.set_image_size(self.video_size)
        self.last_time_fps = time.time()
        self.fps = 0 # FPS calculado
        self.is_sequence_running = False
        self.max_steps = "7"
        self.drone_height = 0 # cm
        self.abort_sequence_event = threading.Event()

        # Configurações de layout da janela
        self.root.columnconfigure(0, weight=3) # Coluna do vídeo (75%)
        self.root.columnconfigure(1, weight=1) # Coluna de controle (25%)
        self.root.rowconfigure(0, weight=1)

        # Frame principal para o vídeo e chat
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.rowconfigure(0, weight=5)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Frame da direita para controles e parâmetros
        right_frame = ttk.Frame(self.root)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        right_frame.rowconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # --- Componentes da Interface ---
        # Label para o vídeo
        self.video_label = tk.Label(main_frame, anchor="n")
        self.video_label.grid(row=0, column=0, sticky="nsew")

        # Container para chat
        chat_frame = ttk.Frame(main_frame)
        chat_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        chat_frame.columnconfigure(0, weight=1)
        self._create_chat_widgets(chat_frame)

        # Container para controles (sidebar) e parâmetros
        self._create_sidebar_widgets(right_frame)
        self._create_params_widgets(right_frame)

        # --- Iniciar Loops de Atualização ---
        self.update_video_frame()
        self.update_stats()
        
        # Garantir que o drone pouse ao fechar a janela
        self.root.protocol("WM_DELETE_WINDOW", self._exit)

    def _create_chat_widgets(self, container: ttk.Frame) -> None:
        """
        Cria a área de input e display do chat.
        Args:
            container (ttk.Frame): Frame onde os widgets do chat serão colocados.
        """
        container.rowconfigure(0, weight=0)
        container.rowconfigure(1, weight=1)
        container.rowconfigure(2, weight=0)
        # Display da resposta
        self.response_label_user = ttk.Label(container, text="", font=("Ubuntu", 12), wraplength=800, justify="left")
        self.response_label_user.grid(row=0, column=0, sticky="sew", pady=(0, 5))
        self.ai_response_frame = ttk.Frame(container)
        self.ai_response_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 5))
        self.ai_response_frame.rowconfigure(0, weight=1)
        self.ai_response_frame.columnconfigure(0, weight=1)
        self.response_text_ai = tk.Text(
            self.ai_response_frame,
            wrap="word",
            height=12,
            state="disabled", # Começa como somente leitura
            font=("Ubuntu", 12),
            bg=LBF_COLOR,
            fg=TEXT_COLOR,
            borderwidth=0,
            highlightthickness=0
        )
        self.response_text_ai.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(self.ai_response_frame, command=self.response_text_ai.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.response_text_ai.config(yscrollcommand=scrollbar.set)

        # Texto
        input_frame = ttk.Frame(container)
        input_frame.grid(row=2, column=0, sticky="ew", pady=5)
        input_frame.columnconfigure(0, weight=1)
        ttk.Label(input_frame, text="Envie um comando para o drone:").grid(row=0, column=0, columnspan=2, sticky="w")
        self.text_input_entry = ttk.Entry(input_frame)
        self.text_input_entry.grid(row=1, column=0, sticky="ew")
        self.send_text_button = ttk.Button(input_frame, text="Enviar", command=self.send_ai_command)
        self.send_text_button.grid(row=1, column=1, padx=(5,0))
        self.root.bind('<Return>', lambda event: self.send_ai_command()) # Enviar com Enter

        # Áudio
        self.start_record_button = ttk.Button(input_frame, text="Iniciar Gravação", command=self.start_recording)
        self.start_record_button.grid(row=2, column=0, sticky="s", pady=(10, 0), padx=(0, 5))
        self.stop_record_button = ttk.Button(input_frame, text="Parar Gravação", command=self.stop_recording, state="disabled")
        self.stop_record_button.grid(row=2, column=1, sticky="s", pady=(10, 0), padx=(5, 0))

    def _create_sidebar_widgets(self, container: ttk.Frame) -> None:
        """
        Cria os botões de controle e o log de comandos.
        Args:
            container (ttk.Frame): Frame onde os widgets de controle serão colocados.
        """
        sidebar_frame = ttk.LabelFrame(container, text="Controles")
        sidebar_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        sidebar_frame.columnconfigure(0, weight=1)
        
        self.takeoff_button = ttk.Button(sidebar_frame, text="Decolar", command=self.takeoff)
        self.takeoff_button.pack(fill="x", padx=5, pady=2)
        self.land_button = ttk.Button(sidebar_frame, text="Pousar", command=self.land)
        self.land_button.pack(fill="x", padx=5, pady=2)
        self.finish_button = ttk.Button(sidebar_frame, text="Encerrar Drone", command=self._exit)
        self.finish_button.pack(fill="x", padx=5, pady=2)
        self.emergency_button = ttk.Button(sidebar_frame, text="Emergência", command=self.emergency_stop)
        self.emergency_button.pack(fill="x", padx=5, pady=5)

        ttk.Separator(sidebar_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        pace_frame = ttk.Frame(sidebar_frame)
        pace_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(pace_frame, text="Max. Passos:").pack(side="left")
        self.max_steps_input = ttk.Entry(pace_frame, width=5)
        self.max_steps_input.insert(0, str(self.max_steps))
        self.max_steps_input.pack(side="left", padx=5)
        self.max_steps_button = ttk.Button(pace_frame, text="Atualizar", command=self.update_max_steps)
        self.max_steps_button.pack(side="left")

        ttk.Separator(sidebar_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        log_frame = ttk.Frame(sidebar_frame)
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        ttk.Label(log_frame, text="Log de Comandos").pack(anchor="w")
        
        self.log_listbox = tk.Listbox(log_frame, height=10)
        self.log_listbox.pack(fill='both', expand=True, side='left')
        
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_listbox.config(yscrollcommand=scrollbar.set)
        
        ttk.Button(sidebar_frame, text="Limpar Logs", command=self.clear_logs).pack(fill='x', padx=5, pady=5)

    def _create_params_widgets(self, container: ttk.Frame) -> None:
        """
        Cria a exibição de parâmetros do drone.
        Args:
            container (ttk.Frame): Frame onde os widgets de parâmetros serão colocados.
        """
        params_frame = ttk.LabelFrame(container, text="Parâmetros")
        params_frame.grid(row=1, column=0, sticky="sew", pady=(5, 0))

        self.param_icons = {}
        self.param_labels = {}
        
        params_info = {
            'battery': ("icons/battery_icon.png", "%"), # (icon_path, unit)
            'fps': ("icons/fps_icon.png", "fps"),
            'height': ("icons/height_icon.png", "cm"),
            'temp': ("icons/temp_icon.png", "°C"),
            'pres': ("icons/pressure_icon.png", "hPa"),
            'time': ("icons/time_icon.png", "s")
        }

        for i, (key, (icon_path, unit)) in enumerate(params_info.items()):
            row_frame = ttk.Frame(params_frame)
            row_frame.pack(fill='x', padx=5, pady=5)
            
            try:
                img = Image.open(icon_path).resize((30, 30), Image.Resampling.LANCZOS)
                photo_image = ImageTk.PhotoImage(img)
                self.param_icons[key] = photo_image
                icon_label = ttk.Label(row_frame, image=self.param_icons[key])
                icon_label.pack(side="left", padx=(0, 10))

            except FileNotFoundError:
                print(f"ERRO DE ARQUIVO: Ícone não encontrado no caminho: '{icon_path}'")
            except Exception as e:
                print(f"ERRO AO CARREGAR IMAGEM: '{icon_path}'. Detalhes: {e}")

            value_label = ttk.Label(row_frame, text=f"N/A {unit}", font=("Ubuntu", 11, "bold"))
            value_label.pack(side="left")
            self.param_labels[key] = (value_label, unit)

    # --- Funções de Controle ---
    
    def takeoff(self) -> None:
        """Inicia a decolagem do drone e atualiza o log."""
        self.tello.takeoff()
        self.update_log("takeoff")

    def land(self) -> None:
        """Pousa o drone e atualiza o log."""
        self.tello.land()
        self.update_log("land")

    def show_message(self, title: str, message: str) -> None:
        """
        Exibe uma mensagem de alerta.
        Args:
            title (str): O título da mensagem.
            message (str): O conteúdo da mensagem.
        """
        messagebox.showinfo(title, message)

    def update_max_steps(self) -> None:
        """Atualiza o número máximo de passos que uma sequência de comandos pode ter"""
        new_max_steps = self.max_steps_input.get()
        if new_max_steps.isdigit():
            self.max_steps = int(new_max_steps)
            print(f"Número máximos de passos atualizado para: {self.max_steps}")

    def clear_logs(self) -> None:
        """Limpa o log de comandos"""
        self.command_log.clear()
        tello_control.log_messages.clear()
        self.log_listbox.delete(0, tk.END)
        print("Logs limpos.")

    def send_ai_command(self) -> None:
        """Prepara e inicia a sequência de comandos da IA em uma thread gerenciadora."""
        if self.is_sequence_running:
            print("Aviso: Sequência de IA já em andamento.")
            return

        user_text = self.text_input_entry.get()
        frame = self.img_ai

        self.text_input_entry.delete(0, tk.END) # Limpa a caixa de entrada de texto

        threading.Thread(
            target=self._execute_ai_sequence,
            args=(user_text, frame),
            daemon=True
        ).start()

    def _execute_ai_sequence(self, user_text: str, initial_frame: Image.Image) -> None:
        """
        Roda em uma thread e gerencia o loop de múltiplos passos.
        Args:
            user_text (str): A entrada de texto do usuário.
            initial_frame (Image.Image): O frame inicial da câmera.
        """
        self.is_sequence_running = True
        self.abort_sequence_event.clear()
        self.root.after(0, self._set_ui_for_sequence, True) # Desabilita a UI por segurança

        MAX_STEPS = int(self.max_steps)
        current_frame = initial_frame
        
        # Contexto persistente
        context_memory = "Starting mission."

        try:
            for step in range(MAX_STEPS):
                # Injeta a memória no prompt
                if step == 0:
                    prompt_text = user_text
                else:
                    prompt_text = f"OBJECTIVE: {user_text}. PREVIOUS ACTION RESULT: {context_memory}. What now?"

                response, command, continue_route = chatbot.run_ai(
                    prompt_text,
                    current_frame,
                    step,
                    self.drone_height
                )

                # Atualiza a UI
                self.root.after(0, self.update_chat_display, f"Passo {step+1}", response)

                if "[ANALYSIS]" in response:
                    try:
                        context_memory = response.split("[ANALYSIS]")[1].split("[")[0].strip()
                    except:
                        context_memory = response[:100]
                else:
                     context_memory = response[:50]

                if command and chatbot.validate_command(command):
                    tello_control.process_ai_command(self.tello, command)
                    self.root.after(0, self.update_log, f'{step + 1}: {command}')
                else:
                    print(f"Sem comando válido no passo {step}.")
                    if not continue_route: break

                if not continue_route:
                    break
                
                was_interrupted = self.abort_sequence_event.wait(6)
                
                if was_interrupted:
                    break
                
                current_frame = self.img_ai

        except Exception as e:
            print(f"Erro seq: {e}")
        finally:
            self.is_sequence_running = False
            self.root.after(0, self._set_ui_for_sequence, False)

    def _set_ui_for_sequence(self, is_running: bool) -> None:
        """
        Habilita ou desabilita os controles da UI durante uma sequência.
        Args:
            is_running (bool): Indica se a sequência está em execução.
        """
        if is_running:
            state = "disabled"
        else:
            state = "normal"

        self.send_text_button.config(state=state)
        self.start_record_button.config(state=state)
        self.takeoff_button.config(state=state)
        self.land_button.config(state=state)
        self.max_steps_button.config(state=state)

    # --- Funções de Atualização da Interface ---

    def update_video_frame(self) -> None:
        """Captura, processa e exibe um novo frame de vídeo."""
        frame = self.tello.get_frame()
        # frame = self.webcam.read()[1] # Ativar webcam
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Garante que temos um array válido antes de prosseguir.
        if isinstance(img_rgb, np.ndarray):
            self.img_ai = Image.fromarray(img_rgb)
            photo = ImageTk.PhotoImage(image=self.img_ai)
        else:
            null_img = Image.new("RGB", self.video_size, color="black")
            photo = ImageTk.PhotoImage(image=null_img)
        
        self.video_label.config(image=photo)
        self._video_frame = photo

        # Contagem de frames para cálculo do FPS
        self.fps_counter += 1

        # Agenda a próxima atualização
        self.root.after(20, self.update_video_frame)
        
    def update_stats(self) -> None:
        """Atualiza os valores dos parâmetros do drone."""
        # FPS
        now = time.time()
        time_fps = now - self.last_time_fps
        if time_fps > 0:
            self.fps = self.fps_counter / time_fps
        self.fps_counter = 0
        self.last_time_fps = now
        int_fps = int(self.fps)

        stats = self.tello.get_info()
        bat, self.drone_height, temph, pres, time_elapsed = stats

        # Atualiza os labels
        self._update_param_label('fps', int_fps)
        self._update_param_label('battery', bat)
        self._update_param_label('height', self.drone_height) if self.drone_height is not None else self._update_param_label('height', 10)
        self._update_param_label('temp', temph)
        self._update_param_label('pres', pres)
        self._update_param_label('time', time_elapsed)

        # Agendar a próxima atualização a cada segundo
        self.root.after(1000, self.update_stats)

    def _update_param_label(self, key: str, value: int | float) -> None:
        """
        Atualiza o label de um parâmetro específico.
        Args:
            key (str): A chave do parâmetro a ser atualizado.
            value (int | float): O novo valor do parâmetro.
        """
        if key in self.param_labels:
            label, unit = self.param_labels[key]
            text = f"{value if value is not None else 'N/A'} {unit}"
            label.config(text=text)

    def update_log(self, message: str) -> None:
        """
        Adiciona uma mensagem ao log na interface.
        Args:
            message (str): A mensagem a ser adicionada ao log.
        """
        tello_control.log_messages.append(message)
        
        # Atualiza a Listbox
        self.log_listbox.delete(0, tk.END)
        for log in reversed(tello_control.log_messages):
            self.log_listbox.insert(0, log)

    def update_chat_display(self, user_msg: str, ai_msg: str) -> None:
        """
        Atualiza os labels do chat, agora usando um widget Text para a resposta da IA.
        """
        self.response_label_user.config(text=f"Você: {user_msg}")

        self.response_text_ai.config(state="normal")
        self.response_text_ai.delete("1.0", tk.END)
        self.response_text_ai.insert(tk.END, f"Drone: {ai_msg}")
        self.response_text_ai.config(state="disabled")
        self.response_text_ai.see(tk.END)

    def _transcribe_audio(self, audio_data: np.ndarray) -> str:
        """Transcreve o áudio gravado para texto.
        Args:
            audio_data (np.ndarray): O áudio gravado.
        Returns:
            str: O texto transcrito.
        """
        recognizer = sr.Recognizer()
        try:
            mem_wav = io.BytesIO()
            write(mem_wav, SAMPLE_RATE, audio_data)
            mem_wav.seek(0)
            with sr.AudioFile(mem_wav) as source:
                audio_for_recognition = recognizer.record(source)
            
            transcribed_text = recognizer.recognize_google(audio_for_recognition, language='pt-BR') # type: ignore
            # transcribed_text = recognizer.recognize_sphinx(audio_for_recognition, language='pt-BR') # type: ignore
            print(f"Texto reconhecido: '{transcribed_text}'")
            return transcribed_text
        except sr.UnknownValueError:
            return "Não foi possível entender o áudio."
        except sr.RequestError:
            return "Erro de conexão com o serviço de transcrição."
        except Exception as e:
            print(f"Erro inesperado na transcrição: {e}")
            return "Erro ao processar o áudio."

    def _record_audio(self) -> None:
        """Grava e depois dispara a transcrição em uma thread."""
        try:
            print(f"Gravando áudio por até {AUDIO_DURATION} segundos...")
            audio_data = sd.rec(int(AUDIO_DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='int16')
            sd.wait()

            self.root.after(0, lambda: self.text_input_entry.insert(0, "Transcrevendo áudio..."))
            transcribed_text = self._transcribe_audio(audio_data)

            def update_entry():
                self.text_input_entry.delete(0, tk.END)
                self.text_input_entry.insert(0, transcribed_text)
            
            self.root.after(0, update_entry)

        except Exception as e:
            print(f"Ocorreu um erro durante o ciclo de gravação: {e}")
        finally:
            self.root.after(0, self.reset_recording_buttons)

    def start_recording(self) -> None:
        """Inicia a gravação de áudio."""
        self.start_record_button.config(state="disabled", text=f"Gravando...({AUDIO_DURATION}s)")
        self.stop_record_button.config(state="normal")
        threading.Thread(target=self._record_audio, daemon=True).start()

    def stop_recording(self) -> None:
        """Para a gravação de áudio."""
        sd.stop()

    def reset_recording_buttons(self) -> None:
        """Função auxiliar para reabilitar o botão de gravação."""
        self.start_record_button.config(state="normal", text="Iniciar Gravação")
        self.stop_record_button.config(state="disabled")

    def emergency_stop(self) -> None:
        """Função para parar imediatamente o drone."""
        self.tello.send_cmd('stop')
        if self.abort_sequence_event:
            self.abort_sequence_event.set()
        print("Comando de emergência enviado ao drone.")

    def _exit(self) -> None:
        """Função chamada ao fechar a janela."""
        print("Encerrando conexão...")
        self.tello.end_tello()
        self.root.destroy()
