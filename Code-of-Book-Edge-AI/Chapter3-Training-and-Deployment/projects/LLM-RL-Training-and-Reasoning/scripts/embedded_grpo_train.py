#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Embedded C++ Code Generation Training with SFT + GRPO
基于嵌入式 C++ 代码的 SFT + GRPO 训练脚本

Features:
- SFT: 教模型生成嵌入式代码格式
- GRPO: 用编译验证作为奖励函数

Author: Xinyu Wei (Microsoft GBB AI Architect)
"""

import os, torch, subprocess, tempfile, re, math, gc, argparse, warnings
import numpy as np
import pandas as pd
from datasets import load_dataset, Dataset
from transformers import TrainerCallback
import collections

# Disable warnings
warnings.filterwarnings("ignore")

# ============ Stub for wandb (offline training) ============
import sys, types, importlib.machinery
wb = types.ModuleType("wandb")
wb.__spec__ = importlib.machinery.ModuleSpec("wandb", loader=None)
wb.run = None
for fn in ("init", "login", "finish", "watch", "log", "config"):
    setattr(wb, fn, lambda *a, **k: None)
sys.modules["wandb"] = wb

# ============ CLI Arguments ============
def get_args():
    p = argparse.ArgumentParser(description="Embedded C++ SFT + GRPO Training")
    p.add_argument("--base_model", default="Qwen/Qwen2.5-Coder-7B")
    p.add_argument("--max_seq_len", type=int, default=2048)
    p.add_argument("--lora_rank", type=int, default=16)
    p.add_argument("--batch_size", type=int, default=2)
    p.add_argument("--num_gen", type=int, default=4)
    p.add_argument("--do_sft", action="store_true")
    p.add_argument("--sft_epochs", type=int, default=1)
    p.add_argument("--sft_sample_frac", type=float, default=1.0)
    p.add_argument("--grpo_steps", type=int, default=300)
    p.add_argument("--print_every", type=int, default=10)
    p.add_argument("--debug_every", type=int, default=50)
    p.add_argument("--save_dir", default="outputs_embedded")
    p.add_argument("--toolchain", default="arm-none-eabi-gcc",
                   help="Cross compiler: arm-none-eabi-gcc, clang, etc.")
    p.add_argument("--use_syntax_only", action="store_true", default=True,
                   help="Only check syntax (faster) instead of full compile")
    return p.parse_args()

# ============ Prompt Templates ============
CODE_START = "<code>"
CODE_END = "</code>"
THINK_START = "<think>"
THINK_END = "</think>"

SYSTEM_PROMPT = f"""You are an expert embedded C/C++ programmer specializing in STM32, FreeRTOS, and hardware drivers.
When given a coding task:
1. First think about the solution between {THINK_START} and {THINK_END}
2. Then provide the complete code between {CODE_START} and {CODE_END}

