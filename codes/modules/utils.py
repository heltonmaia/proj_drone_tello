import logging

def configureLogging(log_file: str = 'codes/log.txt'):
    '''
    Configura o logging para salvar mensagens em um arquivo de log.
    Args:
        log_file: Nome do arquivo de log.
    '''
    logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S"
)