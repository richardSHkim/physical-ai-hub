.PHONY: build-piper build-openpi build-gr00t build-leisaac build-all \
       teleop record \
       train-openpi train-gr00t \
       server-openpi server-gr00t server-down \
       eval \
       rollout-openpi rollout-gr00t \
       submodule-init submodule-status \
       shell-piper shell-openpi shell-gr00t

# ── Docker 빌드 ───────────────────────────────
build-piper:
	docker compose build piper

build-openpi:
	docker compose build openpi

build-gr00t:
	docker compose build gr00t

build-leisaac:
	docker compose build leisaac

build-all:
	docker compose build

# ── 데이터 수집 ───────────────────────────────
teleop:
	bash scripts/collect/teleop_piper.sh

record:
	bash scripts/collect/record_piper.sh

# ── 학습 ──────────────────────────────────────
train-openpi:
	bash scripts/train/train_openpi.sh

train-gr00t:
	bash scripts/train/train_gr00t.sh

# ── Inference 서버 ────────────────────────────
server-openpi:
	docker compose up -d openpi

server-gr00t:
	docker compose up -d gr00t

server-down:
	docker compose down

# ── Eval ──────────────────────────────────────
eval:
	bash scripts/eval/run_leisaac.sh

# ── Rollout ───────────────────────────────────
rollout-openpi:
	bash scripts/rollout/rollout_openpi.sh

rollout-gr00t:
	bash scripts/rollout/rollout_gr00t.sh

# ── Submodule ─────────────────────────────────
submodule-init:
	git submodule update --init --recursive

submodule-status:
	git submodule status

# ── 개발 셸 ──────────────────────────────────
shell-piper:
	docker compose run --rm piper bash

shell-openpi:
	docker compose run --rm openpi bash

shell-gr00t:
	docker compose run --rm gr00t bash
