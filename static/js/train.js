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
    
    // 将任务对象转换为数组并按创建时间排序
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
                        <div><strong>序号:</strong> ${taskNumber}</div>
                        <div class="task-name">
                            <strong>训练对象:</strong>
                            <input type="text" value="${task.name}" 
                                   ${task.status !== "已完成" ? 'disabled' : ''}
                                   onchange="updateTaskName('${task.id}', this.value)">
                        </div>
                        <div><strong>状态:</strong> <span class="status-badge ${getStatusClass(task.status)}">${task.status}</span></div>
                        <div><strong>创建时间:</strong> ${task.create_time}</div>
                        <div><strong>原始视频:</strong> ${task.video_name}</div>
                        <div><strong>原始音频:</strong> ${task.audio_name}</div>
                    </div>
                    ${task.status === "已完成" ? 
                        `<button class="delete-btn" onclick="deleteTask('${task.id}')">×</button>` : 
                        ''}
                </div>
                <div class="log-container" id="log-${task.id}"></div>
            </div>
        `;
        $('#taskContainer').append(taskHtml);
        
        // 初始加载任务日志
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
function pollTaskStatus(taskId, isRefresh = false) {
    $.get(`/train/task_status/${taskId}?refresh=${isRefresh}`, function(response) {
        if (response.error) return;
        
        const logContainer = $(`#log-${taskId}`);
        
        // 更新日志
        if (isRefresh) {
            logContainer.empty();
            response.log.forEach(log => {
                logContainer.append(`<div class="log-line">${log}</div>`);
            });
        } else if (response.new_logs && response.new_logs.length > 0) {
            response.new_logs.forEach(log => {
                logContainer.append(`<div class="log-line">${log}</div>`);
            });
        }
        
        // 滚动到底部
        logContainer.scrollTop(logContainer[0].scrollHeight);
        
        // 更新任务状态
        if (globalTasks[taskId].status !== response.status) {
            globalTasks[taskId].status = response.status;
            const statusBadge = logContainer.closest('.task-item').find('.status-badge');
            statusBadge.text(response.status);
            statusBadge.attr('class', `status-badge ${getStatusClass(response.status)}`);
            
            // 如果任务完成，添加删除按钮
            if (response.status === "已完成") {
                const taskItem = logContainer.closest('.task-item');
                if (!taskItem.find('.delete-btn').length) {
                    taskItem.find('.task-info').after('<button class="delete-btn" onclick="deleteTask(\'' + taskId + '\')">×</button>');
                }
            }
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