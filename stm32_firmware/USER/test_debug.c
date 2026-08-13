/**
 * Debug test firmware: stores debug info in RAM for bootloader readback
 * HSI 8MHz, no PLL, UART1 at 115200
 */
#include "stm32f10x.h"

/* Debug structure in RAM (at a known offset from RAM start) */
#define DEBUG_MAGIC     0xDEB06A55
#define DEBUG_ADDR      0x20000100  /* Fixed address in RAM for debug data */

typedef struct {
    uint32_t magic;          /* 0x20000100: Magic number to confirm firmware ran */
    uint32_t stage;          /* 0x20000104: Current stage counter */
    uint32_t rcc_cr;         /* 0x20000108: RCC_CR value */
    uint32_t rcc_cfgr;       /* 0x2000010C: RCC_CFGR value */
    uint32_t rcc_apb2enr;    /* 0x20000110: RCC_APB2ENR value */
    uint32_t gpioa_crh;      /* 0x20000114: GPIOA_CRH value */
    uint32_t gpiob_crh;      /* 0x20000118: GPIOB_CRH value */
    uint32_t usart1_sr;      /* 0x2000011C: USART1_SR value */
    uint32_t usart1_brr;     /* 0x20000120: USART1_BRR value */
    uint32_t usart1_cr1;     /* 0x20000124: USART1_CR1 value */
    uint32_t systick_val;    /* 0x20000128: SysTick counter */
    uint32_t loop_count;     /* 0x2000012C: Main loop iterations */
    uint32_t checksum;       /* 0x20000130: Simple XOR checksum */
} debug_t;

volatile debug_t * const dbg = (debug_t *)DEBUG_ADDR;
uint32_t SystemCoreClock = 8000000;
volatile uint32_t g_systick = 0;

void uart_send_char(char c) {
    while ((USART1->SR & USART_SR_TXE) == 0);
    USART1->DR = c;
}

void uart_send_str(const char *s) {
    while (*s) uart_send_char(*s++);
}

void SysTick_Handler(void) {
    g_systick++;
    dbg->systick_val = g_systick;
}

/* Minimal SystemInit: HSI only, 8MHz, NO PLL */
void SystemInit(void) {
    RCC->CR |= RCC_CR_HSION;
    while ((RCC->CR & RCC_CR_HSIRDY) == 0);

    RCC->CFGR = 0x00000000;
    FLASH->ACR &= ~FLASH_ACR_LATENCY;
    FLASH->ACR |= FLASH_ACR_LATENCY_0;

    RCC->CFGR |= RCC_CFGR_HPRE_DIV1 | RCC_CFGR_PPRE2_DIV1 | RCC_CFGR_PPRE1_DIV1;
    RCC->CFGR &= ~RCC_CFGR_SW;
    RCC->CFGR |= RCC_CFGR_SW_HSI;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_HSI);

    SystemCoreClock = 8000000;
}

int main(void) {
    /* Stage 0: Initialize debug structure */
    dbg->magic = DEBUG_MAGIC;
    dbg->stage = 0;
    dbg->loop_count = 0;

    /* Stage 1: SysTick */
    SysTick_Config(SystemCoreClock / 1000);
    dbg->stage = 1;

    /* Stage 2: Enable clocks */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_IOPBEN |
                    RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;
    dbg->rcc_apb2enr = RCC->APB2ENR;
    dbg->rcc_cr = RCC->CR;
    dbg->rcc_cfgr = RCC->CFGR;
    dbg->stage = 2;

    /* Stage 3: LED (PB13) */
    GPIOB->CRH &= ~(0xF << 20);
    GPIOB->CRH |= (0x3 << 20);
    GPIOB->BSRR = GPIO_BSRR_BS13;
    dbg->gpiob_crh = GPIOB->CRH;
    dbg->stage = 3;

    /* Stage 4: UART1 TX (PA9) */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);

    /* Stage 5: UART1 RX (PA10) */
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);
    dbg->gpioa_crh = GPIOA->CRH;
    dbg->stage = 5;

    /* Stage 6: UART1 BRR = 0x45 (115200 @ 8MHz) */
    USART1->BRR = 0x45;
    dbg->usart1_brr = USART1->BRR;
    dbg->stage = 6;

    /* Stage 7: UART1 enable */
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;
    dbg->usart1_cr1 = USART1->CR1;
    dbg->usart1_sr = USART1->SR;
    dbg->stage = 7;

    /* Stage 8: Wait for UART to stabilize */
    for (volatile uint32_t i = 0; i < 50000; i++);
    dbg->stage = 8;

    /* Stage 9: Send boot message */
    uart_send_str("\r\n=== DEBUG_FW ===\r\nBOOT:OK\r\n");
    dbg->stage = 9;

    /* Stage 10: Main loop */
    uint32_t last_blink = 0;
    dbg->stage = 10;

    while (1) {
        /* Blink LED every 500ms */
        if ((g_systick - last_blink) >= 500) {
            last_blink = g_systick;
            if (GPIOB->ODR & GPIO_ODR_ODR13) {
                GPIOB->BSRR = GPIO_BSRR_BR13;
            } else {
                GPIOB->BSRR = GPIO_BSRR_BS13;
            }
        }

        /* Echo */
        if (USART1->SR & USART_SR_RXNE) {
            char c = (char)(USART1->DR & 0xFF);
            uart_send_char(c);
        }

        dbg->loop_count++;
        dbg->usart1_sr = USART1->SR;
        dbg->usart1_cr1 = USART1->CR1;

        /* Update checksum */
        uint32_t *p = (uint32_t *)dbg;
        uint32_t cs = 0;
        for (int i = 0; i < 12; i++) {
            cs ^= p[i];
        }
        dbg->checksum = cs;
    }
}