"use client"

import * as React from "react"
import { Info, Lock, PencilLine } from "lucide-react"
import type { Catalog } from "@/lib/api"
import { cn } from "@/lib/utils"
import { formatMoney, formatNumber } from "@/lib/persian-numbers"
import { CHANNEL_IDS, CHANNELS, STATUS_IDS, STATUSES, T, type Channel, type SaleStatus } from "./copy"
import { channelSummaryLine, resolveKit, type Summary } from "./derive"
import { Help, IntInput, Label, OptionTile, PostageBadge, SectionCard, cardClass } from "./primitives"
import type { Action, FormState, KitChoice } from "./state"

type CardProps = {
  state: FormState
  catalog: Catalog
  dispatch: React.Dispatch<Action>
  onChannel: (c: Channel) => void
  summary: Summary
  mobile: boolean
}

// ── [1] کانال فروش و مشتری ──────────────────────────────────────────────

export function ChannelCard({ state, catalog, dispatch, onChannel, mobile }: CardProps) {
  const radios = (
    <div
      role="radiogroup"
      aria-label={T.channelLabel}
      className={cn("grid gap-2.5", mobile ? "grid-cols-3 gap-2" : "grid-cols-5")}
    >
      {CHANNEL_IDS.map((id) => {
        const meta = CHANNELS[id]
        const settings = catalog.settings.channels[id]
        const Icon = meta.icon
        if (mobile) {
          return (
            <OptionTile
              key={id}
              selected={state.channel === id}
              onSelect={() => onChannel(id)}
              className="min-h-16 items-center justify-center"
            >
              <Icon className={cn("size-[18px]", meta.text)} aria-hidden />
              <span className="text-[12.5px] font-bold">{meta.name}</span>
            </OptionTile>
          )
        }
        return (
          <OptionTile key={id} selected={state.channel === id} onSelect={() => onChannel(id)}>
            <span className="flex items-center gap-2 text-[13.5px] font-bold">
              <Icon className={cn("size-[18px]", meta.text)} aria-hidden />
              {meta.name}
            </span>
            <span className="text-xs text-text-3">
              {settings?.applies_shipping_charge
                ? T.tileShip(catalog.settings.default_shipping_charge)
                : meta.noShipTile}
            </span>
            <span className="text-xs text-text-3">
              {settings?.applies_postage ? T.tilePostOn : T.tilePostOff}
            </span>
          </OptionTile>
        )
      })}
    </div>
  )

  const customer = (
    <div className={cn("flex flex-col gap-1.5", !mobile && "max-w-[360px]")}>
      <Label htmlFor="sale-customer" optional>
        {T.customerLabel}
      </Label>
      <input
        id="sale-customer"
        value={state.customerName}
        onChange={(e) => dispatch({ type: "customer", value: e.target.value })}
        placeholder={T.customerPlaceholder}
        className={cn(
          "w-full rounded-lg border border-border-strong bg-card px-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
          mobile ? "h-11" : "h-10"
        )}
      />
      {!mobile && <Help>{T.customerHelp}</Help>}
    </div>
  )

  if (mobile) {
    return (
      <section className={cn(cardClass, "flex flex-col gap-3 p-3.5")} aria-labelledby="s1">
        <h2 id="s1" className="text-sm font-bold text-heading">
          {T.channelLabel}
        </h2>
        {radios}
        <p className="text-xs leading-[19px] text-text-3">{channelSummaryLine(state, catalog)}</p>
        {customer}
      </section>
    )
  }

  return (
    <SectionCard id="s1" title={T.channelCard} caption={T.channelCardCaption} bodyClassName="flex flex-col gap-4">
      {radios}
      <p className="text-xs leading-[19px] text-text-3">{T.channelHelp}</p>
      {customer}
    </SectionCard>
  )
}

// ── [3] ارسال و بسته‌بندی ────────────────────────────────────────────────

