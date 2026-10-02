"use client"

import * as React from "react"
import { CalendarDays } from "lucide-react"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { dateToISO, formatJalali, isoToDate } from "@/lib/jalali"
import { cn } from "@/lib/utils"

/**
 * `.select`-styled Jalali day field for record dates (design 06/07 «تاریخ …»):
 * the day on one side, «امروز» on the other when it is today. Future days are
 * disabled. Value is a Gregorian "YYYY-MM-DD"; `today` is read on the client.
 */
export function DateField({
  id,
  value,
  today,
  onChange,
  todayLabel,
  mobile,
}: {
  id?: string
  value: string
  today: string
  onChange: (iso: string) => void
  todayLabel: string
  mobile?: boolean
}) {
  const [open, setOpen] = React.useState(false)
  const selected = isoToDate(value)
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          id={id}
          type="button"
          className={cn(
            "flex w-full min-w-0 cursor-pointer items-center justify-between gap-2 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
            mobile ? "h-12" : "h-10"
          )}
        >
          <span className="flex items-center gap-2">
            <CalendarDays className="size-4 text-text-3" aria-hidden />
            <b className="tabular-nums">{formatJalali(value, "yyyy/MM/dd")}</b>
          </span>
          {value === today && <span className="text-xs text-text-3">{todayLabel}</span>}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          calendar="persian"
          mode="single"
          selected={selected}
          defaultMonth={selected}
          disabled={{ after: isoToDate(today) }}
          onSelect={(date) => {
            if (date) onChange(dateToISO(date))
            setOpen(false)
          }}
        />
      </PopoverContent>
    </Popover>
  )
}
