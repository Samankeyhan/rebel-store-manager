import type { LucideIcon } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getNavItem } from "@/lib/nav"

/** Placeholder card for a screen (or tab) that isn't built yet. */
export function StubCard({ title, icon: Icon }: { title: string; icon: LucideIcon }) {
  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="size-5 text-primary" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-muted-foreground">
        این صفحه هنوز ساخته نشده است.
      </CardContent>
    </Card>
  )
}

/** Placeholder for a whole page, titled from its nav item. */
export function PageStub({ href }: { href: string }) {
  const { title, icon } = getNavItem(href)
  return <StubCard title={title} icon={icon} />
}
