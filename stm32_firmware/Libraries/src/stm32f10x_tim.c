#include "stm32f10x_tim.h"

uint8_t TIM_GetITStatus(TIM_TypeDef* TIMx, uint16_t TIM_IT) {
  uint8_t bitstatus = 0x00;
  if ((TIMx->DIER & TIM_IT) != (uint16_t)0x00) {
    if ((TIMx->SR & TIM_IT) != (uint16_t)0x00) {
      bitstatus = 0x01;
    }
  }
  return bitstatus;
}

void TIM_ClearITPendingBit(TIM_TypeDef* TIMx, uint16_t TIM_IT) {
  TIMx->SR = (uint16_t)~TIM_IT;
}