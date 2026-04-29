#!/usr/bin/env bash
# =============================================================================
# ACT (Action Chunking Transformer) training script for Piper + Tactile Pick
# =============================================================================
#
# Purpose:
#   Train an ACT policy on a small (~10 min) teleoperated dataset for
#   soft-object pick-and-place using the Piper arm with tactile feedback.
#
# Why ACT:
#   - Designed for low-data regimes (original paper: ~50 demos)
#   - Action chunking reduces compounding errors during grasp & place
#   - Pretrained ResNet18 provides strong visual priors
#   - VAE regularization prevents overfitting on tiny datasets
#
# Hardware assumed:
#   - Piper 6DOF + gripper follower arm (CAN bus)
#   - Piper leader arm for teleop
#   - 2x OpenCV cameras (top/wrist) + 1x Tactile camera
#
# Usage:
#   bash scripts/train_act_piper_tactile_pick.sh
#
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# USER CONFIGURATION -- edit these variables
# ---------------------------------------------------------------------------
DATASET_REPO_ID="your_username/piper_soft_pick_tactile"
DATASET_ROOT="/home/stouching/vla/repo/dataset/piper_soft_pick"
OUTPUT_DIR="/home/stouching/vla/repo/lerobot052base/outputs/train/act_piper_tactile_softpick"

# ---------------------------------------------------------------------------
# ACT hyper-parameters tuned for small-data soft-object picking
# ---------------------------------------------------------------------------
# NOTE: We keep the ACT defaults where they are already optimal for small data.
# Only override what matters for our task.

# Dataset settings
DATASET_ARGS=(
    --dataset.repo_id="${DATASET_REPO_ID}"
    --dataset.root="${DATASET_ROOT}"
    --dataset.streaming=false
)

# Training schedule
TRAIN_ARGS=(
    --steps=30000
    --batch_size=8
    --num_workers=4
    --save_freq=5000
    --log_freq=200
    --eval_freq=0
    --seed=42
)

# Output settings
OUTPUT_ARGS=(
    --output_dir="${OUTPUT_DIR}"
    --job_name=act_piper_tactile_softpick
    --save_checkpoint=true
)

# ACT policy knobs
# Action chunking: predict 100 steps, execute all 100 before re-query.
# For a 30 Hz dataset, 100 steps ≈ 3.3 seconds, enough for pick-and-place.
# VAE regularization is CRITICAL for small data -- keep enabled.
POLICY_ARGS=(
    --policy.type=act
    --policy.chunk_size=100
    --policy.n_action_steps=100
    --policy.use_vae=true
    --policy.kl_weight=10.0
)

# Logging
LOG_ARGS=(
    --wandb.enable=false
)

echo "=========================================="
echo "Starting ACT training for Piper + Tactile"
echo "Dataset: ${DATASET_REPO_ID}"
echo "Output:  ${OUTPUT_DIR}"
echo "=========================================="

uv run lerobot-train \
    "${DATASET_ARGS[@]}" \
    "${TRAIN_ARGS[@]}" \
    "${OUTPUT_ARGS[@]}" \
    "${POLICY_ARGS[@]}" \
    "${LOG_ARGS[@]}"

echo ""
echo "Training complete. Checkpoint saved to: ${OUTPUT_DIR}"
echo ""
echo "To evaluate / run inference:"
echo "  uv run lerobot-eval \\"
echo "      --policy.path=${OUTPUT_DIR}/checkpoints/last \\"
echo "      --dataset.repo_id=${DATASET_REPO_ID} \\"
echo "      ..."
