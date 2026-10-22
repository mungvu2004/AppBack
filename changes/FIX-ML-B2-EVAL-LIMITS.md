# FIX-ML-B2-EVAL-LIMITS — trần chấm model và RAM ml cho SegFormer-B2

- `apps/ml/ml_eval/settings.py`: `ML_EVAL_MAX_BYTES` mặc định 4 → 10 GiB, `ML_EVAL_TIMEOUT_S` 1800 → 3000 s.
  B2 (seg-b2-colab-v2) hỏng chấm dưới 4 GiB (ORT cấp 768 MiB), chấm đủ ~21 phút CPU 4 luồng.
- `deploy/compose/base.yml` + `env.example`: `ML_MEM_LIMIT` mặc định 6g → 8g (đỉnh lượt chấm B2 ~5,2 GiB).
- `deploy/compose/ml.env.example`: thêm `ML_EVAL_MAX_BYTES`, `ML_EVAL_TIMEOUT_S` cho prod.
- Test: `deploy/tests/test_env_example.py` khẳng định 8g. Không đổi API, migration, hợp đồng FE.
