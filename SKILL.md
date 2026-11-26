---
name: videogen
description: 用户要求生成视频、制作短片、让图片动起来、用视频模型出片或续下载已提交的视频任务时使用。经高新网关完成模型发现、一次提交、查询和本地 MP4 交付。
---

# 视频生成

视频输出统一使用 videogen；单张静态图片交给 imagegen-dual。同一模型 ID 可以出现在两个列表中。

收到视频意图后由助手操作本目录专属环境的 Python 和 scripts/client.py，无需用户运行脚本。网关仅用 main（主站）或 sh（上海），凭证来自本机 GAOXIN_API_KEY。缺少凭证时说明本机配置方法，不询问聊天中的密钥。

1. 复用当前任务中已明确的网关、模型和参数。运行 models --gateway main 或 sh 获取该账户的完整候选。仅向用户推荐 adapter 有值且适合素材的候选。若缺少选择，将网关、实际候选、时长、比例、分辨率合并成一次简短确认；账户不同要先确定来源再查。首选可用问卡，回退为编号文字。用户指定齐全即可执行。仅列出的未映射模型说明缺少网关协议，不替换或试投。
2. 已成形的提示词逐字传入，保留镜头、台词和负面要求。若只有意图，助手自行细化主体、动作、镜头运动、节奏和光线，不要求再确认扩写。引用素材时以用户指定文件为准。FastH3-Omni 需要首帧 PNG/JPEG，缺失时才询问。普通文生视频默认 5 秒、16:9；H3 默认 768P，Seedance 默认 720p。
3. 写入 UTF-8 任务 JSON，包含 gateway、model、prompt，可选 seconds、resolution、ratio、first_frame、output_dir、filename 或完整 output_path。用户只给目录就用 output_dir，只给文件名就用 filename。未指定时直接用当前项目 outputs/video 下的唯一 MP4 文件名。助手在目标项目工作目录执行 generate --job <绝对路径>，持续等待至完成。不要询问保存路径。
4. 保存返回的 record 路径。已提交后断线或下载失败，用 resume --record <路径> 继续查询取回，仅发 GET。提交结果未知且无 ID 时停止并告知用户，避免再次计费。已有 ID 的轮询超时可以继续 resume。交付 saved 对应的实际 MP4，以本机绝对路径内联展示。
