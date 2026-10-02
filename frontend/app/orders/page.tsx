import { Suspense } from "react"
import { OrdersList } from "@/components/orders/list/orders-list"

// useSearchParams needs a Suspense boundary in a static export.
export default function OrdersPage() {
  return (
    <Suspense>
      <OrdersList />
    </Suspense>
  )
}
