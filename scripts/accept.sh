#!/bin/sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/.."
case "${1:-}" in ''|--browser) ;; *) echo 'Usage: sh scripts/accept.sh [--browser]' >&2; exit 2 ;; esac
python3 -B - <<'PY_STORAGE_GUARD'
import os
from pathlib import Path
import sys

def fail(reason):
    print('外置存储检查失败（' + reason + '）；请通过 python3 -B /Volumes/资源库/我的资源/回滚点/工具/run-with-storage.py --project /Users/carmen/Desktop/星系 -- sh scripts/accept.sh [--browser] 运行。', file=sys.stderr)
    sys.exit(2)

if not os.path.ismount('/Volumes/资源库'):
    fail('资源库未挂载')
root = Path('/Volumes/资源库/我的资源/回滚点').resolve()
if not root.is_dir() or not os.access(root, os.W_OK):
    fail('资源库目标不可写')
for name in ('CL_ARTIFACTS', 'CL_SHOTS', 'CL_ROLLBACK', 'TMPDIR'):
    value = os.environ.get(name)
    if not value or not Path(value).is_absolute():
        fail(name + ' 未由统一入口设置')
    try:
        path = Path(value).resolve(strict=True)
        path.relative_to(root)
    except (OSError, ValueError):
        fail(name + ' 不在真实外置存储内')
    if not path.is_dir() or not os.access(path, os.W_OK):
        fail(name + ' 目标不是可写目录')
PY_STORAGE_GUARD
ACCEPT_LOGS="$(mktemp -d "${TMPDIR:-/tmp}/castline-accept.XXXXXX")"
ACCEPT_TOTAL=0
ACCEPT_FAILED=0
trap 'exit 130' INT
trap 'exit 143' TERM
run() {
  ACCEPT_TOTAL=$((ACCEPT_TOTAL + 1))
  accept_started=$(date +%s)
  accept_log="$ACCEPT_LOGS/$ACCEPT_TOTAL.log"
  printf '[%s] %s\n' "$ACCEPT_TOTAL" "$*"
  if "$@" > "$accept_log" 2>&1; then
    printf 'PASS · %ss · %s\n' "$(($(date +%s) - accept_started))" "$accept_log"
  else
    accept_code=$?
    ACCEPT_FAILED=$((ACCEPT_FAILED + 1))
    printf 'FAIL · exit %s · %s\n' "$accept_code" "$accept_log"
    tail -40 "$accept_log"
    printf '%s\t%s\t%s\n' "$ACCEPT_TOTAL" "$accept_code" "$*" >> "$ACCEPT_LOGS/failures.tsv"
  fi
}
ATLAS_BASE="${ATLAS_BASE:-http://127.0.0.1:8000}"
ATLAS_NODE="${ATLAS_NODE:-$(command -v node || true)}"
if [ -z "$ATLAS_NODE" ]; then
  _nb=/Users/carmen/.workbuddy/binaries/node
  if [ -x "$_nb/versions/current/bin/node" ]; then
    ATLAS_NODE="$_nb/versions/current/bin/node"
  elif [ -d "$_nb/versions" ]; then
    _cand=$(ls -1 "$_nb/versions" 2>/dev/null | grep -E '^[0-9]' | sort -V | tail -1)
    [ -n "$_cand" ] && [ -x "$_nb/versions/$_cand/bin/node" ] && ATLAS_NODE="$_nb/versions/$_cand/bin/node"
  fi
fi
ATLAS_JSC="${ATLAS_JSC:-/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc}"
if [ -n "$ATLAS_NODE" ] && [ -x "$ATLAS_NODE" ]; then
  case ":$PATH:" in
    *":$(dirname "$ATLAS_NODE"):"*) ;;
    *) PATH="$(dirname "$ATLAS_NODE"):$PATH" ;;
  esac
  export PATH ATLAS_NODE
