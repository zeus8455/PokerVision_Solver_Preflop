## V2.34.0 - enable Solver_Preflop controlled raise branch

Status: passed

Goal:
- Enable controlled bet/raise runtime planning for Solver_Preflop decisions.
- Remove the old V1.1 simple-button blocker only for Solver_Preflop-adapted preflop raise-family actions.
- Keep all lower click guards active: active_confirmed, slot_guard, no_repeat, button_availability, dry_run_or_real_click_flag, click_execution_guard.

Changed:
- external/PokerVisionFinalVersionNoSolver_snapshot/PokerVision V1_2/logic/action_runtime_plan_builder.py

Added:
- tools/apply_v2_34_enable_solver_preflop_raise_branch_patch.py
- tools/run_v2_34_enable_solver_preflop_raise_branch_audit.py
- tests/test_v2_34_enable_solver_preflop_raise_branch_audit.py

Removed:
- tools/run_v2_33_raise_path_contract_audit.py
- tests/test_v2_33_raise_path_contract_audit.py

Validated:
- V2.34 audit status ok
- open_raise -> ["Raise"]
- iso_raise -> ["98%", "Raise"]
- 3bet -> ["98%", "Raise"]
- 4bet -> ["50%", "Raise"]
- all_in -> ["98%", "Raise"]
- runtime_plan_status == ok
- planned_action == bet_raise
- raise_branch_enabled == true
- blocked_reason == null
- v11 decision_id is not v12_stub_*
- real project not touched
- full pytest: 105 passed

Live issue addressed:
- Fold path was already proven in real-live with physical click.
- Raise path was not clickable because Action_Runtime_Plan builder always blocked bet_raise as bet_raise_branch_disabled_for_v1_1_first_real_click_stage.
- V2.34 allows Solver_Preflop-controlled raise-family plans while preserving all runtime click guards.

## V2.32.0 - inject Solver_Preflop bridge before live runtime

Status: passed

Goal:
- Fix live runtime still falling back to legacy v12_stub_* because v11_stage1_runtime received full_state before solver_preflop_bridge_contract was built.
- Build and inject Solver_Preflop bridge into state before _run_v11_stage2_runtime_safely(...).

Changed:
- external/PokerVisionFinalVersionNoSolver_snapshot/PokerVision V1_2/display_analysis_cycle.py

Added:
- tools/apply_v2_32_pre_runtime_solver_bridge_injection_patch.py
- tools/run_v2_32_pre_runtime_solver_bridge_injection_audit.py
- tests/test_v2_32_pre_runtime_solver_bridge_injection_audit.py

Validated:
- V2.32 audit status ok
- pre-runtime Clear_JSON candidate is built before v11 runtime
- solver_preflop_bridge_contract is built before v11 runtime
- state["solver_preflop_bridge_contract"] is set before _run_v11_stage2_runtime_safely(...)
- late pending/final bridge path remains present
- display_analysis_cycle imports successfully
- real project not touched
- full pytest: 104 passed

Live issue addressed:
- After V2.31, v11_stage1_runtime could accept ok/fallback Solver_Preflop bridge.
- But live full_state did not contain solver_preflop_bridge_contract before v11 runtime.
- Runtime therefore still built legacy v12_stub_* and blocked real-click as blocked_stub_real_click.
- V2.32 injects the bridge before runtime, so the live click path can use Solver_Preflop instead of legacy stub.

## V2.31.0 - accept Solver_Preflop fallback bridge in live runtime

Status: passed

Goal:
- Fix live runtime falling back to legacy v12_stub_* when Solver_Preflop bridge status is fallback but bridge_payload.action_decision is available.
- Prevent real-click from being blocked by blocked_stub_real_click when Solver_Preflop already produced a usable safe decision.

Changed:
- external/PokerVisionFinalVersionNoSolver_snapshot/PokerVision V1_2/runtime/v11_stage1_runtime.py
- tools/run_v2_23_live_runtime_solver_bridge_audit.py

Added:
- tools/apply_v2_31_accept_solver_preflop_fallback_contract_patch.py
- tools/run_v2_31_accept_solver_preflop_fallback_contract_audit.py
- tests/test_v2_31_accept_solver_preflop_fallback_contract_audit.py

Validated:
- V2.31 audit status ok
- fallback Solver_Preflop bridge now returns runtime decision
- fallback decision source == PokerVision_Solver_Preflop
- fallback decision_id is not v12_stub_*
- ok bridge status still works
- bad bridge status is still rejected
- V2.23 live runtime solver bridge audit updated for ok|fallback contract
- real project not touched
- full pytest: 103 passed

Live issue addressed:
- After V2.30, duplicate Active retry reached action runtime.
- Runtime selected Solver_Preflop_Bridge in preview but v11_stage1_runtime rejected bridge.status=fallback.
- Runtime then built legacy v12_stub_* and real-click was blocked as blocked_stub_real_click.
- V2.31 accepts fallback bridge when bridge_payload.action_decision exists, so live runtime uses Solver_Preflop instead of legacy stub.

## V2.30.0 - duplicate Active runtime retry when no runtime/final artifact exists

Status: passed

