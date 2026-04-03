from modules.ai_core.config import COMMAND_LIST

SYSTEM_INSTRUCTION_TEXT = f"""
VOCÊ É UM PILOTO DE DRONE TELLO.
Comandos válidos: {COMMAND_LIST}
Argumentos numéricos em cm [20-500] ou graus [1-360].
Exemplos: 'forward 100', 'cw 90', 'up 50', 'takeoff', 'land'.

SAÍDA OBRIGATÓRIA EM JSON:
{{
    "analise": "Breve descrição visual e do status em português.",
    "plano": "O que fará a seguir.",
    "comando": "comando valor" (ou "none"),
    "continua": boolean (true se a missão não acabou)
}}
"""

def get_ai_instruction(objective: str, history: str, height: int, step: int, max_steps: int) -> str:
    """
    Gera o prompt para a IA com base no contexto atual.
    Args:
        objective (str): Objetivo da missão.
        history (str): Histórico de comandos.
        height (int): Altura atual do drone em cm.
        step (int): Passo atual na sequência de comandos.
    Returns:
        str: Instrução formatada para a IA.
    """
    if step == 0:
        return f"""
            ATUAR COMO PILOTO DE DRONE TELLO (Simulação Lógica).
            Objetivo: {objective}
            Histórico: {history}
            Comandos válidos: {COMMAND_LIST}
            Altura do drone: {height} (10cm geralmente significa que está no chão)

            Comandos de voo requerem argumento numérico em cm: forward 20 (para frente 20cm)
            Comandos de rotação em graus: cw 90 (girar sentido horário 90 graus)
            Comandos que não precisam de argumento: [takeoff, land]
            Valores dos argumentos devem estar entre: [20, 500], representam a distância em cm (movimentos) ou graus [1-360] (rotações)
            Avalie se é necessário continuar a missão, se não for necessário: "continua": false

            SAÍDA OBRIGATÓRIA EM JSON:
            {{
                "analise": "Descrição visual MUITO DIRETA (Máx 20 palavras).",
                "plano": "O que fará a seguir (Use string vazia '' se não houver plano).",
                "comando": "comando valor" (Use "none" se for apenas uma resposta conversacional),
                "continua": boolean (false se a interação acabou)
            }}
            """
    else:
        return f"""
            CONTINUAÇÃO DA MISSÃO.
            Objetivo: {objective}
            Histórico: {history}
            Altura: {height} cm
            Passo: {step}/{max_steps}

            Comandos válidos: {COMMAND_LIST}

            SAÍDA OBRIGATÓRIA EM JSON:
            {{
                "analise": "Explicação breve da situação e obstáculos em português.",
                "plano": "2 próximos passos",
                "comando": "comando valor" (ex: "forward 100" ou "none"),
                "continua": boolean (true se a missão não acabou, false se acabou)
            }}
            """
    
def get_step_prompt(objective: str, last_action: str, height: int, step: int, max_steps: int) -> str:
    """
    Gera apenas o delta do prompt para o passo atual.
    Args:
        objective (str): Objetivo da missão.
        last_action (str): Última ação executada pelo drone.
        height (int): Altura atual do drone em cm.
        step (int): Passo atual na sequência de comandos.
        max_steps (int): Número máximo de passos permitidos.
    Returns:
        str: Prompt formatado para o passo atual.
    """
    return f"""
    STATUS ATUAL:
    - Objetivo Global: "{objective}"
    - Passo: {step + 1}/{max_steps}
    - Altura: {height} cm
    - Última Ação Executada: "{last_action}"
    
    Analise a imagem atual e determine o próximo comando.
    Siga a formatação JSON obrigatória.
    """
