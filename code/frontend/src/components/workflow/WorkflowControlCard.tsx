import {
  CheckCircleOutlined,
  CheckOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
  UserSwitchOutlined,
} from '@ant-design/icons';
import { Button, Tag } from 'antd';
import type { WorkflowCheckpoint, WorkflowDefinition } from '../../api/contracts';

const NODE_LABELS: Record<string, string> = {
  load_enterprise: '企业加载',
  build_profile: '企业画像',
  quality_check: '质量审查',
  evidence_review: '证据复核',
  follow_up: '补问',
  human_review: '人工确认',
};

function statusLabel(status: WorkflowCheckpoint['status']): string {
  return {
    running: '运行中',
    paused: '已暂停',
    waiting_for_input: '待补充',
    waiting_human_review: '待人工确认',
    completed: '已完成',
  }[status];
}

function statusClass(status: WorkflowCheckpoint['status']): string {
  return `workflow-status workflow-status-${status}`;
}

export function WorkflowControlCard({
  definitions,
  workflows,
  busy,
  onStart,
  onPause,
  onResume,
  onReview,
}: {
  definitions: WorkflowDefinition[];
  workflows: WorkflowCheckpoint[];
  busy: string | null;
  onStart: (workflowName: WorkflowCheckpoint['workflow_name']) => void;
  onPause: (workflow: WorkflowCheckpoint) => void;
  onResume: (workflow: WorkflowCheckpoint, confirmNoAdditional: boolean) => void;
  onReview: (workflow: WorkflowCheckpoint, decision: 'approve' | 'request_changes') => void;
}) {
  return (
    <div className="workflow-card" aria-label="M4可暂停评估流程">
      <div className="workflow-card-header">
        <div className="workflow-card-title"><SafetyCertificateOutlined /><span>M4 流程控制</span><Tag bordered={false}>LangGraph</Tag></div>
        <span className="workflow-card-caption">状态会按当前运行保存</span>
      </div>
      <p className="workflow-card-notice">可运行多节点审查流程；暂停、恢复和人工确认不会改变企业事实、规则或参考对照层。</p>
      {definitions.some((definition) => !workflows.some((workflow) => workflow.workflow_name === definition.workflow_name)) && (
        <div className="workflow-start-grid">
          {definitions.filter((definition) => !workflows.some((workflow) => workflow.workflow_name === definition.workflow_name)).map((definition) => (
            <div className="workflow-start-item" key={definition.workflow_name}>
              <div><strong>{definition.label}</strong><small>{definition.description}</small></div>
              <Button size="small" icon={<PlayCircleOutlined />} loading={busy === `start:${definition.workflow_name}`} onClick={() => onStart(definition.workflow_name)}>启动</Button>
            </div>
          ))}
        </div>
      )}
      {workflows.map((workflow) => {
        const completedNodes = workflow.state.completed_nodes ?? [];
        const questions = workflow.state.follow_up_questions ?? [];
        const actionKey = `${workflow.workflow_name}:${workflow.status}`;
        return (
          <div className="workflow-run" key={workflow.workflow_name}>
            <div className="workflow-run-head">
              <div><strong>{definitions.find((item) => item.workflow_name === workflow.workflow_name)?.label ?? workflow.workflow_name}</strong><small>检查点 v{workflow.version} · 线程已绑定当前运行</small></div>
              <span className={statusClass(workflow.status)}>{statusLabel(workflow.status)}</span>
            </div>
            <div className="workflow-node-strip">
              {(definitions.find((item) => item.workflow_name === workflow.workflow_name)?.nodes ?? []).map((node) => <span className={completedNodes.includes(node) ? 'workflow-node done' : node === workflow.current_node ? 'workflow-node current' : 'workflow-node'} key={node}>{completedNodes.includes(node) ? <CheckCircleOutlined /> : <span className="workflow-node-dot" />}{NODE_LABELS[node] ?? node}</span>)}
            </div>
            {questions.length > 0 && <div className="workflow-question"><UserSwitchOutlined /><span>{questions[0]}</span></div>}
            {workflow.state.pause_reason && <small className="workflow-pause-reason">{workflow.state.pause_reason}</small>}
            <div className="workflow-actions">
              {workflow.status === 'running' && <Button size="small" icon={<PauseOutlined />} loading={busy === actionKey} onClick={() => onPause(workflow)}>暂停</Button>}
              {workflow.status === 'paused' && <Button size="small" type="primary" icon={<SyncOutlined />} loading={busy === actionKey} onClick={() => onResume(workflow, false)}>继续流程</Button>}
              {workflow.status === 'waiting_for_input' && <>
                <Button size="small" type="primary" icon={<SyncOutlined />} loading={busy === actionKey} onClick={() => onResume(workflow, false)}>提交补充回答</Button>
                <Button size="small" loading={busy === actionKey} onClick={() => onResume(workflow, true)}>确认暂不补充</Button>
              </>}
              {workflow.status === 'waiting_human_review' && <>
                <Button size="small" type="primary" icon={<CheckOutlined />} loading={busy === `${workflow.workflow_name}:approve`} onClick={() => onReview(workflow, 'approve')}>人工通过</Button>
                <Button size="small" icon={<UserSwitchOutlined />} loading={busy === `${workflow.workflow_name}:request_changes`} onClick={() => onReview(workflow, 'request_changes')}>要求补充</Button>
              </>}
              {workflow.status === 'completed' && <span className="workflow-complete"><CheckCircleOutlined /> 本流程已完成</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