Goal:
- Fix real-live case where Active is detected but ActionEventGate suppresses it as duplicate before runtime/click can start.
- Allow duplicate Active to re-enter the guarded runtime branch only when the current table has no Action_Runtime_Plan_JSON and no Final Clear_JSON.

Changed:
- external/PokerVisionFinalVersionNoSolver_snapshot/PokerVision V1_2/display_analysis_cycle.py

Added:
- tools/apply_v2_30_duplicate_active_runtime_retry_flexible_patch.py
- tools/run_v2_30_duplicate_active_runtime_retry_audit.py
- tests/test_v2_30_duplicate_active_runtime_retry_audit.py

Validated:
- V2.30 audit status ok
- duplicate Active retry block is after duplicate suppression log
- retry block is before action_runtime_candidate and duplicate hard-stop
- retry is limited to reason == duplicate_active_frame_blocked
- retry requires no Action_Runtime_Plan_JSON and no Final Clear_JSON for the table
- retry creates action_event_id and sets should_process=True via dataclass replace
- display_analysis_cycle imports successfully
- real project not touched
- full pytest: 102 passed

Live issue addressed:
- After V2.29, stale lifecycle was released correctly.
- The next blocker was duplicate_active_frame_blocked with event_id_present=False.
- That prevented Action_Runtime_Plan_JSON, Final Clear_JSON, and click.
- V2.30 converts unfinished duplicate Active frames into guarded runtime retry events without disabling click guards.

## V2.29.0 - release stale lifecycle inside early gate blocked path

Status: passed

Goal:
- Fix the remaining real-live stale lifecycle lock case where heavy analysis is skipped before the V2.28 release block can run.
- Release table lifecycle directly inside the early gate blocked path when reason == table_lifecycle_already_open_before_analysis.

Changed:
- external/PokerVisionFinalVersionNoSolver_snapshot/PokerVision V1_2/display_analysis_cycle.py

Added:
- tools/apply_v2_29_early_gate_stale_lifecycle_release_patch.py
- tools/run_v2_29_early_gate_stale_lifecycle_release_audit.py
- tests/test_v2_29_early_gate_stale_lifecycle_release_audit.py

Validated:
- V2.29 audit status ok
- V2.29 release is inside early gate blocked path
- V2.29 release occurs before V2.28 late release block
- abort_analysis_cycle used only for table_lifecycle_already_open_before_analysis
- current frame remains skipped after release
- next scan can reopen lifecycle normally
- real project not touched
- full pytest: 101 passed

Live issue addressed:
- table_lifecycle_already_open_before_analysis could block heavy analysis before the previous V2.28 release block was reached.
- This prevented later stages from reaching Clear_JSON -> Solver_Preflop -> Action_Button -> click.
- V2.29 releases that stale lifecycle before continue, allowing the next scan to process normally.

## V2.28.0 - release early transaction lifecycle when action runtime cannot start

Status: passed

Goal:
- Fix real-live lock issue where Active could be detected but Action_Button runtime never starts.
- Prevent table lifecycle from staying locked as table_lifecycle_already_open_before_analysis after no_active_confirmed, duplicate_active_frame_blocked, or missing action_event_id/action runtime candidate.

Changed:
- external/PokerVisionFinalVersionNoSolver_snapshot/PokerVision V1_2/display_analysis_cycle.py

Added:
- tools/apply_v2_28_live_transaction_gate_unlock_patch.py
- tools/run_v2_28_live_transaction_gate_unlock_audit.py
- tests/test_v2_28_live_transaction_gate_unlock_audit.py

Validated:
- V2.28 audit status ok
- early lifecycle release block present before action runtime stage
- abort_analysis_cycle used for early lifecycle cleanup
- transaction gate semantics ok
- real project not touched
- full pytest: 100 passed

Live issue addressed:
- Active was sometimes seen, but duplicated/no-event frames left the table lifecycle open.
- Later frames were blocked by table_lifecycle_already_open_before_analysis.
- This prevented Clear_JSON/Solver_Preflop/Action_Button/click chain from starting.

## V2.26.0 - live no-click probe after V2.25

Status: passed

Goal:
- Re-run safe live no-click probe after Solver_Preflop runtime integration and startup readiness.
- Validate live-cycle, screen capture, YOLO chain, and no physical click.
- Do not falsely mark Solver_Preflop live chain as validated when no Active/Clear_JSON artifacts are produced.

Added:
- tools/run_v2_26_live_no_click_probe_after_v225.py
- tests/test_v2_26_live_no_click_probe_after_v225.py

Validated:
- V2.25 VERSION record is present
- live_cycle_executed == true
- screen_capture_executed == true
- yolo_detector_executed == true
- physical_click_executed == false
- current_cycle restored after probe
- six table slots available
- table_01..table_06 detected
- real project not touched
- solver_live_chain_validated == false when no Active/Clear_JSON artifacts are observed
- full pytest: 99 passed

## V2.25.0 - real startup readiness after V2.24

Status: passed

Goal:
- Prove controlled real-click startup readiness after V2.24 snapshot runtime E2E.
- Run readiness through main.py --startup-audit-only without live UI, screen capture, YOLO, or physical mouse click.

Added:
- tools/run_v2_25_real_startup_readiness_after_v224.py
- tests/test_v2_25_real_startup_readiness_after_v224.py

