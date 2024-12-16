# **Logística Autônoma em Ambientes Fechados com Drones DJI Tello**  
## Participantes
- [Helton Maia](https://heltonmaia.com/) (professor)
- [Bruno Marques](https://sigaa.ufrn.br/sigaa/public/docente/portal.jsf?siape=1170845) (professor)
- Murilo de Lima Barros (aluno)

## **Descrição do Projeto**  
Este projeto tem como objetivo desenvolver um sistema de logística autônoma em ambientes fechados utilizando drones DJI Tello equipados com câmeras para identificar e navegar até QR codes. A proposta visa otimizar tarefas como transporte de pequenos itens, monitoramento e inventário em locais como escritórios, galpões e hospitais, oferecendo uma solução eficiente, flexível e de baixo custo.  

## **Principais Funcionalidades em Desenvolvimento:**  
- **Detecção de QR Codes:**  
   - Uso de algoritmos de visão computacional com OpenCV para identificar QR codes em tempo real e extrair informações relevantes.  
- **Navegação Autônoma:**  
   - Controle do drone para deslocamento preciso até o QR code identificado, incluindo desvio de obstáculos.  
- **Gestão de Rotas:**  
   - Otimização das trajetórias para múltiplos pontos de entrega ou coleta.  

## **Ferramentas Utilizadas:**  
- **Hardware:** Drone DJI Tello.  
- **Software:** Python, OpenCV, PyTello SDK.  
- **Algoritmos:** Detecção de QR codes, planejamento de trajetórias e controle autônomo.  

## **Status Atual:**  
- Desenvolvimento inicial do algoritmo de navegação baseado em visão computacional.  
- Testes em cenários controlados, simulando transporte de pequenos objetos. 
- Melhoria do desempenho. 

## **Próximos Passos:**  
- Melhorar a precisão da navegação autônoma.  
- Integrar um sistema de gerenciamento de múltiplas rotas.  
- Realizar testes extensivos em ambientes reais, como escritórios e pequenos armazéns.  

O projeto busca transformar processos logísticos internos, promovendo eficiência, automação e acessibilidade. Além disso, oferece uma oportunidade de aprendizado prático em áreas como visão computacional, robótica e inteligência artificial.  

Este projeto está em constante evolução. Qualquer contribuição ou feedback será muito bem-vindo!

## **Utilização:**
### Instalação

```bash
# Clone o repositório
git clone https://github.com/heltonmaia/proj_drone_tello
```

```bash
# Instalar dependências
pip install opencv-python
pip install pyzbar
pip install tello_zune
```

### Funcionamento
Com base na detecção de um QR code, o algoritmo envia comandos ao drone via wi-fi e processa dados recebidos da mesma forma. Ao conectar-se ao drone, basta executar o módulo main.py. Recomenda-se um local bem iluminado, para que o drone receba imagens nítidas e possa navegar adequadamente.
Se o drone ler algum comando com passo, como "down 20", sendo o passo definido pelo usuário, o movimento será feito logo em seguida, caso não haja detecção por um período de tempo definido previamente o drone fará rotações em torno do próprio eixo na tentativa de encontrar um código válido. Caso o drone leia o comando "follow", o drone ajustará a própria posição com base nas coordenadas da detecção capturada.

#### Exemplos de comandos válidos:

| Comando         | Descrição                    |
|-----------------|------------------------------|
| `takeoff`       | Decolar                      |
| `land`          | Pousar                       |
| `up x`          | Subir x cm                   |
| `down x`        | Descer x cm                  |
| `right x`       | Mover-se à direita x cm      |
| `left x`        | Mover-se à esquerda x cm     |
| `forward x`     | Mover-se para frente x cm    |
| `back x`        | Mover-se para trás x cm      |
| `follow`        | Seguir                       |

---

Exemplo de funcionamento

![vídeo](video.gif)



