let globalTasks = {};
const POLLING_INTERVAL = 5000;  // 5秒
let pollingTimer = null;

// 获取状态对应的CSS类
function getStatusClass(status) {
    switch(status) {
        case '等待中':
            return 'status-waiting';
        case '生成中':
            return 'status-generating';
        case '已失败':
            return 'status-failed';
        default:
            return '';
    }
}

// 更新任务列表
function updateTasks() {
    $.get('/sync/tasks', function(tasks) {
        globalTasks = tasks;
        renderTasks();

    });
}

// 渲染任务列表
function renderTasks() {
    const container = $('#taskContainer');
    container.empty();
    
    Object.values(globalTasks).forEach(task => {
        const taskElement = $(`
            <div class="task-item" data-task-id="${task.id}">
                <div class="task-header">
                    <span class="task-name">${task.person_name}</span><br>
                   <div class="info-cell"><strong>状态:</strong> <span class="status-badge ${getStatusClass(task.status)}">${task.status}</span></div>
                </div>
                <div class="task-details">
                      <div class="log-container" id="log-${task.id}"></div>

                </div>
            </div>
        `);
        
        container.append(taskElement);

    });
}
// 轮询任务状态
function pollTaskStatus(taskId) {
    try{
       $.get(`/sync/task_status/${taskId}`, function(response) {
        if (response.error) return;

        // 更新任务状态
        if (globalTasks[taskId].status !== response.status) {
            globalTasks[taskId].status = response.status;

            // 更新状态显示
            const statusElement = $(`.task-item[data-task-id="${taskId}"] .status-badge`);
            statusElement.text(response.status);
            statusElement.attr('class', `status-badge ${getStatusClass(response.status)}`);

        }

        // 更新日志 - 使用最新的完整日志
        const logContainer = $(`#log-${taskId}`);
        const taskItem = logContainer.closest('.task-item');
        if (response.logs && response.logs.length > 0) {
            logContainer.html(response.logs.join('<br>'));
            // 自动滚动到底部
            logContainer.scrollTop(logContainer[0].scrollHeight);
        }
// 如果任务完成且有输出文件，添加下载按钮
                if (response.status === "已完成" && response.output_file) {
                    // 添加下载按钮
                    const downloadHtml = `
                         <div class="log-container" id="log-${taskId}"></div>
                    ${response.output_file ?
                        `<button onclick="copyDownloadLink('${response.output_file}')" class="download-btn">下载生成的视频</button>`
                        : ''}`;

                    taskItem.append(downloadHtml);
                }
        // 如果任务还在进行中，继续轮询

    })
    }catch(e){
        console.log("e:暂无id");
    }
}

// 表单提交处理
$(document).ready(function() {
    updateTasks();

    startPolling();// 开始循环日志


    $('#syncForm').on('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        
        $.ajax({
            url: '/sync/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.error) {
                    alert(response.error);
                } else {
                    updateTasks();
                    $('#syncForm')[0].reset();
                }
            },
            error: function() {
                alert('上传失败，请重试');
            }
        });
    });
});

// 开始轮询
function startPolling() {
    // 设置新的轮询
   pollingTimer = setInterval(() => {
        Object.entries(globalTasks).forEach(([taskId, task]) => {
            const logContainer = $(`#log-${taskId}`);
            if (logContainer.text().length < 100) {
                pollTaskStatus(taskId);
            }else if (task.status !== "已完成") {
                pollTaskStatus(taskId);
            }
        });
    }, POLLING_INTERVAL);
}


// 显示下载链接模态框
function showDownloadModal(filePath) {
    const normalizedPath = filePath.replace(/\\/g, '/');
    const fullUrl = `${window.location.origin}/${normalizedPath}`;
    
    navigator.clipboard.writeText(fullUrl).then(function() {
        alert('下载链接已复制到剪贴板');
    }).catch(function(err) {
        console.error('复制失败:', err);
        // 降级处理：创建临时输入框
        const tempInput = document.createElement('input');
        tempInput.value = fullUrl;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        alert('下载链接已复制到剪贴板');
    });
}

// 修改复制链接功能
function copyDownloadLink(filePath) {
    // 确保filePath是从file/action开始的路径
    const normalizedPath = filePath.startsWith('file/action')
        ? filePath
        : filePath.substring(filePath.indexOf('file/action'));

    // 直接使用规范化后的路径
    const fullUrl = `${window.location.origin}/${normalizedPath}`;

    navigator.clipboard.writeText(fullUrl).then(function() {
        alert('下载链接已复制到剪贴板');
    }).catch(function(err) {
        console.error('复制失败:', err);
        const tempInput = document.createElement('input');
        tempInput.value = fullUrl;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        alert('下载链接已复制到剪贴板');
    });
}