Validated:
- V2.24 VERSION record is present
- V2.20 real-live startup readiness tool returns status ok
- real_click_ready == true
- no_click_mode disabled
- master armed
- Action_Button real-click enabled
- Service real-click enabled
- startup audit-only active
- max clicks per run == 0
- live UI not launched
- screen capture not executed
- YOLO detector not executed
- physical_click_executed == false
- full pytest: 98 passed

## V2.24.0 - snapshot live-runtime E2E

Status: passed

Goal:
- Prove Solver_Preflop bridge -> v11_stage1_runtime -> Action_Button dry-run click plan path without YOLO, screen capture, or physical mouse click.

Added:
- tools/run_v2_24_snapshot_live_runtime_e2e.py
- tests/test_v2_24_snapshot_live_runtime_e2e.py

Validated:
- bridge.status == ok
- runtime solver source == PokerVision_Solver_Preflop
- solver decision_id is not v12_stub_* and not v12_fallback_*
- click decision_id matches solver decision_id
- open_raise raise-family action maps to legacy bet_raise
- fake Action_Button pipeline is used
- click status == dry_run
- physical_click_executed == false
- full pytest: 97 passed

# Version history

## V2.23.0
Live runtime Solver_Preflop bridge source:
- updates v11_stage1_runtime.py to read Solver_Preflop bridge contract from full_state
- uses bridge_payload.action_decision as live runtime solver_decision when bridge status is ok
- sets live runtime solver source to PokerVision_Solver_Preflop
- maps Solver_Preflop open_raise/iso_raise/3bet/4bet/5bet/jam/all_in to legacy bet_raise for Action_Button runtime
- preserves solver decision_id and solver_fingerprint
- keeps v12_stub_* only as fallback path
- keeps V2.21/V2.22 real-click blockers active for stub/fallback decisions
- adds V2.23 live runtime Solver_Preflop bridge audit tool
- adds V2.23 pytest coverage
- full test suite: 96 passed
## V2.22.0
Strict real-click source guard:
- adds final Action_Button click-gate protection against non-Solver_Preflop real clicks
- blocks physical click when solver source is not PokerVision_Solver_Preflop
- blocks physical click when solver status is not ok
- blocks v12_stub_* decision IDs at final click gate
- blocks v12_fallback_* decision IDs at final click gate
- exposes solver_source and solver_status in controlled live-click gate report
- adds V2.22 strict real-click source guard audit tool
- adds V2.22 pytest coverage
- full test suite: 95 passed
## V2.21.0
Real-click stub fallback blocker:
- opens V8.7 full live chain scope for real runtime testing
- enables raise branch in controlled full-live mode
- disables simple-actions-only in controlled full-live mode
- allows Solver_Preflop raise/open_raise/iso_raise/3bet/4bet/5bet/jam/all_in action names
- allows Raise and sizing buttons 33%/50%/70%/98% in full-live scope
- adds real-click startup readiness audit tool
- blocks legacy v12_stub_* decisions from executing physical clicks in real-click mode
- returns click_completed=false and guard_passed=false when stub real-click is blocked
- fixes V2.19 live no-click probe stdout so JSON report remains parseable
- adds V2.21 regression audit and pytest coverage
- full test suite: 94 passed
## V2.19.0
Live no-click capture probe regression:
- adds tools/run_v2_19_live_no_click_capture_probe.py
- adds tests/test_v2_19_live_no_click_capture_probe.py
- runs one controlled live display-analysis pass over 6 table slots
- confirms live cycle executes
- confirms screen capture executes
- confirms YOLO detector chain is reachable
- confirms physical click is not executed
- confirms all 6 table slots are bound
- allows zero saved JSON files when no Active/meaningful Trigger_UI classes are detected
- keeps real project mutation disabled and real-click disabled
## V2.18.0
Startup audit-only readiness regression:
- adds tools/run_v2_18_startup_audit_only_readiness.py
- adds tests/test_v2_18_startup_audit_only_readiness.py
- runs main.py --startup-audit-only from the snapshot runtime
- confirms startup readiness exits with returncode 0
- confirms live UI launch is skipped
- confirms screen capture is not executed
- confirms YOLO detectors are not executed
- confirms physical click is not executed
- confirms Action_Button real click is disabled and dry-run is enabled
- confirms Trigger_UI service real click is disabled and dry-run is enabled
- confirms V10 readiness reports safe_no_click
- keeps real project mutation disabled
## V2.17.0
Pre-live config audit:
- adds tools/run_v2_17_pre_live_config_audit.py
- adds tests/test_v2_17_pre_live_config_audit.py
- audits effective imported pre-live config, not only raw text grep
- confirms live data capture no-click mode is enabled
- confirms Action_Button real mouse click is disabled
- confirms Action_Button dry-run is enabled
- confirms Trigger_UI service real click is disabled
- confirms real-click master arm is disabled
- confirms transaction gate is enabled
- confirms dry-run counts as completed for pre-live audit mode
- confirms Final Clear_JSON requires click_result
- confirms slot, no-repeat and button availability guards are required
- confirms Solver_Preflop runtime source is enabled and dry-run only
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.16.0
Snapshot 6-slot preflop E2E regression:
- adds tools/run_v2_16_snapshot_6slot_preflop_e2e.py
- adds tests/test_v2_16_snapshot_6slot_preflop_e2e.py
- runs synthetic 6-slot preflop E2E over table_01 through table_06
- confirms every slot gets its own Final Clear_JSON
- confirms every slot gets its own final Action_Runtime_Plan_JSON
- confirms unique table_id, table_index, slot_bbox and decision_id for all 6 slots
- confirms final runtime source is Solver_Preflop_Bridge for every slot
- confirms final/runtime output paths are scoped to the correct table directory
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.16.0
Snapshot 6-slot preflop E2E regression:
- adds tools/run_v2_16_snapshot_6slot_preflop_e2e.py
- adds tests/test_v2_16_snapshot_6slot_preflop_e2e.py
- runs synthetic 6-slot preflop E2E over table_01 through table_06
- confirms every slot gets its own Final Clear_JSON
- confirms every slot gets its own final Action_Runtime_Plan_JSON
- confirms unique table_id, table_index, slot_bbox and decision_id for all 6 slots
- confirms final runtime source is Solver_Preflop_Bridge for every slot
- confirms final/runtime output paths are scoped to the correct table directory
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.15.0
Snapshot all-preflop E2E regression:
- adds tools/run_v2_15_snapshot_all_preflop_e2e.py
- adds tests/test_v2_15_snapshot_all_preflop_e2e.py
- runs all real snapshot preflop Pending Clear_JSON cases
- confirms Pending Clear_JSON -> Solver_Preflop_Bridge -> Action_Decision_JSON -> Action_Runtime_Plan_JSON
- confirms dry-run transaction completes for every preflop case
- confirms Final Clear_JSON is saved for every preflop case
- confirms click_result is embedded into every Final Clear_JSON
- confirms runtime source is Solver_Preflop_Bridge for every final runtime plan
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.14.0
Snapshot final Solver_Preflop source regression:
- fixes final Solver_Preflop bridge source selection after Final Clear_JSON already contains click_result
- keeps solver_preflop_dryrun_bridge.py guard unchanged
- passes a final Clear_JSON copy without click_result into Solver_Preflop bridge
- confirms final Solver_Preflop bridge status is ok
- confirms final runtime source selection uses Solver_Preflop_Bridge
- confirms final runtime selection reason is v20_solver_preflop_selected
- confirms solver action decision is available and adapted to legacy Action_Decision shape
- confirms final Action_Runtime_Plan_JSON is saved as final and file publication is enabled
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.13.0
Snapshot final Action_Decision publication regression:
- fixes snapshot display_analysis_cycle.py final Action_Decision publication NameError path
- adds solver_preflop_bridge_contract as an explicit optional argument to build_and_save_action_decision_contract
- builds Solver_Preflop bridge before pending Action_Decision preview
- passes Solver_Preflop bridge into pending and final Action_Decision/RuntimePlan publication
- confirms Final Clear_JSON still saves after completed dry-run/clicked transaction
- confirms final Decision_JSON is saved
- confirms final Action_Decision_JSON is saved
- confirms final Action_Runtime_Plan_JSON is saved
- confirms unexpected keyword argument error is absent
- confirms name 'solver_preflop_bridge_contract' is not defined error is absent
- records known V2.14 gap: final Solver_Preflop bridge may be skipped when Final Clear_JSON already contains click_result
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.12.0
Snapshot display transaction integration audit:
- adds tools/run_v2_12_snapshot_display_transaction_integration_audit.py
- adds tests/test_v2_12_snapshot_display_transaction_integration_audit.py
- audits the production save_dark_and_clear_table_frame_json boundary
- confirms transaction_runtime_report.click_completed controls clear_json_save_allowed
- confirms click_result_for_clear is attached only when the transaction completed
- confirms dry_run/clicked completed runtime saves Final Clear_JSON
- confirms skipped/blocked runtime remains pending_only and does not save Final Clear_JSON
- confirms inactive frames save Dark_JSON only
- confirms duplicate/hard-stop frames stop before Pending/Decision/RuntimePlan and save Dark_JSON only
- isolates ClickExecutionGuard with an in-tool forced-pass stub so V2.12 tests only the transaction/save boundary
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.11.0
Snapshot transaction lifecycle audit:
- adds tools/run_v2_11_snapshot_transaction_lifecycle_audit.py
- adds tests/test_v2_11_snapshot_transaction_lifecycle_audit.py
- audits the full TableActionTransactionGate lifecycle without live UI, YOLO, screen capture or physical click
- confirms success path begin_analysis_cycle -> begin_action_cycle -> finalize_from_runtime -> click_done releases the table lock
- confirms early duplicate Active lifecycle blocks repeated heavy analysis
- confirms late duplicate action lifecycle blocks repeated action runtime
- confirms skipped runtime enters click_pending and can be released by observe_inactive
- confirms blocked runtime enters click_failed and requires abort/release before the table can process again
- confirms failed active finalization release aborts the lifecycle and allows the next Active cycle
- confirms release_on_inactive=False keeps the lifecycle lock active
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.10.0
Snapshot transaction source audit:
- adds tools/run_v2_10_snapshot_transaction_source_audit.py
- adds tests/test_v2_10_snapshot_transaction_source_audit.py
- audits TableActionTransactionGate.finalize_from_runtime as the source of clear_json_save_allowed and click_result_for_clear
- confirms display cycle derives clear_json_save_allowed from transaction_runtime_report.click_completed
- confirms click_result_for_clear is available only when click_completed is true
- confirms action_button dry_run/clicked/confirmed complete the transaction
- confirms skipped action_button runtime remains pending and does not publish Final Clear_JSON
- confirms blocked action_button runtime fails and does not publish Final Clear_JSON
- confirms service branch has priority over action_button when service status is completed or failed
- confirms dry_run_counts_as_completed=False prevents dry_run from completing the transaction
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.9.0
Snapshot finalization blocker audit:
- adds tools/run_v2_9_snapshot_finalization_blocker_audit.py
- adds tests/test_v2_9_snapshot_finalization_blocker_audit.py
- audits the central Final Clear_JSON blocker matrix without patching display_analysis_cycle.py
- confirms pending validation failure maps to pending_clear_json_contract_validation_failed
- confirms unfinished transaction maps to action_transaction_not_completed
- confirms missing click_result maps to missing_click_result_for_final_clear_json
- confirms ClickExecutionGuard failure maps to click_execution_guard_failed
- confirms duplicate click_result.decision_id maps to duplicate_click_result_reused
- confirms state-machine no-save path maps to pending_only / duplicate_or_not_advanced
- confirms final Clear_JSON validation failure maps to final_clear_json_contract_validation_failed
- confirms success path saves Final Clear_JSON after dry-run ClickExecutionGuard passes
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.8.0
Snapshot 6-slot isolation audit:
- adds tools/run_v2_8_snapshot_6slot_isolation_audit.py
- adds tests/test_v2_8_snapshot_6slot_isolation_audit.py
- builds synthetic preflop cases for table_01 through table_06 from existing Pending Clear_JSON templates
- validates table_slots.py exposes exactly six unique table slots, table indexes and slot bboxes
- confirms Solver_Preflop_Bridge is selected independently for every table slot
- confirms each slot gets a unique decision_id
- confirms Action_Runtime_Plan_JSON files are scoped under Action_Runtime_Plan_JSON/table_N
- confirms Final Clear_JSON files are scoped under Clear_JSON/table_N
- confirms technical table/slot_bbox data is not embedded into schema-safe Final Clear_JSON
- keeps slot bbox only in synthetic guard/runtime state for dry-run ClickExecutionGuard validation
- keeps real project, live UI, screen capture, YOLO and physical click disabled
## V2.7.0
Snapshot display finalization audit:
- adds tools/run_v2_7_snapshot_display_finalization_audit.py
- adds tests/test_v2_7_snapshot_display_finalization_audit.py
- audits the central Display finalization gates around Pending Clear_JSON -> Action_Runtime_Plan_JSON -> ClickExecutionGuard -> Final Clear_JSON
- confirms pending runtime plan status preview_not_saved_pending_only is expected when publish_files=False
- confirms final runtime plan publication works when publish_files=True
- confirms Solver_Preflop_Bridge is selected as runtime source
- confirms compact click_result remains schema-safe for Final Clear_JSON
- confirms final validation and Final Clear_JSON save path work without touching real project, live UI, screen capture, YOLO, or physical click
## V2.6.0
Snapshot Solver_Preflop Final Clear_JSON embedding check:
- adds tools/run_v2_6_snapshot_final_clear_embedding_check.py
- runs all snapshot Pending preflop Clear_JSON cases through:
  Pending Clear_JSON -> Solver_Preflop bridge -> V2.1 adapter
  -> Action_Runtime_Plan_JSON -> ClickExecutionGuard
  -> schema-safe compact click_result_v09 -> Final Clear_JSON
