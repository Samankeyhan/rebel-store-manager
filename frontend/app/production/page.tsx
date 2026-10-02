import { Suspense } from "react"
import { ProductionPage } from "@/components/production/production-page"

export default function Page() {
  return (
    <Suspense>
      <ProductionPage />
    </Suspense>
  )
}
