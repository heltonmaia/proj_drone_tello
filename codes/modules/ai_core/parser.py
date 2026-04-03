import json
import re

from modules.ai_core.config import ACCEPTED_ROTATIONS, COMMAND_LIST

def _snap_to_closest(value: int, allowed_values: list[int]) -> int:
    """
    Encontra o valor mais próximo dentro de uma lista de permitidos.
    Args:
        value (int): Valor a ser ajustado.
        allowed_values (list[int]): Lista de valores permitidos.
    Returns:
        int: Valor ajustado mais próximo.
    """
    return min(allowed_values, key=lambda x: abs(x - value))

def fix_command(raw_command: str) -> str | None:
    """
    Ajusta o comando recebido para o formato técnico esperado.
    Args:
        raw_command (str): Comando bruto recebido da IA.
    Returns:
        str | None: Comando ajustado ou None se inválido.
    """
    if not raw_command:
        return None
        
    clean_text = raw_command.lower().strip()
    
    if clean_text == "none" or not clean_text:
        return None
        
    parts = clean_text.split()
    cmd = parts[0]

    # Comandos de sistema (sem valor)
    if cmd in ['takeoff', 'land']:
        return cmd

    # Tratamento de valor
    val = 0
    
    # Comandos que requerem valor
    # Caso 1: Comando veio sem número -> Aplica padrão
    if len(parts) == 1:
        if cmd in ['cw', 'ccw']:
            val = 90
        elif cmd in ['up', 'down', 'left', 'right', 'forward', 'back']:
            val = 50
    
    # Caso 2: Comando com número -> Aplica Snapping
    elif len(parts) >= 2:
        val_str = ''.join(filter(str.isdigit, parts[1])) # Extrai apenas dígitos
        if not val_str:
            val = 90 if cmd in ['cw', 'ccw'] else 50 # Se falhar em achar número, usa padrão
        else:
            val = int(val_str)

    final_val = val

    # Rotações: Arredonda para valores aceitos
    if cmd in ['cw', 'ccw']:
        val = max(1, min(val, 360)) # Garante limites absolutos antes de arredondar
        final_val = _snap_to_closest(val, ACCEPTED_ROTATIONS)

    # Movimentos: Arredonda para múltiplos de 10
    elif cmd in ['up', 'down', 'left', 'right', 'forward', 'back']:
        final_val = int(round(val / 10.0) * 10) # Arredonda para a dezena mais próxima
        final_val = max(20, min(final_val, 500)) # Garante limites do SDK Tello (20-500)

    return f"{cmd} {final_val}"

def parse_json_response(text_response: str) -> dict:
    """
    Função unificada para parsear respostas JSON de qualquer provedor de IA.
    Args:
        text_response (str): Resposta em texto da IA.
    Returns:
        dict: Dicionário com os campos esperados.
    """
    try:
        text_response = text_response.strip()
        
        # Limpeza de markdown se houver
        if "```json" in text_response:
            text_response = text_response.split("```json")[1].split("```")[0]
        elif "```" in text_response:
             text_response = text_response.split("```")[1].split("```")[0]
        
        # Tenta carregar o JSON
        data = json.loads(text_response)
        
        return {
            "analise": data.get("analise", "Sem análise."),
            "plano": data.get("plano", ""),
            "comando": fix_command(data.get("comando")),
            "continua": data.get("continua", False)
        }
    except json.JSONDecodeError as e:
        print(f"ERRO JSON: {e}")
        print(f"Texto recebido (Raw): {text_response}")
        
        # Retorno de segurança para não travar a UI
        return {
            "analise": "Erro na comunicação (JSON Inválido). Tentando estabilizar.",
            "comando": "none",
            "continua": False
        }
    except Exception as e:
        print(f"Erro genérico no parse: {e}")
        return {
            "analise": f"Erro: {str(e)}",
            "comando": None,
            "continua": False
        }
    
def validate_command(cmd: str) -> bool:
    """
    Valida o comando recebido.
    Args:
        cmd (str): Comando recebido.
    Returns:
        bool: True se o comando for válido, False caso contrário.
    """
    if not cmd: return False
    
    parts = cmd.lower().split()
    if not parts or parts[0] not in COMMAND_LIST:
        return False

    base_cmd = parts[0]

    # Comandos de Sistema (sem argumento)
    if base_cmd in ['takeoff', 'land']:
        return len(parts) == 1

    # Comandos de Movimento/Rotação (precisam de 1 argumento numérico)
    return len(parts) == 2 and parts[1].isdigit()