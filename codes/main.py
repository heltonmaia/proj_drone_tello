"""
Módulo Principal de Execução do Projeto de Controle de Drone Tello.

Este é o ponto de entrada do projeto, onde a interface gráfica é inicializada e 
o loop principal é executado. Ele integra os módulos de visão computacional, 
chatbot de controle e parser de comandos para criar uma experiência de controle 
inteligente e responsiva para o drone Tello. A interface é construída usando 
Tkinter, e o módulo de chatbot é responsável por processar as entradas visuais 
e gerar comandos de voo contextuais.
"""

import tkinter as tk
from interface import TelloGUI

root = tk.Tk()
app = TelloGUI(root)
root.mainloop()