/**
 * MyFlowMusic Web UI - Core functionality
 * WebSocket progress, Drag-and-drop, Task management
 */

// Global state
const MFM = {
    ws: null,
    tasks: new Map(),
    reconnectAttempts: 0,
    maxReconnectAttempts: 5
};

/**
 * Initialize WebSocket connection for real-time progress
 */
function initWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/progress`;
    
    MFM.ws = new WebSocket(wsUrl);
    
    MFM.ws.onopen = () => {
        console.log('WebSocket connected');
        MFM.reconnectAttempts = 0;
        updateConnectionStatus('connected');
    };
    
    MFM.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleProgressUpdate(data);
    };
    
    MFM.ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus('disconnected');
        
        // Auto-reconnect
        if (MFM.reconnectAttempts < MFM.maxReconnectAttempts) {
            MFM.reconnectAttempts++;
            setTimeout(initWebSocket, 3000 * MFM.reconnectAttempts);
        }
    };
    
    MFM.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus('error');
    };
}

/**
 * Handle progress update from WebSocket
 */
function handleProgressUpdate(data) {
    const { task_id, status, progress, message } = data;
    
    // Update task in global state
    MFM.tasks.set(task_id, { status, progress, message, updatedAt: Date.now() });
    
    // Update UI elements
    updateTaskProgress(task_id, status, progress, message);
    
    // Show notification for completed tasks
    if (status === 'completed' || status === 'error') {
        showNotification(
            status === 'completed' ? '✅ Задача завершена' : '❌ Ошибка задачи',
            message,
            status === 'completed' ? 'success' : 'error'
        );
    }
}

/**
 * Update task progress UI
 */
function updateTaskProgress(taskId, status, progress, message) {
    // Update progress bars
    const progressBars = document.querySelectorAll(`[data-task-id="${taskId}"]`);
    progressBars.forEach(bar => {
        const fill = bar.querySelector('.progress-fill');
        const text = bar.querySelector('.progress-text');
        const statusEl = bar.querySelector('.task-status');
        
        if (fill) fill.style.width = `${progress || 0}%`;
        if (text) text.textContent = `${progress || 0}%`;
        if (statusEl) {
            statusEl.className = `task-status px-2 py-1 rounded text-xs ${getStatusClass(status)}`;
            statusEl.textContent = getStatusLabel(status);
        }
        
        // Update message
        const msgEl = bar.querySelector('.task-message');
        if (msgEl && message) msgEl.textContent = message;
    });
    
    // Update tasks list if on tasks page
    updateTasksList(taskId, status, progress, message);
}

/**
 * Get status CSS class
 */
function getStatusClass(status) {
    const classes = {
        'running': 'bg-blue-600',
        'completed': 'bg-green-600',
        'error': 'bg-red-600',
        'pending': 'bg-gray-600'
    };
    return classes[status] || 'bg-gray-600';
}

/**
 * Get status label
 */
function getStatusLabel(status) {
    const labels = {
        'running': 'Выполняется',
        'completed': 'Готово',
        'error': 'Ошибка',
        'pending': 'Ожидание'
    };
    return labels[status] || status;
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(status) {
    const indicator = document.getElementById('ws-status');
    if (!indicator) return;
    
    const classes = {
        'connected': 'bg-green-500',
        'disconnected': 'bg-red-500',
        'error': 'bg-yellow-500'
    };
    
    indicator.className = `w-3 h-3 rounded-full ${classes[status] || 'bg-gray-500'}`;
    indicator.title = status === 'connected' ? 'Подключено' : 'Отключено';
}

/**
 * Initialize Drag-and-Drop zone
 */
function initDragAndDrop() {
    const dropZone = document.getElementById('drop-zone');
    if (!dropZone) return;
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-active'), false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-active'), false);
    });
    
    dropZone.addEventListener('drop', handleDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

/**
 * Handle file drop
 */
async function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    
    const dropZone = document.getElementById('drop-zone');
    const uploadList = document.getElementById('upload-list');
    
    for (const file of files) {
        if (file.type.startsWith('audio/')) {
            await uploadFile(file, uploadList);
        } else {
            showNotification('Пропущен файл', `${file.name} не является аудио`, 'warning');
        }
    }
}

/**
 * Upload file with progress
 */
async function uploadFile(file, container) {
    const uploadId = `upload-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // Create upload item UI
    const item = document.createElement('div');
    item.className = 'upload-item bg-gray-800 p-4 rounded mb-2';
    item.id = uploadId;
    item.innerHTML = `
        <div class="flex items-center justify-between mb-2">
            <span class="font-semibold">${file.name}</span>
            <span class="upload-status text-sm text-gray-400">Загрузка...</span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-2">
            <div class="upload-progress bg-green-500 h-2 rounded-full transition-all" style="width: 0%"></div>
        </div>
    `;
    
    if (container) container.appendChild(item);
    
    // Simulate upload progress (real implementation would use XMLHttpRequest)
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            updateUploadProgress(uploadId, 100, 'Готово!');
            showNotification('✅ Файл загружен', file.name, 'success');
        } else {
            throw new Error('Upload failed');
        }
    } catch (error) {
        updateUploadProgress(uploadId, 0, 'Ошибка');
        showNotification('❌ Ошибка загрузки', file.name, 'error');
    }
}

