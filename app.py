import gradio as gr
import time
from pathlib import Path
import os
import torch
import shutil
import re
import sys
import tempfile
import webbrowser
from typing import List
import traceback

# --- 0. 导入 SenseVoice 依赖 (使用 funasr) ---
try:
    from funasr import AutoModel
except ImportError as e:
    print("--- 导入 'funasr' 库时发生错误 ---")
    print(f"错误详情 (ImportError): {e}")
    print("\n请确保你已在 (sensevoice) 环境中，并且已运行 'pip install -r requirements.txt'")
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"--- 加载 'funasr' 时发生未知错误 ---")
    print(f"错误详情: {e}")
    traceback.print_exc()
    sys.exit(1)


# --- 1. 配置 ---
PORT = 7080  # 端口
TEMP_DIR = Path("temp_processing_app") # 临时文件目录
IS_CUDA = torch.cuda.is_available()
MAX_FILES = 10 # UI上最多同时显示10个文件的结果
MODEL_ID = "iic/SenseVoiceSmall" # 使用 Small 模型

# --- 2. 加载模型 (全局只加载一次) ---
print(f"正在加载 {MODEL_ID}...")
print("首次运行会自动从 ModelScope 下载模型，请耐心等待。")
start_load = time.time()
device = "cuda" if IS_CUDA else "cpu"
try:
    # 使用 funasr.AutoModel 加载，就像 webui.py 一样
    pipeline_asr = AutoModel(
        model=MODEL_ID,
        vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch", # VAD模型
        vad_kwargs={"max_single_segment_time": 30000},
        trust_remote_code=True, # 允许加载 model.py
        remote_code="./model.py", # 指定 model.py 路径 (假设 app.py 和 model.py 在同级)
        device=device
    )
    print(f"模型加载完毕，耗时: {time.time() - start_load:.2f} 秒")
    print(f"将使用 {'GPU' if IS_CUDA else 'CPU'} 进行推理。")
except Exception as e:
    print(f"--- 模型加载失败 ---")
    print(f"错误: {e}")
    print("请检查：")
    print("1. 网络连接是否正常 (需要下载模型)。")
    print("2. 'model.py' 和 'utils' 文件夹是否与此 app.py 在同一目录。")
    traceback.print_exc()
    sys.exit(1)

# --- 3. 辅助函数：文件名处理、SRT生成、文本格式化 ---

#
emo_dict = {
	"<|HAPPY|>": "😊", "<|SAD|>": "😔", "<|ANGRY|>": "😡", "<|NEUTRAL|>": "",
	"<|FEARFUL|>": "😰", "<|DISGUSTED|>": "🤢", "<|SURPRISED|>": "😮",
}
event_dict = {
	"<|BGM|>": "🎼", "<|Speech|>": "", "<|Applause|>": "👏", "<|Laughter|>": "😀",
	"<|Cry|>": "😭", "<|Sneeze|>": "🤧", "<|Breath|>": "", "<|Cough|>": "🤧",
}
emoji_dict = {
	"<|nospeech|><|Event_UNK|>": "❓", "<|zh|>": "", "<|en|>": "", "<|yue|>": "",
	"<|ja|>": "", "<|ko|>": "", "<|nospeech|>": "", "<|HAPPY|>": "😊", "<|SAD|>": "😔",
	"<|ANGRY|>": "😡", "<|NEUTRAL|>": "", "<|BGM|>": "🎼", "<|Speech|>": "",
	"<|Applause|>": "👏", "<|Laughter|>": "😀", "<|FEARFUL|>": "😰", "<|DISGUSTED|>": "🤢",
	"<|SURPRISED|>": "😮", "<|Cry|>": "😭", "<|EMO_UNKNOWN|>": "", "<|Sneeze|>": "🤧",
	"<|Breath|>": "", "<|Cough|>": "😷", "<|Sing|>": "", "<|Speech_Noise|>": "",
	"<|withitn|>": "", "<|woitn|>": "", "<|GBG|>": "", "<|Event_UNK|>": "",
}
lang_dict =  {
    "<|zh|>": "<|lang|>", "<|en|>": "<|lang|>", "<|yue|>": "<|lang|>",
    "<|ja|>": "<|lang|>", "<|ko|>": "<|lang|>", "<|nospeech|>": "<|lang|>",
}
emo_set = {"😊", "😔", "😡", "😰", "🤢", "😮"}
event_set = {"🎼", "👏", "😀", "😭", "🤧", "😷",}

