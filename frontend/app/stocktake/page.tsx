import { Suspense } from "react"
import { StocktakePage } from "@/components/stocktake/stocktake-page"

export default function Page() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense>
      <StocktakePage />
    </Suspense>
  )
}
