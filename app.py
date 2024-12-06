import os
import platform
import re
import subprocess
import uuid
from datetime import datetime
import shutil
from flask import Flask, request, jsonify, send_from_directory, render_template

# 创建Flask应用
app = Flask(__name__)

# 文件存储目录
# UPLOAD_FOLDER = r'C:\computer\3\itproject\digitaltool\digitaltool\uploads'
# ACT_FOLDER = r'C:\computer\3\itproject\digitaltool\digitaltool\act'
# OUT_FOLDER = r'C:\computer\3\itproject\digitaltool\digitaltool\out'
# TANNN = r"C:\computer\3\itproject\The_Digital_Human_TANGO\TANGO"
# MUSETALK = r"C:\computer\3\itproject\MuseTalk"
# DIGITALTOOL = r"C:\computer\3\itproject\digitaltool\digitaltool"

UPLOAD_FOLDER = r'/root/onethingai-fs/digitaltool/uploads'
ACT_FOLDER = r'/root/onethingai-fs/digitaltool/act'
OUT_FOLDER = r'/root/onethingai-fs/digitaltool/out'
DIGITALTOOL = r"/root/onethingai-fs/digitaltool"
TANNN = r"/root/onethingai-fs/TANGO"
MUSETALK = r"/root/onethingai-fs/MuseTalk"

# 存储任务的内存列表
tasks = []

# 确保上传、动作生成和输出文件夹存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ACT_FOLDER, exist_ok=True)
os.makedirs(OUT_FOLDER, exist_ok=True)

# 清理旧文件：每次启动时清理上传和生成的文件
def clean_old_files():
    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
    if os.path.exists(ACT_FOLDER):
        shutil.rmtree(ACT_FOLDER)
    if os.path.exists(OUT_FOLDER):
        shutil.rmtree(OUT_FOLDER)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(ACT_FOLDER, exist_ok=True)
    os.makedirs(OUT_FOLDER, exist_ok=True)

# 启动时清理文件
clean_old_files()

