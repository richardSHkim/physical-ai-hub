# Physical AI Hub

로봇 학습 파이프라인 통합 허브 — 데이터 수집 → VLA 학습 → 시뮬레이션 평가 → 실물 롤아웃

## 지원 현황

| 구성 요소 | 지원 항목 | 상태 |
|---------|---------|------|
| 로봇 | Agilex PiPER (follower / leader / bi) | ✅ |
| VLA | OpenPI | ✅ |
| VLA | Isaac-GR00T | ✅ |
| 시뮬레이션 | LeIsaac (Isaac Sim) | ✅ |

## 퀵스타트

### 1. 클론 & 서브모듈

```bash
git clone --recurse-submodules <repo-url>
cd physical-ai-hub
```

### 2. 환경변수 설정

```bash
cp envs/.env.base.example envs/.env.base
# envs/.env.base 에 HF_TOKEN, WANDB_API_KEY 입력
```

### 3. Docker 빌드

```bash
docker compose build piper     # 로봇 제어
docker compose build openpi    # OpenPI 학습 & 서빙
docker compose build gr00t     # GR00T 학습 & 서빙
docker compose build leisaac   # Isaac Sim 시뮬레이션
```

## 파이프라인 흐름

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  1. 데이터    │ →  │  2. VLA 학습  │ →  │ 3. 시뮬평가   │ →  │ 4. 실물롤아웃 │
│  수집/텔레옵   │    │  (OpenPI등)  │    │  (LeIsaac)   │    │ (inference)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
 scripts/data/      scripts/vla/      scripts/simulation/ scripts/rollout/
```

### 1. 데이터 수집 (piper 컨테이너)

```bash
bash scripts/data/teleoperate_piper.sh
bash scripts/data/record_piper.sh
```

### 2. VLA 학습 (openpi 컨테이너)

```bash
bash scripts/vla/train_openpi.sh
```

### 3. 시뮬레이션 평가 (leisaac + openpi/gr00t 컨테이너)

piper task를 로드하려면 먼저 씬 에셋과 URDF 에셋을 준비합니다.

**1) 씬 에셋 다운로드** (HuggingFace)

```bash
huggingface-cli download \
    --local-dir simulation/leisaac \
    --include "assets/**" \
    LightwheelAI/leisaac_env
```

**2) PiPER URDF 에셋 복사** (piper_isaac_sim 서브모듈)

```bash
mkdir -p simulation/leisaac/assets/piper_description/urdf
cp -r simulation/piper_isaac_sim/piper_description/urdf/piper_description_v100_realsense_camera_v2 \
      simulation/leisaac/assets/piper_description/urdf/
```

```bash
bash scripts/vla/serve_openpi.sh          # 서버 기동
bash scripts/simulation/eval_leisaac.sh   # 시뮬레이션 평가
```

#### Isaac Sim CUDA/PhysX 트러블슈팅

다음과 같은 오류가 발생하면, 개별 로봇 asset 문제보다 `GPU PhysX / RTX / Omniverse` 런타임 상태 이상을 먼저 의심합니다.

- `PhysX error: Fetching GPU Narrowphase failed! 700`
- `cudaErrorIllegalAddress`
- `PhysX Internal CUDA error. Simulation cannot continue! Error code 700`
- `vkCreateRayTracingPipelinesKHR failed`
- `omni.physx.tensors.plugin` 연쇄 CUDA 오류

로그 해석 기준:

- `omni.physx.plugin`의 `CUDA error 700` 이후 `omni.physx.tensors.plugin` 메모리 할당 실패, 그리고 `RTX` / `Vulkan` / `ray tracing pipeline` 실패가 이어지면 런타임 문제일 가능성이 높습니다.
- 반대로 `prim not found`, `joint not found`, `invalid articulation`, `USD load` 실패처럼 asset 로딩 관련 오류가 먼저 나오면 asset 문제를 우선 확인합니다.

빠른 원인 분리:

- PiPER와 SO-101이 둘 다 같은 CUDA 오류로 실패하면 PiPER asset 자체보다는 Isaac Sim 런타임, GPU PhysX, RTX camera / Vulkan, Omniverse cache 상태를 먼저 봅니다.
- 카메라 없는 최소 GPU 예제는 정상인데 카메라를 켠 예제만 죽으면 RTX 렌더링 경로를 의심합니다.
- 카메라 없이도 바로 `PhysX error 700`이 나면 GPU PhysX 런타임 문제 쪽일 가능성이 큽니다.

가장 먼저 시도할 복구 명령:

```bash
pkill -9 -f isaac
pkill -9 -f omni
pkill -9 -f kit
pkill -9 -f simulation_app
pkill -9 -f python.sh
sleep 3
rm -rf /isaac-sim/kit/cache/Kit /tmp/OmniverseKit* /tmp/carb.*
```

런타임 문제를 빠르게 분리하려면, 이제 시뮬레이션 wrapper에서 디바이스와 카메라를 환경변수로 바로 바꿀 수 있습니다.

```bash
# 1) RTX 카메라 경로만 끄고 확인
LEISAAC_ENABLE_CAMERAS=0 bash scripts/simulation/zero_pose_leisaac.sh

