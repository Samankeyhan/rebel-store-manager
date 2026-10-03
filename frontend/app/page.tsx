import { Suspense } from "react"
import { Dashboard } from "@/components/dashboard/dashboard"

export default function DashboardPage() {
  return (
    // useSearchParams (the period lives in the URL) needs a Suspense boundary in a static export.
    <Suspense>
      <Dashboard />
    </Suspense>
  )
}
