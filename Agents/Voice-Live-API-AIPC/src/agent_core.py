"""两个后端共用的角色设定与工具调用编排。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from . import tools
from .events import emit

logger = logging.getLogger(__name__)


def _argument_summary(arguments: str | None) -> str:
  if not arguments or arguments.strip() in ("", "{}"):
    return ""
  try:
    payload = json.loads(arguments)
  except (TypeError, ValueError, json.JSONDecodeError):
    return "参数已接收"
  if not isinstance(payload, dict):
    return "参数已接收"
  names = sorted(str(name) for name in payload if name != "confirmation_token")
  return "参数: " + ", ".join(names) if names else "参数已接收"


def _safe_error(error: object) -> str | None:
  if not error:
    return None
  category = str(error).partition(":")[0].strip()
  if category.endswith(("Error", "Exception")) and category.replace("_", "").isalnum():
    return f"{category}: 工具执行失败"
  return "工具执行失败"

INSTRUCTIONS = """你是运行在 Windows 电脑上的中文桌面语音助手，名字叫 Aria。
你可以调用工具完成这些事：查天气、查新闻、查股票行情、查时间和时区、修改本机系统时区、联网搜索、
整理新闻简报、把内容发到用户邮箱、生成桌面壁纸图片、更换 Windows 桌面壁纸、
打开或关闭摄像头实时画面、看摄像头当前画面识别物品、查商品哪里有卖、
查看和调节系统音量、静音或取消静音、打开 Windows 内置程序和显示桌面、
查看和调节屏幕亮度、切换电源模式（最佳能效/平衡/最佳性能）、
查看和设置多久自动关屏、多久进入睡眠、多久进入休眠。

对话规则：
- 全程用简洁自然的中文口语回答，一次不超过三句话，不要念 URL 和长串数字。
- 打招呼、确认能不能听见、道谢、闲聊这类不需要外部信息的话，直接一句话回应，不要调用任何工具。
- 只回答用户当前问的这件事。回答完就停住，不要主动推荐、罗列或询问用户要不要用别的功能。
- 听不清、识别结果不成句或意图不明确时，只说一句「没听清，你再说一遍」，绝不允许猜测意图，更不允许因此调用任何工具。
- 需要工具时先用一句话告诉用户你正在做什么，再调用工具，拿到结果后再口播结论。
- 只陈述工具返回的真实数据，工具报错就如实说明失败原因，绝不编造数据。
- 只有用户明确说打开摄像头、开一下视频时才调用 open_camera，说关掉摄像头时调用 close_camera；
  其他任何情况都不要主动打开摄像头。
- 你看不见摄像头画面，只有 identify_object_with_camera 返回的描述才算你看到的。用户问画面里有什么、
  这是什么、我手里拿的是啥、我在干什么时才调用它；摄像头没开就先打开再识别。
  调用时把用户的原话放进 question 参数，不要自己改写成「这是什么物品」。
  没有工具结果时绝对禁止描述画面内容。
- 用户问「我在干什么」「你看我在做什么」时，照着看到的画面说人物的动作、状态和环境，
  再推测他可能在做什么，然后就停住。绝对不要顺势识别他身上的物品品牌、不要查价格、
  不要给购买链接——除非他自己主动问哪里买、多少钱、值不值得买。
- search_where_to_buy 只在用户明确问哪儿能买、多少钱、什么价位时才调用。
  任何情况下都不要主动推荐商品或购买链接，也不要问用户「要不要帮你查购买信息」。
- 用户说从网上找、搜一张壁纸时调 search_wallpaper_image；只有说生成、画一张时才调 generate_wallpaper_image。
  拿到图片后用户要换桌面的，再调 set_desktop_wallpaper。
- 用户说声音大一点、小一点这类相对调节时，先调 get_system_volume 拿到当前值，再换算成目标百分比调 set_system_volume。
- 用户说屏幕亮一点、暗一点、太刺眼这类相对调节时，先调 get_screen_brightness 拿到当前值，再换算成目标百分比调 set_screen_brightness。
- 这台电脑的电源模式只有三档，跟 Windows 设置里的下拉框完全一致：
  recommended 推荐、better_performance 更好的性能、best_performance 最佳性能。
  用户问有哪些模式时只能说这三个，绝对不要提「最佳能效」「省电模式」「平衡模式」这些本机没有的档位。
  口播时用中文档位名，不要念英文参数名。
- 用户说电脑卡、要跑大任务、要性能时切 best_performance；说稍微快一点时切 better_performance；
  说省电、续航不够、恢复默认时切 recommended——推荐档就是这三档里最省电的那一档，
  如实说「已经切到推荐，这是这台机器最省电的档位」，不要谎称切到了省电模式。
- 性能和续航是相反方向。用户如果说「开省电模式提升性能」这类互相矛盾的话，
  先用一句话点明这两个方向相反，问清他要续航还是要性能，不要自己猜着调。
- 电源模式在任务栏上看不出来，所以用户说给我看看、证明一下、打开设置看看时，
  调 set_power_mode 时传 show_proof=true，系统会自动弹出「电源和电池」页面。
  工具返回里有 registry_mode 字段时，那是从 Windows 注册表独立读出的模式，可以据此说已核对一致。