- verifies compact click_result is schema-safe for Clear_JSON
- verifies Final Clear_JSON validates and is saved under Clear_JSON_Final
- verifies saved Final Clear_JSON contains click_result and matches source frame/action/decision
- keeps full live UI, screen capture, YOLO, physical click, and real project mutation disabled
- adds test coverage for Final Clear_JSON embedding
- V2.6 fix: Clear_JSON.click_result does not embed click_completed because snapshot clear_json_builder forbids that key
- V2.6 count fix: final Clear_JSON file count is derived from actual saved final_clear.path values, because the snapshot final dir resolves to Clear_JSON rather than Clear_JSON_Final.

## V2.5.0
Snapshot Solver_Preflop dry-run click-result publication check.

## V2.4.0
Snapshot Solver_Preflop click-guard eligibility check.

## V2.3.0
Snapshot Solver_Preflop runtime plan publication check.

## V2.2.0
Snapshot Solver_Preflop runtime source multi-case check.

## V2.1.0
Snapshot Solver_Preflop runtime source dry-run ON.

## V2.0.0
Snapshot-only runtime source switch scaffold.

## V1.9.0
Snapshot cycle bridge smoke.

## V1.8.0
Snapshot-only main startup smoke.

## V1.7.0
Solver_Preflop bridge diagnostic publication toggle.

