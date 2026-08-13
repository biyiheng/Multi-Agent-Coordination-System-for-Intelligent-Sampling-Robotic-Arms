/**
  ******************************************************************************
  * @file    USER/app_config.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   系统配置管理模块实现
  *          管理系统配置参数，支持Flash持久化存储
  *          开机自动加载配置，支持恢复出厂设置
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include "app_config.h"
#include "y_flash.h"
#include "y_safety.h"
#include <string.h>

/* 全局变量定义 ----------------------------------------------------------------*/

/**
  * @brief  系统配置实例
  *          默认值在初始化时设置
  */
app_config_t app_config;

/* 默认配置常量 ----------------------------------------------------------------*/
static const app_config_t default_config = {
	.magic   = CONFIG_MAGIC,
	.version = CONFIG_VERSION,
	.servo_offsets = {0, 0, 0, 0, 0, 0},
	.baud_rate     = 115200,
	.safety_limits = {
		{500, 2500},	/* 舵机0: 底盘 */
		{500, 2500},	/* 舵机1: 肩关节 */
		{500, 2500},	/* 舵机2: 肘关节1 */
		{500, 2500},	/* 舵机3: 肘关节2 */
		{500, 2500},	/* 舵机4: 腕关节 */
		{500, 2500}		/* 舵机5: 夹爪 */
	},
	.system_name   = "智能采样机械臂",
	.default_ag_id = 0,
	.reserved      = {0}
};

/**
  * @brief  配置管理模块初始化
  * @param  无
  * @返回值 无
  * @说明   设置默认配置，尝试从Flash加载
  */
void app_config_init(void)
{
	/* 先设置默认配置 */
	memcpy(&app_config, &default_config, sizeof(app_config_t));

	/* 尝试从Flash加载配置 */
	if (app_config_load() != 0)
	{
		/* 加载失败，使用默认配置并保存 */
		app_config_save();
	}
}

/**
  * @brief  从Flash加载配置
  * @param  无
  * @返回值 0: 成功, 1: 失败(使用默认配置)
  * @说明   从Flash加载配置，验证魔数和版本
  */
uint8_t app_config_load(void)
{
	app_config_t temp_config;

	/* 从Flash读取配置 */
	if (flash_load_params(&temp_config, sizeof(app_config_t)) != 0)
	{
		return 1;	/* 读取失败 */
	}

	/* 验证魔数 */
	if (temp_config.magic != CONFIG_MAGIC)
	{
		return 1;	/* 魔数不匹配 */
	}

	/* 验证版本 */
	if (temp_config.version != CONFIG_VERSION)
	{
		return 1;	/* 版本不匹配 */
	}

	/* 复制配置 */
	memcpy(&app_config, &temp_config, sizeof(app_config_t));

	/* 应用配置到各模块 */
	{
		uint8_t i;

		/* 应用安全限位到安全模块 */
		for (i = 0; i < CONFIG_SERVO_NUM; i++)
		{
			safety_set_soft_limits(i,
				app_config.safety_limits[i][0],
				app_config.safety_limits[i][1]);
		}
	}

	return 0;
}

/**
  * @brief  保存配置到Flash
  * @param  无
  * @返回值 0: 成功, 1: 失败
  * @说明   将当前配置保存到Flash
  */
uint8_t app_config_save(void)
{
	/* 确保魔数和版本正确 */
	app_config.magic   = CONFIG_MAGIC;
	app_config.version = CONFIG_VERSION;

	/* 保存到Flash */
	if (flash_save_params(&app_config, sizeof(app_config_t)) != 0)
	{
		return 1;
	}

	return 0;
}

/**
  * @brief  恢复出厂设置
  * @param  无
  * @返回值 无
  * @说明   重置所有配置为默认值，并保存到Flash
  */
void app_config_reset(void)
{
	uint8_t i;

	/* 复制默认配置 */
	memcpy(&app_config, &default_config, sizeof(app_config_t));

	/* 擦除Flash参数区 */
	flash_erase_params();

	/* 保存默认配置 */
	app_config_save();

	/* 应用默认安全限位 */
	for (i = 0; i < CONFIG_SERVO_NUM; i++)
	{
		safety_set_soft_limits(i,
			app_config.safety_limits[i][0],
			app_config.safety_limits[i][1]);
	}
}

/**
  * @brief  设置舵机偏移量
  * @param  id: 舵机ID (0~5)
  * @param  offset: 偏移量(-500~500)
  * @返回值 无
  */
void app_config_set_servo_offset(uint8_t id, int16_t offset)
{
	if (id >= CONFIG_SERVO_NUM)
	{
		return;
	}

	/* 限制偏移量范围 */
	if (offset < -500) offset = -500;
	if (offset >  500) offset =  500;

	app_config.servo_offsets[id] = offset;
}

/**
  * @brief  获取舵机偏移量
  * @param  id: 舵机ID (0~5)
  * @返回值 偏移量
  */
int16_t app_config_get_servo_offset(uint8_t id)
{
	if (id >= CONFIG_SERVO_NUM)
	{
		return 0;
	}

	return app_config.servo_offsets[id];
}

/**
  * @brief  应用偏移量到PWM值
  * @param  id: 舵机ID
  * @param  pwm: 原始PWM值
  * @返回值 校正后的PWM值
  * @说明   将原始PWM值加上偏移量，并限制在500~2500范围内
  */
uint16_t app_config_apply_offset(uint8_t id, uint16_t pwm)
{
	int32_t corrected;

	if (id >= CONFIG_SERVO_NUM)
	{
		return pwm;
	}

	/* 应用偏移量 */
	corrected = (int32_t)pwm + app_config.servo_offsets[id];

	/* 限制范围 */
	if (corrected < 500)  corrected = 500;
	if (corrected > 2500) corrected = 2500;

	return (uint16_t)corrected;
}

/**
  * @brief  设置安全限位
  * @param  id: 舵机ID
  * @param  min: 最小PWM
  * @param  max: 最大PWM
  * @返回值 无
  */
void app_config_set_safety_limit(uint8_t id, uint16_t min, uint16_t max)
{
	if (id >= CONFIG_SERVO_NUM)
	{
		return;
	}

	if (min >= max)
	{
		return;
	}

	app_config.safety_limits[id][0] = min;
	app_config.safety_limits[id][1] = max;

	/* 同步到安全模块 */
	safety_set_soft_limits(id, min, max);
}

/**
  * @brief  获取安全限位
  * @param  id: 舵机ID
  * @param  min: 输出最小PWM
  * @param  max: 输出最大PWM
  * @返回值 无
  */
void app_config_get_safety_limit(uint8_t id, uint16_t *min, uint16_t *max)
{
	if (id >= CONFIG_SERVO_NUM)
	{
		*min = 0;
		*max = 0;
		return;
	}

	*min = app_config.safety_limits[id][0];
	*max = app_config.safety_limits[id][1];
}

/**
  * @brief  设置系统名称
  * @param  name: 名称字符串(最大31字符)
  * @返回值 无
  */
void app_config_set_name(char *name)
{
	if (name == NULL)
	{
		return;
	}

	strncpy(app_config.system_name, name, CONFIG_NAME_LEN - 1);
	app_config.system_name[CONFIG_NAME_LEN - 1] = '\0';
}

/**
  * @brief  获取系统名称
  * @param  无
  * @返回值 系统名称指针
  */
char* app_config_get_name(void)
{
	return app_config.system_name;
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/