"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { CircleCheck, Plus, Search, X } from "lucide-react"
import { useIsMobile } from "@/hooks/use-mobile"
import { Alert, Btn } from "@/components/record-sale/primitives"
import { useRecipes } from "@/components/record-sale/use-recipes"
import { Segment } from "@/components/common/segment"
import { CategoriesTab, type CategoryActions } from "@/components/categories/categories-tab"
import { CategoryDialog, type CategoryForm } from "@/components/categories/category-dialog"
import { C } from "@/components/categories/copy"
import {
  DeactivateCategoryDialog,
  type Blockers,
} from "@/components/categories/deactivate-category-dialog"
import { blockers, errorInfo, findNode, itemCounts, refusalOf, type CategoryNode } from "@/components/categories/logic"
import { MoveItemsSheet, type MoveSource } from "@/components/categories/move-items-sheet"
import {
  ApiError,
  deactivateCategory,
  deactivateMaterial,
  deactivateProduct,
  reactivateCategory,
  reactivateMaterial,
  reactivateProduct,
  setMaterialCategory,
  setProductCategory,
  type CategoryKind,
  type CategoryTree,
  type Material,
  type Product,
} from "@/lib/api"
import { categoryPath, descendantIds, treeHas } from "@/lib/category-path"
import { toPersianDigits } from "@/lib/persian-numbers"
import { cn } from "@/lib/utils"
import { P } from "./copy"
import { DeactivateDialog, type DeactivateTarget } from "./deactivate-dialog"
import { Switch } from "./drawer-shell"
import { CategoryFilter } from "./category-picker"
import { costState, norm } from "./figures"
import { MaterialDrawer } from "./material-drawer"
import { MaterialsTab } from "./materials-tab"
import { ProductDrawer } from "./product-drawer"
import { ProductsTab } from "./products-tab"
import { EmptyState, ErrorState, LoadingState, NoMatch } from "./states"
import { useCatalogData } from "./use-catalog-data"

const TABS = ["products", "materials", "categories"] as const
type Tab = (typeof TABS)[number]

/** A ?category= value naming a node of this tree. */
function isCategoryParam(value: string, tree: CategoryTree[]): boolean {
  return /^\d+$/.test(value) && treeHas(tree, Number(value))
}

function isTab(value: string | null): value is Tab {
  return TABS.includes(value as Tab)
}

type Panel =
  | { kind: "none" }
  | { kind: "addProduct" }
  | { kind: "editProduct"; id: number }
  | { kind: "addMaterial" }

/** Server-reported blockers for the category being deactivated (local data was stale). */
type ServerBlock = { items: number | null | undefined; children: boolean }

/**
 * Products & materials (design 05), plus «دسته‌ها» (no design: manage both
 * category trees). The active tab, search, category, the categories tab's
 * kind and «نمایش غیرفعال‌ها» live in the URL (?tab= as before), so a reload
 * or a link (e.g. straight to ?tab=materials) restores them.
 */
