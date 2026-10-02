import { Suspense } from "react"
import { PackagingPage } from "@/components/packaging/packaging-page"

export default function Page() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense>
      <PackagingPage />
    </Suspense>
  )
}
