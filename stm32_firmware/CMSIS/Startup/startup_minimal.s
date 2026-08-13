/**
 * Minimal startup code - skips SystemInit and __libc_init_array
 * Goes directly to main after basic initialization
 */
.syntax unified
.cpu cortex-m3
.fpu softvfp
.thumb

.global g_pfnVectors
.global Default_Handler

.word _sidata
.word _sdata
.word _edata
.word _sbss
.word _ebss

.section .text.Reset_Handler
.weak Reset_Handler
.type Reset_Handler, %function
Reset_Handler:
  /* Set stack pointer */
  ldr   r0, =_estack
  mov   sp, r0

  /* Copy initialized data from flash to RAM */
  ldr   r0, =_sidata
  ldr   r1, =_sdata
  ldr   r2, =_edata
  movs  r3, #0
  b     LoopCopyDataInit

CopyDataInit:
  ldr   r4, [r0, r3]
  str   r4, [r1, r3]
  adds  r3, r3, #4

LoopCopyDataInit:
  adds  r4, r1, r3
  cmp   r4, r2
  bcc   CopyDataInit

  /* Zero BSS */
  ldr   r2, =_sbss
  b     LoopFillZerobss

FillZerobss:
  movs  r3, #0
  str   r3, [r2]
  adds  r2, r2, #4

LoopFillZerobss:
  ldr   r3, =_ebss
  cmp   r2, r3
  bcc   FillZerobss

  /* SKIP SystemInit and __libc_init_array - go directly to main */
  bl    main

  /* Should never return */
  b     .

Default_Handler:
Infinite_Loop:
  b     Infinite_Loop
.size Default_Handler, .-Default_Handler

.macro def_irq_handler handler_name
  .weak \handler_name
  .thumb_set \handler_name, Default_Handler
.endm

def_irq_handler NMI_Handler
def_irq_handler HardFault_Handler
def_irq_handler MemManage_Handler
def_irq_handler BusFault_Handler
def_irq_handler UsageFault_Handler
def_irq_handler SVC_Handler
def_irq_handler DebugMon_Handler
def_irq_handler PendSV_Handler
def_irq_handler SysTick_Handler
def_irq_handler WWDG_IRQHandler
def_irq_handler PVD_IRQHandler
def_irq_handler TAMPER_IRQHandler
def_irq_handler RTC_IRQHandler
def_irq_handler FLASH_IRQHandler
def_irq_handler RCC_IRQHandler
def_irq_handler EXTI0_IRQHandler
def_irq_handler EXTI1_IRQHandler
def_irq_handler EXTI2_IRQHandler
def_irq_handler EXTI3_IRQHandler
def_irq_handler EXTI4_IRQHandler
def_irq_handler DMA1_Channel1_IRQHandler
def_irq_handler DMA1_Channel2_IRQHandler
def_irq_handler DMA1_Channel3_IRQHandler
def_irq_handler DMA1_Channel4_IRQHandler
def_irq_handler DMA1_Channel5_IRQHandler
def_irq_handler DMA1_Channel6_IRQHandler
def_irq_handler DMA1_Channel7_IRQHandler
def_irq_handler ADC1_2_IRQHandler
def_irq_handler USB_HP_CAN1_TX_IRQHandler
def_irq_handler USB_LP_CAN1_RX0_IRQHandler
def_irq_handler CAN1_RX1_IRQHandler
def_irq_handler CAN1_SCE_IRQHandler
def_irq_handler EXTI9_5_IRQHandler
def_irq_handler TIM1_BRK_IRQHandler
def_irq_handler TIM1_UP_IRQHandler
def_irq_handler TIM1_TRG_COM_IRQHandler
def_irq_handler TIM1_CC_IRQHandler
def_irq_handler TIM2_IRQHandler
def_irq_handler TIM3_IRQHandler
def_irq_handler TIM4_IRQHandler
def_irq_handler I2C1_EV_IRQHandler
def_irq_handler I2C1_ER_IRQHandler
def_irq_handler I2C2_EV_IRQHandler
def_irq_handler I2C2_ER_IRQHandler
def_irq_handler SPI1_IRQHandler
def_irq_handler SPI2_IRQHandler
def_irq_handler USART1_IRQHandler
def_irq_handler USART2_IRQHandler
def_irq_handler USART3_IRQHandler
def_irq_handler EXTI15_10_IRQHandler
def_irq_handler RTCAlarm_IRQHandler
def_irq_handler USBWakeUp_IRQHandler

.section .isr_vector, "a", %progbits
.type g_pfnVectors, %object
.size g_pfnVectors, .-g_pfnVectors

g_pfnVectors:
  .word _estack
  .word Reset_Handler
  .word NMI_Handler
  .word HardFault_Handler
  .word MemManage_Handler
  .word BusFault_Handler
  .word UsageFault_Handler
  .word 0
  .word 0
  .word 0
  .word 0
  .word SVC_Handler
  .word DebugMon_Handler
  .word 0
  .word PendSV_Handler
  .word SysTick_Handler
  .word WWDG_IRQHandler
  .word PVD_IRQHandler
  .word TAMPER_IRQHandler
  .word RTC_IRQHandler
  .word FLASH_IRQHandler
  .word RCC_IRQHandler
  .word EXTI0_IRQHandler
  .word EXTI1_IRQHandler
  .word EXTI2_IRQHandler
  .word EXTI3_IRQHandler
  .word EXTI4_IRQHandler
  .word DMA1_Channel1_IRQHandler
  .word DMA1_Channel2_IRQHandler
  .word DMA1_Channel3_IRQHandler
  .word DMA1_Channel4_IRQHandler
  .word DMA1_Channel5_IRQHandler
  .word DMA1_Channel6_IRQHandler
  .word DMA1_Channel7_IRQHandler
  .word ADC1_2_IRQHandler
  .word USB_HP_CAN1_TX_IRQHandler
  .word USB_LP_CAN1_RX0_IRQHandler
  .word CAN1_RX1_IRQHandler
  .word CAN1_SCE_IRQHandler
  .word EXTI9_5_IRQHandler
  .word TIM1_BRK_IRQHandler
  .word TIM1_UP_IRQHandler
  .word TIM1_TRG_COM_IRQHandler
  .word TIM1_CC_IRQHandler
  .word TIM2_IRQHandler
  .word TIM3_IRQHandler
  .word TIM4_IRQHandler
  .word I2C1_EV_IRQHandler
  .word I2C1_ER_IRQHandler
  .word I2C2_EV_IRQHandler
  .word I2C2_ER_IRQHandler
  .word SPI1_IRQHandler
  .word SPI2_IRQHandler
  .word USART1_IRQHandler
  .word USART2_IRQHandler
  .word USART3_IRQHandler
  .word EXTI15_10_IRQHandler
  .word RTCAlarm_IRQHandler
  .word USBWakeUp_IRQHandler