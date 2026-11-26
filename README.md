# 高新视频生成 Skill

将发布包里的 gaoxin-video 目录放入 Codex skills 目录，在技能目录运行：

    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt

需要 Python 3.9+。在本机配置 GAOXIN_API_KEY，重新打开 Codex。可选安装 ffprobe 以验证输出视频流。

示例：“帮我生成一段橘猫在窗边回头的视频”。助手负责发现模型、确认配置、使用或编写提示词、提交任务、查询和保存。默认输出在当前项目 outputs/video 下，任务记录放在输出目录的 .video-tasks 下。

支持 MiniMax-H3 的文生视频、FastH3-Omni 的首帧图生视频，以及 Seedance 兼容协议的文生视频。其他视频候选会标记 adapter 为空，取得网关协议后才能提交。

    python scripts/client.py models --gateway main
    python scripts/client.py generate --job job.json
    python scripts/client.py resume --record <record.json>

job.json 示例：

    {"gateway":"main","model":"MiniMax-H3","prompt":"橘猫缓缓转头","seconds":5,"ratio":"16:9"}

发布前使用模拟网关验收，不代表任何账户的真实出片权限。