fi
if [ -z "$ATLAS_NODE" ] || [ ! -x "$ATLAS_NODE" ]; then
  echo 'Node missing: set ATLAS_NODE to a Node 22+ executable.' >&2
  echo "  （已尝试：PATH 上的 node；/Users/carmen/.workbuddy/binaries/node/versions/current/bin/node；versions/ 下最高版本）" >&2
  exit 2
fi
if [ ! -x "$ATLAS_JSC" ]; then
  echo 'JavaScriptCore missing: set ATLAS_JSC to the jsc executable.' >&2
  exit 2
fi
run python3 tests/source_contract.py
run python3 tests/source_index_contract.py
run python3 -B tests/schema_migration_contract.py
run python3 tests/deep_client_contract.py
run python3 -B tests/http_boundary_contract.py
run python3 -B tests/narrative_enrichment_contract.py
run python3 -B tests/narrative_relation_contract.py
run python3 -B tests/narrative_context_contract.py
run python3 -B tests/narrative_gold_eval_contract.py
run python3 -B tests/task_state_machine_contract.py
run python3 -B tests/narrative_layers_contract.py
run python3 -B tests/dna_census_contract.py
run python3 -B tests/quote_fidelity_contract.py
run python3 -B tests/data_safety_contract.py
run python3 -B tests/error_recovery_contract.py
run "$ATLAS_NODE" tests/material_layers_contract.js
run python3 -s tools/plan100/material_layer_inventory.py --check
run "$ATLAS_NODE" tests/journey_timeline_contract.js
run python3 -B tests/reviewed_publish_contract.py
run python3 -B tests/state_source_boundary_contract.py
run python3 -B tests/headless_health_contract.py
run python3 -B tests/test_api_compatibility.py
run "$ATLAS_NODE" tests/narrative_provenance_regression.js
run "$ATLAS_NODE" tests/narrative_reading_provenance_contract.js
run "$ATLAS_NODE" tests/sky_search_contract.js
run "$ATLAS_NODE" tests/sky_enrich_contract.js
run "$ATLAS_NODE" tests/sky_event_player_contract.js
run "$ATLAS_NODE" tests/sky_scrub_chapters_contract.js
run "$ATLAS_NODE" tests/sky_beam_fx_contract.js
run "$ATLAS_NODE" tests/sky_position_label_contract.js
run "$ATLAS_NODE" tests/sky_task_status_contract.js
run "$ATLAS_NODE" tests/sky_chapter_axis_contract.js
run python3 -B -s tests/p2_branch_reconcile.py --ratchet
run python3 -B -s tests/p2_alias_identity_contract.py --ratchet
run python3 -B -s tests/p2_library_version_choice.py --ratchet
run python3 -B -s tests/p2_four_hard_cases_contract.py
run python3 -B -s tests/p2_coverage_layers.py
run python3 -B -s tests/p3_unit_ledger_contract.py
run "$ATLAS_NODE" tests/sky_event_claim_contract.js
run "$ATLAS_NODE" tests/sky_line_provenance_contract.js
run "$ATLAS_NODE" tests/sky_causal_type_contract.js
run "$ATLAS_NODE" tests/sky_foreshadow_stage_contract.js
run "$ATLAS_NODE" tests/sky_state_transition_contract.js
run "$ATLAS_NODE" tests/sky_knowledge_view_contract.js
run "$ATLAS_NODE" tests/sky_relation_scope_contract.js
run "$ATLAS_NODE" tests/sky_world_object_contract.js
run "$ATLAS_NODE" tests/sky_theme_tension_contract.js
run "$ATLAS_NODE" tests/sky_name_budget_contract.js
run "$ATLAS_NODE" tests/sky_selection_model_contract.js
run "$ATLAS_NODE" tests/sky_search_index_contract.js
run "$ATLAS_NODE" tests/sky_reading_voice_contract.js
run "$ATLAS_NODE" tests/sky_gold_throughput_contract.js
run "$ATLAS_NODE" tests/sky_view_contract.js
run "$ATLAS_NODE" tests/sky_disclosure_contract.js
run "$ATLAS_NODE" tests/sky_channel_registry_contract.js
run python3 -B -s tests/p3_task_five_fields_contract.py --ratchet
run python3 -B -s tests/p2_source_dedup_contract.py --skip-http
run "$ATLAS_NODE" tests/sky_compass_evidence_contract.js
run "$ATLAS_NODE" tests/sky_deconstruction_contract.js
run "$ATLAS_NODE" tests/sky_causal_architecture_contract.js
run "$ATLAS_NODE" tests/sky_state_reading_contract.js
run "$ATLAS_NODE" tests/sky_foreshadow_lifecycle_contract.js
run "$ATLAS_NODE" tests/sky_evidence_export_contract.js
run "$ATLAS_NODE" tests/sky_relation_honesty_contract.js
run "$ATLAS_NODE" tests/storyline_honesty_contract.js
run "$ATLAS_NODE" tests/sky_layout_parent_contract.js
run "$ATLAS_NODE" tests/sky_help_registry_contract.js
run "$ATLAS_NODE" tests/sky_dna_contract.js
run "$ATLAS_NODE" tests/sky_dna_carve_contract.js
run "$ATLAS_NODE" tests/sky_identity_projection_contract.js
run "$ATLAS_NODE" tests/sky_channel_semantics_contract.js
run "$ATLAS_NODE" tests/sky_legend_parity_contract.js
run "$ATLAS_NODE" tests/sky_reduced_motion_contract.js
run "$ATLAS_NODE" tests/ingest_regression.js
run "$ATLAS_NODE" tests/scene_msaa_resolve_contract.js
run "$ATLAS_NODE" tests/scene_fps_wall_clock_contract.js
run "$ATLAS_NODE" tests/atlas_source_contract.js
run "$ATLAS_NODE" tests/schema_migration_contract.js
run "$ATLAS_NODE" tests/narrative_evidence_contract.js
run "$ATLAS_NODE" tests/deep_client_contract.js
run "$ATLAS_NODE" tests/atlas_workspace_state_contract.js
run "$ATLAS_NODE" tests/sky_cloud_noise_contract.js
run "$ATLAS_NODE" tests/sky_cloud_shape_contract.js
run "$ATLAS_NODE" tests/sky_cloud_density_contract.js
run "$ATLAS_NODE" tests/sky_cloud_native_rt_contract.js
run "$ATLAS_NODE" tests/sky_cloud_profile_contract.js
run "$ATLAS_NODE" tests/sky_nebula_rttype_contract.js
run "$ATLAS_NODE" tests/sky_plasma_switch_contract.js
run "$ATLAS_NODE" tests/sky_chrome_insets_contract.js
run "$ATLAS_NODE" tests/sky_snapshot_contract.js
run "$ATLAS_NODE" tests/sky_fullscreen_contract.js
run "$ATLAS_NODE" tests/sky_disc_number_clearance_contract.js
run "$ATLAS_NODE" tests/sky_tug_camera_contract.js
run "$ATLAS_NODE" tests/sky_quality_context_contract.js
run "$ATLAS_NODE" tests/scene_buffer_sizing_contract.js
run "$ATLAS_NODE" tests/sky_boot_layout_contract.js
run "$ATLAS_NODE" tests/scene_motion_clock_contract.js
run "$ATLAS_NODE" tests/crown_motion_contract.js
run "$ATLAS_NODE" tests/gem_birefringence_contract.js
run "$ATLAS_NODE" tests/gem_microdetail_bandwidth_contract.js
run "$ATLAS_NODE" tests/scene_camera_pose_contract.js
run "$ATLAS_NODE" tests/sky_openfuse_badges_contract.js
run "$ATLAS_NODE" tests/boot_errors_contract.js
run "$ATLAS_NODE" tests/sky_follow_camera_contract.js
run "$ATLAS_NODE" tests/sky_resume_contract.js
run "$ATLAS_NODE" tests/sky_event_label_contract.js
run python3 -B -s tests/p1_6_publisher_contract.py
run python3 -B -s tests/p1_4_ordering_contract.py
run "$ATLAS_NODE" tests/p1_reference_integrity_contract.js
run "$ATLAS_NODE" tests/p1_anchor_trust_contract.js
run "$ATLAS_NODE" tests/sky_bookmarks_contract.js
run "$ATLAS_NODE" tests/sky_switcher_contract.js
run "$ATLAS_NODE" tests/sky_readscale_contract.js
run "$ATLAS_NODE" tests/sky_status_label_contract.js
run "$ATLAS_NODE" tests/llm_errors_contract.js
run "$ATLAS_NODE" tests/api_profile_ops_contract.js
run "$ATLAS_JSC" tests/atlas_lifecycle_contract.js
run "$ATLAS_JSC" tests/domain_alignment_contract.js
run "$ATLAS_JSC" tests/scene_camp_halo_contract.js
run "$ATLAS_JSC" tests/scene_camp_halo_smoke_contract.js
run "$ATLAS_JSC" tests/annulus_frame_cache_contract.js
run "$ATLAS_JSC" tests/gem_stage_contract.js
run "$ATLAS_JSC" tests/atlas_world_contract.js
run "$ATLAS_JSC" tests/atlas_fallback_contract.js
run python3 -s scripts/gen-tokens.py
run python3 tests/css_lint.py --ratchet
run python3 -B tests/contrast_audit.py --out "$ACCEPT_LOGS/contrast-report.json"
run python3 tests/inline_style_lint.py
run python3 tests/motion_lint.py --strict
run python3 tests/type_lint.py
run python3 tests/script_load_audit.py
run python3 tests/script_load_audit.py --self-test
run python3 tests/version_stamp.py --check
case "${1:-}" in
  '') ;;
  --browser)
    export CL_GPU="${CL_GPU:-1}"
