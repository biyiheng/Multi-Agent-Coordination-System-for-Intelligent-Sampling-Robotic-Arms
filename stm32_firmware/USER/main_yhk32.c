/**
 * YH-K32 机械臂主固件 - 适配版
 * 
 * 关键发现：Bootloader 的有效波特率是 38400 (不是 115200)
 * 本固件使用 HSI 8MHz + 38400 8N1 UART 配置
 * 
 * 使用 startup_minimal.s (跳过 SystemInit 和 __libc_init_array)
 */
#include "stm32f10x.h"

/* 全局变量 */
volatile uint32_t g_systick = 0;
uint32_t SystemCoreClock = 8000000;  /* HSI 8MHz */

/* ---- 简单时钟初始化 (HSI 8MHz) ---- */
void simple_clock_init(void) {
    /* 确保 HSI 已启用 */
    RCC->CR |= RCC_CR_HSION;
    while ((RCC->CR & RCC_CR_HSIRDY) == 0);
    
    /* 切换到 HSI */
    RCC->CFGR &= ~RCC_CFGR_SW;
    while ((RCC->CFGR & RCC_CFGR_SWS) != 0x00);
    
    /* 禁用 PLL 和 HSE (省电) */
    RCC->CR &= ~(RCC_CR_PLLON | RCC_CR_HSEON);
    
    /* 设置 AHB/APB 预分频器 */
    RCC->CFGR &= ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2);
    RCC->CFGR |= RCC_CFGR_PPRE1_DIV2;  /* APB1 = HCLK/2 = 4MHz */
    /* APB2 = HCLK = 8MHz, AHB = SYSCLK = 8MHz (default 0) */
    
    SystemCoreClock = 8000000;
}

/* ---- SysTick 处理器 ---- */
void SysTick_Handler(void) {
    g_systick++;
}

/* ---- UART 函数 ---- */
void uart1_send_char(char c) {
    while (!(USART1->SR & USART_SR_TXE));
    USART1->DR = c;
}

void uart1_send_str(const char *s) {
    while (*s) uart1_send_char(*s++);
}

/* ---- UART 初始化 (38400 8N1 @ 8MHz) ---- */
void uart1_init_38400(void) {
    /* 使能 GPIOA, USART1, AFIO 时钟 */
    RCC->APB2ENR |= RCC_APB2ENR_IOPAEN | RCC_APB2ENR_USART1EN | RCC_APB2ENR_AFIOEN;
    
    /* PA9: TX - AF 推挽输出, 50MHz */
    GPIOA->CRH &= ~(0xF << 4);
    GPIOA->CRH |= (0xB << 4);
    
    /* PA10: RX - 浮空输入 */
    GPIOA->CRH &= ~(0xF << 8);
    GPIOA->CRH |= (0x4 << 8);
    
    /* 禁用 USART 以配置 BRR */
    USART1->CR1 &= ~USART_CR1_UE;
    
    /* BRR for 38400 @ 8MHz: 8000000/(16*38400) = 13.02 → BRR = 0xD0 */
    USART1->BRR = 0xD0;  /* mantissa=13, fraction=0 */
    
    /* CR2: 1 stop bit */
    USART1->CR2 = 0;
    
    /* CR3: 无流控 */
    USART1->CR3 = 0;
    
    /* CR1: 8N1, TX+RX 使能, USART 使能 */
    USART1->CR1 = USART_CR1_UE | USART_CR1_TE | USART_CR1_RE;
}

/* ---- LED 函数 (PB13, 低电平有效) ---- */
void led_init(void) {
    RCC->APB2ENR |= RCC_APB2ENR_IOPBEN;
    GPIOB->CRH &= ~(0xF << 20);
    GPIOB->CRH |= (0x3 << 20);
    GPIOB->BSRR = GPIO_BSRR_BS13;  /* 灭 */
}

void led_on(void) {
    GPIOB->BSRR = GPIO_BSRR_BR13;
}

void led_off(void) {
    GPIOB->BSRR = GPIO_BSRR_BS13;
}

void led_toggle(void) {
    if (GPIOB->ODR & GPIO_ODR_ODR13) {
        GPIOB->BSRR = GPIO_BSRR_BR13;
    } else {
        GPIOB->BSRR = GPIO_BSRR_BS13;
    }
}

/* ---- 简易延时 ---- */
void delay_ms(uint32_t ms) {
    uint32_t start = g_systick;
    while ((g_systick - start) < ms);
}

/* ---- YH-K32 协议解析 ---- */
/* 舵机命令格式: #NNNPNNNNTNNNN! */
/* 系统命令格式: #SYS:XXXX! */
/* 多位机命令格式: {#000P1500T1000!#001P1500T1000!} */

#define CMD_BUF_SIZE 256
static char cmd_buf[CMD_BUF_SIZE];
static uint16_t cmd_len = 0;

/* 解析单个舵机命令 */
void parse_servo_cmd(const char *cmd) {
    /* 格式: #NNNPNNNNTNNNN! */
    int id, pos, time_ms;
    if (sscanf(cmd, "#%dP%dT%d!", &id, &pos, &time_ms) == 3) {
        char resp[64];
        snprintf(resp, sizeof(resp), "#SERVO:%d,POS=%d,TIME=%d,OK!\r\n", id, pos, time_ms);
        uart1_send_str(resp);
    }
}

