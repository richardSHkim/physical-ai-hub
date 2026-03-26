# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Physical AI Hub는 로봇 학습 파이프라인 통합 허브입니다. 데이터 수집 → VLA 학습 → 시뮬레이션 평가 → 실물 롤아웃을 하나의 레포에서 관리합니다. 데이터는 항상 LeRobot Dataset V3 포맷이 소스 오브 트루스입니다.

## Common Commands

```bash
# 서브모듈 초기화 (클론 직후 필수)
make submodule-init

# Docker 빌드
make build-piper          # piper 로봇 컨테이너
make build-openpi         # OpenPI 컨테이너
make build-gr00t          # GR00T 컨테이너
make build-all            # 전체

# 학습
make train-openpi         # OpenPI
make train-gr00t          # GR00T

# Inference 서버
make server-openpi        # OpenPI 서버 (port 8000)
make server-gr00t         # GR00T 서버 (port 8001)
make server-down          # 전체 서버 종료

# 롤아웃
make rollout-openpi
make rollout-gr00t

# 개발 셸
make shell-piper          # piper 컨테이너 bash 접속
make shell-openpi
make shell-gr00t
```

## Architecture

### 실행 흐름: 3단계 구조

```
make <target>  →  scripts/<category>/<script>.sh  →  <module>/tools/<tool>.py
```

- **Level 0** `Makefile`: 사용자 진입점. 모든 target은 scripts/ 의 shell script와 1:1 대응
- **Level 1** `scripts/`: docker compose run 래퍼. 로직 없음, 상수만 설정
- **Level 2** `<module>/tools/`: 실제 python 로직 위치

### 소유권 분류

| 기호 | 의미 | 폴더 |
|------|------|------|
| 🟢 | 자체 개발 | `robots/`, `rollout/` |
| 🟣 | submodule + 우리 코드 | `vla/openpi/`, `vla/gr00t/`, `eval/` |
| 🟡 | 설정·스크립트만 | `data/` |

### Docker 서비스 구성

| 서비스 | 베이스 이미지 | GPU | 포트 | 특이사항 |
|--------|-------------|-----|------|---------|
| piper | ubuntu:22.04 | - | - | network_mode: host, privileged (CAN 통신) |
| openpi | nvidia/cuda:12.1 | all | 8000 | inference 서버 |
| gr00t | nvidia/cuda:12.1 | all | 8001 | inference 서버 |
| leisaac | nvidia/cuda:12.1 | all | - | Isaac Sim eval |

### Rollout 클라이언트 패턴

`rollout/clients/base.py`에 PolicyClient Protocol을 정의하고, 각 VLA별 구현체(`openpi.py`, `gr00t.py`)가 이를 따릅니다. `rollout/inference_loop.py`가 클라이언트를 선택하여 실행합니다.

### 환경변수

`envs/.env.base` (공통) + `envs/.env.<service>` (서비스별)을 docker-compose env_file 배열로 조합합니다. 실제 env 파일은 gitignore 되며, `.env.example`만 git 추적합니다.

## Conventions

### Shell script 상단 주석 (모든 .sh 필수)

```bash
#!/usr/bin/env bash
# CONTAINER: <service-name>
# RUN: make <target>
#
# 변경할 상수:
VAR="default_value"   # ← 여기만 수정
```

### 커밋 메시지

```
feat(robots/piper): add piper_follower lerobot package
chore(docker): update openpi CUDA base to 12.1
chore(submodule): bump eval/leisaac to abc1234
```

### 핵심 규칙

- **모듈 독립성**: 각 `vla/`, `eval/` 폴더는 다른 폴더를 import하지 않음
- **프레임워크 우선**: upstream을 그대로 사용, 자체 추상화 금지
- **패키지 관리**: `pip` 대신 `uv pip` 사용
- **Submodule 고정**: `git submodule update --remote` 사용 금지. 항상 특정 커밋 SHA 고정
- **robots/ 파일 유지**: `robots/piper/`의 4개 파일(piper_follower, piper_leader, bi_piper_follower, bi_piper_leader)은 통합하지 않고 그대로 유지

### 새 VLA/로봇 추가

- **VLA**: 각 VLA의 원본 코드를 존중합니다. submodule로 추가하고 우리 코드는 `tools/`에만 둡니다.
- **로봇**: LeRobot 방식을 따릅니다.
