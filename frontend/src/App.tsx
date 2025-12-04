import { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import { TaskForm } from './components/TaskForm';
import { TaskList } from './components/TaskList';
import { TaskDetail } from './components/TaskDetail';
import { CreatedPagesList } from './components/CreatedPagesList';
import { Benchmark } from './components/Benchmark';
import { TestInvite } from './components/TestInvite';
import { Toast, ToastMessage } from './components/Toast';
import { taskService } from './services/api';
import { PageGenerationTask, CreateTaskRequest } from './types';

type Tab = 'tasks' | 'report' | 'benchmark' | 'test-invite';

function App() {
  const [tasks, setTasks] = useState<PageGenerationTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<PageGenerationTask | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('tasks');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const prevTasksRef = useRef<PageGenerationTask[]>([]);

  const addToast = (type: ToastMessage['type'], message: string) => {
    const id = Date.now().toString();
    setToasts(prev => [...prev, { id, type, message }]);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  const fetchTasks = useCallback(async () => {
    try {
      const data = await taskService.getTasks();
      setTasks(data);

      // Update selected task if it exists
      if (selectedTask) {
        const updated = data.find(t => t.id === selectedTask.id);
        if (updated) setSelectedTask(updated);
      }
    } catch (err) {
      setError('Failed to fetch tasks');
    }
  }, [selectedTask]);

  // Only fetch tasks once on initial load
  useEffect(() => {
    fetchTasks();
  }, []);

  // Only poll when there are active/running tasks
  useEffect(() => {
    const hasActiveTasks = tasks.some(t => t.status === 'running' || t.status === 'pending');
    if (!hasActiveTasks) return;

    const interval = setInterval(fetchTasks, 10000);
    return () => clearInterval(interval);
  }, [tasks, fetchTasks]);

  // Detect page creation failures and show toast notifications
  useEffect(() => {
    const prevTasks = prevTasksRef.current;

    tasks.forEach(task => {
      const prevTask = prevTasks.find(t => t.id === task.id);

      // Check for new failures
      if (prevTask && task.pages_failed > prevTask.pages_failed) {
        const newFailures = task.pages_failed - prevTask.pages_failed;
        addToast('error', `Page creation failed for "${task.base_page_name}" (${newFailures} failed)`);
      }

      // Check for new successes
      if (prevTask && task.pages_created > prevTask.pages_created) {
        const newCreated = task.pages_created - prevTask.pages_created;
        addToast('success', `Page created successfully for "${task.base_page_name}" (${newCreated} created)`);
      }

      // Task completed notification
      if (prevTask && prevTask.status === 'running' && task.status === 'completed') {
        addToast('info', `Task "${task.base_page_name}" completed! Created: ${task.pages_created}, Failed: ${task.pages_failed}`);
      }

      // Task FAILED notification (when automation crashes or Facebook stops working)
      if (prevTask && prevTask.status === 'running' && task.status === 'failed') {
        const errorMsg = task.error_message || 'Unknown error';
        addToast('error', `Task "${task.base_page_name}" FAILED! Error: ${errorMsg}. Created: ${task.pages_created}/${task.num_pages}`);
      }

      // Task cancelled notification
      if (prevTask && prevTask.status === 'running' && task.status === 'cancelled') {
        addToast('warning', `Task "${task.base_page_name}" was cancelled. Created: ${task.pages_created}/${task.num_pages}`);
      }
    });

    prevTasksRef.current = tasks;
  }, [tasks]);

  const handleCreateTask = async (data: CreateTaskRequest) => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const task = await taskService.createTask(data);
      setTasks(prev => [task, ...prev]);
      setSelectedTask(task);
      setSuccess(`Task created! Starting automation for ${task.num_pages} pages with "${task.base_page_name}"...`);

      // Auto-start the task immediately after creation
      try {
        const startedTask = await taskService.startTask(task.id);
        setTasks(prev => prev.map(t => t.id === task.id ? startedTask : t));
        setSelectedTask(startedTask);
        setSuccess(`Automation started! Creating ${task.num_pages} pages with "${task.base_page_name}"`);
      } catch (startErr) {
        setError('Task created but failed to auto-start. Please start manually.');
      }

      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setError('Failed to create task');
    } finally {
      setLoading(false);
    }
  };

  const handleStartTask = async (id: string) => {
    try {
      const task = await taskService.startTask(id);
      setTasks(prev => prev.map(t => t.id === id ? task : t));
      if (selectedTask?.id === id) setSelectedTask(task);
    } catch (err) {
      setError('Failed to start task');
    }
  };

  const handleCancelTask = async (id: string) => {
    try {
      const task = await taskService.cancelTask(id);
      setTasks(prev => prev.map(t => t.id === id ? task : t));
      if (selectedTask?.id === id) setSelectedTask(task);
    } catch (err) {
      setError('Failed to cancel task');
    }
  };

  const handleDeleteTask = async (id: string) => {
    try {
      await taskService.deleteTask(id);
      setTasks(prev => prev.filter(t => t.id !== id));
      if (selectedTask?.id === id) setSelectedTask(null);
    } catch (err) {
      setError('Failed to delete task');
    }
  };

  return (
    <div className="app">
      <Toast toasts={toasts} removeToast={removeToast} />
      <header className="app-header">
        <h1>Page Generator</h1>
        <p>Automated Facebook Page Creation Tool</p>
      </header>

      <nav className="tabs">
        <button
          className={activeTab === 'tasks' ? 'active' : ''}
          onClick={() => setActiveTab('tasks')}
        >
          Tasks
        </button>
        <button
          className={activeTab === 'report' ? 'active' : ''}
          onClick={() => setActiveTab('report')}
        >
          Created Pages
        </button>
        <button
          className={activeTab === 'benchmark' ? 'active' : ''}
          onClick={() => setActiveTab('benchmark')}
        >
          Benchmark
        </button>
        <button
          className={activeTab === 'test-invite' ? 'active' : ''}
          onClick={() => setActiveTab('test-invite')}
        >
          Test Invite
        </button>
      </nav>

      {error && <div className="error-banner">{error}</div>}
      {success && <div className="success-banner">{success}</div>}

      <main className="app-content">
        {activeTab === 'tasks' && (
          <div className="tasks-view">
            <div className="left-panel">
              <TaskForm onSubmit={handleCreateTask} loading={loading} />
              <TaskList
                tasks={tasks}
                onStart={handleStartTask}
                onCancel={handleCancelTask}
                onDelete={handleDeleteTask}
                onSelect={setSelectedTask}
                selectedTaskId={selectedTask?.id}
              />
            </div>
            <div className="right-panel">
              {selectedTask ? (
                <TaskDetail task={selectedTask} />
              ) : (
                <div className="no-selection">
                  <p>Select a task to view details</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'report' && <CreatedPagesList />}
        {activeTab === 'benchmark' && <Benchmark />}
        {activeTab === 'test-invite' && <TestInvite />}
      </main>
    </div>
  );
}

export default App;
