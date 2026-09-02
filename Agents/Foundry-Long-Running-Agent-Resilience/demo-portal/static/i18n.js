/* English is the source text in HTML/JavaScript; Chinese uses exact-string lookup. */
(function () {
  const STORAGE_KEY = "lra-demo.lang";
  const dictionaries = {
    zh: {
      "LRA Interruption Lab": "LRA 打断实验室",
      "Microsoft Foundry Hosted Agents": "Microsoft Foundry 托管 Agent",
      "Sign in to run the repository-owned Hosted Agents.": "登录后运行本仓库自有的托管 Agent。",
      Username: "用户名",
      Password: "密码",
      "Sign in": "登录",
      "Refresh Agent status": "刷新 Agent 状态",
      "Toggle theme": "切换主题",
      "Sign out": "退出登录",
      Language: "语言",
      "Live resilience experiment": "实时韧性实验",
      "One translation job.\nFour kinds of interruption.": "同一份翻译任务，\n经受四种打断。",
      "One translation job.": "同一份翻译任务，",
      "Four kinds of interruption.": "经受四种打断。",
      "Each run calls Azure Translator, commits every finished section, and fails closed unless the original durable work reaches its declared terminal state.": "每次运行都真实调用 Azure Translator，每完成一段就写入持久化检查点；除非原任务达到声明的终态，否则验收一律失败。",
      "Durable checkpoints": "持久化检查点",
      "Live SSE evidence": "实时 SSE 证据",
      "Fail-closed acceptance": "失败即拒绝的验收",
      "Lease-based recovery of the same durable work item": "后续进程通过租约接管同一条持久化任务",
      "Live objects": "线上对象",
      "Repository-owned Agents": "本仓库自有 Agent",
      "Reading Foundry": "正在读取 Foundry",
      "Control, then interruption": "先跑基线，再制造打断",
      "Run the experiment": "运行实验",
      "Baseline first; every later run starts fresh durable work.": "先跑基线；之后每次测试都会创建一份新的持久化任务。",
      CONTROL: "基线",
      "No interruption": "不制造打断",
      "The repository's 12-section evidence Agent completes on one process.": "本仓库 12 段证据 Agent 在一个进程中完整结束。",
      Expected: "预期",
      "1 process · all checkpoints · completed": "1 个进程 · 检查点齐全 · completed",
      "Run baseline": "运行基线",
      "PROCESS LOSS": "进程崩溃",
      "Process A exits after checkpoint 4": "进程 A 在第 4 个检查点后退出",
      "Foundry assigns the same stored response to Process B, which must resume at checkpoint 5.": "Foundry 把同一个已保存响应交给进程 B，B 必须从第 5 个检查点继续。",
      Acceptance: "验收",
      "A → B · same response · no gaps": "A → B · 响应不变 · 检查点无缺口",
      "Run process-loss test": "运行进程崩溃测试",
      "CALLER LOSS": "客户端断线",
      "The observer disconnects": "观察端断开连接",
      "The Agent continues with no attached caller. The page reconnects to the original response after eight seconds.": "没有客户端连接时 Agent 仍继续工作；页面 8 秒后重新连接原响应。",
      "1 process · same response · progress continues": "1 个进程 · 响应不变 · 进度不中断",
      "Run disconnect test": "运行断线测试",
      "HUMAN WAIT": "等待人工审批",
      "Approval survives instance loss": "等待审批时实例崩溃，审批照样完成",
      "A 10-section sample waits for review. Its process exits; the decision must land on the replacement.": "10 段样稿停下来等待审批。原进程退出后，审批决定必须落到新进程上。",
      "Target language": "目标语言",
      "Simplified Chinese": "简体中文",
      "Traditional Chinese": "繁体中文",
      Japanese: "日语",
      Korean: "韩语",
      French: "法语",
      German: "德语",
      Spanish: "西班牙语",
      "Approve automatically": "由页面自动批准",
      "Sample unchanged · approval on B · 30 sections": "样稿不变 · 审批落在 B · 完成 30 段",
      "Run approval test": "运行审批恢复测试",
      "CHANGE OF INTENT": "中途改主意",
      "Recover, then change the target": "恢复后再改目标语言",
      "Process B resumes language A, then accepts language B on the same conversation. B starts at section 1.": "进程 B 先续跑语言 A，再在同一会话中接收语言 B；新语言从第 1 段开始。",
      "Language A": "语言 A",
      "Language B": "语言 B",
      "A recovered · B starts at 1 · both completed": "A 已恢复 · B 从第 1 段开始 · 两者都完成",
      "Run steering test": "运行中途改主意测试",
      "Live run": "实时运行",
      Scenario: "场景",
      starting: "正在启动",
      Started: "已启动",
      "Checkpoint committed": "检查点已落盘",
      "Interruption observed": "已观察到打断",
      "Durable work recovered": "持久化任务已恢复",
      "Work continued": "任务继续推进",
      "Acceptance passed": "验收通过",
      "Starting the live run…": "正在启动实时运行…",
      "Human decision": "人工决定",
      "The sample survived. Continue on Process B?": "样稿仍在。是否让进程 B 继续？",
      "Nothing runs while you decide.": "你做决定期间没有任务在后台偷跑。",
      Approve: "批准",
      Reject: "拒绝",
      "Observed timeline": "观察到的时间线",
      "Evidence boundary": "证据边界",
      "A live screen is not the proof by itself.": "一块实时屏幕本身不等于证据。",
      "The page shows one run as it happens. The committed JSON reports and event logs remain the reproducible evidence. These fault-enabled Agents are for non-production testing; at-least-once recovery still requires idempotent external effects.": "页面只把单次运行具体展示出来。可复验依据仍是仓库中的 JSON 报告和事件日志。这些开启故障注入的 Agent 只用于非生产测试；at-least-once 恢复仍要求外部操作具备幂等性。",
      "Run damaged-evidence checks": "运行损坏证据检查",
      "Waiting for the first committed section…": "等待第一段落盘…",
      "Choose two different languages so the change of mind is visible": "请选择两种不同语言，这样“改主意”才看得出来",
      "Run the approval scenario first": "请先运行审批场景",
      "Foundry returned {n} repository-owned Agents.": "Foundry 返回了 {n} 个本仓库自有 Agent。",
      "Foundry endpoint not configured": "尚未配置 Foundry 项目端点",
      "Set FOUNDRY_PROJECT_ENDPOINT to read the deployed Agents.": "设置 FOUNDRY_PROJECT_ENDPOINT 后即可读取已部署的 Agent。",
      "Agent status failed": "读取 Agent 状态失败",
      "Stream ended before a result arrived": "数据流结束时还没有收到结果",
      "Authentication required": "需要登录",
      "Live Agent": "线上 Agent",
      "checkpoint recovery": "检查点恢复",
      steering: "中途改主意",
      "approval gate": "人工审批",
      "Safe baseline": "安全基线",
      "Hard process loss": "进程崩溃",
      "Observer disconnect": "客户端断线",
      "Review gate + instance loss": "人工审批 + 实例崩溃",
      "Recovery + change of target": "故障恢复 + 中途改目标",
      "stored response created": "已创建持久化响应",
      "section {done}/{total} committed": "第 {done}/{total} 段已落盘",
      "Process A became unreachable": "进程 A 已不可达",
      "waiting for replacement compute": "正在等待新进程",
      "Process B entered as recovered": "进程 B 已以 recovered 模式进入",
      "caller disconnected for {s}s": "客户端断开 {s} 秒",
      "caller reattached to the original response": "客户端已重新连接原响应",
      "review sample committed": "待审批样稿已落盘",
      "instance lost while approval was pending": "等待审批时原实例已崩溃",
      "replacement instance is serving": "新实例已开始服务",
      "waiting for your decision": "正在等你做决定",
      "direction changed from {from} to {to}": "目标从 {from} 改为 {to}",
      "PASS in {s}s": "PASS，用时 {s} 秒",
      "FAIL · {detail}": "FAIL · {detail}",
      "Checks behaved correctly: {passed}/{total}.": "损坏证据检查行为正确：{passed}/{total}。",
      "Validator failed": "验证器失败",
      "Process {n}": "进程 {n}",
      "Original target": "原目标语言",
      "New target": "新目标语言",
      "Sample for review": "待审批样稿",
      "Remaining after approval": "审批后的剩余段落",
      "No committed sections yet.": "还没有已落盘的段落。",
      "process {id}": "进程 {id}",
      fresh: "首次运行",
      recovered: "恢复后",
      steered: "改主意后",
      sample: "样稿",
      remaining: "剩余",
      completed: "已完成",
      "awaiting approval": "等待审批",
      "run failed": "运行失败",
      "all sections completed": "全部段落已完成",
      "sample rejected; remaining work did not run": "样稿被拒绝；剩余任务未运行"
    }
  };

  const language = window.localStorage.getItem(STORAGE_KEY) === "zh" ? "zh" : "en";

  function t(source, values = {}) {
    let result = language === "zh" ? dictionaries.zh[source] || source : source;
    for (const [key, value] of Object.entries(values)) result = result.replaceAll(`{${key}}`, String(value));
    return result;
  }

  function translateDom(root) {
    if (language !== "zh") return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const trimmed = node.nodeValue.trim();
      if (!trimmed) continue;
      const translated = dictionaries.zh[trimmed];
      if (translated) node.nodeValue = node.nodeValue.replace(trimmed, translated);
    }
    document.querySelectorAll("[title], [aria-label]").forEach((node) => {
      for (const attribute of ["title", "aria-label"]) {
        const value = node.getAttribute(attribute);
        if (value && dictionaries.zh[value]) node.setAttribute(attribute, dictionaries.zh[value]);
      }
    });
  }

  function setLanguage(next) {
    window.localStorage.setItem(STORAGE_KEY, next === "zh" ? "zh" : "en");
    window.location.reload();
  }

  window.t = t;
  window.i18n = { language, setLanguage };
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.addEventListener("DOMContentLoaded", () => {
    translateDom(document.body);
    document.querySelectorAll(".lang-toggle button").forEach((button) => {
      button.classList.toggle("active", button.dataset.lang === language);
      button.addEventListener("click", () => setLanguage(button.dataset.lang));
    });
  });
})();
