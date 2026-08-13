/**
  ******************************************************************************
  * @file    USER/includes/app_protocol.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   应用层协议解析器头文件
  *          负责解析来自树莓派(UART1)的命令帧
  *          命令格式: #PREFIX:CMD! 或 #PREFIX:CMD:DATA!
  *          支持的命令前缀:
  *          - #ARM: 机械臂控制
  *          - #AG:  动作组管理
  *          - #SENSOR: 传感器查询
  *          - #VISION: 视觉模块(转发到OpenMV)
  *          - #SYS: 系统命令
  *          - #BUS: 原始总线舵机命令
  *          支持命令链: cmd1;cmd2;cmd3
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __APP_PROTOCOL_H
#define __APP_PROTOCOL_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"

/* 外部函数声明 ----------------------------------------------------------------*/
extern void delay_ms(uint32_t ms);      /* 毫秒延时 */

/* 宏定义 ----------------------------------------------------------------------*/
#define PROTOCOL_BUF_SIZE		256			/* 协议接收缓冲区大小 */
#define PROTOCOL_RESPONSE_SIZE	256			/* 响应缓冲区大小 */
#define PROTOCOL_MAX_CHAIN		10			/* 最大命令链长度 */

/* 命令类型枚举 ----------------------------------------------------------------*/

/**
  * @brief  协议命令类型枚举
  */
typedef enum
{
	CMD_NONE    = 0,						/* 无命令 */
	CMD_ARM     = 1,						/* 机械臂控制命令 */
	CMD_AG      = 2,						/* 动作组命令 */
	CMD_SENSOR  = 3,						/* 传感器命令 */
	CMD_VISION  = 4,						/* 视觉命令 */
	CMD_SYS     = 5,						/* 系统命令 */
	CMD_BUS     = 6,						/* 总线舵机命令 */
	CMD_YHK32_SERVO = 7,					/* YH-K32单舵机命令 */
	CMD_YHK32_MULTI = 8,					/* YH-K32多舵机命令 */
	CMD_YHK32_SYS   = 9,					/* YH-K32系统命令($DST/$RST/$DGT) */
	CMD_UNKNOWN = 0xFF						/* 未知命令 */
} cmd_type_t;

/* 协议命令结构体 --------------------------------------------------------------*/

/**
  * @brief  协议命令结构体
  */
typedef struct
{
	cmd_type_t type;						/* 命令类型 */
	char       prefix[8];					/* 命令前缀 */
	char       cmd[64];						/* 命令内容 */
	char       data[128];					/* 附加数据 */
	uint8_t    valid;						/* 命令是否有效 */
} protocol_cmd_t;

/* 全局变量声明 ----------------------------------------------------------------*/
extern protocol_cmd_t protocol_cmd;			/* 当前解析的命令 */

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  协议解析器初始化
  * @param  无
  * @返回值 无
  * @说明   初始化接收缓冲区和命令结构体
  */
void app_protocol_init(void);

/**
  * @brief  协议解析运行函数
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，处理接收到的命令
  */
void app_protocol_run(void);

/**
  * @brief  解析协议命令
  * @param  data: 接收到的数据字符串
  * @param  len: 数据长度
  * @返回值 0: 成功, 1: 失败
  * @说明   解析命令前缀和内容，填充protocol_cmd结构体
  */
uint8_t app_protocol_parse(char *data, uint16_t len);

/**
  * @brief  发送协议响应
  * @param  type: 响应类型 "OK" 或 "ERR"
  * @param  data: 响应数据
  * @返回值 无
  * @说明   格式: #CMD:type:data!
  */
void app_protocol_send_response(char *type, char *data);

/**
  * @brief  处理接收到的UART1数据
  * @param  data: 接收到的数据
  * @param  len: 数据长度
  * @返回值 无
  */
void app_protocol_receive(char *data, uint16_t len);

/**
  * @brief  获取协议状态
  * @param  无
  * @返回值 0: 空闲, 1: 忙碌
  */
uint8_t app_protocol_get_status(void);

#endif /* __APP_PROTOCOL_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/