Your code should:
- Follow embedded best practices (no dynamic allocation, handle hardware registers properly)
- Include necessary headers
- Be compilable with arm-none-eabi-gcc"""

# ============ Chat Template ============
def chat_template():
    return (
        "{% for m in messages %}"
        "{% if m['role']=='system' %}"
        "<|system|>{{ m['content'] }}<|end|>"
        "{% elif m['role']=='user' %}"
        "<|user|>{{ m['content'] }}<|end|>"
        "{% elif m['role']=='assistant' %}"
        "<|assistant|>{{ m['content'] }}<|end|>"
        "{% endif %}{% endfor %}"
        "{% if add_generation_prompt %}"
        "<|assistant|>{{ '" + THINK_START + "' }}"
        "{% endif %}"
    )

# ============ Reward Functions ============

# STM32 常用头文件 stub（用于语法检查）
STM32_STUB_HEADERS = '''
// Minimal STM32 HAL stub for syntax checking
#ifndef __STM32_STUB_H
#define __STM32_STUB_H

typedef unsigned int uint32_t;
typedef unsigned short uint16_t;
typedef unsigned char uint8_t;
typedef int int32_t;

#define __IO volatile

typedef struct {
    __IO uint32_t CR1;
    __IO uint32_t CR2;
    __IO uint32_t SR;
    __IO uint32_t DR;
    __IO uint32_t BRR;
} USART_TypeDef;

typedef struct {
    __IO uint32_t MODER;
    __IO uint32_t OTYPER;
    __IO uint32_t OSPEEDR;
    __IO uint32_t PUPDR;
    __IO uint32_t IDR;
    __IO uint32_t ODR;
    __IO uint32_t BSRR;
} GPIO_TypeDef;

extern USART_TypeDef *USART1, *USART2;
extern GPIO_TypeDef *GPIOA, *GPIOB, *GPIOC;

// HAL types
typedef struct {
    void *Instance;
    struct {
        uint32_t BaudRate;
        uint32_t WordLength;
        uint32_t StopBits;
        uint32_t Parity;
        uint32_t Mode;
        uint32_t HwFlowCtl;
    } Init;
} UART_HandleTypeDef;

typedef struct {
    uint32_t Pin;
    uint32_t Mode;
    uint32_t Pull;
    uint32_t Speed;
    uint32_t Alternate;
} GPIO_InitTypeDef;

// HAL macros
#define GPIO_PIN_0  0x0001
#define GPIO_PIN_1  0x0002
#define GPIO_PIN_5  0x0020
#define GPIO_PIN_13 0x2000

#define GPIO_MODE_INPUT     0
#define GPIO_MODE_OUTPUT_PP 1
#define GPIO_MODE_AF_PP     2
#define GPIO_NOPULL         0
#define GPIO_PULLUP         1
#define GPIO_SPEED_FREQ_LOW 0
#define GPIO_SPEED_FREQ_HIGH 2

#define UART_WORDLENGTH_8B 0
#define UART_STOPBITS_1    0
#define UART_PARITY_NONE   0
#define UART_MODE_TX_RX    3

#define HAL_OK 0
#define HAL_ERROR 1

// GPIO Pin State
#define GPIO_PIN_RESET 0
#define GPIO_PIN_SET   1

// HAL functions
static inline void __HAL_RCC_GPIOA_CLK_ENABLE(void) {}
static inline void __HAL_RCC_GPIOB_CLK_ENABLE(void) {}
static inline void __HAL_RCC_USART1_CLK_ENABLE(void) {}

static inline int HAL_GPIO_Init(GPIO_TypeDef *GPIOx, GPIO_InitTypeDef *GPIO_Init) { return HAL_OK; }
static inline int HAL_UART_Init(UART_HandleTypeDef *huart) { return HAL_OK; }
static inline void HAL_GPIO_WritePin(GPIO_TypeDef *GPIOx, uint16_t GPIO_Pin, int PinState) {}
static inline int HAL_GPIO_ReadPin(GPIO_TypeDef *GPIOx, uint16_t GPIO_Pin) { return 0; }
static inline void HAL_Delay(uint32_t Delay) {}

// FreeRTOS stubs
typedef void* TaskHandle_t;
typedef void* QueueHandle_t;
typedef unsigned int BaseType_t;
typedef unsigned int TickType_t;
#define pdTRUE 1
#define pdFALSE 0
#define portMAX_DELAY 0xFFFFFFFF

static inline BaseType_t xTaskCreate(void (*pxTaskCode)(void*), const char* pcName, 
    uint16_t usStackDepth, void* pvParameters, unsigned int uxPriority, TaskHandle_t* pxCreatedTask) { return pdTRUE; }
static inline void vTaskDelay(TickType_t xTicksToDelay) {}
static inline QueueHandle_t xQueueCreate(unsigned int uxQueueLength, unsigned int uxItemSize) { return (void*)1; }
static inline BaseType_t xQueueSend(QueueHandle_t xQueue, const void* pvItemToQueue, TickType_t xTicksToWait) { return pdTRUE; }
static inline BaseType_t xQueueReceive(QueueHandle_t xQueue, void* pvBuffer, TickType_t xTicksToWait) { return pdTRUE; }

#endif
'''

def extract_code(text):
    """从生成文本中提取代码块"""
    # 尝试提取 <code>...</code> 之间的内容
    match = re.search(r'<code>\s*(.*?)\s*</code>', text, re.DOTALL)
    if match:
        return match.group(1)
    
    # 尝试提取 ```c 或 ```cpp 代码块
    match = re.search(r'```(?:c|cpp|c\+\+)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    
    # 如果没有标记，尝试提取看起来像代码的部分
    lines = text.split('\n')
    code_lines = []
    in_code = False
    for line in lines:
        if any(kw in line for kw in ['#include', 'void ', 'int ', 'typedef', 'struct', '{', '}']):
            in_code = True
        if in_code:
            code_lines.append(line)
    
    return '\n'.join(code_lines) if code_lines else text


def check_syntax(code, use_clang=True):
    """
    快速语法检查（不需要完整编译）
    返回: (success: bool, error_msg: str)
    """
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as stub_f:
        stub_f.write(STM32_STUB_HEADERS)
        stub_path = stub_f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as code_f:
        # 包含 stub 头文件
        code_f.write(f'#include "{stub_path}"\n\n')
        code_f.write(code)
        code_path = code_f.name
    
    try:
        if use_clang:
            # clang -fsyntax-only 非常快（几毫秒）
            result = subprocess.run(
                ['clang', '-fsyntax-only', '-x', 'c', '-std=c11', 
                 '-Wno-implicit-function-declaration', code_path],
                capture_output=True, text=True, timeout=5
            )
        else:
            # 使用 arm-none-eabi-gcc
            result = subprocess.run(
                ['arm-none-eabi-gcc', '-fsyntax-only', '-x', 'c', code_path],
                capture_output=True, text=True, timeout=10
            )
        
        success = result.returncode == 0
        error_msg = result.stderr if not success else ""
        return success, error_msg
    
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)
    finally:
        os.unlink(stub_path)
        os.unlink(code_path)


def check_compile(code, toolchain="arm-none-eabi-gcc"):
    """
    完整交叉编译检查
    返回: (success: bool, warnings: int, error_msg: str)
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as stub_f:
        stub_f.write(STM32_STUB_HEADERS)
        stub_path = stub_f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as code_f:
        code_f.write(f'#include "{stub_path}"\n\n')
        code_f.write(code)
        code_path = code_f.name
    
    obj_path = code_path.replace('.c', '.o')
    
    try:
        result = subprocess.run(
            [toolchain, '-c', '-Wall', '-Wextra', '-mcpu=cortex-m4', '-mthumb',
             code_path, '-o', obj_path],
            capture_output=True, text=True, timeout=30
        )
        
        success = result.returncode == 0
        # 统计警告数量
        warnings = result.stderr.count('warning:')
        error_msg = result.stderr if not success else ""
        
        return success, warnings, error_msg
    
    except subprocess.TimeoutExpired:
        return False, 0, "Timeout"
    except Exception as e:
        return False, 0, str(e)
    finally:
        os.unlink(stub_path)
        os.unlink(code_path)
        if os.path.exists(obj_path):
            os.unlink(obj_path)


