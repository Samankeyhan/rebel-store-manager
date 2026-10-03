"use client"

import * as React from "react"
import { Plus, Tag, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Money } from "@/components/common/money"
import { T, type Channel } from "./copy"
import type { LineView } from "./derive"
import { moneyProps } from "./money-field"
import { Btn, Help, InlineMessage, MoneyInput, SectionCard, Stepper, cardClass } from "./primitives"
import { ProductPicker } from "./product-picker"
import { discountField, priceField, type Action, type MoneyField, type Product } from "./state"

type ItemsProps = {
  lines: LineView[]
  products: Product[]
  channel: Channel
  itemsNet: number
  /** Money fields whose typed amount isn't exact (see state.ts MoneyField). */
  invalidMoney: MoneyField[]
  dispatch: React.Dispatch<Action>
  onAddLine: () => void
  openPicker: number | null
  setOpenPicker: (key: number | null) => void
  mobile: boolean
}

function LineMessages({ view, dispatch }: { view: LineView; dispatch: React.Dispatch<Action> }) {
  return (
    <>
      {view.messages.map((m, i) => (
        <InlineMessage key={i} severity={m.severity} icon={m.icon}>
          <span>{m.text}</span>
          {m.useMax !== undefined && (
            <button
              type="button"
              className="cursor-pointer text-xs font-bold text-heading hover:text-primary"
              onClick={() => dispatch({ type: "line", key: view.line.key, patch: { qty: m.useMax } })}
            >
              {T.v2UseMax(m.useMax)}
            </button>
          )}
          {m.toDraft && (
            <button
              type="button"
              className="cursor-pointer text-xs font-bold text-heading hover:text-primary"
              onClick={() => dispatch({ type: "status", status: "DRAFT" })}
            >
              {T.saveAsDraft}
            </button>
          )}
        </InlineMessage>
      ))}
    </>
  )
}

function DiscountFields({
  view,
  invalid,
  dispatch,
  mobile,
}: {
  view: LineView
  invalid: { invalidMoney: MoneyField[] }
  dispatch: React.Dispatch<Action>
  mobile: boolean
}) {
  const { line } = view
  const key = line.key
  const amount = (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={`disc-${key}`} className="text-xs font-semibold">
        {T.discountAmount}
      </label>
      <MoneyInput
        id={`disc-${key}`}
        {...moneyProps(invalid, dispatch, discountField(key), line.discount, (n) => dispatch({ type: "line", key, patch: { discount: n } }))}
        tone={view.discountError ? "error" : null}
        className={mobile ? "h-11" : "h-9"}
      />
    </div>
  )
  const reason = (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={`reason-${key}`} className="text-xs font-semibold">
        {T.discountReason} <span className="font-normal text-text-3">{T.optional}</span>
      </label>
      <input
        id={`reason-${key}`}
        value={line.discountReason}
        onChange={(e) => dispatch({ type: "line", key, patch: { discountReason: e.target.value } })}
        placeholder={T.discountReasonPlaceholder}
        className={cn(
          "w-full rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
          mobile ? "h-11" : "h-9"
        )}
      />
    </div>
  )
  if (mobile) {
    return (
      <div className="flex flex-col gap-2 rounded-lg bg-surface-2 p-2.5">
        {amount}
        {reason}
      </div>
    )
  }
  return (
    <div className="grid grid-cols-[170px_minmax(0,1fr)_auto] items-start gap-2.5 rounded-lg bg-surface-2 p-2.5">
      {amount}
      {reason}
      <Btn variant="ghost" size="sm" className="mt-6" onClick={() => clearDiscount(dispatch, key)}>
        {T.removeDiscount}
      </Btn>
    </div>
  )
}

function clearDiscount(dispatch: React.Dispatch<Action>, key: number) {
  dispatch({ type: "line", key, patch: { discountOpen: false, discount: 0, discountReason: "" } })
}

function AddDiscountButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex cursor-pointer items-center gap-1.5 self-start rounded text-[12.5px] font-semibold text-heading outline-none hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/30"
    >
      <Tag className="size-3.5" aria-hidden />
      {T.addDiscount}
    </button>
  )
}

