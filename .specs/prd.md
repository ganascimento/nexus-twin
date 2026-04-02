# Nexus Twin — Product Requirements Document

## 1. Visão do Produto

Nexus Twin é um **mundo fechado e autônomo** que simula uma cadeia de suprimentos real. A inspiração é direta: um RPG onde cada entidade do mundo — fábricas, armazéns, lojas, caminhões — é um NPC com inteligência própria, objetivos claros e capacidade de se comunicar com outros NPCs para resolver seus problemas.

A diferença para um RPG tradicional: o "mundo" aqui é uma cadeia de suprimentos de **materiais de construção** sobre o mapa real do estado de São Paulo, e os NPCs são agentes de IA autônomos. O usuário não controla os agentes — ele **observa**, **monitora**, **injeta caos** e pode **moldar o mundo** (criar ou remover entidades) para ver como o ecossistema reage e se adapta.

> **Em uma frase:** Um RPG de supply chain onde os NPCs são autônomos e precisam se virar — e o game master define quais materiais existem no mundo.

---

## 2. Definição de Tick

Um **tick** é a unidade de tempo da simulação. Ele tem dois valores:

| Dimensão           | Valor                                                                    |
| ------------------ | ------------------------------------------------------------------------ |
| **Tempo real**     | 10 segundos mínimo (intervalo entre execuções do engine; ajustável pelo usuário) |
| **Tempo simulado** | 1 hora do mundo fictício                                                 |

### Implicações práticas

| Evento                                     | Duração em ticks                       |
| ------------------------------------------ | -------------------------------------- |
| Viagem Campinas → São Paulo (~100 km)      | 2 ticks (2h simuladas)                 |
| Viagem Sorocaba → Ribeirão Preto (~290 km) | 5 ticks                                |
| Manutenção de caminhão                     | Proporcional à degradação (ver abaixo) |
| Evento de caos curto (ex: tempestade)      | 4–8 ticks                              |
| Evento de caos longo (ex: greve)           | 12–24 ticks                            |
| "Próximos dias" nas decisões de loja       | 24 ticks = 1 dia simulado              |

Quando o PRD fala em "próximos dias" ou "N ticks", o N refere-se a ticks simulados. O engine avança 1 tick a cada 10 segundos de tempo real no mínimo — a velocidade pode ser ajustada pelo usuário no dashboard.

### Separação entre física e ciclo de agentes

O tick atualiza física (posições, estoques, tempo) de forma síncrona e sem IA. Agentes LLM são disparados em background (fire-and-forget) apenas quando há gatilho ativo — o tick não espera suas respostas.

| Tipo de agente | Quando acorda o LLM |
| -------------- | ------------------- |
| **Caminhão em trânsito** | Somente em eventos: rota bloqueada, chegada ao destino, quebra, nova ordem |
| **Caminhão idle** | Quando há proposta de contratação disponível |
| **Loja / Armazém / Fábrica** | Quando a projeção indica que o estoque vai cruzar o nível mínimo (reorder_point / min_stock) antes da reposição chegar — `(stock[p] - min_stock[p]) / demand_rate[p] < lead_time_ticks × 1.5` — para qualquer produto `p` gerenciado pela entidade |

Isso garante que caminhões em rota normal não consomem tokens e que lojas/armazéns acordam **antes** do crítico, com tempo de reagir.

---

## 3. Catálogo de Materiais

O mundo opera sobre um **catálogo dinâmico de materiais**. Materiais não são hardcoded — o usuário pode criar novos materiais a qualquer momento. Fábricas, armazéns e lojas são sempre configurados em cima dos materiais cadastrados no catálogo.

### Atributos de um Material

| Atributo    | Descrição                                                                        |
| ----------- | -------------------------------------------------------------------------------- |
| `id`        | Identificador único (slug, ex: `tijolos`, `cimento`, `vergalhao`)                |
| `name`      | Nome de exibição (ex: "Tijolos", "Cimento Portland", "Vergalhão de Ferro")       |
| `is_active` | Se o material está ativo no mundo; materiais inativos não aparecem nos combos     |

### Materiais do Mundo Padrão (Seed)

O sistema inicia com 3 materiais pré-cadastrados. Novos materiais podem ser adicionados pelo usuário a qualquer momento.

| ID            | Nome                  |
| ------------- | --------------------- |
| `tijolos`     | Tijolos               |
| `vergalhao`   | Ferro (vergalhão)     |
| `cimento`     | Cimento               |

> Todos os materiais são medidos em toneladas. Isso permite que a capacidade dos caminhões (`capacity_tons`) seja usada diretamente para calcular quanto cabe de qualquer produto, sem conversão. Para referência: 1 ton ≈ 400 tijolos ≈ 20 sacos de cimento de 50 kg.

> O catálogo é a **fonte única de verdade** para os tipos de material. Qualquer vínculo de fábrica, armazém ou loja com um material referencia o `id` do catálogo. Ao criar ou editar uma fábrica, armazém ou loja no dashboard, um combo box exibe os materiais cadastrados e ativos no catálogo.

---

## 4. Mundo Padrão (Default World)

O sistema sempre inicia com um mundo pré-populado e funcional — sem configuração manual. As entidades abaixo existem ao iniciar a simulação pela primeira vez.

### Fábricas do Mundo Padrão

As fábricas do seed são configuradas com um único produto cada — mas o modelo suporta múltiplos. Produtos referenciam o catálogo da seção 3.