def run_cppcheck(code):
    """
    静态分析检查
    返回: (issues: int, report: str)
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
        f.write(code)
        code_path = f.name
    
    try:
        result = subprocess.run(
            ['cppcheck', '--enable=warning,style', '--quiet', code_path],
            capture_output=True, text=True, timeout=10
        )
        
        issues = result.stderr.count('\n') if result.stderr else 0
        return issues, result.stderr
    
    except Exception as e:
        return 0, str(e)
    finally:
        os.unlink(code_path)


# ============ GRPO Reward Functions ============

def reward_format(completions, **_):
    """格式奖励：检查是否包含必要的标记"""
    scores = []
    for comp in completions:
        text = comp[0]["content"]
        score = 0.0
        
        # 检查思考标记
        if THINK_START in text:
            score += 0.5
        if THINK_END in text:
            score += 0.5
        
        # 检查代码标记
        if CODE_START in text:
            score += 1.0
        if CODE_END in text:
            score += 1.0
        
        # 检查代码内容不为空
        code = extract_code(text)
        if len(code.strip()) > 20:
            score += 1.0
        
        scores.append(min(4.0, score))
    
    return scores


def reward_syntax(completions, use_clang=True, **_):
    """语法检查奖励"""
    scores = []
    for comp in completions:
        text = comp[0]["content"]
        code = extract_code(text)
        
        if not code or len(code.strip()) < 10:
            scores.append(-2.0)
            continue
        
        success, error = check_syntax(code, use_clang=use_clang)
        
        if success:
            scores.append(3.0)  # 语法正确
        else:
            # 根据错误数量给部分分
            error_count = error.count('error:')
            if error_count == 0:
                scores.append(1.0)  # 只有警告
            elif error_count <= 2:
                scores.append(-0.5)  # 少量错误
            else:
                scores.append(-2.0)  # 大量错误
    
    return scores


def reward_compile(completions, toolchain="arm-none-eabi-gcc", **_):
    """编译奖励（完整编译检查）"""
    scores = []
    for comp in completions:
        text = comp[0]["content"]
        code = extract_code(text)
        
        if not code or len(code.strip()) < 10:
            scores.append(-2.0)
            continue
        
        success, warnings, error = check_compile(code, toolchain=toolchain)
        
        if success:
            if warnings == 0:
                scores.append(5.0)  # 编译成功且无警告
            elif warnings <= 2:
                scores.append(4.0)  # 编译成功，少量警告
            else:
                scores.append(3.0)  # 编译成功，较多警告
        else:
            scores.append(-1.0)  # 编译失败
    
    return scores


def reward_static_analysis(completions, **_):
    """静态分析奖励"""
    scores = []
    for comp in completions:
        text = comp[0]["content"]
        code = extract_code(text)
        
        if not code or len(code.strip()) < 10:
            scores.append(0.0)
            continue
        
        issues, _ = run_cppcheck(code)
        
        if issues == 0:
            scores.append(1.0)
        elif issues <= 2:
            scores.append(0.5)
        else:
            scores.append(0.0)
    
    return scores


# ============ Debug Callback ============
def make_debug(freq, num_gen):
    """创建调试回调，打印生成结果和奖励"""
    step = {"i": 0}
    
    def _dbg(prompts=None, completions=None, **_):
        step["i"] += 1
        if step["i"] % freq:
            return [0.0] * len(completions)
        
        fmt_scores = reward_format(completions)
        syn_scores = reward_syntax(completions)
        
        total_comps = len(completions)
        for p_idx, prompt in enumerate(prompts):
            start = p_idx * num_gen
            end = min(start + num_gen, total_comps)
            
            print("=" * 100)
            print(f"PROMPT: {prompt[-1]['content'][:200]}...")
            
            for j, (comp, fmt, syn) in enumerate(
                    zip(completions[start:end], fmt_scores[start:end], syn_scores[start:end])):
                total = fmt + syn
                print(f"\n[Candidate {j}] format={fmt:+.1f} syntax={syn:+.1f} total={total:+.1f}")
                code = extract_code(comp[0]["content"])
                print(f"Code preview:\n{code[:300]}...")
        
        return [0.0] * len(completions)
    
    return _dbg


# ============ Advantage Callback ============
class AdvantageCallback(TrainerCallback):
    def __init__(self, alpha=0.1, window=100):
        self.alpha = alpha
        self.baseline = None
        self.buffer = collections.deque(maxlen=window)
    
    def on_train_batch_end(self, args, state, control, logs=None, **__):
        if not logs or "reward" not in logs:
            return
        
        r = logs["reward"]
        self.baseline = r if self.baseline is None else (1 - self.alpha) * self.baseline + self.alpha * r
        self.buffer.append(r)
        
        success_rate = sum(x > 0 for x in self.buffer) / len(self.buffer)
        print(f"[Step {state.global_step:>4}] reward={r:+.2f} "
              f"baseline={self.baseline:+.2f} adv={r - self.baseline:+.2f} "
              f"success_rate={success_rate:.3f}")


# ============ Dataset Helpers ============

# 嵌入式代码任务示例
EMBEDDED_TASKS = [
    {
        "task": "Initialize GPIO PA5 as output for LED",
        "code": """void LED_GPIO_Init(void) {
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    
    __HAL_RCC_GPIOA_CLK_ENABLE();
    
    GPIO_InitStruct.Pin = GPIO_PIN_5;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}"""
    },
    {
        "task": "Initialize UART1 with 115200 baud rate",
        "code": """UART_HandleTypeDef huart1;

