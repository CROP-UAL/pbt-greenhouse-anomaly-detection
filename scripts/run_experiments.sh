#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src:${ROOT_DIR}/config:${PYTHONPATH:-}"

cd "${ROOT_DIR}"

MODE="${1:-validate}"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Neither python3 nor python was found on PATH." >&2
    exit 127
  fi
fi

case "${MODE}" in
  validate)
    "${PYTHON_BIN}" scripts/validate_repository.py
    ;;
  availability)
    "${PYTHON_BIN}" -m pbt_campaign.availability_audit
    ;;
  campaign)
    "${PYTHON_BIN}" -m pbt_campaign.run_pbt_campaign
    ;;
  posthoc)
    "${PYTHON_BIN}" -m pbt_campaign.posthoc_analysis
    ;;
  figures)
    "${PYTHON_BIN}" results/pbt_campaign/campaign_20260928_150110/posthoc_analysis/plot_counterexample_failure_modes.py
    "${PYTHON_BIN}" results/pbt_campaign/campaign_20260928_150110/posthoc_analysis/plot_rq3_noise_boundary.py
    "${PYTHON_BIN}" results/pbt_campaign/campaign_20260928_150110/posthoc_analysis/plot_rq3_ss_boundary.py
    "${PYTHON_BIN}" results/pbt_campaign/campaign_20260928_150110/posthoc_analysis/plot_rq3_cd_boundary.py
    ;;
  reproduce)
    "${PYTHON_BIN}" -m pbt_campaign.availability_audit
    "${PYTHON_BIN}" -m pbt_campaign.run_pbt_campaign
    "${PYTHON_BIN}" -m pbt_campaign.posthoc_analysis
    ;;
  *)
    echo "Usage: scripts/run_experiments.sh {validate|availability|campaign|posthoc|figures|reproduce}" >&2
    exit 2
    ;;
esac
