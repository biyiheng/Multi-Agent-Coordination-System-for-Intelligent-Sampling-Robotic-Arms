/**
  ******************************************************************************
  * @file    stm32f10x.h
  * @author  MCD Application Team
  * @version V3.5.0
  * @date    11-March-2011
  * @brief   CMSIS Cortex-M3 Device Peripheral Access Layer Header File.
  *          This file contains all the peripheral register's definitions, bits
  *          definitions and memory mapping for STM32F10x Connectivity line,
  *          High-density, Medium-density, Medium-density Value line,
  *          Low-density, Low-density Value line and XL-density devices.
  *
  *          The file is the unique include file that the application programmer
  *          is using in the C source code, usually in main.c. This file contains:
  *           - Configuration section that allows to select:
  *              - The device used in the target application
  *              - To use or not the peripheral's drivers in application code(i.e.
  *                code will be based on direct access to peripheral's registers
  *                rather than drivers API), this option is controlled by
  *                "#define USE_STDPERIPH_DRIVER"
  *              - To change few application-specific parameters such as the HSE
  *                crystal frequency
  *           - Data structures and the address mapping for all peripherals
  *           - Peripheral's registers declarations and bits definition
  *           - Macros to access peripheral's registers hardware
  *
  ******************************************************************************
  * @attention
  *
  * THE PRESENT FIRMWARE WHICH IS FOR GUIDANCE ONLY AIMS AT PROVIDING CUSTOMERS
  * WITH CODING INFORMATION REGARDING THEIR PRODUCTS IN ORDER FOR THEM TO SAVE
  * TIME. AS A RESULT, STMICROELECTRONICS SHALL NOT BE HELD LIABLE FOR ANY
  * DIRECT, INDIRECT OR CONSEQUENTIAL DAMAGES WITH RESPECT TO ANY CLAIMS ARISING
  * FROM THE CONTENT OF SUCH FIRMWARE AND/OR THE USE MADE BY CUSTOMERS OF THE
  * CODING INFORMATION CONTAINED HEREIN IN CONNECTION WITH THEIR PRODUCTS.
  *
  * <h2><center>&copy; COPYRIGHT 2011 STMicroelectronics</center></h2>
  ******************************************************************************
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __STM32F10X_H
#define __STM32F10X_H

#ifdef __cplusplus
 extern "C" {
#endif

/** @addtogroup Library_configuration_section
  * @{
  */

/**
  * @brief STM32F10x Device Series Configuration
  *
  *    STM32F10X_LD        STM32F10X_LD_VL        Low-density devices
  *    STM32F10X_MD        STM32F10X_MD_VL        Medium-density devices
  *    STM32F10X_HD        STM32F10X_HD_VL        High-density devices
  *    STM32F10X_XL                                XL-density devices
  *    STM32F10X_CL                                Connectivity line devices
  *
  *  Tip: To avoid modifying this file each time you need to switch between these
  *       devices, you can define the device in your toolchain compiler preprocessor.
  */
#if !defined (STM32F10X_LD) && !defined (STM32F10X_LD_VL) && !defined (STM32F10X_MD) && !defined (STM32F10X_MD_VL) && !defined (STM32F10X_HD) && !defined (STM32F10X_HD_VL) && !defined (STM32F10X_XL) && !defined (STM32F10X_CL)
  /* #define STM32F10X_LD */     /*!< STM32F10X_LD: STM32 Low density devices */
  /* #define STM32F10X_LD_VL */  /*!< STM32F10X_LD_VL: STM32 Low density Value Line devices */
  #define STM32F10X_MD           /*!< STM32F10X_MD: STM32 Medium density devices */
  /* #define STM32F10X_MD_VL */  /*!< STM32F10X_MD_VL: STM32 Medium density Value Line devices */
  /* #define STM32F10X_HD */     /*!< STM32F10X_HD: STM32 High density devices */
  /* #define STM32F10X_HD_VL */  /*!< STM32F10X_HD_VL: STM32 High density value line devices */
  /* #define STM32F10X_XL */     /*!< STM32F10X_XL: STM32 XL-density devices */
  /* #define STM32F10X_CL */     /*!< STM32F10X_CL: STM32 Connectivity line devices */
#endif

/**
  * @brief STM32F10x Standard Peripheral Library version number
  */
#define __STM32F10X_STDPERIPH_VERSION_MAIN   (0x03) /*!< [31:24] main version */
#define __STM32F10X_STDPERIPH_VERSION_SUB1   (0x05) /*!< [23:16] sub1 version */
#define __STM32F10X_STDPERIPH_VERSION_SUB2   (0x00) /*!< [15:8]  sub2 version */
#define __STM32F10X_STDPERIPH_VERSION_RC     (0x00) /*!< [7:0]  release candidate */
#define __STM32F10X_STDPERIPH_VERSION        ((__STM32F10X_STDPERIPH_VERSION_MAIN << 24)  | \
                                              (__STM32F10X_STDPERIPH_VERSION_SUB1 << 16) | \
                                              (__STM32F10X_STDPERIPH_VERSION_SUB2 << 8)  | \
                                              (__STM32F10X_STDPERIPH_VERSION_RC))

/**
  * @brief Configuration of the Cortex-M3 Processor and Core Peripherals
  */
#if defined (STM32F10X_LD_VL) || defined (STM32F10X_MD_VL) || defined (STM32F10X_HD_VL)
  #define HSE_VALUE    ((uint32_t)8000000) /*!< Value of the External oscillator in Hz */
#else
  #define HSE_VALUE    ((uint32_t)8000000) /*!< Value of the External oscillator in Hz */
#endif /* STM32F10X_LD_VL || STM32F10X_MD_VL || STM32F10X_HD_VL */

#define HSI_VALUE    ((uint32_t)8000000) /*!< Value of the Internal oscillator in Hz */

/*!< Uncomment the line below to expanse the "assert_param" macro in the
     Standard Peripheral Library drivers code */
/* #define USE_FULL_ASSERT    1 */

/* Exported types ------------------------------------------------------------*/
/* Exported constants --------------------------------------------------------*/
/* Exported macro ------------------------------------------------------------*/

/** @addtogroup Exported_types
  * @{
  */

/**
  * @brief IO definitions
  */
#ifdef __cplusplus
  #define   __I     volatile             /*!< Defines 'read only' permissions */
#else
  #define   __I     volatile const       /*!< Defines 'read only' permissions */
#endif
#define     __O     volatile             /*!< Defines 'write only' permissions */
#define     __IO    volatile             /*!< Defines 'read / write' permissions */

/* Includes ------------------------------------------------------------------*/
#include <stdint.h>

/*!< STM32F10x Standard Peripheral Library old types (maintained for legacy purpose) */
typedef int32_t  s32;
typedef int16_t s16;
typedef int8_t  s8;

typedef const int32_t sc32;  /*!< Read Only */
typedef const int16_t sc16;  /*!< Read Only */
typedef const int8_t sc8;   /*!< Read Only */

typedef __IO int32_t  vs32;
typedef __IO int16_t  vs16;
typedef __IO int8_t   vs8;

typedef __I int32_t vsc32;  /*!< Read Only */
typedef __I int16_t vsc16;  /*!< Read Only */
typedef __I int8_t vsc8;   /*!< Read Only */

typedef uint32_t  u32;
typedef uint16_t u16;
typedef uint8_t  u8;

typedef const uint32_t uc32;  /*!< Read Only */
typedef const uint16_t uc16;  /*!< Read Only */
typedef const uint8_t uc8;   /*!< Read Only */

typedef __IO uint32_t  vu32;
typedef __IO uint16_t vu16;
typedef __IO uint8_t  vu8;

typedef __I uint32_t vuc32;  /*!< Read Only */
typedef __I uint16_t vuc16;  /*!< Read Only */
typedef __I uint8_t vuc8;   /*!< Read Only */

/**
  * @}
  */

/** @addtogroup Exported_macro
  * @{
  */

/*!< STM32F10x Standard Peripheral Library old macros (maintained for legacy purpose) */
typedef enum {RESET = 0, SET = !RESET} FlagStatus, ITStatus;

typedef enum {DISABLE = 0, ENABLE = !DISABLE} FunctionalState;
#define IS_FUNCTIONAL_STATE(STATE) (((STATE) == DISABLE) || ((STATE) == ENABLE))

typedef enum {ERROR = 0, SUCCESS = !ERROR} ErrorStatus;

/*!< STM32F10x Standard Peripheral Library old definitions (maintained for legacy purpose) */
#define HSEStartUp_TimeOut   ((uint16_t)0x0500) /*!< Time out for HSE start up */

/**
  * @}
  */

#include "core_cm3.h"
#include "system_stm32f10x.h"

/** @addtogroup Configuration_section_for_CMSIS
  * @{
  */
#define __CM3_REV                 0x0102 /*!< Core Revision r1p2                                  */
#define __MPU_PRESENT             1      /*!< STM32F10X provide an MPU                            */
#define __NVIC_PRIO_BITS          4      /*!< STM32F10X uses 4 Bits for the Priority Levels       */
#define __Vendor_SysTickConfig    0      /*!< Set to 1 if different SysTick Config is used        */

/**
  * @brief STM32F10x Interrupt Number Definition (defined in core_cm3.h)
  */

/**
  * @}
  */

/**
  * @brief  assert_param macro for parameter checking
  */
#ifdef  USE_FULL_ASSERT

/**
  * @brief  The assert_param macro is used for function's parameters check.
  * @param  expr: If expr is false, it calls assert_failed function which reports
  *         the name of the source file and the source line number of the call
  *         that failed. If expr is true, it returns no value.
  * @retval None
  */
  #define assert_param(expr) ((expr) ? (void)0 : assert_failed((uint8_t *)__FILE__, __LINE__))
/* Exported functions ------------------------------------------------------- */
  void assert_failed(uint8_t* file, uint32_t line);
#else
  #define assert_param(expr) ((void)0)
#endif /* USE_FULL_ASSERT */

  /* ========================================================================= */
  /*                   Memory and Peripheral Base Addresses                    */
  /* ========================================================================= */

#define FLASH_BASE                ((uint32_t)0x08000000) /*!< FLASH base address in the alias region */
#define SRAM_BASE                 ((uint32_t)0x20000000) /*!< SRAM base address in the alias region */
#define PERIPH_BASE               ((uint32_t)0x40000000) /*!< Peripheral base address in the alias region */

#define SRAM_BB_BASE              ((uint32_t)0x22000000) /*!< SRAM base address in the bit-band region */
#define PERIPH_BB_BASE            ((uint32_t)0x42000000) /*!< Peripheral base address in the bit-band region */

/*!< Peripheral memory map */
#define APB1PERIPH_BASE            PERIPH_BASE
#define APB2PERIPH_BASE           (PERIPH_BASE + 0x10000)
#define AHBPERIPH_BASE            (PERIPH_BASE + 0x20000)

  /* ========================================================================= */
  /*                     APB1 Peripheral Base Addresses                       */
  /* ========================================================================= */
#define TIM2_BASE                 (APB1PERIPH_BASE + 0x0000)
#define TIM3_BASE                 (APB1PERIPH_BASE + 0x0400)
#define TIM4_BASE                 (APB1PERIPH_BASE + 0x0800)
#define RTC_BASE                  (APB1PERIPH_BASE + 0x2800)
#define WWDG_BASE                 (APB1PERIPH_BASE + 0x2C00)
#define IWDG_BASE                 (APB1PERIPH_BASE + 0x3000)
#define SPI2_BASE                 (APB1PERIPH_BASE + 0x3800)
#define SPI3_BASE                 (APB1PERIPH_BASE + 0x3C00)
#define USART2_BASE               (APB1PERIPH_BASE + 0x4400)
#define USART3_BASE               (APB1PERIPH_BASE + 0x4800)
#define UART4_BASE                (APB1PERIPH_BASE + 0x4C00)
#define UART5_BASE                (APB1PERIPH_BASE + 0x5000)
#define I2C1_BASE                 (APB1PERIPH_BASE + 0x5400)
#define I2C2_BASE                 (APB1PERIPH_BASE + 0x5800)
#define CAN1_BASE                 (APB1PERIPH_BASE + 0x6400)
#define CAN2_BASE                 (APB1PERIPH_BASE + 0x6800)
#define BKP_BASE                  (APB1PERIPH_BASE + 0x6C00)
#define PWR_BASE                  (APB1PERIPH_BASE + 0x7000)
#define DAC_BASE                  (APB1PERIPH_BASE + 0x7400)

  /* ========================================================================= */
  /*                     APB2 Peripheral Base Addresses                       */
  /* ========================================================================= */
#define AFIO_BASE                 (APB2PERIPH_BASE + 0x0000)
#define EXTI_BASE                 (APB2PERIPH_BASE + 0x0400)
#define GPIOA_BASE                (APB2PERIPH_BASE + 0x0800)
#define GPIOB_BASE                (APB2PERIPH_BASE + 0x0C00)
#define GPIOC_BASE                (APB2PERIPH_BASE + 0x1000)
#define GPIOD_BASE                (APB2PERIPH_BASE + 0x1400)
#define GPIOE_BASE                (APB2PERIPH_BASE + 0x1800)
#define GPIOF_BASE                (APB2PERIPH_BASE + 0x1C00)
#define GPIOG_BASE                (APB2PERIPH_BASE + 0x2000)
#define ADC1_BASE                 (APB2PERIPH_BASE + 0x2400)
#define ADC2_BASE                 (APB2PERIPH_BASE + 0x2800)
#define TIM1_BASE                 (APB2PERIPH_BASE + 0x2C00)
#define SPI1_BASE                 (APB2PERIPH_BASE + 0x3000)
#define TIM8_BASE                 (APB2PERIPH_BASE + 0x3400)
#define USART1_BASE               (APB2PERIPH_BASE + 0x3800)
#define ADC3_BASE                 (APB2PERIPH_BASE + 0x3C00)

  /* ========================================================================= */
  /*                     AHB Peripheral Base Addresses                       */
  /* ========================================================================= */
#define DMA1_BASE                 (AHBPERIPH_BASE + 0x0000)
#define DMA2_BASE                 (AHBPERIPH_BASE + 0x0400)
#define RCC_BASE                  (AHBPERIPH_BASE + 0x1000)
#define CRC_BASE                  (AHBPERIPH_BASE + 0x3000)
#define FLASH_R_BASE              (AHBPERIPH_BASE + 0x2000) /*!< Flash registers base address */

  /* ========================================================================= */
  /*                    Peripheral Declaration                                 */
  /* ========================================================================= */

  /* ========================================================================= */
  /*                        RCC Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t CR;
  __IO uint32_t CFGR;
  __IO uint32_t CIR;
  __IO uint32_t APB2RSTR;
  __IO uint32_t APB1RSTR;
  __IO uint32_t AHBENR;
  __IO uint32_t APB2ENR;
  __IO uint32_t APB1ENR;
  __IO uint32_t BDCR;
  __IO uint32_t CSR;
} RCC_TypeDef;

  /* ========================================================================= */
  /*                        GPIO Register Structure                           */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t CRL;
  __IO uint32_t CRH;
  __IO uint32_t IDR;
  __IO uint32_t ODR;
  __IO uint32_t BSRR;
  __IO uint32_t BRR;
  __IO uint32_t LCKR;
} GPIO_TypeDef;

  /* ========================================================================= */
  /*                       USART Register Structure                           */
  /* ========================================================================= */
typedef struct
{
  __IO uint16_t SR;
  uint16_t  RESERVED0;
  __IO uint16_t DR;
  uint16_t  RESERVED1;
  __IO uint16_t BRR;
  uint16_t  RESERVED2;
  __IO uint16_t CR1;
  uint16_t  RESERVED3;
  __IO uint16_t CR2;
  uint16_t  RESERVED4;
  __IO uint16_t CR3;
  uint16_t  RESERVED5;
  __IO uint16_t GTPR;
  uint16_t  RESERVED6;
} USART_TypeDef;

  /* ========================================================================= */
  /*                        TIM Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint16_t CR1;
  uint16_t  RESERVED0;
  __IO uint16_t CR2;
  uint16_t  RESERVED1;
  __IO uint16_t SMCR;
  uint16_t  RESERVED2;
  __IO uint16_t DIER;
  uint16_t  RESERVED3;
  __IO uint16_t SR;
  uint16_t  RESERVED4;
  __IO uint16_t EGR;
  uint16_t  RESERVED5;
  __IO uint16_t CCMR1;
  uint16_t  RESERVED6;
  __IO uint16_t CCMR2;
  uint16_t  RESERVED7;
  __IO uint16_t CCER;
  uint16_t  RESERVED8;
  __IO uint16_t CNT;
  uint16_t  RESERVED9;
  __IO uint16_t PSC;
  uint16_t  RESERVED10;
  __IO uint16_t ARR;
  uint16_t  RESERVED11;
  __IO uint16_t RCR;
  uint16_t  RESERVED12;
  __IO uint16_t CCR1;
  uint16_t  RESERVED13;
  __IO uint16_t CCR2;
  uint16_t  RESERVED14;
  __IO uint16_t CCR3;
  uint16_t  RESERVED15;
  __IO uint16_t CCR4;
  uint16_t  RESERVED16;
  __IO uint16_t BDTR;
  uint16_t  RESERVED17;
  __IO uint16_t DCR;
  uint16_t  RESERVED18;
  __IO uint16_t DMAR;
  uint16_t  RESERVED19;
} TIM_TypeDef;

  /* ========================================================================= */
  /*                       FLASH Register Structure                           */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t ACR;
  __IO uint32_t KEYR;
  __IO uint32_t OPTKEYR;
  __IO uint32_t SR;
  __IO uint32_t CR;
  __IO uint32_t AR;
  __IO uint32_t RESERVED;
  __IO uint32_t OBR;
  __IO uint32_t WRPR;
} FLASH_TypeDef;

  /* ========================================================================= */
  /*                        ADC Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t SR;
  __IO uint32_t CR1;
  __IO uint32_t CR2;
  __IO uint32_t SMPR1;
  __IO uint32_t SMPR2;
  __IO uint32_t JOFR1;
  __IO uint32_t JOFR2;
  __IO uint32_t JOFR3;
  __IO uint32_t JOFR4;
  __IO uint32_t HTR;
  __IO uint32_t LTR;
  __IO uint32_t SQR1;
  __IO uint32_t SQR2;
  __IO uint32_t SQR3;
  __IO uint32_t JSQR;
  __IO uint32_t JDR1;
  __IO uint32_t JDR2;
  __IO uint32_t JDR3;
  __IO uint32_t JDR4;
  __IO uint32_t DR;
} ADC_TypeDef;

  /* ========================================================================= */
  /*                       EXTI Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t IMR;
  __IO uint32_t EMR;
  __IO uint32_t RTSR;
  __IO uint32_t FTSR;
  __IO uint32_t SWIER;
  __IO uint32_t PR;
} EXTI_TypeDef;

  /* ========================================================================= */
  /*                       IWDG Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t KR;
  __IO uint32_t PR;
  __IO uint32_t RLR;
  __IO uint32_t SR;
} IWDG_TypeDef;

  /* ========================================================================= */
  /*                        DMA Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t CCR;
  __IO uint32_t CNDTR;
  __IO uint32_t CPAR;
  __IO uint32_t CMAR;
} DMA_Channel_TypeDef;

typedef struct
{
  __IO uint32_t ISR;
  __IO uint32_t IFCR;
} DMA_TypeDef;

  /* ========================================================================= */
  /*                       AFIO Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t EVCR;
  __IO uint32_t MAPR;
  __IO uint32_t EXTICR[4];
  uint32_t RESERVED0;
  __IO uint32_t MAPR2;
} AFIO_TypeDef;

  /* ========================================================================= */
  /*                       SPI Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint16_t CR1;
  uint16_t  RESERVED0;
  __IO uint16_t CR2;
  uint16_t  RESERVED1;
  __IO uint16_t SR;
  uint16_t  RESERVED2;
  __IO uint16_t DR;
  uint16_t  RESERVED3;
  __IO uint16_t CRCPR;
  uint16_t  RESERVED4;
  __IO uint16_t RXCRCR;
  uint16_t  RESERVED5;
  __IO uint16_t TXCRCR;
  uint16_t  RESERVED6;
} SPI_TypeDef;

  /* ========================================================================= */
  /*                        I2C Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint16_t CR1;
  uint16_t  RESERVED0;
  __IO uint16_t CR2;
  uint16_t  RESERVED1;
  __IO uint16_t OAR1;
  uint16_t  RESERVED2;
  __IO uint16_t OAR2;
  uint16_t  RESERVED3;
  __IO uint16_t DR;
  uint16_t  RESERVED4;
  __IO uint16_t SR1;
  uint16_t  RESERVED5;
  __IO uint16_t SR2;
  uint16_t  RESERVED6;
  __IO uint16_t CCR;
  uint16_t  RESERVED7;
  __IO uint16_t TRISE;
  uint16_t  RESERVED8;
} I2C_TypeDef;

  /* ========================================================================= */
  /*                       WWDG Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t CR;
  __IO uint32_t CFR;
  __IO uint32_t SR;
} WWDG_TypeDef;

  /* ========================================================================= */
  /*                       PWR Register Structure                             */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t CR;
  __IO uint32_t CSR;
} PWR_TypeDef;

  /* ========================================================================= */
  /*                       BKP Register Structure                             */
  /* ========================================================================= */
typedef struct
{
  uint32_t RESERVED0;
  __IO uint32_t DR1;
  __IO uint32_t DR2;
  __IO uint32_t DR3;
  __IO uint32_t DR4;
  __IO uint32_t DR5;
  __IO uint32_t DR6;
  __IO uint32_t DR7;
  __IO uint32_t DR8;
  __IO uint32_t DR9;
  __IO uint32_t DR10;
  __IO uint32_t RTCCR;
  __IO uint32_t CR;
  __IO uint32_t CSR;
} BKP_TypeDef;

  /* ========================================================================= */
  /*                        DAC Register Structure                            */
  /* ========================================================================= */
