/**
  ******************************************************************************
  * @file    USER/includes/stm32f10x_conf.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   外设驱动配置文件
  *          智能采样机械臂系统 - 启用所需外设模块
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __STM32F10x_CONF_H
#define __STM32F10x_CONF_H

/* 包含头文件 ------------------------------------------------------------------*/

/* 启用GPIO模块 - 用于按键、LED、蜂鸣器、传感器接口 */
#include "stm32f10x_gpio.h"

/* 启用USART模块 - 用于UART1(树莓派)、UART2(OpenMV)、UART3(总线舵机) */
#include "stm32f10x_usart.h"

/* 启用TIM模块 - 用于定时器、PWM和舵机控制时序 */
#include "stm32f10x_tim.h"

/* 启用ADC模块 - 用于电压监测 */
#include "stm32f10x_adc.h"

/* 启用RCC模块 - 系统时钟配置 */
#include "stm32f10x_rcc.h"

/* 启用FLASH模块 - 用于参数存储 */
#include "stm32f10x_flash.h"

/* 启用NVIC模块 - 中断优先级管理 */
#include "misc.h"

/* 启用EXTI模块 - 外部中断(按键) */
#include "stm32f10x_exti.h"

/* 启用IWDG模块 - 独立看门狗 */
#include "stm32f10x_iwdg.h"

/* 启用DMA模块 - 用于UART DMA传输 */
#include "stm32f10x_dma.h"

/* 启用PWR模块 - 电源管理 */
#include "stm32f10x_pwr.h"

/* 以下外设未使用，注释掉 */
/*
#include "stm32f10x_bkp.h"
#include "stm32f10x_can.h"
#include "stm32f10x_cec.h"
#include "stm32f10x_crc.h"
#include "stm32f10x_dac.h"
#include "stm32f10x_dbgmcu.h"
#include "stm32f10x_fsmc.h"
#include "stm32f10x_i2c.h"
#include "stm32f10x_rtc.h"
#include "stm32f10x_sdio.h"
#include "stm32f10x_spi.h"
#include "stm32f10x_wwdg.h"
*/

/* 断言配置 --------------------------------------------------------------------*/

/* 取消注释以启用参数断言检查 */
/* #define USE_FULL_ASSERT    1 */

#ifdef USE_FULL_ASSERT

/**
  * @brief  assert_param宏用于函数参数检查
  * @param  expr: 如果为假，调用assert_failed函数
  * @返回值 无
  */
#define assert_param(expr) ((expr) ? (void)0 : assert_failed((uint8_t *)__FILE__, __LINE__))

/* 断言失败处理函数 */
void assert_failed(uint8_t* file, uint32_t line);

#else
#define assert_param(expr) ((void)0)
#endif /* USE_FULL_ASSERT */

#endif /* __STM32F10x_CONF_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/