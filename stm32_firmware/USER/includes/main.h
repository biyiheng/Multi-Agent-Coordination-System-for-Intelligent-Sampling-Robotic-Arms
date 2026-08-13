/**
  ******************************************************************************
  * @file    USER/includes/main.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   主程序头文件 - 智能采样机械臂系统
  *          包含所有标准库和驱动模块头文件
  *          提供全局定义和位带操作宏
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

/* 包含头文件 ------------------------------------------------------------------*/

/* 标准库头文件 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

/* STM32固件库头文件 */
#include "stm32f10x.h"

/* 系统配置头文件 */
#include "stm32f10x_conf.h"

/* 驱动层头文件 */
#include "y_bus_servo.h"		/* 总线舵机驱动 */
#include "y_sensor.h"			/* 传感器驱动 */
#include "y_safety.h"			/* 安全监控模块 */
#include "y_flash.h"			/* Flash存储模块 */
#include "y_action_group.h"		/* 动作组管理模块 */
#include "y_encoder.h"			/* AS5048 绝对值编码器驱动 (工业级升级 S1) */
#include "y_can.h"				/* CAN 通信层 (工业级升级 S2) */

/* 应用层头文件 */
#include "app_config.h"			/* 系统配置管理 */
#include "app_protocol.h"		/* 协议解析器 */
#include "app_arm.h"			/* 机械臂控制 */

/* 系统定义 --------------------------------------------------------------------*/

/* 系统版本信息 */
#define FW_VERSION_MAJOR		1
#define FW_VERSION_MINOR		0
#define FW_VERSION_PATCH		0
#define FW_VERSION_STR			"V1.0.0"

/* 系统时钟频率 */
#define SYSTEM_CLOCK_HZ			72000000	/* 72MHz */
#define SYSTICK_FREQ_HZ			1000		/* 1kHz SysTick */

/* 系统状态枚举 */

/**
  * @brief  系统运行状态枚举
  */
typedef enum
{
	SYS_STATE_INIT     = 0,				/* 初始化中 */
	SYS_STATE_IDLE     = 1,				/* 空闲 */
	SYS_STATE_RUNNING  = 2,				/* 运行中 */
	SYS_STATE_ERROR    = 3,				/* 错误 */
	SYS_STATE_ESTOP    = 4				/* 紧急停止 */
} sys_state_t;

/* 位带操作宏定义 --------------------------------------------------------------*/

/**
  * @brief  GPIO位带操作宏
  *          用于高效的单Bit GPIO操作
  *          SRAM位带区: 0x22000000
  *          外设位带区: 0x42000000
  */

/* 位带计算公式 (defined in stm32f10x.h if not already) */
#ifndef BITBAND
#define BITBAND(addr, bitnum)  ((addr & 0xF0000000) + 0x02000000 + \
                                ((addr & 0x000FFFFF) << 5) + (bitnum << 2))
#endif

/* 位带内存地址转换 */
#define MEM_ADDR(addr)         *((volatile unsigned long *)(addr))

/* 位带操作 */
#define BIT_BAND(addr, bitnum) MEM_ADDR(BITBAND(addr, bitnum))

/* GPIO输出寄存器位带操作 */
#define GPIOA_ODR_Addr    (GPIOA_BASE + 0x0C)
#define GPIOB_ODR_Addr    (GPIOB_BASE + 0x0C)
#define GPIOC_ODR_Addr    (GPIOC_BASE + 0x0C)

#define PAout(n)   BIT_BAND(GPIOA_ODR_Addr, n)
#define PBout(n)   BIT_BAND(GPIOB_ODR_Addr, n)
#define PCout(n)   BIT_BAND(GPIOC_ODR_Addr, n)

/* GPIO输入寄存器位带操作 */
#define GPIOA_IDR_Addr    (GPIOA_BASE + 0x08)
#define GPIOB_IDR_Addr    (GPIOB_BASE + 0x08)
#define GPIOC_IDR_Addr    (GPIOC_BASE + 0x08)

#define PAin(n)    BIT_BAND(GPIOA_IDR_Addr, n)
#define PBin(n)    BIT_BAND(GPIOB_IDR_Addr, n)
#define PCin(n)    BIT_BAND(GPIOC_IDR_Addr, n)

/* 硬件引脚定义 ----------------------------------------------------------------*/

/* LED引脚 */
#define LED_PORT			GPIOB
#define LED_PIN				GPIO_Pin_13
#define LED_CLOCK			RCC_APB2Periph_GPIOB

/* 按键引脚 */
#define KEY1_PORT			GPIOA
#define KEY1_PIN			GPIO_Pin_8
#define KEY2_PORT			GPIOA
#define KEY2_PIN			GPIO_Pin_11
#define KEY_CLOCK			RCC_APB2Periph_GPIOA

/* 蜂鸣器引脚 */
#define BEEP_PORT			GPIOB
#define BEEP_PIN			GPIO_Pin_12
#define BEEP_CLOCK			RCC_APB2Periph_GPIOB

/* UART引脚 */
#define UART1_TX_PORT		GPIOA
#define UART1_TX_PIN		GPIO_Pin_9
#define UART1_RX_PORT		GPIOA
#define UART1_RX_PIN		GPIO_Pin_10
#define UART1_CLOCK			RCC_APB2Periph_GPIOA

#define UART2_TX_PORT		GPIOA
#define UART2_TX_PIN		GPIO_Pin_2
#define UART2_RX_PORT		GPIOA
#define UART2_RX_PIN		GPIO_Pin_3
#define UART2_CLOCK			RCC_APB2Periph_GPIOA

#define UART3_TX_PORT		GPIOB
#define UART3_TX_PIN		GPIO_Pin_10
#define UART3_RX_PORT		GPIOB
#define UART3_RX_PIN		GPIO_Pin_11
#define UART3_CLOCK			RCC_APB2Periph_GPIOB

/* 全局变量声明 ----------------------------------------------------------------*/
extern volatile uint32_t g_systick;			/* 系统滴答计数器 */
extern sys_state_t g_sys_state;				/* 系统运行状态 */

/* 函数声明 --------------------------------------------------------------------*/

/* 系统初始化函数 */
void rcc_config(void);						/* 系统时钟配置 */
void gpio_init(void);						/* GPIO初始化 */
void nvic_config(void);						/* NVIC中断配置 */
void led_init(void);						/* LED初始化 */
void led_set(uint8_t state);				/* LED控制 */
void led_toggle(void);						/* LED翻转 */
void beep_init(void);						/* 蜂鸣器初始化 */
void beep_set(uint8_t state);				/* 蜂鸣器控制 */
void key_init(void);						/* 按键初始化 */
void key_run(void);							/* 按键扫描 */
void uart_init(void);						/* 串口初始化 */
void uart_run(void);						/* 串口数据处理 */
void delay_init(void);						/* 延时初始化 */
void delay_ms(uint32_t ms);					/* 毫秒延时 */
void delay_us(uint32_t us);					/* 微秒延时 */
uint32_t get_systick(void);					/* 获取系统滴答 */

/* UART通信函数 */
void uart1_send_str(char *str);				/* UART1发送字符串 */
void uart2_send_str(char *str);				/* UART2发送字符串 */
void uart3_send_str(char *str);				/* UART3发送字符串 */
void uart1_receive_run(void);				/* UART1接收处理 */
uint8_t uart1_get_rx_data(char *buf, uint16_t *len);	/* 获取UART1接收数据 */

/* 工业级升级模块 (S1 编码器 / S2 CAN) */
void io_upgrade_run(void);		/* 编码器采样与 CAN 收发周期运行 */

#endif /* __MAIN_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/