| ID            | Nome                 | Produtos (catálogo)         | Localização         | Estoque Inicial | Produção máx/tick | Estoque máximo |
| ------------- | -------------------- | --------------------------- | ------------------- | --------------- | ----------------- | -------------- |
| `factory-001` | Tijolaria Anhanguera | `tijolos`                   | Campinas (SP-330)   | 12 ton          | 2 ton/tick        | 30 ton         |
| `factory-002` | Aciaria Sorocabana   | `vergalhao`                 | Sorocaba (SP-280)   | 2.000 ton       | 120 ton/tick      | 5.000 ton      |
| `factory-003` | Cimenteira Paulista  | `cimento`                   | Votorantim (SP-280) | 400 ton         | 30 ton/tick       | 750 ton        |

> **Produção máx/tick** e **Estoque máximo** são definidos por produto (`Dict[material_id, valor]`). A fábrica nunca produz acima do teto por produto em um único tick. O agente decide quanto produzir de cada produto a cada ciclo (0 até o máximo). Se o estoque de um produto atinge o máximo, apenas aquele produto é bloqueado — os demais continuam.

### Armazéns do Mundo Padrão

| ID              | Nome             | Região          | Localização     | Capacidade total | Estoque inicial (Tijolos / Ferro / Cimento) | Mínimo por produto (Tijolos / Ferro / Cimento) |
| --------------- | ---------------- | --------------- | --------------- | ---------------- | ------------------------------------------- | ---------------------------------------------- |
| `warehouse-001` | Hub Norte        | Interior Norte  | Ribeirão Preto  | 800 ton          | — / 500 ton / 100 ton                       | — / 100 ton / 20 ton                           |
| `warehouse-002` | Hub Centro-Oeste | Grande SP Oeste | Jundiaí         | 1.000 ton        | 10 ton / 800 ton / 150 ton                  | 2 ton / 150 ton / 25 ton                       |
| `warehouse-003` | Hub Leste        | Grande SP Leste | Mogi das Cruzes | 600 ton          | 6 ton / 400 ton / 75 ton                    | 1 ton / 80 ton / 15 ton                        |

> Estoque é rastreado por produto — um armazém pode estar cheio de tijolos e zerado de ferro simultaneamente. "Mínimo por produto" é o nível de referência para o gatilho preditivo: o agente acorda quando a projeção de consumo indica que vai atingir esse nível antes da reposição chegar, não quando ele é efetivamente cruzado.

### Lojas do Mundo Padrão

Todas são **lojas de materiais de construção**. Os produtos vendidos referenciam o catálogo da seção 3 — no seed, cada loja é configurada com um subconjunto dos 3 materiais iniciais.

Todas as quantidades estão em **toneladas**.

| ID          | Nome                  | Localização          | Produtos que vende      | Demanda/tick (normal)            | Estoque inicial                  | Mínimo por produto (reorder point) |
| ----------- | --------------------- | -------------------- | ----------------------- | -------------------------------- | -------------------------------- | ---------------------------------- |
| `store-001` | Constrular Centro     | São Paulo (Centro)   | Tijolos, Ferro, Cimento | 0,5 ton / 30 ton / 7,5 ton       | 1,5 ton / 90 ton / 22,5 ton      | 1 ton / 60 ton / 15 ton            |
| `store-002` | Constrular Zona Leste | São Paulo (Itaquera) | Tijolos, Cimento        | 0,4 ton / — / 5 ton              | 1 ton / — / 15 ton               | 1 ton / — / 10 ton                 |
| `store-003` | Constrular Campinas   | Campinas             | Tijolos, Ferro          | 0,3 ton / 20 ton / —             | 1 ton / 60 ton / —               | 1 ton / 40 ton / —                 |
| `store-004` | Material Norte        | Ribeirão Preto       | Cimento, Ferro          | — / 25 ton / 6 ton               | — / 75 ton / 18 ton              | — / 50 ton / 12 ton                |
| `store-005` | Depósito Paulista     | Guarulhos            | Tijolos, Cimento, Ferro | 0,5 ton / 28 ton / 6,5 ton       | 1,5 ton / 84 ton / 20 ton        | 1 ton / 56 ton / 13 ton            |

> **Reorder point:** o agente acorda quando a projeção indica que o estoque vai cruzar o `reorder_point` antes da entrega chegar — calculado a cada tick como `(stock[p] - reorder_point[p]) / demand_rate[p] < lead_time_ticks × 1.5` para qualquer produto `p`. A condição é avaliada por produto de forma independente. Estoque inicial ≈ 3× a demanda/tick (cobertura de 3 ticks, ~3h simuladas). O pedido de reposição cobre 5× a demanda/tick para garantir margem.

### Caminhões do Mundo Padrão

| ID          | Tipo         | Capacidade | Vínculo              | Produto principal | Base           | Degradação inicial |
| ----------- | ------------ | ---------- | -------------------- | ----------------- | -------------- | ------------------ |
| `truck-001` | Proprietário | 15 ton     | Tijolaria Anhanguera | Tijolos           | Campinas       | 20%                |
| `truck-002` | Proprietário | 20 ton     | Cimenteira Paulista  | Cimento           | Votorantim     | 15%                |
| `truck-003` | Proprietário | 12 ton     | Aciaria Sorocabana   | Ferro             | Sorocaba       | 30%                |
| `truck-004` | Terceiro     | 18 ton     | — (livre)            | Qualquer          | São Paulo      | 10%                |
| `truck-005` | Terceiro     | 22 ton     | — (livre)            | Qualquer          | Campinas       | 25%                |
| `truck-006` | Terceiro     | 10 ton     | — (livre)            | Qualquer          | Ribeirão Preto | 40%                |

