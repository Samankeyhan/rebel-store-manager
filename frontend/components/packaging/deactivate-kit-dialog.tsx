"use client"

import * as React from "react"
import { Ban, ChevronDown } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ConfirmShell } from "@/components/orders/detail/confirm-shell"
import { ChannelBadge } from "@/components/common/status"
import { CHANNELS, type Channel } from "@/components/record-sale/copy"
import { Alert } from "@/components/record-sale/primitives"
import { ApiError, deactivateKit, updateChannelSettings, type KitDetail } from "@/lib/api"
import { cn } from "@/lib/utils"
import { K } from "./copy"

const NONE = "none"
const channelName = (c: string) => CHANNELS[c as Channel]?.name ?? c

/**
 * Deactivating a kit that channels use as their default would make every
 * later order on those channels (with the default kit) fail. So the dialog
 * asks for each such channel's new default — another active kit or no kit —
 * saves those first (PATCH /settings/channels/{channel}, one by one), and only
 * then deactivates. A failed channel update stops before deactivating.
 */
export function DeactivateKitDialog({
  kit,
  channels,
  otherKits,
  mobile,
  onClose,
  onDone,
}: {
  kit: KitDetail | null
  /** Channels whose default is this kit. */
  channels: string[]
  /** Active kits a channel can switch to. */
  otherKits: KitDetail[]
  mobile: boolean
  onClose: () => void
  /** After a successful deactivation (or a partial channel update): refresh. */
  onDone: (deactivated: KitDetail | null) => Promise<void>
}) {
  const [choices, setChoices] = React.useState<Record<string, string>>({})
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const [shownFor, setShownFor] = React.useState<number | null>(null)
  if ((kit?.id ?? null) !== shownFor) {
    setShownFor(kit?.id ?? null)
    setChoices({})
    setError(null)
  }

  const missing = channels.filter((c) => choices[c] == null)

  const confirm = async () => {
    if (!kit || missing.length > 0) return
    setBusy(true)
    setError(null)
    const changed: string[] = []
    for (const channel of channels) {
      const choice = choices[channel]
      try {
        await updateChannelSettings(channel, { default_packaging_kit_id: choice === NONE ? null : Number(choice) })
        changed.push(channel)
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : String(e)
        setError(
          [K.deactChannelFailed(channelName(channel), msg), changed.length ? K.deactPartial(changed.map(channelName).join("، ")) : ""]
            .filter(Boolean)
            .join(" ")
        )
        setBusy(false)
        if (changed.length) await onDone(null)
        return
      }
    }
    try {
      const updated = await deactivateKit(kit.id)
      await onDone(updated)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
      if (changed.length) await onDone(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <ConfirmShell
      open={kit != null}
      onOpenChange={(o) => !o && onClose()}
      mobile={mobile}
      busy={busy}
      icon={Ban}
      title={kit ? K.deactTitle(kit.name) : ""}
      subtitle={K.deactSubtitle}
      confirmLabel={K.deactConfirm}
      confirmIcon={Ban}
      confirmDisabled={missing.length > 0}
      onConfirm={confirm}
    >
      <div className="flex flex-col gap-3">
        {error && <Alert tone="err" title={K.saveFailed}>{error}</Alert>}
        {channels.length === 0 ? (
          <p className="text-[13px] text-text-2">{K.deactNoChannels}</p>
        ) : (
          <>
            <div className="text-[13px] leading-[22px]">
              <b>{K.deactChannelsLead}</b> {K.deactChannelsBody}
            </div>
            {channels.map((channel) => {
              const value = choices[channel]
              const label =
                value == null ? K.pickReplacement : value === NONE ? K.noPackaging : (otherKits.find((k) => String(k.id) === value)?.name ?? "")
              return (
                <div key={channel} className="flex items-center justify-between gap-3">
                  <ChannelBadge channel={channel} />
                  <DropdownMenu dir="rtl">
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        aria-label={`${K.pickReplacement} — ${channelName(channel)}`}
                        className={cn(
                          "flex h-10 w-[240px] cursor-pointer items-center justify-between gap-2 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                          value == null && "text-text-3"
                        )}
                      >
                        {label}
                        <ChevronDown className="size-3.5 text-text-3" aria-hidden />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-[240px]">
                      <DropdownMenuRadioGroup value={value ?? ""} onValueChange={(v) => setChoices((c) => ({ ...c, [channel]: v }))}>
                        {otherKits.map((k) => (
                          <DropdownMenuRadioItem key={k.id} value={String(k.id)}>
                            {k.name}
                          </DropdownMenuRadioItem>
                        ))}
                        <DropdownMenuRadioItem value={NONE}>{K.noPackaging}</DropdownMenuRadioItem>
                      </DropdownMenuRadioGroup>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              )
            })}
            {missing.length > 0 && <p className="text-xs text-text-3">{K.replacementRequired}</p>}
          </>
        )}
      </div>
    </ConfirmShell>
  )
}
