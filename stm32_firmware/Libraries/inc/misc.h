#ifndef __MISC_H
#define __MISC_H

#include "stm32f10x.h"

typedef struct {
  uint8_t NVIC_IRQChannel;
  uint8_t NVIC_IRQChannelPreemptionPriority;
  uint8_t NVIC_IRQChannelSubPriority;
  uint8_t NVIC_IRQChannelCmd;
} NVIC_InitTypeDef;

#define NVIC_PriorityGroup_0    ((uint32_t)0x700)
#define NVIC_PriorityGroup_1    ((uint32_t)0x600)
#define NVIC_PriorityGroup_2    ((uint32_t)0x500)
#define NVIC_PriorityGroup_3    ((uint32_t)0x400)
#define NVIC_PriorityGroup_4    ((uint32_t)0x300)

void NVIC_PriorityGroupConfig(uint32_t NVIC_PriorityGroup);
void NVIC_Init(NVIC_InitTypeDef* NVIC_InitStruct);

#endif