import { Suspense } from "react"
import { AdjustmentsPage } from "@/components/adjustments/adjustments-page"

export default function Page() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense>
      <AdjustmentsPage />
    </Suspense>
  )
}
