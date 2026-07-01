# CRUX

**Central Retail Utility & eXecution** — el **frontend principal** de la suite. Es la
consola desde donde se usan la mayoría de las funciones de la plataforma: hoy consume
la API REST de [Pulsar](../pulsar) (FastAPI, `/v1`); mañana, las del resto de la suite.

## Qué es y qué llegará a ser

CRUX aspira a ser **el mejor sistema de análisis de retail**: útil _y_ hermoso. No se
queda en el dashboard convencional. La dirección de producto:

- **Visualización no convencional**: gráficas con animaciones y transiciones, tipos
  ricos (sankey, treemap, calendar heatmap, sunburst), no solo barras y líneas.
- **Mapas de datos**: vistas geográficas a escala — p. ej. flujos de reabasto
  CEDIS → tienda, heatmaps de demanda y de stockouts.
- **Movimiento moderno**: animaciones de UI fluidas, sin sacrificar rendimiento.
- **Tema claro/oscuro** de primera clase.
- **Componentes reutilizables y parametrizados**: el sistema de UI es nuestro (código
  en el repo), no una caja negra.

> Estado actual: **esqueleto**. Stack montado y librerías instaladas; aún sin vistas.
> El plan de construcción vive en [el roadmap de Crux](../../codex/30-crux/roadmap/roadmap-crux.md).

## Stack

| Preocupación          | Elección                                                        |
| --------------------- | --------------------------------------------------------------- |
| Framework / build     | **React 19 + TypeScript (strict) + Vite** (SPA, no SSR)         |
| Routing               | **TanStack Router**                                             |
| Estado de servidor    | **TanStack Query** (caché, polling de runs)                     |
| Estado de cliente     | **Zustand**                                                     |
| Tablas / grids        | **TanStack Table**                                              |
| Gráficas              | **Apache ECharts** (`echarts-for-react`) · _TODO: evaluar visx_ |
| Mapas                 | **MapLibre GL** + **deck.gl** (`react-map-gl`)                  |
| Animación de UI       | **Motion**                                                      |
| Componentes / estilos | **shadcn/ui** + **Tailwind CSS v4** (tema por CSS vars)         |
| Cliente API           | **openapi-fetch** + tipos generados desde el OpenAPI de Pulsar  |
| Lint / formato        | **oxlint** + **Prettier**                                       |

Por qué este stack y no otro: el factor decisivo fue el ecosistema de visualización
React-first (ECharts, deck.gl, visx, Motion, shadcn). Resumen del debate en la memoria
del proyecto.

## Estructura

```
src/
  api/         # cliente tipado de Pulsar (gen:api → schema.d.ts)
  components/
    ui/        # componentes de shadcn/ui
    theme-provider.tsx
  hooks/       # hooks reutilizables
  lib/         # utilidades (cn, helpers)
  routes/      # vistas (TanStack Router, code-based por ahora)
  stores/      # estado de cliente (Zustand)
  main.tsx     # providers: Theme + Query + Router
  index.css    # Tailwind v4 + tokens de tema (claro/oscuro)
```

## Desarrollo

Requiere **Node ≥ 20.19** y **pnpm** (estándar del monorepo,
[`COSMOS-STD-001`](../../codex/10-monorepo/estandares/cosmos-std-001-gestor-de-paquetes.md)).

```bash
pnpm install        # instalar dependencias
pnpm dev            # servidor de desarrollo (Vite)
pnpm build          # typecheck + build de producción
pnpm typecheck      # solo chequeo de tipos
pnpm lint           # oxlint
pnpm format         # Prettier --write
pnpm gen:api        # regenerar el cliente tipado desde el OpenAPI de Pulsar
```

Configuración local: copia [`.env.example`](./.env.example) a `.env` y ajusta
`VITE_API_BASE_URL` si tu API de Pulsar no corre en `http://localhost:8000`.

## Estándares

CRUX hereda los estándares de nivel monorepo (`COSMOS-STD-*`) y tendrá los suyos de
nivel proyecto (`CRUX-STD-*`) cuando los definamos. Marco de gobernanza:
[`codex/10-monorepo/moc-monorepo.md`](../../codex/10-monorepo/moc-monorepo.md).
Documentación completa del proyecto: [`codex/30-crux/moc-crux.md`](../../codex/30-crux/moc-crux.md).
