#!/usr/bin/env bash
# =============================================================================
# start_all.sh - 智能采样机械臂一键启动脚本
# 在真实硬件环境中同时启动全部 5 个 Agent 与模型服务。
#
# 架构说明:
#   - 5 个 Agent (sampling/vision/motion/quality/safety) 均由
#     rpi_control.agents.orchestrator.Orchestrator 实例化, 每个 Agent 经
#     BaseAgent.run() 执行, 约束护栏(不可擅自决策/符合事实逻辑)自动生效。
#   - 4 个 ML 模型 (motion_ik/safety/collision/quality .pkl) 由对应 Agent
#     在初始化时加载, 视觉标定来自 config/settings.yaml。
#   - 主服务 main.py 负责 STM32/OpenMV 通信、机械臂、Web、云同步。
#
# 用法:
#   ./start_all.sh            # 默认: 本地源码方式启动 (全部 5 Agent + 模型服务)
#   ./start_all.sh --docker   # 使用 docker compose 启动
#   ./start_all.sh --check    # 仅做环境/模型/约束自检, 不启动
#   ./start_all.sh --stop     # 停止已启动的进程
#   ./start_all.sh --log      # 跟随主服务与编排器日志
#
# 工业级升级 (10-工业级升级规划.md / 六维软件架构维度) 扩展:
#   ./start_all.sh --ros2     # 若检测到 ROS2: 以 ROS2 节点方式启动各 Agent
#   ./start_all.sh --jetson   # 额外启动 Jetson 视觉节点 (M1, 需在 Jetson 平台)
#   ./start_all.sh --ros2 --jetson   # 组合: ROS2 + Jetson 视觉节点
# =============================================================================
set -euo pipefail

# ---- 配置 -----------------------------------------------------------------
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

PYTHON="${PYTHON:-python3}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
MAIN_PID=""
ORCH_PID=""
PID_DIR="$REPO_DIR/.run"
ORCH_LOG="$PID_DIR/orchestrator.log"
MAIN_LOG="$PID_DIR/main.log"

# 模型服务清单 (Agent 初始化时加载)
MODELS=(
  "rpi_control/models/motion_ik_model.pkl"
  "rpi_control/models/safety_model.pkl"
  "rpi_control/models/collision_model.pkl"
  "rpi_control/models/quality_model.pkl"
)
AGENTS=(sampling vision motion quality safety)

# 工业级升级: ROS2 / Jetson 可选开关
USE_ROS2=0
USE_JETSON=0
ROS2_LAUNCH_FILE="${ROS2_LAUNCH_FILE:-rpi_control/ros2/sampling_arm.launch.py}"
JETSON_NODE_SCRIPT="${JETSON_NODE_SCRIPT:-rpi_control/vision/jetson_vision_node.py}"

log()  { echo -e "\033[1;34m[$(date '+%H:%M:%S')]\033[0m $*"; }
err()  { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; }
ok()   { echo -e "\033[1;32m[ OK ]\033[0m $*"; }
die()  { err "$*"; exit 1; }

mkdir -p "$PID_DIR"

# ---- 解析可选开关 ----------------------------------------------------------
parse_opts() {
  for arg in "$@"; do
    case "$arg" in
      --ros2)   USE_ROS2=1 ;;
      --jetson) USE_JETSON=1 ;;
      --docker|--check|--stop|--log|--stress) ;;
      *) die "未知参数: $arg (支持: --check / --stop / --log / --docker / --ros2 / --jetson / --stress)" ;;
    esac
  done
}

