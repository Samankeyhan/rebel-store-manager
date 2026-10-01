# artboards/

The original design source, one file per artboard, exactly as published. These are authoritative: if a screen document and an artboard ever disagree, the artboard is what was reviewed and signed off.

## What these files are

Each `*.dc.html` is a Claude-Design artboard: plain HTML with inline styles, a `{{placeholder}}` templating syntax, and a `<script type="text/x-dc">` block at the bottom holding the real logic (`class Component extends DCLogic { renderVals() { … } }`). That script is where the formulas, the validation messages and the sample data live — it is the most precise statement of behaviour in this whole handoff, and it is ordinary JavaScript, so it can be read and even run.

`rebel.css` is the shared stylesheet (identical to `../tokens.css`); `canvas.json` is the board index (titles, pages, positions) and is only useful for knowing which artboard belonged to which page.

## Reading them locally

- Images and the font resolve to `../assets/`, so they render when you open a file in a browser from inside this folder.
- `./support.js` is the canvas runtime and is **not** included. Without it the `{{…}}` holes stay unsubstituted and nothing is interactive — that is expected. Read the markup and the script; do not try to run the page.
- The interactive states are separate files, suffixed with the state: `RecordSale-Validation.dc.html`, `OrderDetail-Refund.dc.html`, `Adjustments-Over.dc.html`, and so on. `-Dark` files are the dark theme. `…Mobile*.dc.html` are the 390px layouts.
- **Those suffixed files are thin wrappers** (usually under 1 KB): they `<dc-import>` the main artboard and set its props, e.g. `RecordSale-Validation.dc.html` is `RecordSale` with `preset="errors"`. The markup and logic you want are always in the unsuffixed file — `RecordSale.dc.html`, `Adjustments.dc.html`, `Reports.dc.html` — whose `preset` / `theme` / `tab` props enumerate every state that was designed. A `-States` wrapper holds the empty, loading and error boards for that screen side by side.
- Some artboards are generated from macros (`[[HEAD:]]`, `[[i:icon:size:flip]]`, `[[PAGE:…]]`, `[[STATES:…]]`) that are already expanded here, so what you see is the final markup.

## Component boundaries

`Sidebar.dc.html`, `Topbar.dc.html` and `MobileBar.dc.html` are the shell components every other artboard imports via `<dc-import name="…">`. Everything else is a page.
