#ifndef __STM32F10X_CAN_H
#define __STM32F10X_CAN_H

#include "stm32f10x.h"

/* ========================================================================= */
/*                        CAN Register Structure (bxCAN)                    */
/* ========================================================================= */

/** @brief CAN 发送邮箱寄存器 */
typedef struct
{
  __IO uint32_t TIR;
  __IO uint32_t TDTR;
  __IO uint32_t TDLR;
  __IO uint32_t TDHR;
} CAN_TxMailBox_TypeDef;

/** @brief CAN 接收 FIFO 邮箱寄存器 */
typedef struct
{
  __IO uint32_t RIR;
  __IO uint32_t RDTR;
  __IO uint32_t RDLR;
  __IO uint32_t RDHR;
} CAN_FIFOMailBox_TypeDef;

/** @brief CAN 过滤器寄存器 */
typedef struct
{
  __IO uint32_t FR1;
  __IO uint32_t FR2;
} CAN_FilterRegister_TypeDef;

/** @brief CAN 外设寄存器结构 */
typedef struct
{
  __IO uint32_t MCR;
  __IO uint32_t MSR;
  __IO uint32_t TSR;
  __IO uint32_t RF0R;
  __IO uint32_t RF1R;
  __IO uint32_t IER;
  __IO uint32_t ESR;
  __IO uint32_t BTR;
  uint32_t RESERVED0[88];
  CAN_TxMailBox_TypeDef      sTxMailBox[3];
  CAN_FIFOMailBox_TypeDef    sFIFOMailBox[2];
  uint32_t RESERVED1[12];
  __IO uint32_t FMR;
  __IO uint32_t FM1R;
  uint32_t RESERVED2;
  __IO uint32_t FS1R;
  uint32_t RESERVED3;
  __IO uint32_t FFO1R;
  uint32_t RESERVED4;
  __IO uint32_t FFA1R;
  uint32_t RESERVED5;
  __IO uint32_t FA1R;
  uint32_t RESERVED6[8];
  CAN_FilterRegister_TypeDef sFilterRegister[28];
} CAN_TypeDef;

#define CAN1                ((CAN_TypeDef *) CAN1_BASE)
#define CAN2                ((CAN_TypeDef *) CAN2_BASE)

/* ========================================================================= */
/*                    CAN Exported Structures                              */
/* ========================================================================= */

/** @brief CAN 初始化结构体 */
typedef struct
{
  uint16_t CAN_Prescaler;                /* 波特率预分频 (1-1024) */
  uint8_t  CAN_Mode;                     /* 工作模式 */
  uint8_t  CAN_SJW;                      /* 重新同步跳跃宽度 */
  uint8_t  CAN_BS1;                      /* 时间段1 */
  uint8_t  CAN_BS2;                      /* 时间段2 */
  FunctionalState CAN_TTCM;              /* 时间触发通信 */
  FunctionalState CAN_ABOM;              /* 自动离线管理 */
  FunctionalState CAN_AWUM;              /* 自动唤醒 */
  FunctionalState CAN_NART;              /* 非自动重发 */
  FunctionalState CAN_RFLM;              /* 接收FIFO锁定 */
  FunctionalState CAN_TXFP;              /* 发送FIFO优先级 */
} CAN_InitTypeDef;

/** @brief CAN 过滤器初始化结构体 */
typedef struct
{
  uint16_t CAN_FilterIdHigh;             /* 过滤器ID高16位 */
  uint16_t CAN_FilterIdLow;              /* 过滤器ID低16位 */
  uint16_t CAN_FilterMaskIdHigh;         /* 过滤器掩码ID高16位 */
  uint16_t CAN_FilterMaskIdLow;          /* 过滤器掩码ID低16位 */
  uint16_t CAN_FilterFIFOAssignment;     /* 指定FIFO */
  uint8_t  CAN_FilterNumber;             /* 过滤器号 */
  uint8_t  CAN_FilterMode;               /* 过滤器模式 */
  uint8_t  CAN_FilterScale;              /* 过滤器尺度 */
  FunctionalState CAN_FilterActivation;  /* 激活过滤器 */
} CAN_FilterInitTypeDef;

/** @brief CAN 发送消息结构体 */
typedef struct
{
  uint32_t StdId;                        /* 标准ID */
  uint32_t ExtId;                        /* 扩展ID */
  uint8_t  IDE;                          /* ID类型 */
  uint8_t  RTR;                          /* 帧类型 */
  uint8_t  DLC;                          /* 数据长度 */
  uint8_t  Data[8];                      /* 数据 */
  uint8_t  FMI;                          /* 过滤器匹配索引 */
} CanTxMsg;

