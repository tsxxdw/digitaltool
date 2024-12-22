// 更新任务列表
function updateTasks() {
    $.get('/train/tasks', function(tasks) {
        $('#taskContainer').empty();
        tasks.forEach(function(task) {
            let statusClass = task.status === "完成" ? "status-complete" : "status-training";
            
            let taskHtml = `
                <div class="task-item">
                    <div><strong>任务ID:</strong> ${task.task_id}</div>
                    <div><strong>状态:</strong> <span class="${statusClass}">${task.status}</span></div>
                    <div><strong>创建时间:</strong> ${task.create_time}</div>
                    <div class="log-container" id="log-${task.task_id}"></div>
                </div>
            `;
            $('#taskContainer').append(taskHtml);
            
            // 获取任务状态和日志
            pollTaskStatus(task.task_id);
        });
    });
}

// 轮询任务状态
function pollTaskStatus(taskId) {
    $.get(`/train/task_status/${taskId}`, function(response) {
        if (response.error) return;
        
        $(`#log-${taskId}`).html(response.log.join('<br>'));
        
        if (response.status === "训练中") {
            setTimeout(() => pollTaskStatus(taskId), 2000);
        }
    });
}

// 页面加载完成后执行
$(document).ready(function() {
    // 处理表单提交
    $('#trainForm').submit(function(e) {
        e.preventDefault();
        
        let formData = new FormData(this);
        
        // 禁用提交按钮
        let submitButton = $(this).find('button[type="submit"]');
        submitButton.prop('disabled', true);
        submitButton.text('提交中...');
        
        $.ajax({
            url: '/train/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                alert('训练任务已提交，任务ID: ' + response.task_id);
                updateTasks();
            },
            error: function(xhr) {
                alert('提交失败: ' + xhr.responseJSON.error);
            },
            complete: function() {
                // 恢复提交按钮
                submitButton.prop('disabled', false);
                submitButton.text('开始训练');
            }
        });
    });

    // 页面加载时更新任务列表
    updateTasks();
    
    // 定期更新任务列表
    setInterval(updateTasks, 5000);
}); 