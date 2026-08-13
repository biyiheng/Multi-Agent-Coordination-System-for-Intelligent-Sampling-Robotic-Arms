/**
 * Minimal test firmware for YH-K32 board
 * Tests: LED blink + UART1 output
 */
#include "stm32f10x.h"
#include "stm32f10x_gpio.h"
#include "stm32f10x_rcc.h"
#include "stm32f10x_usart.h"

volatile uint32_t g_systick = 0;

/* Simple UART send */
void uart_send_char(char c) {
    while ((USART1->SR & USART_SR_TXE) == 0);
    USART1->DR = c;
}

void uart_send_str(char *s) {
    while (*s) {
        uart_send_char(*s++);
    }
}

/* Simple delay using SysTick */
void delay_ms(uint32_t ms) {
    uint32_t start = g_systick;
    while ((g_systick - start) < ms);
}

/* SysTick handler */
void SysTick_Handler(void) {
    g_systick++;
}

/* Minimal main */
int main(void) {
    GPIO_InitTypeDef gpio;
    USART_InitTypeDef usart;
    
    /* ---- 1. Clock already configured by SystemInit() ---- */
    /* SystemInit() is called from startup code before main() */
    
    /* ---- 2. Configure SysTick for 1ms ---- */
    SysTick_Config(SystemCoreClock / 1000);
    
    /* ---- 3. Enable GPIO clocks ---- */
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB |
                           RCC_APB2Periph_USART1 | RCC_APB2Periph_AFIO, ENABLE);
    
    /* ---- 4. Configure LED (PB13) ---- */
    gpio.GPIO_Pin = GPIO_Pin_13;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOB, &gpio);
    GPIO_SetBits(GPIOB, GPIO_Pin_13);  /* LED off (active low) */
    
    /* ---- 5. Configure UART1 TX (PA9) ---- */
    gpio.GPIO_Pin = GPIO_Pin_9;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(GPIOA, &gpio);
    
    /* ---- 6. Configure UART1 ---- */
    usart.USART_BaudRate = 9600;  /* Try 9600 to rule out high-speed issues */
    usart.USART_WordLength = USART_WordLength_8b;
    usart.USART_StopBits = USART_StopBits_1;
    usart.USART_Parity = USART_Parity_No;
    usart.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    usart.USART_Mode = USART_Mode_Tx;
    USART_Init(USART1, &usart);
    USART_Cmd(USART1, ENABLE);
    
    /* ---- 7. Send boot message at 9600 ---- */
    uart_send_str("#TEST:BOOT,OK! CLK=");
    
    /* Send SystemCoreClock as hex */
    uint32_t clk = SystemCoreClock;
    char hex_chars[] = "0123456789ABCDEF";
    for (int i = 28; i >= 0; i -= 4) {
        uart_send_char(hex_chars[(clk >> i) & 0xF]);
    }
    uart_send_str("\r\n");
    
    /* ---- 8. Main loop: blink LED and send heartbeat ---- */
    uint32_t last_blink = 0;
    uint32_t last_msg = 0;
    
    while (1) {
        /* Blink LED every 500ms */
        if ((g_systick - last_blink) >= 500) {
            last_blink = g_systick;
            /* Toggle PB13 */
            if (GPIO_ReadOutputDataBit(GPIOB, GPIO_Pin_13)) {
                GPIO_ResetBits(GPIOB, GPIO_Pin_13);  /* LED on */
            } else {
                GPIO_SetBits(GPIOB, GPIO_Pin_13);    /* LED off */
            }
        }
        
        /* Send heartbeat every 2 seconds */
        if ((g_systick - last_msg) >= 2000) {
            last_msg = g_systick;
            uart_send_str("#TEST:HEARTBEAT!\r\n");
        }
    }
}