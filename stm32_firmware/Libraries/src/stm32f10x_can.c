#include "stm32f10x_can.h"

/* 本工程自定义 stm32f10x.h 未提供 bxCAN 位宏, 此处按数据手册自行定义 */

/* CAN_MCR */
#define CAN_MCR_INRQ        ((uint32_t)0x00000001)
#define CAN_MCR_SLEEP       ((uint32_t)0x00000002)
#define CAN_MCR_TXFP        ((uint32_t)0x00000004)
#define CAN_MCR_RFLM        ((uint32_t)0x00000008)
#define CAN_MCR_NART        ((uint32_t)0x00000010)
#define CAN_MCR_AWUM        ((uint32_t)0x00000020)
#define CAN_MCR_ABOM        ((uint32_t)0x00000040)
#define CAN_MCR_TTCM        ((uint32_t)0x00000080)
#define CAN_MCR_RESET       ((uint32_t)0x00008000)

/* CAN_MSR */
#define CAN_MSR_INAK        ((uint32_t)0x00000001)
#define CAN_MSR_SLAK        ((uint32_t)0x00000002)
#define CAN_MSR_ERRI        ((uint32_t)0x00000004)
#define CAN_MSR_WKUI        ((uint32_t)0x00000008)

/* CAN_TSR */
#define CAN_TSR_RQCP0       ((uint32_t)0x00000001)
#define CAN_TSR_TXOK0       ((uint32_t)0x00000002)
#define CAN_TSR_RQCP1       ((uint32_t)0x00000100)
#define CAN_TSR_TXOK1       ((uint32_t)0x00000200)
#define CAN_TSR_RQCP2       ((uint32_t)0x00010000)
#define CAN_TSR_TXOK2       ((uint32_t)0x00020000)
#define CAN_TSR_TME0        ((uint32_t)0x04000000)
#define CAN_TSR_TME1        ((uint32_t)0x08000000)
#define CAN_TSR_TME2        ((uint32_t)0x10000000)

/* CAN_RF0R / CAN_RF1R */
#define CAN_RF0R_RFOM0      ((uint32_t)0x00000020)
#define CAN_RF1R_RFOM1      ((uint32_t)0x00000020)

/* CAN_FMR */
#define CAN_FMR_FINIT       ((uint32_t)0x00000001)

/* CAN 邮箱 TIR 请求发送位 / 中止发送位 */
#define CAN_TIxR_TXRQ       ((uint32_t)0x00000001)
#define CAN_TIxR_ABRQ       ((uint32_t)0x00000002)

/* 初始化结果 */
#define CANINITOK           1
#define CANINITFAILED       0

/* 全局收发消息结构体 */
CanTxMsg CAN_TxMsg;
CanRxMsg CAN_RxMsg;

/** @brief 复位 CAN 外设
 *  @note  本工程 RCC 库未提供 RCC_APBxPeriphResetCmd, 复位操作在
 *         CAN_Init 进入初始化模式时完成; 此处保留空实现以兼容 API。 */
void CAN_DeInit(CAN_TypeDef* CANx)
{
  (void)CANx;
}

/** @brief 初始化 CAN */
uint8_t CAN_Init(CAN_TypeDef* CANx, CAN_InitTypeDef* CAN_InitStruct)
{
  uint32_t wait_ack = 0;
  uint32_t tmpreg = 0;

  /* 进入初始化模式: 置 INRQ */
  CANx->MCR |= CAN_MCR_INRQ;
  wait_ack = 0;
  while (((CANx->MSR & CAN_MSR_INAK) != CAN_MSR_INAK) && (wait_ack < 0x0000FFFF))
  {
    wait_ack++;
  }
  if ((CANx->MSR & CAN_MSR_INAK) != CAN_MSR_INAK)
  {
    return CANINITFAILED;   /* 进入初始化模式失败 */
  }

  /* 复位控制位 */
  CANx->MCR &= (uint32_t)(~(CAN_MCR_TXFP | CAN_MCR_RFLM | CAN_MCR_NART |
                            CAN_MCR_AWUM | CAN_MCR_ABOM | CAN_MCR_TTCM));
  if (CAN_InitStruct->CAN_TTCM == ENABLE) CANx->MCR |= CAN_MCR_TTCM;
  if (CAN_InitStruct->CAN_ABOM == ENABLE) CANx->MCR |= CAN_MCR_ABOM;
  if (CAN_InitStruct->CAN_AWUM == ENABLE) CANx->MCR |= CAN_MCR_AWUM;
  if (CAN_InitStruct->CAN_NART == ENABLE) CANx->MCR |= CAN_MCR_NART;
  if (CAN_InitStruct->CAN_RFLM == ENABLE) CANx->MCR |= CAN_MCR_RFLM;
  if (CAN_InitStruct->CAN_TXFP == ENABLE) CANx->MCR |= CAN_MCR_TXFP;

  /* 配置位时序 BTR */
  tmpreg = 0;
  tmpreg |= (uint32_t)((uint32_t)CAN_InitStruct->CAN_Mode << 30);       /* SILM/LBKM */
  tmpreg |= (uint32_t)((uint32_t)CAN_InitStruct->CAN_SJW << 24);        /* SJW */
  tmpreg |= (uint32_t)((uint32_t)CAN_InitStruct->CAN_BS2 << 20);        /* TS2 */
  tmpreg |= (uint32_t)((uint32_t)CAN_InitStruct->CAN_BS1 << 16);        /* TS1 */
  tmpreg |= (uint32_t)(((uint32_t)CAN_InitStruct->CAN_Prescaler - 1) & 0x000003FF); /* BRP */
  CANx->BTR = tmpreg;

  /* 退出初始化模式: 清 INRQ */
  CANx->MCR &= (uint32_t)(~CAN_MCR_INRQ);
  wait_ack = 0;
  while (((CANx->MSR & CAN_MSR_INAK) == CAN_MSR_INAK) && (wait_ack < 0x0000FFFF))
  {
    wait_ack++;
  }
  if ((CANx->MSR & CAN_MSR_INAK) == CAN_MSR_INAK)
  {
    return CANINITFAILED;   /* 退出初始化模式失败 */
  }

  return CANINITOK;
}

