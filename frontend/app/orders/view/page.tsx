import { Suspense } from "react"
import { OrderDetail } from "@/components/orders/detail/order-detail"

// /orders/view/?id=N — a query param, since a static export can't serve a
// dynamic [id] route for orders created after the build.
export default function OrderViewPage() {
  return (
    <Suspense>
      <OrderDetail />
    </Suspense>
  )
}
