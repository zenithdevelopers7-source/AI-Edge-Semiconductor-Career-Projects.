# Synthetic maintenance documentation exercises

An independently approved maintenance plan can now lead to a saved documentation exercise. This prepares notes, evidence-reference handling and independent review before hardware commissioning. It does not implement technician dispatch, physical execution, machine isolation, permits, repair verification or operational closure.

## Workflow

1. The plan creator explicitly selects **Prepare documentation exercise** from the current approved plan. No records are seeded and no field job is issued. Only one exercise can be created for each approved plan revision; exact retries return the existing record.
2. The exercise retains an immutable snapshot of the approved plan, its approval references and any captured source incident context. The initial record is a draft and makes no physical-work claim.
3. The creator records synthetic work notes, a synthetic outcome and declared evidence-reference text. An outcome and nonblank references are required before submission.
4. A different local administrator reviews the submitted exercise and accepts or rejects the documentation, with a reason. The creator cannot review their own exercise, including when their account is an administrator. The state named `verified` means the synthetic documentation exercise was reviewed; it never establishes verified physical work.
5. The creator can withdraw a submitted exercise. Editing a rejected or reviewed exercise returns it to draft, clears its previous reviewer/decision and retains earlier notes/references in history. Submission freezes editing until withdrawal or review.

Exercise and plan states remain separate. Reviewing an exercise does not resolve the source incident, approve a changed plan, authorize equipment work or qualify a production release.

## Plan revisions and visibility

Creating, editing, submitting and reviewing an exercise require the captured approved plan revision to remain current and approved. A later plan edit makes the earlier exercise historical, even if it was reviewed. Its frozen snapshot and history are retained; no evidence is silently moved to another revision. Withdrawal remains available to the creator for a stale submitted record. After the revised plan is independently approved, its creator may prepare a new exercise for that new approved revision.

Incident context remains the context already captured in the plan. Later incident changes do not rewrite that snapshot. Exercise review concerns only the submitted synthetic documentation and its captured planning context.

Operators can view their own exercises, create them only for their own approved plans and edit/submit/withdraw their own records. Administrators can read all local records and independently review another creator's submitted exercise, but cannot rewrite another creator's notes. Auditors can read/export all local records and have no write permission. Authentication, CSRF, role and session revocation are checked inside serialized write transactions. This is the existing single local workspace, not production multi-tenant authorization.

## Evidence, history and recovery

Notes and reference strings are recorded as declarations; no file upload, independent document authentication, calibration acceptance or physical inspection is implemented. Text is escaped when displayed. Each event records the actor, time, explanation and a snapshot of notes/outcome/references. Earlier contents can be inspected in history and are included in export. Database administrators still control SQLite; the journal is not tamper-proof.

State change, history and audit share one transaction. Audit failure rolls back the change. Expected revisions reject stale/concurrent writes. Limits are 50 exercises per plan and 100 revisions per exercise, with no automatic deletion. Plan details return compact exercise summaries; full bounded notes/history are loaded explicitly. Diagnostics count the two new tables, and the existing verified backup/restore tool preserves them while revoking restored sessions.

## API and permanent boundaries

- `POST /api/maintenance-requests/{id}/exercises`: `expected_plan_revision` only.
- `GET /api/maintenance-exercises/{id}`: current record, captured approved plan and history.
- `PUT /api/maintenance-exercises/{id}`: `expected_revision`, `work_note`, `outcome`, `evidence_refs`.
- `POST /api/maintenance-exercises/{id}/actions`: `expected_revision`, `action` (`submit`, `withdraw`, `verify`, `reject`) and `note`.

Unknown fields and physical-work claims are rejected. Every exercise response declares the synthetic scope and `hardware_connected: false`, `equipment_authorized: false`, `execution_enabled: false`, `physical_work_verified: false` and `production_ready: false`, including after documentation review.

Ten API checks cover approved-plan/creator gates, duplicate creation, independent review, source-plan invalidation, edit invalidation, input/evidence/CSRF/session permissions, bounded history, audit rollback and real disposable backup/restore. Chromium checks cover the complete documentation flow, escaped notes, concurrent conflicts with preserved explanations, export, auditor controls, plan-change guards, outage behavior, contrast and five widths. All checks use disposable synthetic stores and no physical device.

The same 30 selected products and existing firmware pins remain unchanged. Exact received-part inspection, real acquisition, measured ingestion, qualified work execution and independent physical acceptance remain pending.


## In-app planning and exercise draft protection

Planning creation/editing, planning decisions, exercise note editing and exercise decisions now track meaningful changes against their populated form values. A notice identifies the affected editor without copying its contents. Opening a prefilled editor or entering only surrounding whitespace does not invent a draft. Failed/stale saves preserve the existing editor baseline and typed values; successful saves establish a fresh saved view.

Close and Escape ask before dismissing a dirty maintenance editor. Keep editing is the default and Escape on the warning also keeps the editor. The warning is a separate native modal above the existing planning dialog, with focus containment and responsive buttons. Explicit Discard and continue performs the pending action. Planning record/history/editor changes and exercise record/editor/decision changes use the same guard. The shared workspace Escape shortcut cannot bypass it. A warning names the form, never its note/reference contents.

Copying the existing session scratchpad over an already changed planning observation/asset also asks first. Cancelling preserves the form; an accepted copy retains the original baseline so the copied material remains visibly unsaved. The scratchpad's existing session storage behavior is unchanged. Other planning fields are not reset by import. Ordinary saving still requires its explicit submit action and normal browser/server validation. No draft is autosaved, submitted, approved, sent or written to another account by a navigation decision.