function DesktopLine({ view, props }: { view: LineView; props: ItemsProps }) {
  const { dispatch } = props
  const { line, product } = view
  const key = line.key
  const priceNote = !product
    ? ""
    : line.priceEdited
      ? T.priceManual(view.defaultPrice)
      : props.channel === "WHOLESALE"
        ? T.priceWholesale
        : T.priceRetail
  return (
    <div className="flex flex-col gap-2 border-b border-border py-3">
      <div className="grid grid-cols-[minmax(0,1fr)_104px_144px_110px_36px] items-start gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <ProductPicker
            view={view}
            products={props.products}
            channel={props.channel}
            open={props.openPicker === key}
            onOpenChange={(o) => props.setOpenPicker(o ? key : null)}
            onPick={(p) => dispatch({ type: "pickProduct", key, product: p })}
          />
          <Help>{view.meta}</Help>
        </div>
        <Stepper
          value={line.qty}
          onValue={(n) => dispatch({ type: "line", key, patch: { qty: n } })}
          tone={view.qtyTone}
        />
        <div className="flex flex-col gap-1">
          <MoneyInput
            aria-label={T.unitPriceAria}
            {...moneyProps(props, dispatch, priceField(key), line.unitPrice, (n) => dispatch({ type: "price", key, value: n }))}
          />
          <Help className="text-[11.5px]">{priceNote}</Help>
        </div>
        <div className="flex flex-col items-start pt-2 leading-[1.3]">
          <Money value={view.net} className="font-bold" />
          {view.net !== view.gross && <Money value={view.gross} className="text-xs text-text-3 line-through" />}
        </div>
        <Btn
          variant="ghost"
          className="w-9 px-0"
          aria-label={T.removeRow}
          onClick={() => dispatch({ type: "removeLine", key })}
        >
          <Trash2 className="size-4" />
        </Btn>
      </div>
      <LineMessages view={view} dispatch={dispatch} />
      {line.discountOpen ? (
        <DiscountFields view={view} invalid={props} dispatch={dispatch} mobile={false} />
      ) : (
        <AddDiscountButton onClick={() => dispatch({ type: "line", key, patch: { discountOpen: true } })} />
      )}
    </div>
  )
}

function MobileLine({ view, props }: { view: LineView; props: ItemsProps }) {
  const { dispatch } = props
  const { line } = view
  const key = line.key
  const total = (
    <span className="text-[13px]">
      {T.rowTotalMobile}{" "}
      {view.net !== view.gross && (
        <Money value={view.gross} className="text-xs text-text-3 line-through" />
      )}{" "}
      <b>
        <Money value={view.net} />
      </b>
    </span>
  )
  return (
    <div className="flex flex-col gap-2.5 border-b border-border px-3.5 py-3">
      <div className="flex items-center gap-2">
        <div className="min-w-0 grow">
          <ProductPicker
            view={view}
            products={props.products}
            channel={props.channel}
            open={props.openPicker === key}
            onOpenChange={(o) => props.setOpenPicker(o ? key : null)}
            onPick={(p) => dispatch({ type: "pickProduct", key, product: p })}
            mobile
          />
        </div>
        <Btn
          variant="ghost"
          className="size-11 px-0"
          aria-label={T.removeRow}
          onClick={() => dispatch({ type: "removeLine", key })}
        >
          <Trash2 className="size-4" />
        </Btn>
      </div>
      <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-2">
        <Stepper
          size="mobile"
          value={line.qty}
          onValue={(n) => dispatch({ type: "line", key, patch: { qty: n } })}
          tone={view.qtyTone}
        />
        <MoneyInput
          aria-label={T.unitPriceAria}
          {...moneyProps(props, dispatch, priceField(key), line.unitPrice, (n) => dispatch({ type: "price", key, value: n }))}
          className="h-11"
        />
      </div>
      <LineMessages view={view} dispatch={dispatch} />
      {line.discountOpen && <DiscountFields view={view} invalid={props} dispatch={dispatch} mobile />}
      <div className="flex items-center justify-between">
        {line.discountOpen ? (
          <Btn variant="ghost" size="sm" onClick={() => clearDiscount(dispatch, key)}>
            {T.removeDiscount}
          </Btn>
        ) : (
          <AddDiscountButton onClick={() => dispatch({ type: "line", key, patch: { discountOpen: true } })} />
        )}
        {total}
      </div>
    </div>
  )
}

export function ItemsCard(props: ItemsProps) {
  const { lines, mobile } = props
  if (mobile) {
    return (
      <section className={cn(cardClass, "flex flex-col")} aria-labelledby="s2">
        <div className="flex justify-between px-3.5 pt-3.5 pb-1">
          <h2 id="s2" className="text-sm font-bold text-heading">
            {T.itemsCard}
          </h2>
          <span className="text-xs text-text-3">{T.rowCount(lines.length)}</span>
        </div>
        {lines.map((v) => (
          <MobileLine key={v.line.key} view={v} props={props} />
        ))}
        <div className="px-3.5 py-3">
          <Btn className="h-11 w-full" onClick={props.onAddLine}>
            <Plus className="size-3.5" />
            {T.addProductMobile}
          </Btn>
        </div>
      </section>
    )
  }
  return (
    <SectionCard id="s2" title={T.itemsCard} caption={T.rowCount(lines.length)} bodyClassName="px-5 pt-1 pb-4">
      <div className="grid grid-cols-[minmax(0,1fr)_104px_144px_110px_36px] gap-3 border-b border-border pt-2.5 pb-1.5 text-xs font-bold text-text-3">
        <span>{T.colProduct}</span>
        <span>{T.colQty}</span>
        <span>{T.colUnitPrice}</span>
        <span>{T.colRowTotal}</span>
        <span />
      </div>
      {lines.map((v) => (
        <DesktopLine key={v.line.key} view={v} props={props} />
      ))}
      <div className="flex items-center justify-between pt-3">
        <Btn size="sm" onClick={props.onAddLine}>
          <Plus className="size-3.5" />
          {T.addRow}
        </Btn>
        <span className="text-[13px] text-text-3">
          {T.itemsNetFooter}{" "}
          <b className="text-foreground">
            <Money value={props.itemsNet} />
          </b>
        </span>
      </div>
    </SectionCard>
  )
}