/** @brief CAN 接收消息结构体 */
typedef struct
{
  uint32_t StdId;
  uint32_t ExtId;
  uint8_t  IDE;
  uint8_t  RTR;
  uint8_t  DLC;
  uint8_t  Data[8];
  uint8_t  FMI;
  uint8_t  FIFONumber;
} CanRxMsg;

/* ========================================================================= */
/*                        CAN Exported Constants                            */
/* ========================================================================= */

/* CAN_InitStruct.CAN_Mode */
#define CAN_Mode_Normal                  ((uint8_t)0x00)
#define CAN_Mode_LoopBack                ((uint8_t)0x01)
#define CAN_Mode_Silent                  ((uint8_t)0x02)
#define CAN_Mode_Silent_LoopBack         ((uint8_t)0x03)

/* CAN_SJW */
#define CAN_SJW_1tq                      ((uint8_t)0x00)
#define CAN_SJW_2tq                      ((uint8_t)0x01)
#define CAN_SJW_4tq                      ((uint8_t)0x02)

/* CAN_BS1 */
#define CAN_BS1_1tq                      ((uint8_t)0x00)
#define CAN_BS1_2tq                      ((uint8_t)0x01)
#define CAN_BS1_3tq                      ((uint8_t)0x02)
#define CAN_BS1_4tq                      ((uint8_t)0x03)
#define CAN_BS1_5tq                      ((uint8_t)0x04)
#define CAN_BS1_6tq                      ((uint8_t)0x05)
#define CAN_BS1_7tq                      ((uint8_t)0x06)
#define CAN_BS1_8tq                      ((uint8_t)0x07)
#define CAN_BS1_9tq                      ((uint8_t)0x08)
#define CAN_BS1_10tq                     ((uint8_t)0x09)
#define CAN_BS1_11tq                     ((uint8_t)0x0A)
#define CAN_BS1_12tq                     ((uint8_t)0x0B)
#define CAN_BS1_13tq                     ((uint8_t)0x0C)
#define CAN_BS1_14tq                     ((uint8_t)0x0D)
#define CAN_BS1_15tq                     ((uint8_t)0x0E)
#define CAN_BS1_16tq                     ((uint8_t)0x0F)

/* CAN_BS2 */
#define CAN_BS2_1tq                      ((uint8_t)0x00)
#define CAN_BS2_2tq                      ((uint8_t)0x01)
#define CAN_BS2_3tq                      ((uint8_t)0x02)
#define CAN_BS2_4tq                      ((uint8_t)0x03)
#define CAN_BS2_5tq                      ((uint8_t)0x04)
#define CAN_BS2_6tq                      ((uint8_t)0x05)
#define CAN_BS2_7tq                      ((uint8_t)0x06)
#define CAN_BS2_8tq                      ((uint8_t)0x07)

/* 消息 IDE 字段 */
#define CAN_Id_Standard                  ((uint8_t)0x00)
#define CAN_Id_Extended                  ((uint8_t)0x04)

/* 消息 RTR 字段 */
#define CAN_RTR_Data                     ((uint8_t)0x00)
#define CAN_RTR_Remote                   ((uint8_t)0x02)

/* CAN 发送状态 */
#define CAN_TxStatus_Failed              ((uint8_t)0x00)
#define CAN_TxStatus_Ok                  ((uint8_t)0x01)
#define CAN_TxStatus_Pending             ((uint8_t)0x02)
#define CAN_TxStatus_NoMailBox           ((uint8_t)0x04)

/* CAN 接收 FIFO */
#define CAN_FIFO0                        ((uint8_t)0x00)
#define CAN_FIFO1                        ((uint8_t)0x01)

/* CAN 过滤器模式 */
#define CAN_FilterMode_IdMask            ((uint8_t)0x00)
#define CAN_FilterMode_IdList            ((uint8_t)0x01)

/* CAN 过滤器尺度 */
#define CAN_FilterScale_16bit            ((uint8_t)0x00)
#define CAN_FilterScale_32bit            ((uint8_t)0x01)

/* CAN 过滤器 FIFO 分配 */
#define CAN_Filter_FIFO0                 ((uint8_t)0x00)
#define CAN_Filter_FIFO1                 ((uint8_t)0x01)