/** @brief 初始化过滤器 (仅针对 CAN1 的过滤器 0-13) */
void CAN_FilterInit(CAN_FilterInitTypeDef* CAN_FilterInitStruct)
{
  uint32_t filter_number_bitpos = 0;
  uint8_t  filter_number = CAN_FilterInitStruct->CAN_FilterNumber;

  if (filter_number < 14)
  {
    filter_number_bitpos = (uint32_t)1 << filter_number;

    /* 进入过滤器初始化模式 */
    CAN1->FMR |= CAN_FMR_FINIT;

    /* 先禁能过滤器 */
    CAN1->FA1R &= ~filter_number_bitpos;

    /* 过滤器模式: 掩码/列表 */
    if (CAN_FilterInitStruct->CAN_FilterMode == CAN_FilterMode_IdMask)
      CAN1->FM1R &= ~filter_number_bitpos;
    else
      CAN1->FM1R |= filter_number_bitpos;

    /* FIFO 分配 */
    if (CAN_FilterInitStruct->CAN_FilterFIFOAssignment == CAN_Filter_FIFO0)
      CAN1->FFA1R &= ~filter_number_bitpos;
    else
      CAN1->FFA1R |= filter_number_bitpos;

    /* 过滤器尺度: 16bit/32bit */
    if (CAN_FilterInitStruct->CAN_FilterScale == CAN_FilterScale_16bit)
      CAN1->FS1R &= ~filter_number_bitpos;
    else
      CAN1->FS1R |= filter_number_bitpos;

    /* 配置过滤器 ID 与掩码 */
    CAN1->sFilterRegister[filter_number].FR1 =
        ((uint32_t)CAN_FilterInitStruct->CAN_FilterIdHigh << 16) |
        ((uint32_t)CAN_FilterInitStruct->CAN_FilterIdLow & 0x0000FFFF);
    CAN1->sFilterRegister[filter_number].FR2 =
        ((uint32_t)CAN_FilterInitStruct->CAN_FilterMaskIdHigh << 16) |
        ((uint32_t)CAN_FilterInitStruct->CAN_FilterMaskIdLow & 0x0000FFFF);

    /* 激活过滤器 */
    if (CAN_FilterInitStruct->CAN_FilterActivation == ENABLE)
      CAN1->FA1R |= filter_number_bitpos;

    /* 退出过滤器初始化模式 */
    CAN1->FMR &= ~CAN_FMR_FINIT;
  }
}

