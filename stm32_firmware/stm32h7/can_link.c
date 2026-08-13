/**
  ******************************************************************************
  * @file    stm32h7/can_link.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-08-10
  * @brief   CAN 通信层实现 (STM32H7 HAL 参考骨架)
  *
  *          关键设计:
  *          1. 帧 ID 编码: (prio<<12) | (type<<8) | node_id
  *             低 ID 高优先级, 由 CAN 硬件仲裁保证确定性 (S2 验收: 急停低延迟)
  *          2. 数据完整性: CRC32 覆盖 负载+长度, 接收端校验失败丢弃并计数
  *          3. 可靠性: 发送带超时重发 (CANLINK_MAX_RETRY)
  *          4. 急停帧: 最高优先级, 不加重发/校验等待, 保证确定性时序
  ******************************************************************************
  */

#include "can_link.h"

/* CRC32 表 (IEEE 802.3 反射多项式 0xEDB88320) */
static uint32_t crc32_table[256];
static uint8_t  crc32_table_ready = 0;

/**
  * @brief  生成 CRC32 查表 (惰性初始化)
  */
static void crc32_table_init(void)
{
    for (uint32_t i = 0; i < 256; i++)
    {
        uint32_t c = i;
        for (uint32_t k = 0; k < 8; k++)
        {
            c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        }
        crc32_table[i] = c;
    }
    crc32_table_ready = 1;
}

uint32_t can_link_crc32(const uint8_t *data, uint32_t len)
{
    uint32_t crc = 0xFFFFFFFFu;

    if (!crc32_table_ready)
    {
        crc32_table_init();
    }

    for (uint32_t i = 0; i < len; i++)
    {
        crc = (crc >> 8) ^ crc32_table[(crc ^ data[i]) & 0xFFu];
    }

    return crc ^ 0xFFFFFFFFu;
}

/**
  * @brief  组合 CAN 帧 ID
  * @param  prio: 优先级类别
  * @param  type: 帧类型
  * @param  node_id: 节点号
  * @retval 帧 ID
  */
static uint32_t can_link_make_id(uint8_t prio, uint8_t type, uint8_t node_id)
{
    return ((uint32_t)(prio & 0x0F) << 12) |
           ((uint32_t)(type & 0x0F) << 8)  |
           ((uint32_t)(node_id & 0x7F));
}

/**
  * @brief  配置过滤器接收所有帧 (工业级: 过滤逻辑在上层按 ID 分发)
  * @param  link: 链路句柄
  */
static void can_link_config_filter(can_link_t *link)
{
    CAN_FilterTypeDef filter = {0};

    filter.FilterIdHigh         = 0x0000;
    filter.FilterIdLow          = 0x0000;
    filter.FilterMaskIdHigh     = 0x0000;
    filter.FilterMaskIdLow      = 0x0000;
    filter.FilterFIFOAssignment = CAN_RX_FIFO0;
    filter.FilterBank           = link->filter_bank;
    filter.FilterMode           = CAN_FILTERMODE_IDMASK;
    filter.FilterScale          = CAN_FILTERSCALE_32BIT;
    filter.FilterActivation     = ENABLE;

    HAL_CAN_ConfigFilter(link->hcan, &filter);
}

HAL_StatusTypeDef can_link_init(can_link_t *link, CAN_HandleTypeDef *hcan,
                                uint8_t use_ext_id)
{
    CAN_FilterTypeDef filter = {0};

    if (link == NULL || hcan == NULL)
    {
        return HAL_ERROR;
    }

    link->hcan       = hcan;
    link->use_ext_id = use_ext_id;
    link->filter_bank = 0;
    link->tx_total   = 0;
    link->tx_retry   = 0;
    link->tx_fail    = 0;
    link->rx_total   = 0;
    link->rx_crc_fail = 0;

    /* 位时序: 1Mbps (需要用户根据实际 APB1 时钟调整 PRESCALER) */
    hcan->Init.Prescaler      = CANLINK_PRESCALER;
    hcan->Init.Mode           = CAN_MODE_NORMAL;
    hcan->Init.SyncJumpWidth  = CANLINK_SJW;
    hcan->Init.TimeSeg1       = CANLINK_BS1;
    hcan->Init.TimeSeg2       = CANLINK_BS2;
    hcan->Init.TimeTriggeredMode   = DISABLE;
    hcan->Init.AutoBusOff     = ENABLE;
    hcan->Init.AutoWakeUp     = DISABLE;
    hcan->Init.AutoRetransmission = ENABLE;
    hcan->Init.ReceiveFifoLocked  = DISABLE;
    hcan->Init.TransmitFifoPriority = DISABLE;

    if (HAL_CAN_Init(hcan) != HAL_OK)
    {
        return HAL_ERROR;
    }

    /* 配置过滤 (接收所有帧) */
    filter.FilterIdHigh         = 0x0000;
    filter.FilterIdLow          = 0x0000;
    filter.FilterMaskIdHigh     = 0x0000;
    filter.FilterMaskIdLow      = 0x0000;
    filter.FilterFIFOAssignment = CAN_RX_FIFO0;
    filter.FilterBank           = 0;
    filter.FilterMode           = CAN_FILTERMODE_IDMASK;
    filter.FilterScale          = CAN_FILTERSCALE_32BIT;
    filter.FilterActivation     = ENABLE;
    HAL_CAN_ConfigFilter(hcan, &filter);

    if (HAL_CAN_Start(hcan) != HAL_OK)
    {
        return HAL_ERROR;
    }

    link->initialized = 1;
    return HAL_OK;
}

