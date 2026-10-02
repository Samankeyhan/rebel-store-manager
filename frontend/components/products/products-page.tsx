"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ChevronDown, CircleCheck, Plus, Search, X } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { useRecipes } from "@/components/record-sale/use-recipes"
import {
  ApiError,
  deactivateMaterial,
  deactivateProduct,
  reactivateMaterial,
  reactivateProduct,
  type Material,
  type Product,
} from "@/lib/api"
import { categoryLabel } from "@/lib/categories"
import { toPersianDigits } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { P } from "./copy"
import { DeactivateDialog, type DeactivateTarget } from "./deactivate-dialog"
import { Switch } from "./drawer-shell"
import { CATEGORY_CODES, costState, norm } from "./figures"
import { MaterialDrawer } from "./material-drawer"
import { MaterialsTab } from "./materials-tab"
import { ProductDrawer } from "./product-drawer"
import { ProductsTab } from "./products-tab"
import { EmptyState, ErrorState, LoadingState, NoMatch } from "./states"
import { useCatalogData } from "./use-catalog-data"

const TABS = ["products", "materials"] as const
type Tab = (typeof TABS)[number]

function isTab(value: string | null): value is Tab {
  return TABS.includes(value as Tab)
}

type Panel =
  | { kind: "none" }
  | { kind: "addProduct" }
  | { kind: "editProduct"; id: number }
  | { kind: "addMaterial" }

/**
 * Products & materials (design 05). The active tab, search, category and
 * «نمایش غیرفعال‌ها» live in the URL (?tab= as before), so a reload or a link
 * (e.g. straight to ?tab=materials) restores them.
 */
