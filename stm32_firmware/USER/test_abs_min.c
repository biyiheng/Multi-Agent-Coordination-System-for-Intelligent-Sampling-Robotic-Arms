/**
 * ABSOLUTE MINIMAL firmware for YH-K32
 * 
 * Strategy: Don't touch ANYTHING except UART TX.
 * Use bootloader's clock and UART configuration exactly as-is.
 * Just send a single character repeatedly.
 * 
 * This is the simplest possible firmware - if this doesn't work,
 * the issue is with the startup/flash/vector table.
 */
#include "stm32f10x.h"

/* No SystemInit, no SysTick, no LED, no clock config */
/* Just use whatever the bootloader set up */

/* Direct UART TX using bootloader's config */
void uart_putc(char c) {
    /* Wait for TXE (Transmit Data Register Empty) */
    while (!(USART1->SR & USART_SR_TXE));
    USART1->DR = c;
}

int main(void) {
    /* Tiny delay to let bootloader finish */
    for (volatile uint32_t i = 0; i < 500000; i++);
    
    /* Send 'U' repeatedly - simplest possible output */
    while (1) {
        uart_putc('U');
        for (volatile uint32_t i = 0; i < 500000; i++);
    }
    
    return 0;
}