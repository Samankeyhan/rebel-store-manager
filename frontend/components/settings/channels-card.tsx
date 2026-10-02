"use client"

import { Switch } from "@/components/products/drawer-shell"
import { CHANNEL_IDS, CHANNELS, type Channel } from "@/components/record-sale/copy"
import { Alert, ChannelBadge, Help, InlineMessage, IntInput, Label, cardClass } from "@/components/record-sale/primitives"
import type { KitDetail } from "@/lib/api"
import { cn } from "@/lib/utils"
import { S, joinList } from "./copy"
import type { ChannelDraft, Draft } from "./draft"
import { KitPicker, isInactiveChoice } from "./kit-picker"

type Props = {
  draft: Draft
  kits: KitDetail[]
  /** The estimate the hero shows (echoed on channels whose postage is on). */
  estimate: number
  shippingError: string | null
  onShipping: (n: number) => void
  onChannel: (channel: Channel, patch: Partial<ChannelDraft>) => void
  mobile: boolean
}

function SwitchCell({
  id,
  aria,
  checked,
  onChange,
  caption,
}: {
  id: string
  aria: string
  checked: boolean
  onChange: (on: boolean) => void
  caption: string
}) {
  return (
    <span className="flex items-center">
      <span id={id} className="sr-only">
        {aria}
      </span>
      <Switch checked={checked} onChange={onChange} labelledBy={id} />
      <span className={cn("ms-2.5 text-xs tabular-nums", checked ? "text-foreground" : "text-text-3")}>{caption}</span>
    </span>
  )
}

