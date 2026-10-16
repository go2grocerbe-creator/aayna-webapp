# AAYNA — Database Discovery & Isolated MongoDB Verification

Branch `chore/production-consolidation-20261015`, starting checkpoint `6b852d2` (2026-10-16).
No connection string, password, token or certificate appears in this report or in any committed file.
No write connection was opened to any existing database. Nothing was deployed, purchased or provisioned.

## 1. Result in one paragraph

- **Production database: UNKNOWN.** The production database has never been provisioned as far as any evidence shows. A MongoDB Atlas Flex cluster (Singapore) is *planned* in the infrastructure docs, but those docs state its credentials were never created. Nothing in the code, history or configuration points at a hosted database.
- **Where the real data is:** the only real AAYNA data that can be located is in a MongoDB server running on the founder's Windows PC (`localhost`, database `aayna_dev`, with the older `aayna_test` kept as a backup copy).
- **Official MongoDB for testing:** none could be installed or reached from this workspace.
- **The five release checks therefore remain NOT VERIFIED.** That status doesn't change in this round.
- **Superseded 2026-10-17: all five checks PASS on official MongoDB 8.0.34** (Atlas test cluster; see §10).
- **What was added:** a runner that makes them verifiable safely. It starts its own throwaway, credential-protected official `mongod` (fresh empty data folder, non-default port, loopback only), runs every check there and deletes it afterwards. A guard in the release checks now refuses any instance that also holds real AAYNA data. The runner's plumbing and guards were proven here using a stand-in engine. It needs one founder action to produce real MongoDB results (§6).

## 2. Database identification (Step 1)

