import tkinter as tk
from tkinter import ttk, font, Listbox, END
from PIL import Image, ImageTk
import cv2
import numpy as np
import modules.tello_control as tello_control
import modules.chatbot as chatbot
from tello_zune import TelloZune
import threading

class TelloApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Tello Drone Control")

        # Configurações de estilo
        BG_COLOR = "#262626"
        TEXT_COLOR = "#FFFFFF"
        LBF_COLOR = "#3c3c3c"
        self.root.configure(bg=BG_COLOR)
        self.root.geometry("1200x850")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure('TFrame', background=BG_COLOR)
        style.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=('Ubuntu', 10))
        style.configure('Bold.TLabel', background=BG_COLOR, foreground='white', font=('Ubuntu', 11, 'bold')) # Um estilo customizado para negrito
        style.configure('TButton', background='#555555', foreground='white', borderwidth=1, focusthickness=3, focuscolor='none')
        style.map('TButton', background=[('active', "#939393")]) # Cor quando o mouse está sobre
        style.configure('TLabelframe', background=LBF_COLOR, bordercolor=TEXT_COLOR)
        style.configure('TLabelframe.Label', background=LBF_COLOR, foreground=TEXT_COLOR, font=('Ubuntu', 11))

        # Inicializa o Tello e outros componentes
        self.tello = TelloZune()
        # self.tello.start_tello()
        self.command_log = tello_control.log_messages
        tello_control.pace = "50" # Valor inicial do passo
        self.webcam = cv2.VideoCapture(0) # Inicializa a webcam

        # Configurações de layout da janela
        self.root.columnconfigure(0, weight=3) # Coluna do vídeo (75%)
        self.root.columnconfigure(1, weight=1) # Coluna de controle (25%)
        self.root.rowconfigure(0, weight=1)

        # Frame principal para o vídeo e chat
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=0)
        main_frame.columnconfigure(0, weight=1)

        # Frame da direita para controles e parâmetros
        right_frame = ttk.Frame(self.root)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        right_frame.rowconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # --- Componentes da Interface ---
        # Label para o vídeo
        self.video_label = tk.Label(main_frame, text="Iniciando câmera...", anchor="center")
        self.video_label.grid(row=0, column=0, sticky="nsew")

        # Container para chat
        chat_container = ttk.Frame(main_frame)
        chat_container.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        chat_container.columnconfigure(0, weight=1)
        self._create_chat_widgets(chat_container)

        # Container para controles (sidebar) e parâmetros
        self._create_sidebar_widgets(right_frame)
        self._create_params_widgets(right_frame)

        # --- Iniciar Loops de Atualização ---
        self.update_video_frame()
        self.update_stats()
        
        # Garantir que o drone pouse ao fechar a janela
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_chat_widgets(self, container):
        """Cria a área de input e display do chat."""
        # Display da resposta
        self.response_label_user = ttk.Label(container, text="", font=("Ubuntu", 10, "bold"))
        self.response_label_user.grid(row=0, column=0, sticky="w")
        self.response_label_ai = ttk.Label(container, text="", wraplength=700) # wraplength quebra a linha
        self.response_label_ai.grid(row=1, column=0, sticky="w")
        
        # Input do usuário
        input_frame = ttk.Frame(container)
        input_frame.grid(row=2, column=0, sticky="ew", pady=5)
        input_frame.columnconfigure(0, weight=1)
        
        ttk.Label(input_frame, text="Envie um comando para o drone:").grid(row=0, column=0, columnspan=2, sticky="w")
        self.user_input_entry = ttk.Entry(input_frame)
        self.user_input_entry.grid(row=1, column=0, sticky="ew")
        self.send_button = ttk.Button(input_frame, text="Enviar", command=self.send_ai_command)
        self.send_button.grid(row=1, column=1, padx=(5,0))
        self.root.bind('<Return>', lambda event: self.send_ai_command()) # Enviar com Enter

    def _create_sidebar_widgets(self, container):
        """Cria os botões de controle e o log de comandos."""
        sidebar_frame = ttk.LabelFrame(container, text="Controles")
        sidebar_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        sidebar_frame.columnconfigure(0, weight=1)
        
        ttk.Button(sidebar_frame, text="Decolar", command=self.takeoff).pack(fill="x", padx=5, pady=2)
        ttk.Button(sidebar_frame, text="Pousar", command=self.land).pack(fill="x", padx=5, pady=2)
        ttk.Button(sidebar_frame, text="Encerrar Drone", command=self._on_closing).pack(fill="x", padx=5, pady=5)

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
        
        self.log_listbox = Listbox(log_frame, height=10)
        self.log_listbox.pack(fill='both', expand=True, side='left')
        
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_listbox.config(yscrollcommand=scrollbar.set)
        
        ttk.Button(sidebar_frame, text="Limpar Logs", command=self.clear_logs).pack(fill='x', padx=5, pady=5)

    def _create_params_widgets(self, container):
        """
        Cria a exibição de parâmetros do drone.
        """
        params_frame = ttk.LabelFrame(container, text="Parâmetros")
        params_frame.grid(row=1, column=0, sticky="nsew")

        self.param_icons = {}
        self.param_labels = {}
        
        params_info = {
            'battery': ("images/battery_icon.png", "%"),
            'height': ("images/height_icon.png", "cm"),
            'temp': ("images/temp_icon.png", "°C"),
            'pres': ("images/pressure_icon.png", "hPa"),
            'time': ("images/time_icon.png", "s")
        }

        for i, (key, (icon_path, unit)) in enumerate(params_info.items()):
            row_frame = ttk.Frame(params_frame)
            row_frame.pack(fill='x', padx=5, pady=5)
            
            try:
                # Tenta abrir a imagem a partir do caminho especificado
                img = Image.open(icon_path).resize((30, 30), Image.Resampling.LANCZOS)
                
                # Cria o objeto de imagem do Tkinter e o armazena no nosso dicionário
                photo_image = ImageTk.PhotoImage(img)
                self.param_icons[key] = photo_image
                
                # Cria o Label para o ícone
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


    # --- Funções de Controle (Lógica dos botões) ---
    
    def takeoff(self):
        self.tello.add_command("takeoff")
        self.update_log("takeoff")

    def land(self):
        self.tello.add_command("land")
        self.update_log("land")

    def update_pace(self):
        new_pace = self.pace_input.get()
        if new_pace.isdigit():
            tello_control.pace = new_pace
            print(f"Passo atualizado para: {tello_control.pace}")

    def clear_logs(self):
        self.command_log.clear()
        tello_control.log_messages.clear()
        self.log_listbox.delete(0, END)

    def send_ai_command(self):
        user_input = self.user_input_entry.get()
        if not user_input:
            return

        # frame = self.tello.get_frame()
        frame = self.webcam.read()[1]  # Lê o frame da webcam
        current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Inicia o processamento do comando da IA em uma thread separada
        threading.Thread(target=self._process_ai, args=(user_input, current_frame), daemon=True).start()
        
        self.user_input_entry.delete(0, END)

    def _process_ai(self, user_input, frame):
        """Processa o comando da IA em uma thread separada."""
        response, command = chatbot.run_ai(user_input, frame)
        
        # Atualizar a interface a partir da thread principal
        self.root.after(0, self.update_chat_display, user_input, response)
        
        if command and chatbot.validate_command(command):
            tello_control.process_ai_command(self.tello, command)
            self.root.after(0, self.update_log, command)

    # --- Funções de Atualização da Interface ---

    def update_video_frame(self):
        """Captura e exibe um novo frame do drone."""
        # frame = self.tello.get_frame()
        frame = self.webcam.read()[1]
        
        processed_frame = tello_control.moves(self.tello, frame)
        
        array_frame = None
        if isinstance(processed_frame, (list, tuple)):
            array_frame = np.array(processed_frame)
        elif isinstance(processed_frame, np.ndarray):
            array_frame = processed_frame

        if isinstance(array_frame, np.ndarray) and array_frame.ndim == 3:
            img = cv2.cvtColor(array_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            photo = ImageTk.PhotoImage(image=img)
        else:
            # Se processed_frame não for válido, exibe um frame preto
            img = Image.new("RGB", (640, 480), color="black")
            photo = ImageTk.PhotoImage(image=img)
        
        self.video_label.config(image=photo)
        self._video_image_ref = photo  # Manter referência para não ser limpo pelo garbage collector
        
        # Agendar a próxima atualização (aprox. 30 FPS)
        self.root.after(33, self.update_video_frame)
        
    def update_stats(self):
        """Atualiza os valores dos parâmetros do drone."""
        stats = self.tello.get_info()
        bat, height, temph, pres, time_elapsed = stats

        # Atualiza os labels
        self._update_param_label('battery', bat)
        self._update_param_label('height', height)
        self._update_param_label('temp', temph)
        self._update_param_label('pres', pres)
        self._update_param_label('time', time_elapsed)

        # Agendar a próxima atualização a cada segundo
        self.root.after(1000, self.update_stats)

    def _update_param_label(self, key, value):
        if key in self.param_labels:
            label, unit = self.param_labels[key]
            text = f"{value if value is not None else 'N/A'} {unit}"
            label.config(text=text)

    def update_log(self, message):
        """Adiciona uma mensagem ao log na interface."""
        tello_control.log_messages.append(message)
        
        # Atualiza a Listbox
        self.log_listbox.delete(0, END)
        for log in reversed(tello_control.log_messages):
            self.log_listbox.insert(0, log)

    def update_chat_display(self, user_msg, ai_msg):
        """Atualiza os labels do chat."""
        self.response_label_user.config(text=f"Você: {user_msg}")
        self.response_label_ai.config(text=f"Drone: {ai_msg}")

    def _on_closing(self):
        """Função chamada ao fechar a janela."""
        print("Encerrando conexão...")
        self.tello.end_tello()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TelloApp(root)
    root.mainloop()