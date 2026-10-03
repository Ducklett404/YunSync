export const runtimeConfig = {
  dataMode: (import.meta.env.VITE_DATA_MODE || 'demo') as 'demo' | 'real',
  showDemoBadge: import.meta.env.VITE_DATA_MODE !== 'real',
}
