"use client"

import * as React from "react"
import { ThemeProvider } from "next-themes"
import { Direction } from "radix-ui"
import { TooltipProvider } from "@/components/ui/tooltip"
import { TopBarCrumbProvider } from "@/components/top-bar-crumb"
import { CurrencyProvider } from "@/components/currency-provider"

/**
 * App-wide client providers. DirectionProvider tells Radix primitives the
 * app is RTL (arrow-key order in menus, submenu side); <html dir> alone
 * only affects CSS. CurrencyProvider loads the display currency (lib/money.ts).
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
          <CurrencyProvider>
            <TopBarCrumbProvider>{children}</TopBarCrumbProvider>
          </CurrencyProvider>
        </TooltipProvider>
      </Direction.DirectionProvider>
    </ThemeProvider>
  )
}
