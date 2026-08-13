#ifndef __CORE_CM3_H
#define __CORE_CM3_H

#include <stdint.h>

/*
 * CMSIS Cortex-M3 Core Peripheral Access Layer Header
 * Version: V1.30
 * Target: STM32F103C8T6 (ARM Cortex-M3, medium-density)
 */

/* IO definitions */
#define __IO    volatile
#define __I     volatile const
#define __O     volatile

/* CMSIS compiler specific defines */
#define __CM3_CMSIS_VERSION_MAIN  (0x01)
#define __CM3_CMSIS_VERSION_SUB   (0x30)

/* ========================================================================= */
/* Memory mapping                                                            */
/* ========================================================================= */
#define FLASH_BASE            ((uint32_t)0x08000000)
#define SRAM_BASE             ((uint32_t)0x20000000)
#define PERIPH_BASE           ((uint32_t)0x40000000)
#define APB1PERIPH_BASE       PERIPH_BASE
#define APB2PERIPH_BASE       (PERIPH_BASE + 0x10000)
#define AHBPERIPH_BASE        (PERIPH_BASE + 0x20000)

/* ========================================================================= */
/* System Control Block (SCB)                                                */
/* ========================================================================= */
typedef struct {
  __IO uint32_t CPUID;                    /*!< CPUID Base Register */
  __IO uint32_t ICSR;                     /*!< Interrupt Control and State Register */
  __IO uint32_t VTOR;                     /*!< Vector Table Offset Register */
  __IO uint32_t AIRCR;                    /*!< Application Interrupt and Reset Control Register */
  __IO uint32_t SCR;                      /*!< System Control Register */
  __IO uint32_t CCR;                      /*!< Configuration and Control Register */
  __IO uint32_t SHPR[3];                  /*!< System Handler Priority Registers (4-7, 8-11, 12-15) */
  __IO uint32_t SHCSR;                    /*!< System Handler Control and State Register */
  __IO uint32_t CFSR;                     /*!< Configurable Fault Status Register */
  __IO uint32_t HFSR;                     /*!< HardFault Status Register */
  __IO uint32_t DFSR;                     /*!< Debug Fault Status Register */
  __IO uint32_t MMFAR;                    /*!< MemManage Fault Address Register */
  __IO uint32_t BFAR;                     /*!< BusFault Address Register */
  __IO uint32_t AFSR;                     /*!< Auxiliary Fault Status Register */
} SCB_Type;

#define SCS_BASE  (0xE000E000)            /*!< System Control Space Base Address */
#define SCB_BASE  (SCS_BASE + 0x0D00)     /*!< System Control Block Base Address */
#define SCB       ((SCB_Type *) SCB_BASE)

/* ========================================================================= */
/* System Timer (SysTick)                                                    */
/* ========================================================================= */
typedef struct {
  __IO uint32_t CTRL;                     /*!< SysTick Control and Status Register */
  __IO uint32_t LOAD;                     /*!< SysTick Reload Value Register */
  __IO uint32_t VAL;                      /*!< SysTick Current Value Register */
  __I  uint32_t CALIB;                    /*!< SysTick Calibration Register */
} SysTick_Type;

#define SysTick ((SysTick_Type *) 0xE000E010)

#define SysTick_CTRL_CLKSOURCE_Pos    2
#define SysTick_CTRL_CLKSOURCE_Msk    (1UL << SysTick_CTRL_CLKSOURCE_Pos)
#define SysTick_CTRL_TICKINT_Pos      1
#define SysTick_CTRL_TICKINT_Msk      (1UL << SysTick_CTRL_TICKINT_Pos)
#define SysTick_CTRL_ENABLE_Pos       0
#define SysTick_CTRL_ENABLE_Msk       (1UL << SysTick_CTRL_ENABLE_Pos)

/* ========================================================================= */
/* Nested Vectored Interrupt Controller (NVIC)                               */
/* ========================================================================= */
typedef struct {
  __IO uint32_t ISER[8];                  /*!< Interrupt Set Enable Registers */
  uint32_t RESERVED0[24];
  __IO uint32_t ICER[8];                  /*!< Interrupt Clear Enable Registers */
  uint32_t RESERVED1[24];
  __IO uint32_t ISPR[8];                  /*!< Interrupt Set Pending Registers */
  uint32_t RESERVED2[24];
  __IO uint32_t ICPR[8];                  /*!< Interrupt Clear Pending Registers */
  uint32_t RESERVED3[24];
  __IO uint32_t IABR[8];                  /*!< Interrupt Active Bit Registers */
  uint32_t RESERVED4[56];
  __IO uint8_t  IP[240];                  /*!< Interrupt Priority Registers */
  uint32_t RESERVED5[644];
  __O  uint32_t STIR;                     /*!< Software Trigger Interrupt Register */
} NVIC_Type;

