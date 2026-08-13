/**
  ******************************************************************************
  * @file    SRC/safety/y_safety.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   安全监控模块实现
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

/* 包含头文件 ------------------------------------------------------------------*/
#include "y_safety.h"
#include "y_bus_servo.h"

/* 外部函数声明 ----------------------------------------------------------------*/
extern void led_set(uint8_t state);				/* LED控制函数 */
extern void led_toggle(void);					/* LED翻转函数 */
extern void beep_set(uint8_t state);			/* 蜂鸣器控制函数 */
extern uint32_t get_systick(void);				/* 获取系统滴答计数 */

/* 全局变量定义 ----------------------------------------------------------------*/

/**
  * @brief  当前安全状态
  */
safety_status_t safety_current_status = SAFETY_OK;

/**
  * @brief  各舵机软限位 - 最小PWM值
  */
uint16_t safety_min_pwm[SAFETY_SERVO_NUM] = {
	500, 500, 500, 500, 500, 500
};

/**
  * @brief  各舵机软限位 - 最大PWM值
  */
uint16_t safety_max_pwm[SAFETY_SERVO_NUM] = {
	2500, 2500, 2500, 2500, 2500, 2500
};

/* 私有变量 --------------------------------------------------------------------*/
static uint8_t  safety_estopped;				/* 紧急停止标志 */
static uint32_t safety_last_check_time;			/* 上次检查时间 */
static uint32_t safety_warning_start_time;		/* 警告开始时间 */
static uint8_t  safety_led_state;				/* LED当前状态 */
static uint32_t safety_led_last_toggle;			/* LED上次翻转时间 */

/* 私有函数声明 ----------------------------------------------------------------*/
static void safety_check_limits(void);
static void safety_trigger_estop(void);
static void safety_feed_watchdog(void);

/**
  * @brief  安全模块初始化
  * @param  无
  * @返回值 无
  * @说明   初始化软限位为默认值(500~2500)，配置看门狗和LED
  */
void safety_init(void)
{
	uint8_t i;

	/* 初始化软限位为默认值 */
	for (i = 0; i < SAFETY_SERVO_NUM; i++)
	{
		safety_min_pwm[i] = 500;
		safety_max_pwm[i] = 2500;
	}

	/* 清除紧急停止标志 */
	safety_estopped = 0;

	/* 设置初始安全状态 */
	safety_current_status = SAFETY_OK;

	/* 初始化LED状态 */
	safety_led_state = 0;
	safety_led_last_toggle = 0;

	/* 初始化时间戳 */
	safety_last_check_time = 0;
	safety_warning_start_time = 0;

	/* 关闭LED和蜂鸣器 */
	led_set(0);
	beep_set(0);
}

/**
  * @brief  安全状态检查
  * @param  无
  * @返回值 无
  * @说明   检查所有舵机位置是否在软限位范围内，更新安全状态
  */
void safety_check(void)
{
	uint32_t now = get_systick();

	/* 如果已经急停，不再检查 */
	if (safety_estopped)
	{
		return;
	}

	/* 执行限位检查 */
	safety_check_limits();

	/* 喂看门狗 */
	safety_feed_watchdog();

	/* 更新上次检查时间 */
	safety_last_check_time = now;
}

/**
  * @brief  检查舵机位置是否超限
  * @param  无
  * @返回值 无
  * @说明   遍历所有舵机，检查当前位置是否在软限位范围内
  */
static void safety_check_limits(void)
{
	uint8_t i;
	uint16_t pos;
	uint8_t warning = 0;
	uint8_t error = 0;

	for (i = 0; i < SAFETY_SERVO_NUM; i++)
	{
		pos = bus_servo_get_position(i);

		/* 检查是否超出软限位 */
		if (pos < safety_min_pwm[i] || pos > safety_max_pwm[i])
		{
			/* 超出限位20%以上视为严重错误 */
			if (pos < (safety_min_pwm[i] * 80 / 100) ||
			    pos > (safety_max_pwm[i] * 120 / 100))
			{
				error = 1;
			}
			else
			{
				warning = 1;
			}
		}
	}

	/* 更新安全状态 */
	if (error)
	{
		/* 严重超限，触发急停 */
		safety_trigger_estop();
	}
	else if (warning)
	{
		/* 轻微超限，发出警告 */
		if (safety_current_status != SAFETY_WARNING)
		{
			safety_current_status = SAFETY_WARNING;
			safety_warning_start_time = get_systick();
		}
	}
	else
	{
		/* 一切正常 */
		if (safety_current_status == SAFETY_WARNING)
		{
			safety_current_status = SAFETY_OK;
		}
	}
}

