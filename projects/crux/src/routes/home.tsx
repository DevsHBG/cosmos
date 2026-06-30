import { useTheme } from '@/components/theme-context'

/**
 * Página placeholder. Confirma que el stack (Vite + React + Tailwind + theming)
 * está vivo. Aquí se construirá la consola de análisis; hoy es solo esqueleto.
 */
export function HomePage() {
  const { theme, setTheme } = useTheme()

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 p-8 text-center">
      <div className="space-y-3">
        <p className="text-xs font-medium tracking-[0.2em] text-muted-foreground uppercase">
          Central Retail Utility &amp; eXecution
        </p>
        <h1 className="text-5xl font-semibold tracking-tight">CRUX</h1>
        <p className="max-w-md text-muted-foreground">
          Esqueleto listo. El frontend de la suite Pulsar aún no tiene vistas — aquí vivirá la
          consola de análisis de retail.
        </p>
      </div>

      <button
        type="button"
        onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        className="rounded-md border border-border bg-card px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
      >
        Tema: {theme}
      </button>
    </main>
  )
}
