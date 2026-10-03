"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Box, Pencil, Plus, TriangleAlert } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { ErrorBlock, LoadingBlock, StateShell } from "@/components/common/screen-states"
import { ChannelBadge } from "@/components/common/status"
import { Toast } from "@/components/common/toast"
import { DrawerShell, Switch } from "@/components/products/drawer-shell"
import { unitLabel } from "@/components/products/figures"
import { CHANNEL_IDS } from "@/components/record-sale/copy"
import { Btn, StockPill, cardClass } from "@/components/record-sale/primitives"
import type { KitDetail, Material, Settings } from "@/lib/api"
import { formatNumber, formatQuantity } from "@/lib/persian-numbers"
import { formatMoney } from "@/lib/money"
import { cn } from "@/lib/utils"
import { K } from "./copy"
import { DeactivateKitDialog } from "./deactivate-kit-dialog"
import { LOW_KITS, kitAvailability, type Availability } from "./figures"
import { KitEditor } from "./kit-editor"
import { NewKitDialog } from "./new-kit-dialog"
import { usePackagingData } from "./use-packaging-data"

/** Channels whose default kit is `kitId` (null = no kit), in the app's channel order. */
function channelsWithDefault(settings: Settings, kitId: number | null): string[] {
  return CHANNEL_IDS.filter((c) => (settings.channels[c]?.default_packaging_kit_id ?? null) === kitId)
}

function availPill(a: Availability) {
  if (a.kind === "unlimited") return { text: K.unlimited, tone: "neutral" as const }
  return a.count < LOW_KITS ? { text: K.availLow(a.count), tone: "out" as const } : { text: K.availOk(a.count), tone: "neutral" as const }
}

/**
 * بسته‌بندی (design 08): kits as a list + editor. Kit cost is always the API's
 * kit_cost; channel defaults are shown read-only (they're edited on Settings),
 * except that deactivating a default kit asks for the channels' replacements.
 */
