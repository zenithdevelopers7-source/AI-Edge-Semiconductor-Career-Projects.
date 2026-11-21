# Administrator-managed local accounts

Settings now includes **Accounts for independent review**, visible only to an authenticated administrator. This allows separate local accounts for the existing review workflows without database edits. No account, password, invitation or approval is created by installing this feature.

## Supported workflow

An administrator can create a local account with an email-form username, a selected role, an initial password of 14–256 characters (not entirely whitespace), a reason and their own current password. The browser asks for the initial password twice. Passwords are not trimmed, returned, displayed in history or stored in plaintext. The existing salted password-hashing function is used. Creation does not send email or establish that the named person or email owner was verified. Administrators must manage initial credential handover outside this application.

The supported local roles are:

| Role | Local capabilities |
| --- | --- |
| Administrator | Manage local account access, read local domain records and independently review another creator's submissions |
| Operator | Create own records and handle explicitly assigned incidents; planning and documentation-exercise records remain creator-scoped |
| Auditor | Read/export existing domain records under the existing read scopes; no writes and no team-management access |

No role enables physical equipment operation, real device enrollment or production acceptance.

Administrators can change role or enable/disable an account. Each action requires their current password, a substantive reason, CSRF and the expected account revision. All target-account sessions are revoked when access changes; self-changes end the current session. Disabling an account prevents sign-in and preserves its authored records and review history. There is no account-delete endpoint. At least one enabled administrator must remain; serialized transactions protect the last active administrator from disable/demotion.

## Explicit password rotation

An administrator can now open an account and select **Change this account's local password**. The administrator enters their current password, the new target-account password twice and a reason. The new password must be different from the existing one, 14–256 characters and not entirely whitespace; valid leading/trailing whitespace is preserved. Password confirmation is a browser check; the server independently validates the submitted password and authorization. Existing hashes cannot be retrieved.

The password hash update, shared account-revision increment, session revocation, management history and audit commit in one transaction. Audit failure retains the earlier password and sessions. Role and enabled/disabled state are unchanged; changing a disabled account's password does not enable it. Rotating the administrator's own password ends their session, including when they are the last active administrator; they must sign in with the new password.

Password changes use the same expected-revision, administrator reauthentication, denial/rate-limit and history-capacity rules as access changes. Competing role/access/password changes cannot silently overwrite each other. No email, password-recovery link, identity proof or second factor is issued. Non-administrators cannot call this administrative route, even for their own account. Their self-service password change and unauthenticated recovery remain separate future work.

Sign-in now rechecks the current password hash and enabled state under the session-issuance write lock after the expensive password check. An in-flight check of an old password cannot create a fresh authorized session after rotation. If sign-in commits first, rotation revokes that session in its own transaction.

The browser clears password fields after attempts and redirects after confirmed self-rotation. If the result is uncertain because the response was lost, verify sign-in with the new password and inspect account history/revision before another change; the application does not retry a credential write automatically. A successful other-account rotation does not reveal or retain the chosen password for handover.

Nine additional API checks cover old/new login behavior, self-rotation, role/CSRF/password checks, competing changes, rollback, disabled-state and whitespace preservation, current-session/denial limits, actual backup/restore and the in-flight old-password regression. Chromium checks confirmation, reauthentication, cleared fields, session revocation, history, old/new credentials, self-rotation sign-in, outage handling, contrast and five widths. These checks rotate disposable fixture credentials only.

## Credential and transaction boundaries

Current session, revocation and administrator role are checked again inside each write transaction. Administrator password failures are recorded without the attempted secret and limited to five failures per administrator in a 15-minute window. Denial records and their sanitized audit event persist even when the request is refused. A successfully committed account action clears that administrator's failure count. A rate-limited administrator must wait for the window to expire.

Role/access change, metadata history, session revocation and audit commit together. An audit failure rolls the account change back. Duplicate usernames are rejected without changing an existing password; a response-loss retry never silently resets credentials. If creation's result is uncertain, refresh the list and inspect the account before retrying.

The browser clears password fields after requests, on refresh and when the document becomes hidden. It does not save them in browser storage. Reason text is retained for rejected changes where possible; keep secrets out of reasons and other free-text fields. Existing hashes cannot be read through this API. A session or role error clears the displayed account controls on refresh. Changes are revision-checked; concurrent updates are rejected.

## History and recovery

New accounts start at metadata revision 1 with a creation event. Existing accounts are presented with baseline revision 1 and no invented creation date/history; their first managed change records revision 2. No existing password, role or access flag is rewritten during installation. Account metadata/history and reauthentication-denial tables are included in service diagnostics and the existing verified database backup/restore workflow. Restoring revokes sessions as before.

Limits are 100 local accounts and 200 managed revisions per account; capacity limits retain existing records and reject further creation/changes. Disabled accounts count toward the local account limit. Lists are paginated (maximum 50 per page). SQLite administrators can still alter local data; application history is not a tamper-proof identity service.

## API and remaining identity work

- `GET /api/team?q=&offset=0&limit=25`: administrator-only bounded metadata list.
- `GET /api/team/{id}`: administrator-only metadata and management history.
- `POST /api/team`: explicit local account creation.
- `POST /api/team/{id}`: role/access change with revision, reason and current administrator password.
- `POST /api/team/{id}/password`: explicit administrator-controlled password rotation with the expected account revision, new password, reason and current administrator password.

Every response declares local scope and false invitation, identity-verification, hardware, equipment-authorization and production-readiness flags. Self-service password change, unauthenticated recovery, verified invitations, enterprise identity/MFA, identity lifecycle integration, distributed abuse protection, approved TLS deployment and emergency recovery remain pending. Changing a role does not retroactively rewrite earlier authorship or prove a reviewer's professional qualification. A demoted administrator retains captured context in their own plans, but source links hide current incident metadata outside their new operator scope.

Eleven API checks cover hashing/no secret responses, login, roles/CSRF/session revocation, password-denial persistence/rate limiting, last-admin protection, concurrent edits, demotion-safe source links, duplicate usernames, self-demotion, retained authorship, capacity, audit rollback and actual disposable backup/restore. Chromium covers explicit creation/sign-in, cleared password fields, last-admin protection, role-change revocation, history, non-admin visibility, outage/retry, contrast and five widths. Tests use disposable accounts only.