/**
  * @brief  触发紧急停止
  * @param  无
  * @返回值 无
  * @说明   停止所有舵机，设置急停标志，激活蜂鸣器
  */
static void safety_trigger_estop(void)
{
	/* 设置紧急停止标志 */
	safety_estopped = 1;

	/* 更新安全状态 */
	safety_current_status = SAFETY_ESTOP;

	/* 停止所有舵机 */
	bus_servo_emergency_stop();

	/* 激活蜂鸣器报警 */
	beep_set(1);
}

/**
  * @brief  紧急停止
  * @param  无
  * @返回值 无
  * @说明   外部调用的紧急停止函数
  */
void safety_emergency_stop(void)
{
	safety_trigger_estop();
}

/**
  * @brief  安全状态复位
  * @param  无
  * @返回值 无
  * @说明   从错误/急停状态恢复到正常状态
  */
void safety_reset(void)
{
	/* 清除紧急停止标志 */
	safety_estopped = 0;

	/* 恢复安全状态 */
	safety_current_status = SAFETY_OK;

	/* 关闭蜂鸣器 */
	beep_set(0);

	/* 关闭LED */
	led_set(0);
}

/**
  * @brief  获取当前安全状态
  * @param  无
  * @返回值 当前安全状态枚举值
  */
safety_status_t safety_get_status(void)
{
	return safety_current_status;
}

/**
  * @brief  设置舵机软限位
  * @param  id: 舵机ID (0~5)
  * @param  min: 最小PWM值
  * @param  max: 最大PWM值
  * @返回值 无
  */
void safety_set_soft_limits(uint8_t id, uint16_t min, uint16_t max)
{
	if (id >= SAFETY_SERVO_NUM)
	{
		return;
	}

	/* 确保限位值在有效范围内 */
	if (min < 500)  min = 500;
	if (max > 2500) max = 2500;
	if (min >= max) return;

	safety_min_pwm[id] = min;
	safety_max_pwm[id] = max;
}

/**
  * @brief  安全监控运行函数
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，执行定期安全检查
  */
void safety_monitor(void)
{
	uint32_t now = get_systick();

	/* 每100ms执行一次安全检查 */
	if ((now - safety_last_check_time) >= 100)
	{
		safety_check();
	}

	/* 更新LED指示 */
	safety_update_led();
}

/**
  * @brief  更新LED状态指示
  * @param  无
  * @返回值 无
  * @说明   根据安全状态控制LED闪烁模式：
  *         SAFETY_OK: 1Hz慢闪(500ms亮/500ms灭)
  *         SAFETY_WARNING: 5Hz快闪(100ms亮/100ms灭)
  *         SAFETY_ERROR: 常亮
  *         SAFETY_ESTOP: 快速双闪(100ms亮/100ms灭/100ms亮/700ms灭)
  */
void safety_update_led(void)
{
	uint32_t now = get_systick();
	uint32_t elapsed = now - safety_led_last_toggle;

	switch (safety_current_status)
	{
		case SAFETY_OK:
			/* 1Hz慢闪: 500ms周期 */
			if (elapsed >= 500)
			{
				safety_led_state = !safety_led_state;
				led_set(safety_led_state);
				safety_led_last_toggle = now;
			}
			break;

		case SAFETY_WARNING:
			/* 5Hz快闪: 100ms周期 */
			if (elapsed >= 100)
			{
				safety_led_state = !safety_led_state;
				led_set(safety_led_state);
				safety_led_last_toggle = now;
			}
			break;

		case SAFETY_ERROR:
			/* 常亮 */
			led_set(1);
			break;

		case SAFETY_ESTOP:
			/* 快速双闪: 100ms亮/100ms灭/100ms亮/700ms灭 */
			{
				uint32_t cycle = elapsed % 1000;

				if (cycle < 100)
				{
					led_set(1);
				}
				else if (cycle < 200)
				{
					led_set(0);
				}
				else if (cycle < 300)
				{
					led_set(1);
				}
				else
				{
					led_set(0);
				}
			}
			break;

		default:
			break;
	}
}

/**
  * @brief  喂看门狗
  * @param  无
  * @返回值 无
  * @说明   定期喂狗防止系统复位
  */
static void safety_feed_watchdog(void)
{
	/* 清除独立看门狗计数器 */
	IWDG_ReloadCounter();
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/