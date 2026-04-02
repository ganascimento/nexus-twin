# Geo Stack — Como funciona o mapa

Este documento explica as decisões por trás da infraestrutura geoespacial do Nexus Twin: por que cada ferramenta foi escolhida, o que ela faz e como as peças se encaixam.

---

## O problema central

Queremos exibir um mapa real do estado de São Paulo e mover caminhões pelas rodovias reais (Anhanguera, Bandeirantes, Dutra, Castelo Branco, etc.). Para isso, três problemas precisam ser resolvidos de forma independente:

| Problema                            | Ferramenta escolhida              |
| ----------------------------------- | --------------------------------- |
| Exibir o mapa na tela               | MapLibre GL JS + Martin + PMTiles |
| Calcular rotas reais pelas rodovias | Valhalla                          |
| Guardar geometrias no banco         | PostGIS                           |

Cada um desses problemas tem uma solução diferente. Eles se comunicam, mas são independentes.

---

## 1. De onde vêm os dados do mapa

### OpenStreetMap

O [OpenStreetMap](https://www.openstreetmap.org) (OSM) é um projeto colaborativo — pense no Wikipedia, mas para mapas. Voluntários ao redor do mundo mapeiam ruas, rodovias, prédios, rios, pontos de interesse, tudo. Os dados são abertos e gratuitos.

O OSM disponibiliza os dados brutos para download. O site **Geofabrik** organiza esses downloads por região para facilitar. Em vez de baixar o planeta inteiro (~70 GB), você baixa só o que precisa.

Para o Nexus Twin, baixamos o extrato do **Sudeste do Brasil**:

```
https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf
```

Tamanho: ~800 MB. Formato: `.osm.pbf` (binário comprimido com todos os dados geoespaciais da região: SP, RJ, MG, ES).

---

## 2. Como o mapa chega ao browser

### O conceito de tiles

Um mapa na web não é uma imagem gigante. Ele é dividido em milhares de pedaços chamados **tiles** (azulejos). Quando você dá zoom ou move o mapa, o browser pede só os tiles da área visível.

```
Zoom 5  → poucos tiles, SP inteiro cabe na tela, sem detalhe de rua
Zoom 12 → muitos tiles, ruas visíveis, nomes de bairro
Zoom 16 → tiles bem detalhados, calçadas, numeração
```

O arquivo `.osm.pbf` contém os dados brutos — ruas, polígonos, metadados — mas o browser não sabe o que fazer com ele diretamente. Precisamos convertê-lo para um formato que o browser entenda.

### Planetiler → PMTiles

O **Planetiler** é uma ferramenta de linha de comando que lê o `.osm.pbf` e gera um arquivo **PMTiles**.

**PMTiles** é um formato de arquivo único e compacto que contém todos os tiles vetoriais do mapa organizados por índice. "Vetorial" significa que os dados são geometrias (linhas, polígonos, pontos), não imagens — isso permite customizar cores, fontes e estilos no browser em tempo real.

```bash
# Exemplo do que o Planetiler faz (roda uma vez, ~30 min)
planetiler --osm-path=sudeste.osm.pbf --output=sudeste.pmtiles
```

Resultado: um arquivo `sudeste.pmtiles` de ~2–4 GB com tudo que o mapa precisa.

### Martin

O browser não lê o `sudeste.pmtiles` diretamente — ele precisa de um servidor que responda às requisições de tiles. O **Martin** é esse servidor.

Martin é escrito em Rust, o que o torna muito rápido e com consumo de memória baixo. Ele recebe o arquivo `.pmtiles`, expõe um endpoint HTTP e responde às requisições dos tiles:

```
GET http://localhost:3001/tiles/{z}/{x}/{y}
```

O browser (via MapLibre) faz essas requisições automaticamente conforme o usuário navega no mapa.

### MapLibre GL JS

No browser, o **MapLibre GL JS** é a biblioteca que orquestra tudo. Ela:

1. Sabe a posição e zoom atual do mapa
2. Calcula quais tiles precisa carregar
3. Pede esses tiles ao Martin
4. Renderiza tudo com WebGL (aceleração por GPU)

MapLibre é open-source, mantido pela comunidade. É um fork do Mapbox GL JS feito quando o Mapbox fechou seu código-fonte. A API é praticamente idêntica.

```
Browser (MapLibre)  →  GET /tiles/12/3456/789  →  Martin  →  lê .pmtiles  →  retorna tile
```

Nenhuma chamada sai para a internet durante o uso. Tudo local.

---

## 3. Como as rotas reais são calculadas

### Valhalla

O **Valhalla** é um motor de roteamento open-source. Dado um ponto A e um ponto B, ele calcula o melhor caminho pelas vias reais do OSM.

Ele usa os mesmos dados brutos que você baixou do Geofabrik. Em um setup único, ele pré-compila esses dados em um grafo de roteamento (uma estrutura de dados otimizada para encontrar caminhos rapidamente).

```bash
# Setup único (~20 min)
valhalla_build_tiles -c valhalla.json sudeste.osm.pbf
```

Depois disso, ele expõe uma API HTTP. Quando um caminhão começa uma viagem no Nexus Twin, o backend chama:

```json
POST http://localhost:8002/route
{
  "locations": [
    { "lat": -22.9056, "lon": -47.0608 },
    { "lat": -23.5505, "lon": -46.6333 }
  ],
  "costing": "truck"
}
```

E Valhalla retorna uma lista de coordenadas — os waypoints exatos da rota pelas rodovias reais:

```json
{
  "trip": {
    "legs": [
      {
        "shape": "encodedPolyline...",
        "summary": { "length": 98.4, "time": 5640 }
      }
    ]
  }
}
```

O `shape` é uma polyline codificada (formato compacto) que, decodificada, dá centenas de pares `[lat, lon]` representando o trajeto real — incluindo curvas, trechos da Anhanguera, trechos da Bandeirantes, etc.

O parâmetro `"costing": "truck"` faz o Valhalla considerar restrições específicas de caminhões: peso máximo por via, altura máxima em viadutos, proibições de acesso.

### Por que Valhalla e não OSRM?

**OSRM** é outro motor de roteamento popular, mais rápido em consultas individuais. Mas para este projeto Valhalla foi escolhido por:

- **Setup mais simples:** OSRM exige pré-processamento mais pesado em memória RAM para o extrato do Sudeste
- **Restrições de caminhão:** Valhalla tem suporte nativo a peso, altura, e tipo de carga
- **Flexibilidade:** Valhalla suporta rotas multi-modal e otimização de múltiplos pontos de parada (útil para entregar em vários armazéns)

---

## 4. PostGIS — geometrias no banco de dados

O PostgreSQL por padrão não sabe o que é uma coordenada geográfica. O **PostGIS** é uma extensão que adiciona tipos de dados geoespaciais e funções para trabalhar com eles.

Com PostGIS você pode fazer queries como:

```sql
-- Caminhões a menos de 50 km de São Paulo
SELECT truck_id FROM trucks
WHERE ST_Distance(position, ST_Point(-46.63, -23.55)::geography) < 50000;

-- Interseção de rota com área de tempestade
SELECT route_id FROM routes
WHERE ST_Intersects(path, storm_polygon);
```

No Nexus Twin, PostGIS guarda:

- Posição atual de cada caminhão (ponto geográfico)
- Rotas completas como `LINESTRING` (geometria de linha com todos os waypoints)
- Polígonos de eventos de caos (áreas afetadas por tempestade, greve, etc.)

---

## 5. Como tudo se conecta em runtime

```
Startup (uma vez)
├── Martin carrega sudeste.pmtiles
├── Valhalla carrega o grafo de rotas compilado
└── Backend conecta ao PostGIS

Usuário abre o browser
├── MapLibre inicia e pede tiles ao Martin
└── Mapa de SP aparece na tela

Caminhão inicia viagem (ex: Campinas → São Paulo)
├── Backend chama Valhalla: POST /route {Campinas, São Paulo, costing: truck}
├── Valhalla retorna ~200 waypoints pelas rodovias reais
├── Backend calcula timestamps por waypoint (distância ÷ velocidade)
├── Salva {truck_id, path, timestamps} no PostGIS
└── Envia via WebSocket para o frontend

Frontend recebe os dados
├── deck.gl TripsLayer recebe path + timestamps
└── Anima o caminhão ao longo da rota a 60fps
   (interpolação suave entre waypoints, sem novas requisições ao servidor)
```
