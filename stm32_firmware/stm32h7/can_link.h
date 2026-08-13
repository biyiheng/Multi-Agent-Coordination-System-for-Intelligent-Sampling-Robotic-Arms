/**
  ******************************************************************************
  * @file    stm32h7/can_link.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-08-10
  * @brief   CAN 通信层头文件 (STM32H7 HAL 参考骨架)
  *
  *          工业级升级规划 §2.3 / S2: CAN 1Mbps 总线移植 + CRC32 校验 +
  *          超时重发 + 确定性调度 (帧 ID 优先级仲裁, 急停帧最高优先级)。
  *          本文件为面向 STM32H7 的迁移参考骨架, 接口与现有 F103 工程
  *          SRC/can/y_can 保持一致。
  *
  *          帧格式 (8 字节数据):
  *            byte[0..len-1]  有效负载
  *            byte[len]       CRC32 低 8 位 (校验覆盖 负载+长度)
  *
  *          帧 ID 优先级映射 (ID 越小优先级越高, CAN 仲裁保证确定性):
  *            0x0000xx 系统/急停 (最高优先级)
  *            0x0001xx 关节位置/速度闭环
  *            0x0002xx 传感器/遥测
  *            0x0003xx 视觉/诊断
  ******************************************************************************
  */

#ifndef __CAN_LINK_H
#define __CAN_LINK_H

#include "stm32h7xx_hal.h"
#include <stdint.h>

/* 波特率与位时序 (1Mbps, APB1=100MHz -> prescaler=5, 1tq+15tq+2tq) */
#define CANLINK_SJW          CAN_SJW_1TQ
#define CANLINK_BS1          CAN_BS1_15TQ
#define CANLINK_BS2          CAN_BS2_2TQ
#define CANLINK_PRESCALER    5

/* 最大数据长度 (CAN 经典帧 8 字节) */
#define CANLINK_MAX_DATA     8
/* CRC 尾字节: 有效负载 + 长度 字节的 CRC32 低 8 位 */
#define CANLINK_CRC_FOOTER   1
/* 最大重发次数 */
#define CANLINK_MAX_RETRY    3
/* 发送超时 (ms) */
#define CANLINK_TX_TIMEOUT   10

/* 帧优先级类别 (对应 ID 高字节) */
#define CANLINK_PRIO_SYSTEM  0x00  /* 急停/系统 */
#define CANLINK_PRIO_JOINT   0x10  /* 关节闭环 */
#define CANLINK_PRIO_SENSOR  0x20  /* 传感器/遥测 */
#define CANLINK_PRIO_VISION  0x30  /* 视觉/诊断 */

/* 帧类型 (对应 ID 低字节高位) */
#define CANLINK_TYPE_CMD     0x00  /* 命令帧 */
#define CANLINK_TYPE_ACK     0x08  /* 应答帧 */
#define CANLINK_TYPE_EMERG   0x0F  /* 急停帧 */

/**
  * @brief  CAN 链路状态
  */
typedef struct {
    CAN_HandleTypeDef *hcan;    /* HAL CAN 句柄 */
    uint32_t filter_bank;       /* 过滤器组号 */
    uint8_t  use_ext_id;        /* 1=扩展ID, 0=标准ID */
    uint32_t tx_total;          /* 发送总帧数 */
    uint32_t tx_retry;          /* 重发次数 */
    uint32_t tx_fail;           /* 发送失败次数 */
    uint32_t rx_total;          /* 接收总帧数 */
    uint32_t rx_crc_fail;       /* CRC 校验失败次数 */
    uint8_t  initialized;       /* 初始化标志 */
} can_link_t;

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  初始化 CAN 链路
  * @param  link: 链路句柄
  * @param  hcan: HAL CAN 句柄
  * @param  use_ext_id: 1=扩展ID, 0=标准ID
  * @retval HAL_StatusTypeDef
  */
HAL_StatusTypeDef can_link_init(can_link_t *link, CAN_HandleTypeDef *hcan,
                                uint8_t use_ext_id);

/**
  * @brief  发送数据帧 (带 CRC32 + 超时重发)
  * @param  link: 链路句柄
  * @param  prio: 优先级类别 (CANLINK_PRIO_*)
  * @param  node_id: 节点号 (0-127, 填入 ID 低字节)
  * @param  data: 负载数据 (1-7 字节, 留 1 字节给 CRC)
  * @param  len: 负载长度 (1-7)
  * @retval HAL_StatusTypeDef
  */
HAL_StatusTypeDef can_link_send(can_link_t *link, uint8_t prio,
                                uint8_t node_id, uint8_t *data, uint8_t len);

/**
  * @brief  接收并校验数据帧
  * @param  link: 链路句柄
  * @param  rx_id: 输出帧 ID
  * @param  data: 输出负载
  * @param  len: 输出负载长度
  * @retval HAL_StatusTypeDef (HAL_ERROR = 无帧或 CRC 失败)
  */
HAL_StatusTypeDef can_link_receive(can_link_t *link, uint32_t *rx_id,
                                   uint8_t *data, uint8_t *len);

/**
  * @brief  发送急停帧 (最高优先级, 无重发, 保证低延迟)
  * @param  link: 链路句柄
  * @retval HAL_StatusTypeDef
  */
HAL_StatusTypeDef can_link_emergency_stop(can_link_t *link);

/**
  * @brief  计算 CRC32 (IEEE 802.3 多项式 0xEDB88320)
  * @param  data: 数据指针
  * @param  len: 数据长度
  * @retval CRC32 校验值
  */
uint32_t can_link_crc32(const uint8_t *data, uint32_t len);

#endif /* __CAN_LINK_H */
