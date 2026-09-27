"use client"

import * as React from "react"
import { CalendarIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { dateToISO, formatJalali, isoToDate } from "@/lib/jalali"

/**
 * Jalali date pickers. Values in and out are Gregorian "YYYY-MM-DD" strings,
 * so a form can send them to the API as-is; only the display is Jalali.
 */

type TriggerProps = {
  placeholder?: string
  disabled?: boolean
  className?: string
  id?: string
}

// Spreads the rest props so PopoverTrigger's asChild can inject its
// onClick/aria/ref into the button.
function Trigger({
  label,
  placeholder,
  className,
  ...props
}: React.ComponentProps<typeof Button> & {
  label: string | null
  placeholder?: string
}) {
  return (
    <Button
      variant="outline"
      data-empty={label === null}
      className={cn(
        "w-56 justify-start gap-2 font-normal data-[empty=true]:text-muted-foreground",
        className
      )}
      {...props}
    >
      <CalendarIcon />
      {label ?? placeholder}
    </Button>
  )
}

export function JalaliDatePicker({
  value,
  onChange,
  placeholder = "انتخاب تاریخ",
  ...triggerProps
}: TriggerProps & {
  value: string | null
  onChange: (value: string | null) => void
}) {
  const [open, setOpen] = React.useState(false)
  const selected = value ? isoToDate(value) : undefined

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Trigger
          label={value ? formatJalali(value) : null}
          placeholder={placeholder}
          {...triggerProps}
        />
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          calendar="persian"
          mode="single"
          selected={selected}
          defaultMonth={selected}
          onSelect={(date) => {
            onChange(date ? dateToISO(date) : null)
            setOpen(false)
          }}
        />
      </PopoverContent>
    </Popover>
  )
}

export type IsoDateRange = { from: string | null; to: string | null }

export function JalaliDateRangePicker({
  value,
  onChange,
  placeholder = "انتخاب بازه",
  ...triggerProps
}: TriggerProps & {
  value: IsoDateRange
  onChange: (value: IsoDateRange) => void
}) {
  const from = value.from ? isoToDate(value.from) : undefined
  const to = value.to ? isoToDate(value.to) : undefined

  let label: string | null = null
  if (value.from && value.to) {
    label = `${formatJalali(value.from)} تا ${formatJalali(value.to)}`
  } else if (value.from) {
    label = `از ${formatJalali(value.from)}`
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Trigger
          label={label}
          placeholder={placeholder}
          {...triggerProps}
          className={cn("w-auto min-w-56", triggerProps.className)}
        />
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          calendar="persian"
          mode="range"
          numberOfMonths={2}
          selected={{ from, to }}
          defaultMonth={from}
          onSelect={(range) =>
            onChange({
              from: range?.from ? dateToISO(range.from) : null,
              to: range?.to ? dateToISO(range.to) : null,
            })
          }
        />
      </PopoverContent>
    </Popover>
  )
}
