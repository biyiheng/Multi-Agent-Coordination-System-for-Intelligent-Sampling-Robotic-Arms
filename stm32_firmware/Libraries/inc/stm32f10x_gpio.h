#ifndef __STM32F10X_GPIO_H
#define __STM32F10X_GPIO_H

#include "stm32f10x.h"

typedef enum {
  GPIO_Speed_10MHz = 1,
  GPIO_Speed_2MHz  = 2,
  GPIO_Speed_50MHz = 3
} GPIOSpeed_TypeDef;

typedef enum {
  GPIO_Mode_AIN          = 0x0,
  GPIO_Mode_IN_FLOATING  = 0x04,
  GPIO_Mode_IPD          = 0x28,
  GPIO_Mode_IPU          = 0x48,
  GPIO_Mode_Out_OD       = 0x14,
  GPIO_Mode_Out_PP       = 0x10,
  GPIO_Mode_AF_OD        = 0x1C,
  GPIO_Mode_AF_PP        = 0x18
} GPIOMode_TypeDef;

typedef struct {
  uint16_t GPIO_Pin;
  GPIOSpeed_TypeDef GPIO_Speed;
  GPIOMode_TypeDef GPIO_Mode;
} GPIO_InitTypeDef;

#define GPIO_Pin_0    ((uint16_t)0x0001)
#define GPIO_Pin_1    ((uint16_t)0x0002)
#define GPIO_Pin_2    ((uint16_t)0x0004)
#define GPIO_Pin_3    ((uint16_t)0x0008)
#define GPIO_Pin_4    ((uint16_t)0x0010)
#define GPIO_Pin_5    ((uint16_t)0x0020)
#define GPIO_Pin_6    ((uint16_t)0x0040)
#define GPIO_Pin_7    ((uint16_t)0x0080)
#define GPIO_Pin_8    ((uint16_t)0x0100)
#define GPIO_Pin_9    ((uint16_t)0x0200)
#define GPIO_Pin_10   ((uint16_t)0x0400)
#define GPIO_Pin_11   ((uint16_t)0x0800)
#define GPIO_Pin_12   ((uint16_t)0x1000)
#define GPIO_Pin_13   ((uint16_t)0x2000)
#define GPIO_Pin_14   ((uint16_t)0x4000)
#define GPIO_Pin_15   ((uint16_t)0x8000)
#define GPIO_Pin_All  ((uint16_t)0xFFFF)

typedef enum {Bit_RESET = 0, Bit_SET} BitAction;

void GPIO_Init(GPIO_TypeDef* GPIOx, GPIO_InitTypeDef* GPIO_InitStruct);
void GPIO_SetBits(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);
void GPIO_ResetBits(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);
void GPIO_WriteBit(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin, uint8_t BitVal);
uint8_t GPIO_ReadInputDataBit(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);
uint8_t GPIO_ReadOutputDataBit(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin);

#endif