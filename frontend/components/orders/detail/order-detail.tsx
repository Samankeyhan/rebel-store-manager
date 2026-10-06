"use client"

import * as React from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { CircleCheck, Info, RotateCw, TriangleAlert, X } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { Skeleton } from "@/components/ui/skeleton"
import { usePageCrumb } from "@/components/top-bar-crumb"
import { statusName } from "@/components/common/status"
import { T as SaleT } from "@/components/record-sale/copy"
import { Alert, Btn, btnClass, cardClass } from "@/components/record-sale/primitives"
import {
  ApiError,
  changeOrderStatus,
  getCatalog,
  getOrder,
  returnOrder,
  setOrderPaidDate,
  type Catalog,
  type OrderDetail as Detail,
} from "@/lib/api"
import { formatQuantity } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { D, L } from "../copy"
import { LIST_QUERY_KEY } from "../order-figures"
import { classifyPaymentError } from "@/lib/payment-methods"
import { DEFAULT_TZ, storeToday } from "@/lib/store-day"
import { paymentErrorText } from "@/components/payment-methods/copy"
import { CancelDialog, ChangePaidDateDialog, CommitConfirm, PaidConfirm, RefundDialog } from "./dialogs"
import { HeaderCard, InternalCard, ItemsCard, SensitiveActions, type Actions } from "./sections"
import { useCurrency } from "@/lib/use-currency"


type Load =
  | { status: "loading" }
  | { status: "missing" }
  | { status: "error"; code: string }
  | { status: "ready"; detail: Detail }

type Banner = { tone: "info" | "err"; title?: string; text: string; code?: string }
type Dialog =
  | { kind: "cancel" }
  | { kind: "refund" }
  | { kind: "commit"; target: string }
  /** PENDING → PAID / COMPLETED: asks for the payment day. */
  | { kind: "paid"; target: string }
  | { kind: "paidDate" }
  | null

const PAID = new Set(["PAID", "COMPLETED"])
const UNPAID = new Set(["DRAFT", "PENDING"])

function listHref(): string {
  try {
    const q = window.sessionStorage.getItem(LIST_QUERY_KEY)
    return q ? `/orders/?${q}` : "/orders/"
  } catch {
    return "/orders/"
  }
}

