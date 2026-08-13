/**
  ******************************************************************************
  * @file    stm32h7/as5048_encoder.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-08-10
  * @brief   AS5048A/B 绝对值编码器驱动头文件 (STM32H7 HAL 参考骨架)
  *
  *          工业级升级规划 §1.3 / S1: 关节输出轴加装 AS5048 高精度绝对值
  *          编码器 (14bit, 分辨率 0.0219°), 通过 SPI 读取绝对角度, 用于
  *          关节闭环反馈。本文件为面向 STM32H7 的迁移参考骨架, 接口与
  *          现有 F103 工程 SRC/encoder/y_encoder 保持一致。
  *
  *          接线 (SPI1, 典型):
  *            PA5  -> AS5048 CLK
  *            PA6  <- AS5048 MISO
  *            PA7  -> AS5048 MOSI
  *            PC4  -> AS5048 CSn (片选, 低有效)
  *            PC5  -> AS5048 PROG (可选, 写零位)
  *
  *          说明: 本骨架采用 HAL 库 (STM32H7 标准外设), 供 STM32H7 迁移
  *          阶段使用。当前工程仍为 F103 SPL 实现, 见 SRC/encoder/y_encoder.c
  ******************************************************************************
  */

#ifndef __AS5048_ENCODER_H
#define __AS5048_ENCODER_H

#include "stm32h7xx_hal.h"

/* 寄存器地址 (AS5048A/B) ------------------------------------------------------*/
#define AS5048_REG_NOP          0x0000  /* 空操作 */
#define AS5048_REG_CLEAR_ERROR  0x0001  /* 清除错误标志 */
#define AS5048_REG_PROG         0x0003  /* 编程控制 */
#define AS5048_REG_DIAG         0x3FFD  /* 诊断寄存器 */
#define AS5048_REG_MAG          0x3FFE  /* 磁场诊断 (MAG, 上10bit) */
#define AS5048_REG_ANGLE        0x3FFF  /* 角度寄存器 (14bit) */

/* 状态掩码 --------------------------------------------------------------------*/
#define AS5048_STATUS_OK        0x00    /* 正常 */
#define AS5048_STATUS_ERR       0x01    /* 错误 */

/* 命令位定义: bit15=读(0)/写(1), bit14..6=地址 */
#define AS5048_CMD_READ         0x0000
#define AS5048_CMD_WRITE        0x4000

/* 磁场报警阈值 (MAG 寄存器 11bit, 高位为溢出标志) */
#define AS5048_MAG_TOO_HIGH     0x0800  /* 磁场过强 (bit11) */
#define AS5048_MAG_TOO_LOW      0x0400  /* 磁场过弱 (bit10) */

/* 14bit 满量程与角度换算 */
#define AS5048_RAW_MAX          16384.0f
#define AS5048_DEG_PER_LSB      (360.0f / AS5048_RAW_MAX)

/**
  * @brief  AS5048 编码器设备句柄
  * @note   支持多关节: 每个关节一个句柄实例, 共享同一 SPI 总线,
  *         通过独立 CS 引脚片选。
  */
typedef struct {
    SPI_HandleTypeDef *hspi;    /* SPI 句柄 */
    GPIO_TypeDef      *cs_port; /* 片选端口 */
    uint16_t           cs_pin;  /* 片选引脚 */
    uint16_t           angle_raw;   /* 最近一次角度原始值 (0-16383) */
    float              angle_deg;   /* 最近一次角度 (度) */
    uint8_t            error_count; /* 连续错误计数 */
    uint8_t            initialized; /* 初始化完成标志 */
} as5048_t;

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  初始化 AS5048 编码器
  * @param  enc: 设备句柄
  * @param  hspi: SPI 句柄 (由 HAL_Init 配置)
  * @param  cs_port: 片选端口
  * @param  cs_pin: 片选引脚
  * @retval HAL_StatusTypeDef
  */
HAL_StatusTypeDef as5048_init(as5048_t *enc, SPI_HandleTypeDef *hspi,
                              GPIO_TypeDef *cs_port, uint16_t cs_pin);

/**
  * @brief  读取编码器绝对角度
  * @param  enc: 设备句柄
  * @param  angle_deg: 输出角度 (度, 0-360)
  * @retval HAL_StatusTypeDef (HAL_ERROR 表示读取出错或磁场异常)
  */
HAL_StatusTypeDef as5048_read_angle(as5048_t *enc, float *angle_deg);

/**
  * @brief  读取原始 14bit 值
  * @param  enc: 设备句柄
  * @param  raw: 输出原始值 (0-16383)
  * @retval HAL_StatusTypeDef
  */
HAL_StatusTypeDef as5048_read_raw(as5048_t *enc, uint16_t *raw);

/**
  * @brief  写入零位偏移 (可选, 需硬件 PROG 使能)
  * @param  enc: 设备句柄
  * @param  offset: 零位偏移 (0-16383)
  * @retval HAL_StatusTypeDef
  */
HAL_StatusTypeDef as5048_set_zero_offset(as5048_t *enc, uint16_t offset);

#endif /* __AS5048_ENCODER_H */
