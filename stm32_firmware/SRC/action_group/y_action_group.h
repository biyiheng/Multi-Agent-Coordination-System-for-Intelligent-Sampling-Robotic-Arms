/**
  ******************************************************************************
  * @file    SRC/action_group/y_action_group.h
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   动作组管理模块头文件
  *          支持动作组的录制、存储、回放功能
  *          每个动作组包含多个动作帧，每帧记录6个舵机的目标位置和运动时间
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 防止递归包含 ---------------------------------------------------------------*/
#ifndef __Y_ACTION_GROUP_H
#define __Y_ACTION_GROUP_H

/* 包含头文件 ------------------------------------------------------------------*/
#include "stm32f10x.h"

/* 宏定义 ----------------------------------------------------------------------*/
#define MAX_ACTION_GROUPS		8			/* 最大动作组数量 */
#define MAX_ACTIONS_PER_GROUP	30			/* 每个动作组最大动作帧数 */
#define MAX_SERVO_NUM			6			/* 舵机数量 */

/* 动作组状态枚举 --------------------------------------------------------------*/

/**
  * @brief  动作组播放状态枚举
  */
typedef enum
{
	AG_STATE_IDLE    = 0,					/* 空闲 */
	AG_STATE_PLAYING = 1,					/* 播放中 */
	AG_STATE_RECORDING = 2,					/* 录制中 */
	AG_STATE_PAUSED  = 3,					/* 暂停 */
	AG_STATE_STOPPED = 4					/* 已停止 */
} ag_state_t;

/* 动作帧数据结构体 ------------------------------------------------------------*/

/**
  * @brief  单个动作帧结构体
  *          记录一帧中6个舵机的目标位置和运动时间
  */
typedef struct
{
	uint16_t positions[6];					/* 6个舵机的目标位置 */
	uint16_t time;							/* 运动时间(ms) */
} action_frame_t;

/* 动作组数据结构体 ------------------------------------------------------------*/

/**
  * @brief  动作组结构体
  *          包含ID、动作帧数组、循环次数和标签
  */
typedef struct
{
	uint8_t        id;						/* 动作组ID */
	uint8_t        action_count;			/* 动作帧数量 */
	action_frame_t actions[MAX_ACTIONS_PER_GROUP];	/* 动作帧数组 */
	uint16_t       loop_count;				/* 循环次数(0=无限循环) */
	char           name[32];				/* 动作组名称 */
} action_group_t;

/* 全局变量声明 ----------------------------------------------------------------*/
extern action_group_t action_groups[MAX_ACTION_GROUPS];	/* 动作组数组 */
extern uint8_t        ag_total_count;					/* 已存储动作组总数 */
extern ag_state_t     ag_current_state;					/* 当前播放状态 */

/* 函数声明 --------------------------------------------------------------------*/

/**
  * @brief  动作组模块初始化
  * @param  无
  * @返回值 无
  * @说明   从Flash加载所有动作组数据到RAM
  */
void ag_init(void);

/**
  * @brief  从Flash加载所有动作组
  * @param  无
  * @返回值 0: 成功, 1: 失败
  */
uint8_t ag_load_all(void);

/**
  * @brief  播放指定动作组
  * @param  id: 动作组ID
  * @返回值 0: 成功, 1: 失败
  * @说明   开始播放动作组，在主循环中调用ag_run()执行帧
  */
uint8_t ag_play(uint8_t id);

/**
  * @brief  停止当前动作组播放
  * @param  无
  * @返回值 无
  */
void ag_stop(void);

/**
  * @brief  开始录制动作组
  * @param  id: 动作组ID
  * @返回值 0: 成功, 1: 失败
  * @说明   进入录制模式，通过ag_record_frame()添加动作帧
  */
uint8_t ag_record_start(uint8_t id);

/**
  * @brief  录制一帧动作
  * @param  无
  * @返回值 0: 成功, 1: 失败
  * @说明   采样当前所有舵机位置，作为一帧添加到动作组
  */
uint8_t ag_record_frame(void);

/**
  * @brief  保存当前动作组到Flash
  * @param  无
  * @返回值 0: 成功, 1: 失败
  */
uint8_t ag_save(void);

/**
  * @brief  动作组运行函数
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，执行动作组播放或录制
  */
void ag_run(void);

/**
  * @brief  列出所有动作组信息
  * @param  buf: 输出缓冲区
  * @param  buf_size: 缓冲区大小
  * @返回值 无
  * @说明   将动作组列表信息格式化输出到缓冲区
  */
void ag_list(char *buf, uint16_t buf_size);

/**
  * @brief  删除指定动作组
  * @param  id: 动作组ID
  * @返回值 0: 成功, 1: 失败
  */
uint8_t ag_delete(uint8_t id);

/**
  * @brief  获取动作组数量
  * @param  无
  * @返回值 动作组数量
  */
uint8_t ag_get_count(void);

#endif /* __Y_ACTION_GROUP_H */

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/