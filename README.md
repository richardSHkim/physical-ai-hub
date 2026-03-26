# Physical AI Hub

로봇 학습 파이프라인 통합 허브 — 데이터 수집, VLA 학습, 시뮬레이션 평가, 실물 롤아웃을 하나의 레포에서 관리합니다.

## 지원 현황

| 구성 요소 | 지원 항목 | 상태 |
|---------|---------|------|
| 로봇 | Agilex PiPER (follower / leader / bi) | ✅ |
| VLA | OpenPI | ✅ |
| VLA | Isaac-GR00T | ✅ |
| Eval | LeIsaac | ✅ |
| Eval | IsaacSim / IsaacLab | 🔧 보조 |

## Submodule 현황

| 경로 | Upstream | Fork | 고정 커밋 |
|------|----------|------|----------|
| `vla/openpi/openpi/` | Physical-Intelligence/openpi | - | TBD |
| `vla/gr00t/Isaac-GR00T/` | NVIDIA/Isaac-GR00T | - | TBD |
| `eval/LeIsaac/` | `<your-org>/LeIsaac` | Yes | TBD |

## 퀵스타트

[docs/quickstart.md](docs/quickstart.md)를 참고하세요.

## 디렉토리 구조

```
physical-ai-hub/
├── scripts/        # 모든 실행 진입점 (shell script)
├── robots/         # lerobot 호환 로봇 패키지
├── data/           # LeRobot V3 데이터 도구
├── vla/            # VLA 프레임워크 (openpi, gr00t)
├── eval/           # 시뮬레이션 평가 (LeIsaac)
├── rollout/        # 실물 롤아웃 inference loop
├── docker/         # 서비스별 Dockerfile
├── envs/           # 환경변수 파일
└── docs/           # 문서
```

## 새 로봇/VLA 추가

- [새 로봇 추가 가이드](docs/add_robot.md)
- [새 VLA 추가 가이드](docs/add_vla.md)
- [Submodule & Fork 운영 가이드](docs/submodule_fork_guide.md)
