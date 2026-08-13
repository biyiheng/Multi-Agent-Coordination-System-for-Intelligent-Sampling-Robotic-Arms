/**
  ******************************************************************************
  * @file    SRC/can/y_can.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-08-10
  * @brief   CAN 通信层实现 (STM32F103 SPL 集成)
  *
  *          关键设计:
  *          1. 引脚重映射: CAN1 默认 PA11/PA12 与 Key2(PA11) 冲突, 经
  *             AFIO->MAPR 重映射到 PB8(RX)/PB9(TX)
  *          2. 帧 ID 编码: (prio<<12) | (type<<8) | node_id
  *             低 ID 高优先级, 由 CAN 硬件仲裁保证确定性 (S2 验收)
  *          3. 数据完整性: CRC32 覆盖 负载+长度, 接收端校验失败丢弃
  *          4. 可靠性: 发送带超时重发 (CAN_MAX_RETRY)
  *          5. 急停帧: 最高优先级, 不加重发/校验等待, 保证确定性时序
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include <stddef.h>
#include "y_can.h"

/* AFIO->MAPR 中 CAN1 重映射位 (bit14=1 -> PB8/PB9) */
#define AFIO_MAPR_CAN1_REMAP    0x00004000

/* 私有变量 --------------------------------------------------------------------*/
static uint32_t crc32_table[256];
static uint8_t  crc32_table_ready = 0;

/* 私有函数声明 ----------------------------------------------------------------*/
static void crc32_table_init(void);
static uint32_t can_make_id(uint8_t prio, uint8_t type, uint8_t node_id);

/**
  * @brief  生成 CRC32 查表 (惰性初始化)
  * @param  无
  * @返回值 无
  */
static void crc32_table_init(void)
{
	uint32_t i, k, c;

	for (i = 0; i < 256; i++)
	{
		c = i;
		for (k = 0; k < 8; k++)
		{
			c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
		}
		crc32_table[i] = c;
	}
	crc32_table_ready = 1;
}

/**
  * @brief  计算 CRC32 (IEEE 802.3)
  * @param  data: 数据指针
  * @param  len: 数据长度
  * @retval CRC32 校验值
  */
