# 智能采样机械臂多智能体协同系统 - API 接口文档

## 文档信息

| 属性 | 内容 |
|------|------|
| 项目名称 | 智能采样机械臂多智能体协同系统 |
| 文档版本 | v2.0.0 |
| API 版本 | v1 |
| 创建日期 | 2026-07-23 |
| 文档状态 | 正式发布 |

---

## 目录

1. [概述](#1-概述)
2. [REST API](#2-rest-api)
3. [WebSocket API](#3-websocket-api)
4. [STM32-RPi UART 协议](#4-stm32-rpi-uart-协议)
5. [OpenMV-RPi 视觉协议](#5-openmv-rpi-视觉协议)
6. [错误码](#6-错误码)
7. [速率限制](#7-速率限制)
8. [版本策略](#8-版本策略)

---

## 1. 概述

### 1.1 基础 URL

```
开发环境:  https://sampling-arm-pi.local:8000/api/v1
生产环境:  https://api.your-domain.com/api/v1
```

### 1.2 认证

所有 API 请求（除 `/auth/login` 和 `/health` 外）需要携带 JWT Token。

**请求头:**

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**获取 Token:**

```
POST /api/v1/auth/login
```

### 1.3 通用响应格式

**成功响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

**列表响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [ ... ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

**错误响应:**

```json
{
  "code": 400,
  "message": "参数错误: 缺少必要参数",
  "data": null,
  "error": {
    "type": "ValidationError",
    "details": "field 'type' is required"
  }
}
```

### 1.4 通用请求头

| 头部 | 值 | 说明 |
|------|------|------|
| `Authorization` | `Bearer <token>` | JWT 认证令牌 |
| `Content-Type` | `application/json` | 请求体格式 |
| `Accept` | `application/json` | 期望响应格式 |
| `X-Request-ID` | `uuid` | 请求追踪 ID (可选) |

---

## 2. REST API

### 2.1 认证接口

#### 2.1.1 登录

```
POST /api/v1/auth/login
```

**请求体:**

```json
{
  "username": "admin",
  "password": "your-password"
}
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 86400,
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "id": "user-001",
      "username": "admin",
      "role": "admin"
    }
  }
}
```

**cURL 示例:**

```bash
curl -X POST https://sampling-arm-pi.local:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
```

#### 2.1.2 刷新 Token

```
POST /api/v1/auth/refresh
```

**请求体:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 86400
  }
}
```

#### 2.1.3 登出

```
POST /api/v1/auth/logout
```

**请求头:** `Authorization: Bearer <access_token>`

**响应:**

```json
{
  "code": 200,
  "message": "logged out successfully",
  "data": null
}
```

---

### 2.2 系统接口

#### 2.2.1 健康检查

```
GET /api/v1/health
```

无需认证。

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "healthy",
    "version": "2.0.0",
    "uptime": 3600,
    "components": {
      "stm32": "connected",
      "openmv": "connected",
      "database": "connected"
    }
  }
}
```

**cURL 示例:**

```bash
curl https://sampling-arm-pi.local:8000/api/v1/health
```

#### 2.2.2 系统状态

```
GET /api/v1/status
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "system_status": "IDLE",
    "arm_status": "READY",
    "safety_status": "NORMAL",
    "active_task_id": null,
    "joints": {
      "joint_0": 1500,
      "joint_1": 1500,
      "joint_2": 1500,
      "joint_3": 1500,
      "joint_4": 1500,
      "joint_5": 1000
    },
    "pose": {
      "x": 0.0,
      "y": 0.0,
      "z": 295.0,
      "roll": 0.0,
      "pitch": 0.0,
      "yaw": 0.0
    },
    "speed_coefficient": 50,
    "uptime": 3600,
    "timestamp": 1690000000.123
  }
}
```

#### 2.2.3 系统配置

```
GET /api/v1/config
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "speed_coefficient": "50",
    "acceleration_coefficient": "30",
    "sampling_strategy": "grid",
    "grid_spacing": "20",
    "quality_pass_score": "70",
    "cloud_enabled": "true",
    "cloud_sync_interval": "60"
  }
}
```

```
PUT /api/v1/config
```

**请求体:**

```json
{
  "speed_coefficient": "60",
  "grid_spacing": "15"
}
```

**响应:**

```json
{
  "code": 200,
  "message": "配置更新成功",
  "data": {
    "updated": ["speed_coefficient", "grid_spacing"]
  }
}
```

---

### 2.3 机械臂控制接口

#### 2.3.1 多关节移动

```
POST /api/v1/arm/move
```

**请求体:**

```json
{
  "joints": {
    "joint_0": 1500,
    "joint_1": 1200,
    "joint_2": 2000,
    "joint_3": 1500,
    "joint_4": 1500,
    "joint_5": 1000
  },
  "time_ms": 1000,
  "speed": 50
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `joints` | object | 是 | 关节PWM值映射 (joint_0 ~ joint_5) |
| `time_ms` | integer | 否 | 运动时间 (ms), 默认1000 |
| `speed` | integer | 否 | 速度系数 (0-100), 默认50 |

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "command_id": "cmd-abc123",
    "status": "ACCEPTED"
  }
}
```

**cURL 示例:**

```bash
curl -X POST https://sampling-arm-pi.local:8000/api/v1/arm/move \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "joints": {"joint_0":1500,"joint_1":1200,"joint_2":2000,"joint_3":1500,"joint_4":1500,"joint_5":1000},
    "time_ms": 1000,
    "speed": 50
  }'
```

#### 2.3.2 单关节控制

```
POST /api/v1/arm/joint
```

**请求体:**

```json
{
  "joint_id": 0,
  "pwm": 1500,
  "time_ms": 500
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `joint_id` | integer | 是 | 关节ID (0-5) |
| `pwm` | integer | 是 | 目标PWM值 (500-2500) |
| `time_ms` | integer | 否 | 运动时间 (ms), 默认500 |

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "joint_id": 0,
    "target_pwm": 1500,
    "status": "ACCEPTED"
  }
}
```

#### 2.3.3 笛卡尔空间移动

```
POST /api/v1/arm/move_cartesian
```

**请求体:**

```json
{
  "x": 100.0,
  "y": 50.0,
  "z": 200.0,
  "roll": 0.0,
  "pitch": 0.0,
  "yaw": 0.0,
  "speed": 50
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `x` | float | 是 | 目标X坐标 (mm) |
| `y` | float | 是 | 目标Y坐标 (mm) |
| `z` | float | 是 | 目标Z坐标 (mm) |
| `roll` | float | 否 | 滚转角 (rad), 默认0 |
| `pitch` | float | 否 | 俯仰角 (rad), 默认0 |
| `yaw` | float | 否 | 偏航角 (rad), 默认0 |
| `speed` | integer | 否 | 速度系数 (0-100), 默认50 |

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "target_pose": {"x": 100.0, "y": 50.0, "z": 200.0},
    "ik_solution": {"joint_0": 1500, "joint_1": 1200, "joint_2": 1800, "joint_3": 1400, "joint_4": 1500, "joint_5": 1000},
    "status": "ACCEPTED"
  }
}
```

#### 2.3.4 归零

```
POST /api/v1/arm/home
```

**请求体:**

```json
{
  "speed": 50
}
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "HOMING",
    "estimated_time_ms": 3000
  }
}
```

#### 2.3.5 紧急停止

```
POST /api/v1/arm/estop
```

**响应:**

```json
{
  "code": 200,
  "message": "紧急停止已触发",
  "data": {
    "status": "EMERGENCY_STOP",
    "timestamp": 1690000000.123
  }
}
```

#### 2.3.6 清除紧急停止

```
POST /api/v1/arm/estop/clear
```

**响应:**

```json
{
  "code": 200,
  "message": "紧急停止已清除",
  "data": {
    "status": "IDLE"
  }
}
```

#### 2.3.7 查询关节状态

```
GET /api/v1/arm/joints
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "joints": {
      "joint_0": {"pwm": 1500, "angle": 0.0, "speed": 0},
      "joint_1": {"pwm": 1200, "angle": -27.0, "speed": 0},
      "joint_2": {"pwm": 2000, "angle": 45.0, "speed": 0},
      "joint_3": {"pwm": 1500, "angle": 0.0, "speed": 0},
      "joint_4": {"pwm": 1500, "angle": 0.0, "speed": 0},
      "joint_5": {"pwm": 1000, "angle": 0.0, "speed": 0}
    }
  }
}
```

#### 2.3.8 查询末端位姿

```
GET /api/v1/arm/pose
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "position": {"x": 100.5, "y": 50.2, "z": 200.0},
    "orientation": {"roll": 0.0, "pitch": 0.5, "yaw": 0.0},
    "workspace_valid": true
  }
}
```

#### 2.3.9 设置速度

```
POST /api/v1/arm/speed
```

**请求体:**

```json
{
  "speed": 50
}
```

**响应:**

```json
{
  "code": 200,
  "message": "速度设置成功",
  "data": {
    "speed_coefficient": 50
  }
}
```

#### 2.3.10 播放动作组

```
POST /api/v1/arm/action
```

**请求体:**

```json
{
  "action_id": 1
}
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "action_id": 1,
    "status": "PLAYING"
  }
}
```

---

### 2.4 视觉控制接口

#### 2.4.1 颜色检测

```
POST /api/v1/vision/detect/color
```

**请求体:**

```json
{
  "colors": ["red", "blue", "green"],
  "roi": "full"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `colors` | array | 否 | 检测颜色列表, 默认全部 |
| `roi` | string | 否 | ROI区域 (full/center/top/bottom), 默认full |

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "objects": [
      {"color": "red", "x": 120, "y": 80, "width": 30, "height": 25, "area": 650},
      {"color": "blue", "x": 200, "y": 60, "width": 35, "height": 30, "area": 920}
    ],
    "frame_time_ms": 65,
    "count": 2
  }
}
```

#### 2.4.2 AprilTag 检测

```
POST /api/v1/vision/detect/apriltag
```

**请求体:**

```json
{
  "tag_ids": [0, 1, 2]
}
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "tags": [
      {
        "id": 0,
        "family": "TAG36H11",
        "cx": 160,
        "cy": 120,
        "x_trans": 100.5,
        "y_trans": -50.2,
        "z_trans": 300.0,
        "x_rot": 0.05,
        "y_rot": -0.03,
        "z_rot": 1.57,
        "goodness": 0.95
      }
    ],
    "frame_time_ms": 80,
    "count": 1
  }
}
```

#### 2.4.3 质量检测

```
POST /api/v1/vision/inspect
```

**请求体:**

```json
{
  "expected_color": "red",
  "expected_dimensions": {"width": 30, "height": 25}
}
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "pass": true,
    "score": 85.5,
    "details": {
      "defect_score": 38.0,
      "color_score": 25.0,
      "dimension_score": 22.5,
      "defects": [
        {"x": 15, "y": 10, "area": 25, "type": "scratch"}
      ],
      "color_variance": 8.5,
      "dimension_error_mm": 0.8
    },
    "frame_time_ms": 95
  }
}
```

#### 2.4.4 物体分类

```
POST /api/v1/vision/classify
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "category": "block",
    "confidence": 0.92,
    "alternatives": [
      {"category": "cylinder", "confidence": 0.06},
      {"category": "sphere", "confidence": 0.02}
    ],
    "properties": {
      "aspect_ratio": 1.2,
      "roundness": 0.15,
      "area_pixels": 850
    }
  }
}
```

---

### 2.5 任务管理接口

#### 2.5.1 创建任务

```
POST /api/v1/tasks
```

**请求体 (网格采样):**

```json
{
  "name": "区域网格采样-01",
  "type": "grid",
  "params": {
    "region": {
      "x_min": -150,
      "x_max": 150,
      "y_min": -100,
      "y_max": 100,
      "z": 50
    },
    "spacing": 20,
    "approach_height": 50,
    "retract_height": 100,
    "speed": 50,
    "enable_quality_check": true,
    "target_colors": ["red", "blue"]
  }
}
```

**请求体 (自适应采样):**

```json
{
  "name": "自适应采样-01",
  "type": "adaptive",
  "params": {
    "region": {
      "x_min": -100,
      "x_max": 100,
      "y_min": -100,
      "y_max": 100,
      "z": 50
    },
    "initial_spacing": 40,
    "refinement_threshold": 0.8,
    "max_iterations": 3,
    "speed": 50
  }
}
```

**请求体 (定点采样):**

```json
{
  "name": "定点采样-01",
  "type": "targeted",
  "params": {
    "points": [
      {"x": 100, "y": 50, "z": 50, "approach_angle": 0},
      {"x": -50, "y": 80, "z": 50, "approach_angle": 45},
      {"x": 0, "y": -60, "z": 50, "approach_angle": 90}
    ],
    "speed": 50
  }
}
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "task-abc123",
    "name": "区域网格采样-01",
    "type": "grid",
    "status": "pending",
    "total_points": 100,
    "created_at": "2026-07-23T10:00:00Z"
  }
}
```

**cURL 示例:**

```bash
curl -X POST https://sampling-arm-pi.local:8000/api/v1/tasks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "区域网格采样-01",
    "type": "grid",
    "params": {
      "region": {"x_min": -150, "x_max": 150, "y_min": -100, "y_max": 100, "z": 50},
      "spacing": 20,
      "approach_height": 50,
      "retract_height": 100,
      "speed": 50,
      "enable_quality_check": true,
      "target_colors": ["red", "blue"]
    }
  }'
```

#### 2.5.2 任务列表

```
GET /api/v1/tasks?page=1&page_size=20&status=running&type=grid
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | integer | 否 | 页码, 默认1 |
| `page_size` | integer | 否 | 每页数量, 默认20 |
| `status` | string | 否 | 状态筛选 (pending/running/completed/failed) |
| `type` | string | 否 | 类型筛选 (grid/adaptive/targeted) |

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "task_id": "task-abc123",
        "name": "区域网格采样-01",
        "type": "grid",
        "status": "running",
        "progress": {"completed": 45, "total": 100, "percentage": 45.0},
        "total_points": 100,
        "created_at": "2026-07-23T10:00:00Z",
        "started_at": "2026-07-23T10:00:05Z"
      }
    ],
    "total": 25,
    "page": 1,
    "page_size": 20
  }
}
```

#### 2.5.3 任务详情

```
GET /api/v1/tasks/{task_id}
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "task-abc123",
    "name": "区域网格采样-01",
    "type": "grid",
    "status": "running",
    "params": {
      "region": {"x_min": -150, "x_max": 150, "y_min": -100, "y_max": 100, "z": 50},
      "spacing": 20,
      "speed": 50
    },
    "progress": {
      "completed": 45,
      "total": 100,
      "percentage": 45.0,
      "current_point": {"x": 50, "y": 30, "z": 50}
    },
    "statistics": {
      "samples_found": 42,
      "samples_missed": 3,
      "quality_pass_rate": 88.0,
      "average_cycle_time_ms": 2500
    },
    "created_at": "2026-07-23T10:00:00Z",
    "started_at": "2026-07-23T10:00:05Z",
    "estimated_completion": "2026-07-23T10:04:30Z"
  }
}
```

#### 2.5.4 取消任务

```
DELETE /api/v1/tasks/{task_id}
```

**响应:**

```json
{
  "code": 200,
  "message": "任务已取消",
  "data": {
    "task_id": "task-abc123",
    "status": "cancelled"
  }
}
```

#### 2.5.5 启动任务

```
POST /api/v1/tasks/{task_id}/start
```

**响应:**

```json
{
  "code": 200,
  "message": "任务已启动",
  "data": {
    "task_id": "task-abc123",
    "status": "running"
  }
}
```

#### 2.5.6 暂停任务

```
POST /api/v1/tasks/{task_id}/pause
```

**响应:**

```json
{
  "code": 200,
  "message": "任务已暂停",
  "data": {
    "task_id": "task-abc123",
    "status": "paused",
    "progress": {"completed": 45, "total": 100}
  }
}
```

#### 2.5.7 恢复任务

```
POST /api/v1/tasks/{task_id}/resume
```

**响应:**

```json
{
  "code": 200,
  "message": "任务已恢复",
  "data": {
    "task_id": "task-abc123",
    "status": "running"
  }
}
```

---

### 2.6 采样记录接口

#### 2.6.1 采样记录列表

```
GET /api/v1/samples?task_id=task-abc123&page=1&page_size=50
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 否 | 按任务筛选 |
| `page` | integer | 否 | 页码, 默认1 |
| `page_size` | integer | 否 | 每页数量, 默认50 |
| `color` | string | 否 | 按颜色筛选 |
| `quality_pass` | boolean | 否 | 按质量是否通过筛选 |

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "task_id": "task-abc123",
        "point_index": 0,
        "position": {"x": -150, "y": -100, "z": 50},
        "joints": {"joint_0": 1400, "joint_1": 1300, "joint_2": 1800, "joint_3": 1500, "joint_4": 1500, "joint_5": 1000},
        "color": "red",
        "category": "block",
        "quality_score": 85.5,
        "has_defect": false,
        "timestamp": "2026-07-23T10:00:08Z"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 50
  }
}
```

#### 2.6.2 采样详情

```
GET /api/v1/samples/{sample_id}
```

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "task_id": "task-abc123",
    "point_index": 0,
    "position": {"x": -150, "y": -100, "z": 50},
    "joints": {"joint_0": 1400, "joint_1": 1300, "joint_2": 1800, "joint_3": 1500, "joint_4": 1500, "joint_5": 1000},
    "color": "red",
    "category": "block",
    "quality_score": 85.5,
    "has_defect": false,
    "quality_details": {
      "defect_score": 38.0,
      "color_score": 25.0,
      "dimension_score": 22.5
    },
    "has_image": true,
    "image_url": "/api/v1/samples/1/image",
    "timestamp": "2026-07-23T10:00:08Z"
  }
}
```

---

### 2.7 事件日志接口

#### 2.7.1 事件列表

```
GET /api/v1/events?type=ERROR&source=safety_agent&page=1&page_size=50
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 否 | 事件类型 (INFO/WARNING/ERROR/SAFETY) |
| `source` | string | 否 | 事件来源 |
| `page` | integer | 否 | 页码, 默认1 |
| `page_size` | integer | 否 | 每页数量, 默认50 |
| `start_time` | string | 否 | 起始时间 (ISO 8601) |
| `end_time` | string | 否 | 截止时间 (ISO 8601) |

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "event_type": "ERROR",
        "source": "safety_agent",
        "message": "Joint 2 current over threshold",
        "details": {
          "joint_id": 2,
          "current_ma": 1500,
          "threshold_ma": 800,
          "action": "EMERGENCY_STOP"
        },
        "timestamp": "2026-07-23T10:10:00Z"
      }
    ],
    "total": 50,
    "page": 1,
    "page_size": 50
  }
}
```

---

### 2.8 遥测接口

#### 2.8.1 遥测数据查询

```
GET /api/v1/telemetry?start_time=2026-07-23T10:00:00Z&end_time=2026-07-23T11:00:00Z&limit=100
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `start_time` | string | 否 | 起始时间 (ISO 8601) |
| `end_time` | string | 否 | 截止时间 (ISO 8601) |
| `limit` | integer | 否 | 最大返回条数, 默认100 |

**响应:**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "joint_0": 1500,
        "joint_1": 1200,
        "joint_2": 2000,
        "joint_3": 1500,
        "joint_4": 1500,
        "joint_5": 1000,
        "pos_x": 100.5,
        "pos_y": 50.2,
        "pos_z": 200.0,
        "speed": 500,
        "status": "MOVING",
        "timestamp": "2026-07-23T10:00:10.500Z"
      }
    ],
    "total": 1000,
    "returned": 100
  }
}
```

---

## 3. WebSocket API

### 3.1 连接

```
URL: wss://sampling-arm-pi.local:8001/ws
或:  wss://api.your-domain.com/ws
```

**连接时携带认证:**

```
wss://sampling-arm-pi.local:8001/ws?token=<access_token>
```

### 3.2 客户端 → 服务端消息

#### 3.2.1 订阅遥测

```json
{
  "type": "subscribe",
  "channel": "telemetry",
  "params": {
    "interval_ms": 100
  }
}
```

| 通道 | 说明 |
|------|------|
| `telemetry` | 实时关节角度/位姿/状态 |
| `status` | 系统状态变更 |
| `events` | 事件通知 |
| `task_progress` | 任务进度更新 |

#### 3.2.2 取消订阅

```json
{
  "type": "unsubscribe",
  "channel": "telemetry"
}
```

#### 3.2.3 发送控制命令

```json
{
  "type": "command",
  "action": "estop",
  "params": {}
}
```

### 3.3 服务端 → 客户端消息

#### 3.3.1 遥测数据 (10Hz)

```json
{
  "type": "telemetry",
  "timestamp": 1690000000.123,
  "data": {
    "joints": [1500, 1200, 2000, 1500, 1500, 1000],
    "pose": {
      "position": {"x": 100.5, "y": 50.2, "z": 200.0},
      "orientation": {"roll": 0.0, "pitch": 0.5, "yaw": 0.0}
    },
    "system_status": "MOVING",
    "safety_status": "NORMAL",
    "speed": 500,
    "current_task": "task-abc123",
    "task_progress": 45.0
  }
}
```

#### 3.3.2 状态变更

```json
{
  "type": "status",
  "timestamp": 1690000000.123,
  "data": {
    "previous_status": "IDLE",
    "current_status": "MOVING",
    "reason": "任务启动"
  }
}
```

#### 3.3.3 事件通知

```json
{
  "type": "event",
  "timestamp": 1690000000.123,
  "data": {
    "event_type": "WARNING",
    "source": "safety_agent",
    "message": "Joint 1 approaching limit",
    "severity": "medium"
  }
}
```

#### 3.3.4 任务进度

```json
{
  "type": "task_progress",
  "timestamp": 1690000000.123,
  "data": {
    "task_id": "task-abc123",
    "completed": 45,
    "total": 100,
    "percentage": 45.0,
    "current_point": {"x": 50, "y": 30, "z": 50},
    "status": "running"
  }
}
```

#### 3.3.5 错误通知

```json
{
  "type": "error",
  "timestamp": 1690000000.123,
  "data": {
    "code": 500,
    "message": "通讯超时: STM32 无响应",
    "severity": "critical"
  }
}
```

### 3.4 WebSocket 连接示例 (JavaScript)

```javascript
const ws = new WebSocket('wss://sampling-arm-pi.local:8001/ws?token=<access_token>');

