#ifndef __STM32F10X_TIM_H
#define __STM32F10X_TIM_H

#include "stm32f10x.h"

#define TIM_IT_Update  ((uint16_t)0x0001)

uint8_t TIM_GetITStatus(TIM_TypeDef* TIMx, uint16_t TIM_IT);
void TIM_ClearITPendingBit(TIM_TypeDef* TIMx, uint16_t TIM_IT);

#endif