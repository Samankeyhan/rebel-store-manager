"use client"

import * as React from "react"
import { ThemeProvider } from "next-themes"
import { Direction } from "radix-ui"
import { TooltipProvider } from "@/components/ui/tooltip"
import { TopBarCrumbProvider } from "@/components/top-bar-crumb"

/**
 * App-wide client providers. DirectionProvider tells Radix primitives the
 * app is RTL (arrow-key order in menus, submenu side); <html dir> alone
 * only affects CSS.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <Direction.DirectionProvider dir="rtl">
        <TooltipProvider>
          <TopBarCrumbProvider>{children}</TopBarCrumbProvider>
        </TooltipProvider>
      </Direction.DirectionProvider>
    </ThemeProvider>
  )
}