typedef struct
{
  __IO uint32_t CR;
  __IO uint32_t SWTRIGR;
  __IO uint32_t DHR12R1;
  __IO uint32_t DHR12L1;
  __IO uint32_t DHR8R1;
  __IO uint32_t DHR12R2;
  __IO uint32_t DHR12L2;
  __IO uint32_t DHR8R2;
  __IO uint32_t DHR12RD;
  __IO uint32_t DHR12LD;
  __IO uint32_t DHR8RD;
  __IO uint32_t DOR1;
  __IO uint32_t DOR2;
} DAC_TypeDef;

  /* ========================================================================= */
  /*                    Peripheral Instance Definitions                        */
  /* ========================================================================= */

/* RCC -----------------------------------------------------------------------*/
#define RCC                 ((RCC_TypeDef *) RCC_BASE)

/* GPIO ----------------------------------------------------------------------*/
#define GPIOA               ((GPIO_TypeDef *) GPIOA_BASE)
#define GPIOB               ((GPIO_TypeDef *) GPIOB_BASE)
#define GPIOC               ((GPIO_TypeDef *) GPIOC_BASE)
#define GPIOD               ((GPIO_TypeDef *) GPIOD_BASE)
#define GPIOE               ((GPIO_TypeDef *) GPIOE_BASE)

/* USART ---------------------------------------------------------------------*/
#define USART1              ((USART_TypeDef *) USART1_BASE)
#define USART2              ((USART_TypeDef *) USART2_BASE)
#define USART3              ((USART_TypeDef *) USART3_BASE)

/* TIM -----------------------------------------------------------------------*/
#define TIM1                ((TIM_TypeDef *) TIM1_BASE)
#define TIM2                ((TIM_TypeDef *) TIM2_BASE)
#define TIM3                ((TIM_TypeDef *) TIM3_BASE)
#define TIM4                ((TIM_TypeDef *) TIM4_BASE)

/* FLASH ---------------------------------------------------------------------*/
#define FLASH               ((FLASH_TypeDef *) FLASH_R_BASE)

/* ADC -----------------------------------------------------------------------*/
#define ADC1                ((ADC_TypeDef *) ADC1_BASE)
#define ADC2                ((ADC_TypeDef *) ADC2_BASE)

/* EXTI ----------------------------------------------------------------------*/
#define EXTI                ((EXTI_TypeDef *) EXTI_BASE)

/* IWDG ----------------------------------------------------------------------*/
#define IWDG                ((IWDG_TypeDef *) IWDG_BASE)

/* DMA -----------------------------------------------------------------------*/
#define DMA1                ((DMA_TypeDef *) DMA1_BASE)
#define DMA1_Channel1       ((DMA_Channel_TypeDef *) (DMA1_BASE + 0x0008))
#define DMA1_Channel2       ((DMA_Channel_TypeDef *) (DMA1_BASE + 0x001C))
#define DMA1_Channel3       ((DMA_Channel_TypeDef *) (DMA1_BASE + 0x0030))
#define DMA1_Channel4       ((DMA_Channel_TypeDef *) (DMA1_BASE + 0x0044))
#define DMA1_Channel5       ((DMA_Channel_TypeDef *) (DMA1_BASE + 0x0058))
#define DMA1_Channel6       ((DMA_Channel_TypeDef *) (DMA1_BASE + 0x006C))
#define DMA1_Channel7       ((DMA_Channel_TypeDef *) (DMA1_BASE + 0x0080))

/* AFIO ----------------------------------------------------------------------*/
#define AFIO                ((AFIO_TypeDef *) AFIO_BASE)

/* SPI -----------------------------------------------------------------------*/
#define SPI1                ((SPI_TypeDef *) SPI1_BASE)
#define SPI2                ((SPI_TypeDef *) SPI2_BASE)

/* I2C -----------------------------------------------------------------------*/
#define I2C1                ((I2C_TypeDef *) I2C1_BASE)
#define I2C2                ((I2C_TypeDef *) I2C2_BASE)

/* WWDG ----------------------------------------------------------------------*/
#define WWDG                ((WWDG_TypeDef *) WWDG_BASE)

/* PWR -----------------------------------------------------------------------*/
#define PWR                 ((PWR_TypeDef *) PWR_BASE)

/* BKP -----------------------------------------------------------------------*/
#define BKP                 ((BKP_TypeDef *) BKP_BASE)

  /* ========================================================================= */
  /*                Register Bit Definitions                                  */
  /* ========================================================================= */

  /* ========================================================================= */
  /*                            RCC Registers                                 */
  /* ========================================================================= */

/* --------------------  RCC_CR Register  -------------------- */
#define  RCC_CR_HSION                        ((uint32_t)0x00000001)        /*!< Internal High Speed clock enable */
#define  RCC_CR_HSIRDY                       ((uint32_t)0x00000002)        /*!< Internal High Speed clock ready flag */
#define  RCC_CR_HSITRIM                      ((uint32_t)0x000000F8)        /*!< Internal High Speed clock trimming */
#define  RCC_CR_HSITRIM_0                    ((uint32_t)0x00000008)        /*!< Bit 0 */
#define  RCC_CR_HSITRIM_1                    ((uint32_t)0x00000010)        /*!< Bit 1 */
#define  RCC_CR_HSITRIM_2                    ((uint32_t)0x00000020)        /*!< Bit 2 */
#define  RCC_CR_HSITRIM_3                    ((uint32_t)0x00000040)        /*!< Bit 3 */
#define  RCC_CR_HSITRIM_4                    ((uint32_t)0x00000080)        /*!< Bit 4 */
#define  RCC_CR_HSICAL                       ((uint32_t)0x0000FF00)        /*!< Internal High Speed clock Calibration */
#define  RCC_CR_HSICAL_0                     ((uint32_t)0x00000100)        /*!< Bit 0 */
#define  RCC_CR_HSICAL_1                     ((uint32_t)0x00000200)        /*!< Bit 1 */
#define  RCC_CR_HSICAL_2                     ((uint32_t)0x00000400)        /*!< Bit 2 */
#define  RCC_CR_HSICAL_3                     ((uint32_t)0x00000800)        /*!< Bit 3 */
#define  RCC_CR_HSICAL_4                     ((uint32_t)0x00001000)        /*!< Bit 4 */
#define  RCC_CR_HSICAL_5                     ((uint32_t)0x00002000)        /*!< Bit 5 */
#define  RCC_CR_HSICAL_6                     ((uint32_t)0x00004000)        /*!< Bit 6 */
#define  RCC_CR_HSICAL_7                     ((uint32_t)0x00008000)        /*!< Bit 7 */
#define  RCC_CR_HSEON                        ((uint32_t)0x00010000)        /*!< External High Speed clock enable */
#define  RCC_CR_HSERDY                       ((uint32_t)0x00020000)        /*!< External High Speed clock ready flag */
#define  RCC_CR_HSEBYP                       ((uint32_t)0x00040000)        /*!< External High Speed clock Bypass */
#define  RCC_CR_CSSON                        ((uint32_t)0x00080000)        /*!< Clock Security System enable */
#define  RCC_CR_PLLON                        ((uint32_t)0x01000000)        /*!< PLL enable */
#define  RCC_CR_PLLRDY                       ((uint32_t)0x02000000)        /*!< PLL clock ready flag */

/* --------------------  RCC_CFGR Register  -------------------- */
#define  RCC_CFGR_SW                         ((uint32_t)0x00000003)        /*!< SYSCLK source selection */
#define  RCC_CFGR_SW_HSI                     ((uint32_t)0x00000000)        /*!< HSI selected as system clock */
#define  RCC_CFGR_SW_HSE                     ((uint32_t)0x00000001)        /*!< HSE selected as system clock */
#define  RCC_CFGR_SW_PLL                     ((uint32_t)0x00000002)        /*!< PLL selected as system clock */
#define  RCC_CFGR_SWS                        ((uint32_t)0x0000000C)        /*!< SYSCLK status */
#define  RCC_CFGR_SWS_HSI                    ((uint32_t)0x00000000)        /*!< HSI oscillator used as system clock */
#define  RCC_CFGR_SWS_HSE                    ((uint32_t)0x00000004)        /*!< HSE oscillator used as system clock */
#define  RCC_CFGR_SWS_PLL                    ((uint32_t)0x00000008)        /*!< PLL used as system clock */
#define  RCC_CFGR_HPRE                       ((uint32_t)0x000000F0)        /*!< AHB prescaler */
#define  RCC_CFGR_HPRE_DIV1                  ((uint32_t)0x00000000)        /*!< SYSCLK not divided */
#define  RCC_CFGR_HPRE_DIV2                  ((uint32_t)0x00000080)        /*!< SYSCLK divided by 2 */
#define  RCC_CFGR_HPRE_DIV4                  ((uint32_t)0x00000090)        /*!< SYSCLK divided by 4 */
#define  RCC_CFGR_HPRE_DIV8                  ((uint32_t)0x000000A0)        /*!< SYSCLK divided by 8 */
#define  RCC_CFGR_HPRE_DIV16                 ((uint32_t)0x000000B0)        /*!< SYSCLK divided by 16 */
#define  RCC_CFGR_HPRE_DIV64                 ((uint32_t)0x000000C0)        /*!< SYSCLK divided by 64 */
#define  RCC_CFGR_HPRE_DIV128                ((uint32_t)0x000000D0)        /*!< SYSCLK divided by 128 */
#define  RCC_CFGR_HPRE_DIV256                ((uint32_t)0x000000E0)        /*!< SYSCLK divided by 256 */
#define  RCC_CFGR_HPRE_DIV512                ((uint32_t)0x000000F0)        /*!< SYSCLK divided by 512 */
#define  RCC_CFGR_PPRE1                      ((uint32_t)0x00000700)        /*!< APB1 prescaler */
#define  RCC_CFGR_PPRE1_DIV1                 ((uint32_t)0x00000000)        /*!< HCLK not divided */
#define  RCC_CFGR_PPRE1_DIV2                 ((uint32_t)0x00000400)        /*!< HCLK divided by 2 */
#define  RCC_CFGR_PPRE1_DIV4                 ((uint32_t)0x00000500)        /*!< HCLK divided by 4 */
#define  RCC_CFGR_PPRE1_DIV8                 ((uint32_t)0x00000600)        /*!< HCLK divided by 8 */
#define  RCC_CFGR_PPRE1_DIV16                ((uint32_t)0x00000700)        /*!< HCLK divided by 16 */
#define  RCC_CFGR_PPRE2                      ((uint32_t)0x00003800)        /*!< APB2 prescaler */
#define  RCC_CFGR_PPRE2_DIV1                 ((uint32_t)0x00000000)        /*!< HCLK not divided */
#define  RCC_CFGR_PPRE2_DIV2                 ((uint32_t)0x00002000)        /*!< HCLK divided by 2 */
#define  RCC_CFGR_PPRE2_DIV4                 ((uint32_t)0x00002800)        /*!< HCLK divided by 4 */
#define  RCC_CFGR_PPRE2_DIV8                 ((uint32_t)0x00003000)        /*!< HCLK divided by 8 */
#define  RCC_CFGR_PPRE2_DIV16                ((uint32_t)0x00003800)        /*!< HCLK divided by 16 */
#define  RCC_CFGR_ADCPRE                     ((uint32_t)0x0000C000)        /*!< ADC prescaler */
#define  RCC_CFGR_ADCPRE_DIV2                ((uint32_t)0x00000000)        /*!< PCLK2 divided by 2 */
#define  RCC_CFGR_ADCPRE_DIV4                ((uint32_t)0x00004000)        /*!< PCLK2 divided by 4 */
#define  RCC_CFGR_ADCPRE_DIV6                ((uint32_t)0x00008000)        /*!< PCLK2 divided by 6 */
#define  RCC_CFGR_ADCPRE_DIV8                ((uint32_t)0x0000C000)        /*!< PCLK2 divided by 8 */
#define  RCC_CFGR_PLLSRC                     ((uint32_t)0x00010000)        /*!< PLL entry clock source */
#define  RCC_CFGR_PLLSRC_HSI_DIV2            ((uint32_t)0x00000000)        /*!< HSI oscillator clock / 2 selected as PLL input clock */
#define  RCC_CFGR_PLLSRC_HSE                 ((uint32_t)0x00010000)        /*!< HSE oscillator clock selected as PLL input clock */
#define  RCC_CFGR_PLLXTPRE                   ((uint32_t)0x00020000)        /*!< HSE divider for PLL entry */
#define  RCC_CFGR_PLLXTPRE_HSE               ((uint32_t)0x00000000)        /*!< HSE clock not divided */
#define  RCC_CFGR_PLLXTPRE_HSE_DIV2          ((uint32_t)0x00020000)        /*!< HSE clock divided by 2 */
#define  RCC_CFGR_PLLMULL                    ((uint32_t)0x003C0000)        /*!< PLL multiplication factor */
#define  RCC_CFGR_PLLMULL4                   ((uint32_t)0x00080000)        /*!< PLL input clock x 4 */
#define  RCC_CFGR_PLLMULL5                   ((uint32_t)0x000C0000)        /*!< PLL input clock x 5 */
#define  RCC_CFGR_PLLMULL6                   ((uint32_t)0x00100000)        /*!< PLL input clock x 6 */
#define  RCC_CFGR_PLLMULL7                   ((uint32_t)0x00140000)        /*!< PLL input clock x 7 */
#define  RCC_CFGR_PLLMULL8                   ((uint32_t)0x00180000)        /*!< PLL input clock x 8 */
#define  RCC_CFGR_PLLMULL9                   ((uint32_t)0x001C0000)        /*!< PLL input clock x 9 */
#define  RCC_CFGR_PLLMULL10                  ((uint32_t)0x00200000)        /*!< PLL input clock x 10 */
#define  RCC_CFGR_PLLMULL11                  ((uint32_t)0x00240000)        /*!< PLL input clock x 11 */
#define  RCC_CFGR_PLLMULL12                  ((uint32_t)0x00280000)        /*!< PLL input clock x 12 */
#define  RCC_CFGR_PLLMULL13                  ((uint32_t)0x002C0000)        /*!< PLL input clock x 13 */
#define  RCC_CFGR_PLLMULL14                  ((uint32_t)0x00300000)        /*!< PLL input clock x 14 */
#define  RCC_CFGR_PLLMULL15                  ((uint32_t)0x00340000)        /*!< PLL input clock x 15 */
#define  RCC_CFGR_PLLMULL16                  ((uint32_t)0x00380000)        /*!< PLL input clock x 16 */
#define  RCC_CFGR_USBPRE                     ((uint32_t)0x00400000)        /*!< USB prescaler */
#define  RCC_CFGR_MCO                        ((uint32_t)0x07000000)        /*!< Microcontroller clock output */
#define  RCC_CFGR_MCO_NOCLOCK                ((uint32_t)0x00000000)        /*!< No clock */
#define  RCC_CFGR_MCO_SYSCLK                 ((uint32_t)0x04000000)        /*!< System clock (SYSCLK) selected */
#define  RCC_CFGR_MCO_HSI                    ((uint32_t)0x05000000)        /*!< HSI clock selected */
#define  RCC_CFGR_MCO_HSE                    ((uint32_t)0x06000000)        /*!< HSE clock selected */
#define  RCC_CFGR_MCO_PLLCLK_DIV2            ((uint32_t)0x07000000)        /*!< PLL clock divided by 2 selected */

/* --------------------  RCC_CIR Register  -------------------- */
#define  RCC_CIR_LSIRDYF                     ((uint32_t)0x00000001)        /*!< LSI Ready Interrupt flag */
#define  RCC_CIR_LSERDYF                     ((uint32_t)0x00000002)        /*!< LSE Ready Interrupt flag */
#define  RCC_CIR_HSIRDYF                     ((uint32_t)0x00000004)        /*!< HSI Ready Interrupt flag */
#define  RCC_CIR_HSERDYF                     ((uint32_t)0x00000008)        /*!< HSE Ready Interrupt flag */
#define  RCC_CIR_PLLRDYF                     ((uint32_t)0x00000010)        /*!< PLL Ready Interrupt flag */
#define  RCC_CIR_CSSF                        ((uint32_t)0x00000080)        /*!< Clock Security System Interrupt flag */
#define  RCC_CIR_LSIRDYIE                    ((uint32_t)0x00000100)        /*!< LSI Ready Interrupt Enable */
#define  RCC_CIR_LSERDYIE                    ((uint32_t)0x00000200)        /*!< LSE Ready Interrupt Enable */
#define  RCC_CIR_HSIRDYIE                    ((uint32_t)0x00000400)        /*!< HSI Ready Interrupt Enable */
#define  RCC_CIR_HSERDYIE                    ((uint32_t)0x00000800)        /*!< HSE Ready Interrupt Enable */
#define  RCC_CIR_PLLRDYIE                    ((uint32_t)0x00001000)        /*!< PLL Ready Interrupt Enable */
#define  RCC_CIR_LSIRDYC                     ((uint32_t)0x00010000)        /*!< LSI Ready Interrupt Clear */
#define  RCC_CIR_LSERDYC                     ((uint32_t)0x00020000)        /*!< LSE Ready Interrupt Clear */
#define  RCC_CIR_HSIRDYC                     ((uint32_t)0x00040000)        /*!< HSI Ready Interrupt Clear */
#define  RCC_CIR_HSERDYC                     ((uint32_t)0x00080000)        /*!< HSE Ready Interrupt Clear */
#define  RCC_CIR_PLLRDYC                     ((uint32_t)0x00100000)        /*!< PLL Ready Interrupt Clear */
#define  RCC_CIR_CSSC                        ((uint32_t)0x00800000)        /*!< Clock Security System Interrupt Clear */

/* --------------------  RCC_APB2RSTR Register  -------------------- */
#define  RCC_APB2RSTR_AFIORST                ((uint32_t)0x00000001)        /*!< Alternate Function I/O reset */
#define  RCC_APB2RSTR_IOPARST                ((uint32_t)0x00000004)        /*!< IO port A reset */
#define  RCC_APB2RSTR_IOPBRST                ((uint32_t)0x00000008)        /*!< IO port B reset */
#define  RCC_APB2RSTR_IOPCRST                ((uint32_t)0x00000010)        /*!< IO port C reset */
#define  RCC_APB2RSTR_IOPDRST                ((uint32_t)0x00000020)        /*!< IO port D reset */
#define  RCC_APB2RSTR_IOPERST                ((uint32_t)0x00000040)        /*!< IO port E reset */
#define  RCC_APB2RSTR_IOPFRST                ((uint32_t)0x00000080)        /*!< IO port F reset */
#define  RCC_APB2RSTR_IOPGRST                ((uint32_t)0x00000100)        /*!< IO port G reset */
#define  RCC_APB2RSTR_ADC1RST                ((uint32_t)0x00000200)        /*!< ADC 1 interface reset */
#define  RCC_APB2RSTR_ADC2RST                ((uint32_t)0x00000400)        /*!< ADC 2 interface reset */
#define  RCC_APB2RSTR_TIM1RST                ((uint32_t)0x00000800)        /*!< TIM1 Timer reset */
#define  RCC_APB2RSTR_SPI1RST                ((uint32_t)0x00001000)        /*!< SPI 1 reset */
#define  RCC_APB2RSTR_TIM8RST                ((uint32_t)0x00002000)        /*!< TIM8 Timer reset */
#define  RCC_APB2RSTR_USART1RST              ((uint32_t)0x00004000)        /*!< USART1 reset */
#define  RCC_APB2RSTR_ADC3RST                ((uint32_t)0x00008000)        /*!< ADC3 interface reset */

/* --------------------  RCC_APB1RSTR Register  -------------------- */
#define  RCC_APB1RSTR_TIM2RST                ((uint32_t)0x00000001)        /*!< Timer 2 reset */
#define  RCC_APB1RSTR_TIM3RST                ((uint32_t)0x00000002)        /*!< Timer 3 reset */
#define  RCC_APB1RSTR_TIM4RST                ((uint32_t)0x00000004)        /*!< Timer 4 reset */
#define  RCC_APB1RSTR_WWDGRST                ((uint32_t)0x00000800)        /*!< Window Watchdog reset */
#define  RCC_APB1RSTR_SPI2RST                ((uint32_t)0x00004000)        /*!< SPI 2 reset */
#define  RCC_APB1RSTR_SPI3RST                ((uint32_t)0x00008000)        /*!< SPI 3 reset */
#define  RCC_APB1RSTR_USART2RST              ((uint32_t)0x00020000)        /*!< USART 2 reset */
#define  RCC_APB1RSTR_USART3RST              ((uint32_t)0x00040000)        /*!< USART 3 reset */
#define  RCC_APB1RSTR_UART4RST               ((uint32_t)0x00080000)        /*!< UART 4 reset */
#define  RCC_APB1RSTR_UART5RST               ((uint32_t)0x00100000)        /*!< UART 5 reset */
#define  RCC_APB1RSTR_I2C1RST                ((uint32_t)0x00200000)        /*!< I2C1 reset */
#define  RCC_APB1RSTR_I2C2RST                ((uint32_t)0x00400000)        /*!< I2C2 reset */
#define  RCC_APB1RSTR_USBRST                 ((uint32_t)0x00800000)        /*!< USB reset */
#define  RCC_APB1RSTR_CAN1RST                ((uint32_t)0x02000000)        /*!< CAN1 reset */
#define  RCC_APB1RSTR_CAN2RST                ((uint32_t)0x04000000)        /*!< CAN2 reset */
#define  RCC_APB1RSTR_BKPRST                 ((uint32_t)0x08000000)        /*!< Backup interface reset */
#define  RCC_APB1RSTR_PWRRST                 ((uint32_t)0x10000000)        /*!< Power interface reset */
#define  RCC_APB1RSTR_DACRST                 ((uint32_t)0x20000000)        /*!< DAC interface reset */

/* --------------------  RCC_AHBENR Register  -------------------- */
#define  RCC_AHBENR_DMA1EN                   ((uint32_t)0x00000001)        /*!< DMA1 clock enable */
#define  RCC_AHBENR_DMA2EN                   ((uint32_t)0x00000002)        /*!< DMA2 clock enable */
#define  RCC_AHBENR_SRAMEN                   ((uint32_t)0x00000004)        /*!< SRAM interface clock enable */
#define  RCC_AHBENR_FLITFEN                  ((uint32_t)0x00000010)        /*!< FLITF clock enable */
#define  RCC_AHBENR_CRCEN                    ((uint32_t)0x00000040)        /*!< CRC clock enable */