> Caminhões proprietários transportam exclusivamente os produtos da fábrica vinculada. Caminhões terceiros aceitam qualquer produto — a decisão de qual carga aceitar é autônoma (ver seção 5, Caminhão).

### 4.1 Mapeamento Fábrica → Armazéns Parceiros

Cada fábrica tem armazéns parceiros preferidos — os hubs que ela abastece por padrão. O agente da fábrica prioriza esses armazéns ao decidir para onde enviar produção, mas pode enviar para outros se os parceiros estiverem lotados.

| Fábrica                  | Produto | Armazéns parceiros (preferência)                                                | Critério geográfico                                               |
| ------------------------ | ------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `factory-001` Tijolaria  | Tijolos | `warehouse-002` (Jundiaí) → `warehouse-003` (Mogi)                              | Campinas conecta direto pela Anhanguera/Bandeirantes              |
| `factory-002` Aciaria    | Ferro   | `warehouse-002` (Jundiaí) → `warehouse-001` (Ribeirão)                          | Sorocaba acessa Jundiaí pela SP-280; Ribeirão via Anhanguera      |
| `factory-003` Cimenteira | Cimento | `warehouse-001` (Ribeirão) → `warehouse-002` (Jundiaí) → `warehouse-003` (Mogi) | Votorantim abastece todos — produto com maior demanda distribuída |

**Regra de fallback:** se todos os armazéns parceiros estiverem com estoque acima de 80% da capacidade **e não houver pedido de reabastecimento urgente pendente de nenhum parceiro**, a fábrica para a produção ou reduz ao mínimo — não faz sentido produzir sem destino.

**Exceção anti-deadlock:** se qualquer armazém parceiro tiver um `pending_order` com status `pending` ou `confirmed` direcionado a esta fábrica, a regra de 80% é ignorada para aquele produto específico — a fábrica mantém produção suficiente para atender o pedido mesmo que o armazém ainda esteja acima de 80%. Isso evita o deadlock circular em que o armazém esvaziou após o evento de caos mas a fábrica continua parada porque os outros parceiros ainda estão cheios.

**Armazéns não-parceiros:** a fábrica pode enviar para um armazém fora da lista se ele emitir um pedido de reabastecimento urgente e nenhum caminhão estiver disponível para os parceiros. Isso é excepcional e decidido autonomamente pelo agente.

---

## 5. Os Atores do Mundo (NPCs)

Cada ator tem uma identidade, responsabilidades únicas e se comunica com os outros para atingir seus objetivos.

---

### Fábrica

**Quem é:** Produtora de um ou mais materiais cadastrados no catálogo (seção 3). Tem capacidade produtiva por produto, estoque de saída e um plantel de caminhões próprios.

**Atributos:**

| Atributo                    | Descrição                                                                                        |
| --------------------------- | ------------------------------------------------------------------------------------------------ |
| `products`                  | `List[material_id]` — materiais que esta fábrica produz (referencia o catálogo, seção 3)         |
| `stock`                     | `Dict[material_id, quantidade]` — estoque atual no galpão de saída por produto                  |
| `stock_max`                 | `Dict[material_id, quantidade]` — capacidade máxima por produto; se atingida, produção para      |
| `production_rate_max`       | `Dict[material_id, quantidade_por_tick]` — teto físico de produção por produto por tick          |
| `production_rate_current`   | `Dict[material_id, quantidade_por_tick]` — quanto o agente decidiu produzir neste tick (0 até max) |
| `status`                    | `operating` / `stopped` / `reduced_capacity` (ex: quebra de máquina)                             |
| `trucks_owned`              | `List[truck_id]` — caminhões proprietários vinculados a esta fábrica                             |
| `partner_warehouses`        | `List[warehouse_id]` — armazéns que esta fábrica abastece (ver seção 4.1)                        |

> Ao criar ou editar uma fábrica no dashboard, o usuário seleciona quais materiais ela produz a partir de um combo com os materiais ativos no catálogo (seção 3).

**Mecânica de produção:**

A fábrica produz a cada tick, para cada produto, a quantidade definida por `production_rate_current[produto]`. O agente escolhe esse valor livremente entre 0 e `production_rate_max[produto]`:

- **Parar (0):** quando os armazéns parceiros estão cheios e não há demanda pendente.
- **Produção parcial:** quando há demanda moderada ou estoque de saída perto do limite.
- **Produção máxima:** quando há pedidos urgentes ou estoque dos armazéns está crítico.

Se `stock[produto]` atinge `stock_max[produto]`, a produção daquele produto é bloqueada automaticamente pelo engine — o agente não precisa gerenciar isso, mas deve antever e reduzir produção antes de lotar. Cada produto é gerenciado independentemente.

**Seus objetivos:**

- Manter produção alinhada com a demanda real (não produzir em excesso nem ficar sem estoque)
- Distribuir o estoque produzido de forma eficiente entre os armazéns parceiros
- Priorizar caminhões próprios antes de contratar terceiros

**Com quem se comunica:**

- **Lojas** → recebe pedidos de compra direto (caso excepcional)
- **Armazéns** → decide para qual armazém enviar cada lote produzido
- **Caminhões proprietários** → aciona primeiro para transporte
- **Caminhões terceiros** → contrata quando frota própria está ocupada ou insuficiente