# --- [修复] CJK 空格修复 ---
# CJK (中日韩) 字符的 Unicode 范围
CJK_RANGES = (
    r'\u4e00-\u9fff'  # CJK 统一表意文字
    r'\u3040-\u309f'  # 日语平假名
    r'\u30a0-\u30ff'  # 日语片假名
    r'\uac00-\ud7af'  # 韩语
)
CJK_PATTERN = f'([{CJK_RANGES}])'

def _is_cjk(char):
    """检查一个字符是否是 CJK 字符"""
    return re.match(CJK_PATTERN, char)

def _remove_cjk_spacing(text: str) -> str:
    """移除 CJK 字符之间的所有空格"""
    # 查找 (CJK)(空格)(CJK)，替换为 (CJK)(CJK)
    return re.sub(f'{CJK_PATTERN}\\s+{CJK_PATTERN}', r'\1\2', text)
# --- 修复结束 ---

def format_str_v2(s):
    #
    sptk_dict = {}
    for sptk in emoji_dict:
        sptk_dict[sptk] = s.count(sptk)
        s = s.replace(sptk, "")
    emo = "<|NEUTRAL|>"
    for e in emo_dict:
        if sptk_dict[e] > sptk_dict[emo]:
            emo = e
    for e in event_dict:
        if sptk_dict[e] > 0:
            s = event_dict[e] + s
    s = s + emo_dict[emo]

    for emoji in emo_set.union(event_set):
        s = s.replace(" " + emoji, emoji)
        s = s.replace(emoji + " ", emoji)
    return s.strip()

def format_str_v3(s):
    #
    def get_emo(s):
        return s[-1] if s[-1] in emo_set else None
    def get_event(s):
        return s[0] if s[0] in event_set else None

    s = s.replace("<|nospeech|><|Event_UNK|>", "❓")
    for lang in lang_dict:
        s = s.replace(lang, "<|lang|>")
    s_list = [format_str_v2(s_i).strip(" ") for s_i in s.split("<|lang|>")]
    new_s = " " + s_list[0]
    cur_ent_event = get_event(new_s)
    for i in range(1, len(s_list)):
        if len(s_list[i]) == 0:
            continue
        if get_event(s_list[i]) == cur_ent_event and get_event(s_list[i]) != None:
            s_list[i] = s_list[i][1:]
        cur_ent_event = get_event(s_list[i])
        if get_emo(s_list[i]) != None and get_emo(s_list[i]) == get_emo(new_s):
            new_s = new_s[:-1]
        
        # [修复] CJK 智能空格
        current_char = s_list[i].strip().lstrip()
        if not new_s or not current_char or _is_cjk(new_s[-1]) or _is_cjk(current_char[0]):
            new_s += current_char
        else:
            new_s += " " + current_char
            
    new_s = new_s.replace("The.", " ")
    
    # [修复] 再次清理 CJK 字符之间的空格
    new_s = _remove_cjk_spacing(new_s)
    
    return new_s.strip()

def _clean_text(text: str) -> str:
    """ 为 .txt 文件或 display 清理文本：移除所有 <|tags|>, emoji, 和 [timestamps] """
    # 1. 移除 [timestamps]
    text = re.sub(r"\[\d+\.\d+s-\d+\.\d+s\]\s*", "", text)
    # 2. 移除 all <|tags|>
    text = re.sub(r"<\|.*?\|>", "", text)
    # 3. 移除 all emojis
    all_emojis = "".join(list(emo_set.union(event_set)))
    text = re.sub(f"[{re.escape(all_emojis)}❓]", "", text)
    
    # 4. [修复] 移除 CJK 字符之间的空格
    text = _remove_cjk_spacing(text)
    
    # 5. 清理多余的换行
    text = re.sub(r"(\n\s*){2,}", "\n", text).strip()
    return text

