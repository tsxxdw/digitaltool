// 全局变量
const POLLING_INTERVAL = 10000;  // 10秒
let globalTasks = {};           // 存储所有任务
let pollingTimer = null;        // 轮询定时器

// 更新任务列表
function updateTasks() {
    $.get('/train/tasks', function(tasks) {
        globalTasks = tasks;
        renderTasks();
        startPolling();
    });
}

// 渲染任务列表
function renderTasks() {
    $('#taskContainer').empty();
    
    const taskArray = Object.entries(globalTasks).map(([id, task]) => ({
        id,
        ...task
    })).sort((a, b) => {
        return new Date(b.create_time) - new Date(a.create_time);
    });
    
    taskArray.forEach((task, index) => {
        const taskNumber = taskArray.length - index;
        
        let taskHtml = `
            <div class="task-item" data-task-id="${task.id}">
                <div class="task-header">
                    <div class="task-info">
                        <div class="info-row">
                            <div class="info-cell"><strong>序号:</strong> ${taskNumber}</div>
                            <div class="info-cell"><strong>状态:</strong> <span class="status-badge ${getStatusClass(task.status)}">${task.status}</span></div>
                            <div class="info-cell"><strong>创建时间:</strong> ${task.create_time}</div>
                            ${task.status === "已完成" ? 
                                `<div class="info-cell">
                                    <button onclick="saveTrainPerson('${task.id}')" class="save-btn">保存训练人物</button>
                                </div>` : 
                                ''
                            }
                        </div>
                        <div class="info-row">
                            <div class="info-cell name-cell">
                                <strong>训练对象:</strong>
                                <input type="text" value="${task.name}" 
                                       ${task.status === "训练中" ? 'disabled' : ''}
                                       onchange="updateTaskName('${task.id}', this.value)">
                            </div>
                        </div>
                        <div class="info-row">
                            <div class="info-cell"><strong>原始视频:</strong> <span class="file-name">${task.video_name}</span></div>
                            <div class="info-cell"><strong>原始音频:</strong> <span class="file-name">${task.audio_name}</span></div>
                        </div>
                        <div class="info-row">
                            <div class="info-cell file-path"><strong>转换后视频:</strong> <span class="path-text">${task.new_video_name}</span></div>
                        </div>
                        <div class="info-row">
                            <div class="info-cell file-path"><strong>转换后音频:</strong> <span class="path-text">${task.new_audio_name}</span></div>
                        </div>
                    </div>
                </div>
                <div class="log-container" id="log-${task.id}"></div>
            </div>
        `;
        $('#taskContainer').append(taskHtml);
        
        pollTaskStatus(task.id, true);
    });
}

// 启动轮询
function startPolling() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
    }
    
    pollingTimer = setInterval(() => {
        Object.entries(globalTasks).forEach(([taskId, task]) => {
            if (task.status !== "已完成") {
                pollTaskStatus(taskId, false);
            }
        });
    }, POLLING_INTERVAL);
}

// 轮询任务状态
function pollTaskStatus(taskId) {
    $.get(`/train/task_status/${taskId}`, function(response) {
        if (response.error) return;
        
        // 更新任务状态
        if (globalTasks[taskId].status !== response.status) {
            globalTasks[taskId].status = response.status;
            
            // 更新状态显示
            const statusElement = $(`.task-item[data-task-id="${taskId}"] .status-badge`);
            statusElement.text(response.status);
            statusElement.attr('class', `status-badge ${getStatusClass(response.status)}`);
            
            // 如果状态变为"已完成"，添加保存按钮
            if (response.status === "已完成") {
                const infoRow = $(`.task-item[data-task-id="${taskId}"] .info-row:first`);
                if (infoRow.find('.save-btn').length === 0) {
                    infoRow.append(`
                        <div class="info-cell">
                            <button onclick="saveTrainPerson('${taskId}')" class="save-btn">保存训练人物</button>
                        </div>
                    `);
                }
            }
        }
        
        // 更新日志 - 使用最新的完整日志
        const logContainer = $(`#log-${taskId}`);
        if (response.logs && response.logs.length > 0) {
            logContainer.html(response.logs.join('<br>'));
            // 自动滚动到底部
            logContainer.scrollTop(logContainer[0].scrollHeight);
        }
        
        // 如果任务还在进行中，继续轮询
        if (response.status === "训练中" || response.status === "等待中") {
            setTimeout(() => pollTaskStatus(taskId), 10000);  // 10秒轮询一次
        }
    });
}

// 更新任务名称
function updateTaskName(taskId, newName) {
    if (!/^[a-zA-Z0-9\u4e00-\u9fa5]+$/.test(newName)) {
        alert('名称只能包含字母、数字、汉字');
        return;
    }
    
    $.post('/train/update_name', {
        task_id: taskId,
        name: newName
    }, function(response) {
        if (response.error) {
            alert(response.error);
        } else {
            globalTasks[taskId].name = newName;
        }
    });
}

// 删除任务
function deleteTask(taskId) {
    if (!confirm('确定要删除此任务吗？')) return;
    
    $.post('/train/delete_task', {
        task_id: taskId
    }, function(response) {
        if (response.error) {
            alert(response.error);
        } else {
            delete globalTasks[taskId];
            $(`.task-item[data-task-id="${taskId}"]`).remove();
        }
    });
}

// 获取状态对应的CSS类
function getStatusClass(status) {
    switch(status) {
        case '等待中':
            return 'status-waiting';
        case '训练中':
            return 'status-training';
        case '已完成':
            return 'status-complete';
        default:
            return '';
    }
}

// 页面加载完成后执行
$(document).ready(function() {
    // 初始加载任务列表
    updateTasks();
    
    // 监听表单提交
    $('#uploadForm').on('submit', function(e) {
        e.preventDefault();
        
        const videoFile = $('#video')[0].files[0];
        const audioFile = $('#audio')[0].files[0];
        const name = $('#name').val();
        
        if (!videoFile || !audioFile || !name) {
            alert('请填写所有必填项');
            return false;
        }
        
        if (!/^[a-zA-Z0-9\u4e00-\u9fa5]+$/.test(name)) {
            alert('训练对象名称只能包含字母、数字、汉字');
            return false;
        }
        
        const formData = new FormData();
        formData.append('video', videoFile);
        formData.append('audio', audioFile);
        formData.append('name', name);
        
        $('#submitBtn').prop('disabled', true);
        $('.loading-overlay').show(); // 显示加载圈
        
        $.ajax({
            url: '/train/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.error) {
                    alert(response.error);
                } else {
                    $('#uploadForm')[0].reset();
                    updateTasks();
                }
            },
            error: function(xhr) {
                alert('上传失败：' + (xhr.responseJSON?.error || '服务器错误'));
            },
            complete: function() {
                $('#submitBtn').prop('disabled', false);
                $('.loading-overlay').hide(); // 隐藏加载圈
            }
        });
        
        return false;
    });
});

// 在页面卸载时清除定时器
$(window).on('unload', function() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
    }
});

// 保存训练人物
function saveTrainPerson(taskId) {
    $.post('/train/save_person', {
        task_id: taskId
    }, function(response) {
        if (response.error) {
            alert(response.error);
        } else {
            alert('保存成功！');
        }
    });
} 