**Perguntas que o agente responde a cada ciclo:**

- "Qual a demanda agregada dos armazéns parceiros? Quanto devo produzir este tick?"
- "Meu estoque de saída está perto do limite? Devo reduzir ou parar a produção?"
- "Qual armazém está com mais capacidade livre para receber minha produção?"
- "Preciso contratar um caminhão terceiro ou minha frota própria dá conta?"

---

### Armazém (Galpão)

**Quem é:** Hub de distribuição regional. Recebe estoque das fábricas e abastece as lojas da sua região. Opera com os materiais que foram configurados para ele (selecionados a partir do catálogo, seção 3).

> Ao criar ou editar um armazém no dashboard, o usuário seleciona os materiais aceitos a partir de um combo com os materiais ativos no catálogo.

**Atributos:**

| Atributo         | Descrição                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------- |
| `capacity_total` | Capacidade máxima combinada de todos os produtos (em unidades equivalentes)                 |
| `stock`          | `Dict[produto, quantidade]` — estoque atual por produto                                     |
| `min_stock`      | `Dict[produto, quantidade]` — nível mínimo por produto; o agente acorda quando a **projeção** indica que vai atingir este nível antes da reposição chegar (não espera cruzar o limite) |
| `region`         | Zona geográfica de atendimento (define quais lojas são "suas")                              |
| `pending_orders` | Lista de pedidos de lojas aguardando atendimento                                            |
| `status`         | `operating` / `rationing` (racionando estoque entre lojas) / `offline` (removido do mundo)  |

**Seus objetivos:**

- Nunca deixar estoque zerado de produtos críticos
- Não lotar (capacidade finita)
- Responder aos pedidos das lojas da sua zona o mais rápido possível

**Com quem se comunica:**

- **Fábricas** → solicita reabastecimento quando estoque cai abaixo do nível mínimo
- **Lojas** → recebe pedidos; **confirma** disponibilidade e ETA, ou **rejeita** com motivo (estoque insuficiente)
- **Caminhões** → solicita entregas para as lojas

**Perguntas que o agente responde a cada ciclo:**

- "Meu estoque de cada produto está em nível crítico? Preciso pedir reabastecimento?"
- "Tenho produto suficiente para atender todos os pedidos pendentes? Se não, quais priorizo?"
- "De qual fábrica devo pedir? A mais próxima ou a que tem mais estoque disponível?"

---

### Loja (Material de Construção)

**Quem é:** Ponto de venda final de materiais de construção. Vende quaisquer materiais cadastrados no catálogo (seção 3) para o consumidor final. Tem demanda contínua e precisa de estoque constante de cada produto que comercializa.

> Ao criar ou editar uma loja no dashboard, o usuário seleciona os materiais que ela vende a partir de um combo com os materiais ativos no catálogo.

**Atributos:**

| Atributo         | Descrição                                                                          |
| ---------------- | ---------------------------------------------------------------------------------- |
| `stock`          | `Dict[produto, quantidade]` — estoque atual por produto                            |
| `demand_rate`    | `Dict[produto, quantidade_por_tick]` — consumo médio por tick em condições normais |
| `reorder_point`  | `Dict[produto, quantidade]` — nível de referência para gatilho preditivo; o agente acorda quando a projeção indica que vai atingir esse nível antes da entrega chegar |
| `pending_orders` | Pedidos enviados a armazéns ainda não entregues; cada pedido inclui `retry_after_tick` para controlar backoff após rejeição |
| `products_sold`  | Lista de produtos que esta loja comercializa                                       |
| `status`         | `open` / `demand_paused` (feriado/demanda zero) / `offline` (removida do mundo)    |

**Seus objetivos:**

- Nunca perder venda por falta de estoque
- Pedir ao armazém correto na quantidade certa (não pedir demais, não pedir de menos)
- Antever a demanda com base no histórico de vendas por produto

**Mecanismo de backoff após rejeição:**

Quando um pedido é rejeitado, a loja não retenta imediatamente — ela define `retry_after_tick` no pedido antes de tentar novamente. Isso evita loops de requisições que inundam a simulação:

| Motivo da rejeição                                  | Backoff        |
| --------------------------------------------------- | -------------- |
| Armazém sem estoque (mas já solicitou reabastecimento) | 6 ticks     |
| Armazém sem estoque (sem pedido à fábrica em curso) | 3 ticks        |
| Fábrica em quebra de máquina                        | 8 ticks        |
| Fábrica com estoque zerado                          | 12 ticks       |

Ao atingir `retry_after_tick`, a loja tenta o mesmo destino novamente. Se for rejeitada uma segunda vez com o mesmo motivo, escala para a próxima alternativa disponível (outro armazém da região ou, em último caso, compra direta na fábrica).

**Com quem se comunica:**

- **Armazéns** → envia pedidos de reposição por produto; recebe **confirmação** (com ETA) ou **rejeição** (com motivo e backoff sugerido)
- **Fábrica** → em casos excepcionais (armazém sem estoque e sem previsão de entrega após backoff), pode comprar direto

**Perguntas que o agente responde a cada ciclo:**

- "Meu estoque de cada produto cobre a demanda prevista para os próximos 3 dias (72 ticks)?"
- "Qual armazém tem o produto que preciso, está na minha região e entrega mais rápido?"
- "Já tenho um pedido pendente para este produto? Ainda estou no período de backoff ou posso retentar?"

---

