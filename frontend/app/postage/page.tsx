import { Suspense } from "react"
import { PostagePage } from "@/components/postage/postage-page"

export default function Page() {
  return (
    // useSearchParams (the ledger's range is in the URL) needs a Suspense boundary in a static export.
    <Suspense>
      <PostagePage />
    </Suspense>
  )
}