#define NVIC_BASE  (SCS_BASE + 0x0100)
#define NVIC       ((NVIC_Type *) NVIC_BASE)

#define NVIC_SetPriorityGrouping __NVIC_SetPriorityGrouping
#define NVIC_GetPriorityGrouping __NVIC_GetPriorityGrouping
#define NVIC_EnableIRQ           __NVIC_EnableIRQ
#define NVIC_DisableIRQ          __NVIC_DisableIRQ
#define NVIC_SetPriority         __NVIC_SetPriority

/* ========================================================================= */
/* SCB AIRCR bit definitions                                                 */
/* ========================================================================= */
#define SCB_AIRCR_VECTKEY_Pos     16
#define SCB_AIRCR_VECTKEY_Msk     (0xFFFFUL << SCB_AIRCR_VECTKEY_Pos)
#define SCB_AIRCR_PRIGROUP_Pos    8
#define SCB_AIRCR_PRIGROUP_Msk    (7UL << SCB_AIRCR_PRIGROUP_Pos)
#define SCB_AIRCR_SYSRESETREQ_Pos 2
#define SCB_AIRCR_SYSRESETREQ_Msk (1UL << SCB_AIRCR_SYSRESETREQ_Pos)

/* SCB CCR bit definitions */
#define SCB_CCR_UNALIGN_TRP_Pos   3
#define SCB_CCR_UNALIGN_TRP_Msk   (1UL << SCB_CCR_UNALIGN_TRP_Pos)

/* CCR aliases for compatibility */
#define SCB_CCR  SCB->CCR
#define SCB_CCSR SCB->CCR

