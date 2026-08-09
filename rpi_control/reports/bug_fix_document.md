# Bug修复文档

> **文档版本**: v1.0  
> **生成日期**: 2026-07-29  
> **覆盖周期**: 2026-07-27 ~ 2026-07-29  
> **Bug总数**: 10（阶段一6 + 阶段二4）  

---

## 一、Bug总览

| # | Bug名称 | 严重级别 | 发现阶段 | 状态 |
|---|---------|----------|----------|------|
| 1 | WebSocket遥测崩溃：`active_connections` 属性不存在 | 🔴 Critical | 阶段二·自检 | ✅ 已修复 |
| 2 | API joint_id 范围不一致（1-6 vs 0-5） | 🟡 Medium | 阶段二·自检 | ✅ 已修复 |
| 3 | 数据库路径不一致 | 🟡 Medium | 阶段二·自检 | ✅ 已修复 |
| 4 | 缺少 `.gitignore` 和 systemd service 文件 | 🟡 Medium | 阶段二·自检 | ✅ 已修复 |
| 5 | IK不可达点检测被clamping掩盖 | 🟡 Medium | 阶段一·测试 | ✅ 已修复 |
| 6 | 测试路由指向已废弃的API路径 | 🟡 Medium | 阶段一·测试 | ✅ 已修复 |
| 7 | 测试函数签名不匹配 | 🟡 Medium | 阶段一·测试 | ✅ 已修复 |
| 8 | 测试障碍物类型错误 | 🟡 Medium | 阶段一·测试 | ✅ 已修复 |
| 9 | 安全测试路径错误 | 🟡 Medium | 阶段一·测试 | ✅ 已修复 |
| 10 | IK测试断言方式错误 | 🟡 Medium | 阶段一·测试 | ✅ 已修复 |

---

## 二、🔴 Critical Bug 详细分析

---

### Bug 1：WebSocket遥测崩溃 - `ws_manager.active_connections` 属性不存在

#### 发现过程

在逐文件审查 [telemetry.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/web/websocket/telemetry.py) 时，发现 `TelemetryStream` 类中存在两处对 `ws_manager.active_connections` 的引用：

1. **第99行** - `_streaming_loop` 方法中：
   ```python
   # 修复前
   if telemetry and ws_manager.active_connections:
       await ws_manager.broadcast(telemetry)
   ```

2. **第211行** - `_collect_system_status` 方法中：
   ```python
   # 修复前
   "connected_clients": len(ws_manager.active_connections),
   ```

但检查 `WebSocketManager` 类（定义在 [handler.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/web/websocket/handler.py) 中）时发现，该类**没有 `active_connections` 属性**。其实际暴露的接口是：
- `client_count` 属性（返回当前连接数）
- `_clients` 字典（内部存储，不应直接访问）

#### 问题原因

**根本原因：接口不一致导致AttributeError**

这是一个典型的开发过程中不同模块间接口不同步的问题。`telemetry.py` 的开发者在编写遥测代码时，假设 `WebSocketManager` 有一个 `active_connections` 属性，但该类的实际实现使用了 `client_count` 来暴露连接数。

这种问题通常发生在以下场景：
1. 两个模块由不同开发者（或同一开发者在不同时间）编写
2. `WebSocketManager` 的接口在开发过程中发生了变更，但 `telemetry.py` 没有同步更新
3. 缺少类型注解或接口文档，导致IDE无法在编码阶段发现此问题

#### 影响分析

- **运行时崩溃**：当 `TelemetryStream` 的 `_streaming_loop` 运行时，访问 `ws_manager.active_connections` 会抛出 `AttributeError`
- **遥测功能完全瘫痪**：所有实时遥测数据（关节位置、传感器数据、系统状态）将无法推送
- **WebSocket连接失败**：`broadcast()` 调用失败，所有前台仪表盘无法获取实时数据
- **间接影响**：`_collect_system_status` 中的 `len(ws_manager.active_connections)` 同样崩溃，导致状态报告功能失效

#### 解决方案

在 [telemetry.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/web/websocket/telemetry.py) 中进行两处修改：

**修复点1** - `_streaming_loop` 方法（第99行）：
```python
# 修复后
if telemetry and ws_manager.client_count > 0:
    await ws_manager.broadcast(telemetry)
```

**修复点2** - `_collect_system_status` 方法（第211行）：
```python
# 修复后
"connected_clients": ws_manager.client_count,
```