/* --------------------  RCC_APB2ENR Register  -------------------- */
#define  RCC_APB2ENR_AFIOEN                  ((uint32_t)0x00000001)        /*!< Alternate Function I/O clock enable */
#define  RCC_APB2ENR_IOPAEN                  ((uint32_t)0x00000004)        /*!< I/O port A clock enable */
#define  RCC_APB2ENR_IOPBEN                  ((uint32_t)0x00000008)        /*!< I/O port B clock enable */
#define  RCC_APB2ENR_IOPCEN                  ((uint32_t)0x00000010)        /*!< I/O port C clock enable */
#define  RCC_APB2ENR_IOPDEN                  ((uint32_t)0x00000020)        /*!< I/O port D clock enable */
#define  RCC_APB2ENR_IOPEEN                  ((uint32_t)0x00000040)        /*!< I/O port E clock enable */
#define  RCC_APB2ENR_IOPFEN                  ((uint32_t)0x00000080)        /*!< I/O port F clock enable */
#define  RCC_APB2ENR_IOPGEN                  ((uint32_t)0x00000100)        /*!< I/O port G clock enable */
#define  RCC_APB2ENR_ADC1EN                  ((uint32_t)0x00000200)        /*!< ADC1 clock enable */
#define  RCC_APB2ENR_ADC2EN                  ((uint32_t)0x00000400)        /*!< ADC2 clock enable */
#define  RCC_APB2ENR_TIM1EN                  ((uint32_t)0x00000800)        /*!< TIM1 clock enable */
#define  RCC_APB2ENR_SPI1EN                  ((uint32_t)0x00001000)        /*!< SPI1 clock enable */
#define  RCC_APB2ENR_TIM8EN                  ((uint32_t)0x00002000)        /*!< TIM8 clock enable */
#define  RCC_APB2ENR_USART1EN                ((uint32_t)0x00004000)        /*!< USART1 clock enable */
#define  RCC_APB2ENR_ADC3EN                  ((uint32_t)0x00008000)        /*!< ADC3 clock enable */

/* --------------------  RCC_APB1ENR Register  -------------------- */
#define  RCC_APB1ENR_TIM2EN                  ((uint32_t)0x00000001)        /*!< Timer 2 clock enable */
#define  RCC_APB1ENR_TIM3EN                  ((uint32_t)0x00000002)        /*!< Timer 3 clock enable */
#define  RCC_APB1ENR_TIM4EN                  ((uint32_t)0x00000004)        /*!< Timer 4 clock enable */
#define  RCC_APB1ENR_WWDGEN                  ((uint32_t)0x00000800)        /*!< Window Watchdog clock enable */
#define  RCC_APB1ENR_SPI2EN                  ((uint32_t)0x00004000)        /*!< SPI 2 clock enable */
#define  RCC_APB1ENR_SPI3EN                  ((uint32_t)0x00008000)        /*!< SPI 3 clock enable */
#define  RCC_APB1ENR_USART2EN                ((uint32_t)0x00020000)        /*!< USART 2 clock enable */
#define  RCC_APB1ENR_USART3EN                ((uint32_t)0x00040000)        /*!< USART 3 clock enable */
#define  RCC_APB1ENR_UART4EN                 ((uint32_t)0x00080000)        /*!< UART 4 clock enable */
#define  RCC_APB1ENR_UART5EN                 ((uint32_t)0x00100000)        /*!< UART 5 clock enable */
#define  RCC_APB1ENR_I2C1EN                  ((uint32_t)0x00200000)        /*!< I2C1 clock enable */
#define  RCC_APB1ENR_I2C2EN                  ((uint32_t)0x00400000)        /*!< I2C2 clock enable */
#define  RCC_APB1ENR_USBEN                   ((uint32_t)0x00800000)        /*!< USB clock enable */
#define  RCC_APB1ENR_CAN1EN                  ((uint32_t)0x02000000)        /*!< CAN1 clock enable */
#define  RCC_APB1ENR_CAN2EN                  ((uint32_t)0x04000000)        /*!< CAN2 clock enable */
#define  RCC_APB1ENR_BKPEN                   ((uint32_t)0x08000000)        /*!< Backup interface clock enable */
#define  RCC_APB1ENR_PWREN                   ((uint32_t)0x10000000)        /*!< Power interface clock enable */
#define  RCC_APB1ENR_DACEN                   ((uint32_t)0x20000000)        /*!< DAC interface clock enable */

/* --------------------  RCC_BDCR Register  -------------------- */
#define  RCC_BDCR_LSEON                      ((uint32_t)0x00000001)        /*!< External Low Speed oscillator enable */
#define  RCC_BDCR_LSERDY                     ((uint32_t)0x00000002)        /*!< External Low Speed oscillator Ready */
#define  RCC_BDCR_LSEBYP                     ((uint32_t)0x00000004)        /*!< External Low Speed oscillator Bypass */
#define  RCC_BDCR_RTCSEL                     ((uint32_t)0x00000300)        /*!< RTC Clock Source Selection */
#define  RCC_BDCR_RTCSEL_NOCLOCK             ((uint32_t)0x00000000)        /*!< No clock */
#define  RCC_BDCR_RTCSEL_LSE                 ((uint32_t)0x00000100)        /*!< LSE oscillator clock used as RTC clock */
#define  RCC_BDCR_RTCSEL_LSI                 ((uint32_t)0x00000200)        /*!< LSI oscillator clock used as RTC clock */
#define  RCC_BDCR_RTCSEL_HSE                 ((uint32_t)0x00000300)        /*!< HSE oscillator clock divided by 128 used as RTC clock */
#define  RCC_BDCR_RTCEN                      ((uint32_t)0x00008000)        /*!< RTC clock enable */
#define  RCC_BDCR_BDRST                      ((uint32_t)0x00010000)        /*!< Backup domain software reset */

/* --------------------  RCC_CSR Register  -------------------- */
#define  RCC_CSR_LSION                       ((uint32_t)0x00000001)        /*!< Internal Low Speed oscillator enable */
#define  RCC_CSR_LSIRDY                      ((uint32_t)0x00000002)        /*!< Internal Low Speed oscillator Ready */
#define  RCC_CSR_RMVF                        ((uint32_t)0x01000000)        /*!< Remove reset flag */
#define  RCC_CSR_PINRSTF                     ((uint32_t)0x04000000)        /*!< PIN reset flag */
#define  RCC_CSR_PORRSTF                     ((uint32_t)0x08000000)        /*!< POR/PDR reset flag */
#define  RCC_CSR_SFTRSTF                     ((uint32_t)0x10000000)        /*!< Software Reset flag */
#define  RCC_CSR_IWDGRSTF                    ((uint32_t)0x20000000)        /*!< Independent Watchdog reset flag */
#define  RCC_CSR_WWDGRSTF                    ((uint32_t)0x40000000)        /*!< Window watchdog reset flag */
#define  RCC_CSR_LPWRRSTF                    ((uint32_t)0x80000000)        /*!< Low-Power reset flag */

  /* ========================================================================= */
  /*                            GPIO Registers                                */
  /* ========================================================================= */

/* ----------- GPIO Port Configuration Low Register (CRL) ----------- */
#define  GPIO_CRL_CNF                         ((uint32_t)0xCCCCCCCC)       /*!< Port x configuration bits */
#define  GPIO_CRL_MODE                        ((uint32_t)0x33333333)       /*!< Port x mode bits */

/* GPIO_CRL_CNF (per pin) */
#define  GPIO_CRL_CNF0_0                      ((uint32_t)0x00000004)        /*!< Pin 0 configuration bit 0 */
#define  GPIO_CRL_CNF0_1                      ((uint32_t)0x00000008)        /*!< Pin 0 configuration bit 1 */
#define  GPIO_CRL_CNF1_0                      ((uint32_t)0x00000040)        /*!< Pin 1 configuration bit 0 */
#define  GPIO_CRL_CNF1_1                      ((uint32_t)0x00000080)        /*!< Pin 1 configuration bit 1 */
#define  GPIO_CRL_CNF2_0                      ((uint32_t)0x00000400)        /*!< Pin 2 configuration bit 0 */
#define  GPIO_CRL_CNF2_1                      ((uint32_t)0x00000800)        /*!< Pin 2 configuration bit 1 */
#define  GPIO_CRL_CNF3_0                      ((uint32_t)0x00004000)        /*!< Pin 3 configuration bit 0 */
#define  GPIO_CRL_CNF3_1                      ((uint32_t)0x00008000)        /*!< Pin 3 configuration bit 1 */
#define  GPIO_CRL_CNF4_0                      ((uint32_t)0x00040000)        /*!< Pin 4 configuration bit 0 */
#define  GPIO_CRL_CNF4_1                      ((uint32_t)0x00080000)        /*!< Pin 4 configuration bit 1 */
#define  GPIO_CRL_CNF5_0                      ((uint32_t)0x00400000)        /*!< Pin 5 configuration bit 0 */
#define  GPIO_CRL_CNF5_1                      ((uint32_t)0x00800000)        /*!< Pin 5 configuration bit 1 */
#define  GPIO_CRL_CNF6_0                      ((uint32_t)0x04000000)        /*!< Pin 6 configuration bit 0 */
#define  GPIO_CRL_CNF6_1                      ((uint32_t)0x08000000)        /*!< Pin 6 configuration bit 1 */
#define  GPIO_CRL_CNF7_0                      ((uint32_t)0x40000000)        /*!< Pin 7 configuration bit 0 */
#define  GPIO_CRL_CNF7_1                      ((uint32_t)0x80000000)        /*!< Pin 7 configuration bit 1 */

/* GPIO_CRL_MODE (per pin) */
#define  GPIO_CRL_MODE0_0                     ((uint32_t)0x00000001)        /*!< Pin 0 mode bit 0 */
#define  GPIO_CRL_MODE0_1                     ((uint32_t)0x00000002)        /*!< Pin 0 mode bit 1 */
#define  GPIO_CRL_MODE1_0                     ((uint32_t)0x00000010)        /*!< Pin 1 mode bit 0 */
#define  GPIO_CRL_MODE1_1                     ((uint32_t)0x00000020)        /*!< Pin 1 mode bit 1 */
#define  GPIO_CRL_MODE2_0                     ((uint32_t)0x00000100)        /*!< Pin 2 mode bit 0 */
#define  GPIO_CRL_MODE2_1                     ((uint32_t)0x00000200)        /*!< Pin 2 mode bit 1 */
#define  GPIO_CRL_MODE3_0                     ((uint32_t)0x00001000)        /*!< Pin 3 mode bit 0 */
#define  GPIO_CRL_MODE3_1                     ((uint32_t)0x00002000)        /*!< Pin 3 mode bit 1 */
#define  GPIO_CRL_MODE4_0                     ((uint32_t)0x00010000)        /*!< Pin 4 mode bit 0 */
#define  GPIO_CRL_MODE4_1                     ((uint32_t)0x00020000)        /*!< Pin 4 mode bit 1 */
#define  GPIO_CRL_MODE5_0                     ((uint32_t)0x00100000)        /*!< Pin 5 mode bit 0 */
#define  GPIO_CRL_MODE5_1                     ((uint32_t)0x00200000)        /*!< Pin 5 mode bit 1 */
#define  GPIO_CRL_MODE6_0                     ((uint32_t)0x01000000)        /*!< Pin 6 mode bit 0 */
#define  GPIO_CRL_MODE6_1                     ((uint32_t)0x02000000)        /*!< Pin 6 mode bit 1 */
#define  GPIO_CRL_MODE7_0                     ((uint32_t)0x10000000)        /*!< Pin 7 mode bit 0 */
#define  GPIO_CRL_MODE7_1                     ((uint32_t)0x20000000)        /*!< Pin 7 mode bit 1 */

/* ----------- GPIO Port Configuration High Register (CRH) ----------- */
#define  GPIO_CRH_CNF                         ((uint32_t)0xCCCCCCCC)       /*!< Port x configuration bits */
#define  GPIO_CRH_MODE                        ((uint32_t)0x33333333)       /*!< Port x mode bits */

/* GPIO_CRH_CNF (per pin) */
#define  GPIO_CRH_CNF8_0                      ((uint32_t)0x00000004)        /*!< Pin 8 configuration bit 0 */
#define  GPIO_CRH_CNF8_1                      ((uint32_t)0x00000008)        /*!< Pin 8 configuration bit 1 */
#define  GPIO_CRH_CNF9_0                      ((uint32_t)0x00000040)        /*!< Pin 9 configuration bit 0 */
#define  GPIO_CRH_CNF9_1                      ((uint32_t)0x00000080)        /*!< Pin 9 configuration bit 1 */
#define  GPIO_CRH_CNF10_0                     ((uint32_t)0x00000400)        /*!< Pin 10 configuration bit 0 */
#define  GPIO_CRH_CNF10_1                     ((uint32_t)0x00000800)        /*!< Pin 10 configuration bit 1 */
#define  GPIO_CRH_CNF11_0                     ((uint32_t)0x00004000)        /*!< Pin 11 configuration bit 0 */
#define  GPIO_CRH_CNF11_1                     ((uint32_t)0x00008000)        /*!< Pin 11 configuration bit 1 */
#define  GPIO_CRH_CNF12_0                     ((uint32_t)0x00040000)        /*!< Pin 12 configuration bit 0 */
#define  GPIO_CRH_CNF12_1                     ((uint32_t)0x00080000)        /*!< Pin 12 configuration bit 1 */
#define  GPIO_CRH_CNF13_0                     ((uint32_t)0x00400000)        /*!< Pin 13 configuration bit 0 */
#define  GPIO_CRH_CNF13_1                     ((uint32_t)0x00800000)        /*!< Pin 13 configuration bit 1 */
#define  GPIO_CRH_CNF14_0                     ((uint32_t)0x04000000)        /*!< Pin 14 configuration bit 0 */
#define  GPIO_CRH_CNF14_1                     ((uint32_t)0x08000000)        /*!< Pin 14 configuration bit 1 */
#define  GPIO_CRH_CNF15_0                     ((uint32_t)0x40000000)        /*!< Pin 15 configuration bit 0 */
#define  GPIO_CRH_CNF15_1                     ((uint32_t)0x80000000)        /*!< Pin 15 configuration bit 1 */

/* GPIO_CRH_MODE (per pin) */
#define  GPIO_CRH_MODE8_0                     ((uint32_t)0x00000001)        /*!< Pin 8 mode bit 0 */
#define  GPIO_CRH_MODE8_1                     ((uint32_t)0x00000002)        /*!< Pin 8 mode bit 1 */
#define  GPIO_CRH_MODE9_0                     ((uint32_t)0x00000010)        /*!< Pin 9 mode bit 0 */
#define  GPIO_CRH_MODE9_1                     ((uint32_t)0x00000020)        /*!< Pin 9 mode bit 1 */
#define  GPIO_CRH_MODE10_0                    ((uint32_t)0x00000100)        /*!< Pin 10 mode bit 0 */
#define  GPIO_CRH_MODE10_1                    ((uint32_t)0x00000200)        /*!< Pin 10 mode bit 1 */
#define  GPIO_CRH_MODE11_0                    ((uint32_t)0x00001000)        /*!< Pin 11 mode bit 0 */
#define  GPIO_CRH_MODE11_1                    ((uint32_t)0x00002000)        /*!< Pin 11 mode bit 1 */
#define  GPIO_CRH_MODE12_0                    ((uint32_t)0x00010000)        /*!< Pin 12 mode bit 0 */
#define  GPIO_CRH_MODE12_1                    ((uint32_t)0x00020000)        /*!< Pin 12 mode bit 1 */
#define  GPIO_CRH_MODE13_0                    ((uint32_t)0x00100000)        /*!< Pin 13 mode bit 0 */
#define  GPIO_CRH_MODE13_1                    ((uint32_t)0x00200000)        /*!< Pin 13 mode bit 1 */
#define  GPIO_CRH_MODE14_0                    ((uint32_t)0x01000000)        /*!< Pin 14 mode bit 0 */
#define  GPIO_CRH_MODE14_1                    ((uint32_t)0x02000000)        /*!< Pin 14 mode bit 1 */
#define  GPIO_CRH_MODE15_0                    ((uint32_t)0x10000000)        /*!< Pin 15 mode bit 0 */
#define  GPIO_CRH_MODE15_1                    ((uint32_t)0x20000000)        /*!< Pin 15 mode bit 1 */

/* ----------- GPIO Port Input Data Register (IDR) ----------- */
#define  GPIO_IDR_IDR0                        ((uint32_t)0x00000001)        /*!< Port input data bit 0 */
#define  GPIO_IDR_IDR1                        ((uint32_t)0x00000002)        /*!< Port input data bit 1 */
#define  GPIO_IDR_IDR2                        ((uint32_t)0x00000004)        /*!< Port input data bit 2 */
#define  GPIO_IDR_IDR3                        ((uint32_t)0x00000008)        /*!< Port input data bit 3 */
#define  GPIO_IDR_IDR4                        ((uint32_t)0x00000010)        /*!< Port input data bit 4 */
#define  GPIO_IDR_IDR5                        ((uint32_t)0x00000020)        /*!< Port input data bit 5 */
#define  GPIO_IDR_IDR6                        ((uint32_t)0x00000040)        /*!< Port input data bit 6 */
#define  GPIO_IDR_IDR7                        ((uint32_t)0x00000080)        /*!< Port input data bit 7 */
#define  GPIO_IDR_IDR8                        ((uint32_t)0x00000100)        /*!< Port input data bit 8 */
#define  GPIO_IDR_IDR9                        ((uint32_t)0x00000200)        /*!< Port input data bit 9 */
#define  GPIO_IDR_IDR10                       ((uint32_t)0x00000400)        /*!< Port input data bit 10 */
#define  GPIO_IDR_IDR11                       ((uint32_t)0x00000800)        /*!< Port input data bit 11 */
#define  GPIO_IDR_IDR12                       ((uint32_t)0x00001000)        /*!< Port input data bit 12 */
#define  GPIO_IDR_IDR13                       ((uint32_t)0x00002000)        /*!< Port input data bit 13 */
#define  GPIO_IDR_IDR14                       ((uint32_t)0x00004000)        /*!< Port input data bit 14 */
#define  GPIO_IDR_IDR15                       ((uint32_t)0x00008000)        /*!< Port input data bit 15 */

/* ----------- GPIO Port Output Data Register (ODR) ----------- */
#define  GPIO_ODR_ODR0                        ((uint32_t)0x00000001)        /*!< Port output data bit 0 */
#define  GPIO_ODR_ODR1                        ((uint32_t)0x00000002)        /*!< Port output data bit 1 */
#define  GPIO_ODR_ODR2                        ((uint32_t)0x00000004)        /*!< Port output data bit 2 */
#define  GPIO_ODR_ODR3                        ((uint32_t)0x00000008)        /*!< Port output data bit 3 */
#define  GPIO_ODR_ODR4                        ((uint32_t)0x00000010)        /*!< Port output data bit 4 */
#define  GPIO_ODR_ODR5                        ((uint32_t)0x00000020)        /*!< Port output data bit 5 */
#define  GPIO_ODR_ODR6                        ((uint32_t)0x00000040)        /*!< Port output data bit 6 */
#define  GPIO_ODR_ODR7                        ((uint32_t)0x00000080)        /*!< Port output data bit 7 */
#define  GPIO_ODR_ODR8                        ((uint32_t)0x00000100)        /*!< Port output data bit 8 */
#define  GPIO_ODR_ODR9                        ((uint32_t)0x00000200)        /*!< Port output data bit 9 */
#define  GPIO_ODR_ODR10                       ((uint32_t)0x00000400)        /*!< Port output data bit 10 */
#define  GPIO_ODR_ODR11                       ((uint32_t)0x00000800)        /*!< Port output data bit 11 */
#define  GPIO_ODR_ODR12                       ((uint32_t)0x00001000)        /*!< Port output data bit 12 */
#define  GPIO_ODR_ODR13                       ((uint32_t)0x00002000)        /*!< Port output data bit 13 */
#define  GPIO_ODR_ODR14                       ((uint32_t)0x00004000)        /*!< Port output data bit 14 */
#define  GPIO_ODR_ODR15                       ((uint32_t)0x00008000)        /*!< Port output data bit 15 */

