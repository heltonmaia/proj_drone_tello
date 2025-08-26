import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

import cv2
import numpy as np
from PIL import Image, ImageTk
import sounddevice as sd

import modules.chatbot as chatbot
import modules.tello_control as tello_control
from tello_zune import TelloZune

BG_COLOR = "#262626"
TEXT_COLOR = "#FFFFFF"
LBF_COLOR = "#3c3c3c"
SAMPLE_RATE = 44100
AUDIO_DURATION = 5
DISPLAY_SIZE = (800, 600)

class TelloGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tello Drone Control")

        # Configurações de estilo
        self.root.configure(bg=BG_COLOR)
        self.root.geometry("1200x1000")
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
        self.tello.start_tello()
        self.command_log = tello_control.log_messages
        tello_control.pace = "50" # Valor inicial do passo
        self.webcam = cv2.VideoCapture(0) # Inicializa a webcam
        self.audio = None
        self.video_frame = None
        self.is_recording = False
        self.fps_counter = 0
        self.last_time_fps = time.time()
        self.fps = 0 # FPS calculado

        # Configurações de layout da janela
        self.root.columnconfigure(0, weight=3) # Coluna do vídeo (75%)
        self.root.columnconfigure(1, weight=1) # Coluna de controle (25%)
        self.root.rowconfigure(0, weight=1)

        # Frame principal para o vídeo e chat
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.rowconfigure(0, weight=1, minsize=500)
        main_frame.rowconfigure(1, weight=0)
        main_frame.columnconfigure(0, weight=1)

        # Frame da esquerda para controles e parâmetros
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
        chat_frame.grid(row=1, column=0, sticky="sew", pady=(10, 0))
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
        # Display da resposta
        self.response_label_user = ttk.Label(container, text="", font=("Ubuntu", 12), wraplength=800, justify="left")
        self.response_label_user.grid(row=0, column=0, sticky="sew", pady=(0, 5))
        self.response_label_ai = ttk.Label(container, text="", font=("Ubuntu", 12), justify="left", wraplength=800) # wraplength quebra a linha
        self.response_label_ai.grid(row=1, column=0, sticky="sew", pady=(0, 5))

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
        
        ttk.Button(sidebar_frame, text="Decolar", command=self.takeoff).pack(fill="x", padx=5, pady=2)
        ttk.Button(sidebar_frame, text="Pousar", command=self.land).pack(fill="x", padx=5, pady=2)
        ttk.Button(sidebar_frame, text="Encerrar Drone", command=self._exit).pack(fill="x", padx=5, pady=5)

        ttk.Separator(sidebar_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        pace_frame = ttk.Frame(sidebar_frame)
        pace_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(pace_frame, text="Passo (cm):").pack(side="left")
        self.pace_input = ttk.Entry(pace_frame, width=5)
        self.pace_input.insert(0, tello_control.pace)
        self.pace_input.pack(side="left", padx=5)
        ttk.Button(pace_frame, text="Atualizar", command=self.update_pace).pack(side="left")

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
                # Se o arquivo não for encontrado, agora veremos um erro claro no terminal!
                print(f"ERRO DE ARQUIVO: Ícone não encontrado no caminho: '{icon_path}'")
            except Exception as e:
                # Pega qualquer outro erro que possa ocorrer ao carregar a imagem
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
        """Pousa do drone e atualiza o log."""
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

    def update_pace(self) -> None:
        """Atualiza o passo do drone com o valor inserido pelo usuário."""
        new_pace = self.pace_input.get()
        if new_pace.isdigit():
            tello_control.pace = new_pace
            print(f"Passo atualizado para: {tello_control.pace}")

    def clear_logs(self) -> None:
        """Limpa o log de comandos e a lista de mensagens."""
        self.command_log.clear()
        tello_control.log_messages.clear()
        self.log_listbox.delete(0, tk.END)
        print("Logs limpos.")

    def send_ai_command(self) -> None:
        """Envia o comando de IA para o drone com base na entrada do usuário."""
        user_text = self.text_input_entry.get()
        
        user_audio = self.audio

        frame = self.img_ai
        
        # Inicia o processamento do comando da IA em uma thread separada
        threading.Thread(target=self._process_ai, args=(user_text, user_audio, frame), daemon=True).start()
        
        self.text_input_entry.delete(0, tk.END)
        self.audio = None

    def _process_ai(self, user_text: str, user_audio: np.ndarray | None, frame: Image.Image) -> None:
        """
        Processa o comando da IA em uma thread separada.
        Args:
            user_text (str): A mensagem do usuário.
            user_audio (np.ndarray | None): O áudio do usuário.
            frame (Image.Image): O frame atual da câmera.
        """
        response, command = chatbot.run_ai(user_text, user_audio, frame)
        
        # Atualizar a interface a partir da thread principal
        user = user_text if not None else "Áudio"
        self.root.after(0, self.update_chat_display, user, response)
        
        if command and chatbot.validate_command(command):
            tello_control.process_ai_command(self.tello, command)
            self.root.after(0, self.update_log, command)

    # --- Funções de Atualização da Interface ---

    def update_video_frame(self) -> None:
        """Captura, processa e exibe um novo frame de vídeo."""
        frame = self.tello.get_frame()
        # frame = self.webcam.read()[1] # Ativar webcam
        frame = cv2.resize(frame, DISPLAY_SIZE)
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        processed_frame = tello_control.moves(self.tello, img_rgb)

        # Garante que temos um array válido antes de prosseguir.
        if isinstance(processed_frame, np.ndarray):
            self.img_ai = Image.fromarray(processed_frame)

            photo = ImageTk.PhotoImage(image=self.img_ai)
        else:
            null_img = Image.new("RGB", DISPLAY_SIZE, color="black")
            photo = ImageTk.PhotoImage(image=null_img)
        
        self.video_label.config(image=photo)
        self._video_frame = photo

        # Contagem de frames para cálculo do FPS
        self.fps_counter += 1

        # Agenda a próxima atualização
        self.root.after(15, self.update_video_frame)
        
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
        bat, height, temph, pres, time_elapsed = stats

        # Atualiza os labels
        self._update_param_label('fps', int_fps)
        self._update_param_label('battery', bat)
        self._update_param_label('height', height)
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
        Atualiza os labels do chat.
        Args:
            user_msg (str): A mensagem do usuário.
            ai_msg (str): A mensagem do drone.
        """
        self.response_label_user.config(text=f"Você: {user_msg}")
        self.response_label_ai.config(text=f"Drone: {ai_msg}")

    def _record_audio(self) -> None:
        """Função para gravar áudio em uma thread separada."""
        try:
            self.audio = sd.rec(int(AUDIO_DURATION * SAMPLE_RATE),
                                samplerate=SAMPLE_RATE,
                                channels=1,
                                dtype='int16')
            sd.wait()
            print("Gravação finalizada.")

        except Exception as e:
            print(f"Ocorreu um erro durante a gravação: {e}")
            self.audio = None # Limpa o áudio em caso de erro
        finally:
            self.is_recording = False
            
            self.root.after(0, self.reset_recording_buttons)

    def start_recording(self) -> None:
        """Inicia a gravação de áudio."""
        self.is_recording = True
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

    def _exit(self) -> None:
        """Função chamada ao fechar a janela."""
        print("Encerrando conexão...")
        self.tello.end_tello()
        self.root.destroy()
