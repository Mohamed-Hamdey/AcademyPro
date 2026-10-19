# CRUD Audit — Academy System v2.0

Snapshot as of build v1.0.0 (before Part 3 changes).

Legend:
  ✅ Exists and works
  ⚠️  Partial / has caveats
  ❌ Missing
  🚫 Intentionally missing (should stay missing)

## Players

| Operation | Status | Notes |
|---|---|---|
| Create | ✅ | Form + validation |
| Read (list) | ✅ | With filters, search |
| Read (detail) | ✅ | With subscriptions, attendance, records |
| Update | ✅ | Full edit form |
| Delete | ❌ | No delete, no archive |
| Search by name | ⚠️ | Simple `LIKE`, no Arabic normalization (fixing in 3.2-adjacent) |
| Search by ID | ⚠️ | Only in scan screen, not player list |

**Gaps:** no archive/delete. No Arabic normalization (fixing in current batch). Numeric search in player list (fixing in current batch).

## Subscriptions

| Operation | Status | Notes |
|---|---|---|
| Create (activate) | ✅ | Full form |
| Read | ✅ | Per-player list, dashboards |
| Update plan type | ❌ | Locked after creation |
| Update allowed days | ❌ | Locked after creation |
| Update sessions total | ❌ | Only "adjust remaining" exists |
| Update start date | ❌ | Locked after creation |
| Update expiry date | ⚠️ | Recomputed when a payment is recorded |
| Update activity | ❌ | Locked after creation |
| Suspend | ✅ | Sets status='suspended' |
| Delete | ❌ | No delete, no archive |
| Record additional payment | ✅ | Updates expiry, logs ledger entry |
| Adjust remaining sessions | ✅ | Sets arbitrary value |
| Undo check-in | ✅ | Same-day only, restores 1 session |

**Gaps:** Cannot edit most fields. No delete. This is sub-phase 3.2 + 3.3.

## Activities

| Operation | Status | Notes |
|---|---|---|
| Create | ✅ | Form |
| Read | ✅ | With show-inactive toggle |
| Update | ✅ | Edit form |
| Deactivate | ✅ | Sets active=0 |
| Reactivate | ✅ | Sets active=1 |
| Delete | 🚫 | **Intentionally missing.** Subs + attendance reference activity_id. |
| Archive (stronger than deactivate) | ❌ | Optional future feature |

**Gap:** none urgent.

## Users

| Operation | Status | Notes |
|---|---|---|
| Create | ✅ | Form |
| Read | ✅ | List with avatars |
| Update | ✅ | Form |
| Change password | ✅ | Dialog |
| Deactivate | ✅ | Sets active=0 |
| Reactivate | ✅ | Sets active=1 |
| Delete | ❌ | No delete, no tombstone |
| Search | ⚠️ | Simple LIKE, no debounce (fixing) |

**Gap:** tombstone (sub-phase 3.4A).

## Payments

| Operation | Status | Notes |
|---|---|---|
| Create | ✅ | Via subscription payment, ledger |
| Read | ✅ | Per-player, per-day, per-month |
| Update amount | ❌ | Immutable |
| Update method | ❌ | Immutable |
| Update date | ❌ | Immutable |
| Update notes | ❌ | Immutable |
| Delete | ⚠️ | Repo method exists (`delete`), no UI |
| Correction entries | ❌ | Not implemented |

**Gaps:** no edit, no delete UI (repo `delete` exists but unused), no corrections. Sub-phase 3.4B.

## Expenses

| Operation | Status | Notes |
|---|---|---|
| Create | ✅ | Form |
| Read | ✅ | With month filter, category breakdown |
| Update | ✅ | Full edit |
| Delete | ✅ | With confirmation + audit |
| Search | N/A | Filtered by month only |

**Gap:** none.

## Attendance

| Operation | Status | Notes |
|---|---|---|
| Create (check-in) | ✅ | Full pipeline |
| Read | ✅ | Per-player, today, audit |
| Undo (same-day) | ✅ | Restores 1 session |
| Delete older record | ❌ | No admin delete |
| Correction entry | ❌ | Not implemented |

