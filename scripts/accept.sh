#!/bin/sh
# 项目验收：默认只跑离线契约 + 静态门；--browser 再跑真浏览器（星空壳 / 星域 / 预演实验室 / 星空光层 / 镜头 + 旧壳 ?shell=atlas 回归）。
# 不调用模型、不触发分析、不改 data/。用法：ATLAS_BASE=http://127.0.0.1:8765 sh scripts/accept.sh [--browser]
set -eu
cd "$(dirname "$0")/.."
ATLAS_BASE="${ATLAS_BASE:-http://127.0.0.1:8000}"
ATLAS_NODE="${ATLAS_NODE:-$(command -v node || true)}"
if [ -z "$ATLAS_NODE" ] && [ -x /Users/carmen/.workbuddy/binaries/node/versions/22.22.2-3/bin/node ]; then
  ATLAS_NODE=/Users/carmen/.workbuddy/binaries/node/versions/22.22.2-3/bin/node
fi
ATLAS_JSC="${ATLAS_JSC:-/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc}"
if [ -z "$ATLAS_NODE" ] || [ ! -x "$ATLAS_NODE" ]; then
  echo 'Node missing: set ATLAS_NODE to a Node 22+ executable.' >&2
  exit 2
fi
if [ ! -x "$ATLAS_JSC" ]; then
  echo 'JavaScriptCore missing: set ATLAS_JSC to the jsc executable.' >&2
  exit 2
fi
python3 tests/source_contract.py
python3 tests/deep_client_contract.py
"$ATLAS_NODE" tests/atlas_source_contract.js
"$ATLAS_NODE" tests/deep_client_contract.js
"$ATLAS_NODE" tests/atlas_workspace_state_contract.js
"$ATLAS_JSC" tests/atlas_lifecycle_contract.js
"$ATLAS_JSC" tests/domain_alignment_contract.js
"$ATLAS_JSC" tests/scene_camp_halo_contract.js
"$ATLAS_JSC" tests/scene_camp_halo_smoke_contract.js
"$ATLAS_JSC" tests/annulus_frame_cache_contract.js
"$ATLAS_JSC" tests/gem_stage_contract.js
"$ATLAS_JSC" tests/atlas_world_contract.js
"$ATLAS_JSC" tests/atlas_fallback_contract.js
python3 tests/css_lint.py --ratchet
python3 tests/inline_style_lint.py
python3 tests/motion_lint.py --strict
python3 tests/type_lint.py
python3 tests/script_load_audit.py
python3 tests/version_stamp.py --check
case "${1:-}" in
  '') ;;
  --browser)
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_util.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_shell.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_shell_lifecycle.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_keyboard_owner.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/keyboard-owner-$(date +%s)"
    CL_GPU="${CL_GPU:-1}" python3 -B -s tests/sky_home_frame.py --base "$ATLAS_BASE" --out "${CL_SHOTS:-/tmp/castline-shots}/home-frame-$(date +%s)-$$"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_field.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_lab.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_deep.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_view.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_deck.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_groupdeck.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_loader.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_opening.py --base "$ATLAS_BASE" --book dafeng
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_depth.py --base "$ATLAS_BASE"
    CL_URL="$ATLAS_BASE/" python3 tests/atlas_lifecycle_contract.py
    CL_URL="$ATLAS_BASE/" python3 tests/annulus_frame_cache_contract.py
    CL_URL="$ATLAS_BASE/" python3 tests/gem_stage_contract_browser.py
    CL_URL="$ATLAS_BASE/" python3 tests/annulus_rotation.py --size 1200x800
    CL_URL="$ATLAS_BASE/" python3 tests/annulus_rotation.py --size 390x844
    CL_URL="$ATLAS_BASE/" python3 tests/gem_rotation_browser.py
    CL_URL="$ATLAS_BASE/" python3 tests/camp_world_browser.py
    python3 tests/domain_alignment_browser.py --base "$ATLAS_BASE"
    python3 tests/domain_alignment_browser.py --base "$ATLAS_BASE" --size 1131x826
    python3 tests/domain_alignment_browser.py --base "$ATLAS_BASE" --size 390x844
    python3 tests/gem_preview_restore_browser.py --base "$ATLAS_BASE"
    python3 tests/scene_frame_render_browser.py --base "$ATLAS_BASE"
    python3 tests/atlas_workspace_browser.py --base "$ATLAS_BASE"
    python3 tests/atlas_aggregate_browser.py --base "$ATLAS_BASE"
    python3 tests/atlas_fallback_entry.py --url "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/atlas_lab_browser.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_satdrag.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_tug.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_dial.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_field_layer.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_nebula.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_network.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_disc_threads.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_ui_finish.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_upright.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_label_density.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_meteor.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_beam_edges.py --base "$ATLAS_BASE"
    CL_GPU="${CL_GPU:-1}" python3 -s tests/sky_axis_layout.py --base "$ATLAS_BASE"
    ;;
  *) echo 'Usage: sh scripts/accept.sh [--browser]' >&2; exit 2 ;;
esac
echo 'ATLAS REFACTOR CONTRACTS PASSED (not a full-novel/real-device/art-direction sign-off)'
