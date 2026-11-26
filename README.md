# 高新视频生成 Skill

将发布包里的 videogen 目录放入 Codex skills 目录，在技能目录运行：

    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt

需要 Python 3.9+。可选用 CCSwitch、Magpie、直接提供 Key 或已有的 GAOXIN_API_KEY。重新打开 Codex 加载技能。可选安装 ffprobe 以验证输出视频流。

示例：“帮我生成一段橘猫在窗边回头的视频”。助手负责发现模型、确认配置、使用或编写提示词、提交任务、查询和保存。默认输出在当前项目 outputs/video 下，任务记录放在输出目录的 .video-tasks 下。

支持 MiniMax-H3 的文生视频、FastH3-Omni 的首帧图生视频，以及 Seedance 兼容协议的文生视频。其他视频候选会标记 adapter 为空，取得网关协议后才能提交。

    python scripts/client.py models --gateway main
    python scripts/client.py generate --job job.json
    python scripts/client.py resume --record <record.json>

job.json 示例：

    {"gateway":"main","model":"MiniMax-H3","prompt":"橘猫缓缓转头","seconds":5,"ratio":"16:9"}

发布前使用模拟网关验收，不代表任何账户的真实出片权限。

## 账户来源

凭证可选 CCSwitch、Magpie 或用户直接交给助手的 BYOK。先列出非敏感来源，用户已选则直接使用。BYOK 将本轮密钥作为单行标准输入传给子进程；勿回显、写入任务 JSON、命令行参数、脚本、记录或持久偏好。后续独立进程需要同一 Key 时，助手从当前已授权上下文再次通过标准输入传入。切勿从历史聊天取密钥或在失败时更换账户。客户端使用 profiles 列出来源，models --profile <ref> 查询模型。任务 JSON 可填写 profile 来源标识。BYOK 使用 byok。
