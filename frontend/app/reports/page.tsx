import { Suspense } from "react"
import { ReportsPage } from "@/components/reports/reports-page"

export default function Page() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense>
      <ReportsPage />
    </Suspense>
  )
}