# ---- ROS2 / Jetson 环境探测 ------------------------------------------------
probe_industrial() {
  if [[ "$USE_ROS2" -eq 1 ]]; then
    if command -v ros2 >/dev/null 2>&1; then
      ok "检测到 ROS2: $(ros2 --version 2>/dev/null)"
      [[ -f "$ROS2_LAUNCH_FILE" ]] || warn_ros2_launch
    else
      err "未检测到 ROS2 (ros2 命令不存在)"
      err "已回退到本地源码方式启动 Agent (--ros2 仅在 ROS2 环境生效)"
      USE_ROS2=0
    fi
  fi
  if [[ "$USE_JETSON" -eq 1 ]]; then
    if [[ -f "$JETSON_NODE_SCRIPT" ]]; then
      ok "发现 Jetson 视觉节点脚本: $JETSON_NODE_SCRIPT"
    else
      err "未找到 Jetson 视觉节点脚本 $JETSON_NODE_SCRIPT (M1 中期能力, 未实现时自动跳过)"
      USE_JETSON=0
    fi
  fi
}

warn_ros2_launch() {
  err "警告: 未找到 ROS2 launch 文件 $ROS2_LAUNCH_FILE"
  err "将退回到逐 Agent 启动 (ros2 run), 建议后续补齐 ROS2 包"
}

# ---- 启动 ROS2 节点 (各 Agent 以 ROS2 节点方式运行) -------------------------
do_start_ros2() {
  log "== 以 ROS2 节点方式启动 5 个 Agent =="
  if [[ -f "$ROS2_LAUNCH_FILE" ]]; then
    nohup ros2 launch "$ROS2_LAUNCH_FILE" >"$PID_DIR/ros2_launch.log" 2>&1 &
    echo $! > "$PID_DIR/ros2.pid"
    log "ROS2 launch 已启动 (PID=$(cat "$PID_DIR/ros2.pid"))"
  else
    # 回退: 逐节点 ros2 run (包名/可执行名与 ROS2 包约定一致)
    local node_pkg="sampling_arm"
    for a in "${AGENTS[@]}"; do
      nohup ros2 run "$node_pkg" "${a}_agent_node" >"$PID_DIR/ros2_${a}.log" 2>&1 &
    done
    log "已以 ros2 run 逐节点启动 ${AGENTS[*]}"
  fi
}

# ---- 启动 Jetson 视觉节点 (M1) ----------------------------------------------
do_start_jetson() {
  log "== 启动 Jetson 视觉节点 =="
  nohup "$PYTHON" "$JETSON_NODE_SCRIPT" >"$PID_DIR/jetson_vision.log" 2>&1 &
  echo $! > "$PID_DIR/jetson.pid"
  ok "Jetson 视觉节点已启动 (PID=$(cat "$PID_DIR/jetson.pid"), 日志 $PID_DIR/jetson_vision.log)"
}

# ---- 自检 -----------------------------------------------------------------
do_check() {
  log "== 环境与依赖自检 =="
  command -v "$PYTHON" >/dev/null || die "未找到 python ($PYTHON)"
  "$PYTHON" -c "import rpi_control, numpy, scipy, yaml; print('   deps OK')" \
    || die "依赖缺失, 请先安装 requirements.txt"
  log "== 模型服务检查 =="
  local missing=0
  for m in "${MODELS[@]}"; do
    if [[ -f "$m" ]]; then ok "模型就绪: $m"; else err "模型缺失: $m"; missing=1; fi
  done
  [[ "$missing" -eq 0 ]] || die "存在缺失模型, 请先完成训练/复制模型"
  log "== Agent 加载与约束自检 =="
  "$PYTHON" - <<'PY'
from rpi_control.agents.orchestrator import Orchestrator
from rpi_control.agents.base_agent import BaseAgent
o = Orchestrator()
assert set(o.agents) >= {"sampling","vision","motion","quality","safety"}, o.agents
assert not o._agent_init_errors, o._agent_init_errors
for name, ag in o.agents.items():
    assert isinstance(ag, BaseAgent), name
print("   5 个 Agent 全部加载, 无初始化错误, 均经 BaseAgent.run() 生效护栏")
PY
  log "== 检查完成 (全部通过) =="
}

