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

piper task를 로드하려면 먼저 URDF 에셋을 leisaac assets 경로로 복사합니다.

```bash
cp -r simulation/piper_isaac_sim/piper_description/urdf/piper_description_v100_realsense_camera_v2 \
      simulation/leisaac/assets/piper_description/urdf/
```

```bash
bash scripts/vla/serve_openpi.sh          # 서버 기동
bash scripts/simulation/eval_leisaac.sh   # 시뮬레이션 평가
```

### 4. 실물 롤아웃 (piper + openpi/gr00t 컨테이너)

```bash
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