**Gap:** admin delete for old records (sub-phase 3.4C).

## Audit log

| Operation | Status | Notes |
|---|---|---|
| Create | ✅ | Via `audit_service.record(...)` |
| Read | ✅ | Filtered list |
| Update | 🚫 | **Never.** Immutable by design. |
| Delete | 🚫 | **Never.** Immutable by design. |

**Gap:** none, intentionally.

## Notes

| Operation | Status | Notes |
|---|---|---|
| Read | ✅ | On player detail |
| Write | ✅ | Save button |
| Delete | ✅ | By blanking the field |

**Gap:** none.

## Settings

| Operation | Status | Notes |
|---|---|---|
| Read | ✅ | `load_config()` from bundled file |
| Write | ❌ | File-based, edited by hand |

**Gap:** config is edited by hand, not via UI. Deferred.

---

## Summary of gaps by priority

### TODO (this batch — Part 3)

1. **Subscription editing** — new dialog for editing: sessions_total, allowed_days, activity, start_date, payment_amount, payment_date. Audit every change. (Sub-phase 3.2)
2. **Subscription delete** — soft-delete via `archived_at`. Excluded from all lists. Restorable from recycle bin. (Sub-phase 3.3)
3. **Player delete** — soft-delete via `archived_at`. Excluded from all lists. Restorable. (Sub-phase 3.3)
4. **Recycle bin** — new screen listing archived players + subscriptions, with restore and permanent-delete options. (Sub-phase 3.3)
5. **User tombstone** — new "Delete" button. Renames user, disables login, preserves audit trail. (Sub-phase 3.4A)
6. **Payment edit-safe-fields + delete** — edit notes/method/date; delete with confirmation + audit. Amount immutable (delete + re-create). (Sub-phase 3.4B)
7. **Attendance admin delete** — same as undo but for any date. Audit entry captures original row. (Sub-phase 3.4C, deferred)

### NOT TODO (by design)

- **Activity hard delete** — attendance + subscriptions reference activity_id. Deactivate is the answer.
- **User hard delete** — tombstone is the answer.
- **Audit log edit/delete** — immutable by design.
- **Payment amount edit** — delete + recreate preserves auditability.
- **Notes history** — not worth the complexity; blanking is enough.

### Deferred to future phases

- Settings UI (currently config file).
- Attendance correction entries (only if customer asks).
- Payment correction entries (only if customer asks).
- Full text search across entities.
- Batch operations (bulk deactivate players, etc.).

---

## Files that will change in Part 3

For visibility, here's what each sub-phase touches:

**3.2 — Subscription editing:**
- `repositories/subscriptions_repo.py` (add `update_fields`)
- `services/subscription_service.py` (add `update_fields`)
- `ui/dialogs/edit_subscription_dialog.py` (new)
- `ui/screens/player_detail_screen.py` (add "Edit subscription" button)
- `translations/ar.json`, `en.json`

**3.3 — Soft delete + recycle bin:**
- `migrations/010_add_archived_at.py` (new migration)
- `repositories/players_repo.py` (respect archived_at)
- `repositories/subscriptions_repo.py` (respect archived_at)
- `services/player_service.py` (new — archive/restore)
- `services/subscription_service.py` (archive/restore)
- `ui/screens/recycle_bin_screen.py` (new)
- `ui/shell.py` (add menu item)
- `ui/main_window.py` (register new screen)
- `translations/ar.json`, `en.json`

**3.4A — User tombstone:**
- `repositories/users_repo.py` (add `tombstone`)
- `ui/screens/users_screen.py` (add Delete button)
- `translations/ar.json`, `en.json`

**3.4B — Payment edit + delete:**
- `repositories/payments_repo.py` (add `update_safe_fields`)
- `services/payment_service.py` (add `update_safe_fields`, `delete`)
- `ui/dialogs/edit_payment_dialog.py` (new)
- `ui/dialogs/confirm_delete_payment_dialog.py` (new)
- `ui/screens/player_detail_screen.py` (add Edit + Delete on payments table)
- `translations/ar.json`, `en.json`

**3.4C — Attendance admin delete (deferred):**
- Same pattern, not started yet.