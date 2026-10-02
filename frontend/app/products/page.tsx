import { Suspense } from "react"
import { ProductsPage } from "@/components/products/products-page"

export default function Page() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense>
      <ProductsPage />
    </Suspense>
  )
}
