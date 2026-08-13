/**
  ******************************************************************************
  * @file    SRC/action_group/y_action_group.c
  * @author  Q
  * @version V1.0.0
  * @date    2026-07-23
  * @brief   动作组管理模块实现
  *          支持动作组的录制、存储、回放功能
  *          动作组存储在RAM中，通过Flash持久化
  *          回放: 按帧顺序发送舵机命令，支持循环
  *          录制: 定时采样当前舵机位置作为动作帧
  ******************************************************************************
  * @attention
  * 版权所有 (C) 2026 友辉科技
  * 本软件按"原样"提供，不附带任何明示或暗示的保证。
  ******************************************************************************
  */

/* 包含头文件 ------------------------------------------------------------------*/
#include "y_action_group.h"
#include "y_bus_servo.h"
#include "y_flash.h"
#include <string.h>
#include <stdio.h>

/* 外部函数声明 ----------------------------------------------------------------*/
extern uint32_t get_systick(void);				/* 获取系统滴答 */
extern void delay_ms(uint32_t ms);				/* 毫秒延时 */

/* 全局变量定义 ----------------------------------------------------------------*/

/**
  * @brief  动作组数组
  */
action_group_t action_groups[MAX_ACTION_GROUPS];

/**
  * @brief  已存储动作组总数
  */
uint8_t ag_total_count = 0;

/**
  * @brief  当前播放状态
  */
ag_state_t ag_current_state = AG_STATE_IDLE;

/* 私有变量 --------------------------------------------------------------------*/
static uint8_t  ag_current_id;					/* 当前操作的动作组ID */
static uint8_t  ag_current_frame;				/* 当前播放/录制的帧索引 */
static uint16_t ag_loop_remaining;				/* 剩余循环次数 */
static uint32_t ag_frame_start_time;			/* 当前帧开始时间 */
static uint8_t  ag_recording_id;				/* 正在录制的动作组ID */

/**
  * @brief  动作组模块初始化
  * @param  无
  * @返回值 无
  * @说明   从Flash加载所有动作组数据到RAM
  */
void ag_init(void)
{
	uint8_t i;

	/* 初始化动作组数组 */
	for (i = 0; i < MAX_ACTION_GROUPS; i++)
	{
		action_groups[i].id          = i;
		action_groups[i].action_count = 0;
		action_groups[i].loop_count  = 1;
		action_groups[i].name[0]     = '\0';
	}

	/* 初始化状态 */
	ag_current_state = AG_STATE_IDLE;
	ag_current_frame = 0;
	ag_loop_remaining = 0;
	ag_total_count = 0;

	/* 从Flash加载动作组 */
	ag_load_all();
}

/**
  * @brief  从Flash加载所有动作组
  * @param  无
  * @返回值 0: 成功, 1: 失败
  * @说明   遍历所有可能的动作组ID，从Flash加载到RAM
  */
uint8_t ag_load_all(void)
{
	uint8_t  i;
	uint8_t  loaded = 0;
	uint8_t  result;

	for (i = 0; i < MAX_ACTION_GROUPS; i++)
	{
		result = flash_load_action_group(i, &action_groups[i], sizeof(action_group_t));
		if (result == 0)
		{
			loaded++;
		}
	}

	ag_total_count = loaded;

	return (loaded > 0) ? 0 : 1;
}

/**
  * @brief  播放指定动作组
  * @param  id: 动作组ID
  * @返回值 0: 成功, 1: 失败
  * @说明   开始播放动作组，重置帧索引和循环计数
  */
uint8_t ag_play(uint8_t id)
{
	if (id >= MAX_ACTION_GROUPS)
	{
		return 1;
	}

	if (action_groups[id].action_count == 0)
	{
		return 1;	/* 空动作组 */
	}

	/* 停止当前播放 */
	if (ag_current_state == AG_STATE_PLAYING)
	{
		ag_stop();
	}

	/* 设置播放参数 */
	ag_current_id    = id;
	ag_current_frame  = 0;
	ag_loop_remaining = action_groups[id].loop_count;
	ag_current_state  = AG_STATE_PLAYING;
	ag_frame_start_time = get_systick();

	/* 发送第一帧 */
	{
		action_frame_t *frame = &action_groups[id].actions[0];
		bus_servo_set_all(frame->positions, frame->time);
	}

	return 0;
}

/**
  * @brief  停止当前动作组播放
  * @param  无
  * @返回值 无
  * @说明   停止播放并停止所有舵机运动
  */
void ag_stop(void)
{
	ag_current_state = AG_STATE_STOPPED;
	bus_servo_stop();
}

/**
  * @brief  开始录制动作组
  * @param  id: 动作组ID
  * @返回值 0: 成功, 1: 失败
  * @说明   进入录制模式，初始化动作组
  */
uint8_t ag_record_start(uint8_t id)
{
	if (id >= MAX_ACTION_GROUPS)
	{
		return 1;
	}

	/* 初始化动作组 */
	action_groups[id].id           = id;
	action_groups[id].action_count = 0;
	action_groups[id].loop_count   = 1;

	/* 设置录制状态 */
	ag_recording_id   = id;
	ag_current_frame   = 0;
	ag_current_state   = AG_STATE_RECORDING;

	return 0;
}

