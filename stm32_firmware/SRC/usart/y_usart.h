#ifndef __Y_USART_H
#define __Y_USART_H

#include "main.h"

/* UART缓冲区大小 */
#define UART_BUF_SIZE  256

/* 全局变量声明 ------------------------------------------------------------*/
extern u8  uart_receive_buf[UART_BUF_SIZE];     /* UART驱动层接收缓冲区 */
extern u16 uart1_get_ok;                         /* UART1接收状态标记 (bit15=完成, bit13-0=长度) */

/* 函数声明 ---------------------------------------------------------------*/
void uart1_init(uint32_t baudrate);              /* 初始化UART1 */
void uart3_init(uint32_t baudrate);              /* 初始化UART3 */

#endif /* __Y_USART_H */