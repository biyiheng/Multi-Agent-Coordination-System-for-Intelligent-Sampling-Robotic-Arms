#include "stm32f10x_flash.h"

void FLASH_SetLatency(uint32_t FLASH_Latency) {
  uint32_t tmpreg = 0;
  tmpreg = FLASH->ACR;
  tmpreg &= (uint32_t)((uint32_t)~((uint32_t)FLASH_ACR_LATENCY));
  tmpreg |= FLASH_Latency;
  FLASH->ACR = tmpreg;
}

void FLASH_PrefetchBufferCmd(uint32_t FLASH_Prefetch) {
  FLASH->ACR |= FLASH_Prefetch;
}

void FLASH_Unlock(void) {
  if ((FLASH->CR & FLASH_CR_LOCK) != 0) {
    FLASH->KEYR = 0x45670123;
    FLASH->KEYR = 0xCDEF89AB;
  }
}

void FLASH_Lock(void) {
  FLASH->CR |= FLASH_CR_LOCK;
}

uint8_t FLASH_ErasePage(uint32_t Page_Address) {
  uint8_t status = FLASH_COMPLETE;
  FLASH->CR |= FLASH_CR_PER;
  FLASH->AR = Page_Address;
  FLASH->CR |= FLASH_CR_STRT;
  while ((FLASH->SR & FLASH_SR_BSY) != 0) { }
  if ((FLASH->SR & FLASH_SR_PGERR) != 0) status = FLASH_ERROR_PG;
  if ((FLASH->SR & FLASH_SR_WRPRTERR) != 0) status = FLASH_ERROR_WRP;
  FLASH->CR &= ~FLASH_CR_PER;
  return status;
}

uint8_t FLASH_ProgramWord(uint32_t Address, uint32_t Data) {
  uint8_t status = FLASH_COMPLETE;
  FLASH->CR |= FLASH_CR_PG;
  *(__IO uint16_t*)Address = (uint16_t)Data;
  while ((FLASH->SR & FLASH_SR_BSY) != 0) { }
  Address += 2;
  *(__IO uint16_t*)Address = (uint16_t)(Data >> 16);
  while ((FLASH->SR & FLASH_SR_BSY) != 0) { }
  if ((FLASH->SR & FLASH_SR_PGERR) != 0) status = FLASH_ERROR_PG;
  if ((FLASH->SR & FLASH_SR_WRPRTERR) != 0) status = FLASH_ERROR_WRP;
  FLASH->CR &= ~FLASH_CR_PG;
  return status;
}

void FLASH_ClearFlag(uint32_t FLASH_FLAG) {
  FLASH->SR = FLASH_FLAG;
}