/* ========================================================================= */
/* Interrupt Number Definitions                                              */
/* ========================================================================= */
typedef enum IRQn {
  /* Cortex-M3 Processor Exceptions Numbers */
  NonMaskableInt_IRQn    = -14,           /*!< 2 Non Maskable Interrupt */
  MemoryManagement_IRQn  = -12,           /*!< 4 Memory Management Interrupt */
  BusFault_IRQn          = -11,           /*!< 5 Bus Fault Interrupt */
  UsageFault_IRQn        = -10,           /*!< 6 Usage Fault Interrupt */
  SVCall_IRQn            = -5,            /*!< 11 SV Call Interrupt */
  DebugMonitor_IRQn      = -4,            /*!< 12 Debug Monitor Interrupt */
  PendSV_IRQn            = -2,            /*!< 14 Pend SV Interrupt */
  SysTick_IRQn           = -1,            /*!< 15 System Tick Interrupt */

  /* STM32F10x Medium-Density Specific Interrupt Numbers */
  WWDG_IRQn              = 0,             /*!< Window WatchDog Interrupt */
  PVD_IRQn               = 1,             /*!< PVD through EXTI Line detection Interrupt */
  TAMPER_IRQn            = 2,             /*!< Tamper Interrupt */
  RTC_IRQn               = 3,             /*!< RTC global Interrupt */
  FLASH_IRQn             = 4,             /*!< FLASH global Interrupt */
  RCC_IRQn               = 5,             /*!< RCC global Interrupt */
  EXTI0_IRQn             = 6,             /*!< EXTI Line0 Interrupt */
  EXTI1_IRQn             = 7,             /*!< EXTI Line1 Interrupt */
  EXTI2_IRQn             = 8,             /*!< EXTI Line2 Interrupt */
  EXTI3_IRQn             = 9,             /*!< EXTI Line3 Interrupt */
  EXTI4_IRQn             = 10,            /*!< EXTI Line4 Interrupt */
  DMA1_Channel1_IRQn     = 11,            /*!< DMA1 Channel 1 global Interrupt */
  DMA1_Channel2_IRQn     = 12,            /*!< DMA1 Channel 2 global Interrupt */
  DMA1_Channel3_IRQn     = 13,            /*!< DMA1 Channel 3 global Interrupt */
  DMA1_Channel4_IRQn     = 14,            /*!< DMA1 Channel 4 global Interrupt */
  DMA1_Channel5_IRQn     = 15,            /*!< DMA1 Channel 5 global Interrupt */
  DMA1_Channel6_IRQn     = 16,            /*!< DMA1 Channel 6 global Interrupt */
  DMA1_Channel7_IRQn     = 17,            /*!< DMA1 Channel 7 global Interrupt */
  ADC1_2_IRQn            = 18,            /*!< ADC1 and ADC2 global Interrupt */
  USB_HP_CAN1_TX_IRQn    = 19,            /*!< USB Device High Priority or CAN1 TX Interrupts */
  USB_LP_CAN1_RX0_IRQn   = 20,            /*!< USB Device Low Priority or CAN1 RX0 Interrupts */
  CAN1_RX1_IRQn          = 21,            /*!< CAN1 RX1 Interrupt */
  CAN1_SCE_IRQn          = 22,            /*!< CAN1 SCE Interrupt */
  EXTI9_5_IRQn           = 23,            /*!< External Line[9:5] Interrupts */
  TIM1_BRK_IRQn          = 24,            /*!< TIM1 Break Interrupt */
  TIM1_UP_IRQn           = 25,            /*!< TIM1 Update Interrupt */
  TIM1_TRG_COM_IRQn      = 26,            /*!< TIM1 Trigger and Commutation Interrupt */
  TIM1_CC_IRQn           = 27,            /*!< TIM1 Capture Compare Interrupt */
  TIM2_IRQn              = 28,            /*!< TIM2 global Interrupt */
  TIM3_IRQn              = 29,            /*!< TIM3 global Interrupt */
  TIM4_IRQn              = 30,            /*!< TIM4 global Interrupt */
  I2C1_EV_IRQn           = 31,            /*!< I2C1 Event Interrupt */
  I2C1_ER_IRQn           = 32,            /*!< I2C1 Error Interrupt */
  I2C2_EV_IRQn           = 33,            /*!< I2C2 Event Interrupt */
  I2C2_ER_IRQn           = 34,            /*!< I2C2 Error Interrupt */
  SPI1_IRQn              = 35,            /*!< SPI1 global Interrupt */
  SPI2_IRQn              = 36,            /*!< SPI2 global Interrupt */
  USART1_IRQn            = 37,            /*!< USART1 global Interrupt */
  USART2_IRQn            = 38,            /*!< USART2 global Interrupt */
  USART3_IRQn            = 39,            /*!< USART3 global Interrupt */
  EXTI15_10_IRQn         = 40,            /*!< External Line[15:10] Interrupts */
  RTCAlarm_IRQn          = 41,            /*!< RTC Alarm through EXTI Line Interrupt */
  USBWakeUp_IRQn         = 42,            /*!< USB Device WakeUp from suspend through EXTI Line Interrupt */
} IRQn_Type;

/* ========================================================================= */
/* CMSIS Intrinsic Functions                                                 */
/* ========================================================================= */
#if defined (__CC_ARM)
  #define __ASM            __asm
  #define __INLINE         __inline
#elif defined (__GNUC__)
  #define __ASM            __asm
  #define __INLINE         inline
#endif

/* No Operation */
static __INLINE void __NOP(void) { __ASM volatile ("nop"); }

/* Wait For Interrupt */
static __INLINE void __WFI(void) { __ASM volatile ("wfi"); }

/* Wait For Event */
static __INLINE void __WFE(void) { __ASM volatile ("wfe"); }

/* Send Event */
static __INLINE void __SEV(void) { __ASM volatile ("sev"); }

/* Enable IRQ Interrupts */
static __INLINE void __enable_irq(void) { __ASM volatile ("cpsie i"); }

/* Disable IRQ Interrupts */
static __INLINE void __disable_irq(void) { __ASM volatile ("cpsid i"); }

/* Reverse byte order (32-bit) */
static __INLINE uint32_t __REV(uint32_t value) {
  __ASM volatile ("rev %0, %0" : "=r" (value) : "0" (value));
  return value;
}

/* Reverse byte order (16-bit) */
static __INLINE uint32_t __REV16(uint32_t value) {
  __ASM volatile ("rev16 %0, %0" : "=r" (value) : "0" (value));
  return value;
}

/* Reverse byte order (16-bit, signed) */
static __INLINE int32_t __REVSH(int32_t value) {
  __ASM volatile ("revsh %0, %0" : "=r" (value) : "0" (value));
  return value;
}

