#!/usr/bin/env bash
# CONTAINER: gr00t
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../envs/.env.gr00t"
set +a

GR00T_ROOT="$(cd "$(dirname "$0")/../../vla/Isaac-GR00T" && pwd)"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

DATASET_PATH="${GR00T_DATASET_PATH:-datasets/richardshkim/piper_banana_v2_v2.1}"
RUN_NAME="${GR00T_RUN_NAME:-gr00t_n_1d6_piper}"
OUTPUT_DIR="${GR00T_OUTPUT_DIR:-outputs/Isaac-GR00T}/${RUN_NAME}"
CONFIG_PATH="${GR00T_MODALITY_CONFIG_PATH:-vla/gr00t/tools/piper_modality_config.py}"
BASE_MODEL="${GR00T_BASE_MODEL:-nvidia/GR00T-N1.6-3B}"
NUM_GPUS="${GR00T_NUM_GPUS:-1}"
MAX_STEPS="${GR00T_MAX_STEPS:-2000}"
SAVE_STEPS="${GR00T_SAVE_STEPS:-2000}"
GLOBAL_BATCH_SIZE="${GR00T_GLOBAL_BATCH_SIZE:-32}"

# 절대경로 변환 (상대경로인 경우 PROJECT_ROOT 기준)
if [[ "${DATASET_PATH}" != /* ]]; then
    DATASET_PATH="${PROJECT_ROOT}/${DATASET_PATH}"
fi
if [[ "${CONFIG_PATH}" != /* ]]; then
    CONFIG_PATH="${PROJECT_ROOT}/${CONFIG_PATH}"
fi
if [[ "${OUTPUT_DIR}" != /* ]]; then
    OUTPUT_DIR="${PROJECT_ROOT}/${OUTPUT_DIR}"
fi

if [[ ! -f "${CONFIG_PATH}" ]]; then
    echo "[ERROR] Modality config not found at ${CONFIG_PATH}" >&2
    echo "  Create: vla/gr00t/tools/piper_modality_config.py" >&2
    exit 1
fi

exec "${GR00T_ROOT}/.venv/bin/python" \
    "${GR00T_ROOT}/gr00t/experiment/launch_finetune.py" \
    --base_model_path "${BASE_MODEL}" \
    --dataset_path "${DATASET_PATH}" \
    --modality_config_path "${CONFIG_PATH}" \
    --embodiment_tag NEW_EMBODIMENT \
    --num_gpus "${NUM_GPUS}" \
    --output_dir "${OUTPUT_DIR}" \
    --save_steps "${SAVE_STEPS}" \
    --save_total_limit 5 \
    --max_steps "${MAX_STEPS}" \
    --warmup_ratio 0.05 \
    --weight_decay 1e-5 \
    --learning_rate 1e-4 \
    --global_batch_size "${GLOBAL_BATCH_SIZE}" \
    --dataloader_num_workers 4 \
    --gradient_accumulation_steps 1 \
    --shard_size 1024 \
    --num_shards_per_epoch 100000 \
    --episode_sampling_rate 0.1 \
    --state_dropout_prob 0.0 \
    --tune_projector \
    --tune_diffusion_model \
    --color_jitter_params brightness 0.3 contrast 0.4 saturation 0.5 hue 0.08 \
    --use_wandb \
    "$@"
