# Version history

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