# 任务方法定义
def tannn(task):
    print(f"开始执行动作生成，任务ID：{task['task_id']}")
    # 需要执行的命令
    os_type = platform.system()
    inference_path = os.path.join(TANNN, "inference.py")
    input_audio = task['audio']
    input_video = task['video']
    output_video = os.path.join(ACT_FOLDER, f"{task['task_id']}.mp4")
    cmd_lip = ""
    if os_type == "Windows":
        # Windows 环境下，使用 cmd 激活 conda 环境并执行命令
        cmd_lip = f"cmd /c \"cd /d {TANNN} && conda activate tango && python inference.py --audio_path {input_audio} --video_path {input_video} --save_path {output_video}\""
        #cmd_lip = f"cmd /c \"cd /d {TANNN} && conda activate tango && python inference.py --audio_path \"{input_audio}\" --video_path \"{input_video}\" --save_path \"{output_video}\"\""

    else:
        # Linux/macOS 环境下，先进入目录，然后激活环境并执行命令
        cmd_lip = f"cd {TANNN} && conda activate tango && python inference.py --audio_path {input_audio} --video_path {input_video} --save_path {output_video}"

    print("cmd_lip",cmd_lip)
    # 启动子进程（异步执行）
    process = subprocess.Popen(f"bash -c '{cmd_lip}'", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 获取进程的标准输出和标准错误输出
    stdout, stderr = process.communicate()

    # 打印输出
    print("命令输出：", stdout.decode())
    if stderr:
        print("错误信息：", stderr.decode())
    # 等待进程结束
    process.wait()
    print("命令执行完成，返回码：", process.returncode)
    print(f"动作生成完成，任务ID：{task['task_id']}.mp4")

def mu(task):
    print(f"开始执行口唇同步，任务ID：{task['task_id']}")
    # 需要执行的命令
    os_type = platform.system()
    inference_path = os.path.join(MUSETALK, "inference.py")
    input_audio = task['audio']
    input_video = os.path.join(ACT_FOLDER, f"{task['task_id']}.mp4")
    output_video = os.path.join(OUT_FOLDER, f"{task['task_id']}.mp4")
    cmd_lip = ""
    if os_type == "Windows":
        # Windows 环境下，使用 cmd 激活 conda 环境并执行命令
        cmd_lip = f"cmd /c \"cd /d {MUSETALK} && conda activate musetalk && python -m scripts.inference --audio_path {input_audio} --video_path {input_video} --save_path {output_video}\""
        #cmd_lip = f"cmd /c \"cd /d {MUSETALK} && conda activate musetalk && python -m scripts.inference --audio_path \"{input_audio}\" --video_path \"{input_video}\" --save_path \"{output_video}\"\""

    else:
        # Linux/macOS 环境下，先进入目录，然后激活环境并执行命令
        cmd_lip = f"cd {MUSETALK} && conda activate musetalk && python -m scripts.inference --audio_path {input_audio} --video_path {input_video} --save_path {output_video}"

    print("cmd_MUSETALKlip", cmd_lip)
    # 启动子进程（异步执行）
    process = subprocess.Popen(f"bash -c '{cmd_lip}'", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 获取进程的标准输出和标准错误输出
    stdout, stderr = process.communicate()

    # 打印输出
    print("命令输出：", stdout.decode())
    if stderr:
        print("错误信息：", stderr.decode())
    # 等待进程结束
    process.wait()
    print(f"口唇同步完成，任务ID：{task['task_id']}.mp4")

def comple(task_id):
    print(f"任务完成，任务ID：{task_id}")
    # 这里可以增加最终的清理或其他处理
    pass

def clean_string(input_str):
    # 只保留汉字和字母，去除其他字符
    result = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', input_str)
    return result

# 首页路由，渲染 index.html
@app.route('/')
def index():
    return render_template('index.html')

# 上传视频和音频文件
@app.route('/upload', methods=['POST'])
def upload_files():
    video_file = request.files.get('video')
    audio_file = request.files.get('audio')

    if not video_file or not audio_file:
        return jsonify({"error": "Both video and audio files are required"}), 400

    # 生成唯一文件名：原文件名 + 日期时间戳 + 4位随机数
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_suffix = str(uuid.uuid4().int)[:8]  # 获取4位随机数
    video_filename = f"{timestamp}_{random_suffix}.mp4"
    audio_filename = f"{timestamp}_{random_suffix}.wav"

    video_path = os.path.join(UPLOAD_FOLDER, video_filename)
    audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)

    video_file.save(video_path)
    audio_file.save(audio_path)

    # 创建任务并添加到任务列表
    task_id = f"task_{timestamp}_{random_suffix}"
    task = {
        'task_id': task_id,
        'video': video_path,
        'audio': audio_path,
        'status': 'waiting',
        'output': None,
        'originaudioname':audio_file.filename.split('.')[0],
        'originvideoname': video_file.filename.split('.')[0]
    }
    tasks.append(task)

    return jsonify({"task_id": task_id, "status": "uploaded"}), 200


# 检查所有任务的状态
@app.route('/check_tasks', methods=['GET'])
def check_tasks():
    # 查找正在处理的任务
    processing_task = None
    for task in tasks:
        if task['status'] in ['action_generating', 'lip_syncing']:
            processing_task = task
            break

    # 如果没有正在处理的任务，选择一个“等待中”的任务开始处理
    if not processing_task:
        for task in tasks:
            if task['status'] == 'waiting':
                task['status'] = 'action_generating'  # 任务开始动作生成
                tannn(task)  # 调用动作生成方法
                break

    # 检查任务的状态并更新
    for task in tasks:
        if task['status'] == 'action_generating':
            # 检查动作生成是否完成，假设文件生成了，从 act 文件夹中查找
            task_output_filename = os.path.join(ACT_FOLDER, f"{task['task_id']}.mp4")
            if os.path.exists(task_output_filename):
                task['status'] = 'lip_syncing'  # 动作生成完成，进入口唇同步
                mu(task)  # 调用口唇同步方法
        elif task['status'] == 'lip_syncing':
            # 假设口唇同步完成，文件存在就变为已完成，从 out 文件夹中查找
            task_output_filename = os.path.join(OUT_FOLDER, f"{task['task_id']}.mp4")
            if os.path.exists(task_output_filename):
                task['status'] = 'completed'
                task['output'] = f"{task['task_id']}.mp4"
                comple(task['task_id'])  # 调用完成方法

    return jsonify({"tasks": tasks})


# 下载已完成任务的视频文件
@app.route('/download/<task_id>', methods=['GET'])
def download_video(task_id):
    task = next((t for t in tasks if t['task_id'] == task_id), None)

    if not task or task['status'] != 'completed':
        return jsonify({"error": "Task not found or not completed yet"}), 404

    # 生成下载路径，确保文件存在
    output_path = os.path.join(OUT_FOLDER, task['output'])
    if not os.path.exists(output_path):
        return jsonify({"error": "Output file not found"}), 404

    # 发送生成的视频文件给用户下载
    return send_from_directory(OUT_FOLDER, task['output'], as_attachment=True)


@app.route('/get_tasks', methods=['GET'])
def get_tasks():
    # 返回当前内存中的所有任务列表
    return jsonify({'tasks': tasks})

# 启动Flask服务器
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
