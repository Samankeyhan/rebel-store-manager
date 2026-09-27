"use client"

import * as React from "react"
import { CircleAlert, Package } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  JalaliDatePicker,
  JalaliDateRangePicker,
  type IsoDateRange,
} from "@/components/jalali-date-picker"
import { ApiError, getCatalog, type Catalog } from "@/lib/api"
import { dateToISO, formatJalali } from "@/lib/jalali"
import { formatMoney, formatNumber } from "@/lib/persian-numbers"

type CatalogState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; catalog: Catalog }

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
  )
}

function CatalogCard() {
  const [state, setState] = React.useState<CatalogState>({ status: "loading" })

  React.useEffect(() => {
    let cancelled = false
    getCatalog().then(
      (catalog) => !cancelled && setState({ status: "ready", catalog }),
      (error: unknown) =>
        !cancelled &&
        setState({
          status: "error",
          error:
            error instanceof ApiError
              ? error
              : new ApiError(String(error), 0, "UnknownError"),
        })
    )
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Package className="size-5 text-primary" />
          کاتالوگ
        </CardTitle>
        <CardDescription>داده‌ی زنده از سرور</CardDescription>
      </CardHeader>
      <CardContent>
        {state.status === "loading" && (
          <div className="space-y-3">
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-3/4" />
          </div>
        )}
        {state.status === "error" && (
          <div className="flex gap-2 text-destructive">
            <CircleAlert className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-medium">
                {state.error.type === "NetworkError"
                  ? "سرور در دسترس نیست."
                  : "خطا در دریافت کاتالوگ."}
              </p>
              <p className="text-xs opacity-80" dir="ltr">
                {state.error.message}
              </p>
            </div>
          </div>
        )}
        {state.status === "ready" && (
          <div className="divide-y">
            <Stat
              label="محصولات"
              value={formatNumber(state.catalog.products.length)}
            />
            <Stat
              label="مواد اولیه"
              value={formatNumber(state.catalog.materials.length)}
            />
            <Stat
              label="برآورد هزینه‌ی پست"
              value={formatMoney(state.catalog.postage_estimate)}
            />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function PlaceholderCard({ title }: { title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>به‌زودی</CardDescription>
      </CardHeader>
      <CardContent>
        <Skeleton className="h-16 w-full animate-none" />
      </CardContent>
    </Card>
  )
}

// Temporary: exercises both Jalali pickers until a real screen uses them.
function DatePickerDemo() {
  const [date, setDate] = React.useState<string | null>(null)
  const [range, setRange] = React.useState<IsoDateRange>({ from: null, to: null })

  return (
    <Card>
      <CardHeader>
        <CardTitle>انتخاب تاریخ (نمونه)</CardTitle>
        <CardDescription>
          مقدار ارسالی به سرور میلادی است؛ نمایش شمسی.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <JalaliDatePicker value={date} onChange={setDate} />
        <JalaliDateRangePicker value={range} onChange={setRange} />
        <p className="text-xs text-muted-foreground" dir="ltr">
          {JSON.stringify({ date, range })}
        </p>
      </CardContent>
    </Card>
  )
}

const noopSubscribe = () => () => {}

export default function DashboardPage() {
  // Client-only clock: the prerendered HTML (server snapshot) has no date,
  // otherwise a static export would freeze the build date.
  const today = React.useSyncExternalStore(
    noopSubscribe,
    () => dateToISO(new Date()),
    () => null
  )

  return (
    <div className="flex flex-col gap-6">
      <p className="text-muted-foreground">
        {today ? `امروز ${formatJalali(today, "EEEE d MMMM yyyy")}` : " "}
      </p>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <CatalogCard />
        <PlaceholderCard title="فروش امروز" />
        <PlaceholderCard title="موجودی کم" />
        <DatePickerDemo />
      </div>
    </div>
  )
}
