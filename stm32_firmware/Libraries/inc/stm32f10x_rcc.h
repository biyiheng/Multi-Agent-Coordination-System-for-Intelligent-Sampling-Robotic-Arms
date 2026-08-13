#ifndef __STM32F10X_RCC_H
#define __STM32F10X_RCC_H

#include "stm32f10x.h"

typedef struct {
  uint32_t SYSCLK_Frequency;
  uint32_t HCLK_Frequency;
  uint32_t PCLK1_Frequency;
  uint32_t PCLK2_Frequency;
  uint32_t ADCCLK_Frequency;
} RCC_ClocksTypeDef;

/* HSE config */
#define RCC_HSE_OFF    ((uint32_t)0x00000000)
#define RCC_HSE_ON     ((uint32_t)0x00010000)
#define RCC_HSE_Bypass ((uint32_t)0x00040000)

/* PLL entry clock source */
#define RCC_PLLSource_HSI_Div2  ((uint32_t)0x00000000)
#define RCC_PLLSource_HSE_Div1  ((uint32_t)0x00010000)
#define RCC_PLLSource_HSE_Div2  ((uint32_t)0x00030000)

/* PLL multiplication factor */
#define RCC_PLLMul_4   ((uint32_t)0x00080000)
#define RCC_PLLMul_5   ((uint32_t)0x000C0000)
#define RCC_PLLMul_6   ((uint32_t)0x00100000)
#define RCC_PLLMul_7   ((uint32_t)0x00140000)
#define RCC_PLLMul_8   ((uint32_t)0x00180000)
#define RCC_PLLMul_9   ((uint32_t)0x001C0000)
#define RCC_PLLMul_10  ((uint32_t)0x00200000)
#define RCC_PLLMul_11  ((uint32_t)0x00240000)
#define RCC_PLLMul_12  ((uint32_t)0x00280000)
#define RCC_PLLMul_13  ((uint32_t)0x002C0000)
#define RCC_PLLMul_14  ((uint32_t)0x00300000)
#define RCC_PLLMul_15  ((uint32_t)0x00340000)
#define RCC_PLLMul_16  ((uint32_t)0x00380000)

/* SYSCLK source */
#define RCC_SYSCLKSource_HSI      ((uint32_t)0x00000000)
#define RCC_SYSCLKSource_HSE      ((uint32_t)0x00000004)
#define RCC_SYSCLKSource_PLLCLK   ((uint32_t)0x00000008)

/* HCLK divider */
#define RCC_SYSCLK_Div1   ((uint32_t)0x00000000)
#define RCC_SYSCLK_Div2   ((uint32_t)0x00000080)
#define RCC_SYSCLK_Div4   ((uint32_t)0x00000090)
#define RCC_SYSCLK_Div8   ((uint32_t)0x000000A0)
#define RCC_SYSCLK_Div16  ((uint32_t)0x000000B0)
#define RCC_SYSCLK_Div64  ((uint32_t)0x000000C0)
#define RCC_SYSCLK_Div128 ((uint32_t)0x000000D0)
#define RCC_SYSCLK_Div256 ((uint32_t)0x000000E0)
#define RCC_SYSCLK_Div512 ((uint32_t)0x000000F0)

/* APB1/APB2 divider */
#define RCC_HCLK_Div1  ((uint32_t)0x00000000)
#define RCC_HCLK_Div2  ((uint32_t)0x00000400)
#define RCC_HCLK_Div4  ((uint32_t)0x00000500)
#define RCC_HCLK_Div8  ((uint32_t)0x00000600)
#define RCC_HCLK_Div16 ((uint32_t)0x00000700)