**修复说明**：
- `ws_manager.active_connections`（布尔判断）→ `ws_manager.client_count > 0`（数值比较）
- `len(ws_manager.active_connections)`（取长度）→ `ws_manager.client_count`（直接获取数值）
- 语义完全等价：检查是否有活跃连接时广播；报告已连接客户端数量

#### 验证方法

1. 启动 WebSocket 服务
2. 连接一个 WebSocket 客户端
3. 确认 `_streaming_loop` 能正常启动并推送遥测数据
4. 确认 `_collect_system_status` 返回的 `connected_clients` 字段正确

---

## 三、🟡 Medium Bug 详细分析

---

### Bug 2：API joint_id 范围不一致（1-6 vs 0-5）

#### 发现过程

在审查 [arm_routes.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/web/routes/arm_routes.py) 的 API 端点时，发现第65行的 joint_id 验证为：
```python
# 修复前
if not (1 <= joint_id <= 6):
    raise HTTPException(status_code=400, detail="joint_id must be between 1 and 6")
```

但检查底层硬件接口 `STM32Interface.move_servo()`（定义在 [stm32_comm.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/hardware/stm32_comm.py)）时，发现其期望的 servo_id 范围是 **0-5**（0-based 索引）。

#### 问题原因

**根本原因：API层与硬件抽象层的索引偏移不一致**

这是嵌入式系统中常见的 "off-by-one" 问题。造成此问题的原因：

1. **人机交互习惯 vs 硬件接口习惯**：API 面向用户，倾向于使用 1-based 编号（第1-6号关节），而底层硬件接口（C/C++/固件通信）习惯使用 0-based 索引
2. **缺少索引转换层**：在 API 层和硬件层之间没有添加统一的索引转换（如 `joint_id - 1`）
3. **代码审查盲区**：这种跨层不一致容易被忽视，因为两端代码在各自上下文中都"看起来合理"

#### 影响分析

- **关节控制错位**：用户调用 `joint_id=1` 实际控制的是底层 `joint_id=0`（基座关节），所有关节控制会发生偏移
- **调试困难**：用户看到的关节编号与实际被控制的关节不同，排查问题非常耗时
- **安全风险**：如果用户期望控制末端效应器（joint 6），实际控制的是 joint 5，可能导致意外运动

#### 解决方案

在 [arm_routes.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/web/routes/arm_routes.py) 第65-66行修改：

```python
# 修复后
if not (0 <= joint_id <= 5):
    raise HTTPException(status_code=400, detail="joint_id must be between 0 and 5")
```

同时更新第72行的注释：
```python
# 修复后
# Update mock joint position (0-based, joint_0...joint_5)
joint_attr = f"joint_{joint_id}"
```

**修复说明**：
- 选择统一为 0-based 索引，与底层硬件接口保持一致
- 这是更安全的选择：API 层适配底层，而不是底层适配 API，避免引入额外的转换逻辑
- 如果未来需要面向用户友好的 1-based 显示，可在前端做转换

#### 验证方法

1. 调用 `POST /api/v1/arm/joint` 传入 `joint_id=0`
2. 确认底层 `move_servo(0, ...)` 被正确调用
3. 调用 `joint_id=5` 确认末端效应器正确响应

---

### Bug 3：数据库路径不一致

#### 发现过程

在审查数据库相关配置时，发现三个文件中的数据库路径彼此不一致：

