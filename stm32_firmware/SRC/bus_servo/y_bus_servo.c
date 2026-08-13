/**
  ******************************************************************************
  * @file    SRC/bus_servo/y_bus_servo.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   总线舵机驱动模块实现
  *          通过UART3发送指令控制总线舵机
  *          单舵机格式: #XXXPYYYYTZZZZ!
  *          多舵机格式: {#XXXPYYYYTZZZZ!#XXXPYYYYTZZZZ!...}
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include "y_bus_servo.h"
#include <stdio.h>
#include <string.h>

/* 外部函数声明 ----------------------------------------------------------------*/
extern void uart3_send_str(char *str);			/* UART3发送字符串 */
extern void uart3_send_data(uint8_t *data, uint16_t len);	/* UART3发送数据 */

/* 全局变量定义 ----------------------------------------------------------------*/

/**
  * @brief  舵机数据数组，存储所有舵机的状态信息
  */
bus_servo_t bus_servo_data[BUS_SERVO_NUM];

/* 私有变量 --------------------------------------------------------------------*/
static char servo_cmd_buf[64];					/* 舵机命令缓冲区 */

/* 私有函数声明 ----------------------------------------------------------------*/
static void bus_servo_send_single(uint8_t id, uint16_t pwm, uint16_t time);
static void bus_servo_send_multi(uint16_t positions[6], uint16_t time);

/**
  * @brief  总线舵机初始化
  * @param  无
  * @返回值 无
  * @说明   初始化所有舵机数据为默认中心位置，空闲状态
  */
void bus_servo_init(void)
{
	uint8_t i;

	/* 初始化舵机数据数组 */
	for (i = 0; i < BUS_SERVO_NUM; i++)
	{
		bus_servo_data[i].id       = i;
		bus_servo_data[i].position = SERVO_PWM_CENTER;
		bus_servo_data[i].target   = SERVO_PWM_CENTER;
		bus_servo_data[i].time     = 1000;
		bus_servo_data[i].status   = SERVO_STATUS_IDLE;
	}
}

/**
  * @brief  发送单个舵机控制命令
  * @param  id: 舵机ID (0~5)
  * @param  pwm: PWM值 (500~2500)
  * @param  time: 运动时间(ms)
  * @返回值 无
  * @说明   格式: #XXXPYYYYTZZZZ!
  */
static void bus_servo_send_single(uint8_t id, uint16_t pwm, uint16_t time)
{
	/* 格式化命令字符串 */
	sprintf(servo_cmd_buf, "#%03dP%04dT%04d!", id, pwm, time);

	/* 通过UART3发送到舵机总线 */
	uart3_send_str(servo_cmd_buf);
}

/**
  * @brief  发送多舵机控制命令
  * @param  positions: 6个舵机的PWM值数组
  * @param  time: 运动时间(ms)
  * @返回值 无
  * @说明   格式: {#000P1500T1000!#001P1500T1000!...}
  */
static void bus_servo_send_multi(uint16_t positions[6], uint16_t time)
{
	uint8_t i;

	/* 构建多舵机命令 */
	uart3_send_str("{");

	for (i = 0; i < BUS_SERVO_NUM; i++)
	{
		sprintf(servo_cmd_buf, "#%03dP%04dT%04d!", i, positions[i], time);
		uart3_send_str(servo_cmd_buf);
	}

	uart3_send_str("}");
}

/**
  * @brief  设置单个舵机位置
  * @param  id: 舵机ID (0~5)
  * @param  pwm: PWM值 (500~2500)
  * @param  time: 运动时间(ms)
  * @返回值 无
  * @说明   限制PWM值范围在500~2500之间，更新目标位置并发送命令
  */
void bus_servo_set_position(uint8_t id, uint16_t pwm, uint16_t time)
{
	/* 参数校验 */
	if (id >= BUS_SERVO_NUM)
	{
		return;
	}

	/* 限制PWM值范围 */
	if (pwm < SERVO_PWM_MIN)
	{
		pwm = SERVO_PWM_MIN;
	}
	if (pwm > SERVO_PWM_MAX)
	{
		pwm = SERVO_PWM_MAX;
	}

	/* 更新舵机数据 */
	bus_servo_data[id].target = pwm;
	bus_servo_data[id].time   = time;
	bus_servo_data[id].status = SERVO_STATUS_MOVING;

	/* 发送控制命令 */
	bus_servo_send_single(id, pwm, time);
}

/**
  * @brief  同时设置所有舵机位置
  * @param  positions: 6个舵机的PWM值数组
  * @param  time: 运动时间(ms)
  * @返回值 无
  * @说明   使用多舵机命令格式同时控制所有舵机
  */
