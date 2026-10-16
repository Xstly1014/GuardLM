#!/bin/bash
# 诊断 pip 卡点：进程状态 + 网络连接
PID=$(pgrep -f "pip install" | head -1)
echo "pid=$PID"
if [ -n "$PID" ]; then
  cat /proc/$PID/status | head -4
  echo "--- fds ---"
  ls -la /proc/$PID/fd 2>/dev/null | grep -v "socket\|pipe\|/dev" | tail -5
  echo "--- sockets ---"
  ss -tnp 2>/dev/null | grep "$PID" | head -5
  echo "--- io ---"
  cat /proc/$PID/io 2>/dev/null | grep -E "read_bytes|write_bytes"
fi
