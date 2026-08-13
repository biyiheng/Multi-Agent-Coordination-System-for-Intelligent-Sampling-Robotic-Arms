/**
  ******************************************************************************
  * @file    SRC/sensor/y_sensor.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   传感器驱动模块头文件
  *          支持传感器类型：
  *          - DHT11 温湿度传感器 (PA0)
  *          - HC-SR04 超声波测距 (PB0/TRIG, PB1/ECHO)
  *          - ADC 电压监测 (PA4)
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __Y_SENSOR_H
#define __Y_SENSOR_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"
#include "stm32f10x_gpio.h"
#include "stm32f10x_rcc.h"
#include "stm32f10x_adc.h"

/* 宏定义 ----------------------------------------------------------------------*/

/* 传感器类型枚举 --------------------------------------------------------------*/

/**
  * @brief  传感器类型枚举
  */
typedef enum
{
	SENSOR_TEMP     = 0,					/* 温度传感器 */
	SENSOR_HUMIDITY = 1,					/* 湿度传感器 */
	SENSOR_DISTANCE = 2,					/* 距离传感器 */
	SENSOR_VOLTAGE  = 3						/* 电压传感器 */
} sensor_type_t;

/* 传感器数据结构体 ------------------------------------------------------------*/

/**
  * @brief  传感器数据综合结构体
  */
typedef struct
{
	float    temperature;					/* 温度值 (摄氏度) */
	float    humidity;						/* 湿度值 (%RH) */
	float    distance;						/* 距离值 (cm) */
	float    voltage;						/* 电压值 (V) */
	uint32_t timestamp;						/* 数据采集时间戳 */
} sensor_data_t;

/* 全局变量声明 ----------------------------------------------------------------*/
extern sensor_data_t sensor_data;			/* 传感器数据实例 */

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  传感器模块初始化
  * @param  无
  * @返回值 无
  * @说明   初始化所有传感器的GPIO和ADC
  */
void sensor_init(void);

/**
  * @brief  读取温度值
  * @param  无
  * @返回值 温度值(摄氏度)
  * @说明   从DHT11读取温度数据
  */
float sensor_read_temp(void);

/**
  * @brief  读取湿度值
  * @param  无
  * @返回值 湿度值(%RH)
  * @说明   从DHT11读取湿度数据
  */
float sensor_read_humidity(void);

/**
  * @brief  读取距离值
  * @param  无
  * @返回值 距离值(cm)
  * @说明   从HC-SR04超声波传感器读取距离
  */
float sensor_read_distance(void);

/**
  * @brief  读取电压值
  * @param  无
  * @返回值 电压值(V)
  * @说明   从ADC输入读取系统电压
  */
float sensor_read_voltage(void);

/**
  * @brief  读取所有传感器数据
  * @param  无
  * @返回值 无
  * @说明   一次性读取所有传感器数据并更新sensor_data结构体
  */
void sensor_read_all(void);

/**
  * @brief  获取传感器数据指针
  * @param  无
  * @返回值 传感器数据指针
  */
sensor_data_t* sensor_get_data(void);

#endif /* __Y_SENSOR_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/