/* Flags */
#define RCC_FLAG_HSIRDY  ((uint8_t)0x20)
#define RCC_FLAG_HSERDY  ((uint8_t)0x30)
#define RCC_FLAG_PLLRDY  ((uint8_t)0x38)
#define RCC_FLAG_LSERDY  ((uint8_t)0x40)
#define RCC_FLAG_LSIRDY  ((uint8_t)0x50)
#define RCC_FLAG_PINRST  ((uint8_t)0x7A)
#define RCC_FLAG_PORRST  ((uint8_t)0x7B)
#define RCC_FLAG_SFTRST  ((uint8_t)0x7C)
#define RCC_FLAG_IWDGRST ((uint8_t)0x7D)
#define RCC_FLAG_WWDGRST ((uint8_t)0x7E)
#define RCC_FLAG_LPWRRST ((uint8_t)0x7F)

/* ADC prescaler */
#define RCC_PCLK2_Div2  ((uint32_t)0x00000000)
#define RCC_PCLK2_Div4  ((uint32_t)0x00004000)
#define RCC_PCLK2_Div6  ((uint32_t)0x00008000)
#define RCC_PCLK2_Div8  ((uint32_t)0x0000C000)

/* APB1/APB2 peripheral clocks */
#define RCC_APB2Periph_AFIO    ((uint32_t)0x00000001)
#define RCC_APB2Periph_GPIOA   ((uint32_t)0x00000004)
#define RCC_APB2Periph_GPIOB   ((uint32_t)0x00000008)
#define RCC_APB2Periph_GPIOC   ((uint32_t)0x00000010)
#define RCC_APB2Periph_GPIOD   ((uint32_t)0x00000020)
#define RCC_APB2Periph_GPIOE   ((uint32_t)0x00000040)
#define RCC_APB2Periph_ADC1    ((uint32_t)0x00000200)
#define RCC_APB2Periph_ADC2    ((uint32_t)0x00000400)
#define RCC_APB2Periph_TIM1    ((uint32_t)0x00000800)
#define RCC_APB2Periph_SPI1    ((uint32_t)0x00001000)
#define RCC_APB2Periph_USART1  ((uint32_t)0x00004000)

#define RCC_APB1Periph_TIM2    ((uint32_t)0x00000001)
#define RCC_APB1Periph_TIM3    ((uint32_t)0x00000002)
#define RCC_APB1Periph_TIM4    ((uint32_t)0x00000004)
#define RCC_APB1Periph_WWDG    ((uint32_t)0x00000800)
#define RCC_APB1Periph_SPI2    ((uint32_t)0x00004000)
#define RCC_APB1Periph_USART2  ((uint32_t)0x00020000)
#define RCC_APB1Periph_USART3  ((uint32_t)0x00040000)
#define RCC_APB1Periph_I2C1    ((uint32_t)0x00200000)
#define RCC_APB1Periph_I2C2    ((uint32_t)0x00400000)
#define RCC_APB1Periph_CAN1    ((uint32_t)0x02000000)
#define RCC_APB1Periph_BKP     ((uint32_t)0x08000000)
#define RCC_APB1Periph_PWR     ((uint32_t)0x10000000)

void RCC_DeInit(void);
void RCC_HSEConfig(uint32_t RCC_HSE);
uint8_t RCC_WaitForHSEStartUp(void);
void RCC_PLLConfig(uint32_t RCC_PLLSource, uint32_t RCC_PLLMul);
void RCC_PLLCmd(uint8_t NewState);
void RCC_SYSCLKConfig(uint32_t RCC_SYSCLKSource);
uint8_t RCC_GetSYSCLKSource(void);
void RCC_HCLKConfig(uint32_t RCC_SYSCLK);
void RCC_PCLK1Config(uint32_t RCC_HCLK);
void RCC_PCLK2Config(uint32_t RCC_HCLK);
void RCC_ADCCLKConfig(uint32_t RCC_PCLK2);
void RCC_APB2PeriphClockCmd(uint32_t RCC_APB2Periph, uint8_t NewState);
void RCC_APB1PeriphClockCmd(uint32_t RCC_APB1Periph, uint8_t NewState);
uint8_t RCC_GetFlagStatus(uint8_t RCC_FLAG);

#endif