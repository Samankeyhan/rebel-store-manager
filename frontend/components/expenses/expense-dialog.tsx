"use client"

import * as React from "react"
import { ChevronDown, Loader2, Plus, X } from "lucide-react"
import { DateField } from "@/components/common/date-field"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { DrawerShell, SaveError, textInputClass } from "@/components/products/drawer-shell"
import { Btn, Help, InlineMessage, IntInput, Label } from "@/components/record-sale/primitives"
import { ApiError, createExpense, type Expense, type ExpenseCategory } from "@/lib/api"
import { cn } from "@/lib/utils"
import { E } from "./copy"
import { NewCategoryDialog } from "./new-category-dialog"

/**
 * «ثبت هزینه» (design 11 Expenses-Form): تاریخ + دسته, شرح, مبلغ. Desktop: a
 * centred 500px dialog. Mobile: a bottom sheet (not designed; record-sale
 * precedent). No preview — an expense changes no item's cost; it only adds
 * to the P&L's operating_expenses for its day.
 */
export function ExpenseDialog({
  open,
  mobile,
  today,
  categories,
  initialCategoryId,
  onClose,
  onSaved,
  onCategoryCreated,
  refreshCategories,
}: {
  open: boolean
  mobile: boolean
  today: string
  /** Active categories only. */
  categories: ExpenseCategory[]
  initialCategoryId: number | null
  onClose: () => void
  onSaved: (expense: Expense) => void
  onCategoryCreated: (category: ExpenseCategory) => void
  refreshCategories: () => Promise<void>
}) {
  const [date, setDate] = React.useState(today)
  const [categoryId, setCategoryId] = React.useState<number | null>(null)
  const [description, setDescription] = React.useState("")
  const [amount, setAmount] = React.useState(0)
  const [touched, setTouched] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<{ message: string; code: string } | null>(null)
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>({})
  const [newCategoryOpen, setNewCategoryOpen] = React.useState(false)

  const [wasOpen, setWasOpen] = React.useState(false)
  if (open && !wasOpen) {
    setWasOpen(true)
    setDate(today)
    setCategoryId(initialCategoryId != null && categories.some((c) => c.id === initialCategoryId) ? initialCategoryId : null)
    setDescription("")
    setAmount(0)
    setTouched(false)
    setError(null)
    setFieldErrors({})
  } else if (!open && wasOpen) {
    setWasOpen(false)
  }

  const category = categories.find((c) => c.id === categoryId) ?? null
  const categoryError = fieldErrors.expense_category_id || (touched && category == null ? E.categoryRequired : null)
  const amountError = fieldErrors.amount || (touched && amount <= 0 ? E.amountRequired : null)

  const close = () => {
    if (!busy) onClose()
  }

  const submit = async () => {
    setTouched(true)
    setError(null)
    setFieldErrors({})
    // The API accepts a zero amount; a zero expense means nothing, so the screen doesn't.
    if (category == null || amount <= 0 || busy) return
    setBusy(true)
    try {
      const saved = await createExpense({
        expense_category_id: category.id,
        amount,
        // Today: the server stamps the current time. Another day: that day.
        expense_date: date === today ? null : date,
        description: description.trim() || null,
      })
      onSaved(saved)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        // The category vanished since the list loaded: make them pick again.
        setCategoryId(null)
        setFieldErrors({ expense_category_id: E.categoryGone })
        refreshCategories().catch(() => {})
      } else if (e instanceof ApiError && e.status === 422 && e.field && ["amount", "expense_date", "date"].includes(e.field)) {
        setFieldErrors({ [e.field === "amount" ? "amount" : "expense_date"]: e.message })
      } else {
        setError(
          e instanceof ApiError
            ? { message: e.message, code: e.status === 0 ? "NET_TIMEOUT" : `EXPENSES_${e.status}` }
            : { message: String(e), code: "UNKNOWN" }
        )
      }
    } finally {
      setBusy(false)
    }
  }

  const categoryPicker = (
    <DropdownMenu dir="rtl" modal={false}>
      <DropdownMenuTrigger asChild>
        <button
          id="ef-category"
          type="button"
          className={cn(
            "flex w-full min-w-0 cursor-pointer items-center justify-between gap-2 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
            mobile ? "h-12" : "h-10",
            categoryError && "border-loss ring-3 ring-loss-soft"
          )}
        >
          <span className={cn("truncate", category ? "font-bold" : "text-text-3")}>{category?.name ?? E.pickCategory}</span>
          <ChevronDown className="size-3.5 shrink-0 text-text-3" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-80 w-60 overflow-y-auto">
        {categories.length > 0 && (
          <>
            <DropdownMenuRadioGroup
              value={categoryId == null ? "" : String(categoryId)}
              onValueChange={(v) => {
                setCategoryId(Number(v))
                setFieldErrors((f) => ({ ...f, expense_category_id: "" }))
              }}
            >
              {categories.map((c) => (
                <DropdownMenuRadioItem key={c.id} value={String(c.id)}>
                  {c.name}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem onSelect={() => setNewCategoryOpen(true)}>
          <Plus className="size-4" />
          {E.addCategoryOption}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )

  const fields = (
    <div className={cn("flex flex-col", mobile ? "gap-3" : "gap-3.5")}>
      {error && <SaveError {...error} />}
      <div className="grid grid-cols-2 gap-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="ef-date">{E.fieldDate}</Label>
          <DateField id="ef-date" value={date} today={today} onChange={setDate} todayLabel={E.today} mobile={mobile} />
          {fieldErrors.expense_date && <InlineMessage severity="error">{fieldErrors.expense_date}</InlineMessage>}
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="ef-category">{E.fieldCategory}</Label>
          {categoryPicker}
          {categoryError && <InlineMessage severity="error">{categoryError}</InlineMessage>}
        </div>
      </div>
      {categories.length === 0 && <Help>{E.noCategoriesYet}</Help>}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="et" optional>
          {E.fieldDescription}
        </Label>
        <input
          id="et"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className={textInputClass(mobile)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="ef-amount">{E.fieldAmount}</Label>
        <IntInput
          id="ef-amount"
          value={amount}
          onValue={(n) => {
            setAmount(n)
            setFieldErrors((f) => ({ ...f, amount: "" }))
          }}
          suffix={E.toman}
          tone={amountError ? "error" : null}
          aria-invalid={!!amountError || undefined}
          className={mobile ? "h-12" : undefined}
        />
        {amountError ? <InlineMessage severity="error">{amountError}</InlineMessage> : <Help>{E.amountHelp}</Help>}
      </div>
    </div>
  )

  const submitBtn = (
    <Btn
      variant="primary"
      size={mobile ? "lg" : "md"}
      className={mobile ? "grow" : undefined}
      disabled={busy}
      aria-busy={busy || undefined}
      onClick={submit}
    >
      {busy && <Loader2 className="size-4 animate-spin" />}
      {E.submit}
    </Btn>
  )
  const cancelBtn = (
    <Btn size={mobile ? "lg" : "md"} disabled={busy} onClick={close}>
      {E.cancel}
    </Btn>
  )

  const newCategory = (
    <NewCategoryDialog
      open={newCategoryOpen}
      mobile={mobile}
      onClose={() => setNewCategoryOpen(false)}
      onCreated={(c) => {
        onCategoryCreated(c)
        setCategoryId(c.id)
        setFieldErrors((f) => ({ ...f, expense_category_id: "" }))
        setNewCategoryOpen(false)
      }}
    />
  )

  if (mobile) {
    return (
      <>
        <DrawerShell
          open={open}
          onOpenChange={(o) => !o && close()}
          mobile
          title={E.formTitle}
          busy={busy}
          footer={
            <>
              {submitBtn}
              {cancelBtn}
            </>
          }
        >
          {fields}
        </DrawerShell>
        {newCategory}
      </>
    )
  }

  return (
    <>
      <Dialog open={open} onOpenChange={(o) => !o && close()}>
        <DialogContent
          showCloseButton={false}
          aria-labelledby="ef"
          style={{ maxWidth: "min(500px, calc(100% - 2rem))" }}
          className="w-full gap-0 overflow-hidden rounded-[14px] border border-border bg-card p-0 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)] ring-0 sm:max-w-none"
        >
          <div className="flex items-center justify-between border-b border-border px-6 py-4">
            <DialogTitle id="ef" className="text-base font-bold text-heading">
              {E.formTitle}
            </DialogTitle>
            <DialogDescription className="sr-only">{E.amountHelp}</DialogDescription>
            <Btn variant="ghost" size="sm" className="size-8 px-0" aria-label={E.close} disabled={busy} onClick={close}>
              <X className="size-4" />
            </Btn>
          </div>
          <div className="flex max-h-[70vh] flex-col overflow-y-auto px-6 py-5">{fields}</div>
          <div className="flex justify-start gap-2 border-t border-border bg-surface-2 px-6 py-4">
            {submitBtn}
            {cancelBtn}
          </div>
        </DialogContent>
      </Dialog>
      {newCategory}
    </>
  )
}
