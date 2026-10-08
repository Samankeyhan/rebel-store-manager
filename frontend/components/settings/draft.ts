/**
 * The settings screen edits a local draft and saves it in one go. The API has
 * no batch endpoint, so a save is a sequence of calls: PUT /settings/{key} for
 * each changed global setting, then one PATCH /settings/channels/{channel}
 * per changed channel carrying only that channel's changed fields. Each
 * response becomes the new baseline, so whatever saved stops being dirty; the
 * first failure stops the run and the rest stays in the draft for a retry.
 */

import {
  ApiError,
  updateChannelSettings,
  updateSetting,
  type ChannelSettings,
  type GlobalSettingKey,
  type Settings,
} from "@/lib/api"
import { CHANNEL_IDS, CHANNELS, type Channel } from "@/components/record-sale/copy"
import { M, moneyInputMessage } from "@/components/common/copy"
import type { MoneyInputError } from "@/lib/money"
import { S } from "./copy"

/** The kit picker's value for "no packaging" (same sentinel as Packaging's deactivate dialog). */
export const NONE = "none"

export const kitChoice = (id: number | null): string => (id == null ? NONE : String(id))
export const kitIdOf = (choice: string): number | null => (choice === NONE ? null : Number(choice))

export const WINDOW_MAX = 12

/** The channel's default payment method picker value: NONE («بدون روش») or a method id. */
export const methodChoice = (id: number | null): string => (id == null ? NONE : String(id))
export const methodIdOf = (choice: string): number | null => (choice === NONE ? null : Number(choice))

export type ChannelDraft = { applies_shipping_charge: number; applies_postage: number; kit: string; method: string }

export type MoneyKey = "default_shipping_charge" | "default_postage_estimate"

/**
 * The money keys are integer Rial, or null while MoneyInput holds text that
 * gives no exact amount (blocks save); `moneyErrors` keeps MoneyInput's reason
 * for each null one, so validation reports the field's own message.
 */
export type Draft = {
  default_shipping_charge: number | null
  postage_estimate_window: number
  default_postage_estimate: number | null
  channels: Record<Channel, ChannelDraft>
  moneyErrors: Partial<Record<MoneyKey, MoneyInputError>>
}

/** The message for a money key that holds no exact amount: MoneyInput's own reason. */
const notExact = (draft: Draft, key: MoneyKey) => {
  const error = draft.moneyErrors[key]
  return error ? moneyInputMessage(error) : M.reenter
}

const GLOBAL_KEYS: GlobalSettingKey[] = ["default_shipping_charge", "postage_estimate_window", "default_postage_estimate"]

const GLOBAL_LABELS: Record<GlobalSettingKey, string> = {
  default_shipping_charge: S.chShipping,
  postage_estimate_window: S.chWindow,
  default_postage_estimate: S.chDefaultPost,
}

const channelName = (c: Channel) => CHANNELS[c].name

function channelDraft(c: ChannelSettings | undefined): ChannelDraft {
  return {
    applies_shipping_charge: c?.applies_shipping_charge ?? 0,
    applies_postage: c?.applies_postage ?? 0,
    kit: kitChoice(c?.default_packaging_kit_id ?? null),
    method: methodChoice(c?.default_payment_method_id ?? null),
  }
}

export function fromSettings(s: Settings): Draft {
  return {
    default_shipping_charge: s.default_shipping_charge,
    postage_estimate_window: s.postage_estimate_window,
    default_postage_estimate: s.default_postage_estimate,
    channels: Object.fromEntries(CHANNEL_IDS.map((c) => [c, channelDraft(s.channels[c])])) as Record<Channel, ChannelDraft>,
    moneyErrors: {},
  }
}

export type ChannelPatch = {
  applies_shipping_charge?: number
  applies_postage?: number
  default_packaging_kit_id?: number | null
  default_payment_method_id?: number | null
}

/** Only the fields that differ, ready for PATCH (null = no packaging / no payment method). */
export function channelPatch(saved: ChannelSettings | undefined, draft: ChannelDraft): ChannelPatch {
  const base = channelDraft(saved)
  const patch: ChannelPatch = {}
  if (draft.applies_shipping_charge !== base.applies_shipping_charge) patch.applies_shipping_charge = draft.applies_shipping_charge
  if (draft.applies_postage !== base.applies_postage) patch.applies_postage = draft.applies_postage
  if (draft.kit !== base.kit) patch.default_packaging_kit_id = kitIdOf(draft.kit)
  if (draft.method !== base.method) patch.default_payment_method_id = methodIdOf(draft.method)
  return patch
}