export function ProductsPage() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()
  const tabParam = params.get("tab")
  const tab: Tab = isTab(tabParam) ? tabParam : "products"
  const showInactive = params.get("inactive") === "1"
  const category = (CATEGORY_CODES as readonly string[]).includes(params.get("category") ?? "")
    ? (params.get("category") as string)
    : ""
  const q = params.get("q") ?? ""

  const setParams = React.useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(window.location.search)
      for (const [k, v] of Object.entries(patch)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      if (next.get("tab") === "products") next.delete("tab")
      const qs = next.toString()
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
    },
    [router, pathname]
  )

  // Search is typed locally and pushed to the URL after a short pause.
  const [search, setSearch] = React.useState(q)
  React.useEffect(() => {
    if (search === q) return
    const t = window.setTimeout(() => setParams({ q: search || null }), 250)
    return () => window.clearTimeout(t)
  }, [search, q, setParams])

  const { state, reload, upsertProduct, upsertMaterial } = useCatalogData()
  const [panel, setPanel] = React.useState<Panel>({ kind: "none" })
  const [deactivating, setDeactivating] = React.useState<DeactivateTarget | null>(null)
  const [deactivateBusy, setDeactivateBusy] = React.useState(false)
  const [pageError, setPageError] = React.useState<string | null>(null)
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const products = React.useMemo(() => (state.status === "ready" ? state.products : []), [state])
  const materials = React.useMemo(() => (state.status === "ready" ? state.materials : []), [state])

  const query = norm(q)
  const visibleProducts = products.filter(
    (p) =>
      (showInactive || p.is_active === 1) &&
      (!category || p.category === category) &&
      (!query || norm(p.name).includes(query) || norm(categoryLabel(p.category)).includes(query))
  )
  const visibleMaterials = materials.filter(
    (m) => (showInactive || m.is_active === 1) && (!query || norm(m.name).includes(query))
  )
  // Count pills follow the inactive switch, not the search.
  const productCount = products.filter((p) => showInactive || p.is_active === 1).length
  const materialCount = materials.filter((m) => showInactive || m.is_active === 1).length
  const missingCost = visibleProducts.filter((p) => p.is_active === 1 && costState(p).kind === "missing")

  const editing = panel.kind === "editProduct" ? products.find((p) => p.id === panel.id) ?? null : null

  // Made-to-order products with no stock: estimate their cost from the recipe
  // (record-sale's lazy, cached fetch). No recipe or a failed call → no
  // estimate, and the plain «هنگام فروش از دستور تولید» note stays.
  const recipeIds = [...visibleProducts, ...(editing ? [editing] : [])]
    .filter((p) => costState(p).kind === "fromRecipe")
    .map((p) => p.id)
  const recipes = useRecipes(recipeIds)
  const estimates: Record<number, number> = {}
  for (const [id, r] of Object.entries(recipes)) {
    if (r.status === "ok") estimates[Number(id)] = r.unitCost
  }

  /** Not destructive, so no confirmation: flips is_active back to 1. */
  const reactivate = async (target: DeactivateTarget) => {
    try {
      if (target.kind === "product") {
        const p = await reactivateProduct(target.item.id)
        upsertProduct(p)
        setToast(P.toastReactivated(p.name))
      } else {
        const m = await reactivateMaterial(target.item.id)
        upsertMaterial(m)
        setToast(P.toastReactivated(m.name))
      }
    } catch (e) {
      setPageError(e instanceof ApiError ? e.message : String(e))
    }
  }

  const clearFilters = () => {
    setSearch("")
    setParams({ q: null, category: null })
  }

  const confirmDeactivate = async () => {
    if (!deactivating) return
    setDeactivateBusy(true)
    try {
      if (deactivating.kind === "product") {
        const p = await deactivateProduct(deactivating.item.id)
        upsertProduct(p)
        setToast(P.toastDeactivated(p.name))
      } else {
        const m = await deactivateMaterial(deactivating.item.id)
        upsertMaterial(m)
        setToast(P.toastDeactivated(m.name))
      }
      setDeactivating(null)
      setPanel({ kind: "none" })
    } catch (e) {
      setDeactivating(null)
      setPageError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setDeactivateBusy(false)
    }
  }

  const addProduct = () => setPanel({ kind: "addProduct" })
  const addMaterial = () => setPanel({ kind: "addMaterial" })
  // One add action, scoped to the visible tab.
  const onAdd = tab === "products" ? addProduct : addMaterial
  const addLabel = tab === "products" ? P.addProduct : P.addMaterial

  const toolbar = mobile ? (
    <SearchBox value={search} onChange={setSearch} mobile />
  ) : (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2.5">
        <SearchBox value={search} onChange={setSearch} />
        {tab === "products" && <CategoryFilter value={category} onChange={(c) => setParams({ category: c || null })} />}
        <label className="flex cursor-pointer items-center gap-2 text-[13px]">
          <Switch checked={showInactive} onChange={(v) => setParams({ inactive: v ? "1" : null })} labelledBy="show-inactive" />
          <span id="show-inactive">{P.showInactive}</span>
        </label>
      </div>
      <Btn variant="primary" onClick={onAdd}>
        <Plus className="size-4" />
        {addLabel}
      </Btn>
    </div>
  )

  let body: React.ReactNode
  if (state.status === "loading") body = <LoadingState mobile={mobile} />
  else if (state.status === "error") body = <ErrorState onRetry={reload} mobile={mobile} />
  else if (tab === "products") {
    if (products.length === 0) body = <EmptyState kind="products" onAdd={addProduct} mobile={mobile} />
    else if (visibleProducts.length === 0)
      body = <NoMatch text={q ? P.noProductMatch(q) : P.noMatchFiltered} onClear={clearFilters} mobile={mobile} />
    else
      body = (
        <ProductsTab
          rows={visibleProducts}
          missingCost={missingCost}
          mobile={mobile}
          onEdit={(p) => setPanel({ kind: "editProduct", id: p.id })}
          onDeactivate={(p) => setDeactivating({ kind: "product", item: p })}
          onReactivate={(p) => reactivate({ kind: "product", item: p })}
          estimates={estimates}
        />
      )
  } else {
    if (materials.length === 0) body = <EmptyState kind="materials" onAdd={addMaterial} mobile={mobile} />
    else if (visibleMaterials.length === 0)
      body = <NoMatch text={q ? P.noMaterialMatch(q) : P.noMatchFiltered} onClear={clearFilters} mobile={mobile} />
    else
      body = (
        <MaterialsTab
          rows={visibleMaterials}
          mobile={mobile}
          onDeactivate={(m) => setDeactivating({ kind: "material", item: m })}
          onReactivate={(m) => reactivate({ kind: "material", item: m })}
        />
      )
  }

  return (
    <div className={cn("flex flex-col", mobile ? "gap-3 pb-24" : "gap-5")}>
      {toolbar}
      {state.status === "ready" && (
        <div role="tablist" aria-label={`${P.tabProducts} / ${P.tabMaterials}`} className="flex gap-1 border-b border-border">
          {(
            [
              ["products", P.tabProducts, productCount],
              ["materials", P.tabMaterials, materialCount],
            ] as const
          ).map(([id, label, count]) => {
            const on = tab === id
            return (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={on}
                onClick={() => setParams({ tab: id })}
                className={cn(
                  "-mb-px inline-flex cursor-pointer items-center gap-1.5 border-b-2 border-transparent px-3 text-[13.5px] font-semibold whitespace-nowrap text-text-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/30",
                  mobile ? "h-11 grow justify-center" : "h-10",
                  on && "border-primary text-heading"
                )}
              >
                {label}
                <span
                  className={cn(
                    "inline-flex h-[18px] min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] tabular-nums",
                    on ? "bg-red-soft text-primary" : "bg-surface-3 text-text-2"
                  )}
                >
                  {toPersianDigits(count)}
                </span>
              </button>
            )
          })}
        </div>
      )}
      {mobile && state.status === "ready" && (
        <label className="flex items-center gap-2 text-[13px]">
          <Switch checked={showInactive} onChange={(v) => setParams({ inactive: v ? "1" : null })} labelledBy="show-inactive-m" />
          <span id="show-inactive-m">{P.showInactive}</span>
        </label>
      )}
      {pageError && (
        <Alert
          tone="err"
          title={P.saveFailed}
          action={
            <Btn variant="ghost" size="sm" className="size-8 px-0" aria-label={P.close} onClick={() => setPageError(null)}>
              <X className="size-4" />
            </Btn>
          }
        >
          <div dir="auto">{pageError}</div>
        </Alert>
      )}
      {body}

      {mobile && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card px-4 pt-3 pb-5">
          <Btn variant="primary" size="lg" className="w-full" onClick={onAdd}>
            <Plus className="size-4" />
            {addLabel}
          </Btn>
        </div>
      )}

      <ProductDrawer
        open={panel.kind === "addProduct" || (panel.kind === "editProduct" && editing != null)}
        product={panel.kind === "editProduct" ? editing : null}
        mobile={mobile}
        onClose={() => setPanel({ kind: "none" })}
        onSaved={(p: Product, message: string, close = true) => {
          upsertProduct(p)
          setToast(message)
          if (close) setPanel({ kind: "none" })
        }}
        onDeactivate={(p) => setDeactivating({ kind: "product", item: p })}
        onReactivate={(p) => reactivate({ kind: "product", item: p })}
        estimate={editing ? estimates[editing.id] : undefined}
      />
      <MaterialDrawer
        open={panel.kind === "addMaterial"}
        mobile={mobile}
        onClose={() => setPanel({ kind: "none" })}
        onSaved={(m: Material, message: string) => {
          upsertMaterial(m)
          setToast(message)
          setPanel({ kind: "none" })
        }}
      />
      <DeactivateDialog
        target={deactivating}
        mobile={mobile}
        busy={deactivateBusy}
        onCancel={() => setDeactivating(null)}
        onConfirm={confirmDeactivate}
      />
      {toast && <Toast title={toast} onClose={closeToast} />}
    </div>
  )
}

