(简体中文|[English](./README_en.md))

# SenseVoiceBatch

[![SeneseVoice-Small](https://img.shields.io/badge/Model-SenseVoice--Small-blue.svg)](https://www.modelscope.cn/models/iic/SenseVoiceSmall/summary)
[![FunASR](https://img.shields.io/badge/Framework-FunASR-orange.svg)](https://github.com/modelscope/FunASR)
[![Gradio](https://img.shields.io/badge/UI-Gradio-brightgreen.svg)](https://www.gradio.app/)

一个基于 SenseVoice-Small 和 FunASR 的批量音频转录工具 (Gradio UI)。
支持多文件串行处理、自动VAD切片、SRT/TXT 导出，并自动下载到本地。

An audio batch transcription tool (Gradio UI) powered by SenseVoice-Small & FunASR. Features serial multi-file processing, auto VAD, SRT/TXT export, and auto-download.

---

![SenseVoiceBatch 界面截图](image/screenshot.png)

## ✨ 功能特性

* **Gradio 界面**: 简单易用，拖拽上传。
* **批量处理**: 一次可处理多个文件 (mp3, wav, flac, mp4...)。
* **自动切片 (VAD)**: 内置 VAD，自动处理长音频，无需手动切分。
* **SRT / TXT 导出**:
    * `SRT`: 导出带**精确时间戳**的字幕文件。
    * `TXT`: 导出纯净的文本文件。
* **Emoji 开关**: 自由选择是否在 UI 上显示情绪 (😊) 和事件 (🎼) 图标。
* **自动下载**: 所有产物（SRT/TXT）自动保存到你电脑的 "下载" 文件夹。
* **一键启动**: 提供了 `start_asr_app.bat` 脚本，双击即可启动 (Windows 用户) 。

## 📦 安装指南

本项目依赖 Conda 环境和 `funasr` 库。

**第 1 步: 克隆仓库**
```bash
git clone [https://github.com/Yiewker/SenseVoiceBatch.git](https://github.com/Yiewker/SenseVoiceBatch.git)
cd SenseVoiceBatch
```

**第 2 步: 创建并激活 Conda 环境**

```bash
# (推荐使用 Python 3.9 或 3.10)
conda create -n sensevoice python=3.10 -y
conda activate sensevoice
```

**第 3 步: 安装 PyTorch**
(推荐使用 CUDA 11.8，如果你的 GPU 不支持，请访问 PyTorch 官网查找对应版本)

```bash
# 适用于 NVIDIA GPU
pip install torch torchaudio --index-url [https://download.pytorch.org/whl/cu118](https://download.pytorch.org/whl/cu118)
```

```bash
# 仅适用于 CPU
pip install torch torchaudio
```

**第 4 步: 安装项目依赖**

```bash
pip install -r requirements.txt
```

## 🚀 运行

### 方式 A: (推荐 - 适用于 Windows)

1.  确保你已经完成了上述**安装指南**中的所有步骤。
2.  直接双击运行 `start_asr_app.bat` 文件。

它会自动激活 `sensevoice` 环境，运行 `app.py`，并自动在浏览器中打开 `http://127.0.0.1:7080`。

### 方式 B: (手动 - 适用于所有系统)

1.  打开你的终端 (或 Anaconda Prompt)。
2.  激活环境:
    ```bash
    conda activate sensevoice
    ```
3.  运行 Web UI:
    ```bash
    python app.py
    ```
4.  手动在浏览器中打开 `http://127.0.0.1:7080`。

## ⚠ 重要：项目文件结构

本仓库能正常运行，依赖于原 SenseVoice 项目的 `model.py` 和 `utils` 文件夹。

**本仓库已包含打过补丁的 `model.py`**，修复了原版在时间戳 (SRT) 生成时的一系列 CUDA Bug 和 Type Bug。

请确保你的目录结构如下，否则 `app.py` 会因 `remote_code` 引用失败而无法启动：

```
SenseVoiceBatch/
│
├── 📄 app.py              <-- 我们的 Gradio 界面
├── 📄 model.py            <-- [重要] 打过补丁的模型定义文件
├── 📄 requirements.txt   <-- 依赖列表
├── 📄 start_asr_app.bat   <-- [重要] Windows 启动器
├── 📄 README.md           <-- (就是这个文件)
│
└── 📁 utils/              <-- [重要] 原始的工具文件夹
    ├── 📄 ctc_alignment.py
    ├── 📄 frontend.py
    ├── 📄 infer_utils.py
    └── ... (其他 utils 文件)
```

## 🙏 致谢

  * **FunAudioLLM / SenseVoice (原项目)**:
      * https://github.com/FunAudioLLM/SenseVoice
  * **FunASR (核心框架)**:
      * https://github.com/modelscope/FunASR

<!-- end list -->