/* ----------- GPIO Port Bit Set/Reset Register (BSRR) ----------- */
#define  GPIO_BSRR_BS0                        ((uint32_t)0x00000001)        /*!< Port x Set bit 0 */
#define  GPIO_BSRR_BS1                        ((uint32_t)0x00000002)        /*!< Port x Set bit 1 */
#define  GPIO_BSRR_BS2                        ((uint32_t)0x00000004)        /*!< Port x Set bit 2 */
#define  GPIO_BSRR_BS3                        ((uint32_t)0x00000008)        /*!< Port x Set bit 3 */
#define  GPIO_BSRR_BS4                        ((uint32_t)0x00000010)        /*!< Port x Set bit 4 */
#define  GPIO_BSRR_BS5                        ((uint32_t)0x00000020)        /*!< Port x Set bit 5 */
#define  GPIO_BSRR_BS6                        ((uint32_t)0x00000040)        /*!< Port x Set bit 6 */
#define  GPIO_BSRR_BS7                        ((uint32_t)0x00000080)        /*!< Port x Set bit 7 */
#define  GPIO_BSRR_BS8                        ((uint32_t)0x00000100)        /*!< Port x Set bit 8 */
#define  GPIO_BSRR_BS9                        ((uint32_t)0x00000200)        /*!< Port x Set bit 9 */
#define  GPIO_BSRR_BS10                       ((uint32_t)0x00000400)        /*!< Port x Set bit 10 */
#define  GPIO_BSRR_BS11                       ((uint32_t)0x00000800)        /*!< Port x Set bit 11 */
#define  GPIO_BSRR_BS12                       ((uint32_t)0x00001000)        /*!< Port x Set bit 12 */
#define  GPIO_BSRR_BS13                       ((uint32_t)0x00002000)        /*!< Port x Set bit 13 */
#define  GPIO_BSRR_BS14                       ((uint32_t)0x00004000)        /*!< Port x Set bit 14 */
#define  GPIO_BSRR_BS15                       ((uint32_t)0x00008000)        /*!< Port x Set bit 15 */
#define  GPIO_BSRR_BR0                        ((uint32_t)0x00010000)        /*!< Port x Reset bit 0 */
#define  GPIO_BSRR_BR1                        ((uint32_t)0x00020000)        /*!< Port x Reset bit 1 */
#define  GPIO_BSRR_BR2                        ((uint32_t)0x00040000)        /*!< Port x Reset bit 2 */
#define  GPIO_BSRR_BR3                        ((uint32_t)0x00080000)        /*!< Port x Reset bit 3 */
#define  GPIO_BSRR_BR4                        ((uint32_t)0x00100000)        /*!< Port x Reset bit 4 */
#define  GPIO_BSRR_BR5                        ((uint32_t)0x00200000)        /*!< Port x Reset bit 5 */
#define  GPIO_BSRR_BR6                        ((uint32_t)0x00400000)        /*!< Port x Reset bit 6 */
#define  GPIO_BSRR_BR7                        ((uint32_t)0x00800000)        /*!< Port x Reset bit 7 */
#define  GPIO_BSRR_BR8                        ((uint32_t)0x01000000)        /*!< Port x Reset bit 8 */
#define  GPIO_BSRR_BR9                        ((uint32_t)0x02000000)        /*!< Port x Reset bit 9 */
#define  GPIO_BSRR_BR10                       ((uint32_t)0x04000000)        /*!< Port x Reset bit 10 */
#define  GPIO_BSRR_BR11                       ((uint32_t)0x08000000)        /*!< Port x Reset bit 11 */
#define  GPIO_BSRR_BR12                       ((uint32_t)0x10000000)        /*!< Port x Reset bit 12 */
#define  GPIO_BSRR_BR13                       ((uint32_t)0x20000000)        /*!< Port x Reset bit 13 */
#define  GPIO_BSRR_BR14                       ((uint32_t)0x40000000)        /*!< Port x Reset bit 14 */
#define  GPIO_BSRR_BR15                       ((uint32_t)0x80000000)        /*!< Port x Reset bit 15 */

/* ----------- GPIO Port Bit Reset Register (BRR) ----------- */
#define  GPIO_BRR_BR0                         ((uint32_t)0x00000001)        /*!< Port x Reset bit 0 */
#define  GPIO_BRR_BR1                         ((uint32_t)0x00000002)        /*!< Port x Reset bit 1 */
#define  GPIO_BRR_BR2                         ((uint32_t)0x00000004)        /*!< Port x Reset bit 2 */
#define  GPIO_BRR_BR3                         ((uint32_t)0x00000008)        /*!< Port x Reset bit 3 */
#define  GPIO_BRR_BR4                         ((uint32_t)0x00000010)        /*!< Port x Reset bit 4 */
#define  GPIO_BRR_BR5                         ((uint32_t)0x00000020)        /*!< Port x Reset bit 5 */
#define  GPIO_BRR_BR6                         ((uint32_t)0x00000040)        /*!< Port x Reset bit 6 */
#define  GPIO_BRR_BR7                         ((uint32_t)0x00000080)        /*!< Port x Reset bit 7 */
#define  GPIO_BRR_BR8                         ((uint32_t)0x00000100)        /*!< Port x Reset bit 8 */
#define  GPIO_BRR_BR9                         ((uint32_t)0x00000200)        /*!< Port x Reset bit 9 */
#define  GPIO_BRR_BR10                        ((uint32_t)0x00000400)        /*!< Port x Reset bit 10 */
#define  GPIO_BRR_BR11                        ((uint32_t)0x00000800)        /*!< Port x Reset bit 11 */
#define  GPIO_BRR_BR12                        ((uint32_t)0x00001000)        /*!< Port x Reset bit 12 */
#define  GPIO_BRR_BR13                        ((uint32_t)0x00002000)        /*!< Port x Reset bit 13 */
#define  GPIO_BRR_BR14                        ((uint32_t)0x00004000)        /*!< Port x Reset bit 14 */
#define  GPIO_BRR_BR15                        ((uint32_t)0x00008000)        /*!< Port x Reset bit 15 */

/* ----------- GPIO Port Configuration Lock Register (LCKR) ----------- */
#define  GPIO_LCKR_LCK0                       ((uint32_t)0x00000001)        /*!< Port x Lock bit 0 */
#define  GPIO_LCKR_LCK1                       ((uint32_t)0x00000002)        /*!< Port x Lock bit 1 */
#define  GPIO_LCKR_LCK2                       ((uint32_t)0x00000004)        /*!< Port x Lock bit 2 */
#define  GPIO_LCKR_LCK3                       ((uint32_t)0x00000008)        /*!< Port x Lock bit 3 */
#define  GPIO_LCKR_LCK4                       ((uint32_t)0x00000010)        /*!< Port x Lock bit 4 */
#define  GPIO_LCKR_LCK5                       ((uint32_t)0x00000020)        /*!< Port x Lock bit 5 */
#define  GPIO_LCKR_LCK6                       ((uint32_t)0x00000040)        /*!< Port x Lock bit 6 */
#define  GPIO_LCKR_LCK7                       ((uint32_t)0x00000080)        /*!< Port x Lock bit 7 */
#define  GPIO_LCKR_LCK8                       ((uint32_t)0x00000100)        /*!< Port x Lock bit 8 */
#define  GPIO_LCKR_LCK9                       ((uint32_t)0x00000200)        /*!< Port x Lock bit 9 */
#define  GPIO_LCKR_LCK10                      ((uint32_t)0x00000400)        /*!< Port x Lock bit 10 */
#define  GPIO_LCKR_LCK11                      ((uint32_t)0x00000800)        /*!< Port x Lock bit 11 */
#define  GPIO_LCKR_LCK12                      ((uint32_t)0x00001000)        /*!< Port x Lock bit 12 */
#define  GPIO_LCKR_LCK13                      ((uint32_t)0x00002000)        /*!< Port x Lock bit 13 */
#define  GPIO_LCKR_LCK14                      ((uint32_t)0x00004000)        /*!< Port x Lock bit 14 */
#define  GPIO_LCKR_LCK15                      ((uint32_t)0x00008000)        /*!< Port x Lock bit 15 */
#define  GPIO_LCKR_LCKK                       ((uint32_t)0x00010000)        /*!< Lock key */

  /* ========================================================================= */
  /*                           USART Registers                                 */
  /* ========================================================================= */

/* ---------------------- USART Status Register (SR) ---------------------- */
#define  USART_SR_PE                          ((uint16_t)0x0001)            /*!< Parity Error */
#define  USART_SR_FE                          ((uint16_t)0x0002)            /*!< Framing Error */
#define  USART_SR_NE                          ((uint16_t)0x0004)            /*!< Noise Error flag */
#define  USART_SR_ORE                         ((uint16_t)0x0008)            /*!< OverRun Error */
#define  USART_SR_IDLE                        ((uint16_t)0x0010)            /*!< IDLE line detected */
#define  USART_SR_RXNE                        ((uint16_t)0x0020)            /*!< Read Data Register Not Empty */
#define  USART_SR_TC                          ((uint16_t)0x0040)            /*!< Transmission Complete */
#define  USART_SR_TXE                         ((uint16_t)0x0080)            /*!< Transmit Data Register Empty */
#define  USART_SR_LBD                         ((uint16_t)0x0100)            /*!< LIN Break Detection Flag */
#define  USART_SR_CTS                         ((uint16_t)0x0200)            /*!< CTS Flag */

/* ---------------------- USART Data Register (DR) ---------------------- */
#define  USART_DR_DR                          ((uint16_t)0x01FF)            /*!< Data value */

/* ---------------------- USART Baud Rate Register (BRR) ---------------------- */
#define  USART_BRR_DIV_Fraction               ((uint16_t)0x000F)            /*!< Fraction of USARTDIV */
#define  USART_BRR_DIV_Mantissa               ((uint16_t)0xFFF0)            /*!< Mantissa of USARTDIV */

/* ---------------------- USART Control Register 1 (CR1) ---------------------- */
#define  USART_CR1_SBK                        ((uint16_t)0x0001)            /*!< Send Break */
#define  USART_CR1_RWU                        ((uint16_t)0x0002)            /*!< Receiver wakeup */
#define  USART_CR1_RE                         ((uint16_t)0x0004)            /*!< Receiver Enable */
#define  USART_CR1_TE                         ((uint16_t)0x0008)            /*!< Transmitter Enable */
#define  USART_CR1_IDLEIE                     ((uint16_t)0x0010)            /*!< IDLE Interrupt Enable */
#define  USART_CR1_RXNEIE                     ((uint16_t)0x0020)            /*!< RXNE Interrupt Enable */
#define  USART_CR1_TCIE                       ((uint16_t)0x0040)            /*!< Transmission Complete Interrupt Enable */
#define  USART_CR1_TXEIE                      ((uint16_t)0x0080)            /*!< TXE Interrupt Enable */
#define  USART_CR1_PEIE                       ((uint16_t)0x0100)            /*!< PE Interrupt Enable */
#define  USART_CR1_PS                         ((uint16_t)0x0200)            /*!< Parity Selection */
#define  USART_CR1_PCE                        ((uint16_t)0x0400)            /*!< Parity Control Enable */
#define  USART_CR1_WAKE                       ((uint16_t)0x0800)            /*!< Wakeup method */
#define  USART_CR1_M                          ((uint16_t)0x1000)            /*!< Word length */
#define  USART_CR1_UE                         ((uint16_t)0x2000)            /*!< USART Enable */

/* ---------------------- USART Control Register 2 (CR2) ---------------------- */
#define  USART_CR2_ADD                        ((uint16_t)0x000F)            /*!< Address of the USART node */
#define  USART_CR2_LBDL                       ((uint16_t)0x0020)            /*!< LIN Break Detection Length */
#define  USART_CR2_LBDIE                      ((uint16_t)0x0040)            /*!< LIN Break Detection Interrupt Enable */
#define  USART_CR2_LBCL                       ((uint16_t)0x0100)            /*!< Last Bit Clock pulse */
#define  USART_CR2_CPHA                       ((uint16_t)0x0200)            /*!< Clock Phase */
#define  USART_CR2_CPOL                       ((uint16_t)0x0400)            /*!< Clock Polarity */
#define  USART_CR2_CLKEN                      ((uint16_t)0x0800)            /*!< Clock Enable */
#define  USART_CR2_STOP                       ((uint16_t)0x3000)            /*!< STOP bits */
#define  USART_CR2_STOP_1                     ((uint16_t)0x0000)            /*!< 1 Stop bit */
#define  USART_CR2_STOP_0_5                   ((uint16_t)0x1000)            /*!< 0.5 Stop bit */
#define  USART_CR2_STOP_2                     ((uint16_t)0x2000)            /*!< 2 Stop bits */
#define  USART_CR2_STOP_1_5                   ((uint16_t)0x3000)            /*!< 1.5 Stop bit */
#define  USART_CR2_LINEN                      ((uint16_t)0x4000)            /*!< LIN mode enable */

/* ---------------------- USART Control Register 3 (CR3) ---------------------- */
#define  USART_CR3_EIE                        ((uint16_t)0x0001)            /*!< Error Interrupt Enable */
#define  USART_CR3_IREN                       ((uint16_t)0x0002)            /*!< IrDA mode Enable */
#define  USART_CR3_IRLP                       ((uint16_t)0x0004)            /*!< IrDA Low-Power */
#define  USART_CR3_HDSEL                      ((uint16_t)0x0008)            /*!< Half-Duplex Selection */
#define  USART_CR3_NACK                       ((uint16_t)0x0010)            /*!< Smartcard NACK enable */
#define  USART_CR3_SCEN                       ((uint16_t)0x0020)            /*!< Smartcard mode enable */
#define  USART_CR3_DMAR                       ((uint16_t)0x0040)            /*!< DMA Enable Receiver */
#define  USART_CR3_DMAT                       ((uint16_t)0x0080)            /*!< DMA Enable Transmitter */
#define  USART_CR3_RTSE                       ((uint16_t)0x0100)            /*!< RTS Enable */
#define  USART_CR3_CTSE                       ((uint16_t)0x0200)            /*!< CTS Enable */
#define  USART_CR3_CTSIE                      ((uint16_t)0x0400)            /*!< CTS Interrupt Enable */
#define  USART_CR3_ONEBIT                     ((uint16_t)0x0800)            /*!< One Sample Bit Method enable */

/* ---------------------- USART Guard Time and Prescaler Register (GTPR) ---------------------- */
#define  USART_GTPR_PSC                       ((uint16_t)0x00FF)            /*!< Prescaler value */
#define  USART_GTPR_GT                        ((uint16_t)0xFF00)            /*!< Guard time value */

  /* ========================================================================= */
  /*                            TIM Registers                                  */
  /* ========================================================================= */

/* ---------------------- TIM Control Register 1 (CR1) ---------------------- */
#define  TIM_CR1_CEN                          ((uint16_t)0x0001)            /*!< Counter enable */
#define  TIM_CR1_UDIS                         ((uint16_t)0x0002)            /*!< Update disable */
#define  TIM_CR1_URS                          ((uint16_t)0x0004)            /*!< Update request source */
#define  TIM_CR1_OPM                          ((uint16_t)0x0008)            /*!< One pulse mode */
#define  TIM_CR1_DIR                          ((uint16_t)0x0010)            /*!< Direction */
#define  TIM_CR1_CMS                          ((uint16_t)0x0060)            /*!< Center-aligned mode selection */
#define  TIM_CR1_CMS_EDGE                     ((uint16_t)0x0000)            /*!< Edge-aligned mode */
#define  TIM_CR1_CMS_CENTER_1                 ((uint16_t)0x0020)            /*!< Center-aligned mode 1 */
#define  TIM_CR1_CMS_CENTER_2                 ((uint16_t)0x0040)            /*!< Center-aligned mode 2 */
#define  TIM_CR1_CMS_CENTER_3                 ((uint16_t)0x0060)            /*!< Center-aligned mode 3 */
#define  TIM_CR1_ARPE                         ((uint16_t)0x0080)            /*!< Auto-reload preload enable */
#define  TIM_CR1_CKD                          ((uint16_t)0x0300)            /*!< Clock division */
#define  TIM_CR1_CKD_DIV1                     ((uint16_t)0x0000)            /*!< tDTS = tCK_INT */
#define  TIM_CR1_CKD_DIV2                     ((uint16_t)0x0100)            /*!< tDTS = 2 * tCK_INT */
#define  TIM_CR1_CKD_DIV4                     ((uint16_t)0x0200)            /*!< tDTS = 4 * tCK_INT */

/* ---------------------- TIM Control Register 2 (CR2) ---------------------- */
#define  TIM_CR2_CCPC                         ((uint16_t)0x0001)            /*!< Capture/Compare Preloaded Control */
#define  TIM_CR2_CCUS                         ((uint16_t)0x0004)            /*!< Capture/Compare Control Update Selection */
#define  TIM_CR2_CCDS                         ((uint16_t)0x0008)            /*!< Capture/Compare DMA Selection */
#define  TIM_CR2_MMS                          ((uint16_t)0x0070)            /*!< Master Mode Selection */
#define  TIM_CR2_MMS_RESET                    ((uint16_t)0x0000)            /*!< Reset */
#define  TIM_CR2_MMS_ENABLE                   ((uint16_t)0x0010)            /*!< Enable */
#define  TIM_CR2_MMS_UPDATE                   ((uint16_t)0x0020)            /*!< Update */
#define  TIM_CR2_MMS_COMPARE_PULSE            ((uint16_t)0x0030)            /*!< Compare Pulse */
#define  TIM_CR2_MMS_COMPARE_OC1REF           ((uint16_t)0x0040)            /*!< Compare - OC1REF signal is used as trigger output */
#define  TIM_CR2_MMS_COMPARE_OC2REF           ((uint16_t)0x0050)            /*!< Compare - OC2REF signal is used as trigger output */
#define  TIM_CR2_MMS_COMPARE_OC3REF           ((uint16_t)0x0060)            /*!< Compare - OC3REF signal is used as trigger output */
#define  TIM_CR2_MMS_COMPARE_OC4REF           ((uint16_t)0x0070)            /*!< Compare - OC4REF signal is used as trigger output */
#define  TIM_CR2_TI1S                         ((uint16_t)0x0080)            /*!< TI1 Selection */

/* ---------------------- TIM Slave Mode Control Register (SMCR) ---------------------- */
#define  TIM_SMCR_SMS                         ((uint16_t)0x0007)            /*!< Slave mode selection */
#define  TIM_SMCR_SMS_DISABLE                 ((uint16_t)0x0000)            /*!< Slave mode disabled */
#define  TIM_SMCR_SMS_ENCODER1                ((uint16_t)0x0001)            /*!< Encoder mode 1 */
#define  TIM_SMCR_SMS_ENCODER2                ((uint16_t)0x0002)            /*!< Encoder mode 2 */
#define  TIM_SMCR_SMS_ENCODER3                ((uint16_t)0x0003)            /*!< Encoder mode 3 */
#define  TIM_SMCR_SMS_RESET                   ((uint16_t)0x0004)            /*!< Reset Mode */
#define  TIM_SMCR_SMS_GATED                   ((uint16_t)0x0005)            /*!< Gated Mode */
#define  TIM_SMCR_SMS_TRIGGER                 ((uint16_t)0x0006)            /*!< Trigger Mode */
#define  TIM_SMCR_SMS_EXT_CLK                 ((uint16_t)0x0007)            /*!< External Clock Mode 1 */
#define  TIM_SMCR_TS                          ((uint16_t)0x0070)            /*!< Trigger selection */
#define  TIM_SMCR_TS_ITR0                     ((uint16_t)0x0000)            /*!< Internal Trigger 0 */
#define  TIM_SMCR_TS_ITR1                     ((uint16_t)0x0010)            /*!< Internal Trigger 1 */
#define  TIM_SMCR_TS_ITR2                     ((uint16_t)0x0020)            /*!< Internal Trigger 2 */
#define  TIM_SMCR_TS_ITR3                     ((uint16_t)0x0030)            /*!< Internal Trigger 3 */
#define  TIM_SMCR_TS_TI1F_ED                  ((uint16_t)0x0040)            /*!< TI1 Edge Detector */
#define  TIM_SMCR_TS_TI1FP1                   ((uint16_t)0x0050)            /*!< Filtered Timer Input 1 */
#define  TIM_SMCR_TS_TI2FP2                   ((uint16_t)0x0060)            /*!< Filtered Timer Input 2 */
#define  TIM_SMCR_TS_ETRF                     ((uint16_t)0x0070)            /*!< External Trigger input */
#define  TIM_SMCR_MSM                         ((uint16_t)0x0080)            /*!< Master/Slave mode */
#define  TIM_SMCR_ETF                         ((uint16_t)0x0F00)            /*!< External trigger filter */
#define  TIM_SMCR_ETF_NONE                    ((uint16_t)0x0000)            /*!< No filter, sampling is done at fDTS */
#define  TIM_SMCR_ETF_DTS_DIV2_N6             ((uint16_t)0x0100)            /*!< fSAMPLING=fCK_INT, N=6 */
#define  TIM_SMCR_ETF_DTS_DIV4_N8             ((uint16_t)0x0200)            /*!< fSAMPLING=fCK_INT, N=8 */
#define  TIM_SMCR_ETF_DTS_DIV8_N6_DIV8_N6     ((uint16_t)0x0300)            /*!< fSAMPLING=fDTS/8, N=6 */
#define  TIM_SMCR_ETF_DTS_DIV8_N8             ((uint16_t)0x0400)            /*!< fSAMPLING=fDTS/8, N=8 */
#define  TIM_SMCR_ETF_DTS_DIV16_N5            ((uint16_t)0x0500)            /*!< fSAMPLING=fDTS/16, N=5 */
#define  TIM_SMCR_ETF_DTS_DIV16_N6            ((uint16_t)0x0600)            /*!< fSAMPLING=fDTS/16, N=6 */
#define  TIM_SMCR_ETF_DTS_DIV16_N8            ((uint16_t)0x0700)            /*!< fSAMPLING=fDTS/16, N=8 */
#define  TIM_SMCR_ETF_DTS_DIV32_N5            ((uint16_t)0x0800)            /*!< fSAMPLING=fDTS/32, N=5 */
#define  TIM_SMCR_ETF_DTS_DIV32_N6            ((uint16_t)0x0900)            /*!< fSAMPLING=fDTS/32, N=6 */
#define  TIM_SMCR_ETF_DTS_DIV32_N8            ((uint16_t)0x0A00)            /*!< fSAMPLING=fDTS/32, N=8 */
#define  TIM_SMCR_ETPS                        ((uint16_t)0x3000)            /*!< External trigger prescaler */
#define  TIM_SMCR_ETPS_DIV1                   ((uint16_t)0x0000)            /*!< ETRP frequency divided by 1 */
#define  TIM_SMCR_ETPS_DIV2                   ((uint16_t)0x1000)            /*!< ETRP frequency divided by 2 */
#define  TIM_SMCR_ETPS_DIV4                   ((uint16_t)0x2000)            /*!< ETRP frequency divided by 4 */
#define  TIM_SMCR_ETPS_DIV8                   ((uint16_t)0x3000)            /*!< ETRP frequency divided by 8 */
#define  TIM_SMCR_ECE                         ((uint16_t)0x4000)            /*!< External clock enable */
#define  TIM_SMCR_ETP                         ((uint16_t)0x8000)            /*!< External trigger polarity */

