---
id: null
type: research
project: pulsar
parent: "[[moc-pulsar]]"
status: Cerrada
alcance: "Single-echelon (CEDIS). Distribución CEDIS→tiendas = TODO futuro (multi-echelon)"
created: 2026-06-30
updated: 2026-06-30
relacionado: []
tags: [demanda, reabasto, inventario]
---

# Prevención de quiebres en CEDIS — estado del arte y roadmap

↑ Pertenece a: [Pulsar](../moc-pulsar.md)

| | |
| --- | --- |
| **Tipo** | Investigación / diseño (no normativo) |
| **Objetivo** | Rediseñar el reabasto **CEDIS ← proveedores** para evitar quiebres |
| **Alcance** | Single-echelon (CEDIS). Distribución CEDIS→tiendas = TODO futuro (multi-echelon) |
| **Estado** | Investigación cerrada; pendiente decidir Fase 1 |

> **Cómo leer este documento.** La Parte 1 es el estado del arte; la Parte 2 lo
> aterriza a nuestro caso (lake validado, calendario retail 4-5-4, 3 orígenes, sin
> lead time confiable) con un roadmap por fases. Cada afirmación lleva una etiqueta
> de confianza:
> - **[V]** Verificado: afirmación de fuente primaria que sobrevivió verificación
>   adversarial (≥2/3 votos escépticos no la pudieron refutar).
> - **[E]** Establecido: consenso de libro de texto o práctica de la industria, de
>   fuentes secundarias/practitioner fetchadas (menor rigor de verificación).
> - **[C]** Criterio: juicio arquitectónico propio aterrizado a nuestro caso.
>
> **Nota de honestidad metodológica.** El núcleo verificado (24 claims) se concentra
> en **demanda censurada, forecasting probabilístico, demanda intermitente y safety
> stock con lead time variable** — ahí la evidencia es fuerte y primaria. Los temas
> de **segmentación, productos nuevos, estacionalidad, OTB y práctica de retailers**
> se apoyan en fuentes fetchadas pero **no** pasaron el filtro de los 25 claims
> verificados (quedaron debajo de las fuentes académicas en el ranking); van como
> **[E]/[C]**. Las fuentes completas están al final.

---

# PARTE 1 — Estado del arte

## 1. Demanda censurada / "unconstraining" (el sub-problema #1, y el mejor fundamentado)

Este es el corazón de todo y donde la evidencia es más sólida. Tu sistema ABC
anterior no lo contemplaba; es la causa raíz de "no sé la demanda real".