## V1.6.0
Display-cycle bridge embedding check.

## V1.5.0
Cold-vs-3bet range support.

## V1.4.0
Cold blind vs 3bet classifier fix.

## V1.3.0
Snapshot Clear_JSON bridge check.

## V1.2.0
PokerVision dry-run preflop solver bridge preview.

## V1.1.0
Imported PokerVisionFinalVersionNoSolver source snapshot.

## V1.0.1
Ignored preintegration output files.

## V1.0.0
Pre-integration stabilization.

## V0.9.0
PokerVision integration bridge preview.

## V0.8.1
Ignored generated solver output files.

## V0.8.0
CLI / file-output tools.

## V0.7.0
Solver response contract hardening.

## V0.6.0
All-in guard logic.

## V0.5.0
Defensive ranges.

## V0.4.0
Ranges foundation.

## V0.3.0
Preflop spot classifier expansion.

## V0.2.0
Clear_JSON adapter hardening and synthetic preflop cases.

## V0.1.1
Removed Python cache artifacts from Git.

## V0.1.0
Initial skeleton.



























## V2.35.0 — synthetic real-click gate E2E and controlled canonical raise gate fix

Date: 2026-05-30

Status: targeted proof passed.

Goal:
- Stop relying on repeated real-live runs for every raise-click fix.
- Add a synthetic real-click gate E2E harness that proves runtime would reach the physical mouse executor without moving the real mouse.
- Fix the actual live blocker found in artifacts: normalized `bet_raise` action and canonical `Bet/Raise` button were not accepted by controlled live click gate.
- Fix preflop `5bet` runtime mapping to `50% -> Raise`.

