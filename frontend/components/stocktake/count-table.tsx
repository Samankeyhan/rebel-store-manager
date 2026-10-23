"use client"

import * as React from "react"
import { Btn, MoneyInput, cardClass, inputClass } from "@/components/record-sale/primitives"
import { formatQuantity } from "@/lib/persian-numbers"
import { moveFocus, type InvalidReason, type RowState } from "@/lib/stocktake"
import { cn } from "@/lib/utils"
import { S } from "./copy"
import type { StockRow } from "./figures"

export type CostValue = number | null | undefined

const invalidText: Record<InvalidReason, string> = {
  format: S.invalidFormat,
  ambiguous: S.invalidAmbiguous,
  notWhole: S.invalidNotWhole,
  tooLarge: S.invalidTooLarge,
}

type Props = {
  rows: StockRow[]
  states: Map<string, RowState>
  counts: Record<string, string>
  costs: Record<string, CostValue>
  /** Rows whose system stock moved since the count: they keep the typed count and must be rechecked. */
  flagged: ReadonlySet<string>
  /** Rows the server refused (key → message). */
  rowErrors: Record<string, string>
  /** After a review attempt: highlight the cost a gain still needs. */
  attempted: boolean
  mobile: boolean
  onCount: (key: string, text: string) => void
  onCost: (key: string, value: CostValue) => void
  onRecheck: (key: string) => void
}

function DifferenceText({ state }: { state: RowState }) {
  if (state.status === "gain" || state.status === "loss") {
    return (
      <span dir="ltr" className={cn("font-bold tabular-nums", state.status === "gain" ? "text-profit" : "text-loss")}>
        {S.signed(state.difference)}
      </span>
    )
  }
  if (state.status === "same") return <span className="text-text-3 tabular-nums">۰</span>
  return <span className="text-text-3">—</span>
}

