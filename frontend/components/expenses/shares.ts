/**
 * Whole-percent shares for the «به تفکیک دسته» meters and the mobile stacked
 * bar (design 11 §7: one rounding rule for both). Largest remainder: floor
 * every share, then hand the leftover points to the largest fractional parts
 * (ties: the earlier row, i.e. the larger amount) so the shown percents sum
 * to exactly 100. Display only — amounts are always the API's.
 */
export function sharesOf(amounts: number[]): number[] {
  const sum = amounts.reduce((s, a) => s + a, 0)
  if (sum <= 0) return amounts.map(() => 0)
  const raw = amounts.map((a) => (a * 100) / sum)
  const shares = raw.map(Math.floor)
  let left = 100 - shares.reduce((s, p) => s + p, 0)
  const order = raw.map((r, i) => [r - Math.floor(r), i] as const).sort((a, b) => b[0] - a[0] || a[1] - b[1])
  for (const [, i] of order) {
    if (left <= 0) break
    shares[i] += 1
    left -= 1
  }
  return shares
}