Changed:
- `config.py`
  - Allowed normalized `bet_raise` in the controlled V8.7 full-live click scope.
  - Allowed canonical `Bet/Raise` button in controlled live button allowlist.
- `logic/action_runtime_plan_builder.py`
  - Corrected `5bet` mapping from `98% -> Raise` to `50% -> Raise`.
- `logic/click_execution_guard.py`
  - Accepted `bet_raise` as a valid click-execution action.
- Added synthetic E2E harness:
  - `tools/run_v2_35_synthetic_real_click_gate_e2e.py`
  - `tests/test_v2_35_synthetic_real_click_gate_e2e.py`
  - `tests/fixtures/v2_35_synthetic_click_gate/`

Synthetic proof:
- fold -> FOLD -> gate passed -> clicked -> mouse spy called
- call -> Call -> gate passed -> clicked -> mouse spy called
- check -> Check -> gate passed -> clicked -> mouse spy called
- open_raise -> Bet/Raise -> gate passed -> clicked -> mouse spy called
- iso_raise -> 98% -> Bet/Raise -> gate passed -> clicked -> mouse spy called
- 3bet -> 98% -> Bet/Raise -> gate passed -> clicked -> mouse spy called
- 4bet -> 50% -> Bet/Raise -> gate passed -> clicked -> mouse spy called
- 5bet -> 50% -> Bet/Raise -> gate passed -> clicked -> mouse spy called
- all_in -> 98% -> Bet/Raise -> gate passed -> clicked -> mouse spy called

Negative proof:
- legacy stub bet_raise is blocked.
- wrong solver source bet_raise is blocked.
- missing Bet/Raise button is blocked.
- missing 98% for iso_raise is blocked.

Validation:
- `tools/run_v2_35_synthetic_real_click_gate_e2e.py`
  - `V2.35_SYNTHETIC_REAL_CLICK_GATE_E2E_OK = True`
- `pytest tests/test_v2_35_synthetic_real_click_gate_e2e.py -q`
  - `1 passed`

Notes:
- Full pytest is intentionally not claimed as closed in this checkpoint.
- Legacy snapshot/full-pytest fixture stabilization is a separate follow-up task and must not be mixed with this V2.35 click-gate checkpoint.


## V2.36.0 — synthetic Clear_JSON runtime chain E2E

Date: 2026-05-30

Status: targeted proof passed.

Goal:
- Prove the preflop runtime chain one level above V2.35.
- Start from synthetic Clear_JSON instead of direct click-runtime input.
- Validate Solver_Preflop bridge, v11 runtime selection, fake Action_Button execution, click_result, and synthetic Final publication proof without live UI, screen capture, YOLO, or real mouse movement.

Synthetic chain:
- synthetic Clear_JSON
- Solver_Preflop dryrun bridge
- solver_preflop_bridge_contract
- v11_stage1_runtime
- fake Action_Button result
- mouse executor spy
- click_result
- synthetic Final_Clear_JSON / JSON_Complete publication proof

Positive proof:
- fold -> clicked -> final saved -> mouse spy called
- call -> clicked -> final saved -> mouse spy called
- check -> clicked -> final saved -> mouse spy called
- open_raise -> Bet/Raise -> clicked -> final saved -> mouse spy called
- iso_raise -> 98% -> Bet/Raise -> clicked -> final saved -> mouse spy called
- 3bet -> 98% -> Bet/Raise -> clicked -> final saved -> mouse spy called
- 4bet -> 50% -> Bet/Raise -> clicked -> final saved -> mouse spy called
- 5bet_jam -> 98% -> Bet/Raise -> clicked -> final saved -> mouse spy called