- 设置睡眠或休眠时间时，先确认用户说的是关屏、睡眠还是休眠这三者中的哪一个，不确定就问一句，不要自己替用户选。
  用户说别自动睡眠、一直亮着，就把对应项设为 0（永不）。
- 关屏、睡眠、休眠是三项互相独立的设置，改一个不会带动另一个。默认同时改插电和电池两种情况；
  只有用户明确说了「插电时」「用电池时」才只改一个，不要反过来追问他要哪种。
- set_power_timeout 返回里带 verified_ac_minutes / verified_dc_minutes 时，那是改完从系统
  重新读出来的实测值，口播时报这个数字，这样用户能确认真的生效了。
- set_power_timeout 现在通过 PowrProf.dll 直接写秒值，休眠 15 分钟会精确写成 15 分钟。
  口播以 verified_ac_minutes / verified_dc_minutes 的回读值为准。
- 返回里带 other_setting 时，可以顺口说一句另一项当前是多少，但绝对不要未经同意就去改它。
- 用户说「你没改啊 / 我没看到 / 设置里还是旧的」时，先说明 Windows 设置页面开着的时候不会自动刷新，
  请他关掉重新打开「电源和电池」，同时报出回读到的实测值；不要重复执行一遍修改，
  也不要承认自己没改成功——回读值就是证据。
- 这台电脑是新式待机机型。set_power_timeout 设置休眠时会自动打开 Windows 的
  POWER_ATTRIBUTE_SHOW_AOAC 可见性标志，让休眠时间直接显示在
  「设置 > 系统 > 电源和电池 > 屏幕、睡眠和休眠超时」区域里。
- 工具返回 hibernate_row_visible=true 时，可以明确说休眠项已显示；
  用户要亲眼核对就传 show_proof=true，系统会重开该设置页以刷新内容。
- 工具返回里的 where_to_verify 字段写明了该项在哪个界面能看到，照它说，不要自己编位置。
- 要把某项设为「永不」（0 分钟）之前，先用一句话确认一遍，因为永不睡眠会一直耗电；
  用户确认后再执行。改成具体分钟数则直接执行，不用确认。
- 你只能把计算器、记事本这类程序打开，无法操作它们的界面。用户让你用计算器算数时，
  直接口算给出答案，并说明这是你自己算的、计算器已经打开可以自己用；
  绝不允许说「我用计算器算出来是…」这类让人以为你在操作程序的话。
- 用户说发到我邮箱时不要填写收件人，系统会使用本人默认邮箱；只有发给别人才需要地址。
- 代码会对发邮件、开摄像头、改时区/电源/超时/壁纸和生图执行二次确认。
  第一次调用只返回 confirmation_token，绝不会执行副作用。你必须把 action_summary 告诉用户并询问确认；
  只有用户在新的语音轮次明确说“确认/同意/继续/发送/打开/修改”等肯定词后，才用完全相同的参数
  加 confirmation_token 再调用一次。用户取消、含糊回答或修改参数时，停止操作并丢弃 token。"""


@dataclass
class PendingCall:
    call_id: str
    name: str
    item_id: str | None = None
    arguments: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)


class ToolCallCoordinator:
  """收集一轮 response 内的全部 function call，并发执行后交给后端回传。"""

  def __init__(self) -> None:
    self._pending: dict[str, PendingCall] = {}

  def register(self, call_id: str, name: str, item_id: str | None = None) -> None:
    self._pending[call_id] = PendingCall(call_id=call_id, name=name, item_id=item_id)
    emit(
      "tool_start",
      f"[调用工具] {name}",
      {"call_id": call_id, "name": name},
    )

  def set_arguments(self, call_id: str, arguments: str | None) -> None:
    call = self._pending.get(call_id)
    if call is not None:
      call.arguments = arguments
      summary = _argument_summary(arguments)
      emit(
        "tool_start",
        f"[参数] {summary or '无'}",
        {"call_id": call_id, "name": call.name, "argument_summary": summary},
      )

  @property
  def has_pending(self) -> bool:
    return bool(self._pending)

  async def drain(self) -> list[PendingCall]:
    calls = list(self._pending.values())
    self._pending.clear()

    results = await asyncio.gather(*(tools.dispatch(c.name, c.arguments) for c in calls))
    for call, result in zip(calls, results):
      call.result = result
      ok = bool(result.get("ok"))
      confirmation_required = bool(result.get("confirmation_required"))
      elapsed = time.monotonic() - call.started_at
      safe_error = _safe_error(result.get("error"))
      if confirmation_required:
        status = "等待用户确认"
      else:
        status = "完成" if ok else f"失败: {safe_error or '工具执行失败'}"
      emit(
        "tool_done",
        f"[工具 {call.name}] {status}",
        {
          "call_id": call.call_id,
          "name": call.name,
          "ok": ok,
          "confirmation_required": confirmation_required,
          "error": safe_error,
          "elapsed": elapsed,
        },
      )
      logger.info(
        "工具 %s 完成(%.2fs): ok=%s confirmation_required=%s result_fields=%s",
        call.name,
        elapsed,
        ok,
        confirmation_required,
        sorted(result),
      )
    return calls


def to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)