function patchLabels(channel: Channel, patch: ChannelPatch): string[] {
  const name = channelName(channel)
  const labels: string[] = []
  if ("applies_shipping_charge" in patch) labels.push(S.chChannelShipping(name))
  if ("applies_postage" in patch) labels.push(S.chChannelPostage(name))
  if ("default_packaging_kit_id" in patch) labels.push(S.chChannelKit(name))
  if ("default_payment_method_id" in patch) labels.push(S.chChannelMethod(name))
  return labels
}

/** Labels of everything the draft changes, in save order. */
export function changes(baseline: Settings, draft: Draft): string[] {
  const labels = GLOBAL_KEYS.filter((k) => draft[k] !== baseline[k]).map((k) => GLOBAL_LABELS[k])
  for (const c of CHANNEL_IDS) labels.push(...patchLabels(c, channelPatch(baseline.channels[c], draft.channels[c])))
  return labels
}

/** Client-side checks mirroring db/settings.py's _validate_setting_value. */
export function validate(draft: Draft): Partial<Record<GlobalSettingKey, string>> {
  const errors: Partial<Record<GlobalSettingKey, string>> = {}
  for (const key of ["default_shipping_charge", "default_postage_estimate"] as const) {
    const v = draft[key]
    if (v === null) errors[key] = notExact(draft, key)
    else if (!Number.isSafeInteger(v) || v < 0) errors[key] = S.amountError
  }
  const n = draft.postage_estimate_window
  if (!Number.isInteger(n) || n < 1) errors.postage_estimate_window = S.windowError
  return errors
}

export type SaveFailure = {
  /** What failed, as shown to the user. */
  label: string
  error: ApiError | Error
  /** The global key whose PUT failed, to mark its field. */
  key: GlobalSettingKey | null
  /** A kit choice was part of the failed PATCH (e.g. the kit was deactivated meanwhile). */
  kitChanged: boolean
  /** A payment-method choice was part of the failed PATCH (e.g. the method was deactivated meanwhile). */
  methodChanged: boolean
}

export type SaveResult = {
  /** The new baseline: the server's state after every call that succeeded. */
  settings: Settings
  saved: string[]
  /** Whether a global setting was saved (the postage estimate may have moved). */
  savedGlobal: boolean
  failure: SaveFailure | null
}

export async function saveDraft(baseline: Settings, draft: Draft): Promise<SaveResult> {
  let current = baseline
  const saved: string[] = []
  let savedGlobal = false
  const fail = (failure: SaveFailure): SaveResult => ({ settings: current, saved, savedGlobal, failure })
  const asError = (e: unknown) => (e instanceof Error ? e : new Error(String(e)))

  for (const key of GLOBAL_KEYS) {
    const value = draft[key]
    if (value === current[key]) continue
    // validate() refuses a null amount, so save() never gets here with one.
    if (value === null) {
      const message = key === "postage_estimate_window" ? M.reenter : notExact(draft, key)
      return fail({ label: GLOBAL_LABELS[key], error: new Error(message), key, kitChanged: false, methodChanged: false })
    }
    try {
      current = await updateSetting(key, value)
      saved.push(GLOBAL_LABELS[key])
      savedGlobal = true
    } catch (e) {
      return fail({ label: GLOBAL_LABELS[key], error: asError(e), key, kitChanged: false, methodChanged: false })
    }
  }

  for (const channel of CHANNEL_IDS) {
    const patch = channelPatch(current.channels[channel], draft.channels[channel])
    const labels = patchLabels(channel, patch)
    if (labels.length === 0) continue
    try {
      const updated = await updateChannelSettings(channel, patch)
      current = { ...current, channels: { ...current.channels, [channel]: updated } }
      saved.push(...labels)
    } catch (e) {
      return fail({
        label: labels.length === 1 ? labels[0] : S.chChannel(channelName(channel)),
        error: asError(e),
        key: null,
        kitChanged: "default_packaging_kit_id" in patch,
        methodChanged: "default_payment_method_id" in patch,
      })
    }
  }

  return { settings: current, saved, savedGlobal, failure: null }
}
