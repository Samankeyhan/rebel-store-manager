import { Suspense } from "react"
import { RecordSale } from "@/components/record-sale/record-sale"

// /sales/new/?correct=N opens the form in correction mode («اصلاح سفارش»); a query param, as for
// /orders/view/, since a static export has no dynamic routes. useSearchParams needs the Suspense.
export default function SalesNewPage() {
  return (
    <Suspense>
      <RecordSale />
    </Suspense>
  )
}
