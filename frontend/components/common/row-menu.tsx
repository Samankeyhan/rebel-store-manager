"use client"

import { MoreVertical, Pencil, Trash2 } from "lucide-react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Btn } from "@/components/record-sale/primitives"
import { RowActions } from "./copy"

/** The «ویرایش / حذف» menu at the end of a ledger row or card. */
export function RowMenu({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <DropdownMenu dir="rtl" modal={false}>
      <DropdownMenuTrigger asChild>
        <Btn variant="ghost" size="sm" className="size-8 px-0" aria-label={RowActions.menuAria}>
          <MoreVertical className="size-4" />
        </Btn>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-36">
        <DropdownMenuItem onSelect={onEdit}>
          <Pencil className="size-4" />
          {RowActions.edit}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onDelete} className="text-loss">
          <Trash2 className="size-4" />
          {RowActions.remove}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
