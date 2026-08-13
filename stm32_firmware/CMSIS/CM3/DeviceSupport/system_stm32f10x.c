#include "stm32f10x.h"
#include "system_stm32f10x.h"

uint32_t SystemCoreClock = 72000000;

void SystemInit(void) {
  uint32_t hse_timeout = 0;

  /* Reset RCC */
  RCC->CR |= (uint32_t)0x00000001;
  RCC->CFGR &= (uint32_t)0xF8FF0000;
  RCC->CR &= (uint32_t)0xFEF6FFFF;
  RCC->CIR = 0x009F0000;

#if defined (STM32F10X_HD) || defined (STM32F10X_XL)
  /* High-density: FLASH 2 wait states */
  FLASH->ACR |= FLASH_ACR_LATENCY_2;
#else
  /* Medium-density: FLASH 2 wait states */
  FLASH->ACR |= FLASH_ACR_LATENCY_2;
#endif

  /* HCLK = SYSCLK */
  RCC->CFGR |= (uint32_t)RCC_CFGR_HPRE_DIV1;
  /* PCLK2 = HCLK */
  RCC->CFGR |= (uint32_t)RCC_CFGR_PPRE2_DIV1;
  /* PCLK1 = HCLK/2 */
  RCC->CFGR |= (uint32_t)RCC_CFGR_PPRE1_DIV2;

  /* Try HSE first, fallback to HSI if no external crystal */
  RCC->CR |= ((uint32_t)RCC_CR_HSEON);

  /* Wait for HSE with timeout (~100ms) */
  hse_timeout = 0;
  while ((RCC->CR & RCC_CR_HSERDY) == 0) {
    hse_timeout++;
    if (hse_timeout > 0x100000) {
      /* HSE failed - fallback to HSI */
      RCC->CR &= ~((uint32_t)RCC_CR_HSEON);
      /* PLL source: HSI/2, multiplier: x16 -> 64MHz */
      RCC->CFGR &= (uint32_t)((uint32_t)~(RCC_CFGR_PLLSRC | RCC_CFGR_PLLXTPRE | RCC_CFGR_PLLMULL));
      RCC->CFGR |= (uint32_t)(RCC_CFGR_PLLSRC_HSI_DIV2 | RCC_CFGR_PLLMULL16);
      SystemCoreClock = 64000000;
      goto enable_pll;
    }
  }

  /* HSE OK: PLL source HSE, multiplier x9 -> 72MHz */
  RCC->CFGR &= (uint32_t)((uint32_t)~(RCC_CFGR_PLLSRC | RCC_CFGR_PLLXTPRE | RCC_CFGR_PLLMULL));
  RCC->CFGR |= (uint32_t)(RCC_CFGR_PLLSRC_HSE | RCC_CFGR_PLLMULL9);
  SystemCoreClock = 72000000;

enable_pll:
  /* Enable PLL */
  RCC->CR |= RCC_CR_PLLON;
  while((RCC->CR & RCC_CR_PLLRDY) == 0) { }

  /* Select PLL as system clock */
  RCC->CFGR &= (uint32_t)((uint32_t)~(RCC_CFGR_SW));
  RCC->CFGR |= (uint32_t)RCC_CFGR_SW_PLL;
  while ((RCC->CFGR & (uint32_t)RCC_CFGR_SWS) != (uint32_t)0x08) { }
}

void SystemCoreClockUpdate(void) {
  uint32_t tmp = 0, pllmull = 0, pllsource = 0;
  tmp = RCC->CFGR & RCC_CFGR_SWS;
  switch (tmp) {
    case 0x00: SystemCoreClock = 8000000; break;  /* HSI */
    case 0x04: SystemCoreClock = 8000000; break;  /* HSE */
    case 0x08: /* PLL */
      pllmull = (RCC->CFGR & RCC_CFGR_PLLMULL) >> 18;
      pllsource = (RCC->CFGR & RCC_CFGR_PLLSRC) >> 16;
      if (pllsource != 0) {
        pllmull = (pllmull + 2) * 2;
        SystemCoreClock = 8000000 * pllmull;
      } else {
        pllmull = (pllmull + 2);
        SystemCoreClock = 8000000 / 2 * pllmull;
      }
      break;
    default: SystemCoreClock = 8000000; break;
  }
}