/** @brief 发送消息, 返回邮箱号 (0-2) 或 CAN_TxStatus_NoMailBox */
uint8_t CAN_Transmit(CAN_TypeDef* CANx, CanTxMsg* TxMessage)
{
  uint8_t transmit_mailbox = 0;

  /* 选择空闲邮箱 */
  if ((CANx->TSR & CAN_TSR_TME0) == CAN_TSR_TME0)
    transmit_mailbox = 0;
  else if ((CANx->TSR & CAN_TSR_TME1) == CAN_TSR_TME1)
    transmit_mailbox = 1;
  else if ((CANx->TSR & CAN_TSR_TME2) == CAN_TSR_TME2)
    transmit_mailbox = 2;
  else
    return CAN_TxStatus_NoMailBox;   /* 无空闲邮箱 */

  /* 配置 ID 与 RTR */
  if (TxMessage->IDE == CAN_Id_Standard)
  {
    CANx->sTxMailBox[transmit_mailbox].TIR =
        ((uint32_t)(TxMessage->StdId & 0x7FF) << 21) | (uint32_t)TxMessage->RTR;
  }
  else
  {
    CANx->sTxMailBox[transmit_mailbox].TIR =
        ((uint32_t)(TxMessage->ExtId & 0x1FFFFFFF) << 3) |
        (uint32_t)TxMessage->IDE | (uint32_t)TxMessage->RTR;
  }

  /* 设置 DLC */
  CANx->sTxMailBox[transmit_mailbox].TDTR &= (uint32_t)0xFFFFFFF0;
  CANx->sTxMailBox[transmit_mailbox].TDTR |= (uint32_t)(TxMessage->DLC & 0x0F);

  /* 装载数据 */
  CANx->sTxMailBox[transmit_mailbox].TDLR =
      ((uint32_t)TxMessage->Data[3] << 24) | ((uint32_t)TxMessage->Data[2] << 16) |
      ((uint32_t)TxMessage->Data[1] << 8)  | (uint32_t)TxMessage->Data[0];
  CANx->sTxMailBox[transmit_mailbox].TDHR =
      ((uint32_t)TxMessage->Data[7] << 24) | ((uint32_t)TxMessage->Data[6] << 16) |
      ((uint32_t)TxMessage->Data[5] << 8)  | (uint32_t)TxMessage->Data[4];

  /* 请求发送 */
  CANx->sTxMailBox[transmit_mailbox].TIR |= CAN_TIxR_TXRQ;

  return transmit_mailbox;
}

/** @brief 获取指定邮箱的发送状态 */
uint8_t CAN_TransmitStatus(CAN_TypeDef* CANx, uint8_t TransmitMailbox)
{
  uint8_t state = CAN_TxStatus_Pending;

  if (TransmitMailbox == 0)
  {
    if ((CANx->TSR & CAN_TSR_RQCP0) != 0)
    {
      state = (CANx->TSR & CAN_TSR_TXOK0) ? CAN_TxStatus_Ok : CAN_TxStatus_Failed;
      CANx->TSR |= CAN_TSR_RQCP0;   /* 清除标志 */
    }
  }
  else if (TransmitMailbox == 1)
  {
    if ((CANx->TSR & CAN_TSR_RQCP1) != 0)
    {
      state = (CANx->TSR & CAN_TSR_TXOK1) ? CAN_TxStatus_Ok : CAN_TxStatus_Failed;
      CANx->TSR |= CAN_TSR_RQCP1;
    }
  }
  else if (TransmitMailbox == 2)
  {
    if ((CANx->TSR & CAN_TSR_RQCP2) != 0)
    {
      state = (CANx->TSR & CAN_TSR_TXOK2) ? CAN_TxStatus_Ok : CAN_TxStatus_Failed;
      CANx->TSR |= CAN_TSR_RQCP2;
    }
  }

  return state;
}

uint8_t CAN_GetTransmitStatus(CAN_TypeDef* CANx, uint8_t TransmitMailbox)
{
  return CAN_TransmitStatus(CANx, TransmitMailbox);
}

/** @brief 取消发送 (置 ABRQ 中止排队中的传输)
 *  @note  中止位为 TIR 的 bit1 (ABRQ), 而非 bit0 (TXRQ)。 */
void CAN_CancelTransmit(CAN_TypeDef* CANx, uint8_t Mailbox)
{
  if (Mailbox == 0)
    CANx->sTxMailBox[0].TIR |= CAN_TIxR_ABRQ;
  else if (Mailbox == 1)
    CANx->sTxMailBox[1].TIR |= CAN_TIxR_ABRQ;
  else if (Mailbox == 2)
    CANx->sTxMailBox[2].TIR |= CAN_TIxR_ABRQ;
}