export function ProductsPage() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const mobile = useIsMobile()
  const tabParam = params.get("tab")
  const tab: Tab = isTab(tabParam) ? tabParam : "products"
  const showInactive = params.get("inactive") === "1"
  const catKind: CategoryKind = params.get("kind") === "material" ? "MATERIAL" : "PRODUCT"
  // Category filters: a category id per tab (?category= products,
  // ?matCategory= materials), or "none" for uncategorised materials.
  // Anything unrecognised — e.g. an old ?category=VINYL link — means «همه».
  const categoryParam = params.get("category") ?? ""
  const matCategoryParam = params.get("matCategory") ?? ""
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

  const { state, reload, reloadTree, upsertProduct, upsertMaterial } = useCatalogData()
  const [panel, setPanel] = React.useState<Panel>({ kind: "none" })
  const [deactivating, setDeactivating] = React.useState<DeactivateTarget | null>(null)
  const [deactivateBusy, setDeactivateBusy] = React.useState(false)
  const [pageError, setPageError] = React.useState<string | null>(null)
  const [toast, setToast] = React.useState<string | null>(null)
  const closeToast = React.useCallback(() => setToast(null), [])

  const products = React.useMemo(() => (state.status === "ready" ? state.products : []), [state])
  const materials = React.useMemo(() => (state.status === "ready" ? state.materials : []), [state])

  const productTree = React.useMemo(() => (state.status === "ready" ? state.productTree : []), [state])
  const materialTree = React.useMemo(() => (state.status === "ready" ? state.materialTree : []), [state])

  // «دسته‌ها»: the tree of the selected kind and item counts per category,
  // derived from the lists already loaded (inactive items included, as the
  // backend counts them when refusing a deactivation).
  const catTree = catKind === "PRODUCT" ? productTree : materialTree
  const catItems: (Product | Material)[] = catKind === "PRODUCT" ? products : materials
  const catCounts = React.useMemo(() => itemCounts(catItems), [catItems])
  const uncategorised = React.useMemo(() => {
    const none = catItems.filter((it) => it.category_id == null)
    return { total: none.length, inactive: none.filter((it) => it.is_active !== 1).length }
  }, [catItems])
  const catCount = catTree.reduce(
    (n, t) =>
      n +
      (showInactive || t.is_active === 1 ? 1 : 0) +
      t.children.filter((c) => showInactive || c.is_active === 1).length,
    0
  )

  const [catForm, setCatForm] = React.useState<CategoryForm | null>(null)
  const [catDeactivating, setCatDeactivating] = React.useState<CategoryNode | null>(null)
  const [catServerBlock, setCatServerBlock] = React.useState<ServerBlock | null>(null)
  const [catBusy, setCatBusy] = React.useState(false)
  const [moveSource, setMoveSource] = React.useState<MoveSource | null>(null)

  /** Refetch the tree (and, for renames and refusals, the items) without failing the screen. */
  const refreshCategories = React.useCallback(
    (withItems = false) => reloadTree(catKind, withItems).catch((e) => setPageError(errorInfo(e).message)),
    [reloadTree, catKind]
  )

  // The node being deactivated, as it is in the current tree.
  const catDeactivateNode = catDeactivating ? (findNode(catTree, catDeactivating.id)?.node ?? catDeactivating) : null
  const catBlockers: Blockers = React.useMemo(() => {
    if (!catDeactivateNode) return { items: 0, activeChildren: [], children: false }
    const local = blockers(catDeactivateNode, catCounts)
    return {
      items: local.items > 0 ? local.items : catServerBlock?.items !== undefined ? catServerBlock.items : 0,
      activeChildren: local.activeChildren,
      children: local.activeChildren.length > 0 || (catServerBlock?.children ?? false),
    }
  }, [catDeactivateNode, catCounts, catServerBlock])

  const confirmCatDeactivate = async () => {
    if (!catDeactivating || catBusy) return
    setCatBusy(true)
    try {
      const c = await deactivateCategory(catDeactivating.id)
      setCatDeactivating(null)
      setToast(C.toastDeactivated(c.name))
      await refreshCategories()
    } catch (e) {
      const r = refusalOf(e)
      if (r.kind === "inUse") {
        // The page's data was stale: show the server's reason, then catch up.
        setCatServerBlock((b) => ({ items: r.count, children: b?.children ?? false }))
        await refreshCategories(true)
      } else if (r.kind === "hasChildren") {
        setCatServerBlock((b) => ({ items: b?.items, children: true }))
        await refreshCategories()
      } else {
        setCatDeactivating(null)
        setPageError(r.kind === "other" ? r.message : e instanceof Error ? e.message : String(e))
      }
    } finally {
      setCatBusy(false)
    }
  }

  const catActions: CategoryActions = {
    onAddSub: (parent) => setCatForm({ mode: "create", parentId: parent.id }),
    onRename: (node) => setCatForm({ mode: "rename", node }),
    onMove: (node) => setMoveSource({ from: node }),
    onDeactivate: (node) => {
      setCatServerBlock(null)
      setCatDeactivating(node)
    },
    /** Not destructive, so no confirmation. */
    onReactivate: async (node) => {
      try {
        const c = await reactivateCategory(node.id)
        setToast(C.toastReactivated(c.name))
        await refreshCategories()
      } catch (e) {
        const r = refusalOf(e)
        if (r.kind === "parentInactive") {
          setPageError(C.parentInactiveNote(node.parent_name ?? ""))
          await refreshCategories()
        } else setPageError(r.kind === "other" ? r.message : e instanceof Error ? e.message : String(e))
      }
    },
    onShowItems: (node) => {
      const patch: Record<string, string | null> =
        catKind === "PRODUCT"
          ? { tab: "products", category: String(node.id), q: null }
          : { tab: "materials", matCategory: String(node.id), q: null }
      // Inactive items count here, so make sure they show up there too.
      if ((catCounts.get(node.id)?.inactive ?? 0) > 0) patch.inactive = "1"
      setSearch("")
      setParams(patch)
    },
  }

  const moveItem = async (itemId: number, categoryId: number) => {
    if (catKind === "PRODUCT") upsertProduct(await setProductCategory(itemId, categoryId))
    else upsertMaterial(await setMaterialCategory(itemId, categoryId))
  }

  const { category, matCategory, productCategoryIds, materialCategoryIds } = React.useMemo(() => {
    const category = isCategoryParam(categoryParam, productTree) ? categoryParam : ""
    const matCategory =
      matCategoryParam === "none" || isCategoryParam(matCategoryParam, materialTree) ? matCategoryParam : ""
    return {
      category,
      matCategory,
      // Picking a parent also matches its subcategories (and items still on it).
      productCategoryIds: category ? descendantIds(productTree, Number(category)) : null,
      materialCategoryIds:
        matCategory && matCategory !== "none" ? descendantIds(materialTree, Number(matCategory)) : null,
    }
  }, [categoryParam, matCategoryParam, productTree, materialTree])

  const query = norm(q)
  const visibleProducts = products.filter(
    (p) =>
      (showInactive || p.is_active === 1) &&
      (!productCategoryIds || productCategoryIds.has(p.category_id)) &&
      (!query || norm(p.name).includes(query) || norm(categoryPath(p)).includes(query))
  )
  const visibleMaterials = materials.filter(
    (m) =>
      (showInactive || m.is_active === 1) &&
      (matCategory !== "none" || m.category_id == null) &&
      (!materialCategoryIds || (m.category_id != null && materialCategoryIds.has(m.category_id))) &&
      (!query || norm(m.name).includes(query) || norm(categoryPath(m)).includes(query))
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
    setParams({ q: null, category: null, matCategory: null })
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
  const addCategory = () => setCatForm({ mode: "create", parentId: null })
  const onAdd = tab === "products" ? addProduct : tab === "materials" ? addMaterial : addCategory
  const addLabel = tab === "products" ? P.addProduct : tab === "materials" ? P.addMaterial : C.add

  const kindSwitch = (
    <Segment
      value={catKind}
      label={C.kindLabel}
      mobile={mobile}
      className={mobile ? "w-full" : "w-[220px]"}
      options={[
        ["PRODUCT", C.kindProducts],
        ["MATERIAL", C.kindMaterials],
      ]}
      onChange={(k) => setParams({ kind: k === "MATERIAL" ? "material" : null })}
    />
  )

  const toolbar = mobile ? (
    tab === "categories" ? kindSwitch : <SearchBox value={search} onChange={setSearch} mobile />
  ) : (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2.5">
        {tab === "categories" ? kindSwitch : <SearchBox value={search} onChange={setSearch} />}
        {tab === "categories" ? null : tab === "products" ? (
          <CategoryFilter tree={productTree} value={category} onChange={(c) => setParams({ category: c || null })} />
        ) : (
          <CategoryFilter
            tree={materialTree}
            value={matCategory}
            onChange={(c) => setParams({ matCategory: c || null })}
            withNone
          />
        )}
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
  else if (tab === "categories")
    body = (
      <CategoriesTab
        kind={catKind}
        tree={catTree}
        counts={catCounts}
        uncategorised={catKind === "MATERIAL" ? uncategorised : { total: 0, inactive: 0 }}
        showInactive={showInactive}
        mobile={mobile}
        actions={catActions}
        onAdd={addCategory}
        onShowInactive={() => setParams({ inactive: "1" })}
      />
    )
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
              ["categories", C.tab, catCount],
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
        tree={productTree}
      />
      <MaterialDrawer
        open={panel.kind === "addMaterial"}
        tree={materialTree}
        mobile={mobile}
        onClose={() => setPanel({ kind: "none" })}
        onSaved={(m: Material, message: string) => {
          upsertMaterial(m)
          setToast(message)
          setPanel({ kind: "none" })
        }}
      />
      <CategoryDialog
        form={catForm}
        kind={catKind}
        tree={catTree}
        counts={catCounts}
        mobile={mobile}
        onClose={() => setCatForm(null)}
        onSaved={(c, mode) => {
          setCatForm(null)
          setToast(mode === "rename" ? C.toastRenamed(c.name) : C.toastCreated(c.name))
          // Items carry their category's name, so a rename refetches them too.
          refreshCategories(mode === "rename")
        }}
        onStale={() => refreshCategories()}
      />
      <DeactivateCategoryDialog
        target={catDeactivating}
        kind={catKind}
        blockers={catBlockers}
        mobile={mobile}
        busy={catBusy}
        onCancel={() => setCatDeactivating(null)}
        onConfirm={confirmCatDeactivate}
        onMove={(node) => {
          setCatDeactivating(null)
          setMoveSource({ from: node })
        }}
      />
      <MoveItemsSheet
        source={moveSource}
        kind={catKind}
        tree={catTree}
        items={catItems}
        mobile={mobile}
        onClose={() => setMoveSource(null)}
        move={moveItem}
        onFinished={(n, to) => setToast(C.toastMoved(n, catKind, to))}
        onStale={() => refreshCategories()}
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