function SearchBox({ value, onChange, mobile }: { value: string; onChange: (v: string) => void; mobile?: boolean }) {
  return (
    <div className={cn("relative flex items-center", mobile ? "w-full" : "w-[280px]")}>
      <Search className="pointer-events-none absolute start-3 size-4 text-text-3" aria-hidden />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={P.searchPlaceholder}
        aria-label={P.searchAria}
        className={cn(
          "w-full rounded-lg border border-border-strong bg-card ps-[38px] pe-3 text-sm outline-none placeholder:text-text-3 focus:border-heading focus:ring-3 focus:ring-ring/30",
          mobile ? "h-11" : "h-10"
        )}
      />
    </div>
  )
}

function CategoryFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <DropdownMenu dir="rtl">
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-10 cursor-pointer items-center gap-2.5 rounded-lg border border-border-strong bg-card px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
        >
          <span className="text-text-3">{P.categoryLabel}</span>
          <span className="font-bold">{value ? categoryLabel(value) : P.categoryAll}</span>
          <ChevronDown className="size-3.5 text-text-3" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-44">
        <DropdownMenuRadioGroup value={value} onValueChange={onChange}>
          <DropdownMenuRadioItem value="">{P.categoryAll}</DropdownMenuRadioItem>
          {CATEGORY_CODES.map((c) => (
            <DropdownMenuRadioItem key={c} value={c}>
              {categoryLabel(c)}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function Toast({ title, onClose }: { title: string; onClose: () => void }) {
  React.useEffect(() => {
    const t = window.setTimeout(onClose, 4000)
    return () => window.clearTimeout(t)
  }, [onClose, title])
  return (
    // Bottom-left: a screen-edge choice (design-system §5 Toast).
    <div
      role="status"
      className="fixed bottom-6 left-6 z-50 flex w-[360px] max-w-[calc(100vw-32px)] items-center gap-3 rounded-xl border border-border bg-card px-4 py-3.5 shadow-[0_18px_44px_rgba(18,22,38,.18),0_2px_6px_rgba(18,22,38,.08)]"
    >
      <CircleCheck className="size-5 shrink-0 text-profit" aria-hidden />
      <div className="min-w-0 grow text-[13.5px] font-bold">{title}</div>
      <Btn variant="ghost" size="sm" className="w-8 px-0" aria-label={P.close} onClick={onClose}>
        <X className="size-4" />
      </Btn>
    </div>
  )
}