/**
  * @brief  录制一帧动作
  * @param  无
  * @返回值 0: 成功, 1: 失败
  * @说明   采样当前所有舵机位置，作为一帧添加到动作组
  */
uint8_t ag_record_frame(void)
{
	uint8_t          i;
	action_frame_t  *frame;

	if (ag_current_state != AG_STATE_RECORDING)
	{
		return 1;
	}

	if (ag_current_frame >= MAX_ACTIONS_PER_GROUP)
	{
		return 1;	/* 动作帧已满 */
	}

	/* 获取当前帧指针 */
	frame = &action_groups[ag_recording_id].actions[ag_current_frame];

	/* 采样所有舵机位置 */
	for (i = 0; i < MAX_SERVO_NUM; i++)
	{
		frame->positions[i] = bus_servo_get_position(i);
	}

	/* 默认运动时间500ms */
	frame->time = 500;

	/* 更新动作组计数 */
	ag_current_frame++;
	action_groups[ag_recording_id].action_count = ag_current_frame;

	return 0;
}

/**
  * @brief  保存当前动作组到Flash
  * @param  无
  * @返回值 0: 成功, 1: 失败
  * @说明   将当前录制的动作组保存到Flash
  */
uint8_t ag_save(void)
{
	if (ag_current_state != AG_STATE_RECORDING)
	{
		return 1;
	}

	if (action_groups[ag_recording_id].action_count == 0)
	{
		return 1;	/* 空动作组不保存 */
	}

	/* 保存到Flash */
	if (flash_save_action_group(ag_recording_id,
		&action_groups[ag_recording_id],
		sizeof(action_group_t)) != 0)
	{
		return 1;
	}

	/* 更新总数 */
	if (ag_recording_id >= ag_total_count)
	{
		ag_total_count = ag_recording_id + 1;
	}

	/* 退出录制状态 */
	ag_current_state = AG_STATE_IDLE;

	return 0;
}

/**
  * @brief  动作组运行函数
  * @param  无
  * @返回值 无
  * @说明   在主循环中调用，执行动作组播放
  */
void ag_run(void)
{
	action_frame_t *frame;
	uint32_t        now;
	uint32_t        elapsed;

	if (ag_current_state != AG_STATE_PLAYING)
	{
		return;
	}

	now = get_systick();
	elapsed = now - ag_frame_start_time;

	/* 获取当前帧 */
	frame = &action_groups[ag_current_id].actions[ag_current_frame];

	/* 检查当前帧是否完成 */
	if (elapsed >= frame->time)
	{
		/* 前进到下一帧 */
		ag_current_frame++;

		/* 检查是否到达动作组末尾 */
		if (ag_current_frame >= action_groups[ag_current_id].action_count)
		{
			/* 检查循环 */
			if (ag_loop_remaining == 0)
			{
				/* 无限循环 */
				ag_current_frame = 0;
			}
			else if (ag_loop_remaining > 1)
			{
				ag_loop_remaining--;
				ag_current_frame = 0;
			}
			else
			{
				/* 播放完成 */
				ag_current_state = AG_STATE_IDLE;
				return;
			}
		}

		/* 发送下一帧 */
		frame = &action_groups[ag_current_id].actions[ag_current_frame];
		bus_servo_set_all(frame->positions, frame->time);
		ag_frame_start_time = now;
	}
}

/**
  * @brief  列出所有动作组信息
  * @param  buf: 输出缓冲区
  * @param  buf_size: 缓冲区大小
  * @返回值 无
  * @说明   将动作组列表信息格式化输出到缓冲区
  */
void ag_list(char *buf, uint16_t buf_size)
{
	uint8_t  i;
	uint16_t offset = 0;
	int      len;

	offset += snprintf(buf + offset, buf_size - offset,
		"Action Groups: %d\r\n", ag_total_count);

	for (i = 0; i < ag_total_count; i++)
	{
		if (action_groups[i].action_count > 0)
		{
			len = snprintf(buf + offset, buf_size - offset,
				"  ID:%d  Frames:%d  Loops:%d  Name:%s\r\n",
				action_groups[i].id,
				action_groups[i].action_count,
				action_groups[i].loop_count,
				action_groups[i].name);
			offset += len;
		}
	}
}

/**
  * @brief  删除指定动作组
  * @param  id: 动作组ID
  * @返回值 0: 成功, 1: 失败
  */
uint8_t ag_delete(uint8_t id)
{
	if (id >= MAX_ACTION_GROUPS)
	{
		return 1;
	}

	/* 清除动作组数据 */
	action_groups[id].action_count = 0;
	action_groups[id].loop_count   = 1;
	action_groups[id].name[0]      = '\0';

	/* 更新总数 */
	if (id < ag_total_count)
	{
		ag_total_count--;
	}

	return 0;
}

/**
  * @brief  获取动作组数量
  * @param  无
  * @返回值 动作组数量
  */
uint8_t ag_get_count(void)
{
	return ag_total_count;
}

/******************* (C) COPYRIGHT 2026 友辉科技 *****END OF FILE****/