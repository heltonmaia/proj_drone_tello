# **Controle Autônomo em Ambientes Fechados com Drones DJI Tello**  
## Participantes
- [Helton Maia](https://heltonmaia.com/) (professor)
- [Bruno Marques](https://sigaa.ufrn.br/sigaa/public/docente/portal.jsf?siape=1170845) (professor)
- Murilo de Lima Barros (aluno)

## **Descrição do Projeto**
Este projeto desenvolve um sistema de logística autônoma em ambientes fechados utilizando drone DJI Tello equipado com câmera para identificar e navegar com instruções do usuário. Nossa solução busca otimizar tarefas de transporte de pequenos itens, monitoramento e inventário em escritórios, galpões e etc.

## **Funcionalidades de Chatbot e Controle**

O sistema utiliza uma arquitetura de IA híbrida que combina processamento de imagem com modelos de linguagem de grande escala (LLMs) para transformar intenções do usuário em planos de voo.

* **Navegação Multi-Passo:** Diferente de comandos únicos, o sistema gerencia sequências de passos (`MAX_STEPS`), permitindo que o drone execute missões complexas como "Procure a porta e atravesse-a" de forma iterativa.
* **Gestão de Contexto e Memória:** * **OpenAI/Gemini:** Implementação de histórico de conversa dinâmico que mantém o contexto da missão sem repetir dados redundantes, otimizando o uso de tokens.
* **Stateful Control:** O chatbot recebe o estado atual (altura, último comando executado e objetivo global) para decidir o próximo movimento com base no sucesso da ação anterior.


* **Visão Espacial Auxiliada (Grid Overlay):** Antes do envio para a IA, cada frame da câmera recebe uma sobreposição de grade 3x3, fornecendo ao modelo uma referência geométrica para melhor percepção de distância e centralização de objetos.
* **Controle de Execução e Segurança:**
    * **Cálculo de Inércia:** O sistema calcula automaticamente o tempo de espera necessário para cada comando (rotações vs. translações) antes de capturar o próximo frame para análise.
    * **Abortagem Instantânea:** Interface com suporte a interrupção de sequências em tempo real via sinalizadores de eventos (`abort_sequence_event`).
    * **Validação de Comandos:** Filtro rigoroso (`fix_command` e `_snap_to_closest`) que ajusta as saídas da IA para valores aceitos pelo SDK da Tello (ex: arredondamento de ângulos e limites de distância).

## **Capacidades da IA por Provedor**

| Provedor | Modelo | Gestão de Contexto | Especialidade |
| --- | --- | --- | --- |
| **OpenAI** | `gpt-4o-mini` | Histórico em JSON com limpeza de buffer de imagem. | Baixa latência e voos curtos. |
| **Gemini** | `gemini-2.5-flash` | Sessão de chat nativa (Stateful). | Alta compreensão de contexto visual. |
| **Local** | `minicpm-v:8b` | Prompt de passo único otimizado. | Privacidade total e execução sem latência de API. |

## **Ferramentas Utilizadas**
- **Hardware:** Drone DJI Tello
- **Software:** Python, OpenCV, Tkinter
- **IA:** Chatbot baseado em modelo de linguagem (Gemini/OpenAI/Local)

## **Instalação**
```bash
# Clone o repositório
git clone https://github.com/heltonmaia/proj_drone_tello.git
cd proj_drone_tello
```

```bash
# Instale dependências
pip install -r requirements.txt
```

```bash
# Caso seja retornado erro requerendo uma biblioteca de áudio
sudo apt-get install portaudio19-dev
```

## **Uso**
1. **Conecte-se** à rede Wi‑Fi do drone DJI Tello.
2. **Execute** a interface:
    ```bash
    python3 -u main.py
    ```
3. **Na UI**:
    - Visualize o vídeo ao vivo.
    - Digite um comando na caixa de texto, ou grave um comando de voz com até 5 segundos.
    - Clique em "Enviar" ou pressione a tecla Enter na caixa de texto

## **Modelos**:
### **API**
Para usar o chatbot usando modelos via requisições:
- Crie uma chave de API OpenAI e/ou Gemini.
- Insira esta chave em um módulo de nome `utils.py` seguindo a estrutura do exemplo em `codes/modules/utils-example.py`.
- Escolha os modelos em `codes/modules/chatbot.py` alterando as variáveis `GEMINI_MODEL_NAME` e `OPENAI_MODEL_NAME`, por padrão o projeto usa `gemini-2.5-flash` e `gpt-4o-mini`, respectivamente.
- Escolha entre Gemini ou OpenAI na variável `AI_PROVIDER` no módulo `chatbot.py`.
### **Local**
Para usar um modelo localmente:
- Baixe o modelo que deseja via `ollama pull "nome_do_modelo"`, por padrão o projeto usa `minicpm-v:8b`. Antes de usá-lo, execute o comando abaixo:
    ```bash
    ollama pull minicpm-v:8b
    ```
- Em `codes/modules/chatbot.py` descomente a linha `AI_PROVIDER = 'LOCAL'`, deixando as outras opções comentadas.

## **Demonstração**
### Interface de usuário
![Tela de controle](images/interface.png)

### Controle via Chatbot
![Demonstração Chatbot](images/chatbot.gif)

[Demonstração chatbot vídeo completo](https://youtu.be/KoX4nQp3aLM)

 

 