### Caminhão

**Quem é:** Veículo de transporte. Executa ordens de entrega entre fábricas, armazéns e lojas. Tem dois perfis com comportamentos distintos:

- **Proprietário:** segue ordens diretas da fábrica vinculada. Sem autonomia para recusar ou priorizar — executa o que a fábrica determinar.
- **Terceiro:** agente autônomo e self-interested. Não tem dono. Avalia ativamente quais demandas aceitar com base no que é melhor para ele — maximizar entregas realizadas com o menor desgaste e risco possíveis.

**Atributos físicos:**

| Atributo         | Descrição                                                                                                        |
| ---------------- | ---------------------------------------------------------------------------------------------------------------- |
| `capacity_tons`  | Capacidade máxima de carga em toneladas                                                                          |
| `truck_type`     | `proprietario` (vinculado a uma fábrica) ou `terceiro` (livre para contrato)                                     |
| `base_location`  | Localização de repouso quando sem carga                                                                          |
| `degradation`    | Nível de desgaste acumulado (0–100%). Aumenta a cada km rodado e carga transportada                              |
| `breakdown_risk` | Probabilidade de quebra por viagem — função de `degradation`. Começa baixa, cresce exponencialmente acima de 70% |
| `status`         | `idle` / `in_transit` / `broken` / `maintenance`                                                                 |
| `cargo`          | `{product, quantity, origin, destination}` — carga atual; `null` quando `idle`                                   |
| `current_route`  | `{path: [[lng,lat],...], timestamps: [ms,...], eta_ticks: int}` — rota ativa; `null` quando `idle`               |

**Mecânica de degradação:**

- A cada viagem, `degradation` aumenta proporcionalmente à distância percorrida e ao peso transportado.
- **Rotas ruins podem acelerar a degradação** — estradas em mau estado, com muitos buracos ou clima adverso têm uma chance de aplicar um multiplicador de desgaste extra naquela viagem. Isso é probabilístico: a mesma rota ruim pode não causar dano adicional em uma viagem e causar em outra.
- `breakdown_risk` é calculado a cada viagem com base em `degradation` e no risco da rota. Valores de referência:

| `degradation` | `breakdown_risk` base (rota normal) | `breakdown_risk` (rota de risco) |
| ------------- | ----------------------------------- | -------------------------------- |
| 0–29%         | 1%                                  | 3%                               |
| 30–59%        | 5%                                  | 10%                              |
| 60–69%        | 12%                                 | 22%                              |
| 70–79%        | 25%                                 | 40%                              |
| 80–89%        | 45%                                 | 65%                              |
| 90–94%        | 70%                                 | 85%                              |
| ≥ 95%         | guardrail — viagem bloqueada        | guardrail — viagem bloqueada     |

O crescimento é exponencial acima de 70%. "Rota de risco" = bloqueio ativo, tempestade regional ou histórico de acidentes naquele segmento. O engine sorteia o evento de quebra com base nesse percentual ao iniciar cada viagem.

- A cada viagem iniciada, calcula-se se o caminhão quebra no meio do percurso com base em `breakdown_risk`. Uma quebra deixa a carga presa até outro caminhão ser designado.
- Manutenção zera `degradation` mas imobiliza o caminhão por um número de ticks **proporcional ao nível de degradação no momento em que entra em manutenção**:

| Degradação ao entrar em manutenção  | Ticks imobilizado | Equivalente simulado     |
| ----------------------------------- | ----------------- | ------------------------ |
| < 30%                               | 2 ticks           | 2h (revisão rápida)      |
| 30% – 59%                           | 4 ticks           | 4h (manutenção leve)     |
| 60% – 79%                           | 8 ticks           | 8h (manutenção completa) |
| 80% – 94%                           | 14 ticks          | 14h (reparo pesado)      |
| ≥ 95% (guardrail — quebra iminente) | 24 ticks          | 24h (reforma geral)      |

Isso cria um incentivo real para manutenção preventiva: um agente que age cedo paga 2 ticks; um que procrastina até o limite paga 24. O NPC deve considerar esse custo de oportunidade ao decidir quando parar.

**Critério de escolha de rota — Tempo vs. Risco:**

- Sem consumo de combustível — o único trade-off é **tempo de entrega** vs. **risco da rota**.
- Rotas mais curtas podem ter maior risco: estrada em mau estado, trânsito intenso, clima adverso — e podem acelerar a degradação do caminhão.
- O agente pondera: vale pegar a rota mais rápida se ela tem risco 40% maior de atraso e pode desgastar mais o veículo?

---

### Lógica de decisão do caminhão terceiro

O caminhão terceiro é um agente self-interested — ele não serve a ninguém, ele serve a si mesmo. Quando há múltiplas demandas disponíveis (fábricas e armazéns querendo contratar), ele avalia e escolhe a que maximiza sua taxa de entrega com o menor desgaste possível.

**Critérios de avaliação de uma demanda (em ordem de prioridade):**

1. **Risco da rota** — rotas com clima adverso, bloqueios ou histórico de acidentes são penalizadas. O caminhão prefere evitar rotas que aumentam `breakdown_risk` mesmo que sejam mais rápidas.
2. **Distância total** — menor distância = menos desgaste acumulado. Entre duas ordens de risco similar, prefere a mais curta.
3. **Aproveitamento de carga** — prefere cargas que utilizam ≥ 80% da sua capacidade. Viagens com carga muito leve são ineficientes para a taxa de entrega.
4. **Degradação atual** — o agente recebe seu `degradation` atual como contexto e raciocina autonomamente sobre o risco. Um caminhão a 75% pode aceitar uma viagem curta e segura, mas recusar uma longa em rodovia de risco — ou pode aceitar ambas se a urgência for alta o suficiente. Essa é uma decisão do NPC, não uma regra fixa. O único limite absoluto é o guardrail do engine: `degradation ≥ 95%` bloqueia qualquer viagem independente da decisão do agente.

