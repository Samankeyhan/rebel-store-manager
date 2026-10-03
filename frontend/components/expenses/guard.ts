/**
 * Whether «ثبت هزینه» may send POST /expenses. Dependency-free so
 * lib/money-forms.test.mjs can check it. `amount` is integer Toman, or null
 * while MoneyInput holds an amount that isn't exact (Rial, not a multiple of
 * 10) — never submitted. The API accepts a zero amount; a zero expense means
 * nothing, so the screen doesn't.
 */
export function expenseSubmittable(form: { categoryId: number | null; amount: number | null; busy: boolean }): boolean {
  return form.categoryId != null && form.amount !== null && form.amount > 0 && !form.busy
}
