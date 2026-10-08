"use client"

import * as React from "react"
import { Info, Loader2 } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { ErrorBlock, LoadingBlock } from "@/components/common/screen-states"
import { Toast } from "@/components/common/toast"
import { Alert, Btn, cardClass } from "@/components/record-sale/primitives"
import type { Channel } from "@/components/record-sale/copy"
import { ApiError, updateDisplayCurrency, type GlobalSettingKey } from "@/lib/api"
import { currencyLabel, getCurrency, setCurrency, type Currency } from "@/lib/money"
import { useCurrency } from "@/lib/use-currency"
import { cn } from "@/lib/utils"
import { PM } from "@/components/payment-methods/copy"
import { ChannelsCard } from "./channels-card"
import { S, joinList } from "./copy"
import { changes, fromSettings, saveDraft, validate, type ChannelDraft, type Draft, type MoneyKey } from "./draft"
import type { MoneyInputError } from "@/lib/money"
import { GeneralCard } from "./general-card"
import { PaymentMethodsCard } from "./payment-methods-card"
import { PostageCard, heroFigure } from "./postage-card"
import { useSettingsData } from "./use-settings-data"

const SECTIONS = [
  { hash: "#ship", label: S.navShip },
  { hash: "#pay", label: S.navPay },
  { hash: "#post", label: S.navPost },
  { hash: "#general", label: S.navGeneral },
] as const

function subscribeHash(onChange: () => void) {
  window.addEventListener("hashchange", onChange)
  return () => window.removeEventListener("hashchange", onChange)
}
const useHash = () => React.useSyncExternalStore(subscribeHash, () => window.location.hash, () => "")

/**
 * تنظیمات (design 15): the one place channel configuration and the global
 * settings are edited (Packaging and Postage show them read-only and link
 * here). Edits go into a draft; «ذخیره تغییرات» saves every change in turn
 * (see draft.ts). Store/invoice fields and «کاربران» aren't built: the
 * backend has no settings for them.
 */