**Taxa de entrega como objetivo principal:**

O caminhão terceiro quer completar o maior número de viagens por janela de tempo — mas não a qualquer custo. Uma quebra imobiliza o caminhão por vários ticks e zera sua taxa de entrega naquele período. Por isso, ele prefere **muitas viagens curtas e seguras** a poucas viagens longas e arriscadas.

**Urgência crescente de pedidos:**

Propostas de contratação publicadas por fábricas e armazéns incluem o campo `age_ticks` — quantos ticks esse pedido está sem atendimento. O caminhão recebe esse valor e pode usá-lo como fator de decisão: um pedido com muitos ticks em aberto sinaliza urgência real na cadeia. A cada 3 ticks sem atendimento, o pedido sobe um nível de prioridade — eventualmente superando a penalidade de uma rota de risco. Isso evita deadlocks logísticos onde nenhum caminhão aceita uma rota adversa enquanto a cadeia inteira espera.

**Recusa de demanda:**

O caminhão terceiro pode recusar uma ordem de contratação. Quando recusa, comunica o motivo ao solicitante (alta degradação, rota de risco, aproveitamento de carga abaixo de 80% da capacidade) para que o agente solicitante possa buscar outro caminhão.

---

**Seus objetivos (proprietário e terceiro):**

- Completar entregas com o melhor equilíbrio entre tempo e risco
- Escolher a rota com menor risco de atraso e desgaste
- Monitorar própria degradação e alertar quando próximo do limite
- Reagir a imprevistos em tempo real

**Com quem se comunica:**

- **Fábricas / Armazéns** → recebe ordens (proprietário) ou avalia propostas de contratação (terceiro)
- **Ferramentas externas** → consulta condições de rota (clima, tráfego)
- **Outros agentes** → alerta sobre quebras ou atrasos que impactam o plano dos outros

**Ciclo LLM — event-driven:**

O agente LLM do caminhão **não roda a cada tick**. Enquanto em trânsito sem imprevistos, o caminhão é pura física — posição interpolada por timestamp, sem custo de token. O LLM é disparado apenas nos seguintes eventos:

| Evento | Agente acorda |
| ------ | ------------- |
| `route_blocked` | Recalcular rota |
| `truck_arrived` | Notificar destino, aguardar nova ordem |
| `truck_breakdown` | Alertar cadeia, carga precisa de resgate |
| `new_order` (proprietário) | Planejar rota |
| `contract_proposal` (terceiro) | Avaliar e aceitar/recusar |

**Perguntas que o agente responde quando acordado:**

- _Proprietário:_ "Qual a rota com melhor balanço de tempo vs. risco para a entrega que me foi atribuída?"
- _Terceiro:_ "Qual das demandas disponíveis oferece a melhor relação entre carga aproveitada, distância e risco de rota?"
- "Dado meu desgaste atual, o risco desta rota e a urgência da entrega — vale a pena aceitar agora ou é melhor parar para manutenção?"
- "Se eu quebrar no meio do caminho, quem pode assumir minha carga?"

---

## 6. Gestão do Mundo pelo Usuário

O usuário não é apenas observador passivo — ele pode **moldar o mundo** em tempo real, criando ou removendo entidades. Os agentes reagem às mudanças imediatamente no próximo tick.

### Operações disponíveis via Dashboard

#### Catálogo de Materiais

| Operação                  | O que faz                                                                            |
| ------------------------- | ------------------------------------------------------------------------------------ |
| **Criar Material**        | Adiciona novo material ao catálogo (nome); unidade é sempre `ton`; fica disponível nos combos |
| **Editar Material**       | Altera nome de um material existente                                                 |
| **Desativar Material**    | Marca material como inativo — some dos combos mas mantém histórico de entidades      |

> Materiais não podem ser excluídos se houver fábricas, armazéns ou lojas vinculadas a eles. Desative-os para retirá-los de circulação.

#### Entidades do Mundo

| Operação                   | O que faz                                                                                    |
| -------------------------- | -------------------------------------------------------------------------------------------- |
| **Criar Fábrica**          | Localização, capacidade, estoque inicial e **seleção de materiais produzidos** (combo multi) |
| **Editar Fábrica**         | Altera materiais produzidos, capacidades e armazéns parceiros                                |
| **Remover Fábrica**        | Remove fábrica do mundo; pedidos pendentes são redistribuídos                                |
| **Criar Armazém**          | Localização, região de atuação, capacidade e **seleção de materiais aceitos** (combo multi)  |
| **Editar Armazém**         | Altera materiais aceitos, capacidades e mínimos por produto                                  |
| **Remover Armazém**        | Remove armazém; lojas da região precisam se reajustar                                        |
| **Criar Loja**             | Localização, **seleção de materiais vendidos** (combo multi) e demanda esperada por produto  |
| **Editar Loja**            | Altera materiais vendidos, demanda e reorder points por produto                              |
| **Remover Loja**           | Remove loja; pedidos pendentes são cancelados                                                |
| **Criar Caminhão**         | Adiciona caminhão (proprietário ou terceiro) com capacidade e base                           |
| **Remover Caminhão**       | Remove caminhão; se em trânsito, carga precisa ser reassinalada                              |
| **Ajustar Estoque**        | Adiciona ou reduz estoque de qualquer entidade manualmente (por produto)                     |
| **Injetar Evento de Caos** | Dispara eventos disruptivos (ver seção 7)                                                    |