Negative proof:
- missing Bet/Raise button blocks click and skips final publication.
- postflop Clear_JSON is skipped.
- Clear_JSON with existing click_result is skipped.

Validation:
- `tools/run_v2_36_synthetic_clear_json_runtime_chain.py`
  - `V2.36_SYNTHETIC_CLEAR_JSON_RUNTIME_CHAIN_OK = True`
- `pytest tests/test_v2_36_synthetic_clear_json_runtime_chain.py -q`
  - `1 passed`

Notes:
- Full pytest is intentionally not claimed as closed in this checkpoint.
- Legacy snapshot/full-pytest fixture stabilization remains separate.

## V2.37.0 — Solver_Preflop runtime lineage cleanup

Date: 2026-05-30

Status: targeted proof passed.

Goal:
- Make runtime artifacts clearly show Solver_Preflop lineage.
- Preserve original Solver_Preflop semantic raw actions through v11 runtime, click_result, and Action_Runtime_Plan_JSON.
- Prevent raise-family decisions from collapsing lineage to generic `raise`.

Changed:
- `runtime/v11_stage1_runtime.py`
  - Added `runtime_lineage` block.
  - Preserves original Solver_Preflop raw action:
    - open_raise
    - iso_raise
    - 3bet
    - 4bet
    - 5bet_jam
  - Links decision_id, selected source, bridge status, runtime action, click status, and click completion.

- `runtime/action_click_stub.py`
  - click_result now carries Solver_Preflop lineage:
    - solver_source
    - solver_status
    - solver_raw_action
    - solver_engine_action
    - solver_fingerprint
    - source_frame_id

- `logic/action_runtime_plan_builder.py`
  - Action_Runtime_Plan_JSON now carries Solver_Preflop lineage:
    - decision_id
    - solver_source
    - solver_raw_action
    - solver_engine_action
    - solver_fingerprint
    - runtime_source_selection
    - lineage

Added:
- `tools/run_v2_37_lineage_cleanup_audit.py`
- `tests/test_v2_37_lineage_cleanup_audit.py`

Validation:
- `tools/run_v2_37_lineage_cleanup_audit.py`
  - `V2.37_LINEAGE_CLEANUP_AUDIT_OK = True`
- `pytest tests/test_v2_37_lineage_cleanup_audit.py -q`
  - `1 passed`

Proof:
- Runtime lineage OK for:
  - fold
  - call
  - check
  - open_raise
  - iso_raise
  - 3bet
  - 4bet
  - 5bet_jam
- Runtime plan lineage OK for:
  - open_raise
  - iso_raise
  - 4bet
  - 5bet
  - fold

Notes:
- Full pytest is intentionally not claimed as closed in this checkpoint.
- Legacy snapshot/full-pytest fixture stabilization remains separate.

## V2.38.0 — synthetic lifecycle regression

Date: 2026-05-30

Status: targeted proof passed.

Goal:
- Prove PokerVision preflop lifecycle behavior synthetically without live UI, screen capture, YOLO, or real mouse movement.
- Cover duplicate Active suppression, retry policy, transaction lifecycle, dry-run completion, Final publication gating, and no-repeat click behavior.

Proof:
- ActionEventGate duplicate/inactive release works.
- V2.30 duplicate Active retry policy works:
  - unfinished duplicate allows retry;
  - duplicate with runtime_plan blocks retry;
  - duplicate with final_clear blocks retry;
  - non-duplicate blocks retry.
- TableActionTransaction lifecycle works:
  - second analysis blocked while lifecycle is open;
  - abort releases lifecycle;
  - clicked completion releases lifecycle;
  - blocked click does not publish Final Clear_JSON;
  - failed finalization release works;
  - inactive release works.
- Dry-run completion policy works.
- Same decision_id no-repeat guard blocks second click.

Validation:
- `tools/run_v2_38_synthetic_lifecycle_regression.py`
  - `V2.38_SYNTHETIC_LIFECYCLE_REGRESSION_OK = True`
- `pytest tests/test_v2_38_synthetic_lifecycle_regression.py -q`
  - `1 passed`

Notes:
- Full pytest is intentionally not claimed as closed in this checkpoint.
- Legacy snapshot/full-pytest fixture stabilization remains separate.

## V2.39.0 — preflop spot-classifier no-raise fallback cleanup

Date: 2026-05-30

Status: targeted proof passed.

Goal:
- Improve Solver_Preflop decision quality before full live mode.
- Stop obvious no-raise/limp/check spots from falling into unknown_no_raise_preflop_spot.
- Correct positional inference for final commitments where Hero is the threebettor facing a 4bet.

Changed:
- `solver_preflop/spot_classifier.py`
  - SB blind-only 0.5bb vs limper(s) is classified as limp/isolation spot, not unknown.
  - BB no-raise/no-limper/to_call=0 is classified as `bb_unopened_option_no_raise`.
  - Added positional two-level 4bet inference:
    - CO=22, BTN Hero=9 is inferred as CO open -> BTN 3bet -> CO 4bet.
    - Hero BTN becomes `threebettor_vs_normal_4bet`, not `opener_vs_normal_3bet`.

- `solver_preflop/range_engine.py`
  - `bb_unopened_option_no_raise` maps to guarded default check.

