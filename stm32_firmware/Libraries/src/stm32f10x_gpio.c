#include "stm32f10x_gpio.h"

void GPIO_Init(GPIO_TypeDef* GPIOx, GPIO_InitTypeDef* GPIO_InitStruct) {
  uint32_t currentmode = 0x00, currentpin = 0x00, pinpos = 0x00, pos = 0x00;
  uint32_t tmpreg = 0x00, pinmask = 0x00;
  assert_param(IS_GPIO_ALL_PERIPH(GPIOx));
  assert_param(IS_GPIO_MODE(GPIO_InitStruct->GPIO_Mode));
  assert_param(IS_GPIO_PIN(GPIO_InitStruct->GPIO_Pin));

  currentmode = ((uint32_t)GPIO_InitStruct->GPIO_Mode) & ((uint32_t)0x0F);
  if ((((uint32_t)GPIO_InitStruct->GPIO_Mode) & ((uint32_t)0x10)) != 0x00) {
    currentmode |= (uint32_t)GPIO_InitStruct->GPIO_Speed;
  }

  if (((uint32_t)GPIO_InitStruct->GPIO_Pin & ((uint32_t)0x00FF)) != 0x00) {
    tmpreg = GPIOx->CRL;
    for (pinpos = 0x00; pinpos < 0x08; pinpos++) {
      pos = ((uint32_t)0x01) << pinpos;
      currentpin = (GPIO_InitStruct->GPIO_Pin) & pos;
      if (currentpin == pos) {
        pos = pinpos << 2;
        pinmask = (((uint32_t)0x0F) << pos);
        tmpreg &= ~pinmask;
        tmpreg |= (currentmode << pos);
        if (GPIO_InitStruct->GPIO_Mode == GPIO_Mode_IPD) {
          GPIOx->BRR = (((uint32_t)0x01) << pinpos);
        } else if (GPIO_InitStruct->GPIO_Mode == GPIO_Mode_IPU) {
          GPIOx->BSRR = (((uint32_t)0x01) << pinpos);
        }
      }
    }
    GPIOx->CRL = tmpreg;
  }

  if (GPIO_InitStruct->GPIO_Pin > 0x00FF) {
    tmpreg = GPIOx->CRH;
    for (pinpos = 0x00; pinpos < 0x08; pinpos++) {
      pos = (((uint32_t)0x01) << (pinpos + 0x08));
      currentpin = ((GPIO_InitStruct->GPIO_Pin) >> 0x08) & pos;
      if (currentpin == pos) {
        pos = pinpos << 2;
        pinmask = (((uint32_t)0x0F) << pos);
        tmpreg &= ~pinmask;
        tmpreg |= (currentmode << pos);
        if (GPIO_InitStruct->GPIO_Mode == GPIO_Mode_IPD) {
          GPIOx->BRR = (((uint32_t)0x01) << (pinpos + 0x08));
        } else if (GPIO_InitStruct->GPIO_Mode == GPIO_Mode_IPU) {
          GPIOx->BSRR = (((uint32_t)0x01) << (pinpos + 0x08));
        }
      }
    }
    GPIOx->CRH = tmpreg;
  }
}

void GPIO_SetBits(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin) {
  assert_param(IS_GPIO_ALL_PERIPH(GPIOx));
  assert_param(IS_GPIO_PIN(GPIO_Pin));
  GPIOx->BSRR = GPIO_Pin;
}

void GPIO_ResetBits(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin) {
  assert_param(IS_GPIO_ALL_PERIPH(GPIOx));
  assert_param(IS_GPIO_PIN(GPIO_Pin));
  GPIOx->BRR = GPIO_Pin;
}

void GPIO_WriteBit(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin, uint8_t BitVal) {
  assert_param(IS_GPIO_ALL_PERIPH(GPIOx));
  assert_param(IS_GPIO_PIN(GPIO_Pin));
  if (BitVal != (uint8_t)0) {
    GPIOx->BSRR = GPIO_Pin;
  } else {
    GPIOx->BRR = GPIO_Pin;
  }
}

uint8_t GPIO_ReadInputDataBit(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin) {
  uint8_t bitstatus = 0x00;
  assert_param(IS_GPIO_ALL_PERIPH(GPIOx));
  assert_param(IS_GPIO_PIN(GPIO_Pin));
  if ((GPIOx->IDR & GPIO_Pin) != (uint32_t)0x00) {
    bitstatus = (uint8_t)1;
  }
  return bitstatus;
}

uint8_t GPIO_ReadOutputDataBit(GPIO_TypeDef* GPIOx, uint16_t GPIO_Pin) {
  uint8_t bitstatus = 0x00;
  assert_param(IS_GPIO_ALL_PERIPH(GPIOx));
  assert_param(IS_GPIO_PIN(GPIO_Pin));
  if ((GPIOx->ODR & GPIO_Pin) != (uint32_t)0x00) {
    bitstatus = (uint8_t)1;
  }
  return bitstatus;
}