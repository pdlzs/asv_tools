cd /mnt/c/Users/Luo/Code/numpy/benchmarks
rm -rf results
asv run \
    -b "bench_app" \
    -b "bench_clip" \
    -b "bench_core"