# 2) GPU PhysX 자체가 문제인지 CPU로 확인
LEISAAC_DEVICE=cpu LEISAAC_ENABLE_CAMERAS=0 bash scripts/simulation/zero_pose_leisaac.sh

# 3) 평가 스크립트도 동일하게 적용 가능
LEISAAC_ENABLE_CAMERAS=0 bash scripts/simulation/eval_leisaac.sh
LEISAAC_DEVICE=cpu LEISAAC_ENABLE_CAMERAS=0 bash scripts/simulation/eval_leisaac.sh
```

해석 기준:

- `LEISAAC_ENABLE_CAMERAS=0`에서는 살고, 기본값(`LEISAAC_ENABLE_CAMERAS=1`)에서만 죽으면 RTX camera / rendering 경로를 우선 의심합니다.
- `LEISAAC_DEVICE=cpu LEISAAC_ENABLE_CAMERAS=0`에서도 죽으면 단순 GPU PhysX 문제보다 asset / task 초기화 쪽 로그를 다시 확인합니다.
- CPU + no-camera는 되는데 기본 GPU 모드에서만 `PhysX error 700`이 나면 GPU PhysX 또는 드라이버/캐시 상태 쪽 가능성이 큽니다.

1차 조치 후에도 동일하면 Omniverse 사용자 상태 디렉터리와 mount 상태를 점검합니다.

- `/root/.cache/ov`
- `/root/.nvidia-omniverse/config`
- `/root/.nvidia-omniverse/logs`
- `/root/.local/share/ov/data`

```bash
mount | grep -E '/root/.cache/ov|/root/.nvidia-omniverse|/root/.local/share/ov'
cat /proc/mounts | grep -E '/root/.cache/ov|/root/.nvidia-omniverse|/root/.local/share/ov'
```

주의할 점:

- 컨테이너를 새로 만들어도 host volume, bind mount, `/tmp`, 사용자 설정 디렉터리가 재사용되면 문제가 그대로 남을 수 있습니다.
- 비정상 종료 뒤에는 재실행 전에 프로세스 종료와 캐시 정리를 먼저 수행하는 편이 안전합니다.
- 장애가 재발하면 첫 치명 에러, 실행 명령, PiPER/SO-101 재현 여부, 캐시 정리 후 해결 여부를 함께 기록해두면 다음 분석이 빨라집니다.

실전 체크리스트:

1. 첫 에러가 `PhysX GPU ... 700`인지 확인
2. PiPER와 SO-101 둘 다 재현되는지 확인
3. Isaac/Omni 프로세스 정리
4. `Kit cache`와 `/tmp/carb.*` 정리
5. 재실행
6. 여전히 동일하면 사용자 상태 디렉터리와 bind mount 점검

### 4. 실물 롤아웃 (piper + openpi/gr00t 컨테이너)

```bash
docker compose exec piper uv pip install --system -e /workspace/robots/piper
bash scripts/vla/serve_openpi.sh        # 서버 기동
bash scripts/rollout/rollout_openpi.sh  # 롤아웃
```

## 디렉토리 구조

```
physical-ai-hub/
├── scripts/          # 모든 실행 진입점 (shell)
│   ├── data/         #   데이터 수집·텔레옵
│   ├── vla/          #   학습·서빙
│   ├── simulation/   #   시뮬레이션 평가
│   ├── rollout/      #   실물 롤아웃
│   └── robots/       #   로봇 셋업 유틸
├── robots/           # lerobot 호환 로봇 패키지
├── rollout/          # inference loop
├── data/             # LeRobot V3 데이터 도구
├── vla/              # VLA 프레임워크
│   ├── openpi/       #   submodule + tools/
│   └── gr00t/        #   submodule + tools/
├── simulation/       # 시뮬레이션 평가
│   ├── leisaac/      #   submodule (LeIsaac)
│   └── piper_isaac_sim/ #   submodule (PiPER URDF 에셋)
├── docker/           # 서비스별 Dockerfile
└── envs/             # 환경변수 (.env.base + .env.<service>)
```

## Docker 서비스

| 서비스 | GPU | 포트 | 용도 |
|--------|-----|------|------|
| piper | - | host | 로봇 제어 (CAN 통신, privileged) |
| openpi | all | 8000 | OpenPI 학습 & 서빙 |
| gr00t | all | 8001 | GR00T 학습 & 서빙 |
| leisaac | all | - | Isaac Sim 시뮬레이션 |

## 환경변수

- `envs/.env.base` — 공통 시크릿 (HF_TOKEN, WANDB_API_KEY) ← **gitignore**
- `envs/.env.piper` — PiPER 로봇 설정
- `envs/.env.openpi` — OpenPI 설정
- `envs/.env.gr00t` — GR00T 설정
- `envs/.env.leisaac` — LeIsaac 시뮬레이션 설정