/* ---------------------- TIM DMA/Interrupt Enable Register (DIER) ---------------------- */
#define  TIM_DIER_UIE                         ((uint16_t)0x0001)            /*!< Update interrupt enable */
#define  TIM_DIER_CC1IE                       ((uint16_t)0x0002)            /*!< Capture/Compare 1 interrupt enable */
#define  TIM_DIER_CC2IE                       ((uint16_t)0x0004)            /*!< Capture/Compare 2 interrupt enable */
#define  TIM_DIER_CC3IE                       ((uint16_t)0x0008)            /*!< Capture/Compare 3 interrupt enable */
#define  TIM_DIER_CC4IE                       ((uint16_t)0x0010)            /*!< Capture/Compare 4 interrupt enable */
#define  TIM_DIER_COMIE                       ((uint16_t)0x0020)            /*!< COM interrupt enable */
#define  TIM_DIER_TIE                         ((uint16_t)0x0040)            /*!< Trigger interrupt enable */
#define  TIM_DIER_BIE                         ((uint16_t)0x0080)            /*!< Break interrupt enable */
#define  TIM_DIER_UDE                         ((uint16_t)0x0100)            /*!< Update DMA request enable */
#define  TIM_DIER_CC1DE                       ((uint16_t)0x0200)            /*!< Capture/Compare 1 DMA request enable */
#define  TIM_DIER_CC2DE                       ((uint16_t)0x0400)            /*!< Capture/Compare 2 DMA request enable */
#define  TIM_DIER_CC3DE                       ((uint16_t)0x0800)            /*!< Capture/Compare 3 DMA request enable */
#define  TIM_DIER_CC4DE                       ((uint16_t)0x1000)            /*!< Capture/Compare 4 DMA request enable */
#define  TIM_DIER_COMDE                       ((uint16_t)0x2000)            /*!< COM DMA request enable */
#define  TIM_DIER_TDE                         ((uint16_t)0x4000)            /*!< Trigger DMA request enable */

/* ---------------------- TIM Status Register (SR) ---------------------- */
#define  TIM_SR_UIF                           ((uint16_t)0x0001)            /*!< Update interrupt Flag */
#define  TIM_SR_CC1IF                         ((uint16_t)0x0002)            /*!< Capture/Compare 1 interrupt Flag */
#define  TIM_SR_CC2IF                         ((uint16_t)0x0004)            /*!< Capture/Compare 2 interrupt Flag */
#define  TIM_SR_CC3IF                         ((uint16_t)0x0008)            /*!< Capture/Compare 3 interrupt Flag */
#define  TIM_SR_CC4IF                         ((uint16_t)0x0010)            /*!< Capture/Compare 4 interrupt Flag */
#define  TIM_SR_COMIF                         ((uint16_t)0x0020)            /*!< COM interrupt Flag */
#define  TIM_SR_TIF                           ((uint16_t)0x0040)            /*!< Trigger interrupt Flag */
#define  TIM_SR_BIF                           ((uint16_t)0x0080)            /*!< Break interrupt Flag */
#define  TIM_SR_CC1OF                         ((uint16_t)0x0200)            /*!< Capture/Compare 1 Overcapture Flag */
#define  TIM_SR_CC2OF                         ((uint16_t)0x0400)            /*!< Capture/Compare 2 Overcapture Flag */
#define  TIM_SR_CC3OF                         ((uint16_t)0x0800)            /*!< Capture/Compare 3 Overcapture Flag */
#define  TIM_SR_CC4OF                         ((uint16_t)0x1000)            /*!< Capture/Compare 4 Overcapture Flag */

/* ---------------------- TIM Event Generation Register (EGR) ---------------------- */
#define  TIM_EGR_UG                           ((uint16_t)0x0001)            /*!< Update Generation */
#define  TIM_EGR_CC1G                         ((uint16_t)0x0002)            /*!< Capture/Compare 1 Generation */
#define  TIM_EGR_CC2G                         ((uint16_t)0x0004)            /*!< Capture/Compare 2 Generation */
#define  TIM_EGR_CC3G                         ((uint16_t)0x0008)            /*!< Capture/Compare 3 Generation */
#define  TIM_EGR_CC4G                         ((uint16_t)0x0010)            /*!< Capture/Compare 4 Generation */
#define  TIM_EGR_COMG                         ((uint16_t)0x0020)            /*!< Capture/Compare Control Update Generation */
#define  TIM_EGR_TG                           ((uint16_t)0x0040)            /*!< Trigger Generation */
#define  TIM_EGR_BG                           ((uint16_t)0x0080)            /*!< Break Generation */

/* ---------------------- TIM Capture/Compare Mode Register 1 (CCMR1) ---------------------- */
/* Channel 1 */
#define  TIM_CCMR1_CC1S                       ((uint16_t)0x0003)            /*!< CC1 Channel Selection */
#define  TIM_CCMR1_CC1S_OUTPUT                ((uint16_t)0x0000)            /*!< CC1 channel is configured as output */
#define  TIM_CCMR1_CC1S_INPUT_TI1             ((uint16_t)0x0001)            /*!< CC1 channel is configured as input, IC1 is mapped on TI1 */
#define  TIM_CCMR1_CC1S_INPUT_TI2             ((uint16_t)0x0002)            /*!< CC1 channel is configured as input, IC1 is mapped on TI2 */
#define  TIM_CCMR1_CC1S_INPUT_TRC             ((uint16_t)0x0003)            /*!< CC1 channel is configured as input, IC1 is mapped on TRC */
#define  TIM_CCMR1_OC1FE                      ((uint16_t)0x0004)            /*!< Output Compare 1 Fast enable */
#define  TIM_CCMR1_OC1PE                      ((uint16_t)0x0008)            /*!< Output Compare 1 Preload enable */
#define  TIM_CCMR1_OC1M                       ((uint16_t)0x0070)            /*!< Output Compare 1 Mode */
#define  TIM_CCMR1_OC1M_FROZEN                ((uint16_t)0x0000)            /*!< Frozen */
#define  TIM_CCMR1_OC1M_ACTIVEONMATCH         ((uint16_t)0x0010)            /*!< Set channel 1 to active level on match */
#define  TIM_CCMR1_OC1M_INACTIVEONMATCH       ((uint16_t)0x0020)            /*!< Set channel 1 to inactive level on match */
#define  TIM_CCMR1_OC1M_TOGGLE                ((uint16_t)0x0030)            /*!< Toggle */
#define  TIM_CCMR1_OC1M_FORCEINACTIVE         ((uint16_t)0x0040)            /*!< Force inactive level */
#define  TIM_CCMR1_OC1M_FORCEACTIVE           ((uint16_t)0x0050)            /*!< Force active level */
#define  TIM_CCMR1_OC1M_PWM1                  ((uint16_t)0x0060)            /*!< PWM mode 1 */
#define  TIM_CCMR1_OC1M_PWM2                  ((uint16_t)0x0070)            /*!< PWM mode 2 */
#define  TIM_CCMR1_OC1CE                      ((uint16_t)0x0080)            /*!< Output Compare 1 Clear Enable */
#define  TIM_CCMR1_IC1PSC                     ((uint16_t)0x000C)            /*!< Input Capture 1 Prescaler */
#define  TIM_CCMR1_IC1PSC_DIV1                ((uint16_t)0x0000)            /*!< Capture performed each time an edge is detected on the capture input */
#define  TIM_CCMR1_IC1PSC_DIV2                ((uint16_t)0x0004)            /*!< Capture performed once every 2 events */
#define  TIM_CCMR1_IC1PSC_DIV4                ((uint16_t)0x0008)            /*!< Capture performed once every 4 events */
#define  TIM_CCMR1_IC1PSC_DIV8                ((uint16_t)0x000C)            /*!< Capture performed once every 8 events */
#define  TIM_CCMR1_IC1F                       ((uint16_t)0x00F0)            /*!< Input Capture 1 Filter */

/* Channel 2 */
#define  TIM_CCMR1_CC2S                       ((uint16_t)0x0300)            /*!< CC2 Channel Selection */
#define  TIM_CCMR1_CC2S_OUTPUT                ((uint16_t)0x0000)            /*!< CC2 channel is configured as output */
#define  TIM_CCMR1_CC2S_INPUT_TI2             ((uint16_t)0x0100)            /*!< CC2 channel is configured as input, IC2 is mapped on TI2 */
#define  TIM_CCMR1_CC2S_INPUT_TI1             ((uint16_t)0x0200)            /*!< CC2 channel is configured as input, IC2 is mapped on TI1 */
#define  TIM_CCMR1_CC2S_INPUT_TRC             ((uint16_t)0x0300)            /*!< CC2 channel is configured as input, IC2 is mapped on TRC */
#define  TIM_CCMR1_OC2FE                      ((uint16_t)0x0400)            /*!< Output Compare 2 Fast enable */
#define  TIM_CCMR1_OC2PE                      ((uint16_t)0x0800)            /*!< Output Compare 2 Preload enable */
#define  TIM_CCMR1_OC2M                       ((uint16_t)0x7000)            /*!< Output Compare 2 Mode */
#define  TIM_CCMR1_OC2M_FROZEN                ((uint16_t)0x0000)            /*!< Frozen */
#define  TIM_CCMR1_OC2M_ACTIVEONMATCH         ((uint16_t)0x1000)            /*!< Set channel 2 to active level on match */
#define  TIM_CCMR1_OC2M_INACTIVEONMATCH       ((uint16_t)0x2000)            /*!< Set channel 2 to inactive level on match */
#define  TIM_CCMR1_OC2M_TOGGLE                ((uint16_t)0x3000)            /*!< Toggle */
#define  TIM_CCMR1_OC2M_FORCEINACTIVE         ((uint16_t)0x4000)            /*!< Force inactive level */
#define  TIM_CCMR1_OC2M_FORCEACTIVE           ((uint16_t)0x5000)            /*!< Force active level */
#define  TIM_CCMR1_OC2M_PWM1                  ((uint16_t)0x6000)            /*!< PWM mode 1 */
#define  TIM_CCMR1_OC2M_PWM2                  ((uint16_t)0x7000)            /*!< PWM mode 2 */
#define  TIM_CCMR1_OC2CE                      ((uint16_t)0x8000)            /*!< Output Compare 2 Clear Enable */
#define  TIM_CCMR1_IC2PSC                     ((uint16_t)0x0C00)            /*!< Input Capture 2 Prescaler */
#define  TIM_CCMR1_IC2F                       ((uint16_t)0xF000)            /*!< Input Capture 2 Filter */

/* ---------------------- TIM Capture/Compare Mode Register 2 (CCMR2) ---------------------- */
/* Channel 3 */
#define  TIM_CCMR2_CC3S                       ((uint16_t)0x0003)            /*!< CC3 Channel Selection */
#define  TIM_CCMR2_CC3S_OUTPUT                ((uint16_t)0x0000)            /*!< CC3 channel is configured as output */
#define  TIM_CCMR2_CC3S_INPUT_TI3             ((uint16_t)0x0001)            /*!< CC3 channel is configured as input, IC3 is mapped on TI3 */
#define  TIM_CCMR2_CC3S_INPUT_TI4             ((uint16_t)0x0002)            /*!< CC3 channel is configured as input, IC3 is mapped on TI4 */
#define  TIM_CCMR2_CC3S_INPUT_TRC             ((uint16_t)0x0003)            /*!< CC3 channel is configured as input, IC3 is mapped on TRC */
#define  TIM_CCMR2_OC3FE                      ((uint16_t)0x0004)            /*!< Output Compare 3 Fast enable */
#define  TIM_CCMR2_OC3PE                      ((uint16_t)0x0008)            /*!< Output Compare 3 Preload enable */
#define  TIM_CCMR2_OC3M                       ((uint16_t)0x0070)            /*!< Output Compare 3 Mode */
#define  TIM_CCMR2_OC3M_FROZEN                ((uint16_t)0x0000)            /*!< Frozen */
#define  TIM_CCMR2_OC3M_ACTIVEONMATCH         ((uint16_t)0x0010)            /*!< Set channel 3 to active level on match */
#define  TIM_CCMR2_OC3M_INACTIVEONMATCH       ((uint16_t)0x0020)            /*!< Set channel 3 to inactive level on match */
#define  TIM_CCMR2_OC3M_TOGGLE                ((uint16_t)0x0030)            /*!< Toggle */
#define  TIM_CCMR2_OC3M_FORCEINACTIVE         ((uint16_t)0x0040)            /*!< Force inactive level */
#define  TIM_CCMR2_OC3M_FORCEACTIVE           ((uint16_t)0x0050)            /*!< Force active level */
#define  TIM_CCMR2_OC3M_PWM1                  ((uint16_t)0x0060)            /*!< PWM mode 1 */
#define  TIM_CCMR2_OC3M_PWM2                  ((uint16_t)0x0070)            /*!< PWM mode 2 */
#define  TIM_CCMR2_OC3CE                      ((uint16_t)0x0080)            /*!< Output Compare 3 Clear Enable */
#define  TIM_CCMR2_IC3PSC                     ((uint16_t)0x000C)            /*!< Input Capture 3 Prescaler */
#define  TIM_CCMR2_IC3PSC_DIV1                ((uint16_t)0x0000)            /*!< Capture performed each time an edge is detected on the capture input */
#define  TIM_CCMR2_IC3PSC_DIV2                ((uint16_t)0x0004)            /*!< Capture performed once every 2 events */
#define  TIM_CCMR2_IC3PSC_DIV4                ((uint16_t)0x0008)            /*!< Capture performed once every 4 events */
#define  TIM_CCMR2_IC3PSC_DIV8                ((uint16_t)0x000C)            /*!< Capture performed once every 8 events */
#define  TIM_CCMR2_IC3F                       ((uint16_t)0x00F0)            /*!< Input Capture 3 Filter */

/* Channel 4 */
#define  TIM_CCMR2_CC4S                       ((uint16_t)0x0300)            /*!< CC4 Channel Selection */
#define  TIM_CCMR2_CC4S_OUTPUT                ((uint16_t)0x0000)            /*!< CC4 channel is configured as output */
#define  TIM_CCMR2_CC4S_INPUT_TI4             ((uint16_t)0x0100)            /*!< CC4 channel is configured as input, IC4 is mapped on TI4 */
#define  TIM_CCMR2_CC4S_INPUT_TI3             ((uint16_t)0x0200)            /*!< CC4 channel is configured as input, IC4 is mapped on TI3 */
#define  TIM_CCMR2_CC4S_INPUT_TRC             ((uint16_t)0x0300)            /*!< CC4 channel is configured as input, IC4 is mapped on TRC */
#define  TIM_CCMR2_OC4FE                      ((uint16_t)0x0400)            /*!< Output Compare 4 Fast enable */
#define  TIM_CCMR2_OC4PE                      ((uint16_t)0x0800)            /*!< Output Compare 4 Preload enable */
#define  TIM_CCMR2_OC4M                       ((uint16_t)0x7000)            /*!< Output Compare 4 Mode */
#define  TIM_CCMR2_OC4M_FROZEN                ((uint16_t)0x0000)            /*!< Frozen */
#define  TIM_CCMR2_OC4M_ACTIVEONMATCH         ((uint16_t)0x1000)            /*!< Set channel 4 to active level on match */
#define  TIM_CCMR2_OC4M_INACTIVEONMATCH       ((uint16_t)0x2000)            /*!< Set channel 4 to inactive level on match */
#define  TIM_CCMR2_OC4M_TOGGLE                ((uint16_t)0x3000)            /*!< Toggle */
#define  TIM_CCMR2_OC4M_FORCEINACTIVE         ((uint16_t)0x4000)            /*!< Force inactive level */
#define  TIM_CCMR2_OC4M_FORCEACTIVE           ((uint16_t)0x5000)            /*!< Force active level */
#define  TIM_CCMR2_OC4M_PWM1                  ((uint16_t)0x6000)            /*!< PWM mode 1 */
#define  TIM_CCMR2_OC4M_PWM2                  ((uint16_t)0x7000)            /*!< PWM mode 2 */
#define  TIM_CCMR2_OC4CE                      ((uint16_t)0x8000)            /*!< Output Compare 4 Clear Enable */
#define  TIM_CCMR2_IC4PSC                     ((uint16_t)0x0C00)            /*!< Input Capture 4 Prescaler */
#define  TIM_CCMR2_IC4F                       ((uint16_t)0xF000)            /*!< Input Capture 4 Filter */

/* ---------------------- TIM Capture/Compare Enable Register (CCER) ---------------------- */
#define  TIM_CCER_CC1E                        ((uint16_t)0x0001)            /*!< Capture/Compare 1 output enable */
#define  TIM_CCER_CC1P                        ((uint16_t)0x0002)            /*!< Capture/Compare 1 output Polarity */
#define  TIM_CCER_CC1NE                       ((uint16_t)0x0004)            /*!< Capture/Compare 1 Complementary output enable */
#define  TIM_CCER_CC1NP                       ((uint16_t)0x0008)            /*!< Capture/Compare 1 Complementary output Polarity */
#define  TIM_CCER_CC2E                        ((uint16_t)0x0010)            /*!< Capture/Compare 2 output enable */
#define  TIM_CCER_CC2P                        ((uint16_t)0x0020)            /*!< Capture/Compare 2 output Polarity */
#define  TIM_CCER_CC2NE                       ((uint16_t)0x0040)            /*!< Capture/Compare 2 Complementary output enable */
#define  TIM_CCER_CC2NP                       ((uint16_t)0x0080)            /*!< Capture/Compare 2 Complementary output Polarity */
#define  TIM_CCER_CC3E                        ((uint16_t)0x0100)            /*!< Capture/Compare 3 output enable */
#define  TIM_CCER_CC3P                        ((uint16_t)0x0200)            /*!< Capture/Compare 3 output Polarity */
#define  TIM_CCER_CC3NE                       ((uint16_t)0x0400)            /*!< Capture/Compare 3 Complementary output enable */
#define  TIM_CCER_CC3NP                       ((uint16_t)0x0800)            /*!< Capture/Compare 3 Complementary output Polarity */
#define  TIM_CCER_CC4E                        ((uint16_t)0x1000)            /*!< Capture/Compare 4 output enable */
#define  TIM_CCER_CC4P                        ((uint16_t)0x2000)            /*!< Capture/Compare 4 output Polarity */
#define  TIM_CCER_CC4NP                       ((uint16_t)0x8000)            /*!< Capture/Compare 4 Complementary output Polarity */

/* ---------------------- TIM Break and Dead-Time Register (BDTR) ---------------------- */
#define  TIM_BDTR_DTG                         ((uint16_t)0x00FF)            /*!< Dead-Time Generator set-up */
#define  TIM_BDTR_LOCK                        ((uint16_t)0x0300)            /*!< Lock Configuration */
#define  TIM_BDTR_LOCK_OFF                    ((uint16_t)0x0000)            /*!< LOCK OFF - No bit is write protected */
#define  TIM_BDTR_LOCK_LEVEL1                 ((uint16_t)0x0100)            /*!< LOCK Level 1 */
#define  TIM_BDTR_LOCK_LEVEL2                 ((uint16_t)0x0200)            /*!< LOCK Level 2 */
#define  TIM_BDTR_LOCK_LEVEL3                 ((uint16_t)0x0300)            /*!< LOCK Level 3 */
#define  TIM_BDTR_OSSI                        ((uint16_t)0x0400)            /*!< Off-State Selection for Idle mode */
#define  TIM_BDTR_OSSR                        ((uint16_t)0x0800)            /*!< Off-State Selection for Run mode */
#define  TIM_BDTR_BKE                         ((uint16_t)0x1000)            /*!< Break enable */
#define  TIM_BDTR_BKP                         ((uint16_t)0x2000)            /*!< Break Polarity */
#define  TIM_BDTR_AOE                         ((uint16_t)0x4000)            /*!< Automatic Output enable */
#define  TIM_BDTR_MOE                         ((uint16_t)0x8000)            /*!< Main Output enable */

  /* ========================================================================= */
  /*                           FLASH Registers                                 */
  /* ========================================================================= */

/* ---------------------- FLASH Access Control Register (ACR) ---------------------- */
#define  FLASH_ACR_LATENCY                    ((uint32_t)0x00000007)        /*!< LATENCY bits (Latency) */
#define  FLASH_ACR_LATENCY_0                  ((uint32_t)0x00000000)        /*!< Bit 0 - Zero wait state */
#define  FLASH_ACR_LATENCY_1                  ((uint32_t)0x00000001)        /*!< Bit 0 - One wait state */
#define  FLASH_ACR_LATENCY_2                  ((uint32_t)0x00000002)        /*!< Bit 0 - Two wait states */
#define  FLASH_ACR_HLFCYA                     ((uint32_t)0x00000008)        /*!< Flash Half Cycle Access Enable */
#define  FLASH_ACR_PRFTBE                     ((uint32_t)0x00000010)        /*!< Prefetch Buffer Enable */
#define  FLASH_ACR_PRFTBS                     ((uint32_t)0x00000020)        /*!< Prefetch Buffer Status */

/* ---------------------- FLASH Status Register (SR) ---------------------- */
#define  FLASH_SR_BSY                         ((uint32_t)0x00000001)        /*!< Busy */
#define  FLASH_SR_PGERR                       ((uint32_t)0x00000004)        /*!< Programming Error */
#define  FLASH_SR_WRPRTERR                    ((uint32_t)0x00000010)        /*!< Write Protection Error */
#define  FLASH_SR_EOP                         ((uint32_t)0x00000020)        /*!< End of operation */

/* ---------------------- FLASH Control Register (CR) ---------------------- */
#define  FLASH_CR_PG                          ((uint32_t)0x00000001)        /*!< Programming */
#define  FLASH_CR_PER                         ((uint32_t)0x00000002)        /*!< Page Erase */
#define  FLASH_CR_MER                         ((uint32_t)0x00000004)        /*!< Mass Erase */
#define  FLASH_CR_OPTPG                       ((uint32_t)0x00000010)        /*!< Option Byte Programming */
#define  FLASH_CR_OPTER                       ((uint32_t)0x00000020)        /*!< Option Byte Erase */
#define  FLASH_CR_STRT                        ((uint32_t)0x00000040)        /*!< Start */
#define  FLASH_CR_LOCK                        ((uint32_t)0x00000080)        /*!< Lock */
#define  FLASH_CR_OPTWRE                      ((uint32_t)0x00000200)        /*!< Option Bytes Write Enable */
#define  FLASH_CR_ERRIE                       ((uint32_t)0x00000400)        /*!< Error Interrupt Enable */
#define  FLASH_CR_EOPIE                       ((uint32_t)0x00001000)        /*!< End of operation interrupt enable */

