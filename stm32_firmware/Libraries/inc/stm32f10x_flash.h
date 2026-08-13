#ifndef __STM32F10X_FLASH_H
#define __STM32F10X_FLASH_H

#include "stm32f10x.h"

#define FLASH_Latency_0    ((uint32_t)0x00000000)
#define FLASH_Latency_1    ((uint32_t)0x00000001)
#define FLASH_Latency_2    ((uint32_t)0x00000002)

#define FLASH_FLAG_BSY      ((uint32_t)0x00000001)
#define FLASH_FLAG_EOP      ((uint32_t)0x00000020)
#define FLASH_FLAG_PGERR    ((uint32_t)0x00000004)
#define FLASH_FLAG_WRPRTERR ((uint32_t)0x00000010)

#define FLASH_PrefetchBuffer_Enable  ((uint32_t)0x00000010)
#define FLASH_PrefetchBuffer_Disable ((uint32_t)0x00000000)

typedef enum {
  FLASH_BUSY = 1,
  FLASH_ERROR_PG,
  FLASH_ERROR_WRP,
  FLASH_COMPLETE,
  FLASH_TIMEOUT
} FLASH_Status;

void FLASH_SetLatency(uint32_t FLASH_Latency);
void FLASH_PrefetchBufferCmd(uint32_t FLASH_Prefetch);
void FLASH_Unlock(void);
void FLASH_Lock(void);
uint8_t FLASH_ErasePage(uint32_t Page_Address);
uint8_t FLASH_ProgramWord(uint32_t Address, uint32_t Data);
void FLASH_ClearFlag(uint32_t FLASH_FLAG);

#endif