> Em todos os formulários de criação/edição de fábrica, armazém e loja, o campo de materiais exibe um **combo multi-seleção** com os materiais ativos no catálogo. Após selecionar os materiais, campos de configuração por produto (capacidade, estoque inicial, demanda, mínimo) são expandidos dinamicamente no formulário.

---

## 7. Eventos de Caos

O mundo não é previsível. Eventos disruptivos testam a resiliência dos agentes:

| Evento                       | Impacto                                                                                         | Resposta esperada dos agentes                                                                     |
| ---------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Greve de caminhoneiros       | Caminhões terceiros recusam todas as propostas por N ticks (greve = critério de recusa forçado) | Fábricas priorizam frota própria; Armazéns racionam estoque entre lojas por prioridade de demanda |
| Quebra de máquina na fábrica | Capacidade produtiva cai 50%                                                                    | Armazéns redistribuem estoque; Lojas ajustam pedidos; buscam alternativa                          |
| Pico de demanda              | Lojas vendem 3x o normal em um ciclo                                                            | Cadeia toda acelera; agentes negociam prioridade de entrega                                       |
| Bloqueio de rodovia          | Rota indisponível (ex: SP-330)                                                                  | Caminhões desviam; recalculam tempo e risco                                                       |
| Tempestade regional          | Região com chuva intensa por N ticks                                                            | Caminhões naquela rota elevam risco; agentes evitam ou aguardam                                   |
| Caminhão quebrado em rota    | Carga imobilizada no meio do percurso                                                           | Agente alerta; outro caminhão é designado para resgatar a carga                                   |
| Demanda zero repentina       | Loja para de vender (ex: feriado local)                                                         | Pedidos de reposição são pausados; armazém redistribui prioridades                                |

### 7.1 Caos Autônomo — MasterAgent

Além dos eventos injetados manualmente pelo usuário, o **MasterAgent** pode acionar um subconjunto restrito de eventos de caos de forma autônoma, quando detecta condições sistêmicas que tornam o evento iminente ou plausível no contexto da simulação. Isso cria um mundo mais vivo — o caos não depende exclusivamente da intervenção humana.

**Eventos que o MasterAgent pode acionar:**

| Evento                       | Condição de gatilho autônomo                                                                                           |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Quebra de máquina na fábrica | Fábrica operando em produção máxima (`production_rate_current == production_rate_max`) por ≥ 12 ticks consecutivos     |
| Caminhão quebrado em rota    | Caminhão com `degradation ≥ 80%` inicia viagem — o engine já sorteou quebra via `breakdown_risk`; o MasterAgent apenas registra e roteia o evento de alerta resultante |
| Pico de demanda              | Nenhuma loja entrou em ruptura de estoque nos últimos 24 ticks e a simulação está em regime estável — sinaliza um choque de demanda para testar a resiliência |
| Demanda zero repentina       | Não disparado autonomamente — requer ação do usuário (representa feriado ou evento externo explícito)                  |
| Tempestade regional          | Não disparado autonomamente — requer ação do usuário                                                                   |
| Greve de caminhoneiros       | Não disparado autonomamente — requer ação do usuário                                                                   |
| Bloqueio de rodovia          | Não disparado autonomamente — requer ação do usuário                                                                   |

**Regras de frequência e cooldown:**

- O MasterAgent só pode acionar caos autônomo se **nenhum outro evento de caos** (manual ou autônomo) estiver ativo no momento.
- Cooldown entre eventos autônomos: mínimo de **24 ticks** após a resolução do evento anterior.
- Máximo de **1 evento autônomo por vez** — o MasterAgent não empilha eventos.
- O MasterAgent **não aciona caos** se o usuário pausou a simulação ou se há menos de 5 ticks desde o início da simulação.

**Visibilidade para o usuário:**

Eventos de caos autônomos aparecem no feed do dashboard com a origem identificada: `[MasterAgent]` em vez de `[Usuário]`. O usuário pode cancelar um evento autônomo em andamento pelas mesmas ferramentas do painel de caos.

---

## 8. Como os NPCs se Comunicam

Os agentes não têm um controlador central — eles se comunicam por **eventos assíncronos**:

