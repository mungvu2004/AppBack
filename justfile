# Bí danh cho Linux/CI. Máy dev Windows không có `just`: dùng thẳng
# `bash tools/verify/run.sh <việc>` (BE-01 [1]).

verify *ARGS:
    bash tools/verify/run.sh verify {{ARGS}}

lock:
    bash tools/verify/run.sh lock

openapi:
    bash tools/verify/run.sh openapi

merge-heads NAME:
    bash tools/verify/run.sh merge-heads {{NAME}}

shell:
    bash tools/verify/run.sh shell

gc:
    bash tools/verify/run.sh gc
