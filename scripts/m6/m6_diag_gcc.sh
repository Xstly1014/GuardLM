#!/bin/bash
# 复现 triton cuda_utils 编译失败，看真实报错
cat > /tmp/cuda_test.c <<'EOF'
int main(){return 0;}
EOF
echo "=== link -lcuda with -L/usr/lib/wsl/lib ==="
gcc /tmp/cuda_test.c -O3 -shared -fPIC -o /tmp/cuda_test.so -lcuda -L/usr/lib/wsl/lib 2>&1 | head -5
echo "exit=$?"
echo "=== libcuda files ==="
ls -la /usr/lib/wsl/lib/libcuda* 2>/dev/null | head -5
ls -la /usr/lib/x86_64-linux-gnu/libcuda* 2>/dev/null | head -5
echo "=== python3.10 headers ==="
ls /usr/include/python3.10/Python.h 2>/dev/null || echo "NO python3.10 dev headers"