/* CAN 工作模式 (内部) */
#define CAN_OperatingMode_Initialization ((uint8_t)0x00)
#define CAN_OperatingMode_Normal         ((uint8_t)0x01)
#define CAN_OperatingMode_Sleep          ((uint8_t)0x02)

/* CAN 标志位 (ESR/MSR/TSR/RF0R 组合) */
#define CAN_FLAG_RQCP0                   ((uint32_t)0x38000001)
#define CAN_FLAG_RQCP1                   ((uint32_t)0x38000100)
#define CAN_FLAG_RQCP2                   ((uint32_t)0x38010000)
#define CAN_FLAG_FMP0                    ((uint32_t)0x12000003)
#define CAN_FLAG_FF0                     ((uint32_t)0x12000008)
#define CAN_FLAG_FOV0                    ((uint32_t)0x12000010)
#define CAN_FLAG_FMP1                    ((uint32_t)0x14000003)
#define CAN_FLAG_FF1                     ((uint32_t)0x14000008)
#define CAN_FLAG_FOV1                    ((uint32_t)0x14000010)
#define CAN_FLAG_WKU                     ((uint32_t)0x31000008)
#define CAN_FLAG_SLAK                    ((uint32_t)0x31000012)
#define CAN_FLAG_INAK                    ((uint32_t)0x31000001)
#define CAN_FLAG_ERRI                    ((uint32_t)0x31000004)
#define CAN_FLAG_BOF                     ((uint32_t)0x31000082)
#define CAN_FLAG_EPVF                    ((uint32_t)0x31000042)
#define CAN_FLAG_EWGF                    ((uint32_t)0x31000022)
#define CAN_FLAG_LEC                     ((uint32_t)0x31000070)

/* CAN 错误码 */
#define CAN_ErrorCode_NoErr              ((uint8_t)0x00)
#define CAN_ErrorCode_StuffErr           ((uint8_t)0x10)
#define CAN_ErrorCode_FormErr            ((uint8_t)0x20)
#define CAN_ErrorCode_ACKErr             ((uint8_t)0x30)
#define CAN_ErrorCode_BitRecessiveErr    ((uint8_t)0x40)
#define CAN_ErrorCode_BitDominantErr     ((uint8_t)0x50)
#define CAN_ErrorCode_CRCErr             ((uint8_t)0x60)
#define CAN_ErrorCode_SoftwareSetErr     ((uint8_t)0x70)

/* ========================================================================= */
/*                        CAN Exported Functions                            */
/* ========================================================================= */

/** @brief 复位 CAN 外设 */
void CAN_DeInit(CAN_TypeDef* CANx);

/** @brief 初始化 CAN (进入正常模式前需初始化) */
uint8_t CAN_Init(CAN_TypeDef* CANx, CAN_InitTypeDef* CAN_InitStruct);

/** @brief 初始化过滤器 */
void CAN_FilterInit(CAN_FilterInitTypeDef* CAN_FilterInitStruct);

/** @brief 发送消息 (读取全局 CAN_TxMsg), 返回邮箱号或失败 */
uint8_t CAN_Transmit(CAN_TypeDef* CANx, CanTxMsg* TxMessage);

/** @brief 获取指定邮箱的发送状态 */
uint8_t CAN_TransmitStatus(CAN_TypeDef* CANx, uint8_t TransmitMailbox);

/** @brief 获取指定邮箱的发送状态 (与 CAN_TransmitStatus 相同) */
uint8_t CAN_GetTransmitStatus(CAN_TypeDef* CANx, uint8_t TransmitMailbox);

/** @brief 取消发送 */
void CAN_CancelTransmit(CAN_TypeDef* CANx, uint8_t Mailbox);

/** @brief 接收消息 */
void CAN_Receive(CAN_TypeDef* CANx, uint8_t FIFONum, CanRxMsg* RxMessage);

/** @brief 释放指定 FIFO 邮箱 */
void CAN_ReleaseFIFO(CAN_TypeDef* CANx, uint8_t FIFONum);

/** @brief 获取标志状态 */
FlagStatus CAN_GetFlagStatus(CAN_TypeDef* CANx, uint32_t CAN_FLAG);

/** @brief 获取错误码 */
uint8_t CAN_GetErrorCode(CAN_TypeDef* CANx);

/* ========================================================================= */
/*                     CAN 全局收发消息结构体                               */
/* ========================================================================= */
extern CanTxMsg CAN_TxMsg;
extern CanRxMsg CAN_RxMsg;

#endif /* __STM32F10X_CAN_H */
