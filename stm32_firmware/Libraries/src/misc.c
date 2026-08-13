#include "misc.h"

void NVIC_PriorityGroupConfig(uint32_t NVIC_PriorityGroup) {
  assert_param(IS_NVIC_PRIORITY_GROUP(NVIC_PriorityGroup));
  SCB->AIRCR = (uint32_t)((uint32_t)0x05FA0000 | NVIC_PriorityGroup);
}

void NVIC_Init(NVIC_InitTypeDef* NVIC_InitStruct) {
  uint32_t tmppriority = 0x00, tmppre = 0x00, tmpsub = 0x0F;
  uint32_t prioritygroup = 0x00;

  assert_param(IS_NVIC_IRQ_CHANNEL(NVIC_InitStruct->NVIC_IRQChannel));
  assert_param(IS_NVIC_PREEMPTION_PRIORITY(NVIC_InitStruct->NVIC_IRQChannelPreemptionPriority));
  assert_param(IS_NVIC_SUB_PRIORITY(NVIC_InitStruct->NVIC_IRQChannelSubPriority));

  if (NVIC_InitStruct->NVIC_IRQChannelCmd != 0) {
    prioritygroup = ((SCB->AIRCR & SCB_AIRCR_PRIGROUP_Msk) >> SCB_AIRCR_PRIGROUP_Pos);
    tmppriority = (uint32_t)NVIC_InitStruct->NVIC_IRQChannelPreemptionPriority << (0x04 - prioritygroup);
    tmppriority |= (uint32_t)NVIC_InitStruct->NVIC_IRQChannelSubPriority & (uint32_t)0x0F >> (0x04 - prioritygroup);
    tmppriority = tmppriority << 0x04;

    if (NVIC_InitStruct->NVIC_IRQChannel >= 0) {
      NVIC->IP[NVIC_InitStruct->NVIC_IRQChannel] = tmppriority;
      NVIC->ISER[NVIC_InitStruct->NVIC_IRQChannel >> 0x05] = (uint32_t)0x01 << (NVIC_InitStruct->NVIC_IRQChannel & (uint8_t)0x1F);
    } else {
      SCB->SHPR[((uint32_t)NVIC_InitStruct->NVIC_IRQChannel & 0x0F) - 4] = tmppriority;
    }
  } else {
    NVIC->ICER[NVIC_InitStruct->NVIC_IRQChannel >> 0x05] = (uint32_t)0x01 << (NVIC_InitStruct->NVIC_IRQChannel & (uint8_t)0x1F);
  }
}