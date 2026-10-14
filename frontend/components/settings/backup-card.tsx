"use client"

import * as React from "react"
import { Loader2, ShieldCheck } from "lucide-react"
import { Alert, Btn, Help, cardClass } from "@/components/record-sale/primitives"
import { ApiError, createBackup, getBackups, type BackupsOut } from "@/lib/api"
import { backupReason, formatSize, keptText } from "@/lib/backups"
import { backupFailureReason } from "@/lib/error-codes"
import { formatJalaliDateTime } from "@/lib/jalali"
import { cn } from "@/lib/utils"
import { S } from "./copy"

type State = { status: "loading" } | { status: "error" } | { status: "ready"; data: BackupsOut }
type Failure = { reason: string }

/**
 * [4] پشتیبان‌گیری: the backups of the served database: when the last one was made and whether it worked, how many are
 * kept, the folder, the newest ten, and «پشتیبان‌گیری اکنون». There is no restore here: restoring is manual (docs/RUNNING.md).
 */
export function BackupCard({ timeZone, mobile, onToast }: { timeZone: string; mobile: boolean; onToast: (message: string) => void }) {
  const [state, setState] = React.useState<State>({ status: "loading" })
  const [attempt, setAttempt] = React.useState(0)
  const [busy, setBusy] = React.useState(false)
  const [failure, setFailure] = React.useState<Failure | null>(null)

  React.useEffect(() => {
    let cancelled = false
    getBackups().then(
      (data) => !cancelled && setState({ status: "ready", data }),
      () => !cancelled && setState({ status: "error" })
    )
    return () => {
      cancelled = true
    }
  }, [attempt])

  const run = async () => {
    setBusy(true)
    setFailure(null)
    try {
      const created = await createBackup()
      onToast(S.backupDone(created.name))
    } catch (e) {
      setFailure({ reason: e instanceof ApiError ? (backupFailureReason(e) ?? "unknown") : "unknown" })
    } finally {
      setBusy(false)
      setAttempt((n) => n + 1)
    }
  }

  const header = (
    <div className={cn("flex flex-wrap items-center justify-between gap-3", mobile ? "px-3.5 pt-3.5" : "border-b border-border px-5 py-4")}>
      <h2 id="st4" className={cn("flex items-center gap-2 font-bold text-heading", mobile ? "text-sm" : "text-base leading-[26px]")}>
        <ShieldCheck className="size-4 text-text-2" aria-hidden />
        {S.backupTitle}
      </h2>
      <Btn variant="primary" size={mobile ? "md" : "sm"} disabled={busy || state.status !== "ready"} aria-busy={busy || undefined} onClick={run}>
        {busy && <Loader2 className="size-4 animate-spin" />}
        {busy ? S.backupRunning : S.backupNow}
      </Btn>
    </div>
  )

  let body: React.ReactNode
  if (state.status === "loading") {
    body = <p className="px-5 py-5 text-sm text-text-3">…</p>
  } else if (state.status === "error") {
    body = (
      <div className="flex flex-wrap items-center gap-3 px-5 py-5 text-sm">
        <span className="text-loss">{S.backupLoadError}</span>
        <Btn size="sm" onClick={() => setAttempt((n) => n + 1)}>
          {S.backupRetry}
        </Btn>
      </div>
    )
  } else {
    const { data } = state
    const last = data.last
    body = (
      <div className={cn("flex flex-col gap-4", mobile ? "p-3.5" : "px-5 py-5")}>
        {failure && (
          <Alert tone="err" title={S.backupFailedTitle}>
            <div>{backupReason(failure.reason)}</div>
            <div className="mt-1 text-xs text-text-3">
              {S.backupCode}{" "}
              <span dir="ltr" className="inline-block font-mono">
                BACKUP_FAILED · {failure.reason}
              </span>
            </div>
          </Alert>
        )}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px]">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{S.backupLast}:</span>
            {last ? (
              <>
                <span className="tabular-nums">{formatJalaliDateTime(last.at, timeZone)}</span>
                <span
                  className={cn(
                    "inline-flex h-[22px] items-center rounded-md px-2 text-[11.5px] font-semibold",
                    last.ok ? "bg-profit-soft text-profit" : "bg-loss-soft text-loss"
                  )}
                >
                  {last.ok ? S.backupOk : S.backupFailed}
                </span>
                {!last.ok && <span className="text-text-2">{backupReason(last.reason)}</span>}
              </>
            ) : (
              <span className="text-text-3">{S.backupNever}</span>
            )}
          </span>
          <span>
            <span className="font-semibold">{S.backupKept}:</span> <span className="tabular-nums">{keptText(data.count, data.keep)}</span>
          </span>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[13px] font-semibold">{S.backupFolder}</span>
          <div dir="ltr" className="overflow-x-auto rounded-lg border border-border bg-surface-2 px-3 py-2 text-start font-mono text-xs text-text-2">
            {data.folder}
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-semibold">{S.backupRecent}</span>
          {data.items.length === 0 ? (
            <p className="text-sm text-text-3">{S.backupEmpty}</p>
          ) : mobile ? (
            <ul className="flex flex-col gap-1.5">
              {data.items.map((item) => (
                <li key={item.name} className="flex flex-col gap-0.5 rounded-lg border border-border px-3 py-2 text-xs">
                  <span dir="ltr" className="text-start font-mono">
                    {item.name}
                  </span>
                  <span className="text-text-2">
                    {formatJalaliDateTime(item.created_at, timeZone)} · {formatSize(item.size)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-border text-xs text-text-3">
                  <th className="py-1.5 text-start font-semibold">{S.backupColName}</th>
                  <th className="py-1.5 text-start font-semibold">{S.backupColSize}</th>
                  <th className="py-1.5 text-start font-semibold">{S.backupColTime}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.name} className="border-b border-border/60 last:border-b-0">
                    <td className="py-1.5">
                      <span dir="ltr" className="inline-block font-mono text-xs">
                        {item.name}
                      </span>
                    </td>
                    <td className="py-1.5 tabular-nums">{formatSize(item.size)}</td>
                    <td className="py-1.5 tabular-nums">{formatJalaliDateTime(item.created_at, timeZone)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <Help>{S.backupNote}</Help>
      </div>
    )
  }

  return (
    <section id="backup" className={cn(cardClass, "scroll-mt-6")} aria-labelledby="st4">
      {header}
      {body}
    </section>
  )
}
