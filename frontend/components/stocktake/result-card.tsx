"use client"

import Link from "next/link"
import { CircleCheck } from "lucide-react"
import { Money } from "@/components/common/money"
import { Btn, btnClass, cardClass } from "@/components/record-sale/primitives"
import type { StocktakeResult } from "@/lib/api"
import { S } from "./copy"

/** Shown after a count is applied: what was written, with a way back to a new count or to the adjustments list. */
export function ResultCard({ result, onAgain }: { result: StocktakeResult; onAgain: () => void }) {
  return (
    <section className={`${cardClass} flex flex-col gap-3 px-5 py-5`} role="status">
      <div className="flex items-center gap-2">
        <CircleCheck className="size-5 text-profit" aria-hidden />
        <h2 className="text-base font-bold text-heading">{S.resultTitle}</h2>
      </div>
      <p className="text-sm">{S.resultBody(result.corrections.length, result.unchanged_count)}</p>
      <p className="text-xs text-text-2">{result.note}</p>
      {result.corrections.length > 0 && (
        <p className="text-sm">
          <b>{S.total}:</b> <Money value={result.total_value} />
        </p>
      )}
      <div className="flex gap-2">
        <Link href="/adjustments" className={btnClass("primary")}>
          {S.resultHistory}
        </Link>
        <Btn onClick={onAgain}>{S.resultAgain}</Btn>
      </div>
    </section>
  )
}