/* ---------------------- FLASH Option Byte Register (OBR) ---------------------- */
#define  FLASH_OBR_OPTERR                     ((uint32_t)0x00000001)        /*!< Option Byte Error */
#define  FLASH_OBR_RDPRT                      ((uint32_t)0x00000002)        /*!< Read protection */
#define  FLASH_OBR_WDG_SW                     ((uint32_t)0x00000004)        /*!< WDG_SW */
#define  FLASH_OBR_nRST_STOP                  ((uint32_t)0x00000008)        /*!< nRST_STOP */
#define  FLASH_OBR_nRST_STDBY                 ((uint32_t)0x00000010)        /*!< nRST_STDBY */
#define  FLASH_OBR_USER                       ((uint32_t)0x000003FC)        /*!< User option bytes */

/* ---------------------- FLASH Write Protection Register (WRPR) ---------------------- */
#define  FLASH_WRPR_WRP                       ((uint32_t)0xFFFFFFFF)        /*!< Write protect */

  /* ========================================================================= */
  /*                            ADC Registers                                  */
  /* ========================================================================= */

/* ---------------------- ADC Status Register (SR) ---------------------- */
#define  ADC_SR_AWD                           ((uint8_t)0x01)               /*!< Analog watchdog flag */
#define  ADC_SR_EOC                           ((uint8_t)0x02)               /*!< End of conversion */
#define  ADC_SR_JEOC                          ((uint8_t)0x04)               /*!< Injected channel end of conversion */
#define  ADC_SR_JSTRT                         ((uint8_t)0x08)               /*!< Injected channel Start flag */
#define  ADC_SR_STRT                          ((uint8_t)0x10)               /*!< Regular channel Start flag */

/* ---------------------- ADC Control Register 1 (CR1) ---------------------- */
#define  ADC_CR1_AWDCH                        ((uint32_t)0x0000001F)        /*!< AWDCH[4:0] bits (Analog watchdog channel select bits) */
#define  ADC_CR1_AWDCH_0                      ((uint32_t)0x00000001)        /*!< Bit 0 */
#define  ADC_CR1_AWDCH_1                      ((uint32_t)0x00000002)        /*!< Bit 1 */
#define  ADC_CR1_AWDCH_2                      ((uint32_t)0x00000004)        /*!< Bit 2 */
#define  ADC_CR1_AWDCH_3                      ((uint32_t)0x00000008)        /*!< Bit 3 */
#define  ADC_CR1_AWDCH_4                      ((uint32_t)0x00000010)        /*!< Bit 4 */
#define  ADC_CR1_EOCIE                        ((uint32_t)0x00000020)        /*!< Interrupt enable for EOC */
#define  ADC_CR1_AWDIE                        ((uint32_t)0x00000040)        /*!< Analog Watchdog interrupt enable */
#define  ADC_CR1_JEOCIE                       ((uint32_t)0x00000080)        /*!< Interrupt enable for injected channels */
#define  ADC_CR1_SCAN                         ((uint32_t)0x00000100)        /*!< Scan mode */
#define  ADC_CR1_AWDSGL                       ((uint32_t)0x00000200)        /*!< Enable the watchdog on a single channel in scan mode */
#define  ADC_CR1_JAUTO                        ((uint32_t)0x00000400)        /*!< Automatic Injected Group conversion */
#define  ADC_CR1_DISCEN                       ((uint32_t)0x00000800)        /*!< Discontinuous mode on regular channels */
#define  ADC_CR1_JDISCEN                      ((uint32_t)0x00001000)        /*!< Discontinuous mode on injected channels */
#define  ADC_CR1_DISCNUM                      ((uint32_t)0x0000E000)        /*!< DISCNUM[2:0] bits (Discontinuous mode channel count) */
#define  ADC_CR1_DISCNUM_0                    ((uint32_t)0x00002000)        /*!< Bit 0 */
#define  ADC_CR1_DISCNUM_1                    ((uint32_t)0x00004000)        /*!< Bit 1 */
#define  ADC_CR1_DISCNUM_2                    ((uint32_t)0x00008000)        /*!< Bit 2 */
#define  ADC_CR1_DUALMOD                      ((uint32_t)0x000F0000)        /*!< DUALMOD[3:0] bits (Dual mode selection) */
#define  ADC_CR1_DUALMOD_0                    ((uint32_t)0x00010000)        /*!< Bit 0 */
#define  ADC_CR1_DUALMOD_1                    ((uint32_t)0x00020000)        /*!< Bit 1 */
#define  ADC_CR1_DUALMOD_2                    ((uint32_t)0x00040000)        /*!< Bit 2 */
#define  ADC_CR1_DUALMOD_3                    ((uint32_t)0x00080000)        /*!< Bit 3 */
#define  ADC_CR1_JAWDEN                       ((uint32_t)0x00400000)        /*!< Analog watchdog enable on injected channels */
#define  ADC_CR1_AWDEN                        ((uint32_t)0x00800000)        /*!< Analog watchdog enable on regular channels */

/* ---------------------- ADC Control Register 2 (CR2) ---------------------- */
#define  ADC_CR2_ADON                         ((uint32_t)0x00000001)        /*!< A/D Converter ON / OFF */
#define  ADC_CR2_CONT                         ((uint32_t)0x00000002)        /*!< Continuous Conversion */
#define  ADC_CR2_CAL                          ((uint32_t)0x00000004)        /*!< A/D Calibration */
#define  ADC_CR2_RSTCAL                       ((uint32_t)0x00000008)        /*!< Reset Calibration */
#define  ADC_CR2_DMA                          ((uint32_t)0x00000100)        /*!< Direct Memory access mode */
#define  ADC_CR2_ALIGN                        ((uint32_t)0x00000800)        /*!< Data Alignment */
#define  ADC_CR2_JEXTSEL                      ((uint32_t)0x00007000)        /*!< JEXTSEL[2:0] bits (External event select for injected group) */
#define  ADC_CR2_JEXTSEL_0                    ((uint32_t)0x00001000)        /*!< Bit 0 */
#define  ADC_CR2_JEXTSEL_1                    ((uint32_t)0x00002000)        /*!< Bit 1 */
#define  ADC_CR2_JEXTSEL_2                    ((uint32_t)0x00004000)        /*!< Bit 2 */
#define  ADC_CR2_JEXTTRIG                     ((uint32_t)0x00008000)        /*!< External Trigger Conversion mode for injected channels */
#define  ADC_CR2_EXTSEL                       ((uint32_t)0x000E0000)        /*!< EXTSEL[2:0] bits (External Event Select for regular group) */
#define  ADC_CR2_EXTSEL_0                     ((uint32_t)0x00020000)        /*!< Bit 0 */
#define  ADC_CR2_EXTSEL_1                     ((uint32_t)0x00040000)        /*!< Bit 1 */
#define  ADC_CR2_EXTSEL_2                     ((uint32_t)0x00080000)        /*!< Bit 2 */
#define  ADC_CR2_EXTTRIG                      ((uint32_t)0x00100000)        /*!< External Trigger Conversion mode for regular channels */
#define  ADC_CR2_JSWSTART                     ((uint32_t)0x00200000)        /*!< Start Conversion of injected channels */
#define  ADC_CR2_SWSTART                      ((uint32_t)0x00400000)        /*!< Start Conversion of regular channels */
#define  ADC_CR2_TSVREFE                      ((uint32_t)0x00800000)        /*!< Temperature Sensor and VREFINT Enable */

/* ---------------------- ADC Sample Time Register 1 (SMPR1) ---------------------- */
#define  ADC_SMPR1_SMP17                      ((uint32_t)0x00E00000)        /*!< SMP17[2:0] bits (Channel 17 Sample time selection) */
#define  ADC_SMPR1_SMP17_0                    ((uint32_t)0x00200000)        /*!< Bit 0 */
#define  ADC_SMPR1_SMP17_1                    ((uint32_t)0x00400000)        /*!< Bit 1 */
#define  ADC_SMPR1_SMP17_2                    ((uint32_t)0x00800000)        /*!< Bit 2 */
#define  ADC_SMPR1_SMP16                      ((uint32_t)0x001C0000)        /*!< SMP16[2:0] bits (Channel 16 Sample time selection) */
#define  ADC_SMPR1_SMP16_0                    ((uint32_t)0x00040000)        /*!< Bit 0 */
#define  ADC_SMPR1_SMP16_1                    ((uint32_t)0x00080000)        /*!< Bit 1 */
#define  ADC_SMPR1_SMP16_2                    ((uint32_t)0x00100000)        /*!< Bit 2 */
#define  ADC_SMPR1_SMP15                      ((uint32_t)0x00038000)        /*!< SMP15[2:0] bits (Channel 15 Sample time selection) */
#define  ADC_SMPR1_SMP15_0                    ((uint32_t)0x00008000)        /*!< Bit 0 */
#define  ADC_SMPR1_SMP15_1                    ((uint32_t)0x00010000)        /*!< Bit 1 */
#define  ADC_SMPR1_SMP15_2                    ((uint32_t)0x00020000)        /*!< Bit 2 */
#define  ADC_SMPR1_SMP14                      ((uint32_t)0x00007000)        /*!< SMP14[2:0] bits (Channel 14 Sample time selection) */
#define  ADC_SMPR1_SMP14_0                    ((uint32_t)0x00001000)        /*!< Bit 0 */
#define  ADC_SMPR1_SMP14_1                    ((uint32_t)0x00002000)        /*!< Bit 1 */
#define  ADC_SMPR1_SMP14_2                    ((uint32_t)0x00004000)        /*!< Bit 2 */
#define  ADC_SMPR1_SMP13                      ((uint32_t)0x00000E00)        /*!< SMP13[2:0] bits (Channel 13 Sample time selection) */
#define  ADC_SMPR1_SMP13_0                    ((uint32_t)0x00000200)        /*!< Bit 0 */
#define  ADC_SMPR1_SMP13_1                    ((uint32_t)0x00000400)        /*!< Bit 1 */
#define  ADC_SMPR1_SMP13_2                    ((uint32_t)0x00000800)        /*!< Bit 2 */
#define  ADC_SMPR1_SMP12                      ((uint32_t)0x000001C0)        /*!< SMP12[2:0] bits (Channel 12 Sample time selection) */
#define  ADC_SMPR1_SMP12_0                    ((uint32_t)0x00000040)        /*!< Bit 0 */
#define  ADC_SMPR1_SMP12_1                    ((uint32_t)0x00000080)        /*!< Bit 1 */
#define  ADC_SMPR1_SMP12_2                    ((uint32_t)0x00000100)        /*!< Bit 2 */
#define  ADC_SMPR1_SMP11                      ((uint32_t)0x00000038)        /*!< SMP11[2:0] bits (Channel 11 Sample time selection) */
#define  ADC_SMPR1_SMP11_0                    ((uint32_t)0x00000008)        /*!< Bit 0 */
#define  ADC_SMPR1_SMP11_1                    ((uint32_t)0x00000010)        /*!< Bit 1 */
#define  ADC_SMPR1_SMP11_2                    ((uint32_t)0x00000020)        /*!< Bit 2 */
#define  ADC_SMPR1_SMP10                      ((uint32_t)0x00000007)        /*!< SMP10[2:0] bits (Channel 10 Sample time selection) */
#define  ADC_SMPR1_SMP10_0                    ((uint32_t)0x00000001)        /*!< Bit 0 */
#define  ADC_SMPR1_SMP10_1                    ((uint32_t)0x00000002)        /*!< Bit 1 */
#define  ADC_SMPR1_SMP10_2                    ((uint32_t)0x00000004)        /*!< Bit 2 */

/* ---------------------- ADC Sample Time Register 2 (SMPR2) ---------------------- */
#define  ADC_SMPR2_SMP9                       ((uint32_t)0x00038000)        /*!< SMP9[2:0] bits (Channel 9 Sample time selection) */
#define  ADC_SMPR2_SMP9_0                     ((uint32_t)0x00008000)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP9_1                     ((uint32_t)0x00010000)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP9_2                     ((uint32_t)0x00020000)        /*!< Bit 2 */
#define  ADC_SMPR2_SMP8                       ((uint32_t)0x00007000)        /*!< SMP8[2:0] bits (Channel 8 Sample time selection) */
#define  ADC_SMPR2_SMP8_0                     ((uint32_t)0x00001000)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP8_1                     ((uint32_t)0x00002000)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP8_2                     ((uint32_t)0x00004000)        /*!< Bit 2 */
#define  ADC_SMPR2_SMP7                       ((uint32_t)0x00000E00)        /*!< SMP7[2:0] bits (Channel 7 Sample time selection) */
#define  ADC_SMPR2_SMP7_0                     ((uint32_t)0x00000200)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP7_1                     ((uint32_t)0x00000400)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP7_2                     ((uint32_t)0x00000800)        /*!< Bit 2 */
#define  ADC_SMPR2_SMP6                       ((uint32_t)0x000001C0)        /*!< SMP6[2:0] bits (Channel 6 Sample time selection) */
#define  ADC_SMPR2_SMP6_0                     ((uint32_t)0x00000040)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP6_1                     ((uint32_t)0x00000080)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP6_2                     ((uint32_t)0x00000100)        /*!< Bit 2 */
#define  ADC_SMPR2_SMP5                       ((uint32_t)0x00000038)        /*!< SMP5[2:0] bits (Channel 5 Sample time selection) */
#define  ADC_SMPR2_SMP5_0                     ((uint32_t)0x00000008)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP5_1                     ((uint32_t)0x00000010)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP5_2                     ((uint32_t)0x00000020)        /*!< Bit 2 */
#define  ADC_SMPR2_SMP4                       ((uint32_t)0x00000007)        /*!< SMP4[2:0] bits (Channel 4 Sample time selection) */
#define  ADC_SMPR2_SMP4_0                     ((uint32_t)0x00000001)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP4_1                     ((uint32_t)0x00000002)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP4_2                     ((uint32_t)0x00000004)        /*!< Bit 2 */
#define  ADC_SMPR2_SMP3                       ((uint32_t)0x0000E000)        /*!< SMP3[2:0] bits (Channel 3 Sample time selection) */
#define  ADC_SMPR2_SMP3_0                     ((uint32_t)0x00002000)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP3_1                     ((uint32_t)0x00004000)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP3_2                     ((uint32_t)0x00008000)        /*!< Bit 2 */
#define  ADC_SMPR2_SMP2                       ((uint32_t)0x00001C00)        /*!< SMP2[2:0] bits (Channel 2 Sample time selection) */
#define  ADC_SMPR2_SMP2_0                     ((uint32_t)0x00000400)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP2_1                     ((uint32_t)0x00000800)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP2_2                     ((uint32_t)0x00001000)        /*!< Bit 2 */
#define  ADC_SMPR2_SMP1                       ((uint32_t)0x00000380)        /*!< SMP1[2:0] bits (Channel 1 Sample time selection) */
#define  ADC_SMPR2_SMP1_0                     ((uint32_t)0x00000080)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP1_1                     ((uint32_t)0x00000100)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP1_2                     ((uint32_t)0x00000200)        /*!< Bit 2 */
#define  ADC_SMPR2_SMP0                       ((uint32_t)0x00000007)        /*!< SMP0[2:0] bits (Channel 0 Sample time selection) */
#define  ADC_SMPR2_SMP0_0                     ((uint32_t)0x00000001)        /*!< Bit 0 */
#define  ADC_SMPR2_SMP0_1                     ((uint32_t)0x00000002)        /*!< Bit 1 */
#define  ADC_SMPR2_SMP0_2                     ((uint32_t)0x00000004)        /*!< Bit 2 */

/* ---------------------- ADC Regular Sequence Register 1 (SQR1) ---------------------- */
#define  ADC_SQR1_L                           ((uint32_t)0x00F00000)        /*!< L[3:0] bits (Regular channel sequence length) */
#define  ADC_SQR1_L_0                         ((uint32_t)0x00100000)        /*!< Bit 0 */
#define  ADC_SQR1_L_1                         ((uint32_t)0x00200000)        /*!< Bit 1 */
#define  ADC_SQR1_L_2                         ((uint32_t)0x00400000)        /*!< Bit 2 */
#define  ADC_SQR1_L_3                         ((uint32_t)0x00800000)        /*!< Bit 3 */
#define  ADC_SQR1_SQ16                        ((uint32_t)0x000F8000)        /*!< SQ16[4:0] bits (16th conversion in regular sequence) */
#define  ADC_SQR1_SQ16_0                      ((uint32_t)0x00008000)        /*!< Bit 0 */
#define  ADC_SQR1_SQ16_1                      ((uint32_t)0x00010000)        /*!< Bit 1 */
#define  ADC_SQR1_SQ16_2                      ((uint32_t)0x00020000)        /*!< Bit 2 */
#define  ADC_SQR1_SQ16_3                      ((uint32_t)0x00040000)        /*!< Bit 3 */
#define  ADC_SQR1_SQ16_4                      ((uint32_t)0x00080000)        /*!< Bit 4 */
#define  ADC_SQR1_SQ15                        ((uint32_t)0x00007C00)        /*!< SQ15[4:0] bits (15th conversion in regular sequence) */
#define  ADC_SQR1_SQ15_0                      ((uint32_t)0x00000400)        /*!< Bit 0 */
#define  ADC_SQR1_SQ15_1                      ((uint32_t)0x00000800)        /*!< Bit 1 */
#define  ADC_SQR1_SQ15_2                      ((uint32_t)0x00001000)        /*!< Bit 2 */
#define  ADC_SQR1_SQ15_3                      ((uint32_t)0x00002000)        /*!< Bit 3 */
#define  ADC_SQR1_SQ15_4                      ((uint32_t)0x00004000)        /*!< Bit 4 */
#define  ADC_SQR1_SQ14                        ((uint32_t)0x000003E0)        /*!< SQ14[4:0] bits (14th conversion in regular sequence) */
#define  ADC_SQR1_SQ14_0                      ((uint32_t)0x00000020)        /*!< Bit 0 */
#define  ADC_SQR1_SQ14_1                      ((uint32_t)0x00000040)        /*!< Bit 1 */
#define  ADC_SQR1_SQ14_2                      ((uint32_t)0x00000080)        /*!< Bit 2 */
#define  ADC_SQR1_SQ14_3                      ((uint32_t)0x00000100)        /*!< Bit 3 */
#define  ADC_SQR1_SQ14_4                      ((uint32_t)0x00000200)        /*!< Bit 4 */
#define  ADC_SQR1_SQ13                        ((uint32_t)0x0000001F)        /*!< SQ13[4:0] bits (13th conversion in regular sequence) */
#define  ADC_SQR1_SQ13_0                      ((uint32_t)0x00000001)        /*!< Bit 0 */
#define  ADC_SQR1_SQ13_1                      ((uint32_t)0x00000002)        /*!< Bit 1 */
#define  ADC_SQR1_SQ13_2                      ((uint32_t)0x00000004)        /*!< Bit 2 */
#define  ADC_SQR1_SQ13_3                      ((uint32_t)0x00000008)        /*!< Bit 3 */
#define  ADC_SQR1_SQ13_4                      ((uint32_t)0x00000010)        /*!< Bit 4 */

/* ---------------------- ADC Regular Sequence Register 2 (SQR2) ---------------------- */
#define  ADC_SQR2_SQ12                        ((uint32_t)0x000F8000)        /*!< SQ12[4:0] bits (12th conversion in regular sequence) */
#define  ADC_SQR2_SQ12_0                      ((uint32_t)0x00008000)        /*!< Bit 0 */
#define  ADC_SQR2_SQ12_1                      ((uint32_t)0x00010000)        /*!< Bit 1 */
#define  ADC_SQR2_SQ12_2                      ((uint32_t)0x00020000)        /*!< Bit 2 */
#define  ADC_SQR2_SQ12_3                      ((uint32_t)0x00040000)        /*!< Bit 3 */
#define  ADC_SQR2_SQ12_4                      ((uint32_t)0x00080000)        /*!< Bit 4 */
#define  ADC_SQR2_SQ11                        ((uint32_t)0x00007C00)        /*!< SQ11[4:0] bits (11th conversion in regular sequence) */
#define  ADC_SQR2_SQ11_0                      ((uint32_t)0x00000400)        /*!< Bit 0 */
#define  ADC_SQR2_SQ11_1                      ((uint32_t)0x00000800)        /*!< Bit 1 */
#define  ADC_SQR2_SQ11_2                      ((uint32_t)0x00001000)        /*!< Bit 2 */
#define  ADC_SQR2_SQ11_3                      ((uint32_t)0x00002000)        /*!< Bit 3 */
#define  ADC_SQR2_SQ11_4                      ((uint32_t)0x00004000)        /*!< Bit 4 */
#define  ADC_SQR2_SQ10                        ((uint32_t)0x000003E0)        /*!< SQ10[4:0] bits (10th conversion in regular sequence) */
#define  ADC_SQR2_SQ10_0                      ((uint32_t)0x00000020)        /*!< Bit 0 */
#define  ADC_SQR2_SQ10_1                      ((uint32_t)0x00000040)        /*!< Bit 1 */
#define  ADC_SQR2_SQ10_2                      ((uint32_t)0x00000080)        /*!< Bit 2 */
#define  ADC_SQR2_SQ10_3                      ((uint32_t)0x00000100)        /*!< Bit 3 */
#define  ADC_SQR2_SQ10_4                      ((uint32_t)0x00000200)        /*!< Bit 4 */
#define  ADC_SQR2_SQ9                         ((uint32_t)0x0000001F)        /*!< SQ9[4:0] bits (9th conversion in regular sequence) */
#define  ADC_SQR2_SQ9_0                       ((uint32_t)0x00000001)        /*!< Bit 0 */
#define  ADC_SQR2_SQ9_1                       ((uint32_t)0x00000002)        /*!< Bit 1 */
#define  ADC_SQR2_SQ9_2                       ((uint32_t)0x00000004)        /*!< Bit 2 */
#define  ADC_SQR2_SQ9_3                       ((uint32_t)0x00000008)        /*!< Bit 3 */
#define  ADC_SQR2_SQ9_4                       ((uint32_t)0x00000010)        /*!< Bit 4 */

