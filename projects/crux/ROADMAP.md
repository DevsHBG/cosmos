# CRUX — Roadmap

Lo que **vendrá**, no lo que rige hoy. El estado y las convenciones vivas están en el
[`README`](./README.md).

## Fase 0 — Esqueleto ✅ (hecho)

Scaffold Vite + React 19 + TS strict; stack instalado; Tailwind v4 + shadcn/ui listos;
theming claro/oscuro cableado; providers (Theme + Query + Router) y una ruta placeholder.

## Fase 1 — App shell

- Layout principal: sidebar + topbar, navegación, breadcrumbs.
- Componentes base de shadcn/ui (`button`, `card`, `dropdown-menu`, `sonner`…).
- Toggle de tema con menú (claro / oscuro / sistema).
- Convenciones de diseño: tokens, espaciado, tipografía, primitivos reutilizables.

## Fase 2 — Integración con Pulsar (cliente tipado)

- `pnpm gen:api` contra el OpenAPI de Pulsar → tipos.
- Cliente `openapi-fetch` + hooks de TanStack Query.
- Manejo de las convenciones REST de Pulsar: errores `application/problem+json`
  (RFC 9457) con `correlation_id`, paginación por **cursor** (`next_cursor` / `Link`).
- Vista de **jobs/runs** con polling del ciclo `queued → running → ok/failed`.

## Fase 3 — Visualización (ECharts)

- Wrapper parametrizable de ECharts integrado con el tema (claro/oscuro, paleta `--chart-*`).
- Primeras vistas de análisis de inventario/movimientos sobre el calendario retail (4-5-4).
- Tipos no convencionales: calendar heatmap, treemap, sankey.

## Fase 4 — Mapas (MapLibre + deck.gl)

- Mapa base MapLibre (sin costos de tiles) integrado con el tema.
- Capas deck.gl: arcos **CEDIS → tienda** (reabasto), heatmaps de demanda/stockouts.

## Fase 5 — Identidad y autorización

- Login con passkeys / OIDC e integración con el servicio central de auth de la suite
  (ver [`../../docs/identidad-y-autorizacion.md`](../../docs/identidad-y-autorizacion.md)).
- PEP en el cliente: gateo de vistas por permiso (proyecto · módulo · acción · scope).

## TODOs sueltos

- [ ] **Evaluar visx** (primitivas D3) para visualizaciones 100% a medida, además de
      ECharts. Su diseño es excelente; se pospuso por mayor curva inicial.
- [ ] **Peer de `openapi-typescript`**: pide TypeScript `^5.x` y el proyecto usa `6.0`.
      Solo afecta a `pnpm gen:api`. Verificar compatibilidad al integrar la Fase 2;
      si falla, fijar una versión compatible o esperar release que soporte TS 6.
- [ ] Definir los primeros `CRUX-STD-*` (nivel proyecto): estructura de carpetas,
      convención de componentes, manejo de estado servidor vs cliente.
- [ ] Tests (Vitest + Testing Library) y CI.
