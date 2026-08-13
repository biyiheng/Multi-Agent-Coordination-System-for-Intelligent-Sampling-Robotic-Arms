/**
  ******************************************************************************
  * @file    USER/includes/stm32f10x_it.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   中断服务程序头文件
  *          智能采样机械臂系统 - 中断处理函数声明
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __STM32F10x_IT_H
#define __STM32F10x_IT_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"

/* Cortex-M3 异常处理函数声明 --------------------------------------------------*/
void NMI_Handler(void);
void HardFault_Handler(void);
void MemManage_Handler(void);
void BusFault_Handler(void);
void UsageFault_Handler(void);
void SVC_Handler(void);
void DebugMon_Handler(void);
void PendSV_Handler(void);
void SysTick_Handler(void);

/* STM32F10x 外设中断处理函数声明 -----------------------------------------------*/
void USART1_IRQHandler(void);
void USART2_IRQHandler(void);
void USART3_IRQHandler(void);
void TIM2_IRQHandler(void);

/* UART接收数据获取函数声明 ----------------------------------------------------*/
uint8_t uart1_get_rx_data(char *buf, uint16_t *len);
uint8_t uart2_get_rx_data(char *buf, uint16_t *len);
uint8_t uart3_get_rx_data(char *buf, uint16_t *len);
uint32_t get_systick(void);

#endif /* __STM32F10x_IT_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/