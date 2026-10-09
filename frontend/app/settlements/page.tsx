import { Suspense } from "react"
import { SettlementsPage } from "@/components/settlements/settlements-page"

export default function Page() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense>
      <SettlementsPage />
    </Suspense>
  )
}
