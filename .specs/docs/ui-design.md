# Design Visual — Como o mundo é plotado na tela

Este documento explica as decisões de como o estado da simulação é visualizado: quais bibliotecas fazem o quê, como os elementos são renderizados e por que essa abordagem foi escolhida.

---

## A ideia central: mapa fullscreen com HUD sobreposto

O Nexus Twin não é um dashboard com tabelas e gráficos. É uma visualização estilo jogo: o mapa ocupa 100% da tela e a interface de controle fica sobreposta como um HUD (Heads-Up Display — como em jogos de corrida onde a velocidade aparece sobre a cena).

```
┌─────────────────────────────────────────────────────────────┐
│  [StatsBar — barra de status no topo]                        │
│                                                              │
│                                                              │
│          mapa de SP com caminhões se movendo                 │
│          fábricas pulsando, rotas coloridas                  │
│                                                              │
│                                           ┌──────────────┐  │
│                                           │ InspectPanel │  │
│ [AgentLog — feed lateral esquerdo]        │ (ao clicar)  │  │
│                                           └──────────────┘  │
│                          [ChaosPanel — canto inferior]       │
└─────────────────────────────────────────────────────────────┘
```

Isso exige que o mapa e a interface vivam em camadas separadas. O mapa não sabe que a UI existe, e a UI não interfere nos cliques do mapa.

---

## As duas camadas de renderização

### Camada 1: MapLibre GL JS (o mapa base)

MapLibre renderiza o mapa de São Paulo — ruas, rodovias, cidades, rios. Ele fica na camada de baixo, ocupando a tela inteira.

O mapa base existe só como referência visual. Os caminhões, fábricas e rotas **não** são desenhados nele — são desenhados na camada de cima.

### Camada 2: deck.gl (os objetos da simulação)

deck.gl é uma biblioteca de visualização de dados geoespaciais criada pela Uber, desenhada exatamente para animar grandes volumes de objetos sobre um mapa em tempo real. Ela fica sobreposta ao MapLibre, no mesmo canvas WebGL.

É no deck.gl que vivem todos os elementos interativos da simulação:

- Caminhões em movimento
- Fábricas e armazéns
- Rotas coloridas por status
- Ícones de eventos de caos

As duas camadas se integram via uma "ponte" (`MapboxOverlay` do deck.gl), que sincroniza o viewport automaticamente — quando você dá zoom no mapa, os objetos do deck.gl acompanham.

---

## Como cada elemento é renderizado

### Caminhões — `TripsLayer`

O `TripsLayer` é o elemento mais importante da visualização. Ele anima objetos ao longo de trajetórias no tempo.

Cada caminhão recebe dois arrays quando inicia uma viagem:

```js
{
  // Waypoints da rota real (vindos do Valhalla)
  path: [
    [-47.06, -22.90],  // Campinas
    [-47.10, -22.95],  // 5 km adiante na Anhanguera
    [-47.18, -23.01],  // ...
    // ...200 pontos até São Paulo
    [-46.63, -23.55]   // São Paulo
  ],

  // Momento em que o caminhão estará em cada waypoint (em ms desde o início)
  timestamps: [0, 45000, 112000, ..., 5640000]
}
```

O TripsLayer interpola a posição do caminhão entre os waypoints com base no tempo atual da simulação. Isso significa que **o servidor só manda os dados uma vez** — o browser calcula a posição frame a frame sozinho, a 60fps.

O caminhão deixa um rastro (trail) que vai sumindo com o tempo, dando a sensação de movimento. O comprimento do rastro é configurável.

**Por que não atualizar a posição a cada tick do servidor?**

Se a simulação tem 20 caminhões e ticks a cada 5 segundos, mandar a posição a cada tick funcionaria. Mas a animação ficaria travada — o caminhão pularia de ponto a ponto em vez de se mover suavemente. O TripsLayer resolve isso: movimento contínuo e suave sem sobrecarregar o WebSocket.

---

### Fábricas e Armazéns — `ScatterplotLayer`

Fábricas e armazéns são círculos no mapa. O `ScatterplotLayer` renderiza milhares de círculos de forma eficiente com WebGL.

Cada nó tem:

- **Posição:** coordenada fixa (a localização da entidade no mundo)
- **Raio:** proporcional ao nível de estoque atual
- **Cor:** indica o estado de saúde

```js
// Exemplo de dados que o ScatterplotLayer recebe
[
  {
    id: "factory-campinas",
    coordinates: [-47.06, -22.9],
    radius: 800, // metros — grande quando estoque cheio
    color: [34, 197, 94], // verde = operando normalmente
  },
  {
    id: "warehouse-sp",
    coordinates: [-46.63, -23.55],
    radius: 200, // pequeno = estoque crítico
    color: [239, 68, 68], // vermelho = nível crítico
  },
];
```

O efeito visual: você vê os círculos respirando — crescendo quando produção chega, encolhendo quando estoque é consumido. Vermelho acende quando um agente precisa agir.