/* ---------------------- ADC Regular Sequence Register 3 (SQR3) ---------------------- */
#define  ADC_SQR3_SQ6                         ((uint32_t)0x000F8000)        /*!< SQ6[4:0] bits (6th conversion in regular sequence) */
#define  ADC_SQR3_SQ6_0                       ((uint32_t)0x00008000)        /*!< Bit 0 */
#define  ADC_SQR3_SQ6_1                       ((uint32_t)0x00010000)        /*!< Bit 1 */
#define  ADC_SQR3_SQ6_2                       ((uint32_t)0x00020000)        /*!< Bit 2 */
#define  ADC_SQR3_SQ6_3                       ((uint32_t)0x00040000)        /*!< Bit 3 */
#define  ADC_SQR3_SQ6_4                       ((uint32_t)0x00080000)        /*!< Bit 4 */
#define  ADC_SQR3_SQ5                         ((uint32_t)0x00007C00)        /*!< SQ5[4:0] bits (5th conversion in regular sequence) */
#define  ADC_SQR3_SQ5_0                       ((uint32_t)0x00000400)        /*!< Bit 0 */
#define  ADC_SQR3_SQ5_1                       ((uint32_t)0x00000800)        /*!< Bit 1 */
#define  ADC_SQR3_SQ5_2                       ((uint32_t)0x00001000)        /*!< Bit 2 */
#define  ADC_SQR3_SQ5_3                       ((uint32_t)0x00002000)        /*!< Bit 3 */
#define  ADC_SQR3_SQ5_4                       ((uint32_t)0x00004000)        /*!< Bit 4 */
#define  ADC_SQR3_SQ4                         ((uint32_t)0x000003E0)        /*!< SQ4[4:0] bits (4th conversion in regular sequence) */
#define  ADC_SQR3_SQ4_0                       ((uint32_t)0x00000020)        /*!< Bit 0 */
#define  ADC_SQR3_SQ4_1                       ((uint32_t)0x00000040)        /*!< Bit 1 */
#define  ADC_SQR3_SQ4_2                       ((uint32_t)0x00000080)        /*!< Bit 2 */
#define  ADC_SQR3_SQ4_3                       ((uint32_t)0x00000100)        /*!< Bit 3 */
#define  ADC_SQR3_SQ4_4                       ((uint32_t)0x00000200)        /*!< Bit 4 */
#define  ADC_SQR3_SQ3                         ((uint32_t)0x0000001F)        /*!< SQ3[4:0] bits (3rd conversion in regular sequence) */
#define  ADC_SQR3_SQ3_0                       ((uint32_t)0x00000001)        /*!< Bit 0 */
#define  ADC_SQR3_SQ3_1                       ((uint32_t)0x00000002)        /*!< Bit 1 */
#define  ADC_SQR3_SQ3_2                       ((uint32_t)0x00000004)        /*!< Bit 2 */
#define  ADC_SQR3_SQ3_3                       ((uint32_t)0x00000008)        /*!< Bit 3 */
#define  ADC_SQR3_SQ3_4                       ((uint32_t)0x00000010)        /*!< Bit 4 */
#define  ADC_SQR3_SQ2                         ((uint32_t)0x3E000000)        /*!< SQ2[4:0] bits (2nd conversion in regular sequence) */
#define  ADC_SQR3_SQ2_0                       ((uint32_t)0x02000000)        /*!< Bit 0 */
#define  ADC_SQR3_SQ2_1                       ((uint32_t)0x04000000)        /*!< Bit 1 */
#define  ADC_SQR3_SQ2_2                       ((uint32_t)0x08000000)        /*!< Bit 2 */
#define  ADC_SQR3_SQ2_3                       ((uint32_t)0x10000000)        /*!< Bit 3 */
#define  ADC_SQR3_SQ2_4                       ((uint32_t)0x20000000)        /*!< Bit 4 */
#define  ADC_SQR3_SQ1                         ((uint32_t)0x01F00000)        /*!< SQ1[4:0] bits (1st conversion in regular sequence) */
#define  ADC_SQR3_SQ1_0                       ((uint32_t)0x00100000)        /*!< Bit 0 */
#define  ADC_SQR3_SQ1_1                       ((uint32_t)0x00200000)        /*!< Bit 1 */
#define  ADC_SQR3_SQ1_2                       ((uint32_t)0x00400000)        /*!< Bit 2 */
#define  ADC_SQR3_SQ1_3                       ((uint32_t)0x00800000)        /*!< Bit 3 */
#define  ADC_SQR3_SQ1_4                       ((uint32_t)0x01000000)        /*!< Bit 4 */

  /* ========================================================================= */
  /*                           EXTI Registers                                  */
  /* ========================================================================= */

/* ---------------------- EXTI Interrupt Mask Register (IMR) ---------------------- */
#define  EXTI_IMR_MR0                         ((uint32_t)0x00000001)        /*!< Interrupt Mask on line 0 */
#define  EXTI_IMR_MR1                         ((uint32_t)0x00000002)        /*!< Interrupt Mask on line 1 */
#define  EXTI_IMR_MR2                         ((uint32_t)0x00000004)        /*!< Interrupt Mask on line 2 */
#define  EXTI_IMR_MR3                         ((uint32_t)0x00000008)        /*!< Interrupt Mask on line 3 */
#define  EXTI_IMR_MR4                         ((uint32_t)0x00000010)        /*!< Interrupt Mask on line 4 */
#define  EXTI_IMR_MR5                         ((uint32_t)0x00000020)        /*!< Interrupt Mask on line 5 */
#define  EXTI_IMR_MR6                         ((uint32_t)0x00000040)        /*!< Interrupt Mask on line 6 */
#define  EXTI_IMR_MR7                         ((uint32_t)0x00000080)        /*!< Interrupt Mask on line 7 */
#define  EXTI_IMR_MR8                         ((uint32_t)0x00000100)        /*!< Interrupt Mask on line 8 */
#define  EXTI_IMR_MR9                         ((uint32_t)0x00000200)        /*!< Interrupt Mask on line 9 */
#define  EXTI_IMR_MR10                        ((uint32_t)0x00000400)        /*!< Interrupt Mask on line 10 */
#define  EXTI_IMR_MR11                        ((uint32_t)0x00000800)        /*!< Interrupt Mask on line 11 */
#define  EXTI_IMR_MR12                        ((uint32_t)0x00001000)        /*!< Interrupt Mask on line 12 */
#define  EXTI_IMR_MR13                        ((uint32_t)0x00002000)        /*!< Interrupt Mask on line 13 */
#define  EXTI_IMR_MR14                        ((uint32_t)0x00004000)        /*!< Interrupt Mask on line 14 */
#define  EXTI_IMR_MR15                        ((uint32_t)0x00008000)        /*!< Interrupt Mask on line 15 */
#define  EXTI_IMR_MR16                        ((uint32_t)0x00010000)        /*!< Interrupt Mask on line 16 */
#define  EXTI_IMR_MR17                        ((uint32_t)0x00020000)        /*!< Interrupt Mask on line 17 */
#define  EXTI_IMR_MR18                        ((uint32_t)0x00040000)        /*!< Interrupt Mask on line 18 */
#define  EXTI_IMR_MR19                        ((uint32_t)0x00080000)        /*!< Interrupt Mask on line 19 */

/* ---------------------- EXTI Event Mask Register (EMR) ---------------------- */
#define  EXTI_EMR_MR0                         ((uint32_t)0x00000001)        /*!< Event Mask on line 0 */
#define  EXTI_EMR_MR1                         ((uint32_t)0x00000002)        /*!< Event Mask on line 1 */
#define  EXTI_EMR_MR2                         ((uint32_t)0x00000004)        /*!< Event Mask on line 2 */
#define  EXTI_EMR_MR3                         ((uint32_t)0x00000008)        /*!< Event Mask on line 3 */
#define  EXTI_EMR_MR4                         ((uint32_t)0x00000010)        /*!< Event Mask on line 4 */
#define  EXTI_EMR_MR5                         ((uint32_t)0x00000020)        /*!< Event Mask on line 5 */
#define  EXTI_EMR_MR6                         ((uint32_t)0x00000040)        /*!< Event Mask on line 6 */
#define  EXTI_EMR_MR7                         ((uint32_t)0x00000080)        /*!< Event Mask on line 7 */
#define  EXTI_EMR_MR8                         ((uint32_t)0x00000100)        /*!< Event Mask on line 8 */
#define  EXTI_EMR_MR9                         ((uint32_t)0x00000200)        /*!< Event Mask on line 9 */
#define  EXTI_EMR_MR10                        ((uint32_t)0x00000400)        /*!< Event Mask on line 10 */
#define  EXTI_EMR_MR11                        ((uint32_t)0x00000800)        /*!< Event Mask on line 11 */
#define  EXTI_EMR_MR12                        ((uint32_t)0x00001000)        /*!< Event Mask on line 12 */
#define  EXTI_EMR_MR13                        ((uint32_t)0x00002000)        /*!< Event Mask on line 13 */
#define  EXTI_EMR_MR14                        ((uint32_t)0x00004000)        /*!< Event Mask on line 14 */
#define  EXTI_EMR_MR15                        ((uint32_t)0x00008000)        /*!< Event Mask on line 15 */
#define  EXTI_EMR_MR16                        ((uint32_t)0x00010000)        /*!< Event Mask on line 16 */
#define  EXTI_EMR_MR17                        ((uint32_t)0x00020000)        /*!< Event Mask on line 17 */
#define  EXTI_EMR_MR18                        ((uint32_t)0x00040000)        /*!< Event Mask on line 18 */
#define  EXTI_EMR_MR19                        ((uint32_t)0x00080000)        /*!< Event Mask on line 19 */

/* ---------------------- EXTI Rising Trigger Selection Register (RTSR) ---------------------- */
#define  EXTI_RTSR_TR0                        ((uint32_t)0x00000001)        /*!< Rising trigger event configuration bit of line 0 */
#define  EXTI_RTSR_TR1                        ((uint32_t)0x00000002)        /*!< Rising trigger event configuration bit of line 1 */
#define  EXTI_RTSR_TR2                        ((uint32_t)0x00000004)        /*!< Rising trigger event configuration bit of line 2 */
#define  EXTI_RTSR_TR3                        ((uint32_t)0x00000008)        /*!< Rising trigger event configuration bit of line 3 */
#define  EXTI_RTSR_TR4                        ((uint32_t)0x00000010)        /*!< Rising trigger event configuration bit of line 4 */
#define  EXTI_RTSR_TR5                        ((uint32_t)0x00000020)        /*!< Rising trigger event configuration bit of line 5 */
#define  EXTI_RTSR_TR6                        ((uint32_t)0x00000040)        /*!< Rising trigger event configuration bit of line 6 */
#define  EXTI_RTSR_TR7                        ((uint32_t)0x00000080)        /*!< Rising trigger event configuration bit of line 7 */
#define  EXTI_RTSR_TR8                        ((uint32_t)0x00000100)        /*!< Rising trigger event configuration bit of line 8 */
#define  EXTI_RTSR_TR9                        ((uint32_t)0x00000200)        /*!< Rising trigger event configuration bit of line 9 */
#define  EXTI_RTSR_TR10                       ((uint32_t)0x00000400)        /*!< Rising trigger event configuration bit of line 10 */
#define  EXTI_RTSR_TR11                       ((uint32_t)0x00000800)        /*!< Rising trigger event configuration bit of line 11 */
#define  EXTI_RTSR_TR12                       ((uint32_t)0x00001000)        /*!< Rising trigger event configuration bit of line 12 */
#define  EXTI_RTSR_TR13                       ((uint32_t)0x00002000)        /*!< Rising trigger event configuration bit of line 13 */
#define  EXTI_RTSR_TR14                       ((uint32_t)0x00004000)        /*!< Rising trigger event configuration bit of line 14 */
#define  EXTI_RTSR_TR15                       ((uint32_t)0x00008000)        /*!< Rising trigger event configuration bit of line 15 */
#define  EXTI_RTSR_TR16                       ((uint32_t)0x00010000)        /*!< Rising trigger event configuration bit of line 16 */
#define  EXTI_RTSR_TR17                       ((uint32_t)0x00020000)        /*!< Rising trigger event configuration bit of line 17 */
#define  EXTI_RTSR_TR18                       ((uint32_t)0x00040000)        /*!< Rising trigger event configuration bit of line 18 */
#define  EXTI_RTSR_TR19                       ((uint32_t)0x00080000)        /*!< Rising trigger event configuration bit of line 19 */

/* ---------------------- EXTI Falling Trigger Selection Register (FTSR) ---------------------- */
#define  EXTI_FTSR_TR0                        ((uint32_t)0x00000001)        /*!< Falling trigger event configuration bit of line 0 */
#define  EXTI_FTSR_TR1                        ((uint32_t)0x00000002)        /*!< Falling trigger event configuration bit of line 1 */
#define  EXTI_FTSR_TR2                        ((uint32_t)0x00000004)        /*!< Falling trigger event configuration bit of line 2 */
#define  EXTI_FTSR_TR3                        ((uint32_t)0x00000008)        /*!< Falling trigger event configuration bit of line 3 */
#define  EXTI_FTSR_TR4                        ((uint32_t)0x00000010)        /*!< Falling trigger event configuration bit of line 4 */
#define  EXTI_FTSR_TR5                        ((uint32_t)0x00000020)        /*!< Falling trigger event configuration bit of line 5 */
#define  EXTI_FTSR_TR6                        ((uint32_t)0x00000040)        /*!< Falling trigger event configuration bit of line 6 */
#define  EXTI_FTSR_TR7                        ((uint32_t)0x00000080)        /*!< Falling trigger event configuration bit of line 7 */
#define  EXTI_FTSR_TR8                        ((uint32_t)0x00000100)        /*!< Falling trigger event configuration bit of line 8 */
#define  EXTI_FTSR_TR9                        ((uint32_t)0x00000200)        /*!< Falling trigger event configuration bit of line 9 */
#define  EXTI_FTSR_TR10                       ((uint32_t)0x00000400)        /*!< Falling trigger event configuration bit of line 10 */
#define  EXTI_FTSR_TR11                       ((uint32_t)0x00000800)        /*!< Falling trigger event configuration bit of line 11 */
#define  EXTI_FTSR_TR12                       ((uint32_t)0x00001000)        /*!< Falling trigger event configuration bit of line 12 */
#define  EXTI_FTSR_TR13                       ((uint32_t)0x00002000)        /*!< Falling trigger event configuration bit of line 13 */
#define  EXTI_FTSR_TR14                       ((uint32_t)0x00004000)        /*!< Falling trigger event configuration bit of line 14 */
#define  EXTI_FTSR_TR15                       ((uint32_t)0x00008000)        /*!< Falling trigger event configuration bit of line 15 */
#define  EXTI_FTSR_TR16                       ((uint32_t)0x00010000)        /*!< Falling trigger event configuration bit of line 16 */
#define  EXTI_FTSR_TR17                       ((uint32_t)0x00020000)        /*!< Falling trigger event configuration bit of line 17 */
#define  EXTI_FTSR_TR18                       ((uint32_t)0x00040000)        /*!< Falling trigger event configuration bit of line 18 */
#define  EXTI_FTSR_TR19                       ((uint32_t)0x00080000)        /*!< Falling trigger event configuration bit of line 19 */

/* ---------------------- EXTI Software Interrupt Event Register (SWIER) ---------------------- */
#define  EXTI_SWIER_SWIER0                    ((uint32_t)0x00000001)        /*!< Software Interrupt on line 0 */
#define  EXTI_SWIER_SWIER1                    ((uint32_t)0x00000002)        /*!< Software Interrupt on line 1 */
#define  EXTI_SWIER_SWIER2                    ((uint32_t)0x00000004)        /*!< Software Interrupt on line 2 */
#define  EXTI_SWIER_SWIER3                    ((uint32_t)0x00000008)        /*!< Software Interrupt on line 3 */
#define  EXTI_SWIER_SWIER4                    ((uint32_t)0x00000010)        /*!< Software Interrupt on line 4 */
#define  EXTI_SWIER_SWIER5                    ((uint32_t)0x00000020)        /*!< Software Interrupt on line 5 */
#define  EXTI_SWIER_SWIER6                    ((uint32_t)0x00000040)        /*!< Software Interrupt on line 6 */
#define  EXTI_SWIER_SWIER7                    ((uint32_t)0x00000080)        /*!< Software Interrupt on line 7 */
#define  EXTI_SWIER_SWIER8                    ((uint32_t)0x00000100)        /*!< Software Interrupt on line 8 */
#define  EXTI_SWIER_SWIER9                    ((uint32_t)0x00000200)        /*!< Software Interrupt on line 9 */
#define  EXTI_SWIER_SWIER10                   ((uint32_t)0x00000400)        /*!< Software Interrupt on line 10 */
#define  EXTI_SWIER_SWIER11                   ((uint32_t)0x00000800)        /*!< Software Interrupt on line 11 */
#define  EXTI_SWIER_SWIER12                   ((uint32_t)0x00001000)        /*!< Software Interrupt on line 12 */
#define  EXTI_SWIER_SWIER13                   ((uint32_t)0x00002000)        /*!< Software Interrupt on line 13 */
#define  EXTI_SWIER_SWIER14                   ((uint32_t)0x00004000)        /*!< Software Interrupt on line 14 */
#define  EXTI_SWIER_SWIER15                   ((uint32_t)0x00008000)        /*!< Software Interrupt on line 15 */
#define  EXTI_SWIER_SWIER16                   ((uint32_t)0x00010000)        /*!< Software Interrupt on line 16 */
#define  EXTI_SWIER_SWIER17                   ((uint32_t)0x00020000)        /*!< Software Interrupt on line 17 */
#define  EXTI_SWIER_SWIER18                   ((uint32_t)0x00040000)        /*!< Software Interrupt on line 18 */
#define  EXTI_SWIER_SWIER19                   ((uint32_t)0x00080000)        /*!< Software Interrupt on line 19 */

/* ---------------------- EXTI Pending Register (PR) ---------------------- */
#define  EXTI_PR_PR0                          ((uint32_t)0x00000001)        /*!< Pending bit for line 0 */
#define  EXTI_PR_PR1                          ((uint32_t)0x00000002)        /*!< Pending bit for line 1 */
#define  EXTI_PR_PR2                          ((uint32_t)0x00000004)        /*!< Pending bit for line 2 */
#define  EXTI_PR_PR3                          ((uint32_t)0x00000008)        /*!< Pending bit for line 3 */
#define  EXTI_PR_PR4                          ((uint32_t)0x00000010)        /*!< Pending bit for line 4 */
#define  EXTI_PR_PR5                          ((uint32_t)0x00000020)        /*!< Pending bit for line 5 */
#define  EXTI_PR_PR6                          ((uint32_t)0x00000040)        /*!< Pending bit for line 6 */
#define  EXTI_PR_PR7                          ((uint32_t)0x00000080)        /*!< Pending bit for line 7 */
#define  EXTI_PR_PR8                          ((uint32_t)0x00000100)        /*!< Pending bit for line 8 */
#define  EXTI_PR_PR9                          ((uint32_t)0x00000200)        /*!< Pending bit for line 9 */
#define  EXTI_PR_PR10                         ((uint32_t)0x00000400)        /*!< Pending bit for line 10 */
#define  EXTI_PR_PR11                         ((uint32_t)0x00000800)        /*!< Pending bit for line 11 */
#define  EXTI_PR_PR12                         ((uint32_t)0x00001000)        /*!< Pending bit for line 12 */
#define  EXTI_PR_PR13                         ((uint32_t)0x00002000)        /*!< Pending bit for line 13 */
#define  EXTI_PR_PR14                         ((uint32_t)0x00004000)        /*!< Pending bit for line 14 */
#define  EXTI_PR_PR15                         ((uint32_t)0x00008000)        /*!< Pending bit for line 15 */
#define  EXTI_PR_PR16                         ((uint32_t)0x00010000)        /*!< Pending bit for line 16 */
#define  EXTI_PR_PR17                         ((uint32_t)0x00020000)        /*!< Pending bit for line 17 */
#define  EXTI_PR_PR18                         ((uint32_t)0x00040000)        /*!< Pending bit for line 18 */
#define  EXTI_PR_PR19                         ((uint32_t)0x00080000)        /*!< Pending bit for line 19 */

  /* ========================================================================= */
  /*                           IWDG Registers                                  */
  /* ========================================================================= */

/* ---------------------- IWDG Key Register (KR) ---------------------- */
#define  IWDG_KR_KEY                          ((uint16_t)0xFFFF)            /*!< Key value (write only, read 0000h) */

/* ---------------------- IWDG Prescaler Register (PR) ---------------------- */
#define  IWDG_PR_PR                           ((uint8_t)0x07)               /*!< PR[2:0] (Prescaler divider) */
#define  IWDG_PR_PR_0                         ((uint8_t)0x01)               /*!< Bit 0 */
#define  IWDG_PR_PR_1                         ((uint8_t)0x02)               /*!< Bit 1 */
#define  IWDG_PR_PR_2                         ((uint8_t)0x04)               /*!< Bit 2 */

/* ---------------------- IWDG Reload Register (RLR) ---------------------- */
#define  IWDG_RLR_RL                          ((uint16_t)0x0FFF)            /*!< Watchdog counter reload value */

/* ---------------------- IWDG Status Register (SR) ---------------------- */
#define  IWDG_SR_PVU                          ((uint8_t)0x01)               /*!< Watchdog prescaler value update */
#define  IWDG_SR_RVU                          ((uint8_t)0x02)               /*!< Watchdog counter reload value update */

  /* ========================================================================= */
  /*                            DMA Registers                                  */
  /* ========================================================================= */

