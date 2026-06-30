"""
Módulo de Interface Gráfica para Controle do Drone.

Este módulo é responsável por criar a interface gráfica usando Tkinter,integrar 
a transmissão de vídeo da webcam e do drone, exibir os parâmetros do drone, e 
fornecer uma área de chat para interação com a LLM. Ele também gerencia os 
logs de comandos e a execução de sequências de controle geradas pela IA.

Principais Funcionalidades:
    - Transmissão de vídeo da webcam e do drone.
    - Exibição de parâmetros do drone.
    - Área de chat para interação com a LLM.
    - Gerenciamento de logs de comandos e execução de sequências.
    - Botões de controle manual (decolagem, pouso, emergência).
    - Modo de confirmação manual de comandos (desativando o Modo Automático).
"""

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


class ToolTip:
    """Classe para exibir tooltips ao passar o mouse sobre um widget."""
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tooltip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event: tk.Event | None = None) -> None:
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 25

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw, text=self.text, justify="left",
            background="#ffffe0", relief="solid", borderwidth=1,
            font=("Ubuntu", 10), wraplength=250
        )
        label.pack(ipadx=4, ipady=2)

    def _hide(self, event: tk.Event | None = None) -> None:
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


class TelloGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tello Drone Control")

        # Configurações de estilo
        self.root.configure(bg=BG_COLOR)
        self.root.geometry("1300x1200")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure('TFrame', background=BG_COLOR)
        style.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=('Ubuntu', 16))
        style.configure('Bold.TLabel', background=BG_COLOR, foreground='white', font=('Ubuntu', 16, 'bold'))
        style.configure('TButton', background='#555555', foreground='white', borderwidth=1, focusthickness=3, focuscolor='none')
        style.map('TButton', background=[('active', "#939393")])
        style.configure('TLabelframe', background=LBF_COLOR, bordercolor=TEXT_COLOR)
        style.configure('TLabelframe.Label', background=LBF_COLOR, foreground=TEXT_COLOR, font=('Ubuntu', 16))
        style.configure('TCheckbutton', background=LBF_COLOR, foreground=TEXT_COLOR, font=('Ubuntu', 12))

        # Inicializa o Tello e outros componentes
        self.tello = TelloZune()
        
        # Comentar este bloco para testar com webcam
        connected = self.tello.start_tello()

        if not connected:
            messagebox.showerror("Erro de Conexão", "Não foi possível conectar ao drone Tello.")
            self.root.destroy()
            return
        ####

        self.command_log = tello_control.log_messages
        self.webcam = cv2.VideoCapture(0)
        self.video_frame = None
        self.fps_counter = 0
        self.video_size = (800, 600)
        self.tello.set_image_size(self.video_size)
        self.last_time_fps = time.time()
        self.fps = 0
        self.is_sequence_running = False
        self.max_steps = "4"
        self.drone_height = 0 # cm
        self.abort_sequence_event = threading.Event()

        # Variáveis para confirmação manual de comandos
        self.auto_mode_var = tk.BooleanVar(value=True)
        self._confirmation_event = threading.Event()
        self._confirmation_result = False

        # Configurações de layout da janela
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=1)
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
        self.video_label = tk.Label(main_frame, anchor="n")
        self.video_label.grid(row=0, column=0, sticky="nsew")

        chat_frame = ttk.Frame(main_frame)
        chat_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        chat_frame.columnconfigure(0, weight=1)
        self._create_chat_widgets(chat_frame)

        self._create_sidebar_widgets(right_frame)
        self._create_params_widgets(right_frame)

        # --- Iniciar Loops de Atualização ---
        self.update_video_frame()
        self.update_stats()
        
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
        self.response_label_user = ttk.Label(container, text="", font=("Ubuntu", 16), wraplength=800, justify="left")
        self.response_label_user.grid(row=0, column=0, sticky="sew", pady=(0, 5))
        self.ai_response_frame = ttk.Frame(container)
        self.ai_response_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 5))
        self.ai_response_frame.rowconfigure(0, weight=1)
        self.ai_response_frame.columnconfigure(0, weight=1)
        self.response_text_ai = tk.Text(
            self.ai_response_frame,
            wrap="word",
            height=8,
            state="disabled",
            font=("Ubuntu", 16),
            bg=LBF_COLOR,
            fg=TEXT_COLOR,
            borderwidth=0,
            highlightthickness=0
        )
        self.response_text_ai.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(self.ai_response_frame, command=self.response_text_ai.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.response_text_ai.config(yscrollcommand=scrollbar.set)

        input_frame = ttk.Frame(container)
        input_frame.grid(row=2, column=0, sticky="ew", pady=5)
        input_frame.columnconfigure(0, weight=1)
        ttk.Label(input_frame, text="Envie um comando para o drone:", font=("Ubuntu", 16)).grid(row=0, column=0, columnspan=2, sticky="w")
        self.text_input_entry = ttk.Entry(input_frame)
        self.text_input_entry.grid(row=1, column=0, sticky="ew")
        self.send_text_button = ttk.Button(input_frame, text="Enviar", command=self.send_ai_command)
        self.send_text_button.grid(row=1, column=1, padx=(5,0))
        self.root.bind('<Return>', lambda event: self.send_ai_command())

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
        self.finish_button = ttk.Button(sidebar_frame, text="Fechar", command=self._exit)
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

        # --- Checkbox Modo Automático com ícone Info ---
        auto_mode_frame = ttk.Frame(sidebar_frame)
        auto_mode_frame.pack(fill='x', padx=5, pady=5)

        auto_checkbox = ttk.Checkbutton(
            auto_mode_frame,
            text="Modo Automático",
            variable=self.auto_mode_var
        )
        auto_checkbox.pack(side="left")

        info_label = tk.Label(
            auto_mode_frame,
            text="ℹ",
            fg="#6699ff",
            bg=LBF_COLOR,
            font=("Ubuntu", 14, "bold"),
            cursor="question_arrow"
        )
        info_label.pack(side="left", padx=(8, 0))

        tooltip_text = (
            "Modo Automático: Quando ativado, o drone executa todos os comandos "
            "gerados pela IA sem necessidade de confirmação.\n\n"
            "Quando desativado, cada comando requer sua aprovação manual antes "
            "de ser enviado ao drone."
        )
        ToolTip(info_label, tooltip_text)

        ttk.Separator(sidebar_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        log_frame = ttk.Frame(sidebar_frame)
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        ttk.Label(log_frame, text="Log").pack(anchor="w")

        model_frame = ttk.Frame(sidebar_frame)
        model_frame.pack(fill='x', padx=5, pady=(0,5))
        model_name = chatbot.get_model_name()
        ttk.Label(model_frame, text="Modelo: " + model_name).pack(anchor="w")
        
        self.log_listbox = tk.Listbox(log_frame, height=10)
        self.log_listbox.pack(fill='both', expand=True, side='left')
        
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_listbox.config(yscrollcommand=scrollbar.set)
        
        ttk.Button(sidebar_frame, text="Limpar Log", command=self.clear_logs).pack(fill='x', padx=5, pady=5)

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
            'battery': ("icons/battery_icon.png", "%"),
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

            value_label = ttk.Label(row_frame, text=f"N/A {unit}", font=("Ubuntu", 14, "bold"))
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
        self.show_message("Atualização", f"Número máximo de passos definido para: {self.max_steps}")

    def clear_logs(self) -> None:
        """Limpa o log de comandos"""
        self.command_log.clear()
        tello_control.log_messages.clear()
        self.log_listbox.delete(0, tk.END)
        self.tello.clear_command_queue()
        self.show_message("Log", "Log de comandos limpo.")

    def send_ai_command(self) -> None:
        """Prepara e inicia a sequência de comandos da IA em uma thread gerenciadora."""
        if self.is_sequence_running:
            self.show_message("Atenção", "Uma sequência já está em execução. Por favor, aguarde.")
            return

        user_text = self.text_input_entry.get()
        self.text_input_entry.delete(0, tk.END)

        threading.Thread(
            target=self._execute_ai_sequence,
            args=(user_text,),
            daemon=True
        ).start()

    def _get_frame(self) -> Image.Image:
        """
        Captura frame mais recente direto da thread de vídeo.
        Returns:
            Image.Image: O frame atual como uma imagem PIL.
        """
        try:
            if hasattr(self.tello, 'frame') and isinstance(self.tello.frame, np.ndarray):
                if self.tello.frame.size > 0:
                    frame = self.tello.frame.copy()
                    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    return Image.fromarray(img_rgb)
            ret, frame = self.webcam.read()
            if ret:
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                return Image.fromarray(img_rgb)
        except Exception:
            pass
    
        if hasattr(self, 'img_ai') and self.img_ai:
            return self.img_ai
        return Image.new('RGB', (640, 480), color='black')
    
    def _calculate_wait_time(self, command: str) -> float:
        """
        Calcula quanto tempo esperar baseado na física do drone.
        Args:
            command (str): O comando enviado ao drone.
        Returns:
            float: Tempo estimado em segundos para o comando completar.
        """
        if not command: return 1.0
        
        parts = command.split()
        cmd = parts[0].lower()
        val = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

        if cmd in ['cw', 'ccw']:
            return (val / 90.0) * 1.5 + 1.5
        
        if cmd in ['forward', 'back', 'left', 'right', 'up', 'down']:
            return (val / 100.0) * 1.0 + 1.5
            
        return 3.0

    # --- Funções de Confirmação Manual de Comandos ---

    def _show_command_confirmation_dialog(self, command: str) -> None:
        """
        Exibe o dialog de confirmação na thread principal.
        Deve ser chamado via root.after().
        Args:
            command (str): O comando a ser confirmado.
        """
        self._confirmation_result = False

        dialog = tk.Toplevel(self.root)
        dialog.title("Confirmação de Comando")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=LBF_COLOR)

        # Tamanho e centralização
        dialog_width = 420
        dialog_height = 140
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog_width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (dialog_height // 2)
        dialog.geometry(f"+{x}+{y}")

        # Label com a pergunta
        question_label = ttk.Label(
            dialog,
            text=f"Enviar ao drone ({command})?",
            font=("Ubuntu", 14),
            wraplength=380,
            justify="center"
        )
        question_label.pack(pady=(25, 15))

        # Frame para os botões
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=(0, 20))

        def on_accept() -> None:
            self._confirmation_result = True
            dialog.destroy()

        def on_decline() -> None:
            self._confirmation_result = False
            dialog.destroy()

        accept_btn = ttk.Button(btn_frame, text="Aceitar", command=on_accept, width=12)
        accept_btn.pack(side="left", padx=10)

        decline_btn = ttk.Button(btn_frame, text="Recusar", command=on_decline, width=12)
        decline_btn.pack(side="left", padx=10)

        # Foca no botão Aceitar por padrão
        accept_btn.focus_set()

        # Fecha com Escape (equivale a Recusar)
        dialog.bind("<Escape>", lambda e: on_decline())

        # Espera o dialog fechar
        self.root.wait_window(dialog)

        # Sinaliza a thread worker que o usuário respondeu
        self._confirmation_event.set()

    def _request_command_confirmation(self, command: str) -> bool:
        """
        Solicita confirmação do usuário para um comando.
        Deve ser chamado da thread worker. Bloqueia até o usuário responder.
        Args:
            command (str): O comando a ser confirmado.
        Returns:
            bool: True se o usuário aceitou, False se recusou.
        """
        self._confirmation_event.clear()
        self._confirmation_result = False

        # Agenda a exibição do dialog na thread principal
        self.root.after(0, self._show_command_confirmation_dialog, command)

        # Aguarda a resposta do usuário
        self._confirmation_event.wait()

        return self._confirmation_result

    # --- Execução de Sequência da IA ---

    def _execute_ai_sequence(self, user_text: str) -> None:
        """
        Roda em uma thread e gerencia o loop de múltiplos passos.
        Args:
            user_text (str): A entrada de texto do usuário.
        """
        self.is_sequence_running = True
        self.abort_sequence_event.clear()
        self.root.after(0, self._set_ui_for_sequence, True)

        MAX_STEPS = 1 if chatbot.AI_PROVIDER == 'LOCAL' else int(self.max_steps)
        current_frame = self._get_frame()
        
        last_action = "Nenhuma."

        try:
            for step in range(MAX_STEPS):
                current_frame = self._get_frame()
                
                prompt_text = user_text

                response, command, continue_route = chatbot.run_ai(
                    text=prompt_text,
                    frame=current_frame,
                    step=step,
                    height=self.drone_height,
                    last_action=last_action,
                    max_steps=MAX_STEPS
                )

                display_text = user_text if step == 0 else f"Sequência de comandos, passo {step + 1}/{MAX_STEPS}"
                self.root.after(0, self.update_chat_display, display_text, response)

                if command and chatbot.validate_command(command):
                    # --- Verifica o Modo Automático ---
                    if not self.auto_mode_var.get():
                        accepted = self._request_command_confirmation(command)
                        if not accepted:
                            self.root.after(0, self.update_log, f'{step + 1}: RECUSADO - {command}')
                            # Se estava em uma sequência, cancela ali
                            if step > 0 or continue_route:
                                break
                            # Se era um movimento simples, apenas não envia e encerra o loop
                            last_action = "Comando recusado pelo usuário."
                            break

                    last_action = command
                    tello_control.process_ai_command(self.tello, command)
                    self.root.after(0, self.update_log, f'{step + 1}: {command}')
                    
                    wait_time = self._calculate_wait_time(command)
                    
                    was_interrupted = self.abort_sequence_event.wait(wait_time)
                    if was_interrupted:
                        print("Sequência abortada durante espera.")
                        break
                else:
                    last_action = "Nenhum comando."
                    print(f"Sem comando válido no passo {step}.")
                    if not continue_route: break

                if not continue_route:
                    break
                
                if not command:
                    if self.abort_sequence_event.wait(2): break

        except Exception as e:
            print(f"Erro seq: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_sequence_running = False
            self.root.after(0, self._set_ui_for_sequence, False)

    def _set_ui_for_sequence(self, is_running: bool) -> None:
        """
        Habilita ou desabilita os controles da UI durante uma sequência.
        Args:
            is_running (bool): Indica se a sequência está em execução.
        """
        state = "disabled" if is_running else "normal"

        self.send_text_button.config(state=state)
        self.start_record_button.config(state=state)
        self.takeoff_button.config(state=state)
        self.land_button.config(state=state)
        self.max_steps_button.config(state=state)

    # --- Funções de Atualização da Interface ---

    def update_video_frame(self) -> None:
        """Captura, processa e exibe um novo frame de vídeo."""
        frame = self.tello.get_frame()
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if isinstance(img_rgb, np.ndarray):
            self.img_ai = Image.fromarray(img_rgb)
            photo = ImageTk.PhotoImage(image=self.img_ai)
        else:
            null_img = Image.new("RGB", self.video_size, color="black")
            photo = ImageTk.PhotoImage(image=null_img)
        
        self.video_label.config(image=photo)
        self._video_frame = photo

        self.fps_counter += 1
        self.root.after(33, self.update_video_frame)
        
    def update_stats(self) -> None:
        """Atualiza os valores dos parâmetros do drone."""
        now = time.time()
        time_fps = now - self.last_time_fps
        if time_fps > 0:
            self.fps = self.fps_counter / time_fps
        self.fps_counter = 0
        self.last_time_fps = now
        int_fps = int(self.fps)

        stats = self.tello.get_info()
        bat, self.drone_height, temph, pres, time_elapsed = stats

        self._update_param_label('fps', int_fps)
        self._update_param_label('battery', bat)
        self._update_param_label('height', self.drone_height) if self.drone_height is not None else self._update_param_label('height', 10)
        self._update_param_label('temp', temph)
        self._update_param_label('pres', pres)
        self._update_param_label('time', time_elapsed)

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
        
        self.log_listbox.delete(0, tk.END)
        for log in reversed(tello_control.log_messages):
            self.log_listbox.insert(0, log)

    def update_chat_display(self, user_msg: str, ai_msg: str) -> None:
        """
        Atualiza os labels do chat.
        """
        self.response_label_user.config(text=user_msg)

        self.response_text_ai.config(state="normal")
        self.response_text_ai.delete("1.0", tk.END)
        self.response_text_ai.insert(tk.END, ai_msg)
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
        """Função para parar imediatamente o drone e abortar a IA."""
        if self.abort_sequence_event:
            self.abort_sequence_event.set()
        
        self.tello.emergency_stop()
        self.update_log("Parada de emergência")

    def _exit(self) -> None:
        """Função chamada ao fechar a janela."""
        print("Encerrando conexão...")
        self.tello.end_tello()
        self.root.destroy()