/** The count table (desktop) or cards (phone). Enter / ↓ moves to the next visible row's count, Shift+Enter / ↑ to the previous. */
export function CountTable(props: Props) {
  const { rows, states, counts, costs, flagged, rowErrors, attempted, mobile, onCount, onCost, onRecheck } = props
  const refs = React.useRef(new Map<string, HTMLInputElement>())
  const keys = React.useMemo(() => rows.map((r) => r.key), [rows])

  const onKeyDown = (key: string) => (e: React.KeyboardEvent<HTMLInputElement>) => {
    const down = e.key === "ArrowDown" || (e.key === "Enter" && !e.shiftKey)
    const up = e.key === "ArrowUp" || (e.key === "Enter" && e.shiftKey)
    if (!down && !up) return
    e.preventDefault()
    const target = moveFocus(keys, key, down ? 1 : -1)
    const input = target ? refs.current.get(target) : null
    if (input) {
      input.focus()
      input.select()
    }
  }

  const countInput = (row: StockRow, state: RowState) => (
    <input
      ref={(el) => {
        if (el) refs.current.set(row.key, el)
        else refs.current.delete(row.key)
      }}
      value={counts[row.key] ?? ""}
      onChange={(e) => onCount(row.key, e.target.value)}
      onKeyDown={onKeyDown(row.key)}
      onFocus={(e) => e.currentTarget.select()}
      inputMode={row.kind === "PRODUCT" ? "numeric" : "decimal"}
      autoComplete="off"
      dir="ltr"
      aria-label={S.countedAria(row.name)}
      aria-invalid={state.status === "invalid" || undefined}
      className={inputClass(state.status === "invalid" ? "error" : flagged.has(row.key) ? "warn" : null, "h-9 w-28 text-end tabular-nums")}
    />
  )

  const costInput = (row: StockRow, state: RowState) => {
    if (state.status !== "gain") return null
    const value = costs[row.key]
    const missing = state.needsCost
    return (
      <MoneyInput
        value={value}
        allowEmpty
        tone={value === null || (missing && attempted) ? "error" : missing ? "warn" : null}
        placeholder={missing ? S.costPlaceholderRequired : S.costPlaceholderOptional}
        aria-label={`${S.colCost} ${row.name}`}
        onValue={(rial) => onCost(row.key, rial)}
        wrapperClassName="w-40"
      />
    )
  }

  const message = (row: StockRow, state: RowState) => {
    const lines: string[] = []
    if (state.status === "invalid" && state.reason) lines.push(invalidText[state.reason])
    if (state.needsCost && attempted) lines.push(S.costRequired)
    if (costs[row.key] === null) lines.push(S.costInvalid)
    if (rowErrors[row.key]) lines.push(rowErrors[row.key])
    return (
      <>
        {lines.map((line) => (
          <span key={line} role="alert" className="block text-xs font-medium text-loss">
            {line}
          </span>
        ))}
        {state.status === "gain" && row.prefillCost != null && costs[row.key] === row.prefillCost && (
          <span className="block text-xs text-text-3">{S.costPrefilled}</span>
        )}
        {state.status === "gain" && row.costZero && costs[row.key] == null && (
          <span className="block text-xs font-medium text-warn">{S.costZeroWarning}</span>
        )}
        {flagged.has(row.key) && (
          <span className="flex items-center gap-2 text-xs font-medium text-warn">
            {S.moved}
            <Btn size="sm" onClick={() => onRecheck(row.key)}>
              {S.recheck}
            </Btn>
          </span>
        )}
      </>
    )
  }

  if (mobile) {
    return (
      <div className="flex flex-col gap-2.5">
        {rows.map((row) => {
          const state = states.get(row.key) as RowState
          return (
            <div key={row.key} className={cn(cardClass, "flex flex-col gap-2 px-3.5 py-3", !row.isActive && "opacity-60")}>
              <div className="flex items-start justify-between gap-2">
                <span className="font-bold">{row.name}</span>
                <span className="text-xs whitespace-nowrap text-text-3">{row.category}</span>
              </div>
              <div className="flex items-center justify-between gap-3 text-[13px]">
                <span className="text-text-2">
                  {S.colSystem}: <span className="font-semibold tabular-nums">{formatQuantity(row.systemQuantity)}</span> {row.unit}
                </span>
                <span className="flex items-center gap-1.5">
                  {S.colDiff}: <DifferenceText state={state} />
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {countInput(row, state)}
                {costInput(row, state)}
              </div>
              {message(row, state)}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className={cn(cardClass, "overflow-x-auto")}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-xs text-text-3">
            <th className="px-3 py-2.5 text-start font-semibold">{S.colName}</th>
            <th className="px-3 py-2.5 text-start font-semibold">{S.colCategory}</th>
            <th className="px-3 py-2.5 text-start font-semibold">{S.colUnit}</th>
            <th className="px-3 py-2.5 text-end font-semibold">{S.colSystem}</th>
            <th className="px-3 py-2.5 text-start font-semibold">{S.colCounted}</th>
            <th className="px-3 py-2.5 text-end font-semibold">{S.colDiff}</th>
            <th className="px-3 py-2.5 text-start font-semibold">{S.colCost}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const state = states.get(row.key) as RowState
            const extra = message(row, state)
            return (
              <tr key={row.key} className={cn("border-b border-border/70 align-top last:border-b-0", !row.isActive && "opacity-60", flagged.has(row.key) && "bg-warn-soft/40")}>
                <td className="px-3 py-2 font-semibold">
                  {row.name}
                  {!row.isActive && <span className="ms-2 text-xs font-medium text-text-3">{S.inactive}</span>}
                  <div className="empty:hidden">{extra}</div>
                </td>
                <td className="px-3 py-2 text-text-2">{row.category}</td>
                <td className="px-3 py-2 text-text-2">{row.unit}</td>
                <td className="px-3 py-2 text-end tabular-nums">{formatQuantity(row.systemQuantity)}</td>
                <td className="px-3 py-1.5">{countInput(row, state)}</td>
                <td className="px-3 py-2 text-end">
                  <DifferenceText state={state} />
                </td>
                <td className="px-3 py-1.5">{costInput(row, state)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