A pending discard decision belongs to the currently rendered view. If an in-flight save succeeds and replaces that view, the older pending close/switch is cancelled so it cannot dismiss the successful result or a newer form. Existing saved-action revision, role/session/CSRF, scope, independent-review and equipment boundaries are unchanged. Discarding local notes does not alter a saved record or review decision. Read-only record/history/context and auditor views do not prompt.

This is in-app protection for supported editor entry/close actions, not browser autosave or recovery. Browser reload/tab closure, sign-in redirects, already in-flight operations and arbitrary programmatic DOM/dialog replacement are outside its protection. Notes remain in the current page until saved, explicitly discarded or the page is left. Queue refreshes that retain an editor do not replace its draft. Finish or copy important notes before reloading the browser.

A dedicated disposable Chromium suite covers all four form categories; clean/prefilled/whitespace exclusions; default Keep editing, Escape and nested modal focus; close and record/history/editor switches; scratchpad overwrite cancellation/acceptance; explicit saves and outage input retention; a successful in-flight save invalidating an older close; auditor/read-only exclusions; no navigation-created records; keyboard, contrast and five widths. Existing maintenance/exercise suites explicitly choose discard only when deliberately leaving the stale notes they just verified. No endpoint, schema, fixture account/record, device command or hardware change is installed by this feature.


## Maintenance workbench navigation and local history filters

Saved maintenance details now provide section shortcuts for Overview, Exercises, Inspection proposal, Review actions and History. Incident-linked plans additionally show Captured incident, and that shortcut opens the existing frozen-context disclosure. Each keyboard-accessible shortcut scrolls within the planning dialog and transfers focus to a labelled section; the sticky shortcut bar accounts for the dialog inset so its targets remain visible. Current plan status/revision and reviewed revision stay in Overview. Existing editing, independent review, exercise and source-navigation controls remain in their respective sections with the same service permissions and draft guard.

History can be filtered locally by recorded change type, recorded account and literal case-insensitive text in revision/action/account/reason/time metadata, then sorted oldest or newest first. Combined filters show an explicit empty state and count. Clear history filters restores the full timeline and focuses the search field. Actor/type selectors contain only values already recorded in this authorized history. Filtering and section navigation do not fetch extra source records, change saved decisions, add notes or create draft warnings. Expanded frozen captures remain in place because the viewer does not rebuild them when filtering.

Inspect saved revision still opens the complete existing read-only revision response, independently of the current timeline filters. Returning to the latest request performs its normal authorized read and starts with fresh default history filters. Historical inspection is not presented as current approval and exposes no current write controls. Source-free manual plans have no invented captured-incident destination. Auditors can navigate/filter their authorized context; another operator's private plan and service failures expose no stale workbench.

A dedicated disposable Chromium suite checks five/six section destinations, keyboard focus and unobscured targets at five widths, change/account/literal/combined/empty/reset/order filters, retained expanded source context, exact saved-revision inspection, current approval and snapshot preservation, read-only/private-plan and unsaved-draft boundaries, a 200-event presentation fixture, outage clearing, contrast, and zero presentation-triggered service reads or domain mutations. This interface introduces no endpoint, schema, hardware part, approval rule or equipment authority.


## Read-only saved planning revision comparison

Open a saved plan, go to History and expand Compare saved plan revisions. Select two different revisions and choose Compare saved revisions. The oldest/latest recorded revisions are the presentation defaults; no snapshots are fetched until the explicit request. Plans with only one saved revision explain why no comparison is available. Timeline filters do not shorten the comparison's revision choices.

Both reads use the existing authorized read-only revision API. The interface checks plan identity, exact requested revision, snapshot status and expected field types before showing any pair. Six saved fields are compared exactly as recorded: asset, title, priority, observation, proposal and evidence references. Paired cards label Changed or Unchanged and preserve empty values, line breaks and escaped text. Reversed selections retain their A/B direction. The optional changed-fields filter alters presentation only.

Each side separately shows its saved status, bound reviewed revision, recorded reviewer and saved update time. A submission or approval can change these without changing the six planning fields; that is not invented as a content difference. Cleared/null review bindings are distinct from older review metadata that was never recorded. Historical approval is not current approval or an authorization to execute equipment work. Reload the plan through its existing flow to verify current saved state.

The separate JSON download retains both exact authorized saved snapshots and all six field comparisons even when unchanged cards are hidden. It identifies the selected plan/revisions, browser generation time, historical/read-only scope and false approval/equipment/execution/hardware/production/live-integrity-verification flags. The export contains recorded text, not a signed acceptance artifact or independently verified evidence. Current source-incident metadata returned alongside the historical API response is not mixed into this planning-field comparison. Source captures and exercises remain inspectable in their own existing sections.

Changing either revision clears old cards and export authority immediately. Same-revision choices disable comparison/export. Pending comparisons prevent duplicate submission; changing selections or switching/closing the plan invalidates late replies. A failed, unavailable, mismatched or malformed read produces no partial comparison and leaves export disabled until both authorized snapshots are verified again. Authentication expiry retains the existing sign-in redirect, outside in-app draft protection. Auditors can inspect/export their authorized revisions without write controls; private plans remain outside unrelated operator scope. The comparison issues no domain writes, changes no review/history and adds no endpoint or schema.

A disposable Chromium suite covers explicit paired reads and no fetch on opening; six-field exact differences, empty/status-only values, revision-bound review clearing and legacy gaps; reverse/same selections; complete exports despite display filtering; escaped markup and null metadata; partial/mismatched read failures and retry; duplicate/late reply handling across selections/records; auditor/private-plan/authentication boundaries; preserved current approval/history; keyboard, contrast and five widths. No new hardware is selected or connected, and physical/production acceptance remains pending.
