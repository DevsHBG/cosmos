# CRUX — guía para agentes

**Central Retail Utility & eXecution**: el frontend principal de la suite. SPA que
consume la API REST de [Pulsar](../pulsar) (FastAPI, `/v1`). Contexto completo en
[`README.md`](./README.md); plan en [`ROADMAP.md`](./ROADMAP.md).

## Stack y tooling

React 19 + TypeScript **strict** + **Vite** (SPA, sin SSR). UI con **shadcn/ui** +
**Tailwind v4** (tema por CSS vars, claro/oscuro). Datos: **TanStack Query/Router/Table**

- **Zustand**. Viz: **ECharts**; mapas: **MapLibre + deck.gl**; animación: **Motion**.
  Cliente de API: **openapi-fetch** con tipos generados (`pnpm gen:api`).

* Gestor de paquetes: **pnpm** (obligatorio, `COSMOS-STD-001`). Nunca npm/yarn.
* Lint **oxlint**, formato **Prettier**. Comandos: `pnpm dev|build|typecheck|lint|format`.
* Alias de import: `@/` → `src/`.

## Convenciones

- TS strict + `verbatimModuleSyntax`: usa `import type` para imports de solo tipo.
- Componentes de shadcn/ui van en `src/components/ui/` (se añaden con
  `pnpm dlx shadcn@latest add <componente>`); no los edites a mano salvo para
  parametrizar.
- Estado de **servidor** → TanStack Query; estado de **cliente** → Zustand. No mezclar.
- Estilos: clases de Tailwind con tokens del tema (`bg-background`, `text-muted-foreground`,
  paleta `--chart-*`); combinar clases con `cn()` de `@/lib/utils`.

## Estándares

Hereda los de nivel monorepo (`COSMOS-STD-*`, en
[`../../docs/estandares/`](../../docs/estandares/README.md)). Los de nivel proyecto
(`CRUX-STD-*`) están por definir (ver ROADMAP).

---

Estado: **esqueleto** (Fase 0). Aún sin vistas de negocio.
