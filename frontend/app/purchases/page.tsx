import { Suspense } from "react"
import { PurchasesPage } from "@/components/purchases/purchases-page"

export default function Page() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense>
      <PurchasesPage />
    </Suspense>
  )
}