ws.onopen = () => {
  console.log('WebSocket 连接成功');
  
  // 订阅遥测
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'telemetry',
    params: { interval_ms: 100 }
  }));
  
  // 订阅事件
  ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'events'
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  switch (msg.type) {
    case 'telemetry':
      updateDashboard(msg.data);
      break;
    case 'status':
      updateStatus(msg.data);
      break;
    case 'event':
      showNotification(msg.data);
      break;
    case 'error':
      showError(msg.data);
      break;
  }
};

ws.onclose = () => {
  console.log('WebSocket 连接关闭');
  // 自动重连
  setTimeout(connectWebSocket, 3000);
};
```

---

## 4. STM32-RPi UART 协议

### 4.1 物理层参数

| 参数 | 值 |
|------|------|
| 接口 | UART1 (PA9/PA10) |
| 波特率 | 115200 bps |
| 数据位 | 8 |
| 停止位 | 1 |
| 校验位 | 无 |
| 电平 | 3.3V TTL |
| RPi设备路径 | /dev/serial0 |

### 4.2 帧格式

```
命令帧:  #<CMD>:<PARAM1>,<PARAM2>,...,<PARAMN>!\r\n
响应帧:  #<CMD>:<STATUS>[,<DATA>]!\r\n
```

### 4.3 命令参考

#### 4.3.1 机械臂控制 (ARM)

**多关节同步控制:**

```
发送: #ARM:J0,1500,J1,1200,J2,2000,J3,1500,J4,1500,J5,1000!
响应: #ARM:OK!
```

**带时间参数:**

```
发送: #ARM:J0,1500,J1,1200,J2,2000,J3,1500,J4,1500,J5,1000,T1000!
响应: #ARM:OK!
```

#### 4.3.2 单关节控制 (JNT)

```
发送: #JNT:0,1500,1000!
响应: #JNT:OK!
```

格式: `JNT:<joint_id>,<pwm>,<time_ms>!`

#### 4.3.3 动作组 (ACT)

```
发送: #ACT:1!
响应: #ACT:OK!
```

#### 4.3.4 状态查询 (STATUS)

```
发送: #STATUS:?!
响应: #STATUS:IDLE,J0=1500,J1=1200,J2=2000,J3=1500,J4=1500,J5=1000!
```

#### 4.3.5 紧急停止 (ESTOP)

```
发送: #ESTOP:!
响应: #ESTOP:OK!
```

#### 4.3.6 归零 (HOME)

```
发送: #HOME:!
响应: #HOME:OK!
```

#### 4.3.7 速度设置 (SPEED)

```
发送: #SPEED:50!
响应: #SPEED:OK!
```

#### 4.3.8 加速度设置 (ACC)

```
发送: #ACC:30!
响应: #ACC:OK!
```

#### 4.3.9 视觉命令转发 (VIS)

```
发送: #VIS:color_tracing!
响应: #VIS:OK!
```

#### 4.3.10 传感器读取 (SENS)

```
发送: #SENS:0!
响应: #SENS:OK,1024,512!
```

#### 4.3.11 配置读写 (CONF)

```
发送: #CONF:WR,joint_limit_0_min,500!
响应: #CONF:OK!