---

### Rotas — `PathLayer`

As rotas entre fábricas e armazéns são linhas no mapa. O `PathLayer` renderiza linhas com espessura e cor configuráveis.

Cada rota tem um status que muda em tempo real:

| Status    | Cor                | Quando                      |
| --------- | ------------------ | --------------------------- |
| Livre     | Verde `#22c55e`    | Caminhão em trânsito normal |
| Tráfego   | Amarelo `#eab308`  | Evento de lentidão          |
| Bloqueada | Vermelho `#ef4444` | Acidente, greve, tempestade |
| Inativa   | Cinza `#6b7280`    | Sem caminhão no momento     |

A cor muda quando o backend publica um evento via WebSocket. O frontend atualiza só o objeto afetado — sem redesenhar tudo.

---

### Eventos de Caos — `IconLayer`

Quando um evento disruptivo é injetado (tempestade, acidente, greve), um ícone aparece na localização do evento.

O `IconLayer` renderiza ícones georeferenciados. Cada ícone tem tipo, posição e escala:

```js
[
  {
    type: "storm",
    coordinates: [-47.3, -23.1],
    icon: "⛈", // ou SVG customizado
    scale: 1.5,
  },
  {
    type: "accident",
    coordinates: [-46.9, -23.3],
    icon: "⚠️",
    scale: 1.0,
  },
];
```

Ícones desaparecem quando o evento é resolvido.

---

## Interação: o que acontece ao clicar

deck.gl tem suporte a clique nativo em qualquer layer. Quando o usuário clica em um objeto, o deck.gl identifica qual objeto foi clicado e em qual layer.

```
Clique do usuário
  │
  ├── objeto é um caminhão (TripsLayer)?
  │     └── abre InspectPanel com:
  │           - carga atual (tipo, quantidade)
  │           - origem e destino
  │           - ETA estimado
  │           - última decisão do agente
  │
  └── objeto é um nó (ScatterplotLayer)?
        └── abre InspectPanel com:
              - tipo (fábrica / armazém / loja)
              - nível de estoque atual
              - capacidade máxima
              - caminhões a caminho
              - histórico recente de decisões do agente
```

O `InspectPanel` é um componente React normal (não tem nada de WebGL). Ele aparece como um painel lateral deslizante. Clicar fora fecha.

O detalhe importante: o clique no mapa e o clique nos elementos HTML do HUD são separados. O HUD usa `pointer-events: none` como padrão — só os elementos interativos (botões, painéis) habilitam `pointer-events: auto`. Assim, clicar "em cima" do AgentLog não bloqueia o clique no mapa.

---

## Estado global — Zustand

O `worldStore` (Zustand) centraliza o estado da simulação no frontend. Ele é atualizado via WebSocket a cada tick do backend.

```
WebSocket recebe WorldState
  └── worldStore.setState(worldState)
        ├── TrucksLayer re-renderiza com novas posições/trails
        ├── NodesLayer re-renderiza com novos raios/cores
        ├── RoutesLayer re-renderiza com novos status
        └── AgentLog adiciona novas decisões ao feed
```

Zustand foi escolhido por ser simples e performático. O deck.gl só re-renderiza as layers que receberam dados novos — não redesenha o mapa inteiro a cada tick.

---

## Paleta de cores e visual

O visual segue a estética de um painel operacional noturno — fundo escuro para destacar os elementos em movimento.

| Elemento         | Cor                                | Razão                                  |
| ---------------- | ---------------------------------- | -------------------------------------- |
| Fundo do mapa    | Tema escuro (cinza carvão)         | Destaca os elementos coloridos         |
| Caminhão (trail) | Ciano `#06b6d4`                    | Alta visibilidade no fundo escuro      |
| Nó saudável      | Verde `#22c55e`                    | Convenção universal de "ok"            |
| Nó crítico       | Vermelho `#ef4444`                 | Alerta imediato                        |
| Rota livre       | Verde translúcido                  | Não compete visualmente com caminhões  |
| Rota bloqueada   | Vermelho `#ef4444`                 | Mesma cor do nó crítico — consistência |
| HUD / painéis    | `bg-gray-900/80` + `backdrop-blur` | Painel legível sem esconder o mapa     |

---

## Por que deck.gl e não outras opções?

**Leaflet** é a biblioteca de mapas mais popular, mas não foi feita para animações em tempo real. Animar 20 caminhões com Leaflet resulta em DOM manipulation pesada e queda de performance.

**Three.js / Babylon.js** são engines 3D completas. Dariam resultado visual impressionante, mas exigiriam construir desde zero a integração com dados geoespaciais — coordenadas geográficas, projeções de mapa, etc.

**deck.gl** foi feita exatamente para este caso: visualização de dados geoespaciais em tempo real, sobre um mapa, com alta performance. A Uber a usa para visualizar milhões de corridas. Para o Nexus Twin, que tem dezenas de caminhões, é mais do que suficiente.