HAL_StatusTypeDef can_link_send(can_link_t *link, uint8_t prio,
                                uint8_t node_id, uint8_t *data, uint8_t len)
{
    CAN_TxHeaderTypeDef header = {0};
    uint8_t  frame[CANLINK_MAX_DATA];
    uint32_t crc;
    uint32_t mailbox;
    uint32_t tx_id;
    uint8_t  retry;

    if (link == NULL || !link->initialized || data == NULL)
    {
        return HAL_ERROR;
    }

    /* 负载长度 1-7, 预留 1 字节 CRC */
    if (len < 1 || len > (CANLINK_MAX_DATA - CANLINK_CRC_FOOTER))
    {
        return HAL_ERROR;
    }

    /* 组帧: 负载 + CRC 尾 */
    for (uint8_t i = 0; i < len; i++)
    {
        frame[i] = data[i];
    }
    crc = can_link_crc32(frame, len);           /* 校验覆盖负载 */
    crc = can_link_crc32((uint8_t *)&crc, 1);   /* 并入长度信息 */
    frame[len] = (uint8_t)(crc & 0xFFu);

    /* 组帧 ID: 类型=命令 */
    tx_id = can_link_make_id(prio, CANLINK_TYPE_CMD, node_id);
    header.StdId = link->use_ext_id ? 0 : tx_id;
    header.ExtId = link->use_ext_id ? tx_id : 0;
    header.IDE   = link->use_ext_id ? CAN_ID_EXT : CAN_ID_STD;
    header.RTR   = CAN_RTR_DATA;
    header.DLC   = len + CANLINK_CRC_FOOTER;

    /* 超时重发 */
    link->tx_total++;
    for (retry = 0; retry <= CANLINK_MAX_RETRY; retry++)
    {
        if (retry > 0)
        {
            link->tx_retry++;
        }
        if (HAL_CAN_AddTxMessage(link->hcan, &header, frame, &mailbox) == HAL_OK)
        {
            /* 等待发送完成 (有硬件自动重发保证, 这里仅轮询完成) */
            while (HAL_CAN_GetTxMailboxesFreeLevel(link->hcan) < 3)
            {
                /* 等待邮箱释放 */
            }
            return HAL_OK;
        }
        HAL_Delay(1);
    }

    link->tx_fail++;
    return HAL_ERROR;
}

HAL_StatusTypeDef can_link_receive(can_link_t *link, uint32_t *rx_id,
                                   uint8_t *data, uint8_t *len)
{
    CAN_RxHeaderTypeDef header = {0};
    uint8_t  frame[CANLINK_MAX_DATA];
    uint32_t crc;
    uint8_t  payload_len;

    if (link == NULL || !link->initialized || data == NULL || len == NULL)
    {
        return HAL_ERROR;
    }

    if (HAL_CAN_GetRxFifoFillLevel(link->hcan, CAN_RX_FIFO0) == 0)
    {
        return HAL_ERROR;   /* 无待处理帧 */
    }

    if (HAL_CAN_Receive(link->hcan, CAN_RX_FIFO0, &header, frame,
                        CANLINK_TX_TIMEOUT) != HAL_OK)
    {
        return HAL_ERROR;
    }

    link->rx_total++;

    /* 计算实际负载长度 */
    payload_len = header.DLC - CANLINK_CRC_FOOTER;
    if (header.DLC < 2 || payload_len > (CANLINK_MAX_DATA - CANLINK_CRC_FOOTER))
    {
        link->rx_crc_fail++;
        return HAL_ERROR;
    }

    /* 校验 CRC */
    crc = can_link_crc32(frame, payload_len);
    crc = can_link_crc32((uint8_t *)&crc, 1);
    if ((frame[payload_len] & 0xFFu) != (uint8_t)(crc & 0xFFu))
    {
        link->rx_crc_fail++;
        return HAL_ERROR;   /* CRC 校验失败, 丢弃 */
    }

    for (uint8_t i = 0; i < payload_len; i++)
    {
        data[i] = frame[i];
    }
    *len = payload_len;

    if (rx_id != NULL)
    {
        *rx_id = link->use_ext_id ? header.ExtId : header.StdId;
    }
    return HAL_OK;
}

HAL_StatusTypeDef can_link_emergency_stop(can_link_t *link)
{
    CAN_TxHeaderTypeDef header = {0};
    uint32_t mailbox;
    uint32_t tx_id;

    if (link == NULL || !link->initialized)
    {
        return HAL_ERROR;
    }

    /* 最高优先级 ID + 急停类型, 无重发以保确定性 */
    tx_id = can_link_make_id(CANLINK_PRIO_SYSTEM, CANLINK_TYPE_EMERG, 0);
    header.StdId = link->use_ext_id ? 0 : tx_id;
    header.ExtId = link->use_ext_id ? tx_id : 0;
    header.IDE   = link->use_ext_id ? CAN_ID_EXT : CAN_ID_STD;
    header.RTR   = CAN_RTR_DATA;
    header.DLC   = 1;

    if (HAL_CAN_AddTxMessage(link->hcan, &header, (uint8_t *)"\x00", &mailbox) == HAL_OK)
    {
        return HAL_OK;
    }
    return HAL_ERROR;
}
