import {
  Box,
  ChartColumn,
  Factory,
  LayoutDashboard,
  Mail,
  Package,
  ReceiptText,
  Settings,
  ShoppingCart,
  SlidersHorizontal,
  Store,
  Truck,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react"

export type NavItem = { href: string; title: string; icon: LucideIcon }

/** Single source for the sidebar, the top-bar title and the page stubs. */
export const NAV_ITEMS: NavItem[] = [
  { href: "/", title: "داشبورد", icon: LayoutDashboard },
  { href: "/sales/new", title: "فروش جدید", icon: ShoppingCart },
  { href: "/orders", title: "سفارش‌ها", icon: ReceiptText },
  { href: "/products", title: "محصولات و مواد اولیه", icon: Package },
  { href: "/production", title: "تولید", icon: Factory },
  { href: "/purchases", title: "خریدها", icon: Truck },
  { href: "/packaging", title: "بسته‌بندی", icon: Box },
  { href: "/postage", title: "ارسال پستی", icon: Mail },
  { href: "/adjustments", title: "اصلاح موجودی", icon: SlidersHorizontal },
  { href: "/expenses", title: "هزینه‌ها", icon: Wallet },
  { href: "/reports", title: "گزارش‌ها", icon: ChartColumn },
  { href: "/partners", title: "شرکا", icon: Users },
  { href: "/suppliers", title: "تأمین‌کنندگان", icon: Store },
  { href: "/settings", title: "تنظیمات", icon: Settings },
]

// trailingSlash: true means usePathname() returns "/orders/"; compare without it.
function normalize(path: string): string {
  return path.length > 1 ? path.replace(/\/+$/, "") : path
}

/** The nav item for a pathname: exact match, else the longest prefix match. */
export function findNavItem(pathname: string): NavItem | undefined {
  const path = normalize(pathname)
  return (
    NAV_ITEMS.find((item) => item.href === path) ??
    NAV_ITEMS.filter(
      (item) => item.href !== "/" && path.startsWith(item.href + "/")
    ).sort((a, b) => b.href.length - a.href.length)[0]
  )
}

export function getNavItem(href: string): NavItem {
  const item = NAV_ITEMS.find((i) => i.href === href)
  if (!item) throw new Error(`No nav item for ${href}`)
  return item
}