/* ---------------------- DMA Interrupt Status Register (ISR) ---------------------- */
#define  DMA_ISR_GIF1                         ((uint32_t)0x00000001)        /*!< Channel 1 Global interrupt flag */
#define  DMA_ISR_TCIF1                        ((uint32_t)0x00000002)        /*!< Channel 1 Transfer Complete flag */
#define  DMA_ISR_HTIF1                        ((uint32_t)0x00000004)        /*!< Channel 1 Half Transfer flag */
#define  DMA_ISR_TEIF1                        ((uint32_t)0x00000008)        /*!< Channel 1 Transfer Error flag */
#define  DMA_ISR_GIF2                         ((uint32_t)0x00000010)        /*!< Channel 2 Global interrupt flag */
#define  DMA_ISR_TCIF2                        ((uint32_t)0x00000020)        /*!< Channel 2 Transfer Complete flag */
#define  DMA_ISR_HTIF2                        ((uint32_t)0x00000040)        /*!< Channel 2 Half Transfer flag */
#define  DMA_ISR_TEIF2                        ((uint32_t)0x00000080)        /*!< Channel 2 Transfer Error flag */
#define  DMA_ISR_GIF3                         ((uint32_t)0x00000100)        /*!< Channel 3 Global interrupt flag */
#define  DMA_ISR_TCIF3                        ((uint32_t)0x00000200)        /*!< Channel 3 Transfer Complete flag */
#define  DMA_ISR_HTIF3                        ((uint32_t)0x00000400)        /*!< Channel 3 Half Transfer flag */
#define  DMA_ISR_TEIF3                        ((uint32_t)0x00000800)        /*!< Channel 3 Transfer Error flag */
#define  DMA_ISR_GIF4                         ((uint32_t)0x00001000)        /*!< Channel 4 Global interrupt flag */
#define  DMA_ISR_TCIF4                        ((uint32_t)0x00002000)        /*!< Channel 4 Transfer Complete flag */
#define  DMA_ISR_HTIF4                        ((uint32_t)0x00004000)        /*!< Channel 4 Half Transfer flag */
#define  DMA_ISR_TEIF4                        ((uint32_t)0x00008000)        /*!< Channel 4 Transfer Error flag */
#define  DMA_ISR_GIF5                         ((uint32_t)0x00010000)        /*!< Channel 5 Global interrupt flag */
#define  DMA_ISR_TCIF5                        ((uint32_t)0x00020000)        /*!< Channel 5 Transfer Complete flag */
#define  DMA_ISR_HTIF5                        ((uint32_t)0x00040000)        /*!< Channel 5 Half Transfer flag */
#define  DMA_ISR_TEIF5                        ((uint32_t)0x00080000)        /*!< Channel 5 Transfer Error flag */
#define  DMA_ISR_GIF6                         ((uint32_t)0x00100000)        /*!< Channel 6 Global interrupt flag */
#define  DMA_ISR_TCIF6                        ((uint32_t)0x00200000)        /*!< Channel 6 Transfer Complete flag */
#define  DMA_ISR_HTIF6                        ((uint32_t)0x00400000)        /*!< Channel 6 Half Transfer flag */
#define  DMA_ISR_TEIF6                        ((uint32_t)0x00800000)        /*!< Channel 6 Transfer Error flag */
#define  DMA_ISR_GIF7                         ((uint32_t)0x01000000)        /*!< Channel 7 Global interrupt flag */
#define  DMA_ISR_TCIF7                        ((uint32_t)0x02000000)        /*!< Channel 7 Transfer Complete flag */
#define  DMA_ISR_HTIF7                        ((uint32_t)0x04000000)        /*!< Channel 7 Half Transfer flag */
#define  DMA_ISR_TEIF7                        ((uint32_t)0x08000000)        /*!< Channel 7 Transfer Error flag */

/* ---------------------- DMA Interrupt Flag Clear Register (IFCR) ---------------------- */
#define  DMA_IFCR_CGIF1                       ((uint32_t)0x00000001)        /*!< Channel 1 Global interrupt clear */
#define  DMA_IFCR_CTCIF1                      ((uint32_t)0x00000002)        /*!< Channel 1 Transfer Complete clear */
#define  DMA_IFCR_CHTIF1                      ((uint32_t)0x00000004)        /*!< Channel 1 Half Transfer clear */
#define  DMA_IFCR_CTEIF1                      ((uint32_t)0x00000008)        /*!< Channel 1 Transfer Error clear */
#define  DMA_IFCR_CGIF2                       ((uint32_t)0x00000010)        /*!< Channel 2 Global interrupt clear */
#define  DMA_IFCR_CTCIF2                      ((uint32_t)0x00000020)        /*!< Channel 2 Transfer Complete clear */
#define  DMA_IFCR_CHTIF2                      ((uint32_t)0x00000040)        /*!< Channel 2 Half Transfer clear */
#define  DMA_IFCR_CTEIF2                      ((uint32_t)0x00000080)        /*!< Channel 2 Transfer Error clear */
#define  DMA_IFCR_CGIF3                       ((uint32_t)0x00000100)        /*!< Channel 3 Global interrupt clear */
#define  DMA_IFCR_CTCIF3                      ((uint32_t)0x00000200)        /*!< Channel 3 Transfer Complete clear */
#define  DMA_IFCR_CHTIF3                      ((uint32_t)0x00000400)        /*!< Channel 3 Half Transfer clear */
#define  DMA_IFCR_CTEIF3                      ((uint32_t)0x00000800)        /*!< Channel 3 Transfer Error clear */
#define  DMA_IFCR_CGIF4                       ((uint32_t)0x00001000)        /*!< Channel 4 Global interrupt clear */
#define  DMA_IFCR_CTCIF4                      ((uint32_t)0x00002000)        /*!< Channel 4 Transfer Complete clear */
#define  DMA_IFCR_CHTIF4                      ((uint32_t)0x00004000)        /*!< Channel 4 Half Transfer clear */
#define  DMA_IFCR_CTEIF4                      ((uint32_t)0x00008000)        /*!< Channel 4 Transfer Error clear */
#define  DMA_IFCR_CGIF5                       ((uint32_t)0x00010000)        /*!< Channel 5 Global interrupt clear */
#define  DMA_IFCR_CTCIF5                      ((uint32_t)0x00020000)        /*!< Channel 5 Transfer Complete clear */
#define  DMA_IFCR_CHTIF5                      ((uint32_t)0x00040000)        /*!< Channel 5 Half Transfer clear */
#define  DMA_IFCR_CTEIF5                      ((uint32_t)0x00080000)        /*!< Channel 5 Transfer Error clear */
#define  DMA_IFCR_CGIF6                       ((uint32_t)0x00100000)        /*!< Channel 6 Global interrupt clear */
#define  DMA_IFCR_CTCIF6                      ((uint32_t)0x00200000)        /*!< Channel 6 Transfer Complete clear */
#define  DMA_IFCR_CHTIF6                      ((uint32_t)0x00400000)        /*!< Channel 6 Half Transfer clear */
#define  DMA_IFCR_CTEIF6                      ((uint32_t)0x00800000)        /*!< Channel 6 Transfer Error clear */
#define  DMA_IFCR_CGIF7                       ((uint32_t)0x01000000)        /*!< Channel 7 Global interrupt clear */
#define  DMA_IFCR_CTCIF7                      ((uint32_t)0x02000000)        /*!< Channel 7 Transfer Complete clear */
#define  DMA_IFCR_CHTIF7                      ((uint32_t)0x04000000)        /*!< Channel 7 Half Transfer clear */
#define  DMA_IFCR_CTEIF7                      ((uint32_t)0x08000000)        /*!< Channel 7 Transfer Error clear */

/* ---------------------- DMA Channel Configuration Register (CCR) ---------------------- */
#define  DMA_CCR_EN                           ((uint32_t)0x00000001)        /*!< Channel enable */
#define  DMA_CCR_TCIE                         ((uint32_t)0x00000002)        /*!< Transfer complete interrupt enable */
#define  DMA_CCR_HTIE                         ((uint32_t)0x00000004)        /*!< Half Transfer interrupt enable */
#define  DMA_CCR_TEIE                         ((uint32_t)0x00000008)        /*!< Transfer error interrupt enable */
#define  DMA_CCR_DIR                          ((uint32_t)0x00000010)        /*!< Data transfer direction */
#define  DMA_CCR_CIRC                         ((uint32_t)0x00000020)        /*!< Circular mode */
#define  DMA_CCR_PINC                         ((uint32_t)0x00000040)        /*!< Peripheral increment mode */
#define  DMA_CCR_MINC                         ((uint32_t)0x00000080)        /*!< Memory increment mode */
#define  DMA_CCR_PSIZE                        ((uint32_t)0x00000300)        /*!< Peripheral size */
#define  DMA_CCR_PSIZE_8BIT                   ((uint32_t)0x00000000)        /*!< 8-bit */
#define  DMA_CCR_PSIZE_16BIT                  ((uint32_t)0x00000100)        /*!< 16-bit */
#define  DMA_CCR_PSIZE_32BIT                  ((uint32_t)0x00000200)        /*!< 32-bit */
#define  DMA_CCR_MSIZE                        ((uint32_t)0x00000C00)        /*!< Memory size */
#define  DMA_CCR_MSIZE_8BIT                   ((uint32_t)0x00000000)        /*!< 8-bit */
#define  DMA_CCR_MSIZE_16BIT                  ((uint32_t)0x00000400)        /*!< 16-bit */
#define  DMA_CCR_MSIZE_32BIT                  ((uint32_t)0x00000800)        /*!< 32-bit */
#define  DMA_CCR_PL                           ((uint32_t)0x00003000)        /*!< Channel Priority level */
#define  DMA_CCR_PL_LOW                       ((uint32_t)0x00000000)        /*!< Low */
#define  DMA_CCR_PL_MEDIUM                    ((uint32_t)0x00001000)        /*!< Medium */
#define  DMA_CCR_PL_HIGH                      ((uint32_t)0x00002000)        /*!< High */
#define  DMA_CCR_PL_VERY_HIGH                 ((uint32_t)0x00003000)        /*!< Very high */
#define  DMA_CCR_MEM2MEM                      ((uint32_t)0x00004000)        /*!< Memory to memory mode */

  /* ========================================================================= */
  /*                           AFIO Registers                                  */
  /* ========================================================================= */

/* ---------------------- AFIO Event Control Register (EVCR) ---------------------- */
#define  AFIO_EVCR_PIN                        ((uint32_t)0x0000000F)        /*!< PIN[3:0] bits (Pin selection) */
#define  AFIO_EVCR_PIN_PX0                    ((uint32_t)0x00000000)        /*!< Pin 0 */
#define  AFIO_EVCR_PIN_PX1                    ((uint32_t)0x00000001)        /*!< Pin 1 */
#define  AFIO_EVCR_PIN_PX2                    ((uint32_t)0x00000002)        /*!< Pin 2 */
#define  AFIO_EVCR_PIN_PX3                    ((uint32_t)0x00000003)        /*!< Pin 3 */
#define  AFIO_EVCR_PIN_PX4                    ((uint32_t)0x00000004)        /*!< Pin 4 */
#define  AFIO_EVCR_PIN_PX5                    ((uint32_t)0x00000005)        /*!< Pin 5 */
#define  AFIO_EVCR_PIN_PX6                    ((uint32_t)0x00000006)        /*!< Pin 6 */
#define  AFIO_EVCR_PIN_PX7                    ((uint32_t)0x00000007)        /*!< Pin 7 */
#define  AFIO_EVCR_PIN_PX8                    ((uint32_t)0x00000008)        /*!< Pin 8 */
#define  AFIO_EVCR_PIN_PX9                    ((uint32_t)0x00000009)        /*!< Pin 9 */
#define  AFIO_EVCR_PIN_PX10                   ((uint32_t)0x0000000A)        /*!< Pin 10 */
#define  AFIO_EVCR_PIN_PX11                   ((uint32_t)0x0000000B)        /*!< Pin 11 */
#define  AFIO_EVCR_PIN_PX12                   ((uint32_t)0x0000000C)        /*!< Pin 12 */
#define  AFIO_EVCR_PIN_PX13                   ((uint32_t)0x0000000D)        /*!< Pin 13 */
#define  AFIO_EVCR_PIN_PX14                   ((uint32_t)0x0000000E)        /*!< Pin 14 */
#define  AFIO_EVCR_PIN_PX15                   ((uint32_t)0x0000000F)        /*!< Pin 15 */
#define  AFIO_EVCR_PORT                       ((uint32_t)0x00000070)        /*!< PORT[2:0] bits (Port selection) */
#define  AFIO_EVCR_PORT_PA                    ((uint32_t)0x00000000)        /*!< Port A */
#define  AFIO_EVCR_PORT_PB                    ((uint32_t)0x00000010)        /*!< Port B */
#define  AFIO_EVCR_PORT_PC                    ((uint32_t)0x00000020)        /*!< Port C */
#define  AFIO_EVCR_PORT_PD                    ((uint32_t)0x00000030)        /*!< Port D */
#define  AFIO_EVCR_PORT_PE                    ((uint32_t)0x00000040)        /*!< Port E */
#define  AFIO_EVCR_EVOE                       ((uint32_t)0x00000080)        /*!< Event Output Enable */

/* ---------------------- AFIO Remap and Debug I/O Configuration Register (MAPR) ---------------------- */
#define  AFIO_MAPR_SPI1_REMAP                 ((uint32_t)0x00000001)        /*!< SPI1 remapping */
#define  AFIO_MAPR_I2C1_REMAP                 ((uint32_t)0x00000002)        /*!< I2C1 remapping */
#define  AFIO_MAPR_USART1_REMAP               ((uint32_t)0x00000004)        /*!< USART1 remapping */
#define  AFIO_MAPR_USART2_REMAP               ((uint32_t)0x00000008)        /*!< USART2 remapping */
#define  AFIO_MAPR_USART3_REMAP               ((uint32_t)0x00000030)        /*!< USART3 remapping */
#define  AFIO_MAPR_USART3_REMAP_NOREMAP       ((uint32_t)0x00000000)        /*!< No remap */
#define  AFIO_MAPR_USART3_REMAP_PARTIALREMAP  ((uint32_t)0x00000010)        /*!< Partial remap */
#define  AFIO_MAPR_USART3_REMAP_FULLREMAP     ((uint32_t)0x00000030)        /*!< Full remap */
#define  AFIO_MAPR_TIM1_REMAP                 ((uint32_t)0x000000C0)        /*!< TIM1 remapping */
#define  AFIO_MAPR_TIM1_REMAP_NOREMAP         ((uint32_t)0x00000000)        /*!< No remap */
#define  AFIO_MAPR_TIM1_REMAP_PARTIALREMAP    ((uint32_t)0x00000040)        /*!< Partial remap */
#define  AFIO_MAPR_TIM1_REMAP_FULLREMAP       ((uint32_t)0x000000C0)        /*!< Full remap */
#define  AFIO_MAPR_TIM2_REMAP                 ((uint32_t)0x00000300)        /*!< TIM2 remapping */
#define  AFIO_MAPR_TIM2_REMAP_NOREMAP         ((uint32_t)0x00000000)        /*!< No remap */
#define  AFIO_MAPR_TIM2_REMAP_PARTIALREMAP1   ((uint32_t)0x00000100)        /*!< Partial remap 1 */
#define  AFIO_MAPR_TIM2_REMAP_PARTIALREMAP2   ((uint32_t)0x00000200)        /*!< Partial remap 2 */
#define  AFIO_MAPR_TIM2_REMAP_FULLREMAP       ((uint32_t)0x00000300)        /*!< Full remap */
#define  AFIO_MAPR_TIM3_REMAP                 ((uint32_t)0x00000C00)        /*!< TIM3 remapping */
#define  AFIO_MAPR_TIM3_REMAP_NOREMAP         ((uint32_t)0x00000000)        /*!< No remap */
#define  AFIO_MAPR_TIM3_REMAP_PARTIALREMAP    ((uint32_t)0x00000800)        /*!< Partial remap */
#define  AFIO_MAPR_TIM3_REMAP_FULLREMAP       ((uint32_t)0x00000C00)        /*!< Full remap */
#define  AFIO_MAPR_TIM4_REMAP                 ((uint32_t)0x00001000)        /*!< TIM4 remapping */
#define  AFIO_MAPR_CAN_REMAP                  ((uint32_t)0x00006000)        /*!< CAN alternate function remapping */
#define  AFIO_MAPR_CAN_REMAP_REMAP1           ((uint32_t)0x00000000)        /*!< CANRX mapped to PA11, CANTX mapped to PA12 */
#define  AFIO_MAPR_CAN_REMAP_REMAP2           ((uint32_t)0x00004000)        /*!< CANRX mapped to PB8, CANTX mapped to PB9 */
#define  AFIO_MAPR_CAN_REMAP_REMAP3           ((uint32_t)0x00006000)        /*!< CANRX mapped to PD0, CANTX mapped to PD1 */
#define  AFIO_MAPR_PD01_REMAP                 ((uint32_t)0x00008000)        /*!< Port D0/Port D1 mapping on OSC_IN/OSC_OUT */
#define  AFIO_MAPR_SWJ_CFG                    ((uint32_t)0x07000000)        /*!< SWJ_CFG[2:0] bits (Serial Wire JTAG configuration) */
#define  AFIO_MAPR_SWJ_CFG_FULL_SWJ           ((uint32_t)0x00000000)        /*!< Full SWJ (JTAG-DP + SW-DP) : Reset State */
#define  AFIO_MAPR_SWJ_CFG_FULL_SWJ_NO_NJRST  ((uint32_t)0x01000000)        /*!< Full SWJ (JTAG-DP + SW-DP) but without NJTRST */
#define  AFIO_MAPR_SWJ_CFG_JTAGDISABLE        ((uint32_t)0x02000000)        /*!< JTAG-DP Disabled and SW-DP Enabled */
#define  AFIO_MAPR_SWJ_CFG_DISABLE            ((uint32_t)0x04000000)        /*!< JTAG-DP Disabled and SW-DP Disabled */

/* ---------------------- AFIO External Interrupt Configuration Register (EXTICR) ---------------------- */
#define  AFIO_EXTICR1_EXTI0                   ((uint16_t)0x000F)            /*!< EXTI0 configuration */
#define  AFIO_EXTICR1_EXTI1                   ((uint16_t)0x00F0)            /*!< EXTI1 configuration */
#define  AFIO_EXTICR1_EXTI2                   ((uint16_t)0x0F00)            /*!< EXTI2 configuration */
#define  AFIO_EXTICR1_EXTI3                   ((uint16_t)0xF000)            /*!< EXTI3 configuration */
#define  AFIO_EXTICR2_EXTI4                   ((uint16_t)0x000F)            /*!< EXTI4 configuration */
#define  AFIO_EXTICR2_EXTI5                   ((uint16_t)0x00F0)            /*!< EXTI5 configuration */
#define  AFIO_EXTICR2_EXTI6                   ((uint16_t)0x0F00)            /*!< EXTI6 configuration */
#define  AFIO_EXTICR2_EXTI7                   ((uint16_t)0xF000)            /*!< EXTI7 configuration */
#define  AFIO_EXTICR3_EXTI8                   ((uint16_t)0x000F)            /*!< EXTI8 configuration */
#define  AFIO_EXTICR3_EXTI9                   ((uint16_t)0x00F0)            /*!< EXTI9 configuration */
#define  AFIO_EXTICR3_EXTI10                  ((uint16_t)0x0F00)            /*!< EXTI10 configuration */
#define  AFIO_EXTICR3_EXTI11                  ((uint16_t)0xF000)            /*!< EXTI11 configuration */
#define  AFIO_EXTICR4_EXTI12                  ((uint16_t)0x000F)            /*!< EXTI12 configuration */
#define  AFIO_EXTICR4_EXTI13                  ((uint16_t)0x00F0)            /*!< EXTI13 configuration */
#define  AFIO_EXTICR4_EXTI14                  ((uint16_t)0x0F00)            /*!< EXTI14 configuration */
#define  AFIO_EXTICR4_EXTI15                  ((uint16_t)0xF000)            /*!< EXTI15 configuration */

#define  AFIO_EXTICR_EXTI_PA                  ((uint16_t)0x0000)            /*!< PA[x] pin */
#define  AFIO_EXTICR_EXTI_PB                  ((uint16_t)0x0001)            /*!< PB[x] pin */
#define  AFIO_EXTICR_EXTI_PC                  ((uint16_t)0x0002)            /*!< PC[x] pin */
#define  AFIO_EXTICR_EXTI_PD                  ((uint16_t)0x0003)            /*!< PD[x] pin */
#define  AFIO_EXTICR_EXTI_PE                  ((uint16_t)0x0004)            /*!< PE[x] pin */
#define  AFIO_EXTICR_EXTI_PF                  ((uint16_t)0x0005)            /*!< PF[x] pin */
#define  AFIO_EXTICR_EXTI_PG                  ((uint16_t)0x0006)            /*!< PG[x] pin */

  /* ========================================================================= */
  /*                      NVIC Priority Group Definitions                       */
  /* ========================================================================= */

/**
  * @brief  NVIC Priority Group
  */
#define NVIC_PriorityGroup_0         ((uint32_t)0x700) /*!< 0 bits for pre-emption priority
                                                            4 bits for subpriority */
#define NVIC_PriorityGroup_1         ((uint32_t)0x600) /*!< 1 bits for pre-emption priority
                                                            3 bits for subpriority */
#define NVIC_PriorityGroup_2         ((uint32_t)0x500) /*!< 2 bits for pre-emption priority
                                                            2 bits for subpriority */
#define NVIC_PriorityGroup_3         ((uint32_t)0x400) /*!< 3 bits for pre-emption priority
                                                            1 bits for subpriority */
#define NVIC_PriorityGroup_4         ((uint32_t)0x300) /*!< 4 bits for pre-emption priority
                                                            0 bits for subpriority */

  /* ========================================================================= */
  /*                           Bit-Banding Macros                                */
  /* ========================================================================= */

/**
  * @brief  Bit banding macros
  */
#define BITBAND(addr, bitnum) ((addr & 0xF0000000)+0x2000000+((addr &0xFFFFF)<<5)+(bitnum<<2))
#define MEM_ADDR(addr)  *((volatile unsigned long  *)(addr))
#define BIT_ADDR(addr, bitnum)   MEM_ADDR(BITBAND(addr, bitnum))

/* ========================================================================= */
/*                    Legacy convenience macros                              */
/* ========================================================================= */

#define __STM32F10X_STDPERIPH_VERSION_RC     (0x00)

#ifdef __cplusplus
}
#endif

#endif /* __STM32F10X_H */