/** @brief 接收消息 */
void CAN_Receive(CAN_TypeDef* CANx, uint8_t FIFONum, CanRxMsg* RxMessage)
{
  /* 解析 ID */
  RxMessage->IDE = (uint8_t)(CANx->sFIFOMailBox[FIFONum].RIR & 0x00000004);
  if (RxMessage->IDE == CAN_Id_Standard)
  {
    RxMessage->StdId = (uint32_t)(CANx->sFIFOMailBox[FIFONum].RIR >> 21) & 0x000007FF;
  }
  else
  {
    RxMessage->ExtId = (uint32_t)(CANx->sFIFOMailBox[FIFONum].RIR >> 3) & 0x1FFFFFFF;
  }
  RxMessage->RTR = (uint8_t)(CANx->sFIFOMailBox[FIFONum].RIR & 0x00000002);
  RxMessage->DLC = (uint8_t)(CANx->sFIFOMailBox[FIFONum].RDTR & 0x0000000F);
  RxMessage->FMI = (uint8_t)((CANx->sFIFOMailBox[FIFONum].RDTR >> 8) & 0x000000FF);

  /* 读取数据 */
  RxMessage->Data[0] = (uint8_t)(CANx->sFIFOMailBox[FIFONum].RDLR & 0xFF);
  RxMessage->Data[1] = (uint8_t)((CANx->sFIFOMailBox[FIFONum].RDLR >> 8) & 0xFF);
  RxMessage->Data[2] = (uint8_t)((CANx->sFIFOMailBox[FIFONum].RDLR >> 16) & 0xFF);
  RxMessage->Data[3] = (uint8_t)((CANx->sFIFOMailBox[FIFONum].RDLR >> 24) & 0xFF);
  RxMessage->Data[4] = (uint8_t)(CANx->sFIFOMailBox[FIFONum].RDHR & 0xFF);
  RxMessage->Data[5] = (uint8_t)((CANx->sFIFOMailBox[FIFONum].RDHR >> 8) & 0xFF);
  RxMessage->Data[6] = (uint8_t)((CANx->sFIFOMailBox[FIFONum].RDHR >> 16) & 0xFF);
  RxMessage->Data[7] = (uint8_t)((CANx->sFIFOMailBox[FIFONum].RDHR >> 24) & 0xFF);

  RxMessage->FIFONumber = FIFONum;

  /* 释放邮箱 */
  CAN_ReleaseFIFO(CANx, FIFONum);
}

/** @brief 释放指定 FIFO 邮箱 */
void CAN_ReleaseFIFO(CAN_TypeDef* CANx, uint8_t FIFONum)
{
  if (FIFONum == CAN_FIFO0)
    CANx->RF0R |= CAN_RF0R_RFOM0;
  else
    CANx->RF1R |= CAN_RF1R_RFOM1;
}

/** @brief 获取标志状态 */
FlagStatus CAN_GetFlagStatus(CAN_TypeDef* CANx, uint32_t CAN_FLAG)
{
  switch (CAN_FLAG)
  {
    case CAN_FLAG_INAK: return (CANx->MSR & CAN_MSR_INAK) ? SET : RESET;
    case CAN_FLAG_SLAK: return (CANx->MSR & CAN_MSR_SLAK) ? SET : RESET;
    case CAN_FLAG_ERRI: return (CANx->MSR & CAN_MSR_ERRI) ? SET : RESET;
    case CAN_FLAG_WKU:  return (CANx->MSR & CAN_MSR_WKUI) ? SET : RESET;
    case CAN_FLAG_FMP0: return (CANx->RF0R & 0x03) ? SET : RESET;
    case CAN_FLAG_FF0:  return (CANx->RF0R & 0x08) ? SET : RESET;
    case CAN_FLAG_FOV0: return (CANx->RF0R & 0x10) ? SET : RESET;
    case CAN_FLAG_FMP1: return (CANx->RF1R & 0x03) ? SET : RESET;
    case CAN_FLAG_FF1:  return (CANx->RF1R & 0x08) ? SET : RESET;
    case CAN_FLAG_FOV1: return (CANx->RF1R & 0x10) ? SET : RESET;
    case CAN_FLAG_RQCP0:return (CANx->TSR & CAN_TSR_RQCP0) ? SET : RESET;
    case CAN_FLAG_RQCP1:return (CANx->TSR & CAN_TSR_RQCP1) ? SET : RESET;
    case CAN_FLAG_RQCP2:return (CANx->TSR & CAN_TSR_RQCP2) ? SET : RESET;
    case CAN_FLAG_BOF:  return (CANx->ESR & 0x04) ? SET : RESET;
    case CAN_FLAG_EPVF: return (CANx->ESR & 0x02) ? SET : RESET;
    case CAN_FLAG_EWGF: return (CANx->ESR & 0x01) ? SET : RESET;
    case CAN_FLAG_LEC:  return (CANx->ESR & 0x70) ? SET : RESET;
    default:            return RESET;
  }
}

/** @brief 获取错误码 (LEC) */
uint8_t CAN_GetErrorCode(CAN_TypeDef* CANx)
{
  uint8_t lec = (uint8_t)((CANx->ESR >> 4) & 0x07);
  return (uint8_t)(lec << 4);
}
