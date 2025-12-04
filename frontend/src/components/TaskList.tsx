import React from 'react';
import { PageGenerationTask } from '../types';

interface Props {
  tasks: PageGenerationTask[];
  onStart: (id: string) => Promise<void>;
  onCancel: (id: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onSelect: (task: PageGenerationTask) => void;
  selectedTaskId?: string;
}

export const TaskList: React.FC<Props> = ({
  tasks,
  onStart,
  onCancel,
  onDelete,
  onSelect,
  selectedTaskId,
}) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return '#4caf50';
      case 'running': return '#2196f3';
      case 'failed': return '#f44336';
      case 'cancelled': return '#9e9e9e';
      default: return '#ff9800';
    }
  };

  if (tasks.length === 0) {
    return <p className="no-tasks">No tasks yet. Create one above!</p>;
  }

  return (
    <div className="task-list">
      <h2>Tasks</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Pages</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Created/Failed</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr
              key={task.id}
              onClick={() => onSelect(task)}
              className={selectedTaskId === task.id ? 'selected' : ''}
            >
              <td>{task.base_page_name}</td>
              <td>{task.num_pages}</td>
              <td>
                <span
                  className="status-badge"
                  style={{ backgroundColor: getStatusColor(task.status) }}
                >
                  {task.status}
                </span>
              </td>
              <td>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${task.progress}%` }}
                  />
                  <span>{task.progress}%</span>
                </div>
              </td>
              <td>
                {task.pages_created}/{task.pages_failed}
              </td>
              <td className="actions">
                {task.status === 'pending' && (
                  <button onClick={(e) => { e.stopPropagation(); onStart(task.id); }}>
                    Start
                  </button>
                )}
                {task.status === 'running' && (
                  <button onClick={(e) => { e.stopPropagation(); onCancel(task.id); }}>
                    Cancel
                  </button>
                )}
                {['completed', 'failed', 'cancelled'].includes(task.status) && (
                  <button
                    className="delete"
                    onClick={(e) => { e.stopPropagation(); onDelete(task.id); }}
                  >
                    Delete
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