function updateUploadProgress(id, percent, status) {
    const item = document.getElementById(id);
    if (!item) return;
    
    const progress = item.querySelector('.upload-progress');
    const statusEl = item.querySelector('.upload-status');
    
    if (progress) progress.style.width = `${percent}%`;
    if (statusEl) statusEl.textContent = status;
}

/**
 * Show notification toast
 */
function showNotification(title, message, type = 'info') {
    const container = document.getElementById('notifications') || createNotificationContainer();
    
    const toast = document.createElement('div');
    const colors = {
        'success': 'bg-green-600',
        'error': 'bg-red-600',
        'warning': 'bg-yellow-600',
        'info': 'bg-blue-600'
    };
    
    toast.className = `${colors[type] || colors.info} text-white p-4 rounded-lg shadow-lg mb-2 transform transition-all duration-300 translate-x-full`;
    toast.innerHTML = `
        <div class="font-semibold">${title}</div>
        <div class="text-sm opacity-90">${message}</div>
    `;
    
    container.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.remove('translate-x-full'), 10);
    
    // Auto-remove
    setTimeout(() => {
        toast.classList.add('translate-x-full', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'notifications';
    container.className = 'fixed bottom-4 right-4 z-50 w-80';
    document.body.appendChild(container);
    return container;
}

/**
 * Execute workflow action with progress
 */
async function executeAction(action, albumId, options = {}) {
    const endpoint = `/api/albums/${albumId}/${action}`;
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(options)
        });
        
        if (!response.ok) throw new Error('Action failed');
        
        const data = await response.json();
        
        if (data.task_id) {
            showNotification(
                'Задача запущена',
                `${action} для альбома ${albumId}`,
                'info'
            );
            
            // Track this task
            MFM.tasks.set(data.task_id, { 
                status: 'running', 
                progress: 0, 
                message: 'Starting...',
                action,
                albumId
            });
        }
        
        return data;
    } catch (error) {
        showNotification('Ошибка', error.message, 'error');
        throw error;
    }
}

/**
 * Update tasks list on tasks page
 */
function updateTasksList(taskId, status, progress, message) {
    const tasksList = document.getElementById('tasks-list');
    if (!tasksList) return;
    
    let taskEl = tasksList.querySelector(`[data-task="${taskId}"]`);
    
    if (!taskEl) {
        // Create new task element
        taskEl = document.createElement('div');
        taskEl.className = 'task-item bg-gray-800 p-4 rounded mb-2';
        taskEl.setAttribute('data-task', taskId);
        tasksList.prepend(taskEl);
    }
    
    const task = MFM.tasks.get(taskId) || {};
    
    taskEl.innerHTML = `
        <div class="flex items-center justify-between mb-2">
            <div>
                <span class="font-semibold">${task.action || 'Task'}</span>
                <span class="text-gray-400 text-sm ml-2">${task.albumId || ''}</span>
            </div>
            <span class="${getStatusClass(status)} px-2 py-1 rounded text-xs">
                ${getStatusLabel(status)}
            </span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-2 mb-2">
            <div class="bg-blue-500 h-2 rounded-full transition-all" style="width: ${progress || 0}%"></div>
        </div>
        <div class="text-sm text-gray-400">${message || ''}</div>
    `;
}

/**
 * Initialize on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    initDragAndDrop();
    
    // Add global styles for drag state
    const style = document.createElement('style');
    style.textContent = `
        .drag-active {
            border-color: #22c55e !important;
            background-color: rgba(34, 197, 94, 0.1) !important;
        }
    `;
    document.head.appendChild(style);
});

// Export for use in other scripts
window.MFM = MFM;
window.executeAction = executeAction;
window.showNotification = showNotification;
