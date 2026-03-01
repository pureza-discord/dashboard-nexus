export function formatPhone(phone: string): string {
  return phone?.replace(/[^+\d]/g, '') || ''
}

export function formatDate(iso: string): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  } catch {
    return iso.slice(0, 10)
  }
}

export function truncate(text: string, max: number): string {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max)}...` : text
}

export function formatCurrency(value: number, locale = 'pt-BR', currency = 'BRL'): string {
  return new Intl.NumberFormat(locale, { style: 'currency', currency }).format(value)
}