void UART1_Init(void) {
    __HAL_RCC_USART1_CLK_ENABLE();
    
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    HAL_UART_Init(&huart1);
}"""
    },
    {
        "task": "Create a FreeRTOS task that blinks an LED every 500ms",
        "code": """void LED_Blink_Task(void *pvParameters) {
    while (1) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, 1);
        vTaskDelay(500);
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, 0);
        vTaskDelay(500);
    }
}

void Create_LED_Task(void) {
    xTaskCreate(LED_Blink_Task, "LED_Blink", 128, NULL, 1, NULL);
}"""
    },
    {
        "task": "Implement a simple delay function using a loop",
        "code": """void delay_ms(uint32_t ms) {
    volatile uint32_t count;
    while (ms--) {
        // Assuming 72MHz clock, rough approximation
        for (count = 0; count < 7200; count++) {
            __asm__ volatile ("nop");
        }
    }
}"""
    },
    {
        "task": "Read a button state from GPIO PB0 with debounce",
        "code": """int Read_Button_Debounced(void) {
    static int last_state = 0;
    static uint32_t last_time = 0;
    int current_state;
    
    current_state = HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_0);
    
    if (current_state != last_state) {
        HAL_Delay(50);  // Debounce delay
        current_state = HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_0);
    }
    
    last_state = current_state;
    return current_state;
}"""
    },
    {
        "task": "Create a circular buffer for UART receive",
        "code": """#define BUFFER_SIZE 64