/** The tile matching the channel's own default carries «پیش‌فرض». */
function kitTiles(state: FormState, catalog: Catalog) {
  const defaultId = catalog.settings.channels[state.channel]?.default_packaging_kit_id ?? null
  const selected = resolveKit(state, catalog)
  const tiles: { key: string; name: string; cost: number; desc: string; isDefault: boolean; on: boolean; choice: KitChoice }[] =
    catalog.kits.map((k) => ({
      key: `k${k.id}`,
      name: k.name,
      cost: k.kit_cost,
      // KitDetailOut has no description: show what the kit is made of.
      desc: k.items.map((i) => i.material_name).join("، "),
      isDefault: k.id === defaultId,
      on: selected?.id === k.id,
      choice: k.id === defaultId ? { kind: "default" } : { kind: "kit", id: k.id },
    }))
  tiles.push({
    key: "none",
    name: T.noKit,
    cost: 0,
    desc: T.noKitDesc,
    isDefault: defaultId == null,
    on: selected == null,
    choice: defaultId == null ? { kind: "default" } : { kind: "none" },
  })
  return tiles
}

export function ShippingCard({ state, catalog, dispatch, summary, mobile }: CardProps) {
  const channelName = CHANNELS[state.channel].name
  const applies = !!catalog.settings.channels[state.channel]?.applies_shipping_charge
  const over = summary.shippingOverridden

  const shipping = (
    <div className={cn("flex flex-col gap-1.5", !mobile && "max-w-[320px]")}>
      <Label htmlFor="sale-ship">{mobile ? T.shippingLabelMobile : T.shippingLabel}</Label>
      <IntInput
        id="sale-ship"
        value={summary.shipping}
        onValue={(n) => dispatch({ type: "shipping", value: n })}
        tone={over ? "warn" : null}
        suffix={T.toman}
        className={mobile ? "h-11" : undefined}
      />
      {over ? (
        <span className="flex flex-wrap items-center gap-1.5 text-xs leading-[19px] text-warn">
          <PencilLine className="size-3.5 shrink-0" aria-hidden />
          <span>
            {mobile
              ? T.shippingOverrideMobile(summary.shippingDefault)
              : T.shippingOverride(channelName, summary.shippingDefault)}
          </span>
          <button
            type="button"
            onClick={() => dispatch({ type: "shipping", value: null })}
            className="cursor-pointer rounded text-xs font-bold text-heading outline-none hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/30"
          >
            {T.restore}
          </button>
        </span>
      ) : (
        !mobile && (
          <Help>{applies ? T.shippingDefaultHelp(channelName) : CHANNELS[state.channel].noShipHelp}</Help>
        )
      )}
    </div>
  )

  const kits = (
    <div className="flex flex-col gap-1.5">
      <span className="flex items-center gap-1 text-[13px] font-semibold">
        {T.kitLabel}
        {!mobile && (
          <span className="ms-1 inline-flex h-5 items-center gap-1 rounded-md bg-surface-2 px-2 text-[11px] font-normal text-text-2">
            <Lock className="size-3" aria-hidden /> {T.internalChip}
          </span>
        )}
      </span>
      <div role="radiogroup" aria-label={T.kitLabel} className={cn("grid gap-2.5", mobile ? "grid-cols-2 gap-2" : "grid-cols-4")}>
        {kitTiles(state, catalog).map((k) => (
          <OptionTile
            key={k.key}
            selected={k.on}
            onSelect={() => dispatch({ type: "kit", choice: k.choice })}
            tag={!mobile && k.isDefault ? T.defaultTag : undefined}
            className={mobile ? "min-h-14" : undefined}
          >
            <span className="pe-12 text-[13.5px] font-bold">{k.name}</span>
            <span className="text-xs text-text-3 tabular-nums">{T.kitCost(k.cost)}</span>
            {!mobile && k.desc && <span className="line-clamp-2 text-xs text-text-3">{k.desc}</span>}
          </OptionTile>
        ))}
      </div>
      {!mobile && <Help>{T.kitHelp}</Help>}
    </div>
  )

  if (mobile) {
    return (
      <section className={cn(cardClass, "flex flex-col gap-3.5 p-3.5")} aria-labelledby="s3">
        <h2 id="s3" className="text-sm font-bold text-heading">
          {T.shippingCard}
        </h2>
        {shipping}
        {kits}
      </section>
    )
  }
  return (
    <SectionCard id="s3" title={T.shippingCard} bodyClassName="flex flex-col gap-[18px]">
      {shipping}
      {kits}
    </SectionCard>
  )
}

// ── [4a] هزینه‌های داخلی ─────────────────────────────────────────────────