| Source inspected | `MONGO_URL` exists | Type | Points to | Provider determinable | DB name | Access |
|---|---|---|---|---|---|---|
| Founder PC `backend/.env` (read-only parse in the desktop-bridge VM, values never printed) | yes | `mongodb://` | **localhost**, no credentials in URL | Local MongoDB server on the founder PC; server version/edition not visible | `aayna_dev` (`APP_ENV=development`) | documented + config verified; **not connected** (the PC's localhost is not reachable from here, and no connection was attempted) |
| Founder PC `backend/.env.test` | yes | `mongodb://` | localhost | same local server | `aayna_pytest` | config verified only |
| Founder PC `frontend/.env` | — | — | backend URL is localhost | — | — | — |
| Git history, all 13 remote branches | 2 historical values | `mongodb://` | localhost only (Emergent scaffold template); all others are placeholders | — | — | no `.env` file was ever committed |
| `backend/.env.example`, `README.md`, `PRODUCTION_ENV_CHECKLIST.md` | placeholders only | `mongodb://` / `mongodb+srv://` examples | — | — | `aayna_prod` named as the *intended* production DB | documented only |
| `INFRASTRUCTURE_BASELINE.md`, `DEPLOYMENT_RUNBOOK.md` | — | — | MongoDB **Atlas Flex, Singapore** planned | Atlas is a **plan**: "Credentials: Not created — requires an authenticated Atlas account/founder action" | `aayna_prod`, `aayna_staging` planned | **no evidence the cluster exists** |
| Emergent (original build platform) | not inspectable | — | — | No Emergent connector in this session. The history only shows Emergent's default in-pod localhost URL. | — | **UNKNOWN** whether an Emergent environment still holds data |
| Vercel project `aayna-webapp` (team `team_y5Ow…`) | not inspected | — | — | Listing env vars was **denied by the permission system** (treated as credential exploration). I did not attempt a workaround. Vercel hosts the static frontend, which never needs `MONGO_URL`. | — | not inspected |
| Railway | — | — | `backend/railway.json` exists; no evidence a service was created | — | — | not established |
| `shopaayna.com`, `api.shopaayna.com` | — | — | not reachable from this workspace (proxy 403) | — | — | **UNKNOWN** whether anything is live |
| BuyOS / Product Scout `.env*.local` | no `MONGO_URL` | — | uses Supabase (`https`) — a separate system, not the webapp database | — | — | out of scope |

Context from `ENVIRONMENTS.md`: the founder's local server holds real data. The old `aayna_test` database contained 51 real orders and the real catalogue; it was copied to `aayna_dev` and left in place as a backup. **The founder's local MongoDB must be treated as the live data store** until a production cluster exists. Because it holds real data, it is not an acceptable test target, even with a different database name.

## 3. Safe test option (Step 2)

| Option (brief's order) | Finding |
|---|---|
| 1. Existing isolated official MongoDB test instance | **None found.** The repo, the founder's connected folders and the git history contain no test cluster. |
| 2. Official MongoDB installed from a trusted source | **This workspace:** official download hosts are refused by the network allowlist (Phase 4B evidence; not retried, per instruction). Ubuntu doesn't package MongoDB. **Founder PC:** the dev backend talks to a local MongoDB server, so an official `mongod.exe` is *probably* installed. This is **not verified**: Program Files isn't a connected folder, and the bridge VM can't run Windows binaries or reach the PC's localhost. |
| 3. Separately provisioned managed instance | Not done. It needs registration or new infrastructure, so it needs founder approval. |
| GitHub Actions with the official `mongo` service container | The repo is **public**, so Actions minutes are free. However, this workspace's proxy blocks the GitHub Actions API, so I could neither run nor read it. Adding a workflow would be new CI infrastructure, so it needs founder approval. |

Not used: FerretDB for atomicity (it is only a plumbing stand-in, §5); the live/production database; the founder's existing local instance.

## 4. Isolation safeguards (Step 3) — `scripts/verify/run_isolated_mongo_checks.py`

The runner starts **its own** `mongod` from the binary you give it. Before any test runs, it enforces the following:

| Safeguard | How |
|---|---|
| Separate instance, never the existing one | new process; **fresh empty data directory** created by the runner (`aayna-isolated-mongo-*` in the OS temp dir), refused if not empty; deleted afterwards |
| Not the default instance | random free port; refuses 27017; `--bind_ip 127.0.0.1` |
| No real data on the instance | lists databases and refuses if any of `aayna_dev`, `aayna_test`, `aayna_prod`, `aayna_staging`, or anything other than `admin/config/local/aayna_pytest`, is present |
| Temporary credentials | `--auth`; a generated user (`readWrite` + `dbAdmin` on `aayna_pytest` only) is created through the localhost exception. The admin e-mail, admin password and JWT secret are also generated. Nothing is printed, and every generated value is scrubbed from saved logs and the summary. |
| Nothing inherited from the developer's `.env` | Every variable the backend, tests and scripts read (20) is set explicitly. `load_dotenv` never overrides those, so `backend/.env` can't leak in. The **order webhook is forced off** and the **Emergent storage key is forced empty**. |
| Right target before every suite | the test DB is dropped and the backend restarted per suite; `/api/health` must report `aayna_pytest` or the run aborts |
| Engine honesty | `buildInfo` decides the engine. The verdict is PASS only on official MongoDB with every suite exiting 0. On any other engine the verdict is printed as NOT VERIFIED. |

New guard in `scripts/verify/mongo_release_checks.py` (applies to any manual run too):
- It refuses a non-loopback host unless `ALLOW_NONLOCAL_TEST_DB=1` is set, which is intended only for a dedicated, separately provisioned test cluster.
- It refuses any instance that also contains a real AAYNA database.
- This is in addition to the existing rule that `DB_NAME` must contain "test".

## 5. Test results (Step 4)

### Official MongoDB — **NOT RUN** (no instance available; see §3)

| # | Check | Status |
|---|---|---|
| 1 | Dashboard aggregation | **NOT VERIFIED** → PASS on 2026-10-17 (§10) |
| 2 | Low-stock inventory filtering | **NOT VERIFIED** → PASS on 2026-10-17 (§10) |
| 3 | Customer list and detail aggregation | **NOT VERIFIED** → PASS on 2026-10-17 (§10) |
| 4 | 10 concurrent one-item checkouts vs 3 units | **NOT VERIFIED** → PASS on 2026-10-17 (§10) |
| 5 | Simultaneous multi-item checkout protection | **NOT VERIFIED** → PASS on 2026-10-17 (§10) |
| — | Duplicate-order (8 concurrent same-key submissions) | passes on FerretDB; **not re-run on MongoDB** |
| — | Failed-order rollback | passes on FerretDB; **not re-run on MongoDB** |

No claim of production concurrency safety is made.

### Runner self-test (FerretDB 1.24 posing as `mongod`, harness plumbing only)

| Item | Result |
|---|---|
| Starts its own instance in a fresh dir, random port, loopback | PASS |
| Backend points at `aayna_pytest`; webhook off, storage key empty | PASS |
| `release` suite | 7 pass / 0 fail / 5 NOT VERIFIED (identical to Phase 4B) |
| `data_integrity.py` after the concurrency runs | exit 2: duplicate order numbers. This is the FerretDB non-atomicity the checks are designed to expose. |
| `backend_admin_checks.py` | 61/61 |
| backend `pytest` | 120 passed / 1 skipped / 3 failed (the MongoDB-only aggregation tests) |
| Final verdict printed | "NOT VERIFIED — engine is not official MongoDB" (correct) |
| Data dir deleted, no engine process left, no generated secret or e-mail in any saved file | PASS |
| `--auth` user creation | **NOT VERIFIED.** FerretDB has no `createUser`, and the runner exits with a clear error. It needs a real MongoDB run. |

Guard tests: these four were refused correctly (exit 1):
- an instance holding `aayna_dev`
- a remote host
- a non-test `DB_NAME`
- a missing binary

A `mongodb+srv://` target fails at DNS resolution before any connection is made.

Regression with the new guard: release 7/0/5 NV, backend 61/61, pytest 120/1/3, offline 42/42 (unchanged).

Evidence: `docs/audits/evidence/dbdiscovery/` (scrubbed).

Side note: when `EMERGENT_LLM_KEY` is empty, `storage.py` still calls `integrations.emergentagent.com/.../init` on upload. In this workspace the call is refused. With an empty key it can't write anything, but the code still makes a network call. Logged for the storage-migration work; not changed here.

## 6. Founder action genuinely required (pick one)

**A — Run it on your PC (no new services, about 10 minutes).** Your dev backend already uses a local MongoDB, so the official binary is likely installed, typically at `C:\Program Files\MongoDB\Server\<version>\bin\mongod.exe`. Your running MongoDB and its data are **not touched**: the runner starts a second, separate process with its own empty folder and port.

To leave your current checkout (`launch/aayna-readiness-v1`) untouched, use a separate worktree:
```
cd E:\deMarkt\aayna-webapp\Aayna-Webapp
git fetch origin chore/production-consolidation-20261015
git worktree add ..\aayna-verify origin/chore/production-consolidation-20261015
cd ..\aayna-verify
..\Aayna-Webapp\backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
..\Aayna-Webapp\backend\venv\Scripts\python.exe scripts\verify\run_isolated_mongo_checks.py --mongod "C:\Program Files\MongoDB\Server\<version>\bin\mongod.exe" --out ..\aayna-verify-report
```
Share the `aayna-verify-report` folder. It holds only scrubbed logs and `summary.json`, with no secrets. If `mongod.exe` isn't installed, choose B rather than installing it ad hoc.

**B — Allow one download host for this workspace.** In claude.ai → Settings → Capabilities (network access), allow `fastdl.mongodb.org`. I would then install the official MongoDB tarball here and run the same runner. No account, billing or infrastructure is involved.

**C — Approve a GitHub Actions workflow** that runs the runner against the official `mongo` image (free for this public repo). You would read the result in GitHub, because this workspace can't.

Also pending authorization (unchanged from Phase 4B): read-only `data_integrity.py`, `index_migration.py` (dry run) and the image manifest against the real `aayna_dev` on your PC.

## 7. Remaining launch blockers

1. The five MongoDB checks, plus the duplicate-order and rollback re-runs on official MongoDB — **NOT VERIFIED** (needs §6).
2. No production database exists. Provision it (Atlas Flex or other — founder decision), with its own scoped user. Then apply the unique indexes after a backup.
3. The real data lives only on the founder PC. Back it up before any migration, and run the read-only diagnostics on it (authorization).
4. Product images are still on Emergent storage/CDN. Export the originals while reachable; storage provider decision.
5. Unchanged from Phase 4B:
   - payment approach (founder decision)
   - stock-return workflow approval
   - transactions and a shared login limiter before running multiple workers
   - verified legal-entity disclosures

## 8. Update 2026-10-16 — dedicated Atlas test cluster

The founder created a dedicated Atlas test environment:
- Project `AAYNA`, cluster `aayna-dev`, M0, AWS Singapore.
- User `aayna_test_app` with `readWrite` on `aayna_release_test` only.
- Network access restricted to one `/32` IP.

Emergent's `test_database` is real project data and is never a test target.

**Guard hazard found and fixed (`2abf543`).** Five write-capable entry points only checked that the database name contained "test":
- `mongo_release_checks.py`
- `backend_admin_checks.py`
- `inventory_rules.py`
- `index_migration.py --apply`
- pytest `conftest.py`, including its drop-database teardown

So they all accepted `test_database`. They now share `scripts/verify/release_target_guard.py`, an **exact allowlist** with two allowed targets:

| Target | Required |
|---|---|
| local | loopback host and DB `aayna_pytest`; refused if the instance also holds any real database name |
| Atlas | single `mongodb+srv` host whose first label is `aayna-dev` under `*.mongodb.net`; user `aayna_test_app`; DB `aayna_release_test`; replica-set members on the same Atlas domain; authenticated **solely** as that user; **no write-capable privilege on any other database or the cluster** (live `connectionStatus` with `showPrivileges`) |

Always refused: `test_database`, `aayna_dev`, `aayna_test`, `aayna_prod`, `aayna_staging`, `admin`, `local`, `config`, and any other name.

pytest teardown now drops collections, which needs only `readWrite`, and re-verifies the target first.

Verification:
- 27 new offline guard tests; 69/69 offline tests pass in total.
- Every entry point refuses `test_database` before connecting.
- Local suites unchanged: rules 28/28, backend 61/61, release 7 / 0 / 5 NOT VERIFIED, pytest 120 / 1 / 3.

**Runner `--atlas-env` mode (`3544f27`, `d04d072`):**
- It reads `MONGO_URL` from a local file and refuses a file that git tracks or doesn't ignore.
- It runs the guard before any write and resets the test database by dropping its collections.
- It leaves `aayna_release_test` empty afterwards.
- It scrubs the URI, password and host from every log.
- `--check-only` performs the identity and privilege checks without writing anything.

These refusal paths were tested offline:
- wrong cluster
- admin user
- non-`srv` remote
- unresolvable host
- credentials file not gitignored

**Where it runs.** Only the founder's Windows PC is on the Atlas allowlist. The code at `d04d072` was placed in a **separate** folder, `E:\deMarkt\aayna-webapp\aayna-release-verify`, which is not a git repository. The founder's checkout (`launch/aayna-readiness-v1`, clean apart from one untracked `.claude/settings.local.json`) was not touched. That PC's backend venv (Python 3.13.7) has every required package, including `dnspython` for `mongodb+srv`.

**Status:** the five checks are still **NOT VERIFIED** until the founder runs the runner against Atlas (§8 results to follow).

## 9. Atlas connection troubleshooting (2026-10-17)

**Symptom:** `Refusing to run: remote test target is not the approved Atlas cluster 'aayna-dev'`.

**Cause 1: the connection string, not the validator.** The structure of `.env.release-test` was inspected without printing it:
- Scheme `mongodb+srv`, user `aayna_test_app`, a 16-character password.
- The text after `@` was a single word with no dots and no `mongodb.net`. The string contained **no Atlas hostname at all**.
- The validator was right to refuse it.

**Approved hostname:** `aayna-dev.gzn5qto.mongodb.net`.
- Read from the **authenticated Atlas Connect dialog** of cluster `aayna-dev` in project `AAYNA`, where the username and password are only placeholders.
- Atlas reported tier FREE, MongoDB 8.0.34, AWS, one region.
- Public DNS couldn't be used to cross-check: DNS is filtered in both the workspace and the bridge VM.
- Only the hostname in the founder's local file was corrected. The password and username were carried over unchanged and never printed.

**Validator hardening (`42ce6a2`).** It previously accepted any `aayna-dev.<id>.mongodb.net`, so a same-named cluster in another Atlas project would have passed. Now:
- The host must equal the approved host exactly (ASCII, case-insensitive).
- Replica-set members must be exactly `<name>.gzn5qto.mongodb.net`.
- 17 tests cover:
  - a one-character-off ID
  - another project's ID
  - suffix and prefix attacks
  - a trailing dot
  - an underscore lookalike
  - a Cyrillic homoglyph
  - the wrong TLD
  - an `@` in the password causing host confusion
  - lookalike replica-set members

**Cause 2: the Atlas user's role is limited to one collection.** The read-only `--check-only` run went through File Explorer → `check-only.bat` on the founder's PC. It produced:
- Connected to official **MongoDB 8.0.34**, a 3-member replica set.
- Cluster identity verified; authenticated solely as `aayna_test_app`.
- Role `readWrite@aayna_release_test`; no write privilege outside the test database.
- **However,** the privileges apply to the resource `{db: aayna_release_test, collection: "All collections"}`, a single collection literally named "All collections", not the whole database. Atlas therefore refused `listCollections`, error `8000 AtlasError`.
- No writes were made.

**Guard hardening (this commit).** Positive evidence is now required:
- The roles must be exactly `readWrite@aayna_release_test`.
- `find`, `insert`, `update`, `remove`, `listCollections`, `createIndex` and `dropCollection` must be granted on the **whole** test database (empty collection field).
- An empty privilege report, extra roles (`readWriteAnyDatabase`, `atlasAdmin`, `readWrite@test_database`) or a collection-scoped role are all refused, with instructions.
- 94/94 offline tests pass.
- The founder's PC now refuses before any database call: `lacks database-wide [...] the role is limited to collection(s) ['All collections']`.

**Founder action:** in Atlas, go to Security → Database & Network Access → Database Users → `aayna_test_app` → Edit. Keep the built-in role `readWrite` on database `aayna_release_test`, **leave Collection empty**, then Update User. The password is unchanged.

The five checks remain **NOT VERIFIED**. *(The founder then fixed the role; see §10.)*

## 10. Verified results on official MongoDB (2026-10-17)

### Test environment

| Item | Value |
|---|---|
| Engine | **official MongoDB 8.0.34** (`buildInfo`; not an emulator) |
| Cluster | Atlas project `AAYNA`, cluster `aayna-dev`, tier FREE (M0), AWS, one region; 3-member replica set. Host pinned exactly in the guard. |
| Database / user | `aayna_release_test` as `aayna_test_app`. Roles: exactly `readWrite@aayna_release_test`, database-wide (empty collection field) plus Atlas's standard `system.js` entry. **No write privilege outside the test database.** Only `aayna_release_test` is visible to this user. |
| Network | Atlas Network Access: one `/32` (founder's PC). Not opened to the internet. |
| Where it ran | Founder's Windows PC, separate folder `aayna-release-verify` (code `4c5fc7c`), backend venv Python 3.13.7. The founder's checkout was not touched. |
| Isolation at run time | Test DB had 0 collections at start and was **emptied afterwards**. Order webhook off; Emergent storage key empty. Every backend env variable set explicitly. Emergent `test_database` and all real data were never contacted. |
| Run | `run_isolated_mongo_checks.py --atlas-env .env.release-test`, 2026-10-16 18:23–18:24 UTC. Overall verdict: **PASS**. |

### Results (evidence: `docs/audits/evidence/atlas/`, scrubbed: no URI, password or host)

| Suite | Result |
|---|---|
| `mongo_release_checks.py` | **16 passed / 0 failed / 0 NOT VERIFIED** |
| `backend_admin_checks.py` | **62/62** |
| backend pytest | **123 passed, 1 skipped**. The skip is admin image upload, because object storage was deliberately disabled. The 3 tests that failed on FerretDB now pass. |
| `data_integrity.py` (read-only, after the runs) | 0 BLOCKER, 2 REVIEW (exit 1, analysed below) |

The five outstanding checks, plus the duplicate-order and rollback checks:

| # | Check | Result (exact output) |
|---|---|---|
| 1 | Dashboard aggregation | PASS: keys present; today's orders/sales with cancelled orders excluded match raw data (api=2/280.0, raw=2/280.0); `low_stock_count` excludes drafts (api=1, raw=1) |
| 2 | Low-stock filtering | PASS: `low_only` returns exactly the non-draft products at or below their alert (api=1, raw=1); no `cost_price` in the response |
| 3 | Customer list/detail | PASS: `last_order_date` is the newest order; detail lists all orders, newest first |
| 4 | 10 concurrent one-item orders vs 3 units | PASS: three HTTP 200s, 3 orders, stock 0, `out_of_stock`, 3 sale logs |
| 5 | Multi-item atomicity | PASS: a failing multi-item order leaves every product unchanged with no order or customer; **concurrent** 10 two-item orders with the scarce item at 3 → 3 orders, A=7, B=0 |
| — | Duplicate-order idempotency | PASS: 8 concurrent submissions with one key → exactly 1 order (ORD-1011), every response names it, stock decremented once |
| — | Failed-order rollback | PASS: an insert failure gives HTTP 500 JSON, stock restored, no stray customer, key released; the retry succeeds |
| — | Invariants | PASS: no negative stock; no duplicate `client_request_id`; **no duplicate order numbers** (FerretDB had produced them) |

### The two integrity REVIEW findings

**REVIEW 1: duplicate `customers.phone` (+8801700000021 ×2). This is a genuine defect (medium severity), and the fix is already planned.**
- `+8801700000021` is the default phone the release checks use for their concurrency tests: about 28 near-simultaneous checkouts from one number that had never ordered before.
- Checkout looks the customer up by phone and inserts a new record if none exists (`server.py` §8, "Upsert customer"). The only index on `customers.phone` is the non-unique `phone_1`. So two first-time orders from the same phone that arrive together can both create a customer.
- This was predicted in Phase 4B and is now **confirmed on real MongoDB**.
- Impact: one person's history and `total_orders` are split across two customer records in admin. Stock, orders, totals and money are not affected.
- Fix: the planned **unique index on `customers.phone`** (`index_migration.py` plan). Checkout already tolerates the resulting `DuplicateKeyError` by re-reading the record (`6493a1f`).
- Before that index can be built on real data, existing duplicate phones must be merged; `data_integrity.py` lists them.
- That fix path, a unique index plus a concurrent re-run, is **not yet verified on Atlas**.

**REVIEW 2: stock 7 vs last inventory-log `new_stock` 6 (product `REL-190012c5`). The stock is correct; the log snapshot is imprecise under concurrency. Not a stock defect; low severity.**
- This is product A in the concurrent multi-item test: starting stock 10, three successful orders, final stock **7**, which is correct and asserted by the test.
- Each successful order logs `quantity_change = -1` together with `new_stock`, which is the value returned by *its own* atomic decrement.
- While it ran, other requests held temporary reservations on A that were later released when their scarce item B ran out. So one success saw A at 6, momentarily.
- The sum of logged changes (-3) matches the real movement (10 → 7). Only the `previous_stock`/`new_stock` snapshot fields can include other requests' in-flight reservations. Failed orders write no log entries.
- The integrity check compares stock with the *last* log's `new_stock`, a heuristic that flags this case.
- Possible later improvement (not required for launch): describe those fields as snapshots, or have the integrity check compare against the sum of `quantity_change` values instead.

### Limitations
- **M0/free tier:** shared, rate-limited, no backups. Its throughput isn't representative of production; it was used only for correctness and atomicity.
- **Only these tests were proven** (correctness, single backend process, the scenarios above). This doesn't prove behaviour under multiple workers, network partitions or crashes mid-checkout: there are no multi-document transactions (see `PRODUCTION_DATA_INTEGRITY.md` §3).
- **Unique indexes were not applied** to the test DB during this run (`phone_1` and `order_number_1` were non-unique). Behaviour with the planned unique indexes is tested only on FerretDB.
- **Storage:** with an empty storage key the backend still calls Emergent's storage `init` at startup and on upload. Emergent answered **403** from the founder's PC, so nothing can be written there, but it is still an outbound call.
- **Not production evidence:** this is a dedicated test cluster. No production database exists yet.
