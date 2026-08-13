#include "stm32f10x_rcc.h"

static __I uint8_t APBAHBPrescTable[16] = {0, 0, 0, 0, 1, 2, 3, 4, 1, 2, 3, 4, 6, 7, 8, 9};

void RCC_DeInit(void) {
  RCC->CR |= (uint32_t)0x00000001;
  RCC->CFGR &= (uint32_t)0xF8FF0000;
  RCC->CR &= (uint32_t)0xFEF6FFFF;
  RCC->CIR = 0x009F0000;
}

void RCC_HSEConfig(uint32_t RCC_HSE) {
  uint32_t tmpreg = 0;
  tmpreg = RCC->CR;
  tmpreg &= ~(RCC_CR_HSEON | RCC_CR_HSEBYP);
  tmpreg |= RCC_HSE;
  RCC->CR = tmpreg;
}

uint8_t RCC_WaitForHSEStartUp(void) {
  uint8_t HSEStatus = 0;
  uint32_t StartUpCounter = 0;
  HSEStatus = 0;

  RCC->CR |= RCC_CR_HSEON;
  do {
    HSEStatus = RCC->CR & RCC_CR_HSERDY;
    StartUpCounter++;
  } while ((HSEStatus == 0) && (StartUpCounter != 0x0500));

  if ((RCC->CR & RCC_CR_HSERDY) != 0) {
    HSEStatus = 0x01;
  }
  return HSEStatus;
}

void RCC_PLLConfig(uint32_t RCC_PLLSource, uint32_t RCC_PLLMul) {
  uint32_t tmpreg = 0;
  tmpreg = RCC->CFGR;
  tmpreg &= ~(RCC_CFGR_PLLSRC | RCC_CFGR_PLLXTPRE | RCC_CFGR_PLLMULL);
  tmpreg |= RCC_PLLSource | RCC_PLLMul;
  RCC->CFGR = tmpreg;
}

void RCC_PLLCmd(uint8_t NewState) {
  if (NewState != 0) {
    RCC->CR |= RCC_CR_PLLON;
  } else {
    RCC->CR &= ~RCC_CR_PLLON;
  }
}

void RCC_SYSCLKConfig(uint32_t RCC_SYSCLKSource) {
  uint32_t tmpreg = 0;
  tmpreg = RCC->CFGR;
  tmpreg &= ~RCC_CFGR_SW;
  tmpreg |= RCC_SYSCLKSource;
  RCC->CFGR = tmpreg;
}

uint8_t RCC_GetSYSCLKSource(void) {
  return ((uint8_t)(RCC->CFGR & RCC_CFGR_SWS));
}

void RCC_HCLKConfig(uint32_t RCC_SYSCLK) {
  uint32_t tmpreg = 0;
  tmpreg = RCC->CFGR;
  tmpreg &= ~RCC_CFGR_HPRE;
  tmpreg |= RCC_SYSCLK;
  RCC->CFGR = tmpreg;
}

void RCC_PCLK1Config(uint32_t RCC_HCLK) {
  uint32_t tmpreg = 0;
  tmpreg = RCC->CFGR;
  tmpreg &= ~RCC_CFGR_PPRE1;
  tmpreg |= RCC_HCLK;
  RCC->CFGR = tmpreg;
}

void RCC_PCLK2Config(uint32_t RCC_HCLK) {
  uint32_t tmpreg = 0;
  tmpreg = RCC->CFGR;
  tmpreg &= ~RCC_CFGR_PPRE2;
  tmpreg |= RCC_HCLK;
  RCC->CFGR = tmpreg;
}

void RCC_ADCCLKConfig(uint32_t RCC_PCLK2) {
  uint32_t tmpreg = 0;
  tmpreg = RCC->CFGR;
  tmpreg &= ~RCC_CFGR_ADCPRE;
  tmpreg |= RCC_PCLK2;
  RCC->CFGR = tmpreg;
}

void RCC_APB2PeriphClockCmd(uint32_t RCC_APB2Periph, uint8_t NewState) {
  if (NewState != 0) {
    RCC->APB2ENR |= RCC_APB2Periph;
  } else {
    RCC->APB2ENR &= ~RCC_APB2Periph;
  }
}

void RCC_APB1PeriphClockCmd(uint32_t RCC_APB1Periph, uint8_t NewState) {
  if (NewState != 0) {
    RCC->APB1ENR |= RCC_APB1Periph;
  } else {
    RCC->APB1ENR &= ~RCC_APB1Periph;
  }
}

uint8_t RCC_GetFlagStatus(uint8_t RCC_FLAG) {
  uint8_t bitstatus = 0;
  uint32_t tmpreg = 0;
  uint8_t statusreg = RCC_FLAG >> 5;

  if (statusreg == 0x01) {
    tmpreg = RCC->CR;
  } else if (statusreg == 0x02) {
    tmpreg = RCC->BDCR;
  } else {
    tmpreg = RCC->CSR;
  }

  if ((tmpreg & ((uint32_t)1 << (RCC_FLAG & 0x1F))) != (uint32_t)0) {
    bitstatus = 0x01;
  }
  return bitstatus;
}