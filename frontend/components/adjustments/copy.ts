import { formatQuantity } from "@/lib/persian-numbers"
import { currencyLabel, formatMoney, formatMoneyNumber } from "@/lib/money"

/** Screen 10 copy (design/screens/10-stock-adjustments.md §2). `// NEW` = not in the design. */
export const A = {
  // Kind
  fieldKind: "نوع تعدیل",
  waste: "ضایعات",
  wasteSub1: "همیشه موجودی را کم می‌کند",
  wasteSub2: "زیان واقعی است و در سود و زیان می‌آید",
  correction: "اصلاح موجودی",
  correctionSub1: "شمارش انبار با سیستم نمی‌خواند (+ یا −)",
  correctionSub2: "فقط شمارش را درست می‌کند و در سود و زیان نمی‌آید",
  kindHelpMobileWaste: "ضایعات",
  kindHelpMobileMid: " زیان واقعی است و در سود و زیان می‌آید (به بهای تمام‌شده همان روز). ",
  kindHelpMobileCorrection: "اصلاح موجودی",
  kindHelpMobileEnd: " فقط شمارش را درست می‌کند و در سود و زیان نمی‌آید.",

  // Form
  formTitle: "ثبت تعدیل",
  fieldItemType: "نوع کالا", // NEW
  segProduct: "محصول", // NEW
  segMaterial: "متریال", // NEW
  fieldItem: "کالا",
  pickItem: "انتخاب کالا", // NEW
  searchItem: "جستجوی کالا", // NEW
  noItems: "کالای فعالی برای تعدیل نیست.", // NEW
  noItemMatch: (q: string) => `کالایی با «${q}» پیدا نشد.`, // NEW
  stockPill: (q: string, unit: string) => `موجودی ${q} ${unit}`,
  itemMeta: (kind: string, stock: string, unit: string, cost: number | null) =>
    `${kind} · موجودی ${stock} ${unit} · ${cost == null ? "بهای واحد ثبت نشده" : `بهای واحد ${formatMoney(cost)}`}`,
  itemMetaMobile: (kind: string, stock: string, unit: string) => `${kind} · موجودی ${stock} ${unit}`,
  itemRequired: "کالا را انتخاب کنید.", // NEW
  // Waste of a service (a SERVICE material: a cost but no stock)
  serviceTag: "خدمت", // NEW
  servicePill: (cost: number | null) => (cost == null || cost < 1 ? "بها ثبت نشده" : `بهای واحد ${formatMoney(cost)}`), // NEW
  itemMetaService: (cost: number | null) =>
    `متریال (خدمت) · بدون موجودی · ${cost == null || cost < 1 ? "بهای واحد ثبت نشده" : `بهای واحد ${formatMoney(cost)}`}`, // NEW
  fieldServiceQty: "تعداد واحد ضایع‌شده", // NEW
  qtyHelpService: "اعشار مجاز است (مثلاً ۰٫۵)؛ خدمت موجودی ندارد.", // NEW
  fieldServicePrice: "بهای هر واحد", // NEW
  servicePriceHelp: (cost: number) => `پیش‌فرض بهای فعلی (${formatMoney(cost)}) است؛ اگر عوضش کنید، همین بها با این ردیف ذخیره می‌شود.`, // NEW
  servicePriceEdited: "این بها فقط برای همین ردیف ذخیره می‌شود؛ بهای خود متریال عوض نمی‌شود.", // NEW
  servicePriceRequired: "بهای هر واحد را وارد کنید (بیشتر از صفر).", // NEW
  serviceNoCost: (name: string) => `بهای «${name}» هنوز ثبت نشده؛ ضایعات خدمت فقط با بهای ثبت‌شده ممکن است.`, // NEW
  serviceNoCostLink: "ثبت بها", // NEW
  serviceAmountLabel: "مبلغ ضایعات = تعداد × بهای هر واحد (پیش‌نمایش)", // NEW
  serviceNoStock: "موجودی تغییر نمی‌کند", // NEW
  serviceBadge: "ضایعات خدمت", // NEW
  dateFuture: "تاریخ نمی‌تواند در آینده باشد.", // NEW
  fieldDir: "جهت",
  dirPlus: "افزایش",
  dirMinus: "کاهش",
  fieldQty: "مقدار",
  qtyHelpProduct: "محصول: فقط عدد صحیح",
  qtyHelpMaterial: "متریال: اعشار مجاز است (مثلاً ۰٫۵)",
  fieldCost: "بهای واحد موجودی اضافه‌شده",
  costHelp: (cost: number | null) =>
    cost == null
      ? "خالی بماند = بهای واحد ثبت‌نشده می‌ماند. اگر وارد شود، بهای واحد این کالا می‌شود." // NEW
      : `خالی بماند = بهای فعلی (${formatMoney(cost)}). اگر وارد شود، میانگین موزون به‌روز می‌شود.`,
  costZeroMaterial: "بهای این متریال ثبت نشده (۰) است؛ بدون وارد کردن بها، بهای آن صفر می‌ماند.", // NEW
  costPrefilled: "بها از دستور تولید پر شده (برآورد)؛ قابل ویرایش است.", // NEW
  costZero: "صفر یعنی این موجودی رایگان به دست آمده و میانگین بهای واحد را پایین می‌آورد.", // NEW
  get unit() {
    return currencyLabel()
  },
  /** A signed value: «+۱۲٬۰۰۰ تومان». The signed number is LTR-isolated so «+»/«−» stay on its left; the unit follows in the RTL text. */
  signedValue: (rial: number) => `⁦${rial > 0 ? "+" : ""}${formatMoneyNumber(rial)}⁩ ${currencyLabel()}`, // NEW
  fieldDate: "تاریخ تعدیل", // NEW
  today: "امروز",
  fieldReason: "دلیل",
  reasonPlaceholder: "مثلاً پارگی هنگام بسته‌بندی", // NEW

  // Validation (§4)
  qtyRequired: "مقدار را وارد کنید.",
  qtyFraction: "تعداد محصول باید عدد صحیح باشد؛ فقط متریال‌ها می‌توانند اعشاری باشند.",
  qtyOver: (stock: number, unit: string, name: string) =>
    `بیشتر از موجودی فعلی است — فقط ${formatQuantity(stock)} ${unit} «${name}» موجود است.`,
  qtyZeroStock: (name: string) => `موجودی «${name}» صفر است؛ کاهش ممکن نیست.`, // NEW
  serverShort: (available: number, unit: string, name: string) =>
    `موجودی «${name}» در این فاصله تغییر کرده؛ اکنون فقط ${formatQuantity(available)} ${unit} موجود است.`, // NEW

  // Preview
  previewTitle: "پیش‌نمایش",
  badgeWaste: "ضایعات",
  badgePlus: "اصلاح +",
  badgeMinus: "اصلاح −",
  before: "موجودی فعلی",
  after: "پس از ثبت",
  valueWaste: "زیان ضایعات (در سود و زیان)",
  valuePlus: "افزایش ارزش موجودی (بدون اثر در سود و زیان)",
  valueMinus: "کاهش ارزش موجودی (بدون اثر در سود و زیان)",
  avgLabel: "میانگین بهای واحد",
  noCost: "ثبت نشده", // NEW
  noCostWaste: "بهای واحد این کالا ثبت نشده؛ این ضایعات با ارزش صفر در سود و زیان می‌آید.", // NEW
  pickToPreview: "کالا را انتخاب کنید تا اثر تعدیل را ببینید.", // NEW
  noteWaste:
    "ضایعات زیان واقعی است و در سود و زیان می‌آید — در ردیف «ضایعات». ارزش آن با بهای تمام‌شده همین امروز ثبت و ذخیره می‌شود و با تغییر بعدی بهای تمام‌شده عوض نمی‌شود.",
  noteService:
    "ضایعات خدمت هم مثل ضایعات دیگر زیان واقعی است و در سود و زیان، در ردیف «ضایعات» می‌آید؛ موجودی تغییر نمی‌کند. مبلغ = تعداد × بهای هر واحدی که همراه همین ردیف ذخیره می‌شود و با تغییر بعدی بها عوض نمی‌شود.", // NEW
  noteCorrection:
    "اصلاح موجودی فقط شمارش را درست می‌کند و در سود و زیان نمی‌آید؛ فقط موجودی و ارزش انبار تغییر می‌کند.",
  submit: "ثبت تعدیل",
  toastSaved: (name: string) => `تعدیل «${name}» ثبت شد`, // NEW
  close: "بستن",

  // History
  historyTitle: "تاریخچه تعدیل‌ها",
  filterAll: "همه",
  filterWaste: "ضایعات",
  filterCorrection: "اصلاح",
  filterKindLabel: "نوع تعدیل",
  itemPrefix: "کالا:",
  itemAll: "همه",
  itemAllProducts: "همه محصولات", // NEW
  itemAllMaterials: "همه متریال‌ها", // NEW
  groupProducts: "محصولات", // NEW
  groupMaterials: "متریال‌ها", // NEW
  colDate: "تاریخ",
  colItem: "کالا",
  colKind: "نوع",
  colQty: "مقدار",
  get colValue() {
    return `ارزش (${currencyLabel()})`
  },
  colPnl: "اثر در سود و زیان",
  colReason: "دلیل",
  pnlWaste: "ردیف ضایعات",
  pnlNone: "بدون اثر",
  tagProduct: "محصول", // NEW
  tagMaterial: "متریال", // NEW
  footnote:
    "فقط ردیف‌های «ضایعات» به گزارش سود و زیان می‌روند و با بهای تمام‌شده همان روز ارزش‌گذاری می‌شوند. «اصلاح موجودی» هیچ‌وقت در سود و زیان نمی‌آید.",
  footnoteValue: "ارزش هر ردیف = مقدار × بهای واحدی که همراه همان ردیف ذخیره شده است.", // NEW
  recent: "اخیر",
  recentMeta: (date: string, kind: string, qty: string) => `${date} · ${kind} ${qty}`,
  recentNoPnl: "بدون اثر در سود و زیان",

  // States
  emptyTitle: "هنوز تعدیلی ثبت نشده",
  emptyBody:
    "وقتی کالا خراب می‌شود یا شمارش انبار با سیستم نمی‌خواند، این‌جا ثبت کنید تا موجودی و گزارش‌ها درست بمانند.",
  emptyBodyMobile: "ضایعات و اصلاح شمارش انبار را این‌جا ثبت کنید.",
  emptyCta: "ثبت تعدیل",
  noMatch: "تعدیلی با این فیلترها نیست", // NEW
  clearFilters: "پاک کردن فیلترها", // NEW
  loadingAria: "در حال بارگذاری",
  errorTitle: "تاریخچه تعدیل موجودی بارگذاری نشد",
  errorTitleMobile: "تعدیل‌ها بارگذاری نشد",
  errorBody: "اتصال به سرور برقرار نشد. داده‌های شما سالم است؛ دوباره تلاش کنید.",
  retry: "تلاش دوباره",
} as const