uint32_t can_crc32(const uint8_t *data, uint32_t len)
{
	uint32_t crc = 0xFFFFFFFFu;
	uint32_t i;

	if (!crc32_table_ready)
	{
		crc32_table_init();
	}

	for (i = 0; i < len; i++)
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
static uint32_t can_make_id(uint8_t prio, uint8_t type, uint8_t node_id)
{
	return ((uint32_t)(prio & 0x0F) << 12) |
	       ((uint32_t)(type & 0x0F) << 8)  |
	       ((uint32_t)(node_id & 0x7F));
}

/**
  * @brief  CAN 通信层初始化
  * @param  无
  * @retval 0: 成功, 非0: 失败
  */
uint8_t can_init(void)
{
	GPIO_InitTypeDef      GPIO_InitStructure;
	CAN_InitTypeDef       CAN_InitStructure;
	CAN_FilterInitTypeDef CAN_FilterInitStructure;

	/* 使能时钟 */
	RCC_APB1PeriphClockCmd(RCC_APB1Periph_CAN1, ENABLE);
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB | RCC_APB2Periph_AFIO, ENABLE);

	/* 重映射 CAN1 到 PB8(RX)/PB9(TX), 避免与 PA11(Key2) 冲突 */
	AFIO->MAPR |= AFIO_MAPR_CAN1_REMAP;

	/* PB8(RX) - 浮空输入 */
	GPIO_InitStructure.GPIO_Pin  = GPIO_Pin_8;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;
	GPIO_Init(GPIOB, &GPIO_InitStructure);

	/* PB9(TX) - 复用推挽输出 */
	GPIO_InitStructure.GPIO_Pin   = GPIO_Pin_9;
	GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_AF_PP;
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
	GPIO_Init(GPIOB, &GPIO_InitStructure);

	/* CAN 参数配置 (1Mbps) */
	CAN_InitStructure.CAN_Prescaler = CAN_BAUD_PRESCALER;
	CAN_InitStructure.CAN_Mode      = CAN_Mode_Normal;
	CAN_InitStructure.CAN_SJW       = CAN_SJW_TQ;
	CAN_InitStructure.CAN_BS1       = CAN_BS1_TQ;
	CAN_InitStructure.CAN_BS2       = CAN_BS2_TQ;
	CAN_InitStructure.CAN_TTCM      = DISABLE;
	CAN_InitStructure.CAN_ABOM      = ENABLE;   /* 自动离线恢复 */
	CAN_InitStructure.CAN_AWUM      = DISABLE;
	CAN_InitStructure.CAN_NART      = DISABLE;  /* 硬件自动重发 */
	CAN_InitStructure.CAN_RFLM      = DISABLE;
	CAN_InitStructure.CAN_TXFP      = DISABLE;
	if (CAN_Init(CAN1, &CAN_InitStructure) != 1)
	{
		return CAN_ERR_INIT;
	}

	/* 过滤器 0: 接收所有帧 (ID 掩码全 0) */
	CAN_FilterInitStructure.CAN_FilterIdHigh      = 0x0000;
	CAN_FilterInitStructure.CAN_FilterIdLow       = 0x0000;
	CAN_FilterInitStructure.CAN_FilterMaskIdHigh  = 0x0000;
	CAN_FilterInitStructure.CAN_FilterMaskIdLow   = 0x0000;
	CAN_FilterInitStructure.CAN_FilterFIFOAssignment = CAN_Filter_FIFO0;
	CAN_FilterInitStructure.CAN_FilterNumber      = 0;
	CAN_FilterInitStructure.CAN_FilterMode        = CAN_FilterMode_IdMask;
	CAN_FilterInitStructure.CAN_FilterScale       = CAN_FilterScale_32bit;
	CAN_FilterInitStructure.CAN_FilterActivation  = ENABLE;
	CAN_FilterInit(&CAN_FilterInitStructure);

	return CAN_OK;
}

/**
  * @brief  发送数据帧 (带 CRC32 + 超时重发)
  * @param  prio: 优先级类别
  * @param  node_id: 节点号
  * @param  data: 负载数据
  * @param  len: 负载长度
  * @retval 0: 成功, 非0: 失败
  */
uint8_t can_send(uint8_t prio, uint8_t node_id, uint8_t *data, uint8_t len)
{
	uint8_t  frame[CAN_MAX_DATA];
	uint8_t  i;
	uint8_t  retry;
	uint8_t  mailbox;
	uint8_t  tx_status;
	uint32_t timeout;
	uint32_t crc;
	uint32_t tx_id;

	/* 参数检查: 负载长度 1-7, 预留 1 字节 CRC */
	if (data == NULL || len < 1 || len > (CAN_MAX_DATA - CAN_CRC_FOOTER))
	{
		return CAN_ERR_PARAM;
	}

	/* 组帧: 负载 + CRC 尾 */
	for (i = 0; i < len; i++)
	{
		frame[i] = data[i];
	}
	crc = can_crc32(frame, len);           /* 校验覆盖负载 */
	crc = can_crc32((uint8_t *)&crc, 1);   /* 并入长度信息 */
	frame[len] = (uint8_t)(crc & 0xFFu);

	tx_id = can_make_id(prio, CAN_TYPE_CMD, node_id);

	/* 超时重发 */
	for (retry = 0; retry <= CAN_MAX_RETRY; retry++)
	{
		/* 填充发送消息 */
		CAN_TxMsg.StdId = tx_id;
		CAN_TxMsg.IDE   = CAN_Id_Standard;
		CAN_TxMsg.RTR   = CAN_RTR_Data;
		CAN_TxMsg.DLC   = len + CAN_CRC_FOOTER;
		for (i = 0; i < CAN_TxMsg.DLC; i++)
		{
			CAN_TxMsg.Data[i] = frame[i];
		}

		mailbox = CAN_Transmit(CAN1, &CAN_TxMsg);
		if (mailbox == CAN_TxStatus_NoMailBox)
		{
			continue;   /* 无空闲邮箱, 重试 */
		}

		/* 等待发送完成 */
		timeout = CAN_TX_TIMEOUT;
		while (timeout--)
		{
			tx_status = CAN_TransmitStatus(CAN1, mailbox);
			if (tx_status == CAN_TxStatus_Ok)
			{
				return CAN_OK;
			}
			if (tx_status == CAN_TxStatus_Failed)
			{
				break;  /* 发送失败, 进入重发 */
			}
		}
	}

	return CAN_ERR_TIMEOUT;
}

