/**
  ******************************************************************************
  * @file    USER/app_arm.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   机械臂控制模块实现
  *          负责机械臂关节空间运动控制
  *          支持单关节移动、多关节联动、原点回归
  *          任务队列缓冲: 最多10个任务
  *          加减速梯形速度规划: 平滑启停
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include "app_arm.h"
#include "y_bus_servo.h"
#include <string.h>

/* 外部函数声明 ----------------------------------------------------------------*/
extern uint32_t get_systick(void);				/* 获取系统滴答 */

/* 全局变量定义 ----------------------------------------------------------------*/

/**
  * @brief  当前机械臂状态
  */
arm_state_t arm_current_state = ARM_STATE_IDLE;

/* 私有变量 --------------------------------------------------------------------*/
static arm_move_task_t arm_task_queue[ARM_QUEUE_SIZE];	/* 任务队列 */
static uint8_t         arm_queue_head;					/* 队列头指针 */
static uint8_t         arm_queue_tail;					/* 队列尾指针 */
static uint8_t         arm_queue_count;				/* 队列中任务数量 */
static uint16_t        arm_ramp_positions[ARM_JOINT_NUM];	/* 加减速中间位置 */
static uint16_t        arm_target_positions[ARM_JOINT_NUM];	/* 目标位置 */
static uint32_t        arm_ramp_last_time;				/* 上次加减速更新时间 */
static uint8_t         arm_ramp_active;				/* 加减速是否激活 */

/* 私有函数声明 ----------------------------------------------------------------*/
static uint8_t  arm_queue_push(arm_move_task_t *task);
static uint8_t  arm_queue_pop(arm_move_task_t *task);
static void     arm_process_task(arm_move_task_t *task);
static void     arm_start_ramp(void);
static uint8_t  arm_update_ramp(void);

/**
  * @brief  机械臂控制模块初始化
  * @param  无
  * @返回值 无
  * @说明   初始化状态、任务队列和原点位置
  */
void app_arm_init(void)
{
	uint8_t i;

	/* 初始化状态 */
	arm_current_state = ARM_STATE_IDLE;

	/* 初始化任务队列 */
	arm_queue_head  = 0;
	arm_queue_tail  = 0;
	arm_queue_count = 0;
	memset(arm_task_queue, 0, sizeof(arm_task_queue));

	/* 初始化加减速中间位置 */
	for (i = 0; i < ARM_JOINT_NUM; i++)
	{
		arm_ramp_positions[i]  = ARM_ORIGIN_PWM;
		arm_target_positions[i] = ARM_ORIGIN_PWM;
	}

	arm_ramp_active    = 0;
	arm_ramp_last_time = 0;
}

/**
  * @brief  机械臂控制运行函数
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，处理任务队列和加减速
  */
void app_arm_run(void)
{
	arm_move_task_t task;

	/* 处理加减速 */
	if (arm_ramp_active)
	{
		if (arm_update_ramp() == 0)
		{
			/* 加减速完成，继续处理队列 */
			arm_ramp_active = 0;
		}
		else
		{
			/* 还在加减速中，不处理新任务 */
			return;
		}
	}

	/* 处理任务队列 */
	if (arm_queue_count > 0 && arm_current_state != ARM_STATE_MOVING)
	{
		if (arm_queue_pop(&task) == 0)
		{
			arm_process_task(&task);
		}
	}
	else if (arm_queue_count == 0 && arm_current_state == ARM_STATE_MOVING)
	{
		/* 队列空且运动完成 */
		arm_current_state = ARM_STATE_IDLE;
	}
}

/**
  * @brief  任务入队
  * @param  task: 任务指针
  * @返回值 0: 成功, 1: 队列满
  */
static uint8_t arm_queue_push(arm_move_task_t *task)
{
	if (arm_queue_count >= ARM_QUEUE_SIZE)
	{
		return 1;	/* 队列已满 */
	}

	/* 复制任务到队列 */
	memcpy(&arm_task_queue[arm_queue_tail], task, sizeof(arm_move_task_t));

	/* 更新尾指针 */
	arm_queue_tail = (arm_queue_tail + 1) % ARM_QUEUE_SIZE;
	arm_queue_count++;

	return 0;
}

/**
  * @brief  任务出队
  * @param  task: 输出任务指针
  * @返回值 0: 成功, 1: 队列空
  */
static uint8_t arm_queue_pop(arm_move_task_t *task)
{
	if (arm_queue_count == 0)
	{
		return 1;	/* 队列为空 */
	}

	/* 复制任务 */
	memcpy(task, &arm_task_queue[arm_queue_head], sizeof(arm_move_task_t));

	/* 更新头指针 */
	arm_queue_head = (arm_queue_head + 1) % ARM_QUEUE_SIZE;
	arm_queue_count--;

	return 0;
}

/**
  * @brief  处理移动任务
  * @param  task: 任务指针
  * @返回值 无
  * @说明   根据任务类型发送舵机命令，启动加减速
  */
static void arm_process_task(arm_move_task_t *task)
{
	uint8_t i;

	/* 更新目标位置 */
	for (i = 0; i < ARM_JOINT_NUM; i++)
	{
		arm_target_positions[i] = task->positions[i];
	}

	/* 设置状态为运动中 */
	arm_current_state = ARM_STATE_MOVING;

	/* 启动加减速 */
	arm_start_ramp();
}

/**
  * @brief  启动加减速
  * @param  无
  * @返回值 无
  * @说明   初始化加减速，从当前位置开始
  */
static void arm_start_ramp(void)
{
	uint8_t i;

	/* 记录当前位置作为起始位置 */
	for (i = 0; i < ARM_JOINT_NUM; i++)
	{
		arm_ramp_positions[i] = bus_servo_get_position(i);
	}

	arm_ramp_active    = 1;
	arm_ramp_last_time = get_systick();
}