/* Data Synchronization Barrier */
static __INLINE void __DSB(void) { __ASM volatile ("dsb 0xF"); }

/* Data Memory Barrier */
static __INLINE void __DMB(void) { __ASM volatile ("dmb 0xF"); }

/* Instruction Synchronization Barrier */
static __INLINE void __ISB(void) { __ASM volatile ("isb 0xF"); }

/* System Reset */
__attribute__((used)) static __INLINE void NVIC_SystemReset(void) {
  __DSB();
  SCB->AIRCR = ((0x5FA << SCB_AIRCR_VECTKEY_Pos) | SCB_AIRCR_SYSRESETREQ_Msk);
  __DSB();
  while(1);
}

/* Get Priority Mask */
static __INLINE uint32_t __get_PRIMASK(void) {
  uint32_t result;
  __ASM volatile ("mrs %0, primask" : "=r" (result));
  return result;
}

/* Set Priority Mask */
static __INLINE void __set_PRIMASK(uint32_t priMask) {
  __ASM volatile ("msr primask, %0" : : "r" (priMask) : "memory");
}

/* Get CONTROL register */
static __INLINE uint32_t __get_CONTROL(void) {
  uint32_t result;
  __ASM volatile ("mrs %0, control" : "=r" (result));
  return result;
}

/* Set CONTROL register */
static __INLINE void __set_CONTROL(uint32_t control) {
  __ASM volatile ("msr control, %0" : : "r" (control) : "memory");
}

/* ========================================================================= */
/* NVIC Function Implementations                                             */
/* ========================================================================= */

/* Set Priority Grouping */
static __INLINE void __NVIC_SetPriorityGrouping(uint32_t PriorityGroup) {
  uint32_t reg_value;
  reg_value = SCB->AIRCR;
  reg_value &= ~(SCB_AIRCR_VECTKEY_Msk | SCB_AIRCR_PRIGROUP_Msk);
  reg_value = (reg_value | ((uint32_t)0x5FA << SCB_AIRCR_VECTKEY_Pos) | (PriorityGroup << SCB_AIRCR_PRIGROUP_Pos));
  SCB->AIRCR = reg_value;
}

/* Get Priority Grouping */
static __INLINE uint32_t __NVIC_GetPriorityGrouping(void) {
  return ((SCB->AIRCR & SCB_AIRCR_PRIGROUP_Msk) >> SCB_AIRCR_PRIGROUP_Pos);
}

/* Enable External Interrupt */
static __INLINE void __NVIC_EnableIRQ(IRQn_Type IRQn) {
  NVIC->ISER[((uint32_t)(IRQn) >> 5)] = (1 << ((uint32_t)(IRQn) & 0x1F));
}

/* Disable External Interrupt */
static __INLINE void __NVIC_DisableIRQ(IRQn_Type IRQn) {
  NVIC->ICER[((uint32_t)(IRQn) >> 5)] = (1 << ((uint32_t)(IRQn) & 0x1F));
}

/* Set Interrupt Priority */
static __INLINE void __NVIC_SetPriority(IRQn_Type IRQn, uint32_t priority) {
  if(IRQn < 0) {
    SCB->SHPR[((uint32_t)(IRQn) & 0xF)-4] = ((priority << (8 - 4)) & 0xff);
  } else {
    NVIC->IP[(uint32_t)(IRQn)] = ((priority << (8 - 4)) & 0xff);
  }
}

/* System Reset */
static __INLINE void __NVIC_SystemReset(void) {
  __DSB();
  SCB->AIRCR  = ((0x5FA << SCB_AIRCR_VECTKEY_Pos) | SCB_AIRCR_SYSRESETREQ_Msk);
  __DSB();
  while(1) { __NOP(); }
}

/* ========================================================================= */
/* SysTick Configuration Function                                            */
/* ========================================================================= */
static __INLINE uint32_t SysTick_Config(uint32_t ticks) {
  if ((ticks - 1) > 0xFFFFFF) return 1;
  SysTick->LOAD = ticks - 1;
  __NVIC_SetPriority(SysTick_IRQn, (1<<4) - 1);
  SysTick->VAL = 0;
  SysTick->CTRL = SysTick_CTRL_CLKSOURCE_Msk | SysTick_CTRL_TICKINT_Msk | SysTick_CTRL_ENABLE_Msk;
  return 0;
}

#endif /* __CORE_CM3_H */