typedef struct {
    uint8_t buffer[BUFFER_SIZE];
    uint16_t head;
    uint16_t tail;
    uint16_t count;
} CircularBuffer;

void CircularBuffer_Init(CircularBuffer *cb) {
    cb->head = 0;
    cb->tail = 0;
    cb->count = 0;
}

int CircularBuffer_Push(CircularBuffer *cb, uint8_t data) {
    if (cb->count >= BUFFER_SIZE) {
        return -1;  // Buffer full
    }
    cb->buffer[cb->head] = data;
    cb->head = (cb->head + 1) % BUFFER_SIZE;
    cb->count++;
    return 0;
}

int CircularBuffer_Pop(CircularBuffer *cb, uint8_t *data) {
    if (cb->count == 0) {
        return -1;  // Buffer empty
    }
    *data = cb->buffer[cb->tail];
    cb->tail = (cb->tail + 1) % BUFFER_SIZE;
    cb->count--;
    return 0;
}"""
    },
    {
        "task": "Configure SysTick timer for 1ms interrupt",
        "code": """volatile uint32_t systick_counter = 0;

void SysTick_Init(void) {
    // Assuming 72MHz system clock
    // SysTick reload = (72000000 / 1000) - 1 = 71999
    // This gives 1ms tick
}

void SysTick_Handler(void) {
    systick_counter++;
}

uint32_t HAL_GetTick(void) {
    return systick_counter;
}"""
    },
    {
        "task": "Implement a simple state machine for a washing machine",
        "code": """typedef enum {
    STATE_IDLE,
    STATE_FILL,
    STATE_WASH,
    STATE_RINSE,
    STATE_SPIN,
    STATE_DONE
} WashState;

typedef struct {
    WashState current_state;
    uint32_t timer;
} WashMachine;

void WashMachine_Init(WashMachine *wm) {
    wm->current_state = STATE_IDLE;
    wm->timer = 0;
}