- **El mecanismo.** Cuando un SKU se agota, las ventas registradas dejan de
  observar la demanda: solo sabes que la demanda **fue mayor** que lo vendido. Las
  ventas crudas **subestiman sistemáticamente** la demanda real (sesgo a la baja).
  **[V]** *(Nahmias 1994: "in periods when lost sales occur demand is not observed;
  one knows only that demand is larger than sales").*
- **Por qué importa tanto (efecto espiral).** Usar ventas censuradas como insumo
  del pronóstico dispara el *spiral-down effect*: menos demanda estimada → menos
  stock de protección → más quiebres → menos ventas observadas → ciclo
  autorreforzante de caída. **[V]** *(Kourentzes et al. 2019, citando a Cooper et
  al. 2006; en sus datos de renta de autos las restricciones estaban activas ~30%
  del tiempo).* **Esto es exactamente lo que te pasó con ABC.**
- **Cuánto se gana al corregir.** En el benchmark FreshRetailNet-50K (50,000 series
  tienda-producto, horarias, con quiebres anotados), reconstruir la demanda latente
  y pronosticar sobre ella **redujo el sesgo de 7.37% a ~0** y mejoró la precisión
  2.73%. **[V]** *(arXiv 2505.16319, 2025).*
- **El patrón de solución: pipeline en dos etapas** — (1) reconstruir la demanda no
  observada durante quiebres; (2) entrenar el pronóstico sobre la serie
  *des-censurada*. **[V]** *(FreshRetailNet 2025).*
- **Catálogo de métodos** (taxonomía de 5 enfoques: observar latente, dejar
  censurado, descartar censurado, imputar, des-restringir estadísticamente). **[V]**
  *(Guo et al. 2012, survey de 130+ referencias).* Los concretos:
  - **EM (Expectation-Maximization):** fuerte en datasets grandes, pero **rinde mal
    con poca historia o cuando casi todo está censurado**; ahí son superiores los de
    **suavizado exponencial (Holt, Croston)**. **[V]** *(Kourentzes et al. 2019).*
  - **Máxima verosimilitud (MLE):** más eficiente cuando el **% de censura es alto**.
    **[V]** *(Kuznetsov & Burmistrov 2016, JRPM).* Nahmias 1994 ya evaluaba MLE, BLUE
    y un estimador nuevo como benchmark. **[V]**
  - **Modelos de elección no paramétricos** (sustitución del cliente + mínimos
    cuadrados no lineales, sin asumir distribución de llegadas). **[V]** *(Nikseresht
    & Ziarati 2017).*
  - **Imputación proporcional / Projection Detruncation (PD)** — parte de la
    taxonomía clásica de RM. **[E]**

**Lectura para nuestro caso:** la regla de Kourentzes (EM para mucha historia;
suavizado exponencial cuando hay poca o casi todo censurado) es oro, porque mezclas
SKUs maduros con muchos nuevos.

## 2. Forecasting probabilístico / por cuantiles (la pieza central moderna)

- **Predecir la distribución completa, no la media.** Para decisiones de inventario
  necesitas el rango de resultados posibles con su probabilidad, no un solo número.
  **[E]** *(ToolsGroup, Lokad).*
- **El punto de reorden ES un cuantil.** ROP = demanda durante lead time + safety
  stock, y eso equivale a un **pronóstico por cuantil** de la demanda durante el
  lead time al nivel de servicio τ deseado. **[V]** *(Lokad).*
- **Newsvendor de un paso.** Pronosticar directamente los cuantiles de la demanda
  sirve como método data-driven para fijar el nivel de stock óptimo (el *critical
  fractile* CR = Cu/(Cu+Co)), en lugar de pronosticar un punto y luego sumar safety
  stock. **[V]** *(Cao & Shen 2019, Operations Research Letters).*
- **No asumas normalidad.** Las fórmulas estándar de safety stock asumen errores de
  pronóstico **Gaussianos e iid**, y las desviaciones de ese supuesto **degradan el
  desempeño**; alternativas empíricas/no-paramétricas (KDE, GARCH, combinación de
  cuantiles) lo mejoran. **[V]** *(Trapero, Cardós & Kourentzes 2019, Int. J.
  Forecasting).*

## 3. Demanda intermitente (SKUs de baja/errática rotación)

- **Croston y SBA** (Syntetos-Boylan Approximation) actualizan tamaño e intervalo de
  demanda **solo en periodos con demanda positiva**; en periodos de cero **no ajustan
  a la baja**, lo que es un problema cuando el inventario se vuelve obsoleto. **[V]**
  *(Babai et al. 2019, IJPE).*
- **TSB (Teunter-Syntetos-Babai)** lo resuelve actualizando la **probabilidad de
  demanda** (no el intervalo) **en cada periodo**, incluidos los de cero → decae el
  pronóstico ante obsolescencia. **[V]** *(Babai 2019; Teunter-Syntetos-Babai 2011,
  EJOR).*
- Existen híbridos SBA/TSB que conmutan según la señal de obsolescencia. **[V]**
- **Clasificación del patrón de demanda (clave para segmentar):** el método estándar
  cruza **ADI** (intervalo medio entre demandas) y **CV²** (variabilidad del tamaño)
  en 4 cuadrantes — *smooth, erratic, intermittent, lumpy* — y de ahí se elige el
  pronóstico (suavizado para *smooth*, Croston/SBA/TSB para *intermittent/lumpy*).
  **[E]** *(clasificación Syntetos-Boylan-Croston; estándar de la industria).*

## 4. Punto de reorden y safety stock bajo lead time variable

- **Safety stock depende de la VARIANZA de la demanda durante el lead time** (o,
  equivalentemente, de la varianza del error de pronóstico de esa demanda), no solo
  de la media — así que **pronosticar bien la varianza es esencial**. **[V]**
  *(Prak/Trapero et al. 2022, EJOR).*
- **La fórmula clásica de libro de texto** para la varianza de demanda-en-lead-time
  es **la menos precisa** de las tres estrategias estudiadas, salvo con demanda de
  alta autocorrelación negativa. **[V]** *(Trapero et al. 2022).* → cuidado con
  copiar la fórmula `SS = Z·σ·√LT` a ciegas.
- **Políticas de control de inventario** (continua vs periódica): `(s,Q)`, `(s,S)`,
  `(R,S)`. Revisión continua reacciona antes; periódica agrupa pedidos (útil con
  proveedores de ciclo fijo, p. ej. contenedor de China). **[E]**

## 5. Segmentación de SKUs más allá del ABC-XYZ anual  **[E/C]**

El problema que describiste (estacional clasificado B/C al promediar el año; nuevo
en tendencia clasificado "CZ" por 52 semanas de historia) es un **defecto conocido**
del ABC-XYZ anual estático. Cómo lo evita la industria:

- **No promediar el año: segmentar por periodo/temporada.** Recalcular la clase por
  periodo retail (o por temporada definida), no una sola vez al año. Un SKU navideño
  es **A en su ventana** aunque sea C anual.
- **ABC multicriterio:** combinar valor (ventas/margen) con criticidad, volatilidad,
  ciclo de vida — no solo facturación.
- **Clasificación por patrón de demanda (ADI/CV²)** en vez de XYZ ingenuo: distingue
  *smooth/erratic/intermittent/lumpy* y dicta el método de pronóstico (§3).
- **Segmentar por etapa de ciclo de vida** (nuevo / crecimiento / maduro / declive):
  los nuevos van por una pista de *cold-start* (§6), no por la regla de historia
  larga que los castiga.
- **Dinámico, no anual:** reclasificación rodante; las clases cambian con la
  temporada y la madurez.

## 6. Productos nuevos / arranque en frío (cold-start)  **[E]**

Sin historia propia, se pronostica por **proxies**:

- **Like/analog modeling:** asignar el perfil de un producto "hermano" similar ya
  conocido. **[E]** *(Impact Analytics).*
- **Modelos por atributos:** predecir la demanda desde atributos del SKU (categoría,
  precio, temporada, marca) con un modelo entrenado sobre el catálogo histórico.
- **Modelos jerárquicos / pooling:** prestar fuerza estadística del nivel categoría
  hacia el SKU nuevo.
- **Curva de difusión de Bass** para adopción de productos verdaderamente nuevos.
  **[E]** *(literatura de new-product diffusion).*

## 7. Estacionalidad  **[E]**

- **Holt-Winters / ETS** (componente estacional aditivo/multiplicativo). **[E]**
  *(Hyndman, fpp3).*
- **Regresión armónica dinámica (Fourier)** para estacionalidad larga o múltiple
  (semana-del-año dentro del calendario retail), más robusta que dummies cuando hay
  muchos periodos. **[E]** *(fpp3, dynamic harmonic regression).*
- **Descomposición** (STL) para separar tendencia/estacional/residual.
- **Pocos ciclos** (productos con 2-3 años): poolear el índice estacional a nivel
  categoría/temporada en lugar de estimarlo por SKU.
- Encaja directo con tu **calendario retail 4-5-4**: la estacionalidad se modela
  sobre semana/periodo retail, no gregoriano.

## 8. Estimación de lead time con datos sucios  **[C]**

Tu ERP no es confiable (OCs creadas el día de la entrada). Opciones:

- **Prior por origen** como base: Nacional ~15 d, USA ~30 d, China ~120-180 d, con
  su **variabilidad** (no un número fijo).
- **Estimar desde la cadencia de recepciones reales** (los movimientos de entrada,
  `trans_type=20/59`, sí tienen fecha confiable de cuándo llegó la mercancía):
  modelar el intervalo entre reabastos como proxy del ciclo efectivo.
- Tratar el lead time como **distribución**, no constante — alimenta directo la
  varianza de demanda-en-lead-time del §4. **[V (la dependencia), C (la estimación)]**

## 9. Timing de compra estacional / OTB / "last responsible order date"  **[E]**

- **Last responsible order date** ≈ `fin_de_ventana_de_venta − lead_time_origen`.
  Tu ejemplo es exacto: un SKU navideño USA (lead 30 d) **no** debe pedirse el 20-dic
  (llega 10-ene, fuera de campaña). El motor necesita un **cutoff por origen ×
  temporada** que apague la recomendación pasada esa fecha. **[E/C]**
- **Open-to-Buy (OTB):** presupuesto de compra por categoría/periodo; "OTB sin lead
  times está incompleto" — con lead times largos hay que comprometer presupuesto con
  mucha anticipación. **[E]** *(Toolio, RELEX).*
- **Pre-season vs in-season:** comprometer un núcleo pre-temporada y dejar holgura
  para **reabasto en-temporada** según venta real. El modelo Zara: lead times cortos
  para **posponer** el compromiso y reabastecer cerca de la demanda observada. **[E]**
  *(Zara/Inditex; ciclo de 2-3 semanas).* — para tu China (4-6 m) esto **no** aplica;
  ahí el grueso es apuesta pre-temporada y el cutoff manda.

## 10. Práctica industrial y software  **[E]**

- **Retailers:** Zara compite por **velocidad/lead time corto** (reabasto en-temporada);
  Walmart por **automatización + IA** en la cadena. **[E]**
- **Software del sector** (RELEX, Blue Yonder, o9, ToolsGroup, Netstock, GAINSystems,
  SAP IBP): todos convergen en **forecasting probabilístico + segmentación + safety
  stock por nivel de servicio**. Es la validación de que el camino §1–§4 es el
  estándar. **[E]**

## 11. KPIs y trade-offs económicos  **[E]**

- **Nivel de servicio:** *cycle service level* (prob. de no quebrar en un ciclo) vs
  *fill rate* (% de demanda satisfecha) — son distintos; el fill rate suele ser el
  relevante para retail.
- **Trade-off:** los quiebres reducen la facturación **2-5%**; el sobre-stock
  consume **20-30%** del capital de trabajo. **[E]** *(ToolsGroup).* Para
  **estacionales** el costo de sobre-stock es peor (obsolescencia post-temporada).
- **Otros:** GMROI, rotación / semanas de inventario, y precisión/sesgo del
  pronóstico (MAPE, WMAPE, **bias**, MASE). El **bias** es el que delata la censura.

---

# PARTE 2 — Aterrizaje a tu CEDIS + roadmap

## A. Tu ventaja: ya tienes lo que el 90% no tiene

El hallazgo #1 (demanda censurada) requiere **reconstruir el inventario disponible
en el tiempo** para saber *cuándo hubo quiebre*. Tú **ya** puedes: `inventory.movements`
está validado contra OITW y permite la suma corrida → serie de `on_hand` → detectar
periodos de `on_hand = 0`. Eso es precisamente el insumo del *unconstraining*. La
inversión en el lake **se paga aquí**: es el cimiento del que cuelga todo lo demás.

## B. Mapa sub-problema → método → qué tienes

| Sub-problema | Método recomendado | ¿Lo tienes? |
|---|---|---|
| 1. Demanda censurada | Pipeline 2 etapas: detectar quiebre (on_hand=0) → des-censurar → pronosticar | **Sí** (serie on_hand desde el lake) |
| 2. Segmentación | ADI/CV² + ciclo de vida + por periodo retail (no anual) | **Sí** (egreso por SKU×periodo retail) |
| 3. Productos nuevos | Like/analog + atributos + jerárquico | Parcial (necesita atributos de SKU) |
| 4. Estacionalidad | Holt-Winters / Fourier sobre calendario retail | **Sí** (calendario 4-5-4 ya es fuente única) |
| 5. Intermitente / probabilístico | Croston/SBA/TSB + cuantiles | **Sí** (datos), falta capa de modelado |
| 6. Lead time | Prior por origen + estimación desde recepciones | Parcial (origen no está en el lake todavía) |
| 7. Reorden / safety stock | ROP = cuantil de demanda-en-lead-time; SS por nivel de servicio | **Sí** (datos), falta capa de política |
| 8. Timing estacional | Last responsible order date = fin_ventana − lead_time | **Sí** (calendario + prior de lead time) |

## C. Roadmap por fases

### Fase 1 — Interpretable, alto valor (lo que se puede enviar ya)

Objetivo: una recomendación de reorden por SKU en CEDIS que **no** sufra los sesgos
de ABC, **auditable** (sin caja negra).

1. **`sales.history` + serie de inventario** (vista sobre `inventory.movements`):
   egreso de venta filtrado (Entrega 15 + Factura standalone 13 − devoluciones),
   `on_hand_before`, y **flag de quiebre** (`on_hand = 0`) por SKU×almacén×día.
2. **Des-censura v1 (simple):** en los días de quiebre, imputar la demanda con la
   tasa de venta de días **sin** quiebre comparables (mismo periodo retail / día de
   semana). Es la versión interpretable del pipeline de 2 etapas.
3. **Segmentación nueva:** clasificar cada SKU por **ADI/CV²** (smooth/erratic/
   intermittent/lumpy) **y** por etapa de ciclo de vida, recalculado **por periodo
   retail** (no anual). Esto solo ya resuelve tus dos quejas (estacional y nuevo).
4. **Punto de reorden por SKU×origen:** ROP = cuantil de la demanda-en-lead-time al
   nivel de servicio objetivo; lead time = **prior por origen** (15/30/120-180 d) con
   su variabilidad; safety stock por nivel de servicio (empezar con la fórmula y
   marcar los SKUs donde no aplica normalidad).
5. **Guardrail de timing estacional:** *last responsible order date* por origen ×
   temporada; apaga recomendaciones fuera de ventana (tu caso del 20-dic).
6. **KPIs:** nivel de servicio, tasa de quiebre, semanas de cobertura, y **bias** del
   pronóstico (para vigilar censura residual).

### Fase 2 — Probabilístico

1. **Pronóstico por cuantiles** (distribución completa) por segmento; estacional con
   Fourier/Holt-Winters sobre calendario retail; **TSB** para los lumpy/intermitentes.
2. **Des-censura propia:** EM para SKUs con mucha historia; suavizado exponencial
   (Holt/Croston) para los de poca o muy censurados — siguiendo la regla de Kourentzes.
3. **Safety stock empírico/no-paramétrico** (KDE/cuantiles) en lugar de Gaussiano,
   con varianza de demanda-en-lead-time bien estimada (no la fórmula de libro).
4. **Cold-start** por análogos/atributos para productos nuevos.
5. **Lead time como modelo:** estimarlo por origen/proveedor desde la cadencia de
   recepciones reales (requiere traer `origen` y fechas de entrada al modelo).

### Fase 3 — Optimización avanzada

1. **Cantidades de pedido tipo newsvendor** directo del cuantil (critical fractile),
   sin el rodeo punto+safety stock.
2. **Optimización de OTB** por categoría/temporada con lead times.
3. **Multi-echelon (CEDIS→tiendas)** — el TODO diferido; la demanda de tienda
   alimenta la del CEDIS (ver el [roadmap de Pulsar](../roadmap/roadmap-pulsar.md)).

## D. Qué NO hacer (anti-patrones confirmados)

- **No** pronosticar sobre ventas crudas (censuradas) → spiral-down. **[V]**
- **No** usar ABC anual estático → mata estacionales y nuevos. **[V/E]**
- **No** copiar `SS = Z·σ·√LT` a ciegas → es la estimación de varianza menos precisa.
  **[V]**
- **No** confiar en los lead times del ERP. **[contexto del negocio]**
- **No** asumir demanda/errores Gaussianos para todo. **[V]**

---

## Apéndice — Fuentes (26; por nivel)

**Primarias verificadas [V]:**
- Nahmias, S. (1994). *Demand Estimation in Lost Sales Inventory Systems.* Naval Research Logistics 41(6). https://onlinelibrary.wiley.com/doi/abs/10.1002/1520-6750(199410)41:6%3C739::AID-NAV3220410605%3E3.0.CO;2-A
- Guo, Xiao & Wang (2012). *Unconstraining Methods in Revenue Management Systems.* Advances in Operations Research. https://onlinelibrary.wiley.com/doi/10.1155/2012/270910
- Kourentzes, Li & Strauss (2019). *Unconstraining methods for revenue management.* J. Revenue & Pricing Mgmt. https://kourentzes.com/forecasting/wp-content/uploads/2017/09/Kourentzes_2017_Unconstraining.pdf
- Wang et al. (2025). *FreshRetailNet-50K: A Stockout-Annotated Censored Demand Dataset.* arXiv:2505.16319. https://arxiv.org/abs/2505.16319
- Nikseresht & Ziarati (2017). *A Demand Estimation Algorithm Using Censored Data.* ETASR. https://www.researchgate.net/publication/346747394
- Kuznetsov & Burmistrov (2016). *Maximum likelihood approach for demand unconstraining.* J. Revenue & Pricing Mgmt. https://link.springer.com/article/10.1057/rpm.2015.23
- Cao & Shen (2019). *Quantile forecasting and data-driven inventory management under nonstationary demand.* Operations Research Letters. https://www.sciencedirect.com/science/article/abs/pii/S0167637718301366
- Babai et al. (2019). *A new method to forecast intermittent demand in the presence of inventory obsolescence.* Int. J. Production Economics 209. https://www.sciencedirect.com/science/article/abs/pii/S0925527318300562
- Prak/Trapero et al. (2022). *Forecasting of lead-time demand variance: Implications for safety stock.* EJOR 296(3). https://www.sciencedirect.com/science/article/abs/pii/S0377221721003313
- Trapero, Cardós & Kourentzes (2019). *Quantile forecast optimal combination to enhance safety stock estimation.* Int. J. Forecasting 35(1). https://www.researchgate.net/publication/325270169

**Secundarias / practitioner [E]:**
- Lokad — Reorder point / probabilistic forecasting. https://www.lokad.com/reorder-point-definition/ · https://www.lokad.com/blog/2025/12/5/the-state-of-probabilistic-forecasting-in-supply-chain/
- ToolsGroup — Probabilistic forecasting / cost of stockouts vs overstock. https://www.toolsgroup.com/blog/probabilistic-forecasting-in-supply-chain-planning-explained/ · https://www.toolsgroup.com/blog/cost-of-stockouts-vs-overstock/
- Hyndman & Athanasopoulos, *Forecasting: Principles and Practice (fpp3)* — Holt-Winters · Dynamic harmonic regression. https://otexts.com/fpp3/holt-winters.html · https://otexts.com/fpp3/dhr.html
- Impact Analytics — Cold-start modeling. https://www.impactanalytics.co/blog/ai-retail-demand-forecasts-cold-start-modeling-for-new-retail-products
- Toolio · RELEX — Open-to-Buy. https://www.toolio.com/post/open-to-buy-planning-what-is-otb-for-retail · https://www.relexsolutions.com/resources/open-to-buy/
- RELEX — Measuring forecast accuracy. https://www.relexsolutions.com/resources/measuring-forecast-accuracy/
- Zara/Inditex supply chain. https://supplychain360.io/zaras-supply-chain-mastery-an-analysis-of-strategy-and-execution/
- New-product diffusion (Technological Forecasting & Social Change). https://www.sciencedirect.com/science/article/abs/pii/S0040162513001881

**Refutada (transparencia):** la afirmación de "23% de reducción de RMSE" del método
de Nikseresht & Ziarati 2017 fue **refutada** (1-2) por verificación adversarial: el
número no se pudo sustentar contra la fuente. No la uses.

---

*Generado a partir de una investigación multi-fuente con verificación adversarial
(26 fuentes, 24 afirmaciones verificadas, 1 refutada). El núcleo (censura,
probabilístico, intermitente, safety stock) es de fuente primaria verificada; los
demás temas, de fuentes secundarias/práctica.*
