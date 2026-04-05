"""
Módulo de Controle do Drone Tello.

Este módulo é responsável por processar os comandos gerados pela IA e enviá-los 
para o drone Tello. Ele inclui uma função de processamento de comandos que 
valida os comandos recebidos e os encaminha para o drone, garantindo que apenas 
comandos válidos sejam executados. Ele também mantém um log dos comandos 
enviados para facilitar o monitoramento e depuração.
"""

VALID_COMMANDS = [
    'takeoff', 'land', 'up', 'down', 'left', 'right', 'forward', 'back', 'cw', 'ccw'
]
response = ''
log_messages = []

def process_ai_command(tello: object, command: str) -> None:
     """
     Processa comandos da IA
     Args:
         tello (object): Objeto da classe TelloZune, que possui métodos para enviar comandos e obter estado.
         command (str): Comando a ser processado.
     """
     base_cmd = command.split()[0] if ' ' in command else command # Caso tenha espaço, pega apenas o comando
     if base_cmd in VALID_COMMANDS:
        tello.add_command(command) # type: ignore