发送: #CONF:RD,joint_limit_0_min!
响应: #CONF:OK,500!
```

#### 4.3.12 心跳 (PING)

```
发送: #PING:!
响应: #PING:PONG,1690000000!
```

#### 4.3.13 固件信息 (INFO)

```
发送: #INFO:?!
响应: #INFO:智能采样机械臂,v2.0.0,STM32F103C8T6!
```

### 4.4 响应状态码

| 状态 | 含义 |
|------|------|
| `OK` | 命令执行成功 |
| `ERR` | 命令执行失败 |
| `BUSY` | 系统正忙 |
| `ESTOP` | 处于紧急停止状态 |
| `LIMIT` | 关节超出限位 |
| `TIMEOUT` | 命令执行超时 |
| `IDLE` | 系统空闲 |
| `MOVING` | 机械臂运动中 |
| `HOMING` | 正在归零 |

---

## 5. OpenMV-RPi 视觉协议

### 5.1 物理层参数

| 参数 | 值 |
|------|------|
| 接口 | UART2 (PA2/PA3, 经STM32转发) |
| 波特率 | 115200 bps |
| 数据位 | 8 |
| 停止位 | 1 |
| 校验位 | 无 |

### 5.2 命令格式

```
命令帧:  #<CMD>!
响应帧:  #<CMD>:<JSON_DATA>!
```

### 5.3 命令参考

#### 5.3.1 多色追踪

```
命令: #color_tracing!
响应: #color_tracing:{"red":[{"x":120,"y":80,"w":30,"h":25,"area":650}],"blue":[],"green":[],"yellow":[]}!
```

#### 5.3.2 单色追踪

```
命令: #color_track!
响应: #color_track:{"color":"red","x":120,"y":80,"w":30,"h":25,"area":650}!
```

#### 5.3.3 颜色分拣

```
命令: #color_stacking!
响应: #color_stacking:{"detected":"red","count":3}!
```

#### 5.3.4 人脸追踪

```
命令: #face_tracking!
响应: #face_tracking:{"face":{"x":160,"y":120,"w":80,"h":80}}!
```

#### 5.3.5 AprilTag 检测

```
命令: #apriltag_sorting!
响应: #apriltag_sorting:{"tags":[{"id":0,"x":100.5,"y":-50.2,"z":300.0,"rx":0.05,"ry":-0.03,"rz":1.57}]}!
```

#### 5.3.6 AprilTag 堆叠检测

```
命令: #apriltag_stacking!
响应: #apriltag_stacking:{"tags":[{"id":0,"x":100.5,"y":-50.2,"z":300.0}]}!
```

#### 5.3.7 质量检测

```
命令: #quality_check!
响应: #quality_check:{"pass":true,"score":85.5,"defects":[]}!
```

#### 5.3.8 物体分类

```
命令: #classify!
响应: #classify:{"category":"block","confidence":0.92}!
```

#### 5.3.9 视频流控制

```
命令: #stream_on!
响应: #stream_on:OK!

