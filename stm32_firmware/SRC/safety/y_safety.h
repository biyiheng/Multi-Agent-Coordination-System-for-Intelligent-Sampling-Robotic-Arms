/**
  ******************************************************************************
  * @file    SRC/safety/y_safety.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   安全监控模块头文件
  *          负责机械臂运行安全监控，包括：
  *          - 舵机位置软限位检查
  *          - 紧急停止功能
  *          - 看门狗定时器集成
  *          - LED状态指示
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __Y_SAFETY_H
#define __Y_SAFETY_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"
#include "stm32f10x_iwdg.h"

/* 宏定义 ----------------------------------------------------------------------*/
#define SAFETY_SERVO_NUM		6			/* 受监控舵机数量 */

/* 安全状态枚举 ----------------------------------------------------------------*/

/**
  * @brief  安全状态枚举
  */
typedef enum
{
	SAFETY_OK      = 0,						/* 正常状态 */
	SAFETY_WARNING = 1,						/* 警告状态 */
	SAFETY_ERROR   = 2,						/* 错误状态 */
	SAFETY_ESTOP   = 3						/* 紧急停止状态 */
} safety_status_t;

/* 全局变量声明 ----------------------------------------------------------------*/
extern safety_status_t safety_current_status;	/* 当前安全状态 */
extern uint16_t safety_min_pwm[SAFETY_SERVO_NUM];	/* 各舵机最小PWM软限位 */
extern uint16_t safety_max_pwm[SAFETY_SERVO_NUM];	/* 各舵机最大PWM软限位 */

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  安全模块初始化
  * @param  无
  * @返回值 无
  * @说明   初始化软限位为默认值(500~2500)，配置看门狗和LED
  */
void safety_init(void);

/**
  * @brief  安全状态检查
  * @param  无
  * @返回值 无
  * @说明   检查所有舵机位置是否在软限位范围内，更新安全状态
  */
void safety_check(void);

/**
  * @brief  紧急停止
  * @param  无
  * @返回值 无
  * @说明   触发紧急停止，停止所有舵机，设置硬件标志
  */
void safety_emergency_stop(void);

/**
  * @brief  安全状态复位
  * @param  无
  * @返回值 无
  * @说明   从错误/急停状态恢复到正常状态
  */
void safety_reset(void);

/**
  * @brief  获取当前安全状态
  * @param  无
  * @返回值 当前安全状态枚举值
  */
safety_status_t safety_get_status(void);

/**
  * @brief  设置舵机软限位
  * @param  id: 舵机ID (0~5)
  * @param  min: 最小PWM值
  * @param  max: 最大PWM值
  * @返回值 无
  */
void safety_set_soft_limits(uint8_t id, uint16_t min, uint16_t max);

/**
  * @brief  安全监控运行函数
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，执行定期安全检查
  */
void safety_monitor(void);

/**
  * @brief  更新LED状态指示
  * @param  无
  * @返回值 无
  * @说明   根据安全状态控制LED闪烁模式
  *         SAFETY_OK: 1Hz慢闪
  *         SAFETY_WARNING: 5Hz快闪
  *         SAFETY_ERROR: 常亮
  *         SAFETY_ESTOP: 快速双闪
  */
void safety_update_led(void);

#endif /* __Y_SAFETY_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/