export function PackagingPage() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()
  const { state, reload, upsertKit, refreshSettings } = usePackagingData()

  const showInactive = params.get("inactive") === "1"
  const kitParam = Number(params.get("kit"))
  const setParams = React.useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(window.location.search)
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      const qs = next.toString()
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
    },
    [router, pathname]
  )

  const [newOpen, setNewOpen] = React.useState(false)
  const [editOpen, setEditOpen] = React.useState(false)
  const [deactivating, setDeactivating] = React.useState<KitDetail | null>(null)
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const materialById = React.useMemo(
    () => new Map((state.status === "ready" ? state.materials : []).map((m) => [m.id, m])),
    [state]
  )

  let body: React.ReactNode
  let selected: KitDetail | null = null
  if (state.status === "loading") body = <LoadingBlock mobile={mobile} label={K.loadingAria} />
  else if (state.status === "error")
    body = (
      <ErrorBlock
        title={mobile ? K.errorTitleMobile : K.errorTitle}
        body={K.errorBody}
        retry={K.retry}
        onRetry={reload}
        mobile={mobile}
      />
    )
  else if (state.kits.length === 0)
    body = (
      <StateShell
        icon={Box}
        mobile={mobile}
        title={K.emptyTitle}
        body={mobile ? K.emptyBodyMobile : K.emptyBody}
        action={
          <Btn variant="primary" size={mobile ? "lg" : "md"} className="mt-1.5" onClick={() => setNewOpen(true)}>
            <Plus className="size-4" />
            {mobile ? K.emptyCtaMobile : K.emptyCta}
          </Btn>
        }
      />
    )
  else {
    const visible = state.kits.filter((k) => showInactive || k.is_active === 1)
    selected = visible.find((k) => k.id === kitParam) ?? visible[0] ?? null
    const noKitChannels = channelsWithDefault(state.settings, null)

    const cards = visible.map((kit) => (
      <KitCard
        key={kit.id}
        kit={kit}
        channels={channelsWithDefault(state.settings, kit.id)}
        avail={kitAvailability(kit, materialById)}
        materials={materialById}
        selected={kit.id === selected?.id}
        mobile={mobile}
        onSelect={() => setParams({ kit: String(kit.id) })}
        onEdit={() => {
          setParams({ kit: String(kit.id) })
          setEditOpen(true)
        }}
      />
    ))
    const noKitCard = (
      <div className={cn(cardClass, "flex flex-col gap-2 px-4 py-3.5 text-[13px]")}>
        <span className="flex items-center justify-between gap-2">
          <b>{K.noPackaging}</b>
          <b className="tabular-nums">{formatMoney(0)}</b>
        </span>
        <span className="text-xs text-text-3">{noKitChannels.length ? K.noPackagingMeta : K.noPackagingNone}</span>
        {noKitChannels.length > 0 && (
          <span className="flex flex-wrap gap-1.5">
            {noKitChannels.map((c) => (
              <ChannelBadge key={c} channel={c} />
            ))}
          </span>
        )}
      </div>
    )
    const inactiveSwitch = (
      <label className="flex cursor-pointer items-center gap-2 text-[13px]">
        <Switch checked={showInactive} onChange={(v) => setParams({ inactive: v ? "1" : null })} labelledBy="kits-inactive" />
        <span id="kits-inactive">{K.showInactive}</span>
      </label>
    )

    body = mobile ? (
      <div className="flex flex-col gap-3">
        {inactiveSwitch}
        {cards}
        {noKitCard}
      </div>
    ) : (
      <div className="flex items-start gap-6">
        <nav aria-label={K.listLabel} className="flex w-[340px] shrink-0 flex-col gap-2.5">
          {cards}
          {noKitCard}
        </nav>
        {selected ? (
          <KitEditor
            kit={selected}
            materials={state.materials}
            defaultChannels={channelsWithDefault(state.settings, selected.id)}
            mobile={false}
            onSaved={upsertKit}
            onReactivated={(kit) => setToast(K.toastReactivated(kit.name))}
            onDeactivate={() => setDeactivating(selected)}
          />
        ) : (
          <p className={cn(cardClass, "grow px-5 py-10 text-center text-[13px] text-text-3")}>{K.pickKit}</p>
        )}
      </div>
    )
    if (!mobile) {
      body = (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-[13px] text-text-3">{K.hint}</span>
            <span className="flex items-center gap-4">
              {inactiveSwitch}
              <Btn variant="primary" onClick={() => setNewOpen(true)}>
                <Plus className="size-4" />
                {K.newKit}
              </Btn>
            </span>
          </div>
          {body}
        </div>
      )
    }
  }

  const ready = state.status === "ready"
  const otherKits = ready ? state.kits.filter((k) => k.is_active === 1 && k.id !== deactivating?.id) : []

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3 pb-24" : "gap-5")}>
      {body}

      {mobile && ready && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
          <Btn variant="primary" size="lg" className="w-full" onClick={() => setNewOpen(true)}>
            <Plus className="size-[18px]" />
            {K.newKit}
          </Btn>
        </div>
      )}

      {mobile && ready && selected && (
        <DrawerShell
          open={editOpen}
          onOpenChange={setEditOpen}
          mobile
          title={selected.name}
          footer={<Btn onClick={() => setEditOpen(false)}>{K.close}</Btn>}
        >
          <KitEditor
            kit={selected}
            materials={state.materials}
            defaultChannels={channelsWithDefault(state.settings, selected.id)}
            mobile
            onSaved={upsertKit}
            onReactivated={(kit) => setToast(K.toastReactivated(kit.name))}
            onDeactivate={() => {
              setEditOpen(false)
              setDeactivating(selected)
            }}
          />
        </DrawerShell>
      )}

      <NewKitDialog
        open={newOpen}
        mobile={mobile}
        onClose={() => setNewOpen(false)}
        onCreated={(kit) => {
          upsertKit(kit)
          setNewOpen(false)
          setParams({ kit: String(kit.id) })
          if (mobile) setEditOpen(true)
          setToast(K.toastCreated(kit.name))
        }}
      />
      <DeactivateKitDialog
        kit={deactivating}
        channels={ready && deactivating ? channelsWithDefault(state.settings, deactivating.id) : []}
        otherKits={otherKits}
        mobile={mobile}
        onClose={() => setDeactivating(null)}
        onDone={async (kit) => {
          await refreshSettings().catch(() => {})
          if (kit) {
            upsertKit(kit)
            setDeactivating(null)
            setToast(K.toastDeactivated(kit.name))
          }
        }}
      />
      {toast && <Toast title={toast} onClose={closeToast} closeLabel={K.close} />}
    </div>
  )
}

function KitCard({
  kit,
  channels,
  avail,
  materials,
  selected,
  mobile,
  onSelect,
  onEdit,
}: {
  kit: KitDetail
  channels: string[]
  avail: Availability
  materials: Map<number, Material>
  selected: boolean
  mobile: boolean
  onSelect: () => void
  onEdit: () => void
}) {
  const inactive = kit.is_active !== 1
  const chips = (
    <span className="flex flex-wrap items-center gap-1.5">
      {channels.map((c) => (
        <ChannelBadge key={c} channel={c} />
      ))}
      {channels.length === 0 && <span className="text-xs text-text-3">{K.noDefault}</span>}
    </span>
  )
  const header = (
    <span className="flex w-full items-center justify-between gap-2">
      <span className="flex items-center gap-2">
        <b>{kit.name}</b>
        {inactive && <span className="rounded-md bg-surface-2 px-1.5 text-[11px] text-text-3">{K.inactive}</span>}
      </span>
      <b className="tabular-nums">{formatMoney(kit.kit_cost)}</b>
    </span>
  )

  // Mobile: the selected kit is expanded with its lines and availability.
  if (mobile && selected) {
    const low = avail.kind === "count" && avail.count < LOW_KITS
    return (
      <div className={cn(cardClass, "flex flex-col gap-2 border-primary p-3.5 shadow-[0_0_0_1px_var(--primary)]", inactive && "opacity-70")}>
        {header}
        {chips}
        <div className="my-1 h-px bg-border" />
        {kit.items.map((item) => {
          const unit = unitLabel(materials.get(item.material_id)?.unit ?? "")
          return (
            <span key={item.material_id} className="flex justify-between gap-2 text-[13px]">
              <span>
                {item.material_name} × {formatQuantity(item.quantity)}
                {unit !== "عدد" ? ` ${unit}` : ""}
              </span>
              <span className="tabular-nums">{formatNumber(Math.round(item.quantity * item.material_unit_cost))}</span>
            </span>
          )
        })}
        {kit.items.length === 0 && <span className="text-xs text-text-3">{K.emptyKit}</span>}
        {low && avail.kind === "count" && (
          <div role="status" className="flex items-start gap-2 rounded-lg bg-warn-soft px-2.5 py-2 text-xs">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden />
            {`${K.availLow(avail.count)} — ${K.limiting(avail.limiting.name, avail.limiting.stock, unitLabel(avail.limiting.unit))}`}
          </div>
        )}
        <Btn className="h-11" onClick={onEdit}>
          <Pencil className="size-4" />
          {K.editKit}
        </Btn>
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={cn(
        cardClass,
        "flex flex-col gap-2 text-start outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
        mobile ? "px-3.5 py-3" : "px-4 py-3.5",
        selected && "border-primary shadow-[0_0_0_1px_var(--primary)]",
        inactive && "opacity-70"
      )}
    >
      {header}
      <span className="text-xs text-text-3">{K.itemCount(kit.items.length)}</span>
      {chips}
      {!mobile && (
        <span>
          <StockPill {...availPill(avail)} />
        </span>
      )}
    </button>
  )
}
