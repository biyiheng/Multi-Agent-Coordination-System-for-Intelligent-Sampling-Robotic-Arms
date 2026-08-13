/**
  ******************************************************************************
  * @file    SRC/bus_servo/y_bus_servo.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   总线舵机驱动模块头文件
  *          支持ZX20D/ZX15D/ZX15S系列总线舵机控制
  *          通信协议: #XXXPYYYYTZZZZ!
  *          多舵机: {cmd1!cmd2!...}
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __Y_BUS_SERVO_H
#define __Y_BUS_SERVO_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"

/* 宏定义 ----------------------------------------------------------------------*/
#define BUS_SERVO_NUM			6			/* 舵机总数 */

/* 舵机ID定义 ------------------------------------------------------------------*/
#define SERVO_ID_BOTTOM			0			/* 底盘舵机 ZX20D */
#define SERVO_ID_SHOULDER		1			/* 肩关节舵机 ZX15D */
#define SERVO_ID_ELBOW1			2			/* 肘关节1舵机 ZX15D */
#define SERVO_ID_ELBOW2			3			/* 肘关节2舵机 ZX15D */
#define SERVO_ID_WRIST			4			/* 腕关节舵机 ZX15S */
#define SERVO_ID_GRIPPER		5			/* 夹爪舵机 ZX15S */

/* 舵机参数范围 ----------------------------------------------------------------*/
#define SERVO_PWM_MIN			500			/* 最小PWM值 */
#define SERVO_PWM_MAX			2500		/* 最大PWM值 */
#define SERVO_PWM_CENTER		1500		/* 中心位置PWM值 */

/* 舵机状态定义 ----------------------------------------------------------------*/
#define SERVO_STATUS_IDLE		0			/* 空闲状态 */
#define SERVO_STATUS_MOVING		1			/* 运动中 */
#define SERVO_STATUS_STOPPED	2			/* 已停止 */
#define SERVO_STATUS_ERROR		3			/* 错误状态 */

/* 数据类型定义 ----------------------------------------------------------------*/

/**
  * @brief  总线舵机数据结构体
  */
typedef struct
{
	uint8_t  id;							/* 舵机ID (0~5) */
	uint16_t position;						/* 当前位置 (500~2500) */
	uint16_t target;						/* 目标位置 (500~2500) */
	uint16_t time;							/* 运动时间(ms) */
	uint8_t  status;						/* 舵机状态 */
} bus_servo_t;

/* 全局变量声明 ----------------------------------------------------------------*/
extern bus_servo_t bus_servo_data[BUS_SERVO_NUM];	/* 舵机数据数组 */

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  总线舵机初始化
  * @param  无
  * @返回值 无
  */
void bus_servo_init(void);

/**
  * @brief  设置单个舵机位置
  * @param  id: 舵机ID (0~5)
  * @param  pwm: PWM值 (500~2500)
  * @param  time: 运动时间(ms)
  * @返回值 无
  */
void bus_servo_set_position(uint8_t id, uint16_t pwm, uint16_t time);

/**
  * @brief  同时设置所有舵机位置
  * @param  positions: 6个舵机的PWM值数组
  * @param  time: 运动时间(ms)
  * @返回值 无
  */
void bus_servo_set_all(uint16_t positions[6], uint16_t time);

/**
  * @brief  获取舵机当前位置
  * @param  id: 舵机ID (0~5)
  * @返回值 当前位置PWM值
  */
uint16_t bus_servo_get_position(uint8_t id);

/**
  * @brief  释放舵机(卸力)
  * @param  id: 舵机ID (0~5)
  * @返回值 无
  */
void bus_servo_release(uint8_t id);

/**
  * @brief  恢复舵机(恢复力矩)
  * @param  id: 舵机ID (0~5)
  * @返回值 无
  */
void bus_servo_restore(uint8_t id);

/**
  * @brief  设置舵机ID
  * @param  old_id: 当前舵机ID
  * @param  new_id: 新舵机ID
  * @返回值 无
  */
void bus_servo_set_id(uint8_t old_id, uint8_t new_id);

/**
  * @brief  读取舵机ID
  * @param  id: 舵机ID (0~5)
  * @返回值 舵机ID
  */
uint8_t bus_servo_read_id(uint8_t id);

/**
  * @brief  停止所有舵机运动
  * @param  无
  * @返回值 无
  */
void bus_servo_stop(void);

/**
  * @brief  紧急停止所有舵机
  * @param  无
  * @返回值 无
  */
void bus_servo_emergency_stop(void);

#endif /* __Y_BUS_SERVO_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/