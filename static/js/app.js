
 // 每次页面加载时，获取任务列表
    document.addEventListener('DOMContentLoaded', function() {
        fetchTasks();
    });

    // 获取任务列表
    function fetchTasks() {
        fetch('/get_tasks')
            .then(response => response.json())
            .then(data => {
                const tasks = data.tasks;
                const taskList = document.querySelector("#task-list tbody");
                taskList.innerHTML = ""; // 清空现有任务

                tasks.forEach(task => {
                    const row = document.createElement("tr");

                    // 更新任务状态的显示样式
                    const statusClass = task.status.toLowerCase();
                    const downloadButton = task.status === 'completed' ?
                        `<button class="download-btn" onclick="downloadFile('${task.task_id}')">下载</button>` :
                        '等待中';

                    row.innerHTML = `
                        <td>${task.task_id}</td>
                        <td>${task.video.split('/').pop()}</td>
                        <td>${task.audio.split('/').pop()}</td>
                        <td><span class="status ${statusClass}">${task.status}</span></td>
                        <td>${downloadButton}</td>
                    `;
                    taskList.appendChild(row);
                });
            })
            .catch(error => {
                console.error("Error fetching tasks:", error);
                showAlert("加载任务失败，请重试", true);
            });
    }

// 上传文件
document.getElementById("uploadForm").addEventListener("submit", function(event) {
    event.preventDefault();

    const formData = new FormData();
    formData.append("video", document.getElementById("video").files[0]);
    formData.append("audio", document.getElementById("audio").files[0]);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.task_id) {
            // 上传成功，更新任务列表
            document.getElementById("uploadStatus").innerText = `上传成功! 任务ID: ${data.task_id}`;

            // 创建新任务行
            const taskRow = document.createElement("tr");

            // 创建任务ID列
            const taskIdCell = document.createElement("td");
            taskIdCell.textContent = data.task_id;
            taskRow.appendChild(taskIdCell);

            // 创建视频文件列
            const videoCell = document.createElement("td");
            videoCell.textContent = document.getElementById("video").files[0].name;
            taskRow.appendChild(videoCell);

            // 创建音频文件列
            const audioCell = document.createElement("td");
            audioCell.textContent = document.getElementById("audio").files[0].name;
            taskRow.appendChild(audioCell);

            // 创建状态列
            const statusCell = document.createElement("td");
            statusCell.textContent = "等待处理"; // 初始状态
            taskRow.appendChild(statusCell);

            // 创建下载按钮列
            const actionCell = document.createElement("td");
            const downloadButton = document.createElement("button");
            downloadButton.textContent = "下载";
            downloadButton.disabled = true;  // 初始状态下不能下载
            actionCell.appendChild(downloadButton);
            taskRow.appendChild(actionCell);

            // 添加任务行到任务列表
            document.querySelector("#taskList tbody").appendChild(taskRow);
        } else {
            document.getElementById("uploadStatus").innerText = `上传失败: ${data.error}`;
        }
    })
    .catch(error => {
        document.getElementById("uploadStatus").innerText = `上传出错: ${error}`;
    });
});

// 更新任务状态
function updateTaskStatus(taskId, status) {
    const rows = document.querySelectorAll("#taskList tbody tr");
    rows.forEach(row => {
        const taskCell = row.querySelector("td:first-child");
        if (taskCell.textContent === taskId) {
            const statusCell = row.querySelector("td:nth-child(4)");
            const downloadButton = row.querySelector("button");

            statusCell.textContent = status;

            // 如果任务完成，启用下载按钮
            if (status === "completed") {
                downloadButton.disabled = false;
            }
        }
    });
}

// 每隔一段时间查询任务状态并更新页面
setInterval(() => {
    fetch('/check_tasks')
        .then(response => response.json())
        .then(data => {
            data.tasks.forEach(task => {
                updateTaskStatus(task.task_id, task.status);
            });
        });
}, 10000); // 每5秒检查一次任务状态
