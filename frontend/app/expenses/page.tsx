import { Suspense } from "react"
import { ExpensesPage } from "@/components/expenses/expenses-page"

export default function Page() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense>
      <ExpensesPage />
    </Suspense>
  )
}
