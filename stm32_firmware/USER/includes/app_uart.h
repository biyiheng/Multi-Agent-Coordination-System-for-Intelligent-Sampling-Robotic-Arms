/****************************************************************************
 *	@笔者	：	Q
 *	@日期	：	2026年7月23日
 *	@所属	：	杭州友辉科技
 *	@功能	：	UART应用层 - 管理三个串口的接收/发送/转发
 *           UART1: RPi ↔ STM32 命令通信
 *           UART2: STM32 ↔ OpenMV 视觉数据
 *           UART3: STM32 → 总线舵机链
 ****************************************************************************/

#ifndef _APP_UART_H_
#define _APP_UART_H_

#include "main.h"

/* UART配置 ---------------------------------------------------------------*/
#define UART1_BAUDRATE      115200      /* RPi 通信波特率 */
#define UART2_BAUDRATE      115200      /* OpenMV 通信波特率 */
#define UART3_BAUDRATE      115200      /* 舵机通信波特率 */

#define UART1_RX_BUF_SIZE   256         /* UART1接收缓冲区大小 */
#define UART2_RX_BUF_SIZE   256         /* UART2接收缓冲区大小 */
#define UART3_TX_BUF_SIZE   512         /* UART3发送缓冲区大小 */

/* 应用层接收缓冲区 (与驱动层 uart_receive_buf 区分) */
extern u8  app_uart1_rx_buf[UART1_RX_BUF_SIZE];
extern u8  app_uart2_rx_buf[UART2_RX_BUF_SIZE];
extern u16 app_uart1_rx_len;
extern u16 app_uart2_rx_len;

/* 函数声明 ---------------------------------------------------------------*/

/* 初始化所有UART */
void app_uart_init(void);

/* UART1 接收处理 (主循环中调用) */
void app_uart1_process(void);

/* UART1 发送字符串到RPi */
void app_uart1_send_str(u8 *s);

/* UART1 发送响应帧 */
void app_uart1_send_response(const char *cmd, const char *status, const char *data);

/* UART2 发送命令到OpenMV */
void app_uart2_send_str(u8 *s);

/* UART2 接收处理 (主循环中调用) */
void app_uart2_process(void);

/* UART3 发送命令到舵机链 */
void app_uart3_send_str(u8 *s);

/* 获取UART1接收缓冲状态 */
u8 app_uart1_data_ready(void);

/* 获取UART2接收缓冲状态 */
u8 app_uart2_data_ready(void);

/* 清空接收缓冲 */
void app_uart1_flush(void);
void app_uart2_flush(void);

#endif /* _APP_UART_H_ */