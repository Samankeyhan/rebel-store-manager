"use client"

import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"
import { ChevronLeft, ChevronRight, CircleUser, LogOut, Moon, Settings, Sun } from "lucide-react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { findNavItem } from "@/lib/nav"
import { useTopBarCrumb } from "@/components/top-bar-crumb"

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="تغییر پوسته"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      {/* Both icons rendered and swapped in CSS: avoids a hydration mismatch
          since the theme is unknown during static prerender. */}
      <Sun className="dark:hidden" />
      <Moon className="hidden dark:block" />
    </Button>
  )
}

// Placeholder until auth exists; the app is single-user today.
function UserMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="حساب کاربری">
          <CircleUser />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuLabel>مدیر فروشگاه</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings">
            <Settings />
            تنظیمات
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem disabled>
          <LogOut />
          خروج
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function TopBar() {
  const pathname = usePathname()
  const title = findNavItem(pathname)?.title ?? ""
  const crumb = useTopBarCrumb()

  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-4 backdrop-blur">
      <SidebarTrigger className="-ms-1" />
      <Separator orientation="vertical" className="me-1 h-4 data-vertical:self-center" />
      {crumb ? (
        <>
          {/* Mobile: back chevron + title. Desktop: «parent ‹ title». Chevrons
              are chosen per direction in RTL, not mirrored (design-system §1). */}
          <Link
            href={crumb.parentHref}
            aria-label={crumb.parentLabel}
            className="-ms-1 flex size-8 items-center justify-center rounded-md hover:bg-muted md:hidden"
          >
            <ChevronRight className="size-5" />
          </Link>
          <nav aria-label="مسیر" className="flex min-w-0 items-center gap-1.5">
            <Link
              href={crumb.parentHref}
              className="hidden text-sm text-muted-foreground hover:text-foreground md:inline"
            >
              {crumb.parentLabel}
            </Link>
            <ChevronLeft className="hidden size-3.5 text-muted-foreground md:block" aria-hidden />
            <h1 dir="ltr" className="truncate font-mono text-base font-semibold">
              {crumb.title}
            </h1>
          </nav>
        </>
      ) : (
        <h1 className="text-base font-semibold">{title}</h1>
      )}
      <div className="ms-auto flex items-center gap-1">
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  )
}
