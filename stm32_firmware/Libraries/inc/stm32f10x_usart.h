#ifndef __STM32F10X_USART_H
#define __STM32F10X_USART_H

#include "stm32f10x.h"

typedef struct {
  uint32_t USART_BaudRate;
  uint16_t USART_WordLength;
  uint16_t USART_StopBits;
  uint16_t USART_Parity;
  uint16_t USART_Mode;
  uint16_t USART_HardwareFlowControl;
} USART_InitTypeDef;

#define USART_WordLength_8b   ((uint16_t)0x0000)
#define USART_WordLength_9b   ((uint16_t)0x1000)
#define USART_StopBits_1      ((uint16_t)0x0000)
#define USART_StopBits_0_5    ((uint16_t)0x1000)
#define USART_StopBits_2      ((uint16_t)0x2000)
#define USART_StopBits_1_5    ((uint16_t)0x3000)
#define USART_Parity_No       ((uint16_t)0x0000)
#define USART_Parity_Even     ((uint16_t)0x0400)
#define USART_Parity_Odd      ((uint16_t)0x0600)
#define USART_Mode_Rx         ((uint16_t)0x0004)
#define USART_Mode_Tx         ((uint16_t)0x0008)
#define USART_HardwareFlowControl_None ((uint16_t)0x0000)
#define USART_HardwareFlowControl_RTS  ((uint16_t)0x0100)
#define USART_HardwareFlowControl_CTS  ((uint16_t)0x0200)

#define USART_FLAG_TXE   ((uint16_t)0x0080)
#define USART_FLAG_TC    ((uint16_t)0x0040)
#define USART_FLAG_RXNE  ((uint16_t)0x0020)

#define USART_IT_RXNE   ((uint16_t)0x0525)
#define USART_IT_ORE    ((uint16_t)0x0325)
#define USART_IT_TXE    ((uint16_t)0x0727)

void USART_Init(USART_TypeDef* USARTx, USART_InitTypeDef* USART_InitStruct);
void USART_Cmd(USART_TypeDef* USARTx, uint8_t NewState);
void USART_ITConfig(USART_TypeDef* USARTx, uint16_t USART_IT, uint8_t NewState);
void USART_SendData(USART_TypeDef* USARTx, uint16_t Data);
uint16_t USART_ReceiveData(USART_TypeDef* USARTx);
uint8_t USART_GetFlagStatus(USART_TypeDef* USARTx, uint16_t USART_FLAG);
uint8_t USART_GetITStatus(USART_TypeDef* USARTx, uint16_t USART_IT);
void USART_ClearITPendingBit(USART_TypeDef* USARTx, uint16_t USART_IT);

#endif