命令: #stream_off!
响应: #stream_off:OK!
```

#### 5.3.10 相机标定

```
命令: #calibrate!
响应: #calibrate:{"fx":315.0,"fy":315.0,"cx":160.0,"cy":120.0}!
```

### 5.4 数据格式

#### 颜色检测响应

```json
{
  "red": [
    {"x": 120, "y": 80, "w": 30, "h": 25, "area": 650}
  ],
  "blue": [],
  "green": [],
  "yellow": []
}
```

#### AprilTag 响应

```json
{
  "tags": [
    {
      "id": 0,
      "family": "TAG36H11",
      "cx": 160,
      "cy": 120,
      "x": 100.5,
      "y": -50.2,
      "z": 300.0,
      "rx": 0.05,
      "ry": -0.03,
      "rz": 1.57,
      "goodness": 0.95
    }
  ]
}
```

---

## 6. 错误码

### 6.1 HTTP 状态码

| 状态码 | 说明 | 处理建议 |
|--------|------|---------|
| 200 | 成功 | - |
| 201 | 创建成功 | - |
| 400 | 请求参数错误 | 检查请求体格式和参数 |
| 401 | 未认证 | 检查 Token 是否有效 |
| 403 | 无权限 | 检查用户角色权限 |
| 404 | 资源不存在 | 检查 ID 是否正确 |
| 409 | 冲突 | 资源已存在或状态冲突 |
| 429 | 请求过于频繁 | 降低请求频率 |
| 500 | 服务器内部错误 | 查看服务器日志 |
| 503 | 服务不可用 | 系统紧急停止中，等待恢复 |

### 6.2 应用错误码

| 错误码 | 说明 |
|--------|------|
| `ARM_001` | 关节超出限位 |
| `ARM_002` | 目标位置在工作空间外 |
| `ARM_003` | 逆运动学无解 |
| `ARM_004` | 运动执行超时 |
| `ARM_005` | 紧急停止中，无法执行命令 |
| `VIS_001` | 视觉处理器无响应 |
| `VIS_002` | 未检测到目标 |
| `VIS_003` | 相机标定参数无效 |
| `TASK_001` | 任务创建失败 |
| `TASK_002` | 任务状态不允许此操作 |
| `TASK_003` | 任务参数无效 |
| `COMM_001` | STM32 通信超时 |
| `COMM_002` | 命令响应格式错误 |
| `COMM_003` | 命令被拒绝 |
| `SYS_001` | 系统资源不足 |
| `SYS_002` | 数据库错误 |
| `SYS_003` | 配置错误 |
| `SEC_001` | Token 已过期 |
| `SEC_002` | Token 无效 |
| `SEC_003` | 密码错误 |

### 6.3 错误响应示例

```json
{
  "code": 400,
  "message": "关节超出限位",
  "data": null,
  "error": {
    "type": "ARM_001",
    "details": "joint_1 target_pwm=3000 exceeds max_pwm=2400",
    "timestamp": "2026-07-23T10:10:00Z"
  }
}
```

---

## 7. 速率限制

### 7.1 限制策略

| 端点 | 限制 | 时间窗口 | 超出后行为 |
|------|------|---------|-----------|
| `/api/v1/auth/login` | 5 次 | 1 分钟 | 返回 429, 锁定 5 分钟 |
| `/api/v1/arm/*` | 30 次 | 1 分钟 | 返回 429 |
| `/api/v1/tasks` (POST) | 10 次 | 1 分钟 | 返回 429 |
| `/api/v1/vision/*` | 10 次 | 1 分钟 | 返回 429 |
| 全局 | 100 次 | 1 分钟 | 返回 429 |

### 7.2 速率限制响应头

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1690000060
Retry-After: 5
```

### 7.3 429 响应示例

```json
{
  "code": 429,
  "message": "请求过于频繁，请稍后再试",
  "data": {
    "retry_after": 5
  }
}
```

---

## 8. 版本策略

### 8.1 API 版本化

- URL 路径版本化: `/api/v1/`, `/api/v2/`
- 当前版本: `v1`
- 主版本号变更时更新 URL 路径

### 8.2 兼容性承诺

| 变更类型 | 是否兼容 | 说明 |
|---------|---------|------|
| 新增端点 | 是 | 不影响现有端点 |
| 新增可选字段 | 是 | 响应中添加新字段 |
| 新增必填字段 | 否 | 需要升级 API 版本 |
| 删除字段 | 否 | 需要升级 API 版本 |
| 修改字段类型 | 否 | 需要升级 API 版本 |
| 修改错误码 | 否 | 需要升级 API 版本 |

### 8.3 废弃策略

- 废弃端点至少在 2 个次要版本中继续可用
- 废弃端点响应头包含: `Deprecation: true`
- 废弃端点响应头包含: `Sunset: <date>`

---

## 附录

### A. 完整请求示例

#### A.1 创建并执行网格采样任务

```bash
#!/bin/bash

BASE_URL="https://sampling-arm-pi.local:8000/api/v1"

# 1. 登录
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}' \
  | jq -r '.data.access_token')

echo "Token: $TOKEN"

# 2. 归零
curl -s -X POST "$BASE_URL/arm/home" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"speed": 50}' | jq

# 3. 创建任务
TASK_ID=$(curl -s -X POST "$BASE_URL/tasks" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试网格采样",
    "type": "grid",
    "params": {
      "region": {"x_min": -100, "x_max": 100, "y_min": -50, "y_max": 50, "z": 50},
      "spacing": 20,
      "approach_height": 50,
      "retract_height": 100,
      "speed": 50,
      "enable_quality_check": true,
      "target_colors": ["red", "blue"]
    }
  }' | jq -r '.data.task_id')

echo "Task ID: $TASK_ID"

# 4. 启动任务
curl -s -X POST "$BASE_URL/tasks/$TASK_ID/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq

# 5. 查询任务进度
sleep 5
curl -s -X GET "$BASE_URL/tasks/$TASK_ID" \
  -H "Authorization: Bearer $TOKEN" | jq

# 6. 查询采样记录
curl -s -X GET "$BASE_URL/samples?task_id=$TASK_ID" \
  -H "Authorization: Bearer $TOKEN" | jq
```

#### A.2 WebSocket 实时监控 (Python)

```python
import asyncio
import json
import websockets

async def monitor():
    uri = "wss://sampling-arm-pi.local:8001/ws?token=<access_token>"
    
    async with websockets.connect(uri) as ws:
        # 订阅遥测
        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "telemetry",
            "params": {"interval_ms": 100}
        }))
        
        # 订阅事件
        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "events"
        }))
        
        # 接收消息
        async for message in ws:
            data = json.loads(message)
            if data["type"] == "telemetry":
                print(f"Joints: {data['data']['joints']}")
                print(f"Status: {data['data']['system_status']}")
            elif data["type"] == "event":
                print(f"Event: {data['data']['message']}")

asyncio.run(monitor())
```

---

## 9. 多端互通 API (v1)

> 多端互通服务器: App (Android/iOS) / 微信小程序 / Web / 硬件端 (RPi / ESP32 / STM32 / OpenMV)
> 通过统一的账号体系、设备中心与 WebSocket 中枢实现数据互通。

### 9.1 鉴权 (账号体系)

所有端共享同一套账号。密码使用 PBKDF2-HMAC-SHA256 哈希,
Token 仅存 SHA-256 哈希, 不存明文。

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 注册并返回 token | 否 |
| POST | `/api/v1/auth/login` | 登录并返回 token | 否 |
| POST | `/api/v1/auth/logout` | 吊销当前用户全部 token | Bearer |
| GET | `/api/v1/auth/me` | 当前用户信息 | Bearer |

**请求/响应示例 (login):**

```json
// 请求
{ "username": "alice", "password": "secret123", "scope": "app" }

// 响应
{
  "access_token": "<hex-token>",
  "token_type": "bearer",
  "expires_in": 604800,
  "user": { "id": "...", "username": "alice", "role": "user", "enabled": true }
}
```

**鉴权方式:** 请求头 `Authorization: Bearer <access_token>` 或 `X-API-Key: <token>`。
未提供或无效返回 `401`。

### 9.2 设备中心 (设备注册与心跳)

每个端 (App / 小程序 / Web / 硬件) 注册为一条设备记录, 服务端按
`device_id + client_type` 路由遥测与命令。

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/v1/devices/register` | 注册 / 心跳更新 | Bearer |
| GET | `/api/v1/devices` | 设备列表 (可按 `client_type`/`status` 过滤) | Bearer |
| GET | `/api/v1/devices/{id}` | 单个设备详情 | Bearer |
| POST | `/api/v1/devices/{id}/offline` | 标记设备离线 | Bearer |

**设备注册请求示例:**

```json
{
  "device_id": "app-alice",
  "name": "App-Alice",
  "device_type": "app",
  "client_type": "app",
  "mac": null,
  "ip": "192.168.1.50",
  "firmware_version": "1.0.0",
  "extra": { "platform": "android", "app_version": "1.0.0" }
}
```

### 9.3 WiFi / ESP32 配网 API

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/v1/wifi/status` | ESP32 / WiFi 模块状态 | Bearer |
| POST | `/api/v1/wifi/connect` | STA 连接现有热点 | Bearer |
| POST | `/api/v1/wifi/hotspot` | AP 创建软热点 | Bearer |
| GET | `/api/v1/wifi/scan` | 扫描周边 AP | Bearer |
| POST | `/api/v1/wifi/reset` | ESP32 软复位 | Bearer |

**connect 请求/响应示例:**

```json
// 请求
{ "ssid": "HomeWiFi", "password": "12345678", "timeout": 15.0 }

// 响应
{ "status": "ok", "ssid": "HomeWiFi", "ip": "192.168.1.100", "mode": "sta" }
```

### 9.4 WebSocket 多端互通中枢 `/ws/hub`

App / 小程序 / Web / 硬件端 通过 `/ws/hub` 建立长连接统一互通。

**连接协议 (JSON):**

```
Client -> Hub:
  {"type":"hello", "device_id":"app-alice", "client_type":"app",
   "device_type":"app", "role":"controller|observer", "name":"App-Alice"}
  {"type":"command", "target":"<device_id>|all|hardware",
   "action":"wifi.scan", "payload": {...}, "seq": 1001}
  {"type":"telemetry", "data": {...}}
  {"type":"ping"}

Hub -> Client:
  {"type":"welcome", "client_id":"...", "device_id":"..."}
  {"type":"command_ack", "seq":1001, "status":"ok", "targets":[...]}
  {"type":"command", "from":"app-alice", "action":"wifi.scan", "payload":{...}}
  {"type":"telemetry", "from":"esp32-01", "data":{...}}
  {"type":"device_status", "device_id":"esp32-01", "status":"online|offline"}
  {"type":"pong"}
```

**特性:**
- 首次 `hello` 绑定 `device_id + client_type`, 自动写入设备中心 (online)
- `command.target` 支持指定设备 / `all` / `hardware` 三类路由
- 断连时自动标记设备 offline 并广播 `device_status`
- 在线设备快照: `GET /api/v1/hub/devices`

### B. 文档变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0.0 | 2026-01-15 | 初始版本 | 项目组 |
| v2.0.0 | 2026-07-23 | 增加 WebSocket、UART 协议、完整示例 | 项目组 |
| v2.1.0 | 2026-08-14 | 增加多端互通 API: 鉴权 / 设备中心 / WiFi 配网 / WebSocket 中枢 | 项目组 |