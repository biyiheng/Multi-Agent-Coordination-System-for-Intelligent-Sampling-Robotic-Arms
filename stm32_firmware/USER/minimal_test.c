/**
 * Minimal test firmware - sends boot message then blinks LED
 * Uses internal HSI clock (8MHz) to avoid HSE crystal issues
 * UART1 at 115200 baud
 * LED on PB13 (active low)
 */

#include "stm32f10x.h"
#include "stm32f10x_gpio.h"
#include "stm32f10x_rcc.h"
#include "stm32f10x_usart.h"
#include "stm32f10x_flash.h"

/* Simple delay using SysTick */
volatile uint32_t tick = 0;

void SysTick_Handler(void) {
    tick++;
}

void delay_ms(uint32_t ms) {
    uint32_t start = tick;
    while ((tick - start) < ms) { }
}

void uart_putc(char c) {
    while (!(USART1->SR & USART_SR_TXE)) { }
    USART1->DR = c;
}

void uart_puts(const char *s) {
    while (*s) {
        uart_putc(*s++);
    }
}

int main(void) {
    /* Use HSI directly (8MHz) - most reliable */
    /* SystemInit() already configured clock, but let's reconfigure for safety */
    
    /* Configure HSI as system clock */
    RCC->CR |= RCC_CR_HSION;
    while (!(RCC->CR & RCC_CR_HSIRDY)) { }
    
    /* Set HSI as system clock directly (bypass PLL for reliability) */
    RCC->CFGR &= ~RCC_CFGR_SW;
    RCC->CFGR |= RCC_CFGR_SW_HSI;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_HSI) { }
    
    /* Disable PLL and HSE to save power */
    RCC->CR &= ~(RCC_CR_PLLON | RCC_CR_HSEON);
    
    /* Update SystemCoreClock */
    SystemCoreClock = 8000000;
    
    /* Configure SysTick at 1ms */
    SysTick_Config(SystemCoreClock / 1000);
    
    /* Enable GPIO clocks */
    RCC->APB2PeriphClockCmd(RCC_APB2Periph_GPIOB | RCC_APB2Periph_GPIOA | 
                            RCC_APB2Periph_USART1 | RCC_APB2Periph_AFIO, ENABLE);
    
    /* Configure LED (PB13) */
    GPIO_InitTypeDef gpio;
    gpio.GPIO_Pin = GPIO_Pin_13;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    GPIO_Init(GPIOB, &gpio);
    GPIO_SetBits(GPIOB, GPIO_Pin_13);  /* LED off (active low) */
    
    /* Configure UART1 TX (PA9) */
    gpio.GPIO_Pin = GPIO_Pin_9;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &gpio);
    
    /* Configure UART1 RX (PA10) */
    gpio.GPIO_Pin = GPIO_Pin_10;
    gpio.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_Init(GPIOA, &gpio);
    
    /* Configure UART1 */
    USART_InitTypeDef usart;
    usart.USART_BaudRate = 115200;
    usart.USART_WordLength = USART_WordLength_8b;
    usart.USART_StopBits = USART_StopBits_1;
    usart.USART_Parity = USART_Parity_No;
    usart.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    usart.USART_Mode = USART_Mode_Tx | USART_Mode_Rx;
    USART_Init(USART1, &usart);
    USART_Cmd(USART1, ENABLE);
    
    /* Send boot message */
    uart_puts("\r\n#BOOT:HSI,8MHz,115200!\r\n");
    
    /* Main loop - blink LED */
    uint32_t last_blink = 0;
    while (1) {
        if ((tick - last_blink) >= 500) {
            last_blink = tick;
            GPIO_WriteBit(GPIOB, GPIO_Pin_13, 
                (BitAction)(1 - GPIO_ReadOutputDataBit(GPIOB, GPIO_Pin_13)));
        }
    }
}