/** [1] ارسال و کانال‌ها: the one default shipping amount, then each channel's two switches and default kit. */
export function ChannelsCard({ draft, kits, estimate, shippingError, onShipping, onChannel, mobile }: Props) {
  const inactiveChannels = CHANNEL_IDS.filter((c) => isInactiveChoice(draft.channels[c].kit, kits))
  const inactiveAlert = inactiveChannels.length > 0 && (
    <Alert tone="warn" icon="triangle" title={S.kitInactiveTitle}>
      {S.kitInactiveWarn(joinList(inactiveChannels.map((c) => `«${CHANNELS[c].name}»`), 5))}
    </Alert>
  )
  const shipCaption = (on: boolean) => (on ? S.shipOn(draft.default_shipping_charge) : S.off)
  const postCaption = (on: boolean) => (on ? S.postOn(estimate) : S.off)

  const shippingField = (
    <div className={cn("flex flex-col gap-1.5", !mobile && "max-w-[320px]")}>
      <Label htmlFor="st-shipping">{S.shippingLabel}</Label>
      <IntInput
        id="st-shipping"
        value={draft.default_shipping_charge}
        onValue={onShipping}
        suffix={S.toman}
        tone={shippingError ? "error" : null}
        className={mobile ? "h-12 text-base" : undefined}
        aria-invalid={shippingError ? true : undefined}
      />
      {shippingError ? (
        <InlineMessage severity="error">{shippingError}</InlineMessage>
      ) : (
        !mobile && <Help>{S.shippingHelp}</Help>
      )}
    </div>
  )

  if (mobile) {
    return (
      <>
        <section id="ship" className={cn(cardClass, "flex flex-col gap-3 p-3.5")} aria-labelledby="st1">
          <h2 id="st1" className="text-sm font-bold text-heading">
            {S.shipTitleMobile}
          </h2>
          {shippingField}
        </section>
        <section className={cn(cardClass, "overflow-hidden")} aria-labelledby="st1c">
          <h2 id="st1c" className="px-3.5 pt-3.5 pb-3 text-sm font-bold text-heading">
            {S.channelsTitleMobile}
          </h2>
          {inactiveAlert && <div className="px-3.5 pb-3">{inactiveAlert}</div>}
          {CHANNEL_IDS.map((c) => {
            const d = draft.channels[c]
            const name = CHANNELS[c].name
            return (
              <div key={c} className="flex flex-col gap-2.5 border-t border-border px-3.5 py-3">
                <div className="flex items-center justify-between gap-3">
                  <ChannelBadge channel={c} />
                  <div className="w-[200px] min-w-0">
                    <KitPicker value={d.kit} kits={kits} onChange={(kit) => onChannel(c, { kit })} label={S.kitAria(name)} mobile />
                  </div>
                </div>
                <div className="flex flex-wrap gap-4">
                  <label className="flex min-h-9 items-center gap-2 text-[13px]">
                    <span id={`m-ship-${c}`} className="sr-only">
                      {S.switchShippingAria(name)}
                    </span>
                    <Switch
                      checked={d.applies_shipping_charge === 1}
                      onChange={(on) => onChannel(c, { applies_shipping_charge: on ? 1 : 0 })}
                      labelledBy={`m-ship-${c}`}
                    />
                    <span aria-hidden>{S.switchShippingMobile}</span>
                  </label>
                  <label className="flex min-h-9 items-center gap-2 text-[13px]">
                    <span id={`m-post-${c}`} className="sr-only">
                      {S.switchPostageAria(name)}
                    </span>
                    <Switch
                      checked={d.applies_postage === 1}
                      onChange={(on) => onChannel(c, { applies_postage: on ? 1 : 0 })}
                      labelledBy={`m-post-${c}`}
                    />
                    <span aria-hidden>{S.switchPostageMobile}</span>
                  </label>
                </div>
              </div>
            )
          })}
        </section>
      </>
    )
  }

  return (
    <section id="ship" className={cn(cardClass, "scroll-mt-6")} aria-labelledby="st1">
      <div className="flex flex-col gap-0.5 border-b border-border px-5 py-4">
        <h2 id="st1" className="text-base leading-[26px] font-bold text-heading">
          {S.shipTitle}
        </h2>
        <span className="text-xs text-text-3">{S.shipCaption}</span>
      </div>
      <div className="flex flex-col gap-5 p-5">
        {shippingField}
        {inactiveAlert}
        <div className="overflow-hidden rounded-[10px] border border-border">
          <table className="w-full border-separate border-spacing-0 text-[13.5px]">
            <thead>
              <tr className="text-xs font-semibold text-text-3 [&>th]:h-10 [&>th]:border-b [&>th]:border-border [&>th]:bg-surface-2 [&>th]:px-4 [&>th]:text-start [&>th]:whitespace-nowrap">
                <th scope="col">{S.colChannel}</th>
                <th scope="col">{S.colShipping}</th>
                <th scope="col">{S.colPostage}</th>
                <th scope="col">{S.colKit}</th>
              </tr>
            </thead>
            <tbody>
              {CHANNEL_IDS.map((c, i) => {
                const d = draft.channels[c]
                const name = CHANNELS[c].name
                return (
                  <tr
                    key={c}
                    className={cn(
                      "[&>td]:h-14 [&>td]:px-4 [&>td]:whitespace-nowrap",
                      i < CHANNEL_IDS.length - 1 && "[&>td]:border-b [&>td]:border-border"
                    )}
                  >
                    <td>
                      <ChannelBadge channel={c} />
                    </td>
                    <td>
                      <SwitchCell
                        id={`sw-ship-${c}`}
                        aria={S.switchShippingAria(name)}
                        checked={d.applies_shipping_charge === 1}
                        onChange={(on) => onChannel(c, { applies_shipping_charge: on ? 1 : 0 })}
                        caption={shipCaption(d.applies_shipping_charge === 1)}
                      />
                    </td>
                    <td>
                      <SwitchCell
                        id={`sw-post-${c}`}
                        aria={S.switchPostageAria(name)}
                        checked={d.applies_postage === 1}
                        onChange={(on) => onChannel(c, { applies_postage: on ? 1 : 0 })}
                        caption={postCaption(d.applies_postage === 1)}
                      />
                    </td>
                    <td>
                      <KitPicker value={d.kit} kits={kits} onChange={(kit) => onChannel(c, { kit })} label={S.kitAria(name)} mobile={false} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