run env CL_GPU="${CL_GPU:-1}" CL_BASE="$ATLAS_BASE" python3 -B -s tests/p4_8_journey_contract.py
run env CL_GPU="${CL_GPU:-1}" CL_BASE="$ATLAS_BASE" python3 -B -s tests/p1_2_order_semantics_contract.py --ratchet
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_util.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_shell.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_shell_lifecycle.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_interaction_access_browser.py --base "$ATLAS_BASE" --out "$ACCEPT_LOGS/interaction"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_reading_reflow_browser.py --base "$ATLAS_BASE" --out "$ACCEPT_LOGS/reading-reflow"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_search_dual_browser.py --base "$ATLAS_BASE" --out "$ACCEPT_LOGS/search"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_story_browser.py --base "$ATLAS_BASE" --out "$ACCEPT_LOGS/story"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p1_position_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p1-position"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p2_task_status_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p2-task-status"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p3_event_claim_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p3-event-claim"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p3_line_provenance_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p3-line-provenance"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p3_causal_type_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p3-causal-type"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p3_foreshadow_stage_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p3-foreshadow"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p3_state_transition_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p3-state-transition"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p3_knowledge_view_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p3-knowledge-view"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p3_relation_scope_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p3-relation-scope"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p3_world_object_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p3-world-object"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p3_theme_tension_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p3-theme-tension"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p4_name_budget_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p4-name-budget"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p4_selection_model_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p4-selection-model"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p4_search_index_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p4-search-index"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p4_reading_voice_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p4-reading-voice"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p4_view_contract_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p4-view-contract"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p4_disclosure_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p4-disclosure"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p4_channel_registry_render_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/p4-channel-registry"
    run python3 -B -s tests/p2_source_dedup_contract.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/p8_perf_baseline.py --base "$ATLAS_BASE" --out "${CL_ARTIFACTS:-/tmp/castline-artifacts}/p8-perf"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_journey_browser.py
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_enrich_browser.py --base "$ATLAS_BASE" --out "$ACCEPT_LOGS/enrichment"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_label_guard.py --base "$ATLAS_BASE" --out "$ACCEPT_LOGS/labels"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_keyboard_owner.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/keyboard-owner-$(date +%s)"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_menu_keyboard.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/menu-keyboard-$(date +%s)-$$"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_modal_gate.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/modal-gate-$(date +%s)-$$"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/ops_more_menu.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/ops-more-menu-$(date +%s)-$$"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_home_frame.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/home-frame-$(date +%s)-$$"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_field.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_lab.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/scene_motion_browser.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/motion-clock-normal"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/scene_motion_browser.py --base "$ATLAS_BASE" --initial-reduced --out "${CL_SHOTS:-/tmp/castline-shots}/motion-clock-initial"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_deep.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_view.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_deck.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_groupdeck.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_loader.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_opening.py --base "$ATLAS_BASE" --book dafeng
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_depth.py --base "$ATLAS_BASE"
    run env CL_URL="$ATLAS_BASE/" python3 tests/atlas_lifecycle_contract.py
    run env CL_URL="$ATLAS_BASE/" python3 tests/annulus_frame_cache_contract.py
    run env CL_URL="$ATLAS_BASE/" python3 tests/gem_stage_contract_browser.py
    run env CL_URL="$ATLAS_BASE/" python3 tests/annulus_rotation.py --size 1200x800
    run env CL_URL="$ATLAS_BASE/" python3 tests/annulus_rotation.py --size 390x844
    run env CL_URL="$ATLAS_BASE/" python3 tests/gem_rotation_browser.py
    run env CL_URL="$ATLAS_BASE/" python3 tests/camp_world_browser.py
    run python3 tests/domain_alignment_browser.py --base "$ATLAS_BASE"
    run python3 tests/domain_alignment_browser.py --base "$ATLAS_BASE" --size 1131x826
    run python3 tests/domain_alignment_browser.py --base "$ATLAS_BASE" --size 390x844
    run python3 tests/gem_preview_restore_browser.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/design_stack_probe.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/design-stack"
    run python3 tests/scene_frame_render_browser.py --base "$ATLAS_BASE"
    run python3 tests/atlas_workspace_browser.py --base "$ATLAS_BASE"
    run python3 tests/atlas_aggregate_browser.py --base "$ATLAS_BASE"
    run python3 tests/atlas_fallback_entry.py --url "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/atlas_lab_browser.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_satdrag.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_tug.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_constellation_preview.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_constellation_preview.py --base "$ATLAS_BASE" --size 390x844
    run env CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_constellation_preview.py --base "$ATLAS_BASE" --reduce
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_dial.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_field_layer.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_nebula.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_network.py --base "$ATLAS_BASE" --out "$CL_ARTIFACTS/sky-network"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_disc_threads.py --base "$ATLAS_BASE" --out "$CL_ARTIFACTS/sky-disc-threads"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_ui_finish.py --base "$ATLAS_BASE" --out "$CL_ARTIFACTS/sky-ui-finish"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_upright.py --base "$ATLAS_BASE" --out "$CL_ARTIFACTS/sky-upright"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_disc_number_clearance.py --base "$ATLAS_BASE" --out "$CL_ARTIFACTS/sky-disc-number-clearance"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_label_density.py --base "$ATLAS_BASE" --out "$CL_ARTIFACTS/sky-label-density"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_meteor.py --base "$ATLAS_BASE" --out "$CL_ARTIFACTS/sky-meteor"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_beam_edges.py --base "$ATLAS_BASE"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_axis_layout.py --base "$ATLAS_BASE" --out "$CL_ARTIFACTS/sky-axis-layout"
    run env CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_axis_legibility.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/axis-legibility"
    ;;
  *) echo 'Usage: sh scripts/accept.sh [--browser]' >&2; exit 2 ;;
esac
printf 'ACCEPT: %s/%s passed · logs: %s\n' "$((ACCEPT_TOTAL - ACCEPT_FAILED))" "$ACCEPT_TOTAL" "$ACCEPT_LOGS"
if [ "$ACCEPT_FAILED" -ne 0 ]; then
  echo 'FAILED CHECKS:'
  cat "$ACCEPT_LOGS/failures.tsv"
  exit 1
fi
echo 'ATLAS REFACTOR CONTRACTS PASSED (not a full-novel/real-device/art-direction sign-off)'