export function InternalCostsCard({ state, catalog, dispatch, summary, mobile }: CardProps) {
  const window = catalog.settings.postage_estimate_window
  if (mobile) {
    return (
      <section className={cn(cardClass, "flex flex-col gap-3.5 bg-surface-2 p-3.5")} aria-labelledby="s4">
        <h2 id="s4" className="flex items-center gap-1.5 text-sm font-bold text-heading">
          <Lock className="size-4" aria-hidden />
          {T.internalCard}
        </h2>
        <div className="grid grid-cols-2 gap-2">
          <div className="flex min-w-0 flex-col gap-1.5">
            <span className="text-xs font-semibold">{T.postageLabelMobile}</span>
            <div className="flex h-11 items-center rounded-lg border border-dashed border-border-strong bg-card px-3">
              <b className={cn("tabular-nums", !summary.postageOn && "text-text-3")}>{formatNumber(summary.postage)}</b>
            </div>
            <span className="text-[11px] leading-[17px] text-text-3">
              {summary.postageOn ? T.postageHint(window) : T.postageHelpOff(CHANNELS[state.channel].name)}
            </span>
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="sale-fee" className="text-xs font-semibold">
              {T.feeLabel}
            </label>
            <IntInput id="sale-fee" value={state.fee} onValue={(n) => dispatch({ type: "fee", value: n })} className="h-11" />
          </div>
        </div>
        <Help>{T.internalMobileNote}</Help>
      </section>
    )
  }
  return (
    <SectionCard
      id="s4"
      title={T.internalCard}
      caption={T.internalCardCaption}
      icon={<Lock className="size-4" aria-hidden />}
      bodyClassName="flex flex-col gap-3.5"
    >
      <div className="flex flex-col gap-1.5">
        <Label>{T.postageLabel}</Label>
        <div className="flex h-10 items-center justify-between gap-2 rounded-lg border border-dashed border-border-strong bg-surface-2 px-3">
          <span className={cn("font-bold tabular-nums", !summary.postageOn && "text-text-3")}>
            {formatMoney(summary.postage)}
          </span>
          <PostageBadge on={summary.postageOn} />
        </div>
        <Help>{summary.postageOn ? T.postageHelpOn(window) : T.postageHelpOff(CHANNELS[state.channel].name)}</Help>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="sale-fee">{T.feeLabel}</Label>
        <IntInput id="sale-fee" value={state.fee} onValue={(n) => dispatch({ type: "fee", value: n })} suffix={T.toman} />
        <Help>{T.feeHelp}</Help>
      </div>
    </SectionCard>
  )
}

// ── [4b] وضعیت سفارش ─────────────────────────────────────────────────────

export function StatusCard({ state, dispatch, mobile }: CardProps) {
  const seg = (
    <div
      role="radiogroup"
      aria-label={T.statusAria}
      className={cn(
        "w-full gap-0.5 rounded-[10px] border border-border bg-surface-2 p-[3px]",
        mobile ? "grid grid-cols-2" : "flex"
      )}
    >
      {STATUS_IDS.map((id) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={state.status === id}
          onClick={() => dispatch({ type: "status", status: id as SaleStatus })}
          className={cn(
            "cursor-pointer rounded-[7px] px-1.5 text-[13px] font-semibold whitespace-nowrap text-text-2 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
            mobile ? "h-10" : "h-[34px] grow",
            state.status === id && "bg-card text-heading shadow-[0_4px_14px_rgba(18,22,38,.08)]"
          )}
        >
          {STATUSES[id].name}
        </button>
      ))}
    </div>
  )
  if (mobile) {
    return (
      <section className={cn(cardClass, "flex flex-col gap-2.5 p-3.5")} aria-labelledby="s5">
        <h2 id="s5" className="text-sm font-bold text-heading">
          {T.statusCard}
        </h2>
        {seg}
        <p className="text-xs leading-[19px] text-text-3">
          <b>{T.draftNoteBold}</b>
          {T.draftNoteRestMobile}
        </p>
      </section>
    )
  }
  return (
    <SectionCard id="s5" title={T.statusCard} bodyClassName="flex flex-col gap-3">
      {seg}
      <p className="flex gap-1.5 text-xs leading-[19px] text-text-3">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>{STATUSES[state.status].help}</span>
      </p>
      <p className="text-xs leading-[19px] text-text-3">
        <b>{T.draftNoteBold}</b>
        {T.draftNoteRest}
      </p>
    </SectionCard>
  )
}
