/**
  ******************************************************************************
  * @file    SRC/can/y_can.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-08-10
  * @brief   CAN 通信层头文件 (STM32F103 SPL 集成)
  *
  *          工业级升级规划 §2.3 / S2: CAN 1Mbps 总线移植 + CRC32 校验 +
  *          超时重发 + 确定性调度 (帧 ID 优先级仲裁, 急停帧最高优先级)。
  *          本文件为当前 F103 工程内的落地实现, 接口与 stm32h7/can_link
  *          参考骨架保持一致。
  *
  *          引脚 (经 AFIO 重映射):
  *            PB8  <- CAN1_RX
  *            PB9  -> CAN1_TX
  *          (重映射避免与 PA11/Key2 按键冲突)
  *
  *          帧格式 (8 字节数据):
  *            byte[0..len-1]  有效负载
  *            byte[len]       CRC32 低 8 位 (校验覆盖 负载+长度)
  *
  *          帧 ID 优先级映射 (ID 越小优先级越高, CAN 仲裁保证确定性):
  *            0x0000xx 系统/急停 (最高优先级)
  *            0x0010xx 关节位置/速度闭环
  *            0x0020xx 传感器/遥测
  *            0x0030xx 视觉/诊断
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __Y_CAN_H
#define __Y_CAN_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"
#include "stm32f10x_can.h"
#include "stm32f10x_gpio.h"
#include "stm32f10x_rcc.h"

/* 波特率与位时序 (1Mbps, APB1=36MHz -> prescaler=2, 18tq) */
#define CAN_BAUD_PRESCALER      2
#define CAN_BS1_TQ              CAN_BS1_13tq
#define CAN_BS2_TQ              CAN_BS2_4tq
#define CAN_SJW_TQ              CAN_SJW_1tq

/* 最大数据长度 (CAN 经典帧 8 字节) */
#define CAN_MAX_DATA            8
/* CRC 尾字节: 负载 + 长度 字节的 CRC32 低 8 位 */
#define CAN_CRC_FOOTER          1
/* 最大重发次数 */
#define CAN_MAX_RETRY           3
/* 发送超时 (轮询次数) */
#define CAN_TX_TIMEOUT          1000

/* 帧优先级类别 (对应 ID 高字节) */
#define CAN_PRIO_SYSTEM         0x00  /* 急停/系统 */
#define CAN_PRIO_JOINT          0x10  /* 关节闭环 */
#define CAN_PRIO_SENSOR         0x20  /* 传感器/遥测 */
#define CAN_PRIO_VISION         0x30  /* 视觉/诊断 */

/* 帧类型 (对应 ID 低字节高位) */
#define CAN_TYPE_CMD            0x00  /* 命令帧 */
#define CAN_TYPE_ACK            0x08  /* 应答帧 */
#define CAN_TYPE_EMERG          0x0F  /* 急停帧 */

/* 错误码 */
#define CAN_OK                   0   /* 成功 */
#define CAN_ERR_PARAM            1   /* 参数错误 */
#define CAN_ERR_INIT             2   /* 初始化失败 */
#define CAN_ERR_TIMEOUT          3   /* 发送超时 */
#define CAN_ERR_CRC              4   /* CRC 校验失败 */
#define CAN_ERR_NO_FRAME         5   /* 无待处理帧 */

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  CAN 通信层初始化
  * @param  无
  * @retval 0: 成功, 非0: 失败
  * @说明   重映射至 PB8/PB9, 配置过滤器接收所有帧, 1Mbps
  */
uint8_t can_init(void);

/**
  * @brief  发送数据帧 (带 CRC32 + 超时重发)
  * @param  prio: 优先级类别 (CAN_PRIO_*)
  * @param  node_id: 节点号 (0-127, 填入 ID 低字节)
  * @param  data: 负载数据 (1-7 字节, 留 1 字节给 CRC)
  * @param  len: 负载长度 (1-7)
  * @retval 0: 成功, 非0: 失败
  */
uint8_t can_send(uint8_t prio, uint8_t node_id, uint8_t *data, uint8_t len);

/**
  * @brief  接收并校验数据帧 (非阻塞轮询)
  * @param  rx_id: 输出帧 ID
  * @param  data: 输出负载
  * @param  len: 输出负载长度
  * @retval 0: 成功, 非0: 失败 (CAN_ERR_NO_FRAME = 无帧)
  */
uint8_t can_receive(uint32_t *rx_id, uint8_t *data, uint8_t *len);

/**
  * @brief  发送急停帧 (最高优先级, 无重发, 保证确定性)
  * @param  无
  * @retval 0: 成功, 非0: 失败
  */
uint8_t can_emergency_stop(void);

/**
  * @brief  计算 CRC32 (IEEE 802.3 多项式 0xEDB88320)
  * @param  data: 数据指针
  * @param  len: 数据长度
  * @retval CRC32 校验值
  */
uint32_t can_crc32(const uint8_t *data, uint32_t len);

#endif /* __Y_CAN_H */
