from flask import Blueprint, render_template, request, jsonify
import os
import subprocess
import uuid
from datetime import datetime

bp = Blueprint('action', __name__)

# 存储任务信息的字典
tasks = {}

class Task:
    def __init__(self, task_id, video_path, audio_path):
        self.task_id = task_id
        self.video_path = video_path
        self.audio_path = audio_path
        self.status = "处理中"
        self.log = []
        self.output_file = None
        self.create_time = datetime.now()

@bp.route('/action')
def action():
    return render_template('action.html')

@bp.route('/upload', methods=['POST'])
def upload():
    if 'video' not in request.files or 'audio' not in request.files:
        return jsonify({'error': '请上传视频和音频文件'}), 400
        
    video = request.files['video']
    audio = request.files['audio']
    
    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
    # 创建上传目录
    upload_dir = os.path.join('static', 'uploads', task_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存上传的文件
    video_path = os.path.join(upload_dir, video.filename)
    audio_path = os.path.join(upload_dir, audio.filename)
    
    video.save(video_path)
    audio.save(audio_path)
    
    # 创建新任务
    task = Task(task_id, video_path, audio_path)
    tasks[task_id] = task

    print("aa")
    # 启动处理进程 (这里需要替换为实际的处理脚本路径)
    # subprocess.Popen(['python', 'process_video.py',
    #                  '--video', video_path,
    #                  '--audio', audio_path,
    #                  '--task_id', task_id])
    
    return jsonify({'task_id': task_id})

@bp.route('/task_status/<task_id>')
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify({
        'status': task.status,
        'log': task.log,
        'output_file': task.output_file
    })

@bp.route('/tasks')
def get_tasks():
    task_list = []
    for task in tasks.values():
        task_list.append({
            'task_id': task.task_id,
            'status': task.status,
            'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'output_file': task.output_file
        })
    return jsonify(task_list) 