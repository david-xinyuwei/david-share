/* Thermal 3D Modeling Studio — front-end */
(() => {
  'use strict';

  const I18N = {
    zh: {
      title: '热管理 3D 建模工坊', login_sub: '登录后体验 GPT-6 把一句话变成可交互的 3D 模型。', username: '用户名', password: '密码', signin: '登录',
      eyebrow: 'GPT-6 Astra · 生成式 3D 建模', hero: '用一句话，把热管理零件变成可交互的 3D 模型',
      hero_sub: '面向热管理研发场景：电池水冷板、微通道换热器、电子膨胀阀、四通阀、AIDC 液冷冷板、热管理集成模块。GPT-6 直接生成可旋转、可剖切、可爆炸的 three.js 模型，并给出质量、换热面积与材料成本估算；支持上传 2D 图纸/照片还原 3D，支持对话式迭代。',
      stat_model: '模型部署（Azure AI Foundry）', stat_scen: '预置场景', stat_lat: '上次生成耗时', stat_cnt: '本次会话已生成',
      scenarios: '场景卡片', scenarios_hint: '点选 → 载入示例，再发送可实时生成', conversation: '对话', new_chat: '新对话',
      empty_msgs: '选择左上方的场景，或直接描述你要建模的零件。', prompt_ph: '例如：建一个 320×180×12 mm 的铝合金电池水冷板，6 道 S 形流道……',
      upload: '图纸/照片', sample_drawing: '用示例图纸', generate: '实时调用 GPT-6', generating: '生成中…',
      tab_view: '3D 视图', tab_stream: '生成过程', tab_metrics: '工程量', btn_png: '截图 PNG', btn_glb: '导出 GLB', btn_html: '下载 HTML', btn_open: '新窗口', btn_full: '全屏', btn_exit_full: '退出全屏',
      empty_title: '这里会出现你的 3D 模型', empty_sub: '选择左侧场景卡片，或输入零件描述后点击“实时调用 GPT-6”。',
      progress_title: 'GPT-6 正在建模…', m_label: '指标', m_value: '数值', m_unit: '单位', m_note: '说明',
      badge_cache: '预生成示例', badge_live: '实时生成', chars: '字符', example_note: '（这是历史生成的示例，本次未调用模型；点击“实时调用 GPT-6”生成新结果。）',
      need_image: '该场景需要上传一张图纸或照片（或点击"用示例图纸"）。', err_prefix: '生成失败：',
      run_info: (r) => `模型 ${r.model}${r.reasoning_effort ? ` · 推理 ${r.reasoning_effort}` : ''} · 耗时 ${r.latency_s}s${r.ttft_s ? ` · 首字 ${r.ttft_s}s` : ''}${usageText(r.usage, 'zh')} · ${r.created_at}`,
      usage_in: '输入', usage_cached: '命中缓存', usage_out: '输出', usage_reasoning: '推理', usage_total: '累计', usage_turns: '轮',
      versions: '版本', version_example: '示例', version_hint: '继续输入修改要求，GPT-6 会在当前版本上改；点旧版本可回看。', version_branch: '正在查看旧版本：下一条修改将从这一版分支，之后的版本会被替换。',
      m_delta: '较上一版', m_delta_new: '新增',
      tab_render: '渲染图', btn_render: '生成渲染图', btn_render_busy: '渲染中…',
      render_title: '轨 C · WebGL 截图 → gpt-image-2.5 真实感渲染',
      render_intro: '把当前 3D 视图的 WebGL 截图交给 gpt-image-2.5，重绘成真实感效果图，用于方案汇报和概念评审。图像模型会重新构图，比例和细节可能与 STEP 不同，尺寸以 STEP 为准。可多轮微调：每次在上一张渲染图上继续改。',
      render_style: '风格', rs_studio: '工作室产品图', rs_exhibition: '展会灯光', rs_exploded: '爆炸图海报', rs_section: '剖切示意', rs_installed: '装车 / 装机场景',
      render_size: '尺寸', render_quality: '质量', rq_low: '低 · 快', rq_medium: '中', rq_high: '高', rq_xhigh: '极高 · 慢', rq_max: '最高 · 最慢', render_base: '基于', rb_snapshot: '当前 3D 视图截图', rb_previous: '上一张渲染图（微调）',
      render_instruction_ph: '补充要求（可选）：例如 拉丝铝表面、白色背景、俯视 30°、加一根接管的冷却液流动示意…', render_go: '开始渲染',
      render_empty: '先在 3D 视图得到一个模型（渲染就绪），再点「开始渲染」或右上角「生成渲染图」。',
      render_dl: '下载 PNG', render_show_prompt: '查看提示词', render_hide_prompt: '收起提示词',
      btn_proposal: '生成方案书', btn_proposal_busy: '方案书生成中…', proposal_untitled: '自定义需求',
      proposal_started: '正在整理方案书：截取 3D 视图、汇总工程量与 STEP，GPT-6 撰写方案要点 / 设计说明 / 风险 / 下一步（约 30–90 s）…',
      proposal_done: (name, secs, byModel, tokens) => `方案书已下载：${name} · ${secs}s${byModel ? ` · 正文由 GPT-6 撰写${tokens ? `（${fmtInt(+tokens)} tokens）` : ''}` : ' · 未含 GPT-6 正文（模型调用失败，已用原始数据生成）'}`,
      proposal_err: '方案书生成失败：', proposal_step_file: 'STEP 文件',
      render_note: '渲染图由图像模型基于截图重绘，材质与光照为示意，不代表真实表面处理；几何以 3D 模型 / STEP 为准。',
      render_progress: 'gpt-image-2.5 正在渲染…', render_hb: (s) => `图像模型仍在生成…（已等待 ${Math.round(s)} s，连接正常）`, render_snap: '正在截取 3D 视图…',
      render_done: (r) => `渲染完成：${r.model} · ${r.latency_s}s · ${r.size} · ${r.quality}${r.usage ? ` · ${fmtInt(r.usage.total_tokens)} tokens` : ''}`,
      render_caption: (r, i) => `第 ${i} 张 · ${r.source === 'pre_generated' ? '预生成 · ' : ''}${r.style} · 基于${r.base === 'previous' ? '上一张渲染图' : '3D 截图'}${r.instruction ? ` · “${r.instruction}”` : ''} · ${r.source === 'pre_generated' ? '历史生成耗时 ' : ''}${r.latency_s}s`,
      render_err: '渲染失败：', render_no_result: '请先得到一个已渲染就绪的 3D 模型。', render_no_previous: '还没有上一张渲染图，已改为基于 3D 截图。',
      render_badge_ok: '渲染图已生成', render_badge_fail: '渲染失败', render_msg: (r) => `【轨 C · 渲染图】${r.style} · ${r.size}${r.instruction ? ` · ${r.instruction}` : ''}`,
      render_badge_cached: '预生成渲染图（本次未调用 gpt-image）', render_cache_error: '预生成渲染图载入失败：',
      render_cached_msg: (r) => `【轨 C · 预生成渲染图】${r.model} · ${r.style} · ${r.size} · 质量 ${r.quality}，${(r.created_at || '').slice(0, 10)} 基于本场景 3D 视图截图生成；本次未调用 gpt-image，几何以 3D / STEP 为准。${r.engineering ? '另有按 STEP 几何直接渲染的工程渲染图（与 STEP 一致），可在「渲染图」页切换查看。' : ''}`,
      concept_title: '🎨 概念图先行 · 先画后建', concept_hint: '没有图纸时：先用自然语言画概念图，满意后交给 GPT-6 建 3D',
      concept_ph: '例如：一个面向 800 V 平台的热管理集成模块概念：压铸铝阀岛顶部布置九通电子水阀，两台电子水泵并排，集成板换 chiller，接口朝前；参考近两年量产车型的集成模块外形',
      concept_provider: '模型', concept_grounding: '先搜再画', cg_on: '开 · Bing 联网检索后再画', cg_off: '关', concept_go: '画概念图',
      concept_edit_ph: '微调这张图（gpt-image 编辑）：例如 壳体改成深灰阳极氧化，接口改朝左…', concept_edit_go: '微调', concept_use: '用这张图建 3D →',
      concept_note: '概念图只表达外形与布局意图；点「用这张图建 3D」后请在需求里补充关键尺寸（外形包络、接口规格），GPT-6 会按图 + 尺寸建参数化 3D。',
      concept_progress: '正在画概念图…', concept_hb: (s) => `图像模型仍在生成…（已等待 ${Math.round(s)} s）`, concept_started: (d) => `${d.model}${d.web_grounding ? ' · Bing 联网检索' : ''}${d.provider === 'gpt-image' ? ' · ' : ''}`,
      concept_done: (r) => `完成：${r.model} · ${r.latency_s}s${r.web_grounding ? ' · 已联网检索' : ''}${r.usage && (r.usage.total_tokens || r.usage.num_output_tokens) ? ` · ${fmtInt(r.usage.total_tokens || r.usage.num_output_tokens)} tokens` : ''}`,
      concept_caption: (r, i) => `概念图 ${i} · ${r.model}${r.web_grounding ? ' · 先搜再画' : ''}${r.edit ? ` · 微调：“${r.instruction}”` : ''} · ${r.latency_s}s`,
      concept_err: '概念图生成失败：', concept_use_prompt: '按这张概念图建可交互 3D 模型：识别其中的部件与布局，按概念比例建模；关键尺寸：', concept_use_msg: '已把概念图作为图纸附到需求中；请补充外形尺寸后点「实时调用 GPT-6」。',
      provider_gpt: 'gpt-image-2.5（Azure OpenAI）', provider_mai: 'MAI-Image-2.6（可 Bing 联网）',
      signed_out: '已退出', connecting: '连接中', live: '在线',
      mode_example: '浏览预生成示例', mode_live: '仅实时生成',
      hint_example: '点卡片只读取已保存的 GPT-6 示例，不发起模型调用。点击“实时调用 GPT-6”才生成新结果。',
      hint_live: '点卡片只填写需求，不读取任何预生成示例。点击“实时调用 GPT-6”后，才向 Azure 发起请求。',
      cards_live: '点选仅填入需求，不加载缓存',
      render_explainer: '两种模式都由浏览器实时渲染 3D，不是视频；实时生成会等待完整代码返回后再显示模型。',
      source_empty: '尚未加载模型', source_cache: '当前模型：预生成示例（本次未调用 GPT-6）',
      source_live: '当前模型：本次实时调用 GPT-6 的结果', cache_loading: '正在读取已保存的示例；没有调用 GPT-6。',
      cache_error: '示例读取失败：', cache_absent: '该场景暂无已保存示例，可点击“实时调用 GPT-6”生成。',
      render_idle: '空闲 · 尚无 3D 模型（未发起请求）', render_loading: '代码已返回 · 浏览器加载中', render_ready: 'WebGL 已绘制 · 可交互',
      render_failed: '浏览器渲染失败', render_error: '代码已返回，但 3D 渲染未成功：',
      render_degraded: (missing) => `已检测到 WebGL 绘制；${missing ? `脚本未提供 ${missing}` : '通过画布确认显示，未通过场景对象检查'}。截图仍可用；GLB 导出、实时工程量和部件索引按脚本实际提供的接口启用。`,
      phase_connecting: '正在向 Azure 发起实时请求；当前画面若有模型，仍是上一版。',
      phase_streaming: 'GPT-6 正在输出模型代码；完整代码返回后才替换画面。',
      phase_complete: '本次实时调用完成。代码生成与浏览器渲染状态分别显示。',
      no_fallback: '本次请求失败，未用缓存冒充新结果；已保留输入，可重试。',
      source_time: '生成时间', historical_latency: '历史生成耗时', current_latency: '本次生成耗时', trace_id: '请求 ID',
      estimate_note: '以下为模型生成的概念设计估算，未经 CAD/CAE 校核；GLB 是可视化网格，不是 STEP 工程实体（工程实体请用「生成 STEP」走 CadQuery 轨）。',
      tab_cad: 'CAD 实体', btn_step: '生成 STEP', btn_step_busy: 'STEP 生成中…',
      cad_title: '轨 B · CadQuery → STEP 工程实体',
      cad_intro: 'GPT-6 为当前零件编写 CadQuery（OCCT B-rep）脚本，服务器在隔离子进程中执行、导出 STEP/STL，并用 B-rep 精确计算体积与质量。STEP 可直接在 SolidWorks / NX / Creo 中打开。',
      cad_empty: '先在 3D 视图得到一个模型，再点击右上角「生成 STEP」。',
      cad_dl_step: '下载 STEP', cad_dl_stl: '下载 STL', cad_dl_py: '下载 CadQuery 脚本', cad_show_code: '查看脚本', cad_hide_code: '收起脚本',
      cad_viewer_caption: 'STL 预览（由 STEP 实体网格化）· 拖动旋转',
      cad_metrics_note: '体积 / 质量 / 包络 / 表面积由 OCCT 从 B-rep 实体直接计算，可与轨 A 的估算值对照。',
      cad_progress_title: 'GPT-6 正在编写 CadQuery 脚本并由 OCCT 内核执行…',
      cad_ph_model: (n, max) => `第 ${n}/${max} 次 · GPT-6 编写 CadQuery 脚本`, cad_ph_occt: (n, max, lines) => `第 ${n}/${max} 次 · 服务器执行脚本（${lines} 行）→ 导出 STEP/STL`,
      cad_ph_failed: (n) => `第 ${n} 次失败，已把错误回传 GPT-6 修正：`, cad_started: '已连接服务器，任务 ID ',
      cad_done: (r) => `STEP 已生成：${r.attempts} 次尝试 · ${r.latency_s}s · OCCT ${r.raw.elapsed_s}s · STEP ${(r.raw.step_bytes / 1024).toFixed(0)} KB`,
      cad_badge_ok: 'STEP 实体已生成', cad_badge_fail: 'STEP 生成失败', cad_badge_stale: 'STEP 对应上一版模型', cad_err: 'STEP 生成失败：', cad_unavailable: '服务器未安装 CadQuery，暂不可生成 STEP。',
      cad_run_info: (r) => `${r.model} · ${r.attempts} 次尝试 · 总耗时 ${r.latency_s}s · OCCT ${r.raw.elapsed_s}s · STEP ${(r.raw.step_bytes / 1024).toFixed(0)} KB · ${r.created_at}`,
      cad_msg: (r) => `【轨 B · STEP 实体】${r.summary}`, cad_no_result: '请先生成或载入一个 3D 模型。',
      cad_badge_cached: 'STEP 实体 · 预生成示例', cad_run_info_cached: (r) => `预生成 · CadQuery 参考脚本（本次未调用 GPT-6）· OCCT ${r.raw.elapsed_s}s · STEP ${(r.raw.step_bytes / 1024).toFixed(0)} KB · ${r.created_at}`,
      cad_cached_msg: (r) => `【轨 B · 预生成 STEP 实体】${r.summary}`, cad_cache_error: '预生成 STEP 实体载入失败：',
      cad_preview_fail: 'STL 预览加载失败：',
      cad_hb_model: (s) => `GPT-6 仍在编写脚本…（服务器已等待 ${Math.round(s)} s，连接正常）`, cad_hb_occt: (s) => `OCCT 仍在执行脚本…（已运行 ${Math.round(s)} s）`,
      image_sample: '已选择内置演示图纸（不是客户上传文件）。', image_upload: '已选择本次上传的图片。（演示环境为 HTTP 明文传输，请勿上传涉密图纸。）', image_concept: '已附上刚生成的概念图（由图像模型绘制，非客户图纸）。',
      image_error: '图纸加载失败：', image_invalid: '请使用不超过 8 MB 的 PNG、JPEG 或 WebP 图片。',
      enter_prompt: '请先输入建模需求或选择图纸。', export_empty: '未取得导出内容。',
      cancel: '取消', cancelled: '已取消本次实时请求；未完成的结果不会保留，画面中不会出现半成品。',
      stage_wait: '等待 GPT-6 首字…', stage_summary: '正在写摘要', stage_html: '正在写 three.js 场景代码', stage_metrics: '正在计算工程量', stage_suggestions: '正在给出后续建议', stage_finish: '收尾中',
      lines: '行', early_render: '场景代码已完成，先行渲染；工程量与建议仍在生成中。',
      render_preview: '代码已返回 · 浏览器加载中（工程量生成中）', ref_image: '参考图', hide_ref: '隐藏参考图', show_ref: '显示参考图',
      eta_hint: (s) => `通常约 ${s}`, kbd_hint: 'Ctrl/⌘ + Enter 发送',
      metrics_live: '以下数值由场景脚本按参数实时计算（与 3D 画面中的覆盖层一致）；GPT-6 文字区块中的手算值已被替换。',
      metrics_text: '以下数值来自 GPT-6 输出的工程量区块。',
      hero_sub2: '第二批场景：AI 辅助仿真估算（冷板 3D 温度云图 + 出口温度 / 壁温 / 压降）与 APS 智能排程推理（GPT-6 编写排程算法、3D 甘特图对比老师傅经验排法）。',
      theme: '切换主题', logout: '退出', remove_image: '移除', upload_title: '上传图纸 / 照片',
      cache_fallback_en: '该场景暂无当前界面语言的已保存示例，显示的是另一语言的示例；点击“实时调用 GPT-6”可生成当前语言的结果。',
      effort_label: '推理强度', effort_low: '低', effort_medium: '中', effort_high: '高', effort_xhigh: '极高',
      effort_title: 'GPT-6 的 reasoning_effort，只列出模型部署接受的取值。低：最快，演示默认，整段约 2.5–3 分钟；中：约 6 分钟；高 / 极高：几何更严谨但可能 10 分钟以上，仅在离线预生成时使用。选择随每次实时调用与 STEP 生成一起发送；部署不接受的取值会换成最接近的可用值，结果来源栏会显示实际生效值。',
      effort_eta: { low: '约 2.5–3 分钟', medium: '约 6 分钟', high: '8–15 分钟', xhigh: '15 分钟以上' },
      effort_tag: (e) => `推理强度 ${e}`, effort_default: '（服务器默认）',
      sys_stages: '运行阶段', sys_parts: '部件索引 · 点击定位', sys_overview: '全局视角', sys_collapse: '收起', sys_expand: '展开',
      conn_title: '模型连接：登录后自动使用服务器固定连接', conn_heading: '模型连接',
      conn_intro: '填入你自己的 Azure OpenAI 资源后，实时生成与 STEP 将改用你的配额。保存会持久记住 Endpoint、部署名和 key，并将它们备份到本机 password.txt；服务器不保存、不记录连接信息。',
      conn_host_intro: '登录后自动使用服务器固定连接，无需输入 API key。Endpoint 和部署名直接显示在这里；API key 或 Entra token 只保存在服务器，浏览器不会接收。',
      conn_managed_key: (auth) => auth === 'api_key' ? '已在服务器配置（无需输入）' : 'Microsoft Entra 托管身份（无需 API key）',
      conn_auto_tag: '免填直连',
      conn_backup_note: 'password.txt 含明文 key，请保存在私有、非共享且不自动同步的本机目录，不要上传或提交到代码仓库。刷新、退出登录不会清除浏览器连接；更换网址或浏览器后，可导入此文件恢复。',
      conn_endpoint: 'Endpoint', conn_deployment: '部署名（Deployment）', conn_key: 'API key', conn_auth: '认证',
      conn_http_warning: '⚠ 本演示环境为 HTTP 明文传输，请使用可随时轮换的 key，用完可在此清除。',
      conn_test: '测试连接', conn_clear: '清除 · 改用主机默认', conn_cancel: '关闭', conn_save: '保存并备份 password.txt', conn_import: '导入 password 文件',
      conn_testing: '正在用当前连接调用一次模型…', conn_test_ok: (r) => `连接成功：${r.actual_model || r.deployment} @ ${r.endpoint_host} · ${r.latency_s}s`,
      conn_test_fail: (r) => `连接失败（${r.endpoint_host}）：${r.error}`, conn_saved: '已持久保存到本机浏览器。', conn_cleared: '已清除当前网址的浏览器连接，改用主机默认；本地 password 文件未删除。',
      conn_invalid: 'Endpoint 需为 Azure HTTPS 资源地址；key 需为 16–256 位合法字符；部署名可留空，或填写 1–64 位字母、数字、点、下划线、短横线。', conn_own_tag: '你的 key', conn_host_tag: '主机默认',
      conn_clear_confirm: '确定清除当前网址保存在浏览器中的 Endpoint、部署名和 key？本机 password 文件会保留。',
      conn_saving: '正在备份到本机 password.txt…',
      conn_backup_saved: 'password.txt 已写入你选择的本机位置。',
      conn_backup_download: '已发起 password.txt 下载，请确认下载完成并保管好文件。',
      conn_backup_cancelled: '文件备份已取消；请再次点击保存完成备份。',
      conn_backup_failed: '文件备份失败，请检查文件写入权限或浏览器下载设置后重试。',
      conn_save_failed: '浏览器持久保存失败，请检查站点存储权限或可用空间。',
      conn_read_failed: '本地连接读取失败；原数据未删除。请导入 password 文件或重新填写后保存。',
      conn_clear_failed: '浏览器连接清除失败，原配置未主动更改。',
      conn_import_invalid: '无法导入：请选择本应用保存的 password.txt / JSON 文件（不超过 16 KB），并检查连接字段。',
      conn_import_failed: '文件已读取，但浏览器持久保存失败；原配置未主动更改。',
      conn_imported: '已从 password 文件恢复到本机浏览器，后续实时调用使用此连接。',
      conn_required: '本演示的实时生成需要你自己的 Azure OpenAI key（预生成示例不受影响）。', conn_required_btn: '填写模型连接', conn_presenter_hint: '演示主持人：退出后改用管理员账号登录即可免填 key（会话保留 30 天）。',
      key_source: (k, h) => (k === 'visitor' ? `模型连接：你的 key（${h}）` : '模型连接：服务器免填直连'),
      conn_owner_tag: '管理员', conn_owner_note: '你以管理员身份登录：实时生成与 STEP 自动使用服务器 .env 中配置的主机连接，无需在浏览器里填写 key；下面的字段仅在你想临时改用另一个资源时填写。',
      hero_sub3: '第三批场景（系统级）：整车热管理系统回路与 AIDC CDU 液冷分配单元——GPT-6 生成带介质回路流动、工况切换、编号部件热点（对应产品类别）与分阶段讲解的系统动画，并实时计算热平衡。',
    },
    en: {
      title: 'Thermal 3D Modeling Studio', login_sub: 'Sign in to watch GPT-6 turn one sentence into an interactive 3D model.', username: 'Username', password: 'Password', signin: 'Sign in',
      eyebrow: 'GPT-6 Astra · Generative 3D modeling', hero: 'Turn a thermal-management part into an interactive 3D model with one sentence',
      hero_sub: 'Built for thermal-management R&D: battery cold plates, micro-channel heat exchangers, electronic expansion valves, 4-way valves, AIDC liquid-cooling plates and integrated thermal modules. GPT-6 writes the three.js model directly — rotate, cut away, explode — plus mass, heat-transfer area and material cost estimates. Upload a 2D drawing or photo to rebuild it in 3D, then iterate in conversation.',
      stat_model: 'Model deployment (Azure AI Foundry)', stat_scen: 'Preset scenarios', stat_lat: 'Last generation', stat_cnt: 'Generated this session',
      scenarios: 'Scenarios', scenarios_hint: 'Click → load example, send to generate live', conversation: 'Conversation', new_chat: 'New chat',
      empty_msgs: 'Pick a scenario above, or describe the part you want to model.', prompt_ph: 'e.g. Build a 320×180×12 mm aluminium battery cold plate with 6 serpentine channels…',
      upload: 'Drawing/photo', sample_drawing: 'Use sample drawing', generate: 'Call GPT-6 live', generating: 'Generating…',
      tab_view: '3D view', tab_stream: 'Generation', tab_metrics: 'Metrics', btn_png: 'PNG', btn_glb: 'Export GLB', btn_html: 'Download HTML', btn_open: 'New window', btn_full: 'Fullscreen', btn_exit_full: 'Exit fullscreen',
      empty_title: 'Your 3D model will appear here', empty_sub: 'Pick a scenario, or describe a part and click “Call GPT-6 live”.',
      progress_title: 'GPT-6 is modeling…', m_label: 'Metric', m_value: 'Value', m_unit: 'Unit', m_note: 'Note',
      badge_cache: 'Pre-generated example', badge_live: 'Live generation', chars: 'chars', example_note: '(Saved example; no model call this time. Click “Call GPT-6 live” to generate a new result.)',
      need_image: 'This scenario needs a drawing or photo (or click "Use sample drawing").', err_prefix: 'Generation failed: ',
      run_info: (r) => `model ${r.model}${r.reasoning_effort ? ` · reasoning ${r.reasoning_effort}` : ''} · ${r.latency_s}s${r.ttft_s ? ` · TTFT ${r.ttft_s}s` : ''}${usageText(r.usage, 'en')} · ${r.created_at}`,
      usage_in: 'in', usage_cached: 'cache hit', usage_out: 'out', usage_reasoning: 'reasoning', usage_total: 'total', usage_turns: 'turns',
      versions: 'Versions', version_example: 'example', version_hint: 'Keep typing changes — GPT-6 edits the current version; click an older one to review it.', version_branch: 'Viewing an older version: the next change branches from it and replaces the later versions.',
      m_delta: 'vs previous', m_delta_new: 'new',
      tab_render: 'Render', btn_render: 'Photoreal render', btn_render_busy: 'Rendering…',
      render_title: 'Track C · WebGL snapshot → gpt-image-2.5 photoreal render',
      render_intro: 'The current 3D view is captured and handed to gpt-image-2.5, which redraws it as a photoreal visualization for presentations and concept reviews. The image model re-frames the picture, so proportions and details can differ from the STEP; dimensions follow the STEP. Refine over several turns: each pass edits the previous render.',
      render_style: 'Style', rs_studio: 'Studio product shot', rs_exhibition: 'Trade-show lighting', rs_exploded: 'Exploded-view poster', rs_section: 'Section illustration', rs_installed: 'Installed in context',
      render_size: 'Size', render_quality: 'Quality', rq_low: 'Low · fast', rq_medium: 'Medium', rq_high: 'High', rq_xhigh: 'Extra high · slow', rq_max: 'Max · slowest', render_base: 'Based on', rb_snapshot: 'Current 3D view snapshot', rb_previous: 'Previous render (refine)',
      render_instruction_ph: 'Extra instruction (optional): e.g. brushed aluminium, white background, 30° top view, show coolant flow through one port…', render_go: 'Render',
      render_empty: 'Get a model in the 3D view (WebGL ready) first, then click “Render” or “Photoreal render” at the top right.',
      render_dl: 'Download PNG', render_show_prompt: 'Show prompt', render_hide_prompt: 'Hide prompt',
      btn_proposal: 'Proposal (.docx)', btn_proposal_busy: 'Building proposal…', proposal_untitled: 'Custom requirement',
      proposal_started: 'Building the proposal: capturing the 3D view, collecting metrics and STEP data; GPT-6 is writing the summary / rationale / risks / next steps (30–90 s)…',
      proposal_done: (name, secs, byModel, tokens) => `Proposal downloaded: ${name} · ${secs}s${byModel ? ` · narrative written by GPT-6${tokens ? ` (${fmtInt(+tokens)} tokens)` : ''}` : ' · without GPT-6 narrative (model call failed; built from the raw data)'}`,
      proposal_err: 'Proposal failed: ', proposal_step_file: 'STEP file',
      render_note: 'The render is redrawn by an image model from the snapshot: materials and lighting are illustrative, not a surface-finish spec; geometry is defined by the 3D model / STEP.',
      render_progress: 'gpt-image-2.5 is rendering…', render_hb: (s) => `Image model still generating… (${Math.round(s)} s, connection alive)`, render_snap: 'Capturing the 3D view…',
      render_done: (r) => `Render ready: ${r.model} · ${r.latency_s}s · ${r.size} · ${r.quality}${r.usage ? ` · ${fmtInt(r.usage.total_tokens)} tokens` : ''}`,
      render_caption: (r, i) => `#${i} · ${r.source === 'pre_generated' ? 'pre-generated · ' : ''}${r.style} · from ${r.base === 'previous' ? 'previous render' : '3D snapshot'}${r.instruction ? ` · “${r.instruction}”` : ''} · ${r.source === 'pre_generated' ? 'took ' : ''}${r.latency_s}s`,
      render_err: 'Render failed: ', render_no_result: 'Get a WebGL-ready 3D model first.', render_no_previous: 'No previous render yet — using the 3D snapshot instead.',
      render_badge_ok: 'Render ready', render_badge_fail: 'Render failed', render_msg: (r) => `[Track C · render] ${r.style} · ${r.size}${r.instruction ? ` · ${r.instruction}` : ''}`,
      render_badge_cached: 'Pre-generated render (no gpt-image call this time)', render_cache_error: 'Pre-generated render failed to load: ',
      render_cached_msg: (r) => `[Track C · pre-generated render] ${r.model} · ${r.style} · ${r.size} · quality ${r.quality}, made ${(r.created_at || '').slice(0, 10)} from this scenario's 3D view; no gpt-image call this time, geometry follows the 3D model / STEP.${r.engineering ? ' An engineering render made directly from the STEP geometry (matches the STEP) is available through the switch on the Render tab.' : ''}`,
      concept_title: '🎨 Concept first · draw, then build', concept_hint: 'No drawing yet? Describe the idea, get a concept image, then hand it to GPT-6 for the 3D model',
      concept_ph: 'e.g. Concept for an 800 V integrated thermal module: die-cast aluminium valve island with a nine-way coolant valve on top, two electronic water pumps side by side, integrated plate-HX chiller, ports facing forward; in the spirit of recent production modules',
      concept_provider: 'Model', concept_grounding: 'Search first', cg_on: 'On · Bing web grounding before drawing', cg_off: 'Off', concept_go: 'Draw concept',
      concept_edit_ph: 'Refine this image (gpt-image edit): e.g. dark-grey anodised housing, ports facing left…', concept_edit_go: 'Refine', concept_use: 'Build 3D from this image →',
      concept_note: 'A concept image conveys form and layout only; after “Build 3D from this image”, add the key dimensions (envelope, port specs) to the request — GPT-6 builds a parametric 3D model from image + dimensions.',
      concept_progress: 'Drawing the concept…', concept_hb: (s) => `Image model still generating… (${Math.round(s)} s)`, concept_started: (d) => `${d.model}${d.web_grounding ? ' · Bing web grounding' : ''}`,
      concept_done: (r) => `Done: ${r.model} · ${r.latency_s}s${r.web_grounding ? ' · web-grounded' : ''}${r.usage && (r.usage.total_tokens || r.usage.num_output_tokens) ? ` · ${fmtInt(r.usage.total_tokens || r.usage.num_output_tokens)} tokens` : ''}`,
      concept_caption: (r, i) => `Concept ${i} · ${r.model}${r.web_grounding ? ' · search-first' : ''}${r.edit ? ` · refine: “${r.instruction}”` : ''} · ${r.latency_s}s`,
      concept_err: 'Concept generation failed: ', concept_use_prompt: 'Build an interactive 3D model from this concept image: identify the parts and layout, model them in the concept’s proportions; key dimensions: ', concept_use_msg: 'The concept image is attached as the drawing; add the envelope dimensions, then click “Call GPT-6 live”.',
      provider_gpt: 'gpt-image-2.5 (Azure OpenAI)', provider_mai: 'MAI-Image-2.6 (Bing web grounding)',
      signed_out: 'Signed out', connecting: 'Connecting', live: 'Live',
      mode_example: 'Browse saved examples', mode_live: 'Live generation only',
      hint_example: 'Selecting a card only loads a saved GPT-6 example. No model call is made until you click “Call GPT-6 live”.',
      hint_live: 'Selecting a card only fills the prompt; no saved example is loaded. Click “Call GPT-6 live” to send an Azure request.',
      cards_live: 'Select to fill prompt; no cache loaded',
      render_explainer: 'Both modes render interactive 3D in your browser, not video. Live generation displays the new scene after complete code arrives.',
      source_empty: 'No model loaded', source_cache: 'Current model: saved example (no GPT-6 call this time)',
      source_live: 'Current model: this live GPT-6 response', cache_loading: 'Loading a saved example; not calling GPT-6.',
      cache_error: 'Example could not be loaded: ', cache_absent: 'No saved example yet. Click “Call GPT-6 live” to generate one.',
      render_idle: 'Idle · no 3D model yet (no request sent)', render_loading: 'Code received · loading in browser', render_ready: 'WebGL drawn · interactive',
      render_failed: 'Browser rendering failed', render_error: 'Code arrived, but the 3D scene did not render: ',
      render_degraded: (missing) => `WebGL drawing detected; ${missing ? `the script did not expose ${missing}` : 'readiness was confirmed through the canvas, not scene-object checks'}. Snapshots remain available. GLB export, live metrics and the component index depend on the interfaces actually provided by the script.`,
      phase_connecting: 'Starting a live Azure request. Any model still visible is the previous version.',
      phase_streaming: 'GPT-6 is writing scene code. The view changes only after the complete code arrives.',
      phase_complete: 'Live call complete. Code generation and browser rendering have separate statuses.',
      no_fallback: 'Request failed. No cached result substituted; your input is preserved for retry.',
      source_time: 'Generated at', historical_latency: 'Original generation time', current_latency: 'This generation time', trace_id: 'Request ID',
      estimate_note: 'Concept estimates generated by the model, not validated by CAD/CAE. GLB is a visualization mesh, not a STEP engineering solid (use “Generate STEP” for the CadQuery solid).',
      tab_cad: 'CAD solid', btn_step: 'Generate STEP', btn_step_busy: 'Generating STEP…',
      cad_title: 'Track B · CadQuery → STEP engineering solid',
      cad_intro: 'GPT-6 writes a CadQuery (OCCT B-rep) script for the current part; the server runs it in an isolated subprocess, exports STEP/STL and computes exact volume and mass from the B-rep. The STEP opens directly in SolidWorks / NX / Creo.',
      cad_empty: 'Get a model in the 3D view first, then click “Generate STEP” at the top right.',
      cad_dl_step: 'Download STEP', cad_dl_stl: 'Download STL', cad_dl_py: 'Download CadQuery script', cad_show_code: 'Show script', cad_hide_code: 'Hide script',
      cad_viewer_caption: 'STL preview (tessellated from the STEP solid) · drag to rotate',
      cad_metrics_note: 'Volume / mass / bounding box / surface area are computed by OCCT from the B-rep solid — compare with the Track A estimates.',
      cad_progress_title: 'GPT-6 is writing the CadQuery script; the OCCT kernel executes it…',
      cad_ph_model: (n, max) => `Attempt ${n}/${max} · GPT-6 writing CadQuery script`, cad_ph_occt: (n, max, lines) => `Attempt ${n}/${max} · server running script (${lines} lines) → STEP/STL export`,
      cad_ph_failed: (n) => `Attempt ${n} failed; error fed back to GPT-6 for repair:`, cad_started: 'Connected, job ID ',
      cad_done: (r) => `STEP ready: ${r.attempts} attempt(s) · ${r.latency_s}s · OCCT ${r.raw.elapsed_s}s · STEP ${(r.raw.step_bytes / 1024).toFixed(0)} KB`,
      cad_badge_ok: 'STEP solid generated', cad_badge_fail: 'STEP generation failed', cad_badge_stale: 'STEP is from the previous model', cad_err: 'STEP generation failed: ', cad_unavailable: 'CadQuery is not installed on the server; STEP generation unavailable.',
      cad_run_info: (r) => `${r.model} · ${r.attempts} attempt(s) · total ${r.latency_s}s · OCCT ${r.raw.elapsed_s}s · STEP ${(r.raw.step_bytes / 1024).toFixed(0)} KB · ${r.created_at}`,
      cad_msg: (r) => `[Track B · STEP solid] ${r.summary}`, cad_no_result: 'Generate or load a 3D model first.',
      cad_badge_cached: 'STEP solid · pre-generated example', cad_run_info_cached: (r) => `Pre-generated · CadQuery reference script (no GPT-6 call this time) · OCCT ${r.raw.elapsed_s}s · STEP ${(r.raw.step_bytes / 1024).toFixed(0)} KB · ${r.created_at}`,
      cad_cached_msg: (r) => `[Track B · pre-generated STEP solid] ${r.summary}`, cad_cache_error: 'Pre-generated STEP solid failed to load: ',
      cad_preview_fail: 'STL preview failed to load: ',
      cad_hb_model: (s) => `GPT-6 is still writing the script… (server waiting ${Math.round(s)} s, connection alive)`, cad_hb_occt: (s) => `OCCT is still running the script… (${Math.round(s)} s elapsed)`,
      image_sample: 'Using the bundled demonstration drawing (not a customer upload).', image_upload: 'Using your uploaded image. (This demo runs over plain HTTP — do not upload confidential drawings.)', image_concept: 'Attached the concept image just generated (drawn by an image model, not a customer drawing).',
      image_error: 'Image could not be loaded: ', image_invalid: 'Use a PNG, JPEG or WebP image no larger than 8 MB.',
      enter_prompt: 'Enter a modeling request or select an image first.', export_empty: 'No export content received.',
      cancel: 'Cancel', cancelled: 'Live request cancelled; the unfinished result is discarded — no half-built model is shown.',
      stage_wait: 'Waiting for the first token…', stage_summary: 'Writing summary', stage_html: 'Writing three.js scene code', stage_metrics: 'Computing engineering metrics', stage_suggestions: 'Writing follow-up suggestions', stage_finish: 'Finishing',
      lines: 'lines', early_render: 'Scene code complete — rendering now; metrics and suggestions are still streaming.',
      render_preview: 'Code received · loading in browser (metrics streaming)', ref_image: 'Reference', hide_ref: 'Hide reference', show_ref: 'Show reference',
      eta_hint: (s) => `typically about ${s}`, kbd_hint: 'Ctrl/⌘ + Enter to send',
      metrics_live: 'Values below are computed live by the scene script from its parameters (same as the in-scene overlay); the hand-computed values from the GPT-6 text block were replaced.',
      metrics_text: 'Values below come from the metrics block written by GPT-6.',
      hero_sub2: 'Second batch: AI-assisted simulation estimate (3D temperature map, outlet / wall temperature, Δp) and APS scheduling reasoning (GPT-6 writes the scheduler; 3D Gantt vs. the veteran planner).',
      theme: 'Toggle theme', logout: 'Sign out', remove_image: 'Remove', upload_title: 'Upload a drawing / photo',
      cache_fallback_en: 'No English example saved for this scenario yet — showing the Chinese example. Click “Call GPT-6 live” for an English result.',
      effort_label: 'Reasoning', effort_low: 'Low', effort_medium: 'Medium', effort_high: 'High', effort_xhigh: 'Extra high',
      effort_title: 'GPT-6 reasoning_effort; only the values the model deployment accepts are listed. Low: fastest (demo default), about 2.5–3 min in total; Medium: ~6 min; High / Extra high: more rigorous geometry but possibly 10+ min — meant for offline pre-generation. The choice is sent with every live call and STEP job; a value the deployment refuses is replaced by the nearest one it accepts, and the source bar shows the value actually applied.',
      effort_eta: { low: '2.5–3 min', medium: '6 min', high: '8–15 min', xhigh: '15+ min' },
      effort_tag: (e) => `reasoning ${e}`, effort_default: '(server default)',
      sys_stages: 'Operating stages', sys_parts: 'Component index · click to locate', sys_overview: 'Overview', sys_collapse: 'Collapse', sys_expand: 'Expand',
      conn_title: 'Model connection: automatic server-managed connection after sign-in', conn_heading: 'Model connection',
      conn_intro: 'Enter your own Azure OpenAI resource to use your quota for live generation / STEP. Saving remembers the endpoint, deployment and key in this browser and backs them up to a local password.txt file. The server never stores or logs the connection.',
      conn_host_intro: 'After sign-in, the fixed server connection is used automatically—no API key entry required. The endpoint and deployment are shown here; the API key or Entra token stays on the server and is never sent to the browser.',
      conn_managed_key: (auth) => auth === 'api_key' ? 'Configured on server (no entry required)' : 'Microsoft Entra managed identity (no API key)',
      conn_auto_tag: 'automatic',
      conn_backup_note: 'password.txt contains a plaintext key. Keep it in a private, non-shared local folder without automatic sync; never upload or commit it. Reloading or signing out keeps the browser connection. Import the file to restore it on another site address or browser.',
      conn_endpoint: 'Endpoint', conn_deployment: 'Deployment name', conn_key: 'API key', conn_auth: 'Authentication',
      conn_http_warning: '⚠ This demo runs over plain HTTP — use a key you can rotate, and clear it here when done.',
      conn_test: 'Test connection', conn_clear: 'Clear · use host default', conn_cancel: 'Close', conn_save: 'Save + back up password.txt', conn_import: 'Import password file',
      conn_testing: 'Making one small model call with the active connection…', conn_test_ok: (r) => `Connected: ${r.actual_model || r.deployment} @ ${r.endpoint_host} · ${r.latency_s}s`,
      conn_test_fail: (r) => `Connection failed (${r.endpoint_host}): ${r.error}`, conn_saved: 'Persisted in this browser.', conn_cleared: 'Browser connection cleared for this site — using the host deployment. Local password files were not deleted.',
      conn_invalid: 'Use an Azure HTTPS resource endpoint, a valid 16–256 character key, and an optional deployment of 1–64 letters, digits, dots, underscores or hyphens.', conn_own_tag: 'your key', conn_host_tag: 'host default',
      conn_clear_confirm: 'Clear the endpoint, deployment and key saved in this browser for this site? Local password files will be kept.',
      conn_saving: 'Backing up to a local password.txt file…',
      conn_backup_saved: 'password.txt was written to your chosen local location.',
      conn_backup_download: 'password.txt download requested. Please confirm it completed and keep the file private.',
      conn_backup_cancelled: 'File backup cancelled; save again to complete the backup.',
      conn_backup_failed: 'File backup failed. Check file permissions or browser download settings and retry.',
      conn_save_failed: 'Browser persistence failed. Check site storage permissions or available space.',
      conn_read_failed: 'Cannot read the local connection; the original data was not deleted. Import a password file or enter and save the connection again.',
      conn_clear_failed: 'Cannot clear the browser connection; the original settings were not deliberately changed.',
      conn_import_invalid: 'Cannot import: choose a password.txt / JSON file saved by this app (up to 16 KB) and check its connection fields.',
      conn_import_failed: 'File read, but browser persistence failed; the original settings were not deliberately changed.',
      conn_imported: 'Connection restored from the password file and persisted in this browser for live calls.',
      conn_required: 'Live generation on this demo requires your own Azure OpenAI key (saved examples still work).', conn_required_btn: 'Set up model connection', conn_presenter_hint: 'Presenter? Sign out and sign in with the owner account — no key needed (session kept for 30 days).',
      key_source: (k, h) => (k === 'visitor' ? `Model connection: your key (${h})` : 'Model connection: automatic server connection'),
      conn_owner_tag: 'owner', conn_owner_note: 'You are signed in as the owner: live generation and STEP automatically use the host connection configured in the server’s .env — no key needed in the browser. Fill the fields below only to switch temporarily to another resource.',
      hero_sub3: 'Third batch (system level): whole-vehicle thermal-management loops and an AIDC coolant distribution unit — GPT-6 generates system animations with flowing fluid loops, switchable operating modes, numbered component hotspots (mapped to product categories) and staged narration, with the heat balance computed live.',
    },
  };

  Object.assign(I18N.zh, {
    workspace_heading: '研发工作台', workspace_boundary: '概念设计 · 几何查看 · 未经工程校核',
    view_original: '原场景', view_single: '透视', view_quad: '四视图', view_material: '材质预览', view_solid: '实体', view_wireframe: '线框',
    view_fit: '框选模型 / 选中部件', view_grid: '网格', view_section: '剖切', view_none: '关闭', view_section_position: '剖切位置',
    view_exposure: '曝光', view_parts: '部件', view_isolate: '独显选中', view_show_all: '恢复显隐', view_dimensions: '模型包络 · mm',
    view_outliner: '大纲', view_collection: '模型集合', view_statistics: '统计', stat_objects: '网格', stat_vertices: '顶点', stat_triangles: '三角面',
    split_side: '拖动调整左栏宽度（← → 微调，双击恢复）', split_composer: '拖动调整对话记录与输入框的高度（↑ ↓ 微调，双击恢复）',
    view_mesh_boundary: '网格视图 · 不替代 STEP / CAE 校核', view_loading: '正在加载工程视图…',
    view_unavailable: '当前场景未提供完整的工程视图接口', view_ready: '真实模型 · 工程视图',
    geom_concept: '概念网格', geom_brep: 'B-rep 实体', geom_concept_title: 'GPT-6 直接编写的 three.js 概念网格（秒开，几何为近似）',
    geom_brep_title: 'OCCT B-rep 实体：真实圆角 / 孔 / 壁厚，与下载的 STEP 完全一致（点「生成 STEP」后可用）',
    geom_brep_loading: '正在装入 B-rep 实体…', geom_brep_ready: (n, tris) => `B-rep 实体已装入主视口：${n} 个部件 · ${Number(tris).toLocaleString('en-US')} 三角面 · 与 STEP 一致`,
    geom_brep_fail: 'B-rep 实体装入失败：', view_brep_source: 'OCCT B-rep 实体 · 工程视图', badge_brep: 'B-rep 实体（与 STEP 一致）', badge_brep_cached: '预生成 B-rep 实体（与 STEP 一致）',
    render_cad_toggle: '与 CAD 叠放',
    render_cad_note: (o) => `青色线 = 这张渲染图所依据的 STEP 视图（同一相机）的外轮廓和棱线。图像模型会重新构图，这里只用统一缩放和平移把 STEP 对上去，不拉伸、不旋转：线和画面对不上的地方，就是渲染图偏离 CAD 的地方。`
      + `外形重合度 IoU 约 ${o.iou_pct}%（重合面积 ÷ 两者合并面积；渲染图里的零件区域由程序自动分割，地面反光和阴影会计入，所以只作参考）。渲染图是展示图，尺寸以 STEP 为准。`,
    render_view_gpt: '效果图 · gpt-image', render_view_eng: '工程渲染图 · 与 STEP 一致',
    render_eng_caption: (e) => `工程渲染图 · 按 STEP 几何直接渲染，未调用图像模型 · ${(e.size || []).join('×')}${e.source === 'live_browser' ? ` · 在本浏览器渲染（${e.spp} 帧，${Math.round(e.render_ms / 1000)} 秒）` : ''}`,
    render_eng_busy: (p) => `正在按 STEP 几何渲染工程渲染图（在本浏览器里渲染，不调用模型，约 30 秒）…${p ? ` 已累积 ${p.n} 帧` : ''}`,
    render_eng_fail: '工程渲染图生成失败：',
    render_note_eng: '工程渲染图由渲染程序按 STEP 几何、用同一相机直接算出，外形与 STEP 一致；材质与灯光为示意，不代表真实表面处理。',
    render_eng_cad_note: () => '青色线 = 同一相机下 STEP 的外轮廓和棱线，没做任何缩放或平移，直接叠上就和画面重合：这张图的零件像素就是按 STEP 几何算出来的。尺寸以 STEP 为准。',
  });
  Object.assign(I18N.en, {
    workspace_heading: 'Engineering workspace', workspace_boundary: 'Concept design · Geometry review · Not engineering-validated',
    view_original: 'Original', view_single: 'Perspective', view_quad: 'Quad view', view_material: 'Material preview', view_solid: 'Solid', view_wireframe: 'Wireframe',
    view_fit: 'Frame model / selection', view_grid: 'Grid', view_section: 'Section', view_none: 'Off', view_section_position: 'Section position',
    view_exposure: 'Exposure', view_parts: 'Parts', view_isolate: 'Isolate selection', view_show_all: 'Restore visibility', view_dimensions: 'Model bounds · mm',
    view_outliner: 'Outliner', view_collection: 'Model collection', view_statistics: 'Statistics', stat_objects: 'Meshes', stat_vertices: 'Vertices', stat_triangles: 'Triangles',
    split_side: 'Drag to resize the left column (← → to nudge, double-click to reset)', split_composer: 'Drag to share the height between the conversation and the input box (↑ ↓ to nudge, double-click to reset)',
    view_mesh_boundary: 'Mesh view · Not STEP / CAE validation', view_loading: 'Loading engineering views…',
    view_unavailable: 'This scene did not expose the engineering-view interfaces', view_ready: 'Model geometry · Engineering view',
    geom_concept: 'Concept mesh', geom_brep: 'B-rep solid', geom_concept_title: 'three.js concept mesh written directly by GPT-6 (instant, approximate geometry)',
    geom_brep_title: 'OCCT B-rep solid: real fillets / bores / wall thickness, identical to the downloadable STEP (available after “Generate STEP”)',
    geom_brep_loading: 'Loading B-rep solid…', geom_brep_ready: (n, tris) => `B-rep solid in the main viewport: ${n} parts · ${Number(tris).toLocaleString('en-US')} triangles · identical to STEP`,
    geom_brep_fail: 'B-rep solid failed to load: ', view_brep_source: 'OCCT B-rep solid · Engineering view', badge_brep: 'B-rep solid (matches STEP)', badge_brep_cached: 'Pre-generated B-rep solid (matches STEP)',
    render_cad_toggle: 'Overlay CAD',
    render_cad_note: (o) => `Cyan lines = outline and edges of the STEP view this render was made from (same camera). The image model re-frames the picture, so the STEP is placed with one uniform scale and a shift only — no stretch, no rotation: wherever the lines miss the picture, the render departs from the CAD. `
      + `Silhouette IoU about ${o.iou_pct}% (overlap ÷ union; the part area in the render is segmented automatically and includes floor reflections and shadows, so treat it as indicative). The render is a presentation image; take dimensions from the STEP.`,
    render_view_gpt: 'Visualization · gpt-image', render_view_eng: 'Engineering render · matches STEP',
    render_eng_caption: (e) => `Engineering render · STEP geometry rendered directly, no image model · ${(e.size || []).join('×')}${e.source === 'live_browser' ? ` · rendered in this browser (${e.spp} frames, ${Math.round(e.render_ms / 1000)} s)` : ''}`,
    render_eng_busy: (p) => `Rendering the engineering image from the STEP geometry (in this browser, no model call, about 30 s)…${p ? ` ${p.n} frames so far` : ''}`,
    render_eng_fail: 'Engineering render failed: ',
    render_note_eng: 'The engineering render is computed from the STEP geometry with the same camera, so its shapes match the STEP; materials and lighting are illustrative, not a surface-finish spec.',
    render_eng_cad_note: () => 'Cyan lines = outline and edges of the STEP from the same camera, laid on without any scale or shift, and they coincide: the part pixels of this image are computed from the STEP geometry. Take dimensions from the STEP.',
  });

  const $ = (id) => document.getElementById(id);
  const fmtInt = (n) => Number(n || 0).toLocaleString('en-US');
  // Per-turn token accounting from the API's `usage` (prompt / cached-prefix hits / completion / reasoning).
  function usageText(u, lang) {
    if (!u || !Number.isFinite(u.prompt_tokens)) return u && Number.isFinite(u.completion_tokens) ? ` · ${lang === 'zh' ? '输出' : 'out'} ${fmtInt(u.completion_tokens)} tokens` : '';
    const zh = lang === 'zh';
    const cached = (u.prompt_tokens_details && u.prompt_tokens_details.cached_tokens) || 0;
    const reasoning = (u.completion_tokens_details && u.completion_tokens_details.reasoning_tokens) || 0;
    const hit = u.prompt_tokens ? Math.round(cached / u.prompt_tokens * 100) : 0;
    return ` · ${zh ? '输入' : 'in'} ${fmtInt(u.prompt_tokens)}（${zh ? '命中缓存' : 'cache hit'} ${fmtInt(cached)} · ${hit}%）` +
      ` · ${zh ? '输出' : 'out'} ${fmtInt(u.completion_tokens)}${reasoning ? `（${zh ? '推理' : 'reasoning'} ${fmtInt(reasoning)}）` : ''}` +
      ` · ${zh ? '合计' : 'total'} ${fmtInt(u.total_tokens || (u.prompt_tokens + u.completion_tokens))} tokens`;
  }
  // `?lang=en|zh` in the URL wins for this visit (handy for sharing an English link); otherwise the last choice is remembered.
  const urlParams = new URLSearchParams(location.search);
  const urlLang = (urlParams.get('lang') || '').toLowerCase().slice(0, 2);
  // `?industry=<id>` picks the scenario group (persona + hero texts + cards) the same way; the server lists the ids.
  const urlIndustry = (urlParams.get('industry') || '').toLowerCase().replace(/[^a-z0-9_-]/g, '').slice(0, 32);
  const INDUSTRY_KEY = 's3d.industry';
  const state = {
    lang: (urlLang === 'en' || urlLang === 'zh') ? urlLang : (localStorage.getItem('s3d.lang') || 'zh'),
    industry: urlIndustry || localStorage.getItem(INDUSTRY_KEY) || 'thermal',
    industries: [], industryMeta: null,   // groups from the server; meta = active group (UI texts override I18N when present)
    scenarios: [], scenario: null, cachedIds: [], cadCachedIds: [], renderCachedIds: [], me: null,
    history: [],          // [{role, content, image?}] sent to the API
    result: null,         // last rendered result
    resultIsCache: false, // whether the displayed result is the pre-generated example
    image: null,          // data URL attached to the composer
    generating: false, loadingImage: false, count: 0, exportWaiter: null,
    turns: [], turnIndex: -1,   // multi-turn versions of the current conversation (see recordTurn / showVersion)
    tokens: { prompt: 0, cached: 0, completion: 0, turns: 0 }, // session totals from live calls' `usage`
    renders: [], renderIndex: -1, renderBusy: false, renderAbort: null, // 轨 C results for the current conversation
    concepts: [], conceptIndex: -1, conceptBusy: false,                 // 轨 D concept images (text → image → attach as drawing)
    proposalBusy: false,  // .docx proposal being assembled
    mode: 'example', selectionVersion: 0, viewerVersion: 0, renderState: 'idle', renderTimer: null, viewerCanExportGlb: false,
    viewerCanInspect: false, workspace: null, partsOpen: !window.matchMedia('(max-width: 640px)').matches,
    geometry: 'concept',  // what the main viewer shows: 'concept' (轨 A three.js scene) or 'brep' (轨 B OCCT glTF)
    brepBuffer: null,     // glTF bytes of the current 轨 B result (kept so switching back and forth needs no refetch)
    generationPhase: null, requestId: null, imageKind: null,
    renderStartedAt: 0, renderTick: null, // when the current scene started loading in the iframe + the 1 s ticker for the status label
    abort: null,          // AbortController of the in-flight live request
    previewing: false,    // scene rendered from the early `html` event; metrics still streaming
    refImage: null,       // data URL of the drawing/photo the displayed model was built from
    cadAvailable: false,  // server has CadQuery installed (from /api/me)
    cad: null,            // last 轨 B result ({job_id, files, metrics, ...})
    cadBusy: false, cadAbort: null, cadStale: false, cadViewerVersion: 0, cadViewerWaiter: null,
    effort: null,         // GPT-6 reasoning_effort chosen in the UI (null until /api/me tells us the server default)
    efforts: [],          // values the server accepts (from /api/me)
    lastLatencyEffort: null, // effort of the run behind the "last generation" tile, so the ETA hint is not mixed across efforts
    system: { hotspots: [], stages: [], stage: -1, focus: null, collapsed: false, partsOpen: false }, // reported by system scenes via viewer-bridge
  };

  // ---- System scenes: component index + stage strip, driven through the viewer bridge (focus / set-stage).
  function toViewer(msg) { const w = $('viewer').contentWindow; if (w) w.postMessage({ ...msg, renderId: String(state.viewerVersion) }, '*'); }
  function requestWorkspace(options) {
    if (!state.viewerCanInspect || state.renderState !== 'ready') return;
    $('viewStatus').textContent = t('view_loading');
    $('viewStatus').dataset.error = 'false';
    toViewer({ type: 'workspace', options: { lang: state.lang, ...options } });
  }
  function updateWorkspace() {
    const current = state.workspace || { layout: 'original', shading: 'material', section: 'none', grid: true, exposure: 1.1, offset: 50, parts: [] };
    const enabled = state.viewerCanInspect && state.renderState === 'ready';
    const active = !!current.active;
    document.querySelectorAll('[data-workspace-layout]').forEach(button => {
      button.disabled = !enabled;
      button.setAttribute('aria-pressed', String(button.dataset.workspaceLayout === current.layout));
    });
    document.querySelectorAll('[data-workspace-shading]').forEach(button => {
      button.disabled = !enabled || !active;
      button.setAttribute('aria-pressed', String(button.dataset.workspaceShading === current.shading));
    });
    for (const id of ['viewFit', 'viewGrid', 'viewSection', 'viewExposure', 'viewParts', 'viewShowAll']) $(id).disabled = !enabled || !active;
    $('railPng').disabled = $('btnPng').disabled; $('railFull').disabled = $('btnFull').disabled;
    $('viewSectionOffset').disabled = !enabled || !active || current.section === 'none';
    $('viewSection').value = current.section;
    $('viewSectionOffset').value = current.offset;
    $('viewExposure').value = current.exposure;
    $('viewGrid').checked = current.grid;
    $('viewParts').setAttribute('aria-pressed', String(state.partsOpen));
    $('viewportBody').classList.toggle('parts-open', active && state.partsOpen);
    $('viewportBody').classList.toggle('engineering', active);
    $('partInspector').classList.toggle('hidden', !active || !state.partsOpen);
    $('viewIsolate').disabled = !active || !current.selected;
    const list = $('partList'); list.replaceChildren();
    for (const part of current.parts) {
      const row = document.createElement('div'); row.className = 'part-row'; row.classList.toggle('selected', part.id === current.selected);
      const visible = document.createElement('input'); visible.type = 'checkbox'; visible.checked = part.visible;
      visible.setAttribute('aria-label', `${state.lang === 'en' ? 'Visible' : '显示'}: ${part.name}`);
      visible.addEventListener('change', () => requestWorkspace({ visibility: { id: part.id, visible: visible.checked } }));
      const icon = document.createElement('i'); icon.dataset.lucide = 'box'; icon.setAttribute('aria-hidden', 'true');
      const button = document.createElement('button'); button.type = 'button'; button.textContent = part.name; button.title = part.name;
      button.addEventListener('click', () => requestWorkspace({ selected: part.id }));
      button.addEventListener('dblclick', () => requestWorkspace({ selected: part.id, action: 'fit' }));
      row.append(visible, icon, button); list.appendChild(row);
    }
    $('partCount').textContent = String(current.parts.length);
    $('viewDimensions').replaceChildren();
    if (current.bounds) for (const axis of ['x', 'y', 'z']) {
      const label = document.createElement('dt'); label.textContent = axis.toUpperCase();
      const value = document.createElement('dd'); value.textContent = `${Number(current.bounds[axis]).toFixed(2)} mm`;
      $('viewDimensions').append(label, value);
    }
    $('viewStats').replaceChildren();
    if (current.stats) for (const [key, label] of [['objects', 'stat_objects'], ['vertices', 'stat_vertices'], ['triangles', 'stat_triangles']]) {
      const term = document.createElement('dt'); term.textContent = t(label);
      const value = document.createElement('dd'); value.textContent = fmtInt(current.stats[key]);
      $('viewStats').append(term, value);
    }
    if (window.lucide) window.lucide.createIcons({ nameAttr: 'data-lucide' });
    $('viewStatus').textContent = active ? t(state.geometry === 'brep' ? 'view_brep_source' : 'view_ready') : enabled ? t('view_original') : state.renderState === 'ready' ? t('view_unavailable') : '';
    const brepReady = !!(state.cad && !state.cadStale && state.cad.files && state.cad.files.glb);
    document.querySelectorAll('[data-geometry]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.geometry === state.geometry));
      const g = button.dataset.geometry;
      button.disabled = state.generating || (g === 'brep' ? !brepReady : !state.result);
    });
  }
  // ---- Geometry source: the 轨 A concept mesh or the 轨 B OCCT solid in the same main viewer / workspace.
  async function showBrep(cad) {
    if (!cad || !cad.files || !cad.files.glb) return;
    state.geometry = 'brep';
    $('viewStatus').textContent = t('geom_brep_loading'); $('viewStatus').dataset.error = 'false';
    state.viewerVersion += 1; state.renderState = 'loading'; state.viewerCanExportGlb = false; state.viewerCanInspect = false; state.workspace = null;
    state.renderStartedAt = performance.now(); resetSystemPanel(); updateWorkspace(); updateExperience(); updateControls();
    const version = state.viewerVersion;
    try {
      await loadBrepBuffer(cad);
      if (state.viewerVersion !== version) return;
      const html = await (await fetch('/static/brep-viewer.html?rev=23')).text();
      const frame = $('viewer');
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => { cleanup(); reject(new Error('viewer timeout')); }, 40000);
        const cleanup = () => { clearTimeout(timer); window.removeEventListener('message', onMsg); };
        const onMsg = (ev) => {
          if (ev.source !== frame.contentWindow || !ev.data) return;
          if (ev.data.type === 'brep-viewer-ready') frame.contentWindow.postMessage({ type: 'brep', buffer: state.brepBuffer.bytes.slice(0), parts: cad.parts || [], lang: state.lang,
            title: (state.scenario && (state.lang === 'en' && state.scenario.title_en ? state.scenario.title_en : state.scenario.title)) || 'model' }, '*');
          else if (ev.data.type === 'brep-ready') { cleanup(); resolve(ev.data); }
          else if (ev.data.type === 'brep-error') { cleanup(); reject(new Error(ev.data.message)); }
        };
        window.addEventListener('message', onMsg);
        frame.srcdoc = absolutize(withHelper(html));
      }).then((d) => {
        if (state.viewerVersion !== version) return;
        const cached = cad.source === 'pre_generated';
        $('viewerEmpty').classList.add('hidden'); $('stageBadge').classList.remove('hidden', 'cache', 'live'); $('stageBadge').classList.add(cached ? 'cache' : 'live');
        $('stageBadge').textContent = t(cached ? 'badge_brep_cached' : 'badge_brep');
        addMessage('assistant', t('geom_brep_ready', d.parts, d.triangles));
      });
    } catch (e) {
      if (state.viewerVersion !== version) return;
      addMessage('assistant', t('geom_brep_fail') + e.message, { error: true });
      if (state.result) showResult(state.result, state.resultIsCache, state.refImage, { keepProgress: true, sameResult: true });
    }
  }
  async function loadBrepBuffer(cad) {
    if (state.brepBuffer && state.brepBuffer.job === cad.job_id) return;
    const res = await fetch(cad.files.glb, { headers: connHeaders() });
    if (res.status === 401) { showAuth(); throw new Error('unauthorized'); }
    if (!res.ok) throw await httpError(res);
    state.brepBuffer = { job: cad.job_id, bytes: await res.arrayBuffer() };
  }
  // (Not `showConcept` — that name belongs to the 轨 D concept-image gallery further down in this scope.)
  function showConceptMesh() {
    if (state.geometry === 'concept' || !state.result) return;
    showResult(state.result, state.resultIsCache, state.refImage, { keepProgress: true, sameResult: true });
  }
  document.querySelectorAll('[data-geometry]').forEach(button => button.addEventListener('click', () => {
    const g = button.dataset.geometry;
    if (g === 'brep') showBrep(state.cad); else showConceptMesh();
  }));
  document.querySelectorAll('[data-workspace-layout]').forEach(button => button.addEventListener('click', () => requestWorkspace({ layout: button.dataset.workspaceLayout })));
  document.querySelectorAll('[data-workspace-shading]').forEach(button => button.addEventListener('click', () => requestWorkspace({ shading: button.dataset.workspaceShading })));
  $('viewFit').addEventListener('click', () => requestWorkspace({ action: 'fit' }));
  $('viewGrid').addEventListener('change', event => requestWorkspace({ grid: event.target.checked }));
  $('viewSection').addEventListener('change', event => requestWorkspace({ section: event.target.value }));
  $('viewSectionOffset').addEventListener('input', event => requestWorkspace({ offset: Number(event.target.value) }));
  $('viewExposure').addEventListener('input', event => requestWorkspace({ exposure: Number(event.target.value) }));
  $('viewParts').addEventListener('click', () => { state.partsOpen = !state.partsOpen; updateWorkspace(); });
  $('viewIsolate').addEventListener('click', () => requestWorkspace({ action: 'isolate' }));
  $('viewShowAll').addEventListener('click', () => requestWorkspace({ action: 'show-all' }));
  $('railPng').addEventListener('click', () => $('btnPng').click());
  $('railFull').addEventListener('click', () => $('btnFull').click());
  document.querySelectorAll('[data-lang]').forEach(button => button.addEventListener('click', () => {
    if (state.workspace) requestWorkspace({ lang: button.dataset.lang });
  }));
  if (window.lucide) window.lucide.createIcons();
  updateWorkspace();
  function resetSystemPanel() { state.system = { hotspots: [], stages: [], stage: -1, focus: null, collapsed: state.system.collapsed, partsOpen: false }; renderSystemPanel(); }
  function renderSystemPanel() {
    const box = $('systemPanel'); const sys = state.system;
    const has = sys.hotspots.length || sys.stages.length;
    box.classList.toggle('hidden', !has);
    box.classList.toggle('collapsed', sys.collapsed);
    box.innerHTML = '';
    if (!has) return;
    const head = (label, onToggle, toggleLabel) => {
      const h = document.createElement('div'); h.className = 'sp-head';
      const s = document.createElement('span'); s.textContent = label; h.appendChild(s);
      if (onToggle) { const b = document.createElement('button'); b.type = 'button'; b.className = 'linklike'; b.textContent = toggleLabel; b.addEventListener('click', onToggle); h.appendChild(b); }
      return h;
    };
    const collapseToggle = () => { sys.collapsed = !sys.collapsed; renderSystemPanel(); };
    if (sys.stages.length) {
      box.appendChild(head(`${t('sys_stages')} · ${sys.stage + 1}/${sys.stages.length}`, collapseToggle, t(sys.collapsed ? 'sys_expand' : 'sys_collapse')));
      const row = document.createElement('div'); row.className = 'sp-row sp-strip';
      sys.stages.forEach((st, i) => {
        const b = document.createElement('button'); b.type = 'button'; b.className = `sp-stage${i === sys.stage ? ' active' : ''}`;
        b.innerHTML = '<span class="n"></span><span></span>'; b.querySelector('.n').textContent = String(i + 1).padStart(2, '0'); b.lastChild.textContent = st.title;
        b.title = st.text; b.addEventListener('click', () => { sys.stage = i; toViewer({ type: 'set-stage', index: i }); renderSystemPanel(); });
        row.appendChild(b);
      });
      box.appendChild(row);
      if (sys.stage >= 0 && sys.stages[sys.stage] && sys.stages[sys.stage].text) { const p = document.createElement('div'); p.className = 'sp-text'; p.textContent = sys.stages[sys.stage].text; box.appendChild(p); }
    }
    if (sys.hotspots.length) {
      // Long component lists (whole systems easily have 12–16) start folded so the panel never hides the model.
      const open = sys.partsOpen || sys.hotspots.length <= 6;
      const toggle = sys.stages.length
        ? (sys.hotspots.length > 6 ? () => { sys.partsOpen = !sys.partsOpen; renderSystemPanel(); } : null)
        : collapseToggle;
      const label = `${t('sys_parts')} · ${sys.hotspots.length}`;
      box.appendChild(head(label, toggle, sys.stages.length ? t(open ? 'sys_collapse' : 'sys_expand') : t(sys.collapsed ? 'sys_expand' : 'sys_collapse')));
      if (open) {
        const row = document.createElement('div'); row.className = 'sp-row sp-parts';
        for (const h of sys.hotspots) {
          const b = document.createElement('button'); b.type = 'button'; b.className = `sp-part${h.id === sys.focus ? ' active' : ''}`;
          b.innerHTML = '<span class="n"></span><span></span>'; b.querySelector('.n').textContent = h.n; b.lastChild.textContent = h.label;
          if (h.part && h.part !== h.label && !h.label.includes(h.part)) { const s = document.createElement('small'); s.textContent = `· ${h.part}`; b.appendChild(s); }
          b.title = h.note || h.part || h.label;
          b.addEventListener('click', () => { sys.focus = sys.focus === h.id ? null : h.id; toViewer({ type: 'focus', id: sys.focus }); renderSystemPanel(); });
          row.appendChild(b);
        }
        if (sys.focus) { const b = document.createElement('button'); b.type = 'button'; b.className = 'sp-part'; b.textContent = t('sys_overview'); b.addEventListener('click', () => { sys.focus = null; toViewer({ type: 'focus', id: null }); renderSystemPanel(); }); row.appendChild(b); }
        box.appendChild(row);
      } else if (sys.focus) {
        const f = sys.hotspots.find((h) => h.id === sys.focus);
        const p = document.createElement('div'); p.className = 'sp-text'; p.textContent = f ? `${f.n} · ${f.label}${f.note ? ` — ${f.note}` : ''}` : ''; box.appendChild(p);
      }
    }
  }

  const EFFORT_KEY = 's3d.effort';
  function setEffort(value, persist = true) {
    if (!state.efforts.includes(value)) return;
    state.effort = value;
    $('effort').value = value;
    $('effortWrap').classList.toggle('slow', value === 'high' || value === 'xhigh');
    if (persist) localStorage.setItem(EFFORT_KEY, value);
  }

  // The deployment refused the chosen effort and the server sent the nearest value it accepts: re-read the accepted
  // values so the selector stops offering the refused one, and select the value actually applied. A choice the user
  // changed while the request was running is left alone.
  async function followAppliedEffort(requested, applied) {
    if (!requested || !applied || applied === requested || state.effort !== requested) return;
    let me; try { me = await api('/api/me'); } catch (_) { return; }
    if (Array.isArray(me.reasoning_efforts) && me.reasoning_efforts.length) state.efforts = me.reasoning_efforts;
    [...$('effort').options].forEach((o) => { o.hidden = !state.efforts.includes(o.value); });
    if (state.effort === requested) setEffort(applied);
  }

  // ---- Model connection: server-managed by default; legacy BYOK remains available behind an explicit server flag.
  const CONN_KEY = 's3d.aoai';
  const ENDPOINT_RE = /^https:\/\/[A-Za-z0-9-]+\.(openai\.azure\.com|cognitiveservices\.azure\.com|services\.ai\.azure\.com)$/;
  function hostManagedConnection() {
    return !!(state.me && state.me.host_connection_for_all);
  }
  function normalizeConnection(value) {
    if (!value || typeof value.endpoint !== 'string' || typeof value.key !== 'string' ||
        (value.deployment !== undefined && typeof value.deployment !== 'string')) throw new Error(t('conn_invalid'));
    const c = { endpoint: value.endpoint.trim().replace(/\/+$/, ''), deployment: (value.deployment || '').trim(), key: value.key.trim() };
    if (!ENDPOINT_RE.test(c.endpoint) || !/^[A-Za-z0-9._~+/=-]{16,256}$/.test(c.key) ||
        (c.deployment && !/^[A-Za-z0-9._-]{1,64}$/.test(c.deployment))) throw new Error(t('conn_invalid'));
    return c;
  }
  function ownConnection() {
    try {
      const raw = localStorage.getItem(CONN_KEY);
      return raw === null ? null : normalizeConnection(JSON.parse(raw));
    } catch (_) { throw new Error(t('conn_read_failed')); }
  }
  function connHeaders() {
    if (hostManagedConnection()) return {};
    const c = ownConnection();
    return c ? { 'X-AOAI-Endpoint': c.endpoint, 'X-AOAI-Key': c.key, 'X-AOAI-Deployment': c.deployment || '' } : {};
  }
  function setConnectionMode() {
    const managed = hostManagedConnection();
    $('connIntro').textContent = t(managed ? 'conn_host_intro' : 'conn_intro');
    $('connKeyLabel').textContent = t(managed ? 'conn_auth' : 'conn_key');
    $('connBackupNote').classList.toggle('hidden', managed);
    $('connHttpWarning').classList.toggle('hidden', managed || (window.location && window.location.protocol === 'https:'));
    for (const id of ['connImport', 'connClear', 'connSave']) $(id).classList.toggle('hidden', managed);
    for (const id of ['connEndpoint', 'connDeployment', 'connKey']) {
      $(id).readOnly = managed;
      $(id).classList.toggle('hidden', managed);
      $(`${id}Value`).classList.toggle('hidden', !managed);
    }
    $('connKey').type = managed ? 'text' : 'password';
    $('connButton').textContent = managed ? '🔒' : '🔑';
  }
  function renderConnection() {
    let c = null, readError = '';
    const me = state.me || {};
    const managed = hostManagedConnection();
    setConnectionMode();
    if (!managed) {
      try { c = ownConnection(); } catch (err) { readError = err.message; }
    }
    const deployment = c ? (c.deployment || me.deployment || '') : (me.deployment || '');
    const host = c ? c.endpoint.replace(/^https:\/\//, '') : (me.endpoint_host || '');
    const tag = managed ? t('conn_auto_tag') : (c ? t('conn_own_tag') : (me.role === 'owner' ? t('conn_owner_tag') : ''));
    $('globalStatus').textContent = `${deployment} · ${host.split('.')[0]}${tag ? ` · ${tag}` : ''}`;
    $('globalDot').classList.toggle('own', !!c);
    $('connPill').classList.toggle('own', !!c);
    $('statModel').textContent = deployment || '—'; $('statModel').title = host;
    $('connOwnerNote').classList.toggle('hidden', managed || me.role !== 'owner');
    $('connOwnerNote').textContent = t('conn_owner_note');
    const needs = !managed && !!me.byok_required && !c;
    // Visitors who are asked for a key get a one-line pointer to the owner sign-in (the presenter's own machine never needs a key).
    $('connPresenterHint').classList.toggle('hidden', !needs || me.role === 'owner');
    $('connPresenterHint').textContent = t('conn_presenter_hint');
    const notice = $('connNotice'); notice.classList.toggle('hidden', !needs);
    if (needs) { notice.textContent = t('conn_required') + ' '; const b = document.createElement('button'); b.type = 'button'; b.className = 'linklike'; b.textContent = t('conn_required_btn'); b.addEventListener('click', openConnDialog); notice.appendChild(b); }
    if (readError) {
      $('globalStatus').textContent = t('conn_heading') + ' · !';
      $('statModel').textContent = '—'; $('statModel').title = '';
      notice.classList.remove('hidden'); notice.textContent = readError;
    }
  }
  function fillConnForm(c) {
    $('connEndpoint').value = c.endpoint || ''; $('connDeployment').value = c.deployment || ''; $('connKey').value = c.key || '';
  }
  function fillManagedConnection() {
    const me = state.me || {};
    const values = {
      connEndpoint: me.endpoint || (me.endpoint_host ? `https://${me.endpoint_host}` : ''),
      connDeployment: me.deployment || '',
      connKey: t('conn_managed_key', me.host_auth),
    };
    fillConnForm({ endpoint: values.connEndpoint, deployment: values.connDeployment, key: values.connKey });
    for (const [id, value] of Object.entries(values)) $(`${id}Value`).textContent = value;
  }
  function openConnDialog() {
    $('connStatus').textContent = ''; delete $('connStatus').dataset.ok;
    setConnectionMode();
    if (hostManagedConnection()) {
      fillManagedConnection();
    } else {
      try { fillConnForm(ownConnection() || {}); }
      catch (err) { fillConnForm({}); connStatus(err.message, false); }
    }
    $('connDialog').showModal();
    if (hostManagedConnection()) {
      $('connCancel').focus?.();
      for (const id of ['connEndpoint', 'connDeployment', 'connKey']) $(id).scrollLeft = 0;
    }
  }
  function connectionReady() {
    if (hostManagedConnection()) return true;
    try { if (ownConnection() || !state.me || !state.me.byok_required) return true; }
    catch (err) { openConnDialog(); connStatus(err.message, false); return false; }
    openConnDialog(); return false;
  }
  function readConnForm() {
    return normalizeConnection({ endpoint: $('connEndpoint').value, deployment: $('connDeployment').value, key: $('connKey').value });
  }
  function connStatus(text, ok) { const s = $('connStatus'); s.textContent = text; if (ok === undefined) delete s.dataset.ok; else s.dataset.ok = String(ok); }
  let connBusy = false;
  function setConnBusy(busy) {
    connBusy = busy;
    $('connForm').querySelectorAll('button, input').forEach((el) => { el.disabled = busy; });
  }
  async function backupConnection(c) {
    const text = JSON.stringify(c, null, 2) + '\n';
    if (typeof window.showSaveFilePicker === 'function') {
      const handle = await window.showSaveFilePicker({
        suggestedName: 'password.txt',
        types: [{ description: 'Local connection backup', accept: { 'text/plain': ['.txt'] } }],
      });
      const writable = await handle.createWritable();
      let closed = false;
      try { await writable.write(text); await writable.close(); closed = true; }
      finally { if (!closed) await writable.abort(); }
      return 'conn_backup_saved';
    }
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
    try { download(url, 'password.txt'); }
    finally { setTimeout(() => URL.revokeObjectURL(url), 30000); }
    return 'conn_backup_download';
  }
  $('connButton').addEventListener('click', openConnDialog);
  $('connPill').addEventListener('click', openConnDialog);
  $('connForm').addEventListener('submit', (e) => e.preventDefault());
  $('connDialog').addEventListener('cancel', (e) => { if (connBusy) e.preventDefault(); });
  $('connCancel').addEventListener('click', () => $('connDialog').close());
  $('connClear').addEventListener('click', () => {
    if (!window.confirm(t('conn_clear_confirm'))) return;
    try { localStorage.removeItem(CONN_KEY); }
    catch (_) { connStatus(t('conn_clear_failed'), false); return; }
    fillConnForm({}); renderConnection(); connStatus(t('conn_cleared'), true);
  });
  $('connSave').addEventListener('click', async () => {
    let c;
    try { c = readConnForm(); } catch (err) { connStatus(err.message, false); return; }
    setConnBusy(true);
    let browserSaved = false;
    try { localStorage.setItem(CONN_KEY, JSON.stringify(c)); browserSaved = true; }
    catch (_) { /* Still offer a file backup when browser storage is unavailable. */ }
    renderConnection();
    const browserStatus = t(browserSaved ? 'conn_saved' : 'conn_save_failed');
    connStatus(`${browserStatus} ${t('conn_saving')}`);
    try { connStatus(`${browserStatus} ${t(await backupConnection(c))}`, browserSaved); }
    catch (err) { connStatus(`${browserStatus} ${t(err.name === 'AbortError' ? 'conn_backup_cancelled' : 'conn_backup_failed')}`, false); }
    finally { setConnBusy(false); }
  });
  $('connImport').addEventListener('click', () => $('connImportFile').click());
  $('connImportFile').addEventListener('change', async () => {
    const file = $('connImportFile').files[0];
    if (!file) return;
    setConnBusy(true);
    try {
      let c;
      try {
        if (file.size > 16 * 1024) throw new Error('Backup too large');
        c = normalizeConnection(JSON.parse((await file.text()).replace(/^\uFEFF/, '')));
      } catch (_) { connStatus(t('conn_import_invalid'), false); return; }
      try { localStorage.setItem(CONN_KEY, JSON.stringify(c)); }
      catch (_) { connStatus(t('conn_import_failed'), false); return; }
      fillConnForm(c); renderConnection(); connStatus(t('conn_imported'), true);
    } finally { $('connImportFile').value = ''; setConnBusy(false); }
  });
  $('connTest').addEventListener('click', async () => {
    let headers = {};
    if (!hostManagedConnection()) {
      let c;
      try { c = readConnForm(); } catch (err) { connStatus(err.message, false); return; }
      headers = { 'X-AOAI-Endpoint': c.endpoint, 'X-AOAI-Key': c.key, 'X-AOAI-Deployment': c.deployment };
    }
    connStatus(t('conn_testing')); setConnBusy(true);
    try {
      const res = await fetch(`/api/connection/test?lang=${state.lang}`, { method: 'POST', headers });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
      connStatus(data.ok ? t('conn_test_ok', data) : t('conn_test_fail', data), !!data.ok);
    } catch (err) { connStatus(err.message, false); }
    finally { setConnBusy(false); }
  });
  // Non-OK responses from the API endpoints carry a JSON `detail` (validation / BYOK errors) — surface it instead of "400 Bad Request".
  async function httpError(res) {
    const data = await res.json().catch(() => null);
    return new Error((data && (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))) || `${res.status} ${res.statusText}`);
  }

  // UI texts the active industry group may override (server-provided, bilingual); everything else stays in I18N.
  const INDUSTRY_TEXT_KEYS = new Set(['title', 'hero', 'hero_sub', 'hero_sub2', 'hero_sub3']);
  const t = (k, ...a) => {
    const meta = state.industryMeta;
    if (meta && INDUSTRY_TEXT_KEYS.has(k)) {
      const v = meta[state.lang === 'en' ? `${k}_en` : k];
      if (typeof v === 'string') return v;
    }
    const v = (I18N[state.lang] || I18N.zh)[k] ?? I18N.zh[k] ?? k; return typeof v === 'function' ? v(...a) : v;
  };

  function applyLang() {
    document.documentElement.lang = state.lang === 'zh' ? 'zh-CN' : 'en';
    document.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll('.hero-sub2[data-i18n]').forEach((el) => el.classList.toggle('hidden', !el.textContent));  // a group may have fewer hero lines
    document.querySelectorAll('[data-i18n-ph]').forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    document.querySelectorAll('[data-i18n-title]').forEach((el) => { el.title = t(el.dataset.i18nTitle); });
    document.querySelectorAll('.lang-toggle button').forEach((b) => b.classList.toggle('active', b.dataset.lang === state.lang));
    document.title = `${t('title')} · GPT-6 Astra`;
    renderIndustryTabs();
    renderScenarios();
    if (state.result) {
      setBadge(state.resultIsCache);
      const live = state.result.live_metrics && state.result.live_metrics.length;
      renderMetrics(live ? state.result.live_metrics : (state.result.metrics || []), !!live);
    }
    if (state.cad) renderCad(state.cad);
    applyRenderCad();
    renderSystemPanel();
    renderVersions(); renderSessionStats();
    if (state.me) { renderConnection(); updateConceptStudio(); }
    updateExperience();
    updateControls();
    updateFullBtn();
  }
  document.querySelectorAll('.lang-toggle button').forEach((b) => b.addEventListener('click', () => {
    if (b.dataset.lang === state.lang) return;
    const s = state.scenario;
    const promptUntouched = isScenarioPrompt(s, $('prompt').value.trim());
    state.lang = b.dataset.lang; localStorage.setItem('s3d.lang', state.lang); applyLang();
    if (!s) return;
    // Only a saved example is on stage (no live conversation / STEP job / attached image): reload it in the new
    // language. selectScenario() resets the prompt synchronously, so an edited prompt can be put back right after.
    // A pre-generated STEP solid is part of the example, not the user's work: it reloads with it.
    const liveCad = !!(state.cad && state.cad.source !== 'pre_generated');
    const idle = !state.generating && !state.loadingImage && !state.cadBusy && !liveCad && !state.image;
    const exampleOnly = state.mode === 'example' && !state.history.length && (!state.result || state.resultIsCache);
    if (idle && exampleOnly && state.cachedIds.includes(s.id)) {
      const edited = promptUntouched ? null : $('prompt').value;
      selectScenario(s);
      if (edited) $('prompt').value = edited;
      return;
    }
    // Otherwise keep the conversation; just refresh the untouched scenario prompt and the follow-up chips.
    if (promptUntouched) $('prompt').value = promptFor(s);
    if (!state.history.length && !(state.result && !state.resultIsCache)) renderChips(chipsFor(s));
  }));

  function updateExperience() {
    $('modeExample').setAttribute('aria-pressed', String(state.mode === 'example'));
    $('modeLive').setAttribute('aria-pressed', String(state.mode === 'live'));
    $('modeHint').textContent = t(state.mode === 'live' ? 'hint_live' : 'hint_example');
    $('scenarioHint').textContent = t(state.mode === 'live' ? 'cards_live' : 'scenarios_hint');
    $('sourceLabel').textContent = t(!state.result ? 'source_empty' : state.resultIsCache ? 'source_cache' : 'source_live');
    // While the browser is still loading the scene, show the seconds ticking so a slow first load (three.js download) never looks stuck.
    const loadingFor = state.renderState === 'loading' && state.renderStartedAt ? ` · ${Math.floor((performance.now() - state.renderStartedAt) / 1000)} s` : '';
    $('renderStatus').textContent = t(state.previewing && state.renderState === 'loading' ? 'render_preview' : `render_${state.renderState}`) + loadingFor;
    $('renderStatus').dataset.error = String(state.renderState === 'failed');
    $('cancelBtn').textContent = t('cancel');
    $('kbdHint').textContent = t('kbd_hint');
    $('refToggle').textContent = t($('refImage').classList.contains('collapsed') ? 'show_ref' : 'hide_ref');
    $('refImage').classList.toggle('hidden', !state.refImage);
    const r = state.result;
    $('sourceDetails').textContent = r ? [
      r.actual_model || r.model,
      r.reasoning_effort ? t('effort_tag', r.reasoning_effort) : '',
      !state.resultIsCache && r.key_source ? t('key_source', r.key_source, r.endpoint_host || '') : '',
      `${t('source_time')}: ${r.created_at}`,
      `${t(state.resultIsCache ? 'historical_latency' : 'current_latency')}: ${r.latency_s}s`,
      !state.resultIsCache && r.request_id ? `${t('trace_id')}: ${r.request_id}` : '',
    ].filter(Boolean).join(' · ') : '';
    $('generationStatus').textContent = state.generationPhase ? t(state.generationPhase) +
      (state.requestId ? ` · ${t('trace_id')}: ${state.requestId}` : '') : '';
    $('generationStatus').dataset.error = String(state.generationPhase === 'no_fallback');
    $('imageNotice').textContent = state.imageKind ? t(`image_${state.imageKind}`) : '';
    $('imageNotice').classList.toggle('hidden', !state.imageKind);
  }

  function updateControls() {
    const busy = state.generating || state.loadingImage;
    for (const id of ['sendBtn', 'newChat', 'modeExample', 'modeLive', 'imageInput', 'imageRemove', 'sampleDrawing', 'prompt', 'effort']) {
      $(id).disabled = busy;
    }
    document.querySelectorAll('.scenario, .chip, .industry-tabs button').forEach(b => { b.disabled = busy; });
    $('sendBtn').textContent = t(state.generating ? 'generating' : 'generate');
    $('cancelBtn').classList.toggle('hidden', !state.generating);
    // Exports stay available while the early-rendered scene is on stage; the model is what is exported.
    setExportEnabled(!!state.result && state.renderState === 'ready' && !state.loadingImage);
    updateStepBtn();
    updateRenderBtn();
  }

  function updateStepBtn() {
    const b = $('btnStep');
    b.classList.toggle('hidden', !state.cadAvailable);
    $('tabCad').classList.toggle('hidden', !state.cadAvailable);
    b.disabled = !state.cadAvailable || state.cadBusy || state.generating || !state.result || state.previewing;
    b.classList.toggle('busy', state.cadBusy);
    b.textContent = t(state.cadBusy ? 'btn_step_busy' : 'btn_step');
    b.title = state.cadAvailable ? t('cad_intro') : t('cad_unavailable');
  }

  async function setMode(mode) {
    if (state.generating || state.loadingImage || state.mode === mode) return;
    state.mode = mode;
    const scenario = state.scenario;
    if (scenario) await selectScenario(scenario);
    else resetConversation();
    updateExperience();
  }
  $('modeExample').addEventListener('click', () => setMode('example'));
  $('modeLive').addEventListener('click', () => setMode('live'));
  $('effort').addEventListener('change', (e) => setEffort(e.target.value));

  // ---------------------------------------------------------------- theme
  // Dark is the default (set on <html> in index.html, Blender-style workbench); a saved light choice still wins.
  const savedTheme = localStorage.getItem('s3d.theme');
  if (savedTheme) document.documentElement.dataset.theme = savedTheme;
  $('themeButton').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next; localStorage.setItem('s3d.theme', next);
  });

  // ---------------------------------------------------------------- auth
  async function api(path, opts = {}) {
    const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
    if (res.status === 401) { showAuth(); throw new Error('unauthorized'); }
    if (!res.ok) { let msg = res.statusText; try { msg = (await res.json()).detail || msg; } catch (_) { /* ignore */ } throw new Error(msg); }
    return res.json();
  }
  function showAuth() { $('authView').classList.remove('hidden'); $('appView').classList.add('hidden'); }
  function showApp() { $('authView').classList.add('hidden'); $('appView').classList.remove('hidden'); }

  $('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault(); $('loginError').textContent = '';
    try {
      await api('/api/login', { method: 'POST', body: JSON.stringify({ username: $('username').value, password: $('password').value }) });
      await boot();
    } catch (err) { $('loginError').textContent = err.message; }
  });
  $('logoutButton').addEventListener('click', async () => { await fetch('/api/logout', { method: 'POST' }); location.reload(); });

  async function boot() {
    let me;
    try { me = await api('/api/me'); } catch (_) { showAuth(); return; }
    showApp();
    state.me = me;
    // The clear-text warning in the connection dialog only applies when the page itself is served over HTTP.
    document.querySelectorAll('.conn-warning').forEach((el) => el.classList.toggle('hidden', location.protocol === 'https:'));
    $('globalDot').classList.add('live');
    renderConnection();
    updateConceptStudio();
    state.cachedIds = [...new Set([...(me.cached || []), ...(me.cached_en || [])])]; // either language counts (server falls back)
    state.cadCachedIds = Array.isArray(me.cad_cached) ? me.cad_cached : [];           // scenarios with a pre-generated STEP solid
    // … and with a pre-generated render; ?render_cache=0 skips them so pregen_render.py can render through the live path
    state.renderCachedIds = Array.isArray(me.render_cached) && new URLSearchParams(location.search).get('render_cache') !== '0' ? me.render_cached : [];
    state.cadAvailable = !!me.cad_available;
    updateStepBtn();
    // Reasoning-effort selector: options come from the server; the remembered choice wins, else the server default.
    state.efforts = Array.isArray(me.reasoning_efforts) && me.reasoning_efforts.length ? me.reasoning_efforts : ['low', 'medium', 'high', 'xhigh'];
    [...$('effort').options].forEach((o) => { o.hidden = !state.efforts.includes(o.value); });
    const remembered = localStorage.getItem(EFFORT_KEY);
    setEffort(state.efforts.includes(remembered) ? remembered : (state.efforts.includes(me.reasoning_effort) ? me.reasoning_effort : state.efforts[0]), false);
    if (me.stats && me.stats.last_latency_s) { $('statLatency').textContent = `${me.stats.last_latency_s}s`; state.lastLatencyEffort = me.stats.last_effort || null; }
    const data = await api('/api/scenarios');
    state.scenarios = data.scenarios;
    setIndustries(data.industries || state.industries);
    applyLang();
    // Never open on an empty stage: show the first saved example of the active group right away (clearly labelled as such).
    await openFirstExample();
  }

  // ---------------------------------------------------------------- industries (scenario groups)
  const industryScenarios = () => state.scenarios.filter((s) => (s.industry || 'thermal') === state.industry);

  function setIndustries(list) {
    state.industries = Array.isArray(list) ? list : [];
    if (state.industries.length && !state.industries.some((i) => i.id === state.industry)) state.industry = state.industries[0].id;
    state.industryMeta = state.industries.find((i) => i.id === state.industry) || null;
    localStorage.setItem(INDUSTRY_KEY, state.industry);
    $('statScenarios').textContent = state.scenarios.length ? industryScenarios().length : (state.industryMeta && state.industryMeta.count) || '–';
  }

  function renderIndustryTabs() {
    const box = $('industryTabs'); if (!box) return;
    box.innerHTML = ''; box.classList.toggle('hidden', state.industries.length < 2);
    for (const ind of state.industries) {
      const b = document.createElement('button'); b.type = 'button'; b.className = ind.id === state.industry ? 'active' : '';
      b.disabled = state.generating || state.loadingImage || state.cadBusy;
      const label = state.lang === 'en' && ind.label_en ? ind.label_en : ind.label;
      b.innerHTML = '<span></span><small></small>'; b.querySelector('span').textContent = label; b.querySelector('small').textContent = ind.count;
      b.addEventListener('click', () => setIndustry(ind.id));
      box.appendChild(b);
    }
  }

  async function openFirstExample() {
    const first = industryScenarios().find((s) => state.cachedIds.includes(s.id)) || industryScenarios()[0];
    if (first && state.mode === 'example' && !state.result && !state.scenario) await selectScenario(first);
  }

  async function setIndustry(id) {
    if (id === state.industry || state.generating || state.loadingImage || state.cadBusy) return;
    state.industry = id; setIndustries(state.industries);
    const url = new URL(location.href); url.searchParams.set('industry', id); history.replaceState(null, '', url);
    // A conversation from the other group would keep the wrong persona: start clean and show that group's first example.
    resetConversation(true);
    applyLang();
    await openFirstExample();
  }

  // ---------------------------------------------------------------- scenarios
  function renderScenarios() {
    const list = $('scenarioList'); list.innerHTML = '';
    for (const s of industryScenarios()) {
      const el = document.createElement('button'); el.type = 'button';
      el.className = `scenario c-${s.color || 'blue'}${state.scenario && state.scenario.id === s.id ? ' active' : ''}`;
      el.disabled = state.generating || state.loadingImage;
      el.dataset.scenario = s.id;
      const title = state.lang === 'en' && s.title_en ? s.title_en : s.title;
      const sub = state.lang === 'en' && s.subtitle_en ? s.subtitle_en : s.subtitle;
      const pain = state.lang === 'en' && s.pain_en ? s.pain_en : s.pain;
      el.innerHTML = `<div class="s-icon">${s.icon}</div><div><strong></strong><small></small><span class="s-pain"></span></div>`;
      el.querySelector('strong').textContent = title; el.querySelector('small').textContent = sub; el.querySelector('.s-pain').textContent = pain;
      el.addEventListener('click', () => selectScenario(s));
      list.appendChild(el);
    }
  }

  // Scenario prompt / follow-up chips in the UI language (English copies are optional per card).
  const promptFor = (s) => (state.lang === 'en' && s.prompt_en ? s.prompt_en : s.prompt);
  const chipsFor = (s) => (state.lang === 'en' && s.chips_en && s.chips_en.length ? s.chips_en : (s.chips || []));
  const isScenarioPrompt = (s, text) => !!s && (text === s.prompt || (!!s.prompt_en && text === s.prompt_en));

  async function selectScenario(s) {
    if (state.generating || state.loadingImage) return;
    state.scenario = s; renderScenarios();
    resetConversation(false);
    $('prompt').value = promptFor(s);
    renderChips(chipsFor(s));
    $('sampleDrawing').classList.toggle('hidden', !s.requires_image);
    updateExperience();
    const version = state.selectionVersion;
    if (state.mode === 'example' && state.cachedIds.includes(s.id)) {
      state.generationPhase = 'cache_loading'; updateExperience();
      try {
        const cached = await api(`/api/cache/${s.id}?lang=${state.lang}`);
        if (version !== state.selectionVersion || state.generating) return;
        if (cached.source !== 'pre_generated') throw new Error('Unexpected example provenance');
        state.generationPhase = null;
        // Drawing scenarios: the saved example was generated from the bundled sample drawing — show it.
        const ref = s.requires_image && s.sample_image ? s.sample_image : null;
        recordTurn(cached, true, promptFor(s), ref);
        showResult(cached, true, ref);
        addMessage('user', promptFor(s) + (ref ? `\n${t('image_sample')}` : ''), ref ? { imageThumb: ref } : null);
        // The server serves the other language's file when no example exists in the UI language — say so.
        const fallbackNote = cached.lang_fallback ? `\n${t('cache_fallback_en')}` : '';
        addMessage('assistant', `${cached.summary}\n${t('example_note')}${fallbackNote}`, cached);
        // Scenarios with a pre-generated STEP solid show it right away: CAD tab filled, B-rep in the main viewport. The
        // pre-generated render loads alongside, so the render tab is already filled while the B-rep is still loading.
        await Promise.all([
          state.cadAvailable && state.cadCachedIds.includes(s.id) ? showCachedCad(s, version) : null,
          state.me && state.me.image_deployment && state.renderCachedIds.includes(s.id) ? showCachedRender(s, version) : null,
        ]);
      } catch (err) {
        if (version !== state.selectionVersion || state.generating) return;
        state.generationPhase = null; updateExperience();
        addMessage('assistant', t('cache_error') + err.message, { error: true });
      }
    } else if (state.mode === 'example') {
      state.generationPhase = 'cache_absent'; updateExperience();
    }
  }

  function renderChips(chips) {
    const box = $('chips'); box.innerHTML = '';
    for (const c of chips) {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'chip'; b.textContent = c;
      b.addEventListener('click', () => { $('prompt').value = c; $('prompt').focus(); });
      box.appendChild(b);
    }
  }

  // ---- Multi-turn versions: v0 = saved example (if any), v1… = live iterations. Each turn snapshots the result and
  // the conversation history *after* it, so clicking an older version shows it and branches the next request from there.
  function recordTurn(result, isCache, prompt, refImage) {
    if (state.turnIndex >= 0 && state.turnIndex < state.turns.length - 1) state.turns = state.turns.slice(0, state.turnIndex + 1); // branch: drop later versions
    state.turns.push({ result, isCache, prompt, refImage, history: state.history.slice(), suggestions: result.suggestions || [] });
    state.turnIndex = state.turns.length - 1;
    renderVersions();
  }
  function showVersion(i) {
    const turn = state.turns[i];
    if (!turn || state.generating || state.loadingImage) return;
    state.turnIndex = i;
    state.history = turn.history.slice(); state.image = null; state.imageKind = null; $('imagePreview').classList.add('hidden'); $('imageInput').value = '';
    showResult(turn.result, turn.isCache, turn.refImage);
    renderChips(turn.isCache && state.scenario ? chipsFor(state.scenario) : (turn.suggestions.length ? turn.suggestions : (state.scenario ? chipsFor(state.scenario) : [])));
    renderVersions(); updateExperience();
  }
  function previousTurnMetrics() {
    const prev = state.turns[state.turnIndex - 1];
    if (!prev) return null;
    const r = prev.result;
    return (r.live_metrics && r.live_metrics.length) ? r.live_metrics : (r.metrics || []);
  }
  function renderVersions() {
    const strip = $('versionStrip');
    strip.innerHTML = '';
    if (!state.turns.length) { strip.classList.add('hidden'); return; }
    strip.classList.remove('hidden');
    const label = document.createElement('span'); label.className = 'vs-label'; label.textContent = t('versions'); strip.appendChild(label);
    state.turns.forEach((turn, i) => {
      const b = document.createElement('button'); b.type = 'button'; b.className = `vs-chip${i === state.turnIndex ? ' active' : ''}`;
      const name = turn.isCache ? t('version_example') : `v${state.turns.slice(0, i + 1).filter((x) => !x.isCache).length}`;
      b.innerHTML = '<span></span><small></small>'; b.firstChild.textContent = name; b.lastChild.textContent = (turn.prompt || '').slice(0, 26);
      b.title = turn.prompt || ''; b.addEventListener('click', () => showVersion(i));
      strip.appendChild(b);
    });
    const hint = document.createElement('span'); hint.className = 'vs-hint';
    const branching = state.turnIndex < state.turns.length - 1;
    hint.classList.toggle('branch', branching);
    hint.textContent = branching ? t('version_branch') : t('version_hint');
    strip.appendChild(hint);
  }

  // ---------------------------------------------------------------- conversation
  function resetConversation(clearScenario = true) {
    if (state.generating || state.loadingImage) return;
    state.selectionVersion += 1; state.viewerVersion += 1;
    clearTimeout(state.renderTimer);
    state.renderState = 'idle'; state.viewerCanExportGlb = false; state.generationPhase = null; state.requestId = null; state.imageKind = null;
    state.viewerCanInspect = false; state.workspace = null; updateWorkspace();
    state.history = []; state.result = null; state.resultIsCache = false; state.image = null;
    state.turns = []; state.turnIndex = -1; renderVersions();
    state.previewing = false; state.refImage = null; $('refImage').classList.remove('collapsed');
    $('messages').innerHTML = `<div class="empty-hint">${t('empty_msgs')}</div>`;
    $('imagePreview').classList.add('hidden'); $('imageInput').value = '';
    $('viewer').removeAttribute('srcdoc'); $('viewerEmpty').classList.remove('hidden'); $('streamOut').textContent = '';
    resetSystemPanel();
    $('summaryBox').textContent = ''; renderMetrics([], false); $('runInfo').textContent = '';
    $('stageBadge').classList.add('hidden'); setExportEnabled(false);
    resetCad();
    resetRenders();
    if (clearScenario) { state.scenario = null; renderScenarios(); $('prompt').value = ''; renderChips([]); $('sampleDrawing').classList.add('hidden'); }
    updateExperience(); updateControls();
  }
  $('newChat').addEventListener('click', () => resetConversation(true));

  function addMessage(role, text, result) {
    const box = $('messages'); box.querySelector('.empty-hint')?.remove();
    const el = document.createElement('div'); el.className = `msg ${role}${result && result.error ? ' error' : ''}`;
    el.textContent = text;
    if (result && result.imageThumb) { const img = document.createElement('img'); img.className = 'msg-img'; img.src = result.imageThumb; el.appendChild(img); }
    if (result && result.latency_s) { const meta = document.createElement('span'); meta.className = 'msg-meta'; meta.textContent = t('run_info', result); el.appendChild(meta); }
    box.appendChild(el); box.scrollTop = box.scrollHeight;
    return el;
  }

  // image attach
  $('imageInput').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    state.loadingImage = true; updateControls();
    try { validateImage(file); attachImage(await fileToDataURL(file), 'upload'); }
    catch (err) { addMessage('assistant', t('image_error') + err.message, { error: true }); }
    finally { state.loadingImage = false; updateControls(); }
  });
  $('imageRemove').addEventListener('click', () => { state.image = null; state.imageKind = null; $('imagePreview').classList.add('hidden'); $('imageInput').value = ''; updateExperience(); });
  $('sampleDrawing').addEventListener('click', () => attachSample());
  async function attachSample() {
    const s = state.scenario; if (!s || !s.sample_image) return false;
    state.loadingImage = true; updateControls();
    try {
      const res = await fetch(s.sample_image);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob(); validateImage(blob);
      attachImage(await fileToDataURL(blob), 'sample'); return true;
    }
    catch (e) { addMessage('assistant', t('image_error') + e.message, { error: true }); return false; }
    finally { state.loadingImage = false; updateControls(); }
  }
  function validateImage(blob) {
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(blob.type) || blob.size > 8 * 1024 * 1024) throw new Error(t('image_invalid'));
  }
  function attachImage(dataUrl, kind) { state.image = dataUrl; state.imageKind = kind; $('imageThumb').src = dataUrl; $('imageThumb').alt = t(`image_${kind}`); $('imagePreview').classList.remove('hidden'); updateExperience(); }
  function fileToDataURL(blob) { return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(blob); }); }

  // ---------------------------------------------------------------- 轨 D: concept studio (text → concept image → attach to GPT-6)
  function updateConceptStudio() {
    const providers = (state.me && state.me.concept_providers) || [];
    $('conceptStudio').classList.toggle('hidden', !providers.length);
    const sel = $('conceptProvider'); const cur = sel.value; sel.innerHTML = '';
    for (const p of providers) { const o = document.createElement('option'); o.value = p; o.textContent = t(p === 'mai' ? 'provider_mai' : 'provider_gpt'); sel.appendChild(o); }
    if (providers.includes(cur)) sel.value = cur;
    document.querySelector('.concept-grounding').classList.toggle('hidden', sel.value !== 'mai');
  }
  $('conceptProvider').addEventListener('change', () => document.querySelector('.concept-grounding').classList.toggle('hidden', $('conceptProvider').value !== 'mai'));
  function showConcept(i) {
    const c = state.concepts[i]; if (!c) return;
    state.conceptIndex = i;
    $('conceptImg').src = c.image; $('conceptCaption').textContent = t('concept_caption', c, i + 1);
    $('conceptDl').href = c.image; $('conceptDl').download = `concept-${i + 1}.png`;
    $('conceptResult').classList.remove('hidden');
    const h = $('conceptHistory'); h.innerHTML = '';
    state.concepts.forEach((x, k) => { const b = document.createElement('button'); b.type = 'button'; b.className = k === i ? 'active' : ''; b.title = t('concept_caption', x, k + 1); const img = document.createElement('img'); img.src = x.image; img.alt = ''; b.appendChild(img); b.addEventListener('click', () => showConcept(k)); h.appendChild(b); });
  }
  async function runConcept(prompt, editing) {
    if (state.conceptBusy || !prompt) return;
    // Edits follow the provider that drew the current concept when it supports image→image (MAI-Image-2.6 does), else gpt-image.
    const current = editing ? state.concepts[state.conceptIndex] : null;
    const provider = editing ? ((current && current.provider === 'mai' && state.me && state.me.mai_edits) ? 'mai' : 'gpt-image') : $('conceptProvider').value;
    if (provider === 'gpt-image' && !connectionReady()) return;
    state.conceptBusy = true; $('conceptGo').disabled = true; $('conceptEditGo').disabled = true;
    const log = $('conceptProgressLog'); log.textContent = ''; $('conceptProgress').classList.remove('hidden', 'failed'); $('conceptProgressTitle').textContent = t('concept_progress');
    const t0 = performance.now(); let waitLine = null;
    const logLine = (text, err) => { const d = document.createElement('div'); if (err) d.className = 'err'; d.textContent = `[${((performance.now() - t0) / 1000).toFixed(1)}s] ${text}`; log.appendChild(d); log.scrollTop = log.scrollHeight; return d; };
    try {
      const body = { prompt, provider, web_grounding: provider === 'mai' && $('conceptGrounding').value === '1', size: $('conceptSize').value, quality: $('conceptQuality').value, lang: state.lang,
        image: editing && state.concepts[state.conceptIndex] ? state.concepts[state.conceptIndex].image : undefined };
      const res = await fetch('/api/concept', { method: 'POST', headers: { 'Content-Type': 'application/json', ...connHeaders() }, body: JSON.stringify(body) });
      if (res.status === 401) { showAuth(); throw new Error('unauthorized'); }
      if (!res.ok) throw await httpError(res);
      const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = ''; let done = null;
      for (;;) {
        const { value, done: eof } = await reader.read(); if (eof) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, idx); buf = buf.slice(idx + 2);
          const ev = parseSSE(block); if (!ev) continue; const d = ev.data;
          if (ev.event === 'start') logLine(t('concept_started', d) + (d.provider === 'gpt-image' ? t('key_source', d.key_source, d.endpoint_host || '') : ''));
          else if (ev.event === 'heartbeat') { const text = `[${((performance.now() - t0) / 1000).toFixed(1)}s] ${t('concept_hb', d.t)}`; if (waitLine) waitLine.textContent = text; else waitLine = logLine(t('concept_hb', d.t)); }
          else if (ev.event === 'done') done = d;
          else if (ev.event === 'error') throw new Error(d.message);
        }
      }
      if (!done || !done.ok || !done.image) throw new Error('stream ended without result');
      state.concepts.push(done); showConcept(state.concepts.length - 1);
      logLine(t('concept_done', done)); $('conceptProgress').classList.add('hidden');
      if (editing) $('conceptEdit').value = '';
    } catch (err) {
      logLine(err.message, true); $('conceptProgress').classList.add('failed'); addMessage('assistant', t('concept_err') + err.message, { error: true });
    } finally { state.conceptBusy = false; $('conceptGo').disabled = false; $('conceptEditGo').disabled = false; }
  }
  $('conceptForm').addEventListener('submit', (e) => { e.preventDefault(); runConcept($('conceptPrompt').value.trim(), false); });
  $('conceptEditGo').addEventListener('click', () => runConcept($('conceptEdit').value.trim(), true));
  $('conceptUse').addEventListener('click', () => {
    const c = state.concepts[state.conceptIndex]; if (!c) return;
    // The concept becomes the "drawing" for GPT-6 (same path as an uploaded photo); the user adds the key dimensions.
    attachImage(c.image, 'concept');
    const p = $('prompt'); if (!p.value.trim() || isScenarioPrompt(state.scenario, p.value.trim())) p.value = t('concept_use_prompt');
    p.focus(); p.setSelectionRange(p.value.length, p.value.length);
    addMessage('assistant', t('concept_use_msg'));
  });

  // ---------------------------------------------------------------- generate (SSE over fetch)
  // Output contract order: SUMMARY → HTML → METRICS → SUGGESTIONS → END. The HTML block dominates
  // (~8–10k chars of a ~10–12k char answer), so progress is estimated from characters written.
  const EXPECTED_CHARS = 11000;
  function currentStage(raw) {
    if (!raw) return 'stage_wait';
    if (raw.includes('<<<END>>>')) return 'stage_finish';
    if (raw.includes('<<<SUGGESTIONS>>>')) return 'stage_suggestions';
    if (raw.includes('<<<METRICS>>>')) return 'stage_metrics';
    if (raw.includes('<<<HTML>>>')) return 'stage_html';
    return 'stage_summary';
  }
  function estimateProgress(raw) {
    if (!raw) return 2;
    if (raw.includes('<<<END>>>')) return 100;
    if (raw.includes('<<<SUGGESTIONS>>>')) return 96;
    if (raw.includes('<<<METRICS>>>')) return 90;
    const htmlAt = raw.indexOf('<<<HTML>>>');
    if (htmlAt < 0) return 4;
    // typical body: ~9k chars of HTML; </html> means the block is essentially complete
    if (/<\/html>/i.test(raw)) return 88;
    return Math.min(86, 6 + (raw.length - htmlAt) / 9000 * 80);
  }
  const typicalLatency = () => {
    // The measured "last generation" is only a good predictor for the same reasoning effort; otherwise use the guidance table.
    const v = parseFloat($('statLatency').textContent);
    if (v && v > 20 && state.lastLatencyEffort === state.effort) return `${Math.round(v / 10) * 10} s`;
    const table = t('effort_eta');
    return (table && table[state.effort]) || (state.lang === 'zh' ? '2 分钟' : '2 min');
  };
  function tailLines(raw) { const n = raw.split('\n').length; return `${n} ${t('lines')}`; }

  $('composer').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (state.generating || state.loadingImage) return;
    if (!connectionReady()) return;
    const prompt = $('prompt').value.trim();
    if (!prompt && !state.image) { addMessage('assistant', t('enter_prompt'), { error: true }); return; }
    const s = state.scenario;
    state.selectionVersion += 1; // A late example response must not replace a live result.
    state.requestId = null; state.generationPhase = 'phase_connecting'; state.previewing = false;
    const abort = new AbortController(); state.abort = abort;
    setGenerating(true);
    const t0 = performance.now(); let raw = '';
    const meta = $('progressMeta'), tail = $('progressTail'), streamOut = $('streamOut'), fill = $('progressFill'), bar = $('progressBar'), stageEl = $('progressStage');
    streamOut.textContent = ''; fill.style.width = '2%'; fill.classList.add('pulse'); stageEl.textContent = t('stage_wait');
    const updateMeta = () => {
      const secs = (performance.now() - t0) / 1000;
      meta.textContent = `${secs.toFixed(1)} s · ${raw.length} ${t('chars')} · ${tailLines(raw)} · ${t('eta_hint', typicalLatency())}`;
      const p = estimateProgress(raw); fill.style.width = `${p}%`; bar.setAttribute('aria-valuenow', String(Math.round(p)));
      fill.classList.toggle('pulse', !raw);
      stageEl.textContent = t(currentStage(raw));
    };
    const tick = setInterval(updateMeta, 200);
    let history = null;
    try {
      const iterateExample = state.result && state.resultIsCache && !state.history.length && s && !isScenarioPrompt(s, prompt) && !state.image;
      if (s && s.requires_image && !state.image && !state.history.length && !iterateExample) {
        if (s.sample_image) await attachSample();
        if (!state.image) throw new Error(t('need_image'));
      }
      history = [...state.history];
      // Iterating on a saved example: replay its original prompt (in the language it was written in) and its output.
      if (iterateExample) history.push({ role: 'user', content: state.result.prompt || promptFor(s) }, { role: 'assistant', content: state.result.raw });
      const userMsg = { role: 'user', content: prompt, image: state.image || undefined };
      history.push(userMsg);
      const imageNote = state.imageKind ? `\n${t(`image_${state.imageKind}`)}` : '';
      const refImage = state.image || (iterateExample || state.history.length ? state.refImage : null);
      addMessage('user', prompt + imageNote, state.image ? { imageThumb: state.image } : null);
      const requestedEffort = state.effort;
      const res = await fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json', ...connHeaders() }, body: JSON.stringify({ scenario_id: s ? s.id : null, messages: history, lang: state.lang, reasoning_effort: requestedEffort || undefined }), signal: abort.signal });
      if (res.status === 401) { showAuth(); throw new Error('unauthorized'); }
      if (!res.ok) throw await httpError(res);
      const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = ''; let done = null; let lastTailUpdate = 0; let early = null; let liveModel = ''; let liveStart = {};
      for (;;) {
        const { value, done: eof } = await reader.read(); if (eof) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, idx); buf = buf.slice(idx + 2);
          const ev = parseSSE(block); if (!ev) continue;
          if (ev.event === 'start') {
            if (ev.data.source !== 'live' || !ev.data.request_id) throw new Error('Missing live request provenance');
            state.requestId = ev.data.request_id; liveModel = ev.data.model || ''; liveStart = ev.data; updateExperience();
          } else if (ev.event === 'delta') {
            if (!raw) { state.generationPhase = 'phase_streaming'; updateExperience(); }
            raw += ev.data.text; streamOut.textContent = raw;
            if (performance.now() - lastTailUpdate > 120) { tail.textContent = raw.slice(-420); lastTailUpdate = performance.now(); if ($('pane-stream').classList.contains('active')) streamOut.scrollTop = streamOut.scrollHeight; }
          } else if (ev.event === 'html') {
            // Scene code is complete: render it now while metrics/suggestions are still streaming.
            if (ev.data.request_id === state.requestId && ev.data.html && !early) {
              early = ev.data.html;
              state.previewing = true;
              // `model` is the deployment name reported by the server's `start` event — never a literal.
              const preview = { html: early, raw, summary: '', metrics: [], request_id: state.requestId, source: 'live', preview: true,
                model: liveModel, key_source: liveStart.key_source, endpoint_host: liveStart.endpoint_host,
                reasoning_effort: 'reasoning_effort' in ev.data ? ev.data.reasoning_effort : liveStart.reasoning_effort,
                created_at: new Date().toISOString().slice(0, 19) + 'Z', latency_s: ((performance.now() - t0) / 1000).toFixed(1) };
              showResult(preview, false, refImage, { keepProgress: true });
              $('progress').classList.add('progress-mini');
              state.generationPhase = 'early_render'; updateExperience();
            }
          } else if (ev.event === 'done') { done = ev.data; }
          else if (ev.event === 'error') { throw new Error(ev.data.message); }
        }
      }
      if (!done) throw new Error('stream ended without result');
      if (done.source !== 'live' || !state.requestId || done.request_id !== state.requestId) throw new Error('Live response provenance mismatch');
      streamOut.textContent = done.raw || raw;
      if (!done.ok) throw new Error(state.lang === 'zh' ? '模型未返回有效的 HTML 模型，请重试或调整描述。' : 'The model did not return a valid HTML scene. Please retry.');
      state.history = [...history, { role: 'assistant', content: done.raw }];
      state.generationPhase = 'phase_complete'; state.previewing = false;
      // If the early render is already on stage with identical HTML, keep the iframe (no flash).
      // Record the version first so the metrics table can show the change versus the previous version.
      recordTurn(done, false, prompt, refImage);
      showResult(done, false, refImage, { reuseViewer: early === done.html });
      addMessage('assistant', done.summary || '(no summary)', done);
      if (done.suggestions && done.suggestions.length) renderChips(done.suggestions);
      state.count += 1; $('statLatency').textContent = `${done.latency_s}s`; state.lastLatencyEffort = done.reasoning_effort || null;
      followAppliedEffort(requestedEffort, done.reasoning_effort);
      addUsage(done.usage); renderSessionStats();
      $('prompt').value = ''; state.image = null; state.imageKind = null;
      $('imagePreview').classList.add('hidden'); $('imageInput').value = '';
    } catch (err) {
      // An early preview is not a confirmed result (no metrics, no END sentinel): whether the request was
      // cancelled or failed, take it down rather than leave a half-labelled scene on stage.
      const dropPreview = () => {
        state.previewing = false;
        if (state.result && state.result.preview) { state.result = null; state.viewerVersion += 1; clearTimeout(state.renderTimer); $('viewer').removeAttribute('srcdoc'); $('viewerEmpty').classList.remove('hidden'); $('stageBadge').classList.add('hidden'); state.renderState = 'idle'; setRefImage(null); }
      };
      if (err.name === 'AbortError') {
        state.generationPhase = null;
        addMessage('assistant', t('cancelled'), { error: true });
        dropPreview();
      } else {
        state.generationPhase = 'no_fallback';
        addMessage('assistant', t('err_prefix') + err.message, { error: true });
        dropPreview();
      }
    } finally { clearInterval(tick); state.abort = null; $('progress').classList.remove('progress-mini'); setGenerating(false); }
  });
  $('cancelBtn').addEventListener('click', () => { if (state.abort) state.abort.abort(); });
  $('prompt').addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !state.generating) { e.preventDefault(); $('composer').requestSubmit(); } });

  function parseSSE(block) {
    let event = 'message'; const dataLines = [];
    for (const line of block.split('\n')) { if (line.startsWith('event:')) event = line.slice(6).trim(); else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart()); }
    if (!dataLines.length) return null;
    return { event, data: JSON.parse(dataLines.join('\n')) };
  }

  function setGenerating(on) {
    state.generating = on;
    $('progress').classList.toggle('hidden', !on);
    if (on) { $('progressTail').textContent = ''; $('progressMeta').textContent = '0.0 s'; $('viewerEmpty').classList.add('hidden'); switchTab('view'); }
    else $('viewerEmpty').classList.toggle('hidden', !!state.result);
    updateExperience(); updateControls();
  }

  // ---------------------------------------------------------------- result rendering
  function withHelper(html) {
    const bridge = `<script src="${location.origin}/static/viewer-bridge.js?rev=24" data-render-id="${state.viewerVersion}"></script>`;
    // Load before the generated modules so syntax, import and WebGL errors are observable.
    return /<head(?:\s[^>]*)?>/i.test(html) ? html.replace(/<head([^>]*)>/i, `<head$1>${bridge}`) : bridge + html;
  }

  // The viewer iframe is sandboxed (about:srcdoc, opaque origin): root-relative URLs cannot be
  // resolved there, so vendor paths are absolutised against this origin before rendering.
  function absolutize(html) {
    let out = html.replace(/(["'])\s*\/static\/(vendor|studio-kit\.js)/g, `$1${location.origin}/static/$2`);
    if (!/<base\s/i.test(out)) out = out.replace(/<head([^>]*)>/i, `<head$1><base href="${location.origin}/">`);
    return out;
  }

  function showResult(result, isCache, refImage = null, opts = {}) {
    // Keeping the iframe (early render → final result) also keeps the scene-computed metrics it already reported.
    if (opts.reuseViewer && state.result && state.result.live_metrics) result.live_metrics = state.result.live_metrics;
    state.result = result; state.resultIsCache = isCache;
    // A new 轨 A model makes an earlier STEP solid refer to the previous version: keep it, but say so.
    // (Re-showing the same result to switch the geometry source back to the concept mesh is not a new model.)
    if (!opts.reuseViewer && !opts.sameResult && state.cad && !state.cadStale) { state.cadStale = true; setCadBadge('stale'); }
    state.geometry = 'concept';
    if (!opts.reuseViewer) {
      state.viewerVersion += 1; state.renderState = 'loading'; state.viewerCanExportGlb = false;
      state.viewerCanInspect = false; state.workspace = null; updateWorkspace();
      if (state.renders.length) $('renderBase').value = 'snapshot';   // a new 3D version: refine from a fresh snapshot, not an older render
      state.renderStartedAt = performance.now();
      clearInterval(state.renderTick); state.renderTick = setInterval(() => { if (state.renderState !== 'loading') { clearInterval(state.renderTick); return; } updateExperience(); }, 1000);
      resetSystemPanel();
      clearTimeout(state.renderTimer);
      const version = state.viewerVersion;
      // Backstop for a scene that never reports back. While the view pane (another stage tab) or the browser tab
      // is hidden the iframe is 0×0 and cannot draw, so keep waiting instead of reporting a false failure.
      const armRenderTimer = () => {
        state.renderTimer = setTimeout(() => {
          if (state.viewerVersion !== version || state.renderState !== 'loading') return;
          const paneHidden = !$('pane-view').classList.contains('active') || document.visibilityState === 'hidden';
          if (paneHidden) { armRenderTimer(); return; }
          state.renderState = 'failed';
          addMessage('assistant', t('render_error') + 'Viewer readiness timed out', { error: true });
          updateExperience(); updateControls();
        }, 35000);
      };
      armRenderTimer();
      $('viewer').srcdoc = absolutize(withHelper(result.html));
    }
    $('viewerEmpty').classList.add('hidden');
    $('streamOut').textContent = result.raw || result.html;
    $('summaryBox').textContent = result.summary || '';
    if (result.live_metrics && result.live_metrics.length) renderMetrics(result.live_metrics, true);
    else renderMetrics(result.metrics || [], false);
    $('runInfo').textContent = result.latency_s ? t('run_info', result) : '';
    setRefImage(refImage);
    setBadge(isCache); updateExperience(); updateControls(); switchTab('view');
    if (!opts.keepProgress && window.matchMedia('(max-width: 1100px)').matches) $('stage').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  // `live` = numbers computed by the rendered scene itself (window.__metrics via viewer-bridge), which are
  // authoritative over the model's hand-written METRICS block whenever the scene provides them.
  function fillMetricsTable(table, metrics, previous = null) {
    const tb = table.querySelector('tbody'); tb.innerHTML = '';
    const num = (v) => { const m = String(v ?? '').replace(/,/g, '').match(/^-?\d+(\.\d+)?/); return m && !/\//.test(String(v)) ? parseFloat(m[0]) : NaN; };
    for (const m of metrics) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td></td><td class="val"></td><td></td><td class="note"></td>';
      const c = tr.children; c[0].textContent = m.label ?? ''; c[1].textContent = m.value ?? ''; c[2].textContent = m.unit ?? ''; c[3].textContent = m.note ?? '';
      if (previous) {
        // Same label in the previous version → show the change (absolute + %); anything non-numeric shows "—".
        const td = document.createElement('td'); td.className = 'delta';
        const p = previous.find((x) => x.label === m.label); const a = num(m.value), b = p ? num(p.value) : NaN;
        if (p && Number.isFinite(a) && Number.isFinite(b)) {
          const d = a - b; const pct = b !== 0 ? ` (${d >= 0 ? '+' : ''}${(d / Math.abs(b) * 100).toFixed(1)}%)` : '';
          const digits = Math.max((String(m.value).split('.')[1] || '').length, (String(p.value).split('.')[1] || '').length);
          td.textContent = d === 0 ? '＝' : `${d > 0 ? '▲ +' : '▼ '}${d.toFixed(Math.min(digits, 4))}${pct}`;
          td.classList.add(d > 0 ? 'up' : d < 0 ? 'down' : 'same');
        } else td.textContent = p ? '—' : t('m_delta_new');
        tr.appendChild(td);
      }
      tb.appendChild(tr);
    }
  }
  function renderMetrics(metrics, live) {
    const previous = previousTurnMetrics();
    fillMetricsTable($('metricsTable'), metrics, previous && previous.length ? previous : null);
    $('mDeltaHead').classList.toggle('hidden', !(previous && previous.length));
    const src = $('metricsSource');
    src.textContent = metrics.length ? t(live ? 'metrics_live' : 'metrics_text') : '';
    src.classList.toggle('live', !!live && metrics.length > 0);
    state.metricsLive = !!live;
  }
  function addUsage(u) {
    if (!u) return;
    state.tokens.turns += 1; state.tokens.prompt += u.prompt_tokens || 0; state.tokens.completion += u.completion_tokens || 0;
    state.tokens.cached += (u.prompt_tokens_details && u.prompt_tokens_details.cached_tokens) || 0;
  }
  function renderSessionStats() {
    const k = state.tokens; const total = k.prompt + k.completion;
    $('statCount').textContent = k.turns ? `${state.count} · ${fmtInt(total)} tokens` : String(state.count);
    $('statCount').title = k.turns ? `${t('usage_in')} ${fmtInt(k.prompt)} (${t('usage_cached')} ${fmtInt(k.cached)}) · ${t('usage_out')} ${fmtInt(k.completion)} · ${k.turns} ${t('usage_turns')}` : '';
  }
  function setRefImage(src) {
    state.refImage = src || null;
    const img = $('refImageImg');
    if (src) { if (img.getAttribute('src') !== src) img.src = src; }
    else img.removeAttribute('src');
    // visibility + toggle label are derived in updateExperience()
  }
  $('refToggle').addEventListener('click', () => { $('refImage').classList.toggle('collapsed'); updateExperience(); });
  function setBadge(isCache) { const b = $('stageBadge'); b.classList.remove('hidden', 'live', 'cache'); b.classList.add(isCache ? 'cache' : 'live'); b.textContent = isCache ? t('badge_cache') : t('badge_live'); }
  function setExportEnabled(on) {
    ['btnPng', 'btnHtml', 'btnOpen', 'btnFull'].forEach((id) => { $(id).disabled = !on; });
    $('btnGlb').disabled = !on || !state.viewerCanExportGlb;
    updateProposalBtn();
  }

  // ---------------------------------------------------------------- 方案书 (.docx): package the session, GPT-6 writes the narrative
  function updateProposalBtn() {
    const b = $('btnProposal'); if (!b) return;
    b.disabled = state.proposalBusy || state.generating || !state.result || state.previewing;
    b.classList.toggle('busy', !!state.proposalBusy);
    b.textContent = t(state.proposalBusy ? 'btn_proposal_busy' : 'btn_proposal');
  }
  function metricsForProposal(list) {
    return (list || []).slice(0, 12).map((m) => ({ label: String(m.label ?? '').slice(0, 80), value: String(m.value ?? '').slice(0, 40), unit: String(m.unit ?? '').slice(0, 20), note: String(m.note ?? '').slice(0, 120) }));
  }
  function localIso() {
    const d = new Date(), p = (n) => String(n).padStart(2, '0'), off = -d.getTimezoneOffset(), sign = off >= 0 ? '+' : '-';
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}${sign}${p(Math.floor(Math.abs(off) / 60))}:${p(Math.abs(off) % 60)}`;
  }
  async function buildProposal() {
    if (state.proposalBusy || !state.result) return;
    if (!connectionReady()) return;
    state.proposalBusy = true; updateProposalBtn();
    const t0 = performance.now();
    try {
      let snapshot = null;
      if (state.renderState === 'ready') { try { snapshot = (await askViewer('export-png')).url || null; } catch (_) { snapshot = null; } }
      const users = state.history.filter((m) => m.role === 'user' && m.content);
      const requirement = (users.length ? users[users.length - 1].content : $('prompt').value.trim()) || (state.scenario ? promptFor(state.scenario) : t('proposal_untitled'));
      const cur = state.turns[state.turnIndex]; const prev = state.turnIndex > 0 ? state.turns[state.turnIndex - 1] : null;
      const live = state.result.live_metrics && state.result.live_metrics.length ? state.result.live_metrics : state.result.metrics;
      const images = {};
      if (snapshot) images.snapshot = snapshot;
      if (state.renders.length && state.renders[state.renderIndex]) images.render = state.renders[state.renderIndex].image;
      if (state.concepts.length && state.concepts[state.conceptIndex]) images.concept = state.concepts[state.conceptIndex].image;
      if (state.refImage && state.refImage.startsWith('data:image/')) images.drawing = state.refImage;
      const step = {};
      if (state.cad && !state.cadStale) {
        step[t('proposal_step_file')] = `thermal3d-${state.scenario ? state.scenario.id : 'model'}-${state.cad.job_id}.step`.slice(0, 120);
        (state.cad.metrics || []).slice(0, 10).forEach((m) => { step[String(m.label).slice(0, 60)] = `${m.value}${m.unit ? ' ' + m.unit : ''}`.slice(0, 120); });
      }
      const k = state.tokens;
      const body = {
        lang: state.lang, narrative_by_model: true, reasoning_effort: state.effort || undefined,
        title: (state.scenario ? (state.lang === 'en' && state.scenario.title_en ? state.scenario.title_en : state.scenario.title) : t('proposal_untitled')).slice(0, 120),
        requirement: requirement.slice(0, 4000),
        history: users.slice(0, -1).slice(-10).map((m) => m.content.slice(0, 2000)),
        summary: (state.result.summary || '').slice(0, 3000),
        metrics: metricsForProposal(live), previous_metrics: prev && prev.result ? metricsForProposal(prev.result.live_metrics && prev.result.live_metrics.length ? prev.result.live_metrics : prev.result.metrics) : null,
        suggestions: (state.result.suggestions || []).slice(0, 6).map((s) => String(s).slice(0, 200)),
        images, step,
        usage: { input_tokens: k.prompt, output_tokens: k.completion, total_tokens: k.prompt + k.completion, cached_tokens: k.cached, reasoning_tokens: 0, turns: k.turns, elapsed_s: 0 },
        model: (state.me && state.me.deployment) || '', image_model: (state.me && state.me.image_deployment) || '',
        generated_at: localIso(),   // the visitor's wall-clock time (the VM runs on UTC)
      };
      if (cur && cur.result && cur.result.reasoning_tokens) body.usage.reasoning_tokens = cur.result.reasoning_tokens;
      addMessage('assistant', t('proposal_started'));
      const res = await fetch('/api/proposal', { method: 'POST', headers: { 'Content-Type': 'application/json', ...connHeaders() }, body: JSON.stringify(body) });
      if (res.status === 401) { showAuth(); throw new Error('unauthorized'); }
      if (!res.ok) throw await httpError(res);
      const blob = await res.blob();
      const name = ((res.headers.get('content-disposition') || '').match(/filename="([^"]+)"/) || [])[1] || `${fileStem()}.docx`;
      const url = URL.createObjectURL(blob); download(url, name); setTimeout(() => URL.revokeObjectURL(url), 30000);
      const secs = ((performance.now() - t0) / 1000).toFixed(1);
      addMessage('assistant', t('proposal_done', name, secs, res.headers.get('x-proposal-narrative') === 'model', res.headers.get('x-proposal-tokens')));
    } catch (e) {
      addMessage('assistant', t('proposal_err') + e.message, { error: true });
    } finally { state.proposalBusy = false; updateProposalBtn(); }
  }
  $('btnProposal').addEventListener('click', buildProposal);

  // tabs
  document.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.tab)));
  function switchTab(name) {
    document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.tab-pane').forEach((p) => p.classList.toggle('active', p.id === `pane-${name}`));
    if (name === 'stream') { const so = $('streamOut'); so.scrollTop = so.scrollHeight; }
  }

  // ---------------------------------------------------------------- export
  function fileStem() { const s = state.scenario ? state.scenario.id : 'model'; return `thermal3d-${s}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '')}`; }
  function download(url, name) { const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); }
  function askViewer(type) {
    return new Promise((resolve, reject) => {
      if (state.exportWaiter) { reject(new Error('Another export is in progress')); return; }
      state.exportWaiter = { resolve, reject, renderId: String(state.viewerVersion), timer: setTimeout(() => { state.exportWaiter = null; reject(new Error('export timeout')); }, 15000) };
      $('viewer').contentWindow.postMessage({ type, renderId: String(state.viewerVersion) }, '*');
    });
  }
  window.addEventListener('message', (ev) => {
    const d = ev.data || {};
    if (ev.source !== $('viewer').contentWindow || d.renderId !== String(state.viewerVersion)) return;
    if (d.type === 'workspace-state') { state.workspace = d; updateWorkspace(); return; }
    if (d.type === 'workspace-error') {
      $('viewStatus').textContent = d.message; $('viewStatus').dataset.error = 'true';
      addMessage('assistant', d.message, { error: true }); return;
    }
    if (d.type === 'render-ready' || d.type === 'render-error') {
      clearTimeout(state.renderTimer);
      // A late render-ready (e.g. the host timer fired while the studio-kit retrofit was still importing) still wins:
      // drop the timeout message so the conversation does not show a failure next to a working model.
      if (d.type === 'render-ready' && state.renderState === 'failed') document.querySelectorAll('.msg.assistant.error').forEach(el => { if (el.textContent.includes('Viewer readiness timed out')) el.remove(); });
      state.renderState = d.type === 'render-ready' ? 'ready' : 'failed';
      state.viewerCanExportGlb = d.type === 'render-ready' && d.canExportGlb === true;
      state.viewerCanInspect = d.type === 'render-ready' && d.canInspect === true;
      if (d.type === 'render-error') addMessage('assistant', t('render_error') + d.message, { error: true });
      else if (Array.isArray(d.metrics) && d.metrics.length && state.result) {
        // The B-rep viewer reports per-part OCCT masses: show them, but do not overwrite the concept result's own live metrics.
        if (state.geometry === 'concept') state.result.live_metrics = d.metrics;
        renderMetrics(d.metrics, true);
      }
      if (d.type === 'render-ready') {
        // A scene can draw correctly without publishing the globals contract: say what degrades, not "failed".
        if (d.degraded) addMessage('assistant', t('render_degraded', d.missing || ''));
        // System scenes report their component hotspots and operating stages: show the index + stage strip.
        state.system.hotspots = Array.isArray(d.hotspots) ? d.hotspots : [];
        state.system.stages = Array.isArray(d.stages) ? d.stages : [];
        state.system.stage = state.system.stages.length ? 0 : -1; state.system.focus = null;
        renderSystemPanel();
        if (state.viewerCanInspect && (state.geometry === 'brep' || state.scenario?.kind !== 'system')) requestWorkspace({ layout: 'single' });
      }
      updateWorkspace();
      updateExperience(); updateControls(); return;
    }
    if (d.type === 'stage') { if (Number.isInteger(d.index) && d.index !== state.system.stage) { state.system.stage = d.index; renderSystemPanel(); } return; }
    if (d.type === 'scene-error') { addMessage('assistant', t('render_error') + d.message, { error: true }); return; }
    const w = state.exportWaiter; if (!w || w.renderId !== d.renderId) return;
    if (d.type === 'png' || d.type === 'glb') { clearTimeout(w.timer); state.exportWaiter = null; w.resolve(d); }
    else if (d.type === 'export-error') { clearTimeout(w.timer); state.exportWaiter = null; w.reject(new Error(d.message)); }
  });
  $('btnPng').addEventListener('click', async () => { try { const d = await askViewer('export-png'); if (!d.url) throw new Error(t('export_empty')); download(d.url, `${fileStem()}.png`); } catch (e) { addMessage('assistant', `PNG: ${e.message}`, { error: true }); } });
  $('btnGlb').addEventListener('click', async () => {
    try { const d = await askViewer('export-glb'); const url = URL.createObjectURL(new Blob([d.buffer], { type: 'model/gltf-binary' })); download(url, `${fileStem()}.glb`); setTimeout(() => URL.revokeObjectURL(url), 5000); }
    catch (e) { addMessage('assistant', `GLB: ${e.message}`, { error: true }); }
  });
  $('btnHtml').addEventListener('click', () => { if (!state.result) return; const url = URL.createObjectURL(new Blob([absolutize(state.result.html)], { type: 'text/html' })); download(url, `${fileStem()}.html`); setTimeout(() => URL.revokeObjectURL(url), 5000); });
  $('btnOpen').addEventListener('click', () => {
    if (!state.result) return;
    const w = window.open('', '_blank');
    if (!w) { addMessage('assistant', 'Popup blocked', { error: true }); return; }
    w.opener = null;
    const frame = w.document.createElement('iframe');
    frame.setAttribute('sandbox', 'allow-scripts allow-downloads');
    frame.title = '3D viewer'; frame.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;border:0';
    frame.srcdoc = absolutize(state.result.html); w.document.body.appendChild(frame);
  });

  $('btnFull').addEventListener('click', () => { document.querySelector('.stage').classList.toggle('fullscreen'); updateFullBtn(); });
  function updateFullBtn() { $('btnFull').textContent = document.querySelector('.stage').classList.contains('fullscreen') ? t('btn_exit_full') : t('btn_full'); }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && document.querySelector('.stage').classList.contains('fullscreen')) { document.querySelector('.stage').classList.remove('fullscreen'); updateFullBtn(); } });

  // ---------------------------------------------------------------- 轨 B: CadQuery → STEP
  function setCadBadge(kind) {
    applyRenderCad();   // every CAD state change passes here: the render tab's 工程渲染图 switch depends on a current B-rep
    const b = $('cadBadge'); b.classList.remove('hidden', 'live', 'cache', 'error');
    if (!kind) { b.classList.add('hidden'); return; }
    b.classList.add(kind === 'ok' ? 'live' : kind === 'stale' || kind === 'cached' ? 'cache' : 'error');
    b.textContent = t(kind === 'ok' ? 'cad_badge_ok' : kind === 'stale' ? 'cad_badge_stale' : kind === 'cached' ? 'cad_badge_cached' : 'cad_badge_fail');
  }
  function resetCad() {
    if (state.cadAbort) state.cadAbort.abort();
    state.cad = null; state.cadStale = false; state.cadViewerVersion += 1; state.brepBuffer = null; state.geometry = 'concept';
    $('cadViewer').removeAttribute('srcdoc');
    $('cadResult').classList.add('hidden'); $('cadProgress').classList.add('hidden'); $('cadProgress').classList.remove('failed');
    $('cadEmpty').classList.remove('hidden'); $('cadProgressLog').textContent = ''; $('cadCode').classList.add('hidden');
    setCadBadge(null);
    if ($('tabCad').classList.contains('active')) switchTab('view');
  }
  function renderCad(r) {
    $('cadEmpty').classList.add('hidden'); $('cadResult').classList.remove('hidden');
    $('cadSummary').textContent = r.summary || '';
    fillMetricsTable($('cadMetrics'), r.metrics || []);
    const stem = `thermal3d-${state.scenario ? state.scenario.id : 'model'}-${r.job_id}`;
    for (const [id, href, name] of [['cadDlStep', r.files.step, `${stem}.step`], ['cadDlStl', r.files.stl, `${stem}.stl`], ['cadDlPy', r.files.py, `${stem}.py`]]) {
      const a = $(id); a.href = href; a.download = name;
    }
    const cached = r.source === 'pre_generated';
    $('cadRunInfo').textContent = t(cached ? 'cad_run_info_cached' : 'cad_run_info', r);
    $('cadCode').textContent = r.code || '';
    $('cadShowCode').textContent = t($('cadCode').classList.contains('hidden') ? 'cad_show_code' : 'cad_hide_code');
    setCadBadge(state.cadStale ? 'stale' : cached ? 'cached' : 'ok');
  }
  // Pre-generated 轨 B result of a scenario (cad_cache/<id>/ on the server, built from the OCCT-verified reference script):
  // same shape as a live `done`, same rendering path, provenance shown as pre-generated everywhere.
  async function showCachedCad(s, version) {
    try {
      const cad = await api(`/api/cad/cache/${encodeURIComponent(s.id)}?lang=${state.lang}`);
      if (version !== state.selectionVersion || state.generating || state.cadBusy) return;
      state.cad = cad; state.cadStale = false; state.brepBuffer = null;
      renderCad(cad);
      addMessage('assistant', t('cad_cached_msg', cad), { model: cad.model, created_at: cad.created_at });
      await previewStl(cad).catch((e) => addMessage('assistant', t('cad_preview_fail') + e.message, { error: true }));
      if (version !== state.selectionVersion) return;
      if (cad.files.glb) await showBrep(cad);
    } catch (err) {
      if (version !== state.selectionVersion) return;
      addMessage('assistant', t('cad_cache_error') + err.message, { error: true });
    }
  }
  $('cadShowCode').addEventListener('click', () => { const c = $('cadCode'); c.classList.toggle('hidden'); $('cadShowCode').textContent = t(c.classList.contains('hidden') ? 'cad_show_code' : 'cad_hide_code'); });

  // The STL is served by an authenticated endpoint, so the (opaque-origin) sandboxed viewer cannot fetch it
  // itself: the parent fetches the bytes and hands them over with postMessage once the viewer reports ready.
  function stlViewerHtml(renderId) {
    const o = location.origin;
    return `<!doctype html><html><head><meta charset="utf-8">
<script type="importmap">{"imports":{"three":"${o}/static/vendor/three/three.module.js","three/addons/":"${o}/static/vendor/three/jsm/"}}</script>
<style>html,body{margin:0;height:100%;background:#f7f4ef;overflow:hidden}canvas{display:block}#msg{position:absolute;inset:0;display:grid;place-content:center;font:12px system-ui,sans-serif;color:#6f6f6f}</style>
<script>window.addEventListener('error',function(e){parent.postMessage({type:'stl-error',renderId:'${renderId}',message:String(e.message||'script error')},'*');});</script>
</head><body><div id="msg">loading STL…</div>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
const RID = '${renderId}';
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping; document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color('#f7f4ef');
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
const camera = new THREE.PerspectiveCamera(38, innerWidth / innerHeight, 0.1, 5000);
const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.autoRotate = true; controls.autoRotateSpeed = 1.1;
scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 0.5));
const sun = new THREE.DirectionalLight(0xffffff, 1.2); sun.position.set(1, 2, 1.5); scene.add(sun);
function show(buffer) {
  const geo = new STLLoader().parse(buffer); geo.computeVertexNormals(); geo.computeBoundingBox();
  const size = new THREE.Vector3(), center = new THREE.Vector3(); geo.boundingBox.getSize(size); geo.boundingBox.getCenter(center);
  const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: '#d4d9e0', metalness: 0.55, roughness: 0.35 }));
  mesh.position.copy(center).multiplyScalar(-1);
  const group = new THREE.Group(); group.add(mesh); group.rotation.x = -Math.PI / 2; scene.add(group); // CadQuery Z-up → three.js Y-up
  const r = size.length() / 2;
  const grid = new THREE.GridHelper(r * 3, 24, 0xc9c4bb, 0xe6e1d8); grid.position.y = -size.z / 2 - r * 0.02; scene.add(grid);
  camera.position.set(r * 1.7, r * 1.15, r * 1.7); camera.near = r / 200; camera.far = r * 40; camera.updateProjectionMatrix(); controls.target.set(0, 0, 0);
  document.getElementById('msg').remove();
  parent.postMessage({ type: 'stl-ready', renderId: RID, triangles: geo.attributes.position.count / 3 }, '*');
}
addEventListener('message', (e) => {
  if (!e.data || e.data.type !== 'stl' || !e.data.buffer) return;
  try { show(e.data.buffer); } catch (err) { parent.postMessage({ type: 'stl-error', renderId: RID, message: String((err && err.message) || err) }, '*'); }
});
addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
parent.postMessage({ type: 'stl-viewer-ready', renderId: RID }, '*');
</script></body></html>`;
  }
  async function previewStl(cad) {
    const frame = $('cadViewer');
    const version = ++state.cadViewerVersion; const rid = `cad-${version}`;
    const res = await fetch(cad.files.stl);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const buffer = await res.arrayBuffer();
    if (state.cadViewerVersion !== version) return null;
    return new Promise((resolve, reject) => {
      // A newer preview replaced this viewer (e.g. the industry tab auto-selected a scenario, then a card was clicked): settle quietly.
      const timer = setTimeout(() => { cleanup(); if (state.cadViewerVersion !== version) resolve(null); else reject(new Error('viewer timeout')); }, 25000);
      const cleanup = () => { clearTimeout(timer); window.removeEventListener('message', onMsg); };
      const onMsg = (ev) => {
        if (ev.source !== frame.contentWindow || !ev.data || ev.data.renderId !== rid) return;
        if (ev.data.type === 'stl-viewer-ready') frame.contentWindow.postMessage({ type: 'stl', buffer }, '*', [buffer]);
        else if (ev.data.type === 'stl-ready') { cleanup(); resolve(ev.data); }
        else if (ev.data.type === 'stl-error') { cleanup(); reject(new Error(ev.data.message)); }
      };
      window.addEventListener('message', onMsg);
      frame.srcdoc = stlViewerHtml(rid);
    });
  }

  $('btnStep').addEventListener('click', async () => {
    if (state.cadBusy || !state.cadAvailable || state.generating) return;
    if (!connectionReady()) return;
    const r = state.result;
    if (!r || r.preview) { addMessage('assistant', t('cad_no_result'), { error: true }); return; }
    const lastUser = [...state.history].reverse().find((m) => m.role === 'user');
    // Saved example → its own original prompt; otherwise the scenario prompt in the UI language.
    const prompt = (lastUser && lastUser.content) || (state.resultIsCache && r.prompt) || (state.scenario && promptFor(state.scenario)) || $('prompt').value.trim();
    const body = { scenario_id: state.scenario ? state.scenario.id : null, prompt, summary: r.summary || '', html: r.html || '', request_id: r.request_id || null, lang: state.lang, reasoning_effort: state.effort || undefined };
    const abort = new AbortController(); state.cadAbort = abort; state.cadBusy = true;
    const log = $('cadProgressLog'); log.textContent = '';
    $('cadEmpty').classList.add('hidden'); $('cadResult').classList.add('hidden');
    $('cadProgress').classList.remove('hidden', 'failed'); $('cadProgressTitle').textContent = t('cad_progress_title');
    setCadBadge(null); switchTab('cad'); updateControls();
    const t0 = performance.now(); let max = 3;
    const logLine = (text, err) => { const d = document.createElement('div'); if (err) d.className = 'err'; d.textContent = `[${((performance.now() - t0) / 1000).toFixed(1)}s] ${text}`; log.appendChild(d); log.scrollTop = log.scrollHeight; return d; };
    // Server heartbeats (every ~15 s while GPT-6 / OCCT are silent) update one "still working" line instead of spamming the log.
    let waitLine = null;
    const noteHeartbeat = (d) => {
      const text = `[${((performance.now() - t0) / 1000).toFixed(1)}s] ${t(d.phase === 'occt' ? 'cad_hb_occt' : 'cad_hb_model', d.t)}`;
      if (waitLine && waitLine.parentNode) waitLine.textContent = text; else waitLine = logLine(text.replace(/^\[[^\]]*\]\s*/, ''));
      log.scrollTop = log.scrollHeight;
    };
    try {
      const res = await fetch('/api/cad', { method: 'POST', headers: { 'Content-Type': 'application/json', ...connHeaders() }, body: JSON.stringify(body), signal: abort.signal });
      if (res.status === 401) { showAuth(); throw new Error('unauthorized'); }
      if (!res.ok) throw await httpError(res);
      const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = ''; let done = null;
      for (;;) {
        const { value, done: eof } = await reader.read(); if (eof) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, idx); buf = buf.slice(idx + 2);
          const ev = parseSSE(block); if (!ev) continue;
          const d = ev.data;
          if (ev.event === 'start') { max = d.max_attempts || max; logLine(t('cad_started') + d.job_id); }
          else if (ev.event === 'attempt') { waitLine = null; logLine(d.phase === 'model' ? t('cad_ph_model', d.n, max) : t('cad_ph_occt', d.n, max, d.code_lines)); }
          else if (ev.event === 'heartbeat') noteHeartbeat(d);
          else if (ev.event === 'attempt_failed') { waitLine = null; logLine(t('cad_ph_failed', d.n), true); logLine((d.error || '').trim().split('\n').slice(-6).join('\n'), true); }
          else if (ev.event === 'done') done = d;
          else if (ev.event === 'error') throw new Error(d.message);
        }
      }
      if (!done || !done.ok || !done.files) throw new Error('stream ended without result');
      if (state.cadAbort !== abort) return; // reset happened meanwhile
      state.cad = done; state.cadStale = false; state.brepBuffer = null;
      followAppliedEffort(body.reasoning_effort, done.reasoning_effort);
      logLine(t('cad_done', done));
      renderCad(done); $('cadProgress').classList.add('hidden');
      addMessage('assistant', t('cad_msg', done), { latency_s: done.latency_s, model: done.model, created_at: done.created_at, usage: done.usage });
      // (The "last generation" tile and its ETA hint describe 轨 A only — a STEP job must not overwrite them.)
      await previewStl(done).catch((e) => addMessage('assistant', t('cad_preview_fail') + e.message, { error: true }));
      // The solid is the higher-fidelity geometry: make it the main viewport (quad view / section / export all apply).
      if (done.files.glb) { switchTab('view'); await showBrep(done); }
    } catch (err) {
      if (err.name === 'AbortError') { logLine(t('cancelled'), true); }
      else { logLine(err.message, true); $('cadProgress').classList.add('failed'); setCadBadge('fail'); addMessage('assistant', t('cad_err') + err.message, { error: true }); }
    } finally { if (state.cadAbort === abort) state.cadAbort = null; state.cadBusy = false; updateControls(); }
  });

  // ---------------------------------------------------------------- 轨 C: photoreal render (gpt-image edit of the WebGL snapshot)
  function updateRenderBtn() {
    const on = !!(state.me && state.me.image_deployment);
    // A preset example showing its pre-generated render is display-only: no live gpt-image call from this tab.
    const preset = state.resultIsCache && state.renders[state.renderIndex]?.source === 'pre_generated';
    $('btnRender').classList.toggle('hidden', !on || preset); $('tabRender').classList.toggle('hidden', !on);
    $('renderForm').classList.toggle('hidden', preset);
    $('btnRender').disabled = !on || state.renderBusy || state.generating || !state.result || state.previewing || state.renderState !== 'ready';
    $('btnRender').classList.toggle('busy', !!state.renderBusy);
    $('btnRender').textContent = t(state.renderBusy ? 'btn_render_busy' : 'btn_render');
    $('renderGo').disabled = $('btnRender').disabled;
  }
  function setRenderBadge(kind) { const b = $('renderBadge'); b.classList.remove('hidden', 'live', 'cache'); if (!kind) { b.classList.add('hidden'); return; } b.classList.add(kind === 'cached' ? 'cache' : 'live'); b.textContent = t(kind === 'ok' ? 'render_badge_ok' : kind === 'cached' ? 'render_badge_cached' : 'render_badge_fail'); }
  function resetRenders() { state.renders = []; state.renderIndex = -1; state.renderBusy = false; if (state.renderAbort) state.renderAbort.abort(); state.renderAbort = null; $('renderResult').classList.add('hidden'); $('renderProgress').classList.add('hidden'); $('renderEmpty').classList.remove('hidden'); $('renderHistory').innerHTML = ''; setRenderBadge(null); updateRenderBtn(); }
  function showRender(i) {
    const r = state.renders[i]; if (!r) return;
    state.renderIndex = i;
    $('renderPrompt').textContent = r.prompt_used || '';
    showRenderView();
    $('renderEmpty').classList.add('hidden'); $('renderResult').classList.remove('hidden');
    const h = $('renderHistory'); h.innerHTML = '';
    state.renders.forEach((x, k) => { const b = document.createElement('button'); b.type = 'button'; b.className = k === i ? 'active' : ''; b.title = t('render_caption', x, k + 1); const img = document.createElement('img'); img.src = x.image; img.alt = ''; b.appendChild(img); b.addEventListener('click', () => showRender(k)); h.appendChild(b); });
  }
  // Pre-generated 轨 C render of a scenario (render_cache/<id>/ on the server, made by pregen_render.py through this same render
  // path): shown with pre-generated provenance instead of a live render.
  async function showCachedRender(s, version) {
    try {
      const r = await api(`/api/render/cache/${encodeURIComponent(s.id)}`);
      if (version !== state.selectionVersion || state.generating || state.renderBusy || state.renders.length) return;
      state.renders.push(r); showRender(0); setRenderBadge('cached'); updateRenderBtn();
      addMessage('assistant', t('render_cached_msg', r), { model: r.model, created_at: r.created_at, imageThumb: r.image });
    } catch (err) {
      if (version !== state.selectionVersion) return;
      addMessage('assistant', t('render_cache_error') + err.message, { error: true });
    }
  }
  // 渲染图 vs CAD. Pre-generated renders carry a cad_overlay (STEP lines fitted offline onto the gpt-image picture) and an
  // engineering render (the STEP geometry rendered with the same camera, so its lines need no fit). For a live result the
  // engineering render is made in this browser from the current B-rep on first use (engineering-render.html), kept per CAD job.
  function brepCurrent() { return !!(state.cad && !state.cadStale && state.cad.files && state.cad.files.glb); }
  function currentEngineering() {
    const r = state.renders[state.renderIndex];
    if (r && r.engineering) return r.engineering;
    return brepCurrent() && state.engLive && state.engLive.job === state.cad.job_id ? state.engLive.data : null;
  }
  function engineeringOffered() { const r = state.renders[state.renderIndex]; return !!(r && (r.engineering || brepCurrent())); }
  function renderView() { return state.renderView === 'eng' && currentEngineering() ? 'eng' : 'gpt'; }
  function showRenderView() {
    const r = state.renders[state.renderIndex]; if (!r) return;
    const eng = renderView() === 'eng', e = currentEngineering();
    const image = eng ? e.image : r.image, lines = eng ? e.lines : r.cad_overlay && r.cad_overlay.lines;
    $('renderImg').src = image;
    if (lines) $('renderCadLines').src = lines; else $('renderCadLines').removeAttribute('src');
    $('renderDl').href = image; $('renderDl').download = `${fileStem()}-${eng ? 'engineering' : 'render'}-${state.renderIndex + 1}.png`;
    if (eng) { $('renderPrompt').classList.add('hidden'); $('renderShowPrompt').textContent = t('render_show_prompt'); }
    applyRenderCad();
  }
  function applyRenderCad() {
    const r = state.renders[state.renderIndex], view = renderView(), e = currentEngineering();
    const o = r && (view === 'eng' ? e : r.cad_overlay);
    const on = !!(o && o.lines && state.renderCadOn);
    $('renderViewSwitch').classList.toggle('hidden', !engineeringOffered());
    document.querySelectorAll('[data-render-view]').forEach(b => { b.setAttribute('aria-pressed', String(b.dataset.renderView === (state.engBusy ? 'eng' : view))); b.disabled = !!state.engBusy; });
    if (r) $('renderCaption').textContent = state.engBusy ? t('render_eng_busy', state.engProgress) : view === 'eng' ? t('render_eng_caption', e) : t('render_caption', r, state.renderIndex + 1);
    $('renderShowPrompt').classList.toggle('hidden', view === 'eng');
    $('renderNote').textContent = t(view === 'eng' ? 'render_note_eng' : 'render_note');
    $('renderCadToggle').classList.toggle('hidden', !(o && o.lines));
    $('renderCadToggle').setAttribute('aria-pressed', String(on));
    $('renderCadLines').classList.toggle('hidden', !on);
    $('renderCadNote').classList.toggle('hidden', !on);
    $('renderCadNote').textContent = on ? t(view === 'eng' ? 'render_eng_cad_note' : 'render_cad_note', o) : '';
  }
  async function renderEngineeringLive() {
    const cad = state.cad, job = cad.job_id;
    state.engBusy = true; state.engProgress = null; applyRenderCad();
    try {
      await loadBrepBuffer(cad);
      const result = await new Promise((resolve, reject) => {
        const frame = document.createElement('iframe');
        frame.className = 'eng-worker'; frame.setAttribute('aria-hidden', 'true'); frame.tabIndex = -1;
        const finish = (err, res) => { clearTimeout(timer); window.removeEventListener('message', onMsg); frame.remove(); if (err) reject(err); else resolve(res); };
        const timer = setTimeout(() => finish(new Error('timeout')), 120000);
        const onMsg = (ev) => {
          if (ev.source !== frame.contentWindow || !ev.data) return;
          const d = ev.data;
          if (d.type === 'eng-ready') frame.contentWindow.postMessage({ type: 'eng-render', buffer: state.brepBuffer.bytes.slice(0), parts: cad.parts || [], width: 2048, height: 1152, spp: 128, maxMs: 30000 }, location.origin);
          else if (d.type === 'eng-progress') { state.engProgress = d; applyRenderCad(); }
          else if (d.type === 'eng-result') finish(null, d.result);
          else if (d.type === 'eng-error') finish(new Error(d.message));
        };
        window.addEventListener('message', onMsg);
        frame.src = '/static/engineering-render.html?rev=2';
        document.body.appendChild(frame);
      });
      if (state.cad && state.cad.job_id === job) state.engLive = { job, data: { ...result, source: 'live_browser' } };
    } catch (err) {
      addMessage('assistant', t('render_eng_fail') + err.message, { error: true });
      state.renderView = 'gpt';
    } finally { state.engBusy = false; state.engProgress = null; }
  }
  async function selectRenderView(v) {
    if (state.engBusy) return;
    state.renderView = v;
    if (v === 'eng' && !currentEngineering() && brepCurrent()) await renderEngineeringLive();
    showRenderView();
  }
  $('renderCadToggle').addEventListener('click', () => { state.renderCadOn = !state.renderCadOn; applyRenderCad(); });
  document.querySelectorAll('[data-render-view]').forEach(b => b.addEventListener('click', () => selectRenderView(b.dataset.renderView)));
  $('renderShowPrompt').addEventListener('click', () => { const p = $('renderPrompt'); p.classList.toggle('hidden'); $('renderShowPrompt').textContent = t(p.classList.contains('hidden') ? 'render_show_prompt' : 'render_hide_prompt'); });
  async function startRender() {
    if (state.renderBusy || state.generating || !state.result || state.previewing) return;
    if (!connectionReady()) return;
    if (state.renderState !== 'ready') { addMessage('assistant', t('render_no_result'), { error: true }); return; }
    const style = $('renderStyle').value, size = $('renderSize').value, quality = $('renderQuality').value, instruction = $('renderInstruction').value.trim();
    let base = $('renderBase').value;
    const abort = new AbortController(); state.renderAbort = abort; state.renderBusy = true; updateRenderBtn();
    const log = $('renderProgressLog'); log.textContent = '';
    $('renderProgress').classList.remove('hidden', 'failed'); $('renderProgressTitle').textContent = t('render_progress'); $('renderEmpty').classList.add('hidden');
    setRenderBadge(null);
    const t0 = performance.now(); let waitLine = null;
    const logLine = (text, err) => { const d = document.createElement('div'); if (err) d.className = 'err'; d.textContent = `[${((performance.now() - t0) / 1000).toFixed(1)}s] ${text}`; log.appendChild(d); log.scrollTop = log.scrollHeight; return d; };
    try {
      let image;
      if (base === 'previous' && state.renders[state.renderIndex]) image = state.renders[state.renderIndex].image;
      else {
        if (base === 'previous') { logLine(t('render_no_previous'), true); base = 'snapshot'; }
        // Capture while the 3D pane is still the visible one; a busy first frame can miss the 15 s window once, so retry once.
        logLine(t('render_snap'));
        let snap;
        try { snap = await askViewer('export-png'); } catch (e) { if (!/timeout/i.test(e.message)) throw e; snap = await askViewer('export-png'); }
        if (!snap.url) throw new Error(t('export_empty')); image = snap.url;
      }
      switchTab('render');
      const body = { scenario_id: state.scenario ? state.scenario.id : null, summary: state.result.summary || '', image, base, style, instruction, size, quality, lang: state.lang };
      const res = await fetch('/api/render', { method: 'POST', headers: { 'Content-Type': 'application/json', ...connHeaders() }, body: JSON.stringify(body), signal: abort.signal });
      if (res.status === 401) { showAuth(); throw new Error('unauthorized'); }
      if (!res.ok) throw await httpError(res);
      const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = ''; let done = null;
      for (;;) {
        const { value, done: eof } = await reader.read(); if (eof) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, idx); buf = buf.slice(idx + 2);
          const ev = parseSSE(block); if (!ev) continue;
          const d = ev.data;
          if (ev.event === 'start') logLine(`${d.model} · ${t('key_source', d.key_source, d.endpoint_host || '')}`);
          else if (ev.event === 'heartbeat') { const text = `[${((performance.now() - t0) / 1000).toFixed(1)}s] ${t('render_hb', d.t)}`; if (waitLine) waitLine.textContent = text; else waitLine = logLine(t('render_hb', d.t)); }
          else if (ev.event === 'done') done = d;
          else if (ev.event === 'error') throw new Error(d.message);
        }
      }
      if (!done || !done.ok || !done.image) throw new Error('stream ended without result');
      if (state.renderAbort !== abort) return;
      state.renders.push(done); showRender(state.renders.length - 1);
      $('renderBase').value = 'previous'; $('renderInstruction').value = '';   // next pass refines this render by default
      logLine(t('render_done', done)); $('renderProgress').classList.add('hidden'); setRenderBadge('ok');
      addMessage('assistant', t('render_msg', done), { latency_s: done.latency_s, model: done.model, created_at: done.created_at, usage: null, imageThumb: done.image });
    } catch (err) {
      if (err.name === 'AbortError') logLine(t('cancelled'), true);
      else { logLine(err.message, true); $('renderProgress').classList.add('failed'); setRenderBadge('fail'); addMessage('assistant', t('render_err') + err.message, { error: true }); }
    } finally { if (state.renderAbort === abort) state.renderAbort = null; state.renderBusy = false; updateRenderBtn(); }
  }
  $('btnRender').addEventListener('click', startRender);
  $('renderForm').addEventListener('submit', (e) => { e.preventDefault(); startRender(); });

  // ---------------------------------------------------------------- draggable borders
  // Sidebar width (column between sidebar and stage) and input box height (bar above the composer). The left column is
  // usually full (conversation at its minimum), so a taller input box takes room from the conversation first, then from
  // the scenario list down to one card; a shorter one gives it back to the list first.
  function initSplitters() {
    const wb = document.querySelector('.workbench'), side = document.querySelector('.sidebar'), prompt = $('prompt'), msgs = $('messages'), list = $('scenarioList');
    const KEYS = { side: 's3d.sideW', prompt: 's3d.promptH', list: 's3d.listH' }, SIDE_MIN = 240, STAGE_MIN = 520, LIST_MIN = 52;
    const PROMPT_MIN = parseFloat(getComputedStyle(prompt).minHeight) || 60, MSGS_MIN = parseFloat(getComputedStyle(msgs).minHeight) || 70;
    const saved = (k) => { try { return Number(localStorage.getItem(k)) || 0; } catch (e) { return 0; } };
    const save = (k, v) => { try { if (v) localStorage.setItem(k, String(Math.round(v))); else localStorage.removeItem(k); } catch (e) { /* private mode */ } };
    let wantSide = saved(KEYS.side); // the width the user chose; re-applied (clamped) whenever the workbench is resized or first shown
    const setSide = (w) => {
      const avail = wb.getBoundingClientRect().width; // 0 while the app view is still hidden behind the sign-in check
      const max = avail ? Math.max(SIDE_MIN, avail - 12 - STAGE_MIN) : Infinity;
      w = Math.min(max, Math.max(SIDE_MIN, w)); wb.style.setProperty('--side-w', `${Math.round(w)}px`); return w;
    };
    const chooseSide = (w) => { wantSide = w; save(KEYS.side, w); };
    const px = (el) => el.getBoundingClientRect().height;
    function composerStart() {
      const cap = list.style.maxHeight;
      list.style.removeProperty('max-height');
      const full = px(list);   // the list's own height (CSS max 180 px)
      list.style.maxHeight = cap;
      const h0 = prompt.offsetHeight, l0 = px(list), hist = Math.max(0, px(msgs) - MSGS_MIN);
      return { h0, l0, full, hist, max: h0 + hist + Math.max(0, l0 - LIST_MIN), h: 0, l: 0 };
    }
    function composerSet(c, h) {
      h = Math.round(Math.min(c.max, Math.max(PROMPT_MIN, h)));
      const d = h - c.h0, l = d >= 0 ? c.l0 - Math.max(0, d - c.hist) : Math.min(c.full, c.l0 - d);
      prompt.style.height = `${h}px`;
      if (l >= c.full - 0.5) list.style.removeProperty('max-height'); else list.style.maxHeight = `${Math.round(l)}px`;
      c.h = h; c.l = l >= c.full - 0.5 ? 0 : Math.round(l);
    }
    const composerSave = (c) => { save(KEYS.prompt, c.h); save(KEYS.list, c.l); };
    function draggable(handle, axis, begin, move, end) {
      handle.addEventListener('pointerdown', (e) => {
        if (e.button !== 0) return;
        e.preventDefault(); handle.setPointerCapture(e.pointerId);
        const ctx = begin(e);
        handle.classList.add('dragging'); document.body.classList.add(`resizing-${axis}`);
        const onMove = (ev) => move(ctx, ev);
        const onUp = () => {
          handle.removeEventListener('pointermove', onMove); handle.removeEventListener('pointerup', onUp); handle.removeEventListener('pointercancel', onUp);
          handle.classList.remove('dragging'); document.body.classList.remove(`resizing-${axis}`); end(ctx);
        };
        handle.addEventListener('pointermove', onMove); handle.addEventListener('pointerup', onUp); handle.addEventListener('pointercancel', onUp);
      });
    }
    draggable($('splitSide'), 'x', (e) => ({ x0: e.clientX, w0: side.getBoundingClientRect().width, w: 0 }),
      (c, ev) => { c.w = setSide(c.w0 + ev.clientX - c.x0); }, (c) => { if (c.w) chooseSide(c.w); });
    draggable($('splitComposer'), 'y', (e) => ({ ...composerStart(), y0: e.clientY }),
      (c, ev) => composerSet(c, c.h0 - (ev.clientY - c.y0)), (c) => { if (c.h) composerSave(c); });
    $('splitSide').addEventListener('keydown', (e) => {
      const d = { ArrowLeft: -16, ArrowRight: 16 }[e.key]; if (!d) return;
      e.preventDefault(); chooseSide(setSide(side.getBoundingClientRect().width + d));
    });
    $('splitComposer').addEventListener('keydown', (e) => {
      const d = { ArrowUp: 16, ArrowDown: -16 }[e.key]; if (!d) return;
      e.preventDefault(); const c = composerStart(); composerSet(c, c.h0 + d); composerSave(c);
    });
    $('splitSide').addEventListener('dblclick', () => { wb.style.removeProperty('--side-w'); chooseSide(0); });
    $('splitComposer').addEventListener('dblclick', () => {
      prompt.style.removeProperty('height'); list.style.removeProperty('max-height'); save(KEYS.prompt, 0); save(KEYS.list, 0);
    });
    if (wantSide) setSide(wantSide);
    if (saved(KEYS.prompt)) prompt.style.height = `${Math.max(PROMPT_MIN, saved(KEYS.prompt))}px`;
    if (saved(KEYS.list)) list.style.maxHeight = `${Math.max(LIST_MIN, saved(KEYS.list))}px`;
    // Re-clamp the chosen width once the app view is shown and whenever the window is resized.
    new ResizeObserver(() => { if (wantSide && wb.getBoundingClientRect().width) setSide(wantSide); }).observe(wb);
  }

  // ---------------------------------------------------------------- init
  initSplitters();
  applyLang();
  // Industry groups are public so the sign-in page can already carry the group's title (e.g. ?industry=notebook).
  fetch('/api/industries').then((r) => (r.ok ? r.json() : null)).then((d) => { if (d) { setIndustries(d.industries); applyLang(); } }).catch(() => {}).finally(boot);
})();
