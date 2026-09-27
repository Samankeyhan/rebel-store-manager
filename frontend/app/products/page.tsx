"use client"

import * as React from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Layers, Package } from "lucide-react"
import { StubCard } from "@/components/page-stub"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const TABS = ["products", "materials"] as const
type Tab = (typeof TABS)[number]

function isTab(value: string | null): value is Tab {
  return TABS.includes(value as Tab)
}

// The active tab lives in ?tab= so it survives reloads and can be linked to
// (e.g. a low-stock alert linking straight to /products/?tab=materials).
function ProductsTabs() {
  const router = useRouter()
  const pathname = usePathname()
  const param = useSearchParams().get("tab")
  const tab: Tab = isTab(param) ? param : "products"

  return (
    <Tabs
      value={tab}
      onValueChange={(value) =>
        router.replace(
          value === "products" ? pathname : `${pathname}?tab=${value}`,
          { scroll: false }
        )
      }
    >
      <TabsList>
        <TabsTrigger value="products">محصولات</TabsTrigger>
        <TabsTrigger value="materials">مواد اولیه</TabsTrigger>
      </TabsList>
      <TabsContent value="products">
        <StubCard title="محصولات" icon={Package} />
      </TabsContent>
      <TabsContent value="materials">
        <StubCard title="مواد اولیه" icon={Layers} />
      </TabsContent>
    </Tabs>
  )
}

export default function ProductsPage() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <React.Suspense>
      <ProductsTabs />
    </React.Suspense>
  )
}
