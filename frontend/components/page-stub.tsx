import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getNavItem } from "@/lib/nav"

/** Placeholder for screens that aren't built yet. */
export function PageStub({ href }: { href: string }) {
  const { title, icon: Icon } = getNavItem(href)
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