Added:
- `tests/fixtures/v2_39_spot_classifier_no_raise/cases.json`
- `tools/run_v2_39_spot_classifier_no_raise_audit.py`
- `tests/test_v2_39_spot_classifier_no_raise_audit.py`

Validation:
- `tools/run_v2_39_spot_classifier_no_raise_audit.py`
  - `V2.39_SPOT_CLASSIFIER_NO_RAISE_AUDIT_OK = True`
- `pytest tests/test_v2_39_spot_classifier_no_raise_audit.py -q`
  - `1 passed`

Proof:
- BB vs SB limp -> check.
- BB option vs limper -> check.
- BTN iso vs limper -> iso_raise.
- SB iso vs limper -> iso_raise.
- SB weak vs limper -> fold, not unknown.
- BB unopened option -> check.
- CO unopened AKo -> open_raise.
- BB blind vs BTN open AKo -> 3bet.
- CO opener vs BTN 3bet AKo -> 4bet.
- BTN threebettor vs CO 4bet AKo -> 5bet_jam.
- SB cold vs UTG open + CO 3bet T7o -> fold.

Notes:
- Full pytest is intentionally not claimed as closed in this checkpoint.
- Legacy snapshot/full-pytest fixture stabilization remains separate.

## V2.40.0 вЂ” real Clear_JSON adapter fixture audit

Date: 2026-05-30

Status: targeted proof passed.

Goal:
- Validate Solver_Preflop adapter/classifier/decision behavior on real/live-like Clear_JSON artifacts.
- Prove real saved JSON files can pass through:
  - clear_json_adapter
  - spot_classifier
  - decision_engine
  - Solver_Preflop bridge payload
- Keep this stage fully offline: no live room, no screen capture, no YOLO, no real mouse movement.

Validation:
- `tools/run_v2_40_real_clear_json_adapter_audit.py`
  - `V2.40_REAL_CLEAR_JSON_ADAPTER_AUDIT_OK = True`
- `pytest tests/test_v2_40_real_clear_json_adapter_audit.py -q`
  - `1 passed`

Proof cases:
- live_current_table_01_hand_75_sb_vs_btn_open_q3o -> blind_vs_open -> fold.
- live_current_table_01_hand_93_utg_unopened_q2o_fold -> unopened -> fold.
- live_current_table_02_hand_29_bb_option_limp_j7o -> bb_option_vs_1_limper -> check.
- v227_table_01_hand_21_sb_cold_vs_3bet_t7o_fold -> cold_vs_3bet_or_higher -> fold.
- v227_table_03_hand_09_sb_vs_btn_open_j9o_fold -> blind_vs_open -> fold.
- v227_table_03_hand_30_mp_unopened_32o_fold -> unopened -> fold.
- v227_table_02_hand_30_final_with_click_result_rejected -> rejected because Clear_JSON already has click_result.
- v228_table_01_hand_29_flop_rejected -> rejected because street is not preflop.

Notes:
- Full pytest is intentionally not claimed as closed in this checkpoint.
- Live detector/button proof remains V2.41 and requires running the poker room/live mode.

## V2.41.0 вЂ” safe_fallback runtime fold compatibility

Date: 2026-05-30

Status: targeted proof passed.

Goal:
- Fix live spots where Solver_Preflop returns diagnostic `raw_action=safe_fallback`.
- Preserve safe_fallback as lineage/diagnostic information.
- Prevent v11 runtime from rejecting fallback decisions as unknown runtime actions.
- Make runtime receive a valid safe action: `engine_action=fold`, `click_sequence=["FOLD"]`.

Changed:
- `solver_preflop/decision_engine.py`
  - Range-engine unsafe/unsupported nodes now keep `raw_action=safe_fallback`, but expose runtime-safe `engine_action=fold`.
  - Solver input errors now keep `raw_action=safe_fallback`, but expose runtime-safe `engine_action=fold`.
  - Fallback click sequence is now direct `["FOLD"]` for real-live safety.

Added:
- `tools/run_v2_41_safe_fallback_runtime_fold_audit.py`
- `tests/test_v2_41_safe_fallback_runtime_fold_audit.py`

Validation:
- `tools/run_v2_41_safe_fallback_runtime_fold_audit.py`
  - `V2.41_SAFE_FALLBACK_RUNTIME_FOLD_AUDIT_OK = True`
- `pytest tests/test_v2_41_safe_fallback_runtime_fold_audit.py -q`
  - `1 passed`

Proof:
- Solver decision keeps `status=fallback`.
- Solver decision keeps `raw_action=safe_fallback`.
- Solver decision exposes `engine_action=fold`.
- Solver click sequence is `["FOLD"]`.
- Bridge keeps `raw_action=safe_fallback`.
- Bridge exposes `engine_action=fold`.
- v11 runtime extracts valid `action=fold`.
- v11 runtime still keeps `raw_action=safe_fallback` for lineage.
- v11 runtime click sequence is `["FOLD"]`.

Notes:
- This intentionally does not change blind/position recognition.
- This fixes fallback execution policy only: if state is ambiguous or wrong, runtime now folds safely instead of failing with unknown action.
- Full pytest is intentionally not claimed as closed in this checkpoint.
