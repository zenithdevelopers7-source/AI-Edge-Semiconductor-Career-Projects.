# Operations Desk visual system

The current interface uses a light workspace with deep navy navigation with mint selection, white cards and restrained cobalt/teal accents. `theme.css` supplies semantic status colors; the final `experience.css` layer supplies the current product shell, spacing, typography and responsive component presentation.

| Purpose | Color | Use |
| --- | --- | --- |
| Workspace | `#F2F6FC` | Cool, light background |
| Cards/forms | `#FFFFFF` | Primary reading surfaces |
| Primary text | `#14263E` | Headings, values and record content |
| Secondary text | `#465B74` | Supporting explanations and metadata |
| Navigation | `#10243C` | Deep navy sidebar, bright labels, mint active workspace |
| Primary action | `#245BD6` | Cobalt buttons with white text |
| Teal | `#087B78` | Signal chart and selected accents |
| Success | `#096B51` on `#E5F5ED` | Approved-plan and nominal labels |
| Warning | `#87500A` on `#FFF2DB` | Submitted, pending and planning labels |
| Attention | `#A72B46` on `#FCEAF0` | Rejection, critical and error labels |

Normal labels, table content, fields and controls use dark foregrounds on light surfaces. Secondary metadata remains distinct without relying on pale text. Status names are visible alongside their colors; color is not the only indication of state. Keyboard focus uses an explicit cobalt outline, including in navigation.

Industrial image areas retain dark overlays and light captions. The sign-in introduction remains photographic while its form is light. These image/gradient combinations are visually reviewed separately from the automated solid-background text calculation.

Chart colors have been deepened for light surfaces. Trend and telemetry charts recalculate their SVG coordinate space when resized, preserving readable axis-label size rather than shrinking a fixed-size canvas on mobile. The chart data and measurement units are unchanged.

## Verification

The Chromium workspace suite checks sign-in, all 18 workspaces, asset detail, text/field contrast and responsive navigation at 1440/1024/768/390/320 pixels. The planning suite additionally checks its form and decision-history colors while exercising the real isolated local service. The audit targets a contrast ratio of at least 4.5:1 for normal text and 3:1 for large text, using computed colors with alpha compositing. Disabled controls and image/gradient regions are excluded from that calculation and are not presented as automatically certified.

The suites also check that resized trend/telemetry axis labels render at approximately 12 pixels or more, that dense tables scroll within their containers, and that larger readable labels do not create page-wide horizontal overflow. These checks are focused verification, not an accessibility certification of the entire product.

## Operations Desk interaction layer

`experience.js` adds up to five pinned destinations, real search access, asset inspection and a 53-criterion evidence map. Pins and compact/card presentation preferences use local browser storage. They never change account roles, evidence state or server permissions. The evidence map reads the authenticated register and opens existing criterion details; it does not calculate implementation completion or authorize release. It supports grouped arrow/Home/End keyboard navigation.

The overview places metrics and work queues ahead of the retained guide banner. Existing workflows, source disclosures, counts, report reviews, planning and readiness services remain accessible across all 18 workspaces. All local image captions retain their concept/synthetic provenance.

The readability refinement increases working text and controls to 14px, navigation to 15px semibold and supporting labels to 12–13px where practical. Navigation uses icon tiles, clear section dividers, a mint selected row with dark text, brighter secondary labels and an explicit focus outline. It retains the same 18 destinations and a scrollable mobile drawer.
