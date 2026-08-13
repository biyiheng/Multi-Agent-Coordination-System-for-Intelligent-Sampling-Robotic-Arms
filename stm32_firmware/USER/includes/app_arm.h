/**
  ******************************************************************************
  * @file    USER/includes/app_arm.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   机械臂控制模块头文件
  *          负责机械臂关节空间运动控制
  *          支持单关节移动、多关节联动、原点回归
  *          任务队列缓冲和加减速梯形速度规划
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __APP_ARM_H
#define __APP_ARM_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"

/* 宏定义 ----------------------------------------------------------------------*/
#define ARM_JOINT_NUM			6			/* 关节数量 */
#define ARM_QUEUE_SIZE			10			/* 任务队列大小 */
#define ARM_RAMP_STEP			10			/* 加减速步长(PWM值) */
#define ARM_RAMP_INTERVAL		20			/* 加减速间隔(ms) */
#define ARM_ORIGIN_PWM			1500		/* 原点位置PWM值 */

/* 机械臂状态枚举 --------------------------------------------------------------*/

/**
  * @brief  机械臂运行状态枚举
  */
typedef enum
{
	ARM_STATE_IDLE    = 0,					/* 空闲 */
	ARM_STATE_MOVING  = 1,					/* 运动中 */
	ARM_STATE_BUSY    = 2,					/* 忙碌(队列处理中) */
	ARM_STATE_ERROR   = 3,					/* 错误状态 */
	ARM_STATE_HOMING  = 4					/* 回零中 */
} arm_state_t;

/* 关节任务结构体 --------------------------------------------------------------*/

/**
  * @brief  关节移动任务结构体
  */
typedef struct
{
	uint8_t  joint_id;						/* 关节ID (0~5) */
	uint16_t target_pwm;					/* 目标PWM值 */
	uint16_t move_time;						/* 运动时间(ms) */
} arm_joint_task_t;

/* 移动任务结构体 --------------------------------------------------------------*/

/**
  * @brief  全身移动任务结构体
  */
typedef struct
{
	uint16_t positions[ARM_JOINT_NUM];		/* 6个关节目标位置 */
	uint16_t move_time;						/* 运动时间(ms) */
	uint8_t  is_all_joints;				/* 是否多关节联动 */
} arm_move_task_t;

/* 全局变量声明 ----------------------------------------------------------------*/
extern arm_state_t arm_current_state;		/* 当前机械臂状态 */

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  机械臂控制模块初始化
  * @param  无
  * @返回值 无
  * @说明   初始化状态、任务队列和原点位置
  */
void app_arm_init(void);

/**
  * @brief  机械臂控制运行函数
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，处理任务队列和加减速
  */
void app_arm_run(void);

/**
  * @brief  移动单个关节
  * @param  joint_id: 关节ID (0~5)
  * @param  pwm: 目标PWM值
  * @param  time: 运动时间(ms)
  * @返回值 无
  * @说明   将单个关节移动任务加入队列
  */
void app_arm_move_joint(uint8_t joint_id, uint16_t pwm, uint16_t time);

/**
  * @brief  移动所有关节
  * @param  positions: 6个关节的目标PWM值数组
  * @param  time: 运动时间(ms)
  * @返回值 无
  * @说明   将全身移动任务加入队列，所有关节同时运动
  */
void app_arm_move_all(uint16_t positions[6], uint16_t time);

/**
  * @brief  停止所有运动
  * @param  无
  * @返回值 无
  * @说明   清空任务队列，停止所有舵机
  */
void app_arm_stop(void);

/**
  * @brief  回到原点位置
  * @param  无
  * @返回值 无
  * @说明   所有关节回到中心位置(PWM=1500)
  */
void app_arm_origin(void);

/**
  * @brief  获取机械臂状态
  * @param  无
  * @返回值 当前机械臂状态枚举值
  */
uint8_t app_arm_get_status(void);

/**
  * @brief  获取当前关节位置
  * @param  joint_id: 关节ID (0~5)
  * @返回值 当前位置PWM值
  */
uint16_t app_arm_get_position(uint8_t joint_id);

/**
  * @brief  获取所有关节当前位置
  * @param  positions: 输出数组，存储6个关节当前位置
  * @返回值 无
  */
void app_arm_get_all_positions(uint16_t positions[6]);

#endif /* __APP_ARM_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/