# ---- 启动 -----------------------------------------------------------------
do_start() {
  [[ -f "$PID_DIR/.running" ]] && { log "系统已在运行, 先执行 ./start_all.sh --stop"; exit 0; }

  do_check
  probe_industrial

  # 0) 主服务始终启动 (STM32/OpenMV 通信 + Web + 机械臂)
  log "启动主服务 (main.py) ..."
  nohup "$PYTHON" -m rpi_control.main >"$MAIN_LOG" 2>&1 &
  MAIN_PID=$!

  # 1) Agent 编排: 本地源码方式 (默认) 或 ROS2 节点方式 (--ros2)
  if [[ "$USE_ROS2" -eq 1 ]]; then
    do_start_ros2
  else
    log "启动多 Agent 编排器 (sampling/vision/motion/quality/safety) ..."
    nohup "$PYTHON" - <<'PY' >"$ORCH_LOG" 2>&1 &
import asyncio, logging
from rpi_control.agents.orchestrator import Orchestrator
logging.basicConfig(level=logging.INFO)
o = Orchestrator()
async def run():
    while True:
        await asyncio.sleep(5)
asyncio.run(run())
PY
    ORCH_PID=$!
    echo "$ORCH_PID" > "$PID_DIR/orch.pid"
  fi

  # 2) Jetson 视觉节点 (--jetson, 可选)
  if [[ "$USE_JETSON" -eq 1 ]]; then
    do_start_jetson
  fi

  echo "$MAIN_PID" > "$PID_DIR/main.pid"
  touch "$PID_DIR/.running"

  sleep 2
  log "主服务 PID=$MAIN_PID (日志 $MAIN_LOG)"
  [[ "$USE_ROS2" -eq 0 ]] && log "编排器 PID=$ORCH_PID (日志 $ORCH_LOG)"
  log "健康检查: curl http://${HOST}:${PORT}/api/health"
  echo "全部 Agent 与模型服务已启动。"
}

# ---- 停止 -----------------------------------------------------------------
do_stop() {
  log "停止服务 ..."
  for pidf in orch.pid main.pid ros2.pid jetson.pid; do
    if [[ -f "$PID_DIR/$pidf" ]]; then
      kill "$(cat "$PID_DIR/$pidf")" 2>/dev/null || true
      rm -f "$PID_DIR/$pidf"
    fi
  done
  rm -f "$PID_DIR/.running"
  log "已停止。"
}

# ---- 日志 -----------------------------------------------------------------
do_log() {
  if [[ "$USE_ROS2" -eq 1 ]]; then
    tail -f "$MAIN_LOG" "$PID_DIR/ros2_launch.log" "$PID_DIR/jetson_vision.log" 2>/dev/null || true
  else
    tail -f "$MAIN_LOG" "$ORCH_LOG"
  fi
}

# ---- 一键压力验证 (部署前) --------------------------------------------------
do_stress() {
  log "== 一键压力验证: 运行极端工况压力测试并生成报告 =="
  do_check
  if ! "$PYTHON" -m pytest rpi_control/tests/stress_test_extreme.py -q; then
    die "压力测试存在失败用例, 请按 16-故障排查速查表.md 排查"
  fi
  log "压力测试全部通过。"
  if [[ -f "reports/stress_test_results.json" ]]; then
    ok "报告已生成: reports/stress_test_results.json"
  else
    log "以直接运行方式生成报告 ..."
    "$PYTHON" rpi_control/tests/stress_test_extreme.py || true
  fi
}

# ---- 主入口 ---------------------------------------------------------------
main() {
  parse_opts "$@"
  local cmd="${1:-}"
  case "$cmd" in
    --check) do_check ;;
    --stress) do_stress ;;
    --stop)  do_stop ;;
    --log)   do_log ;;
    --docker)
      do_check
      log "以 docker compose 启动 ..."
      docker compose -f rpi_control/docker-compose.yml up -d rpi-control orchestrator
      log "查看: docker compose -f rpi_control/docker-compose.yml logs -f"
      ;;
    "")
      do_start
      ;;
    --ros2|--jetson)
      do_start
      ;;
    *)
      die "未知参数: $cmd"
      ;;
  esac
}
main "$@"