void bus_servo_set_all(uint16_t positions[6], uint16_t time)
{
	uint8_t i;

	/* 更新所有舵机数据 */
	for (i = 0; i < BUS_SERVO_NUM; i++)
	{
		/* 限制PWM值范围 */
		if (positions[i] < SERVO_PWM_MIN)
		{
			positions[i] = SERVO_PWM_MIN;
		}
		if (positions[i] > SERVO_PWM_MAX)
		{
			positions[i] = SERVO_PWM_MAX;
		}

		bus_servo_data[i].target = positions[i];
		bus_servo_data[i].time   = time;
		bus_servo_data[i].status = SERVO_STATUS_MOVING;
	}

	/* 发送多舵机命令 */
	bus_servo_send_multi(positions, time);
}

/**
  * @brief  获取舵机当前位置
  * @param  id: 舵机ID (0~5)
  * @返回值 当前位置PWM值，如果ID无效返回0
  */
uint16_t bus_servo_get_position(uint8_t id)
{
	if (id >= BUS_SERVO_NUM)
	{
		return 0;
	}

	return bus_servo_data[id].position;
}

/**
  * @brief  释放舵机(卸力)
  * @param  id: 舵机ID (0~5)
  * @返回值 无
  * @说明   发送释放命令，舵机卸力可自由转动
  */
void bus_servo_release(uint8_t id)
{
	if (id >= BUS_SERVO_NUM)
	{
		return;
	}

	/* 发送释放命令 */
	sprintf(servo_cmd_buf, "#%03dPREL!", id);
	uart3_send_str(servo_cmd_buf);

	/* 更新舵机状态 */
	bus_servo_data[id].status = SERVO_STATUS_IDLE;
}

/**
  * @brief  恢复舵机(恢复力矩)
  * @param  id: 舵机ID (0~5)
  * @返回值 无
  * @说明   发送恢复命令，舵机恢复力矩回到原位置
  */
void bus_servo_restore(uint8_t id)
{
	if (id >= BUS_SERVO_NUM)
	{
		return;
	}

	/* 发送恢复命令 */
	sprintf(servo_cmd_buf, "#%03dPRES!", id);
	uart3_send_str(servo_cmd_buf);

	/* 更新舵机状态 */
	bus_servo_data[id].status = SERVO_STATUS_IDLE;
}

/**
  * @brief  设置舵机ID
  * @param  old_id: 当前舵机ID
  * @param  new_id: 新舵机ID
  * @返回值 无
  * @说明   修改舵机ID，注意此操作需谨慎，避免ID冲突
  */
void bus_servo_set_id(uint8_t old_id, uint8_t new_id)
{
	if (old_id >= BUS_SERVO_NUM || new_id >= BUS_SERVO_NUM)
	{
		return;
	}

	/* 发送设置ID命令 */
	sprintf(servo_cmd_buf, "#%03dSID%03d!", old_id, new_id);
	uart3_send_str(servo_cmd_buf);
}

/**
  * @brief  读取舵机ID
  * @param  id: 舵机ID (0~5)
  * @返回值 舵机ID
  * @说明   发送读取ID命令，通过UART3接收返回
  */
uint8_t bus_servo_read_id(uint8_t id)
{
	if (id >= BUS_SERVO_NUM)
	{
		return 0xFF;
	}

	/* 发送读取ID命令 */
	sprintf(servo_cmd_buf, "#%03dRID!", id);
	uart3_send_str(servo_cmd_buf);

	/* 返回当前记录的ID */
	return bus_servo_data[id].id;
}

/**
  * @brief  停止所有舵机运动
  * @param  无
  * @返回值 无
  * @说明   发送停止命令，所有舵机立即停止当前运动
  */
void bus_servo_stop(void)
{
	uint8_t i;

	/* 发送停止命令 */
	uart3_send_str("$STP!");

	/* 更新所有舵机状态 */
	for (i = 0; i < BUS_SERVO_NUM; i++)
	{
		bus_servo_data[i].status = SERVO_STATUS_STOPPED;
	}
}

/**
  * @brief  紧急停止所有舵机
  * @param  无
  * @返回值 无
  * @说明   先发送全局停止命令，再逐个发送停止以确保所有舵机都停止
  */
void bus_servo_emergency_stop(void)
{
	uint8_t i;

	/* 发送全局紧急停止命令 */
	uart3_send_str("$DST!");

	/* 逐个发送停止命令确保可靠性 */
	for (i = 0; i < BUS_SERVO_NUM; i++)
	{
		sprintf(servo_cmd_buf, "#%03dSTP!", i);
		uart3_send_str(servo_cmd_buf);
	}

	/* 更新所有舵机状态为停止 */
	for (i = 0; i < BUS_SERVO_NUM; i++)
	{
		bus_servo_data[i].status = SERVO_STATUS_STOPPED;
	}
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/