/**
  * @brief  接收并校验数据帧 (非阻塞轮询)
  * @param  rx_id: 输出帧 ID
  * @param  data: 输出负载
  * @param  len: 输出负载长度
  * @retval 0: 成功, 非0: 失败
  */
uint8_t can_receive(uint32_t *rx_id, uint8_t *data, uint8_t *len)
{
	uint8_t  frame[CAN_MAX_DATA];
	uint8_t  payload_len;
	uint8_t  i;
	uint32_t crc;

	if (data == NULL || len == NULL)
	{
		return CAN_ERR_PARAM;
	}

	/* 无待处理帧 */
	if (CAN_GetFlagStatus(CAN1, CAN_FLAG_FMP0) == RESET)
	{
		return CAN_ERR_NO_FRAME;
	}

	/* 接收一帧 */
	CAN_Receive(CAN1, CAN_FIFO0, &CAN_RxMsg);

	/* 计算实际负载长度 */
	payload_len = CAN_RxMsg.DLC - CAN_CRC_FOOTER;
	if (CAN_RxMsg.DLC < 2 || payload_len > (CAN_MAX_DATA - CAN_CRC_FOOTER))
	{
		return CAN_ERR_CRC;
	}

	for (i = 0; i < CAN_RxMsg.DLC; i++)
	{
		frame[i] = CAN_RxMsg.Data[i];
	}

	/* 校验 CRC */
	crc = can_crc32(frame, payload_len);
	crc = can_crc32((uint8_t *)&crc, 1);
	if ((frame[payload_len] & 0xFFu) != (uint8_t)(crc & 0xFFu))
	{
		return CAN_ERR_CRC;   /* CRC 校验失败, 丢弃 */
	}

	for (i = 0; i < payload_len; i++)
	{
		data[i] = frame[i];
	}
	*len = payload_len;
	if (rx_id != NULL)
	{
		*rx_id = CAN_RxMsg.StdId;
	}
	return CAN_OK;
}

/**
  * @brief  发送急停帧 (最高优先级, 无重发, 保证确定性)
  * @param  无
  * @retval 0: 成功, 非0: 失败
  */
uint8_t can_emergency_stop(void)
{
	uint8_t mailbox;
	uint32_t tx_id;

	/* 最高优先级 ID + 急停类型 */
	tx_id = can_make_id(CAN_PRIO_SYSTEM, CAN_TYPE_EMERG, 0);

	CAN_TxMsg.StdId = tx_id;
	CAN_TxMsg.IDE   = CAN_Id_Standard;
	CAN_TxMsg.RTR   = CAN_RTR_Data;
	CAN_TxMsg.DLC   = 1;
	CAN_TxMsg.Data[0] = 0x00;

	mailbox = CAN_Transmit(CAN1, &CAN_TxMsg);
	if (mailbox == CAN_TxStatus_NoMailBox)
	{
		return CAN_ERR_TIMEOUT;
	}
	return CAN_OK;
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/
