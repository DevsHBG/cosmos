import { createContext, useContext } from 'react'

export type Theme = 'dark' | 'light' | 'system'

export type ThemeProviderState = {
  theme: Theme
  setTheme: (theme: Theme) => void
}

const initialState: ThemeProviderState = {
  theme: 'system',
  setTheme: () => null,
}

export const ThemeProviderContext = createContext<ThemeProviderState>(initialState)

/** Lee el tema actual y su setter. Debe usarse dentro de un `ThemeProvider`. */
export function useTheme() {
  const context = useContext(ThemeProviderContext)
  if (context === undefined) {
    throw new Error('useTheme debe usarse dentro de un ThemeProvider')
  }
  return context
}