/* 解析系统命令 */
void parse_sys_cmd(const char *cmd) {
    char resp[128];
    
    if (strncmp(cmd, "#SYS:BOOT", 9) == 0) {
        uart1_send_str("#SYS:BOOT,OK!\r\n");
    } else if (strncmp(cmd, "#SYS:INFO", 9) == 0) {
        snprintf(resp, sizeof(resp), 
            "#SYS:INFO,NAME=YH-K32_ARM,VER=1.0.0,CLK=HSI_8MHz,UART=38400_8N1,SYSTICK=%lu!\r\n",
            g_systick);
        uart1_send_str(resp);
    } else if (strncmp(cmd, "#SYS:STATUS", 11) == 0) {
        uart1_send_str("#SYS:STATUS,OK!\r\n");
    } else if (strncmp(cmd, "#SYS:PING", 9) == 0) {
        uart1_send_str("#SYS:PONG!\r\n");
    } else {
        snprintf(resp, sizeof(resp), "#SYS:UNKNOWN,%s!\r\n", cmd);
        uart1_send_str(resp);
    }
}

/* 处理接收到的命令 */
void process_command(const char *cmd) {
    if (cmd[0] == '\0') return;
    
    /* 去除尾部的 \r\n */
    char clean[CMD_BUF_SIZE];
    strncpy(clean, cmd, sizeof(clean) - 1);
    clean[sizeof(clean) - 1] = '\0';
    
    /* 去除尾部的空白 */
    int len = strlen(clean);
    while (len > 0 && (clean[len-1] == '\r' || clean[len-1] == '\n')) {
        clean[--len] = '\0';
    }
    
    if (len == 0) return;
    
    /* 判断命令类型 */
    if (clean[0] == '#') {
        if (strncmp(clean, "#SYS:", 5) == 0) {
            parse_sys_cmd(clean);
        } else if (clean[1] >= '0' && clean[1] <= '9') {
            parse_servo_cmd(clean);
        } else {
            char resp[64];
            snprintf(resp, sizeof(resp), "#ERR:UNKNOWN,%s!\r\n", clean);
            uart1_send_str(resp);
        }
    } else if (clean[0] == '$') {
        /* 系统命令 */
        if (strcmp(clean, "$DST!") == 0) {
            uart1_send_str("#SYS:STOP,OK!\r\n");
        } else if (strcmp(clean, "$RST!") == 0) {
            uart1_send_str("#SYS:RESET,OK!\r\n");
        } else {
            char resp[64];
            snprintf(resp, sizeof(resp), "#ERR:UNKNOWN_SYS,%s!\r\n", clean);
            uart1_send_str(resp);
        }
    }
}

/* ---- 主函数 ---- */
int main(void) {
    /* 1. 简单时钟初始化 */
    simple_clock_init();
    
    /* 2. SysTick 1ms */
    SysTick_Config(SystemCoreClock / 1000);
    
    /* 3. LED 初始化 */
    led_init();
    
    /* 4. UART1 初始化 (38400 8N1) */
    uart1_init_38400();
    
    /* 短暂延时 */
    for (volatile uint32_t i = 0; i < 100000; i++);
    
    /* 5. LED 闪烁 3 次表示启动 */
    for (int i = 0; i < 3; i++) {
        led_on();
        delay_ms(200);
        led_off();
        delay_ms(200);
    }
    
    /* 6. 发送启动消息 */
    uart1_send_str("\r\n=== YH-K32 ARM CONTROLLER V1.0 ===\r\n");
    uart1_send_str("#SYS:BOOT,OK!\r\n");
    uart1_send_str("#SYS:INFO,CLK=HSI_8MHz,UART=38400_8N1!\r\n");
    uart1_send_str("=== READY ===\r\n");
    
    /* 7. 主循环 */
    uint32_t last_blink = 0;
    uint32_t last_hb = 0;
    
    while (1) {
        /* LED 心跳 (1Hz) */
        if ((g_systick - last_blink) >= 500) {
            last_blink = g_systick;
            led_toggle();
        }
        
        /* 心跳消息 (每 5s) */
        if ((g_systick - last_hb) >= 5000) {
            last_hb = g_systick;
            char hb[32];
            snprintf(hb, sizeof(hb), "#SYS:HB,%lu!\r\n", g_systick / 1000);
            uart1_send_str(hb);
        }
        
        /* UART 接收处理 */
        if (USART1->SR & USART_SR_RXNE) {
            char c = (char)(USART1->DR & 0xFF);
            
            /* 收到帧结束符 '!' */
            if (c == '!') {
                if (cmd_len < CMD_BUF_SIZE - 1) {
                    cmd_buf[cmd_len++] = c;
                    cmd_buf[cmd_len] = '\0';
                }
                process_command(cmd_buf);
                cmd_len = 0;
            }
            /* 收到 '{' 开始多位机命令 */
            else if (c == '{') {
                cmd_len = 0;
                cmd_buf[0] = '\0';
            }
            /* 收到 '}' 结束多位机命令 */
            else if (c == '}') {
                if (cmd_len > 0) {
                    cmd_buf[cmd_len] = '\0';
                    /* 解析多位机命令中的每个子命令 */
                    char *p = cmd_buf;
                    while (*p) {
                        if (*p == '#') {
                            char sub[64];
                            int j = 0;
                            while (*p && *p != '!' && j < 63) {
                                sub[j++] = *p++;
                            }
                            if (*p == '!') sub[j++] = *p++;
                            sub[j] = '\0';
                            process_command(sub);
                        } else {
                            p++;
                        }
                    }
                    cmd_len = 0;
                }
            }
            /* 普通字符 */
            else if (c == '\r' || c == '\n') {
                /* 忽略换行符 */
            }
            else {
                if (cmd_len < CMD_BUF_SIZE - 1) {
                    cmd_buf[cmd_len++] = c;
                }
            }
        }
    }
    
    return 0;
}