```
Engine calcula: (stock[cimento] - reorder_point[cimento]) / demand_rate[cimento] < lead_time_ticks × 1.5
  └─► Gatilho preditivo — loja ainda acima do reorder_point, mas projeção indica que vai cruzá-lo antes da entrega chegar
  └─► Agente LLM da Loja acorda (fire-and-forget, tick não espera)
  └─► Loja envia pedido ao Armazém mais próximo com cimento disponível

Armazém recebe pedido
  ├─► Se estoque suficiente:
  │     └─► Reserva quantidade, confirma para a Loja com ETA estimado
  │     └─► Solicita Caminhão para entrega
  └─► Se estoque insuficiente:
        └─► Envia rejeição parcial à Loja ("tenho X, faltam Y — aguarde reabastecimento")
        └─► Solicita reabastecimento à Cimenteira Paulista

Loja recebe rejeição parcial
  └─► Avalia: o que foi reservado cobre a demanda por quanto tempo?
  └─► Se cobertura < 2 ticks: escala pedido diretamente à Cimenteira (caso excepcional)
  └─► Se cobertura ≥ 2 ticks: aguarda reabastecimento do armazém

Cimenteira Paulista recebe solicitação do Armazém
  └─► Verifica capacidade de produção e estoque existente
  └─► Decide: produzir agora ou usar estoque
  └─► Verifica caminhões proprietários livres
  ├─► Se proprietário disponível: atribui ordem diretamente
  └─► Se todos ocupados: publica proposta de contratação para caminhões terceiros
        (proposta inclui: origem, destino, produto, quantidade, age_ticks do pedido original)

Caminhão terceiro recebe proposta de contratação
  └─► Avalia: risco da rota, distância, aproveitamento de carga (≥80%), degradação própria, age_ticks
  ├─► Se aceita: confirma à Fábrica, inicia deslocamento para coleta
  └─► Se recusa: comunica motivo; Fábrica tenta próximo caminhão terceiro disponível
        (pedidos com age_ticks alto sinalizam urgência — podem superar penalidade de rota)

Caminhão (proprietário ou terceiro aceito) em execução
  └─► Consulta rota real (Valhalla)
  └─► Pondera tempo vs. risco — considera condições atuais de clima e tráfego
  └─► Executa entrega, reportando posição em tempo real
  └─► Ao concluir: notifica Armazém (ou Loja) de entrega realizada
  └─► Se quebrar em rota: alerta todos os agentes impactados; outro caminhão é convocado
```

Nenhum humano orquestra esse fluxo — os agentes resolvem sozinhos.

---

## 9. O que o Usuário Vê

O usuário é o **game master** do mundo — assiste a partida acontecer e pode interferir quando quiser.

**Dashboard em tempo real:**

- Mapa de São Paulo com fábricas, armazéns e lojas como pontos vivos
- Caminhões animados se movendo pelas rodovias reais
- Indicador de degradação visível em cada caminhão (cor: verde → amarelo → vermelho)
- Feed de decisões dos agentes ("Armazém Jundiaí solicitou reabastecimento — cimento em 8%")
- Alertas visuais de eventos de caos em andamento
- Indicadores de saúde do ecossistema (pedidos atrasados, ruptura de estoque, caminhões quebrados)

**Controles disponíveis:**

- Criar / remover fábricas, armazéns, lojas e caminhões
- Ajustar estoques manualmente
- Injetar eventos de caos
- Inspecionar qualquer NPC (ver estado atual, última decisão, histórico, degradação)
- Pausar / retomar a simulação
- Ajustar velocidade dos ticks

---

## 10. Critérios de Sucesso

O produto funciona quando:

1. **Autonomia real:** Os agentes resolvem o ciclo completo (loja → armazém → fábrica → caminhão) sem intervenção humana
2. **Reação ao caos:** Após a resolução de um evento disruptivo, o ecossistema retorna ao estado operacional normal em no máximo 5 ticks — os agentes reajustam rotas, pedidos e produção sem intervenção humana. Eventos de longa duração (greve, tempestade prolongada) são considerados "em curso" e não contam como falha enquanto ativos; o critério se aplica ao período pós-evento
3. **Comunicação entre agentes:** Um pedido gerado por uma loja resulta em ações encadeadas nos armazéns, fábricas e caminhões corretos
4. **Degradação real:** Caminhões com alta degradação têm chance mensurável de quebra; agentes consideram isso nas decisões
5. **Visibilidade total:** O usuário entende, via dashboard, por que cada agente tomou cada decisão
6. **Sem ruptura prolongada:** Nenhuma loja fica com estoque zero por mais de 3 ticks consecutivos em condições normais
7. **Mundo vivo:** Entidades criadas ou removidas pelo usuário são absorvidas pelo ecossistema no próximo tick

---

## 11. O que este projeto NÃO é

- Não é um sistema de gestão de supply chain real (sem integração com ERPs, sem dados reais de empresas)
- Não é um jogo com mecânicas de pontuação ou progressão para o usuário
- Não é uma ferramenta de predição ou otimização para uso em produção
- Não modela custos financeiros — o foco é fluxo de materiais, tempo e risco
- Não simula consumo de combustível — o trade-off dos caminhões é exclusivamente tempo vs. risco

---

## 12. Localidades do Mundo Padrão

O mundo usa coordenadas reais de cidades paulistas, com rotas pelas rodovias do OSM:

| Entidade                      | Produto               | Localização         | Rodovia principal       |
| ----------------------------- | --------------------- | ------------------- | ----------------------- |
| Fábrica: Tijolaria Anhanguera | Tijolos               | Campinas            | SP-330 (Anhanguera)     |
| Fábrica: Aciaria Sorocabana   | Ferro                 | Sorocaba            | SP-280 (Castelo Branco) |
| Fábrica: Cimenteira Paulista  | Cimento               | Votorantim          | SP-280 (Castelo Branco) |
| Armazém: Hub Norte            | —                     | Ribeirão Preto      | SP-330 / SP-333         |
| Armazém: Hub Centro-Oeste     | —                     | Jundiaí             | SP-330 / SP-348         |
| Armazém: Hub Leste            | —                     | Mogi das Cruzes     | SP-070 (Ayrton Senna)   |
| Lojas (5)                     | Tijolos/Ferro/Cimento | SP capital + região | Várias                  |