/**
  * @brief  更新加减速
  * @param  无
  * @返回值 0: 完成, 1: 进行中
  * @说明   梯形速度规划: 加速-匀速-减速
  */
static uint8_t arm_update_ramp(void)
{
	uint32_t now = get_systick();
	uint8_t  i;
	uint8_t  all_done = 1;
	int16_t  diff;

	/* 检查时间间隔 */
	if ((now - arm_ramp_last_time) < ARM_RAMP_INTERVAL)
	{
		return 1;	/* 时间未到 */
	}

	arm_ramp_last_time = now;

	/* 对每个关节进行加减速 */
	for (i = 0; i < ARM_JOINT_NUM; i++)
	{
		diff = (int16_t)arm_target_positions[i] - (int16_t)arm_ramp_positions[i];

		if (diff > 0)
		{
			/* 正向移动 */
			if (diff > ARM_RAMP_STEP)
			{
				arm_ramp_positions[i] += ARM_RAMP_STEP;
				all_done = 0;
			}
			else
			{
				arm_ramp_positions[i] = arm_target_positions[i];
			}
		}
		else if (diff < 0)
		{
			/* 反向移动 */
			if (-diff > ARM_RAMP_STEP)
			{
				arm_ramp_positions[i] -= ARM_RAMP_STEP;
				all_done = 0;
			}
			else
			{
				arm_ramp_positions[i] = arm_target_positions[i];
			}
		}
		/* diff == 0: 已到达目标 */
	}

	/* 发送中间位置到舵机 */
	bus_servo_set_all(arm_ramp_positions, ARM_RAMP_INTERVAL);

	/* 如果所有关节都到达目标，完成 */
	if (all_done)
	{
		arm_ramp_active = 0;
		return 0;
	}

	return 1;
}

/**
  * @brief  移动单个关节
  * @param  joint_id: 关节ID (0~5)
  * @param  pwm: 目标PWM值
  * @param  time: 运动时间(ms)
  * @返回值 无
  * @说明   将单个关节移动任务加入队列
  */
void app_arm_move_joint(uint8_t joint_id, uint16_t pwm, uint16_t time)
{
	arm_move_task_t task;
	uint8_t i;

	if (joint_id >= ARM_JOINT_NUM)
	{
		return;
	}

	/* 构建任务 */
	task.is_all_joints = 0;
	task.move_time     = time;

	/* 保持其他关节当前位置不变 */
	for (i = 0; i < ARM_JOINT_NUM; i++)
	{
		task.positions[i] = bus_servo_get_position(i);
	}

	/* 设置目标关节位置 */
	task.positions[joint_id] = pwm;

	/* 加入队列 */
	arm_queue_push(&task);
}

/**
  * @brief  移动所有关节
  * @param  positions: 6个关节的目标PWM值数组
  * @param  time: 运动时间(ms)
  * @返回值 无
  * @说明   将全身移动任务加入队列，所有关节同时运动
  */
void app_arm_move_all(uint16_t positions[6], uint16_t time)
{
	arm_move_task_t task;
	uint8_t i;

	/* 构建任务 */
	task.is_all_joints = 1;
	task.move_time     = time;

	for (i = 0; i < ARM_JOINT_NUM; i++)
	{
		/* 限制PWM范围 */
		if (positions[i] < 500)  positions[i] = 500;
		if (positions[i] > 2500) positions[i] = 2500;
		task.positions[i] = positions[i];
	}

	/* 加入队列 */
	arm_queue_push(&task);
}

/**
  * @brief  停止所有运动
  * @param  无
  * @返回值 无
  * @说明   清空任务队列，停止所有舵机
  */
void app_arm_stop(void)
{
	/* 清空任务队列 */
	arm_queue_head  = 0;
	arm_queue_tail  = 0;
	arm_queue_count = 0;

	/* 停止加减速 */
	arm_ramp_active = 0;

	/* 停止所有舵机 */
	bus_servo_stop();

	/* 更新状态 */
	arm_current_state = ARM_STATE_IDLE;
}

/**
  * @brief  回到原点位置
  * @param  无
  * @返回值 无
  * @说明   所有关节回到中心位置(PWM=1500)
  */
void app_arm_origin(void)
{
	uint16_t positions[ARM_JOINT_NUM];
	uint8_t  i;

	/* 设置所有关节为原点位置 */
	for (i = 0; i < ARM_JOINT_NUM; i++)
	{
		positions[i] = ARM_ORIGIN_PWM;
	}

	/* 设置回零状态 */
	arm_current_state = ARM_STATE_HOMING;

	/* 移动所有关节到原点 */
	app_arm_move_all(positions, 2000);
}

/**
  * @brief  获取机械臂状态
  * @param  无
  * @返回值 当前机械臂状态枚举值
  */
uint8_t app_arm_get_status(void)
{
	return (uint8_t)arm_current_state;
}

/**
  * @brief  获取当前关节位置
  * @param  joint_id: 关节ID (0~5)
  * @返回值 当前位置PWM值
  */
uint16_t app_arm_get_position(uint8_t joint_id)
{
	if (joint_id >= ARM_JOINT_NUM)
	{
		return 0;
	}

	return bus_servo_get_position(joint_id);
}

/**
  * @brief  获取所有关节当前位置
  * @param  positions: 输出数组，存储6个关节当前位置
  * @返回值 无
  */
void app_arm_get_all_positions(uint16_t positions[6])
{
	uint8_t i;

	for (i = 0; i < ARM_JOINT_NUM; i++)
	{
		positions[i] = bus_servo_get_position(i);
	}
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/