void WashMachine_Update(WashMachine *wm) {
    switch (wm->current_state) {
        case STATE_IDLE:
            // Wait for start button
            break;
        case STATE_FILL:
            if (wm->timer >= 5000) {
                wm->current_state = STATE_WASH;
                wm->timer = 0;
            }
            break;
        case STATE_WASH:
            if (wm->timer >= 30000) {
                wm->current_state = STATE_RINSE;
                wm->timer = 0;
            }
            break;
        case STATE_RINSE:
            if (wm->timer >= 10000) {
                wm->current_state = STATE_SPIN;
                wm->timer = 0;
            }
            break;
        case STATE_SPIN:
            if (wm->timer >= 15000) {
                wm->current_state = STATE_DONE;
            }
            break;
        case STATE_DONE:
            wm->current_state = STATE_IDLE;
            break;
    }
    wm->timer++;
}"""
    },
]


def build_messages(task, code=None, thoughts=None):
    """构建聊天消息"""
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Write embedded C code to: {task}"},
    ]
    if code and thoughts:
        assistant_content = f"{THINK_START}{thoughts}{THINK_END}\n{CODE_START}\n{code}\n{CODE_END}"
        msgs.append({"role": "assistant", "content": assistant_content})
    return msgs


def create_sft_dataset(tokenizer, sample_frac=1.0):
    """创建 SFT 训练数据集"""
    data = []
    
    for item in EMBEDDED_TASKS:
        thoughts = f"Let me implement {item['task']}. I need to consider hardware initialization and proper register configuration."
        msgs = build_messages(item["task"], item["code"], thoughts)
        text = tokenizer.apply_chat_template(msgs, tokenize=False)
        data.append({"text": text})
    
    # 复制数据以增加训练量
    data = data * 50  # 复制 50 次
    
    df = pd.DataFrame(data)
    if 0 < sample_frac < 1:
        df = df.sample(frac=sample_frac, random_state=42).reset_index(drop=True)
    
    return Dataset.from_pandas(df)


def create_grpo_dataset(tokenizer, max_prompt_len=512):
    """创建 GRPO 训练数据集"""
    # 使用更多变化的任务
    additional_tasks = [
        "Toggle LED on GPIO PA5",
        "Initialize I2C peripheral",
        "Read temperature from ADC",
        "Send data over UART",
        "Configure PWM output for motor control",
        "Implement a simple PID controller",
        "Create a message queue for inter-task communication",
        "Read multiple buttons with interrupt",
        "Implement a software timer",
        "Configure external interrupt on PA0",
    ]
    
    data = []
    for task in additional_tasks + [t["task"] for t in EMBEDDED_TASKS]:
        msgs = build_messages(task)
        data.append({
            "prompt": msgs,
            "task": task
        })
    
    # 复制数据
    data = data * 20
    
    return Dataset.from_list(data)


# ============ Main Training ============
def main():
    args = get_args()
    
    print(f"Loading model: {args.base_model}")
    print(f"Toolchain: {args.toolchain}")
    print(f"Use syntax-only check: {args.use_syntax_only}")
    
    # Import training libraries
    from unsloth import FastLanguageModel
    from trl import SFTTrainer, SFTConfig, GRPOTrainer, GRPOConfig
    from vllm import SamplingParams
    
    # Load model
    model, tokenizer = FastLanguageModel.from_pretrained(
        args.base_model,
        max_seq_length=args.max_seq_len,
        load_in_4bit=False,
        fast_inference=False,
    )
    
    # Add LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_rank,
        use_gradient_checkpointing="unsloth",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
    )
    
    # Set chat template
    tokenizer.chat_template = chat_template()
    
    # ===== Stage 1: SFT =====
    if args.do_sft and args.sft_epochs > 0:
        print("\n" + "=" * 60)
        print("Stage 1: Supervised Fine-Tuning (SFT)")
        print("=" * 60)
        
        sft_dataset = create_sft_dataset(tokenizer, args.sft_sample_frac)
        print(f"SFT dataset size: {len(sft_dataset)}")
        
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=sft_dataset,
            args=SFTConfig(
                per_device_train_batch_size=args.batch_size,
                num_train_epochs=args.sft_epochs,
                logging_steps=args.print_every,
                output_dir=os.path.join(args.save_dir, "sft"),
                report_to="none",
            ),
        )
        trainer.train()
        
        del sft_dataset, trainer
        gc.collect()
        torch.cuda.empty_cache()
    
    # ===== Stage 2: GRPO =====
    print("\n" + "=" * 60)
    print("Stage 2: Group Relative Policy Optimization (GRPO)")
    print("=" * 60)
    
    grpo_dataset = create_grpo_dataset(tokenizer)
    print(f"GRPO dataset size: {len(grpo_dataset)}")
    
    # 选择奖励函数
    if args.use_syntax_only:
        reward_funcs = [
            make_debug(args.debug_every, args.num_gen),
            reward_format,
            reward_syntax,
        ]
        print("Using: format + syntax rewards (fast mode)")
    else:
        reward_funcs = [
            make_debug(args.debug_every, args.num_gen),
            reward_format,
            reward_compile,
            reward_static_analysis,
        ]
        print("Using: format + compile + static analysis rewards (full mode)")
    
    grpo_config = GRPOConfig(
        vllm_sampling_params=SamplingParams(
            max_tokens=512,
            temperature=0.7,
            min_p=0.05,
            top_p=0.9,
            top_k=-1,
            stop=[CODE_END, tokenizer.eos_token],
        ),
        learning_rate=5e-6,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=2,
        num_generations=args.num_gen,
        max_prompt_length=args.max_seq_len // 2,
        max_completion_length=512,
        max_steps=args.grpo_steps,
        logging_steps=args.print_every,
        output_dir=os.path.join(args.save_dir, "grpo"),
        report_to="none",
    )
    
    grpo_trainer = GRPOTrainer(
        model=model,
        args=grpo_config,
        train_dataset=grpo_dataset,
        processing_class=tokenizer,
        reward_funcs=reward_funcs,
        callbacks=[AdvantageCallback()],
    )
    grpo_trainer.train()
    
    # Save model
    output_dir = os.path.join(args.save_dir, "embedded_coder_final")
    model.save_pretrained_merged(output_dir, tokenizer, save_method="merged_16bit")
    print(f"\nModel saved to: {output_dir}")


if __name__ == "__main__":
    main()