export function OrderDetail() {
  // Re-render the whole screen when the display currency switches (lib/money.ts).
  useCurrency()
  const params = useSearchParams()
  const raw = params.get("id") ?? ""
  const id = /^\d+$/.test(raw) ? Number(raw) : null
  const mobile = useIsMobile()

  const [load, setLoad] = React.useState<Load>({ status: "loading" })
  const [catalog, setCatalog] = React.useState<Catalog | null>(null)
  const [attempt, setAttempt] = React.useState(0)
  const [busy, setBusy] = React.useState(false)
  const [dialog, setDialog] = React.useState<Dialog>(null)
  const [banner, setBanner] = React.useState<Banner | null>(null)
  const [toast, setToast] = React.useState<string | null>(null)
  /** The payment day picked in the open dialog, and the server's refusal of it (Persian). */
  const [pickedDay, setPickedDay] = React.useState<string>("")
  const [dayError, setDayError] = React.useState<string | null>(null)
  // Rendered client-side only (useSearchParams under Suspense), so window exists.
  const [backHref] = React.useState(() => (typeof window === "undefined" ? "/orders/" : listHref()))

  React.useEffect(() => {
    if (id == null) return
    let cancelled = false
    getOrder(id).then(
      (detail) => !cancelled && setLoad({ status: "ready", detail }),
      (error: unknown) => {
        if (cancelled) return
        if (error instanceof ApiError && error.status === 404) setLoad({ status: "missing" })
        else
          setLoad({
            status: "error",
            code: error instanceof ApiError && error.status > 0 ? `ORDERS_${error.status}` : "NET_TIMEOUT",
          })
      }
    )
    // Names for categories and the kit; the page still works without it.
    getCatalog().then(
      (c) => !cancelled && setCatalog(c),
      () => {}
    )
    return () => {
      cancelled = true
    }
  }, [id, attempt])

  const detail = load.status === "ready" ? load.detail : null
  usePageCrumb(
    detail?.order.invoice_number
      ? { parentHref: backHref, parentLabel: D.crumbParent, title: detail.order.invoice_number }
      : null
  )

  const timeZone = catalog?.settings.timezone || DEFAULT_TZ

  const refetch = React.useCallback(async () => {
    if (id == null) return
    try {
      setLoad({ status: "ready", detail: await getOrder(id) })
    } catch {
      setAttempt((a) => a + 1)
    }
  }, [id])

  /** Maps an action failure to what the screen shows; the API decides. */
  const handleError = async (error: unknown, d: Detail) => {
    // A refused payment day stays in its dialog, in Persian, so it can be corrected.
    const payment = error instanceof ApiError ? classifyPaymentError(error) : null
    if (payment && dialog && (dialog.kind === "commit" || dialog.kind === "paid" || dialog.kind === "paidDate")) {
      setDayError(paymentErrorText(payment))
      return
    }
    setDialog(null)
    if (payment) {
      setBanner({ tone: "err", title: D.actionFailed, text: paymentErrorText(payment) })
      if (payment.kind === "settled" || payment.kind === "unpaid") await refetch()
      return
    }
    if (!(error instanceof ApiError)) {
      setBanner({ tone: "err", title: D.actionFailed, text: String(error), code: "UNKNOWN" })
      return
    }
    if (error.status === 409 && error.type === "ConflictError") {
      // Someone (or another tab) moved the order on: show where it is now.
      await refetch()
      setBanner({ tone: "info", text: D.conflict })
      return
    }
    if (error.status === 409 && error.type === "InsufficientStockError") {
      const name = String(error.details.item_name ?? "")
      const available = Number(error.details.available ?? 0)
      const isProduct = d.items.some((i) => i.product_name === name)
      const unit = isProduct ? "عدد" : catalog?.materials.find((m) => m.name === name)?.unit ?? ""
      setBanner({
        tone: "err",
        text:
          available <= 0
            ? SaleT.v2BlockingZero(name)
            : SaleT.v2Blocking(`${formatQuantity(available)} ${unit}`.trim(), name),
      })
      return
    }
    if (error.status === 422 && (error.field === "unit_cost" || error.field === "made_to_order")) {
      const item = d.items.find((i) => error.message.includes(i.product_name))
      if (item) {
        setBanner({
          tone: "err",
          text: error.field === "unit_cost" ? SaleT.v3BannerTitle(item.product_name) : SaleT.noRecipe(item.product_name),
        })
        return
      }
    }
    if (error.status === 404) {
      setLoad({ status: "missing" })
      return
    }
    setBanner({
      tone: "err",
      title: D.actionFailed,
      text: error.message,
      code: error.status === 0 ? "NET_TIMEOUT" : `ORDERS_${error.status}`,
    })
  }

  const run = async (d: Detail, request: () => Promise<Detail>, toastText: (r: Detail) => string) => {
    setBusy(true)
    setBanner(null)
    try {
      const result = await request()
      setLoad({ status: "ready", detail: result })
      setDialog(null)
      setToast(toastText(result))
    } catch (error) {
      await handleError(error, d)
    } finally {
      setBusy(false)
    }
  }

  if (id == null || load.status === "missing") {
    return <NotFound invoice={null} onRetry={() => setAttempt((a) => a + 1)} backHref={backHref} mobile={mobile} />
  }
  if (load.status === "loading") return <DetailLoading mobile={mobile} />
  if (load.status === "error") {
    return <NotFound invoice={null} onRetry={() => setAttempt((a) => a + 1)} backHref={backHref} mobile={mobile} code={load.code} />
  }

  const d = load.detail
  /** The store's calendar day, read when it's needed (a session can cross midnight). */
  const today = () => storeToday(new Date(), timeZone)
  const becomesPaid = (target: string) => UNPAID.has(d.order.status) && PAID.has(target)
  /**
   * paidDate only when the order becomes paid. The dialog's default is the
   * store's today — what the server stores when paid_date is omitted — so the
   * day is sent only when it differs from today at submit time: what is
   * stored is always what the dialog showed.
   */
  const forward = (target: string, paidDay?: string) => {
    const paidDate = paidDay && becomesPaid(target) && paidDay !== today() ? paidDay : null
    return run(d, () => changeOrderStatus(d.order.id, target, paidDate), (r) => D.toastStatus(statusName(r.order.status)))
  }
  const openWithDay = (next: NonNullable<Dialog>, day: string) => {
    setPickedDay(day)
    setDayError(null)
    setDialog(next)
  }

  const actions: Actions = {
    busy,
    onForward: (target) => {
      // Leaving DRAFT deducts stock for the first time: confirm that one (with the payment day if it becomes paid).
      if (d.order.status === "DRAFT") return openWithDay({ kind: "commit", target }, today())
      if (becomesPaid(target)) return openWithDay({ kind: "paid", target }, today())
      void forward(target)
    },
    onCancel: () => setDialog({ kind: "cancel" }),
    onRefund: () => setDialog({ kind: "refund" }),
    onChangePaidDate: () => openWithDay({ kind: "paidDate" }, d.order.paid_date ?? today()),
  }
  const pick = {
    value: pickedDay,
    today: today(),
    onChange: (iso: string) => {
      setPickedDay(iso)
      setDayError(null)
    },
    error: dayError,
  }
  const dialogProps = {
    detail: d,
    catalog,
    timeZone,
    mobile,
    busy,
    onOpenChange: (open: boolean) => !open && setDialog(null),
  }

  const bannerNode = banner && (
    <Alert
      tone={banner.tone === "info" ? "warn" : "err"}
      icon={banner.tone === "info" ? <Info className="size-5" /> : "alert"}
      title={banner.title}
      action={
        <Btn variant="ghost" size="sm" className="w-8 px-0" aria-label={L.close} onClick={() => setBanner(null)}>
          <X className="size-4" />
        </Btn>
      }
    >
      <div dir="auto">{banner.text}</div>
      {banner.code && (
        <div className="mt-1 text-xs text-text-3">
          {L.errorCode}{" "}
          <span dir="ltr" className="inline-block font-mono">
            {banner.code}
          </span>
        </div>
      )}
    </Alert>
  )

  const dialogs = (
    <>
      <CancelDialog
        {...dialogProps}
        open={dialog?.kind === "cancel"}
        onConfirm={(reason) =>
          run(d, () => returnOrder(d.order.id, "CANCELLED", reason), () => D.toastCancelled)
        }
      />
      <RefundDialog
        {...dialogProps}
        open={dialog?.kind === "refund"}
        onConfirm={(reason) =>
          run(d, () => returnOrder(d.order.id, "REFUNDED", reason), () => D.toastRefunded)
        }
      />
      <CommitConfirm
        {...dialogProps}
        open={dialog?.kind === "commit"}
        target={dialog?.kind === "commit" ? dialog.target : "COMPLETED"}
        paid={dialog?.kind === "commit" && PAID.has(dialog.target) ? pick : null}
        onConfirm={() => dialog?.kind === "commit" && forward(dialog.target, pickedDay)}
      />
      <PaidConfirm
        {...dialogProps}
        open={dialog?.kind === "paid"}
        target={dialog?.kind === "paid" ? dialog.target : "PAID"}
        paid={pick}
        onConfirm={() => dialog?.kind === "paid" && forward(dialog.target, pickedDay)}
      />
      <ChangePaidDateDialog
        {...dialogProps}
        open={dialog?.kind === "paidDate"}
        current={d.order.paid_date ?? ""}
        paid={pick}
        onConfirm={() => run(d, () => setOrderPaidDate(d.order.id, pickedDay), () => D.toastPaidDate)}
      />
      {toast && <Toast title={toast} onClose={() => setToast(null)} />}
    </>
  )

  if (mobile) {
    return (
      <div className="flex flex-col gap-3.5 pb-24">
        {bannerNode}
        <HeaderCard detail={d} catalog={catalog} timeZone={timeZone} actions={actions} mobile />
        <ItemsCard detail={d} catalog={catalog} mobile />
        <InternalCard detail={d} catalog={catalog} mobile actions={actions} />
        <SensitiveActions detail={d} actions={actions} />
        {dialogs}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {bannerNode}
      <HeaderCard detail={d} catalog={catalog} timeZone={timeZone} actions={actions} mobile={false} />
      <div className="flex flex-col items-stretch gap-6 xl:flex-row xl:items-start">
        <div className="flex min-w-0 grow flex-col gap-5">
          <ItemsCard detail={d} catalog={catalog} mobile={false} />
        </div>
        <div className="flex w-full shrink-0 flex-col gap-5 xl:w-[388px]">
          <InternalCard detail={d} catalog={catalog} mobile={false} actions={actions} />
        </div>
      </div>
      {dialogs}
    </div>
  )
}

function Toast({ title, onClose }: { title: string; onClose: () => void }) {
  React.useEffect(() => {
    const t = window.setTimeout(onClose, 4000)
    return () => window.clearTimeout(t)
  }, [onClose])
  return (
    // Bottom-left: a screen-edge choice (design-system §5 Toast).
    <div
      role="status"
      className="fixed bottom-6 left-6 z-50 flex w-[360px] max-w-[calc(100vw-32px)] items-start gap-3 rounded-xl border border-border bg-card px-4 py-3.5 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)]"
    >
      <CircleCheck className="mt-0.5 size-5 shrink-0 text-profit" aria-hidden />
      <div className="min-w-0 grow">
        <div className="text-[13.5px] font-bold">{title}</div>
        <div className="text-[12.5px] text-text-3">{D.toastBody}</div>
      </div>
      <Btn variant="ghost" size="sm" className="w-8 px-0" aria-label={L.close} onClick={onClose}>
        <X className="size-4" />
      </Btn>
    </div>
  )
}

const sk = "rounded-md bg-surface-2"

function DetailLoading({ mobile }: { mobile: boolean }) {
  if (mobile) {
    return (
      <div aria-busy="true" className="flex flex-col gap-3.5">
        <Skeleton className={cn(sk, "h-[180px] rounded-xl")} />
        <Skeleton className={cn(sk, "h-[220px] rounded-xl")} />
        <Skeleton className={cn(sk, "h-[160px] rounded-xl")} />
      </div>
    )
  }
  return (
    <div aria-busy="true" className="flex flex-col gap-5">
      <div className={cn(cardClass, "flex flex-col gap-3 p-5")}>
        <Skeleton className={cn(sk, "h-6 w-80 max-w-full")} />
        <Skeleton className={cn(sk, "h-3.5 w-[420px] max-w-full")} />
        <Skeleton className={cn(sk, "mt-2 h-10 w-[520px] max-w-full")} />
      </div>
      <div className="flex flex-col gap-6 xl:flex-row">
        <div className={cn(cardClass, "flex grow flex-col gap-3 p-5")}>
          <Skeleton className={cn(sk, "h-[18px] w-30")} />
          <Skeleton className={cn(sk, "h-11")} />
          <Skeleton className={cn(sk, "h-11")} />
          <Skeleton className={cn(sk, "h-[110px] w-[340px] max-w-full self-end")} />
        </div>
        <div className={cn(cardClass, "flex w-full flex-col gap-2.5 p-5 xl:w-[388px]")}>
          <Skeleton className={cn(sk, "h-[18px] w-40")} />
          <Skeleton className={cn(sk, "h-4")} />
          <Skeleton className={cn(sk, "h-4")} />
          <Skeleton className={cn(sk, "h-4")} />
          <Skeleton className={cn(sk, "h-9")} />
        </div>
      </div>
    </div>
  )
}

function NotFound({
  invoice,
  onRetry,
  backHref,
  mobile,
  code,
}: {
  invoice: string | null
  onRetry: () => void
  backHref: string
  mobile: boolean
  code?: string
}) {
  return (
    <section role="alert" className={cardClass}>
      <div className={cn("flex flex-col items-center gap-2.5 px-6 text-center", mobile ? "py-12" : "py-[110px]")}>
        <div className="mb-1 flex size-14 items-center justify-center rounded-2xl bg-loss-soft text-loss">
          <TriangleAlert className={mobile ? "size-[26px]" : "size-7"} aria-hidden />
        </div>
        <div className="text-[15px] font-bold text-heading">
          {mobile ? D.notFoundTitleMobile : D.notFoundTitle(invoice)}
        </div>
        <div className="max-w-[420px] text-[13px] text-text-3">{mobile ? D.notFoundBodyMobile : D.notFoundBody}</div>
        <div className="mt-1.5 flex gap-2">
          <Btn size={mobile ? "lg" : "md"} onClick={onRetry}>
            <RotateCw className="size-4" />
            {L.retry}
          </Btn>
          <Link href={backHref} className={btnClass("ghost", mobile ? "lg" : "md")}>
            {D.backToOrders}
          </Link>
        </div>
        {code && !mobile && (
          <div className="text-xs text-text-3">
            {L.errorCode}{" "}
            <span dir="ltr" className="inline-block font-mono">
              {code}
            </span>
          </div>
        )}
      </div>
    </section>
  )
}