| 文件 | 修改前路径 | 
|------|-----------|
| [repository.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/database/repository.py#L34) | `sqlite:///./data/sampling_arm.db` |
| [settings.yaml](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/config/settings.yaml#L30) | `sqlite:///data/sampling.db` |
| [.env.example](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/.env.example#L29) | `sqlite:///data/sampling.db` |

#### 问题原因

**根本原因：配置漂移（Configuration Drift）**

这是典型的配置漂移问题，由以下原因造成：

1. **多入口初始化**：代码可以通过多种方式启动（直接运行、Docker、systemd），不同入口可能使用不同的配置文件
2. **开发过程中路径变更**：数据库文件名从 `sampling_arm.db` 改为 `sampling.db`，但 `repository.py` 的默认参数没有同步更新
3. **SQLite 路径格式不一致**：`sqlite:///./data/` vs `sqlite:///data/` — 前者是相对路径（相对于工作目录），后者是绝对路径（相对于文件系统根目录）。在 Linux 上 `sqlite:///data/` 会尝试在 `/data/` 目录创建数据库，这通常没有权限
4. **缺少配置验证**：没有在启动时检查所有配置来源的一致性

#### 影响分析

- **多数据库文件**：不同启动方式会创建不同的数据库文件，导致数据分散
- **数据丢失假象**：通过 Docker 写入的数据，直接运行时"看不到"，反之亦然
- **路径错误**：`sqlite:///data/sampling.db`（绝对路径）在 Linux 上会尝试写入 `/data/sampling.db`，通常没有权限

#### 解决方案

统一所有三个文件中的数据库路径为 `sqlite:///./data/sampling.db`：

**修复点1** - [repository.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/database/repository.py#L34)：
```python
# 修复后
def __init__(self, db_url: str = "sqlite:///./data/sampling.db"):
```

**修复点2** - [settings.yaml](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/config/settings.yaml#L30)：
```yaml
# 修复后
database:
  url: "sqlite:///./data/sampling.db"
```

**修复点3** - [.env.example](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/.env.example#L29)：
```bash
# 修复后
DATABASE_URL=sqlite:///./data/sampling.db
```

**修复说明**：
- 使用 `./data/` 前缀确保相对路径语义，无论从哪个工作目录启动都能正确定位到项目下的 `data/` 目录
- 统一使用 `sampling.db` 作为数据库文件名
- 三重保障：代码默认值、YAML配置、环境变量三者一致

#### 验证方法

1. 通过不同方式启动（直接运行、Docker、systemd）
2. 检查 `data/sampling.db` 是否被正确创建
3. 确认不存在 `sampling_arm.db` 或 `/data/sampling.db` 等错误文件

---

### Bug 4：缺少 `.gitignore` 和 systemd service 文件

#### 发现过程

在审查部署相关文件时，发现两个缺失：

1. **`.gitignore` 缺失**：虽然项目有 `.dockerignore`（Docker忽略规则），但没有 `.gitignore`（Git忽略规则）
2. **systemd service 文件缺失**：`DEPLOY_CHECKLIST.md` 和 `deploy.sh` 都提到了 systemd 部署方式，但 `scripts/` 目录下没有对应的 `.service` 文件

#### 问题原因

**根本原因：开发焦点在核心功能，部署运维文件滞后**

1. **`.gitignore` 缺失原因**：
   - 开发初期可能使用了全局 `.gitignore` 配置
   - 项目从其他模板迁移时，`.gitignore` 未被包含
   - 开发过程中主要关注 `.dockerignore`（Docker构建需要），忽略了 `.gitignore`

2. **`.service` 文件缺失原因**：
   - `deploy.sh` 脚本中可能通过 `cat <<EOF` 内联生成 service 文件
   - 但在独立部署场景下，运维人员需要一个独立的 `.service` 文件

#### 影响分析

- **安全隐患**：没有 `.gitignore` 可能导致 `.env`（含密钥）、模型文件（`.pkl`）、数据库文件（`.db`）被误提交到 Git 仓库
- **部署不便**：缺少 systemd service 文件，运维人员需要手动创建，增加了部署出错的风险
- **文档不一致**：部署文档提到 systemd 部署但没有对应文件，导致文档与实际不一致

#### 解决方案

**补充文件1** - [.gitignore](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/.gitignore)（78行）：
```
关键保护规则：
- .env, .env.local, .env.*.local（环境变量文件）
- *.pkl, *.h5, *.keras, *.onnx（模型文件）
- data/*.db, logs/*.log（数据和日志文件）
- __pycache__/, .pytest_cache/（Python缓存）
- venv/, .venv/（虚拟环境）
- .vscode/, .idea/（IDE配置）
```

**补充文件2** - [scripts/rpi-sampling-arm.service](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/scripts/rpi-sampling-arm.service)（53行）：
```
关键配置：
- User=sampling, Group=sampling（非root运行）
- WorkingDirectory=/opt/sampling-arm/rpi_control
- EnvironmentFile=.env（环境变量加载）
- NoNewPrivileges=yes（安全加固）
- ProtectSystem=strict（系统目录只读）
- DeviceAllow=白名单（UART/I2C/GPIO设备）
- MemoryHigh=512M, CPUQuota=150%（资源限制）
- Restart=on-failure（自动重启）
```

#### 验证方法

1. 运行 `git status` 确认 `.gitignore` 生效，敏感文件被忽略
2. 将 `.service` 文件复制到 `/etc/systemd/system/`，运行 `systemctl daemon-reload`
3. 确认 `systemctl start rpi-sampling-arm` 能正常启动服务

---

### Bug 5：IK不可达点检测被clamping掩盖

#### 发现过程

在运行白盒测试时，IK（逆运动学）的"不可达点检测"测试失败。经分析发现，`_solve_position_ik` 方法中对 `cos_theta_3` 的 clamping 操作过于激进。

#### 问题原因

**根本原因：clamping掩盖了真正的不可达情况**

在 `kinematics.py` 第362-371行：
```python
# 修复前
cos_theta_3 = (r ** 2 + z_prime ** 2 - a1 ** 2 - a2 ** 2) / (2 * a1 * a2)
cos_theta_3 = max(-1.0, min(1.0, cos_theta_3))  # 无条件clamping
```

问题在于无条件地将 `cos_theta_3` 钳制到 `[-1.0, 1.0]`。当目标点真正不可达时（cos值超出范围很多），这个 clamping 会将其强制变为边界值，从而"制造"出一个本不存在的解。这违反了 IK 的语义：不可达点应该返回无解。

#### 解决方案

```python
# 修复后
denom = 2 * a1 * a2
if denom == 0:
    continue  # Invalid link lengths, skip
cos_raw = (r ** 2 + z_prime ** 2 - a1 ** 2 - a2 ** 2) / denom
if abs(cos_raw) > 1.0 + 1e-3:
    continue  # Truly unreachable
cos_theta_3 = max(-1.0, min(1.0, cos_raw))
```

**修复说明**：
- 先计算原始 `cos_raw` 值
- 检查 `denom` 是否为0（防止除零）
- 仅当 `|cos_raw| > 1.0 + 1e-3` 时才判定为真正不可达（1e-3 容差处理浮点误差）
- 只有通过不可达检查的才进行 clamping

---

### Bug 6-10：测试代码Bug（5项）

#### 共通原因

这些 Bug 都是测试代码与生产代码不同步造成的：
- **路由变更**：API 路由从 `/api/arm/status` 迁移到 `/api/v1/arm/status`，但测试代码未更新
- **函数签名变更**：IK 函数签名从分离的 `(pos, ori)` 改为统一的 `np.array([x,y,z,r,p,y])`
- **类型变更**：障碍物从 `dict` 改为 `Obstacle` 对象

#### 修复汇总

| Bug | 文件 | 修复前 | 修复后 |
|-----|------|--------|--------|
| 6 | `tests/test_performance.py` | `/api/arm/status` | `/api/v1/arm/status` |
| 7 | `tests/test_performance.py` | `ik(pos, ori)` | `ik(np.array([x,y,z,r,p,y]))` |
| 8 | `tests/test_performance.py` | `{"x": 10, ...}` | `Obstacle(...)` |
| 9 | `tests/test_security.py` | `/api/arm/status` | `/api/v1/arm/status` |
| 10 | `tests/test_whitebox_core.py` | `try/except` | `pytest.raises(...)` |

---

## 四、Bug分类统计

| 分类 | 数量 | 占比 |
|------|------|------|
| 运行时崩溃（AttributeError） | 1 | 10% |
| 接口不一致（Off-by-one/路径） | 2 | 20% |
| 缺失文件 | 2 | 20% |
| 算法逻辑错误 | 1 | 10% |
| 测试代码不同步 | 5 | 50% |

## 五、Bug严重级别分布

| 级别 | 数量 | 说明 |
|------|------|------|
| 🔴 Critical | 1 | 运行时崩溃，功能完全不可用 |
| 🟡 Medium | 9 | 功能异常、配置错误、测试失败 |
| 🟢 Low | 0 | - |

## 六、经验教训

1. **跨模块接口一致性**：当多个模块共享同一对象时，应使用类型注解和接口文档确保属性名一致
2. **索引规范统一**：在涉及硬件交互的系统中，应明确约定并文档化索引规范（0-based 或 1-based）
3. **配置集中管理**：数据库路径等关键配置应有单一来源，其他位置通过引用而非复制
4. **测试同步更新**：生产代码变更后，必须同步更新测试代码，建议使用 CI/CD 自动检测
5. **部署文件完整性**：项目应包含完整的部署文件（`.gitignore`、`.service`、`Makefile` 等），而非依赖内联生成

---

*文档生成时间: 2026-07-29 | 工作留痕*