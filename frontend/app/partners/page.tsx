import { Suspense } from "react"
import { PartnersPage } from "@/components/partners/partners-page"

export default function Page() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense>
      <PartnersPage />
    </Suspense>
  )
}
