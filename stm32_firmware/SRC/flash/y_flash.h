/**
  ******************************************************************************
  * @file    SRC/flash/y_flash.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   Flash存储模块头文件
  *          使用STM32内部Flash存储系统参数和动作组数据
  *          存储位置: 最后1KB(page 127)用于参数存储
  *          磨损均衡: 2页轮转存储
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __Y_FLASH_H
#define __Y_FLASH_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"
#include "stm32f10x_flash.h"

/* 宏定义 ----------------------------------------------------------------------*/

/* STM32F103C8T6 Flash参数 */
#define FLASH_PAGE_SIZE			1024		/* 页大小(字节) - 中容量产品 */
#define FLASH_TOTAL_SIZE		65536		/* 总Flash大小(字节) - 64KB */
#define FLASH_PARAM_PAGE1		126			/* 参数页1 (0x0801F800) */
#define FLASH_PARAM_PAGE2		127			/* 参数页2 (0x0801FC00) */
#define FLASH_PARAM_ADDR1		0x0801F800	/* 参数页1起始地址 */
#define FLASH_PARAM_ADDR2		0x0801FC00	/* 参数页2起始地址 */
#define FLASH_ACTION_ADDR		0x0801E000	/* 动作组存储起始地址 */

/* 参数存储结构体大小 */
#define FLASH_PARAM_SIZE		256			/* 参数区最大字节数 */

/* 存储标记 */
#define FLASH_MAGIC_NUMBER		0x59484653	/* "SFHY" 友辉标记 */

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  Flash存储模块初始化
  * @param  无
  * @返回值 无
  * @说明   检查Flash存储区是否有效，加载参数
  */
void flash_init(void);

/**
  * @brief  保存系统参数到Flash
  * @param  data: 参数数据指针
  * @param  size: 数据大小(字节)
  * @返回值 0: 成功, 1: 失败
  * @说明   使用磨损均衡策略，在两个页之间轮转存储
  */
uint8_t flash_save_params(void *data, uint16_t size);

/**
  * @brief  从Flash加载系统参数
  * @param  data: 参数数据缓冲区指针
  * @param  size: 数据大小(字节)
  * @返回值 0: 成功, 1: 失败
  * @说明   从最新的有效页加载参数数据
  */
uint8_t flash_load_params(void *data, uint16_t size);

/**
  * @brief  擦除参数存储区
  * @param  无
  * @返回值 0: 成功, 1: 失败
  * @说明   擦除两个参数页
  */
uint8_t flash_erase_params(void);

/**
  * @brief  保存动作组到Flash
  * @param  group_id: 动作组ID
  * @param  data: 动作组数据指针
  * @param  size: 数据大小(字节)
  * @返回值 0: 成功, 1: 失败
  */
uint8_t flash_save_action_group(uint8_t group_id, void *data, uint16_t size);

/**
  * @brief  从Flash加载动作组
  * @param  group_id: 动作组ID
  * @param  data: 数据缓冲区指针
  * @param  size: 数据大小(字节)
  * @返回值 0: 成功, 1: 失败
  */
uint8_t flash_load_action_group(uint8_t group_id, void *data, uint16_t size);

/**
  * @brief  擦除动作组存储区
  * @param  无
  * @返回值 0: 成功, 1: 失败
  */
uint8_t flash_erase_action_groups(void);

/**
  * @brief  获取Flash存储状态
  * @param  无
  * @返回值 0: 正常, 1: 未初始化, 2: 错误
  */
uint8_t flash_get_status(void);

#endif /* __Y_FLASH_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/