def _timestamp_list_to_srt(timestamp_list: list) -> str:
    """ 
    [修复] 将 [[start_ms, end_ms, token], ...] 格式的列表转换为 SRT 格式。
    并智能处理 CJK 空格。
    """
    def _format_time(ms):
        sec = ms / 1000.0
        hour = int(sec // 3600)
        sec = sec % 3600
        minute = int(sec // 60)
        sec = sec % 60
        # 格式化为 HH:MM:SS,mmm
        return f"{hour:02d}:{minute:02d}:{sec:06.3f}".replace('.', ',')

    srt_content = ""
    line_index = 1
    
    current_start_ms = -1
    current_end_ms = -1
    current_text = ""
    
    # 合并相邻的句子
    for item in timestamp_list:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue # 跳过无效数据
            
        start_ms, end_ms, token = item[0], item[1], item[2]
        
        # 移除 token 中的所有 <|tags|>
        token = re.sub(r"<\|.*?\|>", "", token).strip()
        if not token:
            continue
            
        if current_start_ms == -1:
            # 开始新句子
            current_start_ms = start_ms
            current_end_ms = end_ms
            current_text = token
        else:
            # [修复] 智能拼接
            current_end_ms = end_ms
            if not current_text or not token or _is_cjk(current_text[-1]) or _is_cjk(token[0]):
                current_text += token
            else:
                current_text += " " + token

        # 如果 token 包含句号/问号/感叹号，则结束当前句子
        if token.endswith((".", "。", "!", "！", "?", "？")):
            start_time_str = _format_time(current_start_ms)
            end_time_str = _format_time(current_end_ms)
            srt_content += f"{line_index}\n{start_time_str} --> {end_time_str}\n{current_text}\n\n"
            line_index += 1
            current_start_ms = -1 # 重置
            current_text = ""
            
    # 处理最后一句
    if current_start_ms != -1:
        start_time_str = _format_time(current_start_ms)
        end_time_str = _format_time(current_end_ms)
        srt_content += f"{line_index}\n{start_time_str} --> {end_time_str}\n{current_text}\n\n"

    return srt_content


# --- 格式化代码结束 ---

def get_safe_windows_filename(filename: str) -> str:
    """ 移除 Windows 文件名中的非法字符 """
    if sys.platform == "win32":
        invalid_chars = r'[<>:"/\\|?*]'
        return re.sub(invalid_chars, '_', filename)
    return filename

def get_downloads_folder() -> Path:
    """跨平台获取用户的 Downloads 文件夹"""
    if os.name == 'nt': # Windows
        try:
            import winreg
            subkey = r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey)
            value = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')[0]
            downloads_path = Path(os.path.expandvars(value))
        except Exception:
            downloads_path = Path(os.environ.get('USERPROFILE', Path.home())) / 'Downloads'
    else: # macOS/Linux
        downloads_path = Path.home() / 'Downloads'
    
    downloads_path.mkdir(exist_ok=True)
    return downloads_path

DOWNLOADS_PATH = get_downloads_folder() # 全局定义下载路径

def get_unique_download_path(original_name: str, generate_srt: bool) -> Path:
    """ 获取用户 Downloads 文件夹中的一个安全且唯一的文件路径 """
    extension = ".srt" if generate_srt else ".txt"
    base_name = Path(original_name).stem
    safe_base_name = get_safe_windows_filename(base_name)
    
    output_name = f"{safe_base_name}{extension}"
    output_path = DOWNLOADS_PATH / output_name
    
    counter = 1
    while output_path.exists():
        output_name = f"{safe_base_name} ({counter}){extension}"
        output_path = DOWNLOADS_PATH / output_name
        counter += 1
            
    return output_path

def cleanup_temp_dir():
    """清理上一次运行留下的临时文件"""
    if TEMP_DIR.exists():
        try:
            shutil.rmtree(TEMP_DIR)
        except Exception as e:
            print(f"清理临时目录失败: {e}")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


# --- 4. Gradio 调用的主函数 (流式) ---

def process_files_streaming(uploaded_files, generate_srt, enable_emoji, progress=gr.Progress()):
    """
    Gradio 调用的主函数 (V5 流式版)
    这是一个 generator 函数，它会 `yield` 更新
    """
    if not uploaded_files:
        yield {status_bar: gr.Markdown("错误：未上传任何文件。")}
        return

    num_files = len(uploaded_files)
    if num_files > MAX_FILES:
        yield {status_bar: gr.Markdown(f"错误：一次最多上传 {MAX_FILES} 个文件。")}
        return

    print("\n--- 开始新任务 ---")
    cleanup_temp_dir()
    
    # 1. 初始化 UI：为每个文件创建占位符
    updates = {}
    for i in range(num_files):
        file_name = Path(uploaded_files[i].name).name
        updates[result_accordions[i]] = gr.Accordion(label=f"处理中: {file_name}", open=True, visible=True)
        updates[result_texts[i]] = gr.Textbox(value="[1/2] 已加入队列...", interactive=False, visible=True, show_copy_button=True)
        updates[result_files[i]] = gr.File(value=None, visible=False) # 隐藏下载按钮
    
    # 隐藏所有未使用的 UI 块
    for i in range(num_files, MAX_FILES):
        updates[result_accordions[i]] = gr.Accordion(visible=False)
        updates[result_texts[i]] = gr.Textbox(visible=False)
        updates[result_files[i]] = gr.File(visible=False)
    
    updates[status_bar] = gr.Markdown(f"已提交 {num_files} 个文件任务。将按顺序处理...")
    yield updates

    # 2. 串行处理每个文件 (A -> B -> C)
    for i in range(num_files):
        file = uploaded_files[i]
        file_name = Path(file.name).name
        
        print(f"\n--- 正在处理文件 {i+1}/{num_files}: {file_name} ---")
        
        # 2a. 开始处理
        yield {result_texts[i]: gr.Textbox(value="[1/2] 正在转录 (模型内置VAD与自动切片)...", interactive=False, show_copy_button=True)}
        
        # funasr 的 generate 方法参数
        params = {
            "language": "auto",       # 自动检测语言
            "use_itn": True,          # 自动数字转换
            "merge_vad": True,        # 合并VAD切分的片段
            "merge_length_s": 15,     # 合并到15秒
            
            # [关键修复] 无论如何都要请求时间戳 (output_timestamp=True)
            # 因为 `funasr` v1.2.7 在 `generate` 时如果 `output_timestamp=False`
            # 它返回的 `result[0]["text"]` 会缺少 VAD 合并后的 <|tags|>
            # 这会导致我们的 `format_str_v3` (emoji) 逻辑出错。
            # 所以我们统一请求时间戳，这最稳定。
            "output_timestamp": True, 
            
            # [关键功能] 根据Emoji开关设置
            "ban_emo_unk": enable_emoji,
        }

        try:
            # 2b. **核心：** 调用 funasr.AutoModel
            start_transcribe = time.time()
            result = pipeline_asr.generate(input=file.name, **params)
            print(f"文件 {file_name} 转录完成，耗时: {time.time() - start_transcribe:.2f}s")

            # 2c. 合并并保存
            yield {result_texts[i]: gr.Textbox(value="[2/2] 转录完成，正在格式化和保存文件...", interactive=False, show_copy_button=True)}
            
            # SenseVoice 的原始输出 (带 <|tag|>)
            raw_text_output = result[0]["text"]
            
            # 获取唯一的下载路径 ( .txt 或 .srt )
            output_path = get_unique_download_path(file_name, generate_srt)
            
            # 准备在UI上显示的文本
            display_text = ""
            
            with open(output_path, "w", encoding="utf-8") as f:
                if generate_srt:
                    # 从 result[0]["timestamp"] (列表) 生成 SRT
                    timestamp_list = result[0].get("timestamp", [])
                    srt_content = _timestamp_list_to_srt(timestamp_list)
                    
                    if not srt_content: # Bug 校验
                        srt_content = "SRT_GENERATION_FAILED:\n\n模型返回了空的时间戳列表。\n\nRaw text output:\n" + raw_text_output
                        
                    f.write(srt_content)
                    display_text = srt_content # 在UI上也显示SRT内容
                else:
                    # 写入纯文本
                    # 无论 emoji 开关如何，下载的 .txt 始终为纯文本
                    plain_text = _clean_text(raw_text_output)
                    f.write(plain_text)
                    
                    # UI 显示则根据开关决定
                    if enable_emoji:
                        display_text = format_str_v3(raw_text_output) # 带 emoji
                    else:
                        display_text = plain_text # 纯文本

            print(f"文件保存成功: {output_path}")
            
            # 2d. 更新UI
            yield {
                result_accordions[i]: gr.Accordion(label=f"✅ 完成: {file_name}", open=False),
                result_texts[i]: gr.Textbox(value=display_text, interactive=True, show_copy_button=True), # 文本框可交互
                result_files[i]: gr.File(value=str(output_path), visible=True, label=f"下载到: {output_path.name}") # 显示下载按钮
            }

        except Exception as e:
            print(f"文件 {file_name} 处理失败: {e}")
            traceback.print_exc()
            yield {
                result_accordions[i]: gr.Accordion(label=f"❌ 失败: {file_name}", open=True),
                result_texts[i]: gr.Textbox(value=f"处理失败: {e}\n\n{traceback.format_exc()}", interactive=True, show_copy_button=True)
            }
        finally:
            # 在每个文件处理后清理显存
            if IS_CUDA:
                torch.cuda.empty_cache()

    print("\n--- 所有任务完成 ---")
    yield {status_bar: gr.Markdown(f"✅ 所有 {num_files} 个文件处理完成。")}


# --- 5. 启动 Gradio 界面 ---

print("启动 Gradio Web UI...")

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        f"""
        # 🔥 SenseVoice (Small) 批量转录工具
        使用 `funasr.AutoModel` 和 `{MODEL_ID}`。
        可一次上传多个文件 (mp3, wav, flac, mp4...)。
        模型内置VAD，可自动处理长音频，无需手动切片。
        """
    )
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 1. 上传文件")
            input_files = gr.File(
                label=f"上传音频或视频文件 (最多{MAX_FILES}个)", 
                file_count="multiple",
                type="filepath" # 使用 filepath 模式
            )
            
            gr.Markdown("### 2. 配置参数")
            generate_srt = gr.Checkbox(
                label="生成 .srt 字幕文件", 
                value=False, 
                info="勾选后将下载 .srt 文件 (带时间戳)，否则下载 .txt 文件 (纯文本)。"
            )
            
            # <-- 新增 Emoji 开关 -->
            enable_emoji = gr.Checkbox(
                label="显示 Emoji (情绪/事件)", 
                value=False, # 默认关闭
                info="勾选后，将在文本框中显示情绪/事件图标。不影响下载的 .txt/.srt 文件。"
            )
            
            submit_btn = gr.Button("🚀 开始转录", variant="primary")
            
        with gr.Column(scale=2):
            gr.Markdown("### 3. 转录结果")
            status_bar = gr.Markdown("请上传文件并点击开始。")
            
            # --- 动态 UI 占位符 ---
            result_accordions = []
            result_texts = []
            result_files = []
            
            for i in range(MAX_FILES):
                with gr.Accordion(f"结果 {i+1}", visible=False) as acc:
                    text = gr.Textbox(label="转录文本", show_copy_button=True, interactive=False, lines=15)
                    file = gr.File(label="下载文件", visible=False)
                    
                    result_accordions.append(acc)
                    result_texts.append(text)
                    result_files.append(file)
            
    # 绑定点击事件 (加入 enable_emoji)
    submit_btn.click(
        fn=process_files_streaming,
        inputs=[input_files, generate_srt, enable_emoji],
        outputs=[status_bar] + result_accordions + result_texts + result_files
    )

# --- 6. 启动服务 (带 Gradio 安全路径修复) ---

url = f"http://127.0.0.1:{PORT}"
print(f"Gradio 运行在: {url}")

# 自动打开浏览器
if os.environ.get("GRADIO_RELOAD") != "true":
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"无法自动打开浏览器: {e}")
        
# 关键修复：允许 Gradio 访问 "Downloads" 文件夹
cwd = str(Path.cwd()) # 1. 当前工作目录
temp_dir = str(Path(tempfile.gettempdir())) # 2. 系统临时目录
gradio_temp_dir = str(TEMP_DIR.absolute()) # 3. 我们的处理目录
downloads_dir = str(DOWNLOADS_PATH.absolute()) # 4. 我们的下载目录

trusted_paths = [cwd, temp_dir, gradio_temp_dir, downloads_dir]

print("\n--- 启动 Gradio 服务 ---")
print(f"已添加以下路径到 Gradio 信任列表 (allowed_paths):")
for path in trusted_paths:
    print(f" - {path}")

demo.launch(
    inbrowser=False, 
    show_error=True, 
    allowed_paths=trusted_paths, # 修复 Gradio 的 InvalidPathError
    server_port=PORT # 指定新端口
)