export function SettingsPage() {
  const mobile = useIsMobile()
  const hash = useHash()
  const { state, reload, setSettings, refreshKits, refreshEstimate, refreshMethods, putMethod } = useSettingsData()
  const [draft, setDraft] = React.useState<Draft | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [saveError, setSaveError] = React.useState<string | null>(null)
  /** A global setting the server refused, until it's edited again. */
  const [serverError, setServerError] = React.useState<{ key: GlobalSettingKey; message: string } | null>(null)
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])
  const currency = useCurrency()
  const [currencyBusy, setCurrencyBusy] = React.useState(false)
  const [currencyError, setCurrencyError] = React.useState<string | null>(null)

  // Seed the draft from the first load (and again after a reload).
  if (state.status === "ready" && draft === null) setDraft(fromSettings(state.settings))
  if (state.status !== "ready" && draft !== null) setDraft(null)

  const ready = state.status === "ready" && draft !== null
  const dirty = ready ? changes(state.settings, draft) : []

  React.useEffect(() => {
    if (dirty.length === 0) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener("beforeunload", warn)
    return () => window.removeEventListener("beforeunload", warn)
  }, [dirty.length])

  // Arriving with #post (Postage's link) or #ship (Packaging's): scroll once the cards exist.
  React.useEffect(() => {
    if (ready && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" })
    // Only on first render of the loaded screen, not on every hash click (the anchor already scrolls).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready])

  if (state.status === "loading" || (state.status === "ready" && !draft))
    return <LoadingBlock mobile={mobile} label={S.loadingAria} />
  if (state.status === "error" || !draft)
    return <ErrorBlock title={S.errorTitle} body={S.errorBody} retry={S.retry} onRetry={reload} mobile={mobile} />

  const { settings, kits, batches, estimate, methods } = state
  const clientErrors = validate(draft)
  const errorFor = (key: GlobalSettingKey) => clientErrors[key] ?? (serverError?.key === key ? serverError.message : null)
  const invalid = Object.keys(clientErrors).length > 0
  const hero = heroFigure(batches, estimate, settings, draft)

  const setGlobal = (key: GlobalSettingKey) => (value: number | null) => {
    setDraft((d) => d && { ...d, [key]: value })
    if (serverError?.key === key) setServerError(null)
  }
  /** A money key also keeps MoneyInput's reason while it holds no exact amount. */
  const setMoney = (key: MoneyKey) => (value: number | null, error: MoneyInputError | null) => {
    setDraft((d) => d && { ...d, [key]: value, moneyErrors: { ...d.moneyErrors, [key]: error ?? undefined } })
    if (serverError?.key === key) setServerError(null)
  }
  const setChannel = (channel: Channel, patch: Partial<ChannelDraft>) =>
    setDraft((d) => d && { ...d, channels: { ...d.channels, [channel]: { ...d.channels[channel], ...patch } } })

  /**
   * «واحد پول» saves on its own, immediately — it isn't part of the draft:
   * it changes no data, only how every amount (draft amounts included, which
   * are kept in integer Rial) is shown and typed. Optimistic; reverted if the PUT fails.
   */
  const changeCurrency = async (next: Currency) => {
    if (currencyBusy || next === currency) return
    const previous = getCurrency()
    setCurrencyBusy(true)
    setCurrencyError(null)
    setCurrency(next)
    try {
      const saved = await updateDisplayCurrency(next)
      setCurrency(saved.display_currency)
      setSettings({ ...settings, display_currency: saved.display_currency })
      setToast(S.currencySaved(currencyLabel(saved.display_currency)))
    } catch (e) {
      setCurrency(previous)
      setCurrencyError(S.currencyFailed(e instanceof Error ? e.message : String(e)))
    }
    setCurrencyBusy(false)
  }

  const revert = () => {
    setDraft(fromSettings(settings))
    setSaveError(null)
    setServerError(null)
  }

  const save = async () => {
    if (busy || invalid || dirty.length === 0) return
    setBusy(true)
    setSaveError(null)
    setServerError(null)
    const result = await saveDraft(settings, draft)
    setSettings(result.settings)
    if (result.savedGlobal) await refreshEstimate().catch(() => {})
    const f = result.failure
    if (f) {
      // A refused default payment method gets the Persian reason; everything else the server's message.
      const methodRefused =
        f.methodChanged && f.error instanceof ApiError
          ? f.error.type === "NotFoundError"
            ? PM.methodGone
            : f.error.field === "default_payment_method_id"
              ? PM.inactiveDefault
              : null
          : null
      const parts = [
        S.saveStep(f.label, methodRefused ?? f.error.message),
        result.saved.length ? S.savePartial(joinList(result.saved, 99)) : "",
      ]
      if (f.kitChanged && f.error instanceof ApiError && f.error.type === "NotFoundError") {
        // The chosen kit was deactivated meanwhile: show the picker's real options.
        await refreshKits().catch(() => {})
        parts.push(S.kitsReloaded)
      }
      if (
        f.methodChanged &&
        f.error instanceof ApiError &&
        (f.error.type === "NotFoundError" || f.error.field === "default_payment_method_id")
      ) {
        // The chosen method was deactivated (or removed) meanwhile: show the picker's real options.
        await refreshMethods().catch(() => {})
        parts.push(S.methodsReloaded)
      }
      setSaveError(parts.filter(Boolean).join(" "))
      if (f.key && f.error instanceof ApiError && f.error.field === "value") setServerError({ key: f.key, message: f.error.message })
    } else {
      setToast(S.toastSaved)
    }
    setBusy(false)
  }

  const saveButton = (size: "sm" | "lg", className?: string) => (
    <Btn
      variant="primary"
      size={size}
      className={className}
      disabled={busy || invalid || dirty.length === 0}
      aria-busy={busy || undefined}
      onClick={save}
    >
      {busy && <Loader2 className="size-4 animate-spin" />}
      {S.save}
    </Btn>
  )

  const errorAlert = saveError && (
    <Alert tone="err" title={S.saveFailed}>
      {saveError}
    </Alert>
  )
  const invalidNote = invalid && dirty.length > 0 && <span className="text-xs text-warn">{S.invalid}</span>

  const cards = (
    <>
      <ChannelsCard
        draft={draft}
        kits={kits}
        methods={methods}
        estimate={hero.estimate}
        shippingError={errorFor("default_shipping_charge")}
        onShipping={setMoney("default_shipping_charge")}
        onChannel={setChannel}
        mobile={mobile}
      />
      <PaymentMethodsCard
        methods={methods}
        settings={settings}
        mobile={mobile}
        onChanged={putMethod}
        onRefresh={refreshMethods}
        onToast={setToast}
      />
      <PostageCard
        draft={draft}
        hero={hero}
        windowError={errorFor("postage_estimate_window")}
        defaultError={errorFor("default_postage_estimate")}
        onWindow={setGlobal("postage_estimate_window")}
        onDefault={setMoney("default_postage_estimate")}
        mobile={mobile}
      />
      <GeneralCard
        timezone={settings.timezone}
        currency={currency}
        onCurrency={changeCurrency}
        currencyBusy={currencyBusy}
        currencyError={currencyError}
        mobile={mobile}
      />
    </>
  )

  const toastNode = toast && <Toast title={toast} onClose={closeToast} closeLabel={S.close} />

  if (mobile) {
    return (
      <div className="flex flex-col gap-3 pb-32">
        {errorAlert}
        {cards}
        <div className="fixed inset-x-0 bottom-0 z-30 flex flex-col gap-2 border-t border-border bg-card px-4 pt-3 pb-5">
          {dirty.length > 0 && (
            <div className="flex items-center justify-between gap-3 text-[13px]" role="status">
              <span className="font-semibold">{S.unsavedMobile(dirty.length)}</span>
              <Btn variant="ghost" size="sm" disabled={busy} onClick={revert}>
                {S.revert}
              </Btn>
            </div>
          )}
          {invalidNote}
          {saveButton("lg", "w-full")}
        </div>
        {toastNode}
      </div>
    )
  }

  const active = SECTIONS.some((s) => s.hash === hash) ? hash : "#ship"

  return (
    <div className="flex items-start gap-6">
      <nav aria-label={S.navAria} className={cn(cardClass, "sticky top-6 flex w-[220px] shrink-0 flex-col gap-0.5 p-2")}>
        {SECTIONS.map((s) => (
          <a
            key={s.hash}
            href={s.hash}
            aria-current={s.hash === active ? "true" : undefined}
            className={cn(
              "flex h-10 items-center rounded-lg px-3 text-sm outline-none hover:bg-surface-2 focus-visible:ring-3 focus-visible:ring-ring/30",
              s.hash === active && "bg-red-soft font-bold hover:bg-red-soft"
            )}
          >
            {s.label}
          </a>
        ))}
      </nav>
      <div className="flex min-w-0 grow flex-col gap-5">
        {errorAlert}
        {cards}
        {dirty.length > 0 && (
          <div
            role="status"
            className="sticky bottom-5 z-20 flex items-center gap-3 rounded-xl bg-foreground px-4 py-3 text-background shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)]"
          >
            <Info className="size-[18px] shrink-0" aria-hidden />
            <span className="min-w-0 grow text-[13px]">
              {S.unsaved(dirty.length, joinList(dirty))}
              {invalid && <span className="ms-2 font-bold">{S.invalid}</span>}
            </span>
            <Btn
              size="sm"
              className="border-white/30 bg-transparent text-background hover:bg-white/10"
              disabled={busy}
              onClick={revert}
            >
              {S.revert}
            </Btn>
            {saveButton("sm")}
          </div>
        )}
      </div>
      {toastNode}
    </div>
  )
}
