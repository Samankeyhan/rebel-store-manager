import type { Action, FormState, MoneyField } from "./state"

/**
 * MoneyInput props for a record-sale amount: shows null (and so the field's
 * own error) while the typed amount isn't exact Toman, and flags/unflags the
 * field in the reducer so the order can't be saved meanwhile.
 */
export function moneyProps(
  state: Pick<FormState, "invalidMoney">,
  dispatch: React.Dispatch<Action>,
  field: MoneyField,
  value: number,
  onExact: (toman: number) => void
) {
  return {
    value: state.invalidMoney.includes(field) ? null : value,
    onValue: (v: number | null | undefined) => {
      if (v == null) {
        dispatch({ type: "moneyInvalid", field, invalid: true })
        return
      }
      onExact(v)
      dispatch({ type: "moneyInvalid", field, invalid: false })
    },
  }
}
