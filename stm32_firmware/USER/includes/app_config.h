/**
  ******************************************************************************
  * @file    USER/includes/app_config.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   系统配置管理模块头文件
  *          管理系统配置参数，包括:
  *          - 舵机偏移量校准
  *          - 通信波特率设置
  *          - 安全限位参数
  *          - 系统名称标识
  *          支持Flash持久化存储和恢复出厂设置
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __APP_CONFIG_H
#define __APP_CONFIG_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"

/* 宏定义 ----------------------------------------------------------------------*/
#define CONFIG_SERVO_NUM		6			/* 舵机数量 */
#define CONFIG_NAME_LEN			32			/* 系统名称最大长度 */
#define CONFIG_MAGIC			0x43464759	/* "YFGC" 友辉配置标记 */
#define CONFIG_VERSION			0x00010000	/* 配置版本 V1.0.0 */

/* 系统配置结构体 --------------------------------------------------------------*/

/**
  * @brief  系统配置结构体
  *          包含所有可持久化的系统配置参数
  */
typedef struct
{
	uint32_t magic;							/* 配置魔数标记 */
	uint32_t version;						/* 配置版本号 */

	/* 舵机校准参数 */
	int16_t  servo_offsets[CONFIG_SERVO_NUM];	/* 舵机偏移量(正负值) */

	/* 通信参数 */
	uint32_t baud_rate;						/* UART1波特率 */

	/* 安全限位参数 */
	uint16_t safety_limits[CONFIG_SERVO_NUM][2];	/* [i][0]=min, [i][1]=max */

	/* 系统信息 */
	char     system_name[CONFIG_NAME_LEN];	/* 系统名称 */

	/* 动作组参数 */
	uint8_t  default_ag_id;					/* 默认动作组ID */

	/* 保留字段 */
	uint8_t  reserved[64];					/* 保留用于扩展 */
} app_config_t;

/* 全局变量声明 ----------------------------------------------------------------*/
extern app_config_t app_config;				/* 系统配置实例 */

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  配置管理模块初始化
  * @param  无
  * @返回值 无
  * @说明   设置默认配置，尝试从Flash加载
  */
void app_config_init(void);

/**
  * @brief  从Flash加载配置
  * @param  无
  * @返回值 0: 成功, 1: 失败(使用默认配置)
  * @说明   从Flash加载配置，如果失败则使用默认配置
  */
uint8_t app_config_load(void);

/**
  * @brief  保存配置到Flash
  * @param  无
  * @返回值 0: 成功, 1: 失败
  * @说明   将当前配置保存到Flash
  */
uint8_t app_config_save(void);

/**
  * @brief  恢复出厂设置
  * @param  无
  * @返回值 无
  * @说明   重置所有配置为默认值，并保存到Flash
  */
void app_config_reset(void);

/**
  * @brief  设置舵机偏移量
  * @param  id: 舵机ID (0~5)
  * @param  offset: 偏移量(-500~500)
  * @返回值 无
  */
void app_config_set_servo_offset(uint8_t id, int16_t offset);

/**
  * @brief  获取舵机偏移量
  * @param  id: 舵机ID (0~5)
  * @返回值 偏移量
  */
int16_t app_config_get_servo_offset(uint8_t id);

/**
  * @brief  应用偏移量到PWM值
  * @param  id: 舵机ID
  * @param  pwm: 原始PWM值
  * @返回值 校正后的PWM值
  * @说明   将原始PWM值加上偏移量，并限制在500~2500范围内
  */
uint16_t app_config_apply_offset(uint8_t id, uint16_t pwm);

/**
  * @brief  设置安全限位
  * @param  id: 舵机ID
  * @param  min: 最小PWM
  * @param  max: 最大PWM
  * @返回值 无
  */
void app_config_set_safety_limit(uint8_t id, uint16_t min, uint16_t max);

/**
  * @brief  获取安全限位
  * @param  id: 舵机ID
  * @param  min: 输出最小PWM
  * @param  max: 输出最大PWM
  * @返回值 无
  */
void app_config_get_safety_limit(uint8_t id, uint16_t *min, uint16_t *max);

/**
  * @brief  设置系统名称
  * @param  name: 名称字符串(最大31字符)
  * @返回值 无
  */
void app_config_set_name(char *name);

/**
  * @brief  获取系统名称
  * @param  无
  * @返回值 系统名称指针
  */
char* app_config_get_name(void);

#endif /* __APP_CONFIG_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/