/**
 * AI Agent Tool Calling - Interactive Frontend Controller
 * Handles chat interactions, calls /api/chat, manages HITL approvals,
 * integrates real LLM provider settings, runs evals, and drives live architecture animations.
 */

// DOM Elements - Chat & Visualizer
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const flowStatus = document.getElementById('flow-status');
const inspectorContent = document.getElementById('inspector-content');
const promptChips = document.querySelectorAll('.prompt-chip');
const clearChatBtn = document.getElementById('clear-chat-btn');
const viewDataBtn = document.getElementById('view-data-btn');
const dataModal = document.getElementById('data-modal');
const modalCloseBtn = document.getElementById('modal-close-btn');
const modalCodeViewer = document.getElementById('modal-code-viewer');
const tabButtons = document.querySelectorAll('.tab-btn');
const memoryBadgeText = document.getElementById('memory-badge-text');

// DOM Elements - LLM Settings Modal
const llmSettingsBtn = document.getElementById('llm-settings-btn');
const llmBadgeText = document.getElementById('llm-badge-text');
const llmModal = document.getElementById('llm-modal');
const llmModalCloseBtn = document.getElementById('llm-modal-close-btn');
const llmProviderSelect = document.getElementById('llm-provider-select');
const llmApiKey = document.getElementById('llm-api-key');
const llmModelName = document.getElementById('llm-model-name');
const llmSaveBtn = document.getElementById('llm-save-btn');
const llmStatusDetails = document.getElementById('llm-status-details');

// DOM Elements - Evals Benchmarking Modal
const runEvalsBtn = document.getElementById('run-evals-btn');
const evalsModal = document.getElementById('evals-modal');
const evalsModalCloseBtn = document.getElementById('evals-modal-close-btn');
const runEvalsActionBtn = document.getElementById('run-evals-action-btn');
const evalTableBody = document.getElementById('eval-table-body');

let currentSessionId = 'sess_' + Math.random().toString(36).substring(2, 9);
let cachedMockData = null;

// Architecture Diagram Nodes
const nodes = {
  user: document.getElementById('node-user'),
  inputGuardrail: document.getElementById('node-input-guardrail'),
  memory: document.getElementById('node-memory'),
  agent1: document.getElementById('node-agent-1'),
  selector: document.getElementById('node-selector'),
  hitl: document.getElementById('node-hitl'),
  crm: document.getElementById('node-crm'),
  crmKb: document.getElementById('node-crm-kb'),
  db: document.getElementById('node-db'),
  cancel: document.getElementById('node-cancel'),
  itsm: document.getElementById('node-itsm'),
  escalate: document.getElementById('node-escalate'),
  agent2: document.getElementById('node-agent-2'),
  outputGuardrail: document.getElementById('node-output-guardrail'),
  final: document.getElementById('node-final')
};

const arrows = {
  arrow0: document.getElementById('arrow-0'),
  arrow1: document.getElementById('arrow-1'),
  arrowMem: document.getElementById('arrow-mem'),
  arrow2: document.getElementById('arrow-2'),
  arrowHitl: document.getElementById('arrow-hitl'),
  branch: document.getElementById('branch-arrow'),
  converge: document.getElementById('converge-arrow'),
  arrow5: document.getElementById('arrow-5'),
  arrow6: document.getElementById('arrow-6')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  fetchMockData();
  fetchLLMStatus();
});

function setupEventListeners() {
  chatForm.addEventListener('submit', handleChatSubmit);

  promptChips.forEach(chip => {
    chip.addEventListener('click', () => {
      userInput.value = chip.getAttribute('data-prompt');
      userInput.focus();
      handleChatSubmit(new Event('submit'));
    });
  });

  const resetViewBtn = document.getElementById('reset-view-btn');
  if (resetViewBtn) {
    resetViewBtn.addEventListener('click', () => {
      const visualizerSection = document.getElementById('visualizer-section');
      if (visualizerSection) {
        visualizerSection.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  }

  // Chat Scroll Navigation
  const scrollTopBtn = document.getElementById('scroll-top-btn');
  if (scrollTopBtn) {
    scrollTopBtn.addEventListener('click', () => {
      chatMessages.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  const scrollBottomBtn = document.getElementById('scroll-bottom-btn');
  if (scrollBottomBtn) {
    scrollBottomBtn.addEventListener('click', () => {
      chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
    });
  }

  clearChatBtn.addEventListener('click', () => {
    chatMessages.innerHTML = '';
    resetDiagram();
    inspectorContent.textContent = 'Conversation cleared. Type a question or click a prompt above.';
    const visualizerSection = document.getElementById('visualizer-section');
    if (visualizerSection) {
      visualizerSection.scrollTo({ top: 0, behavior: 'smooth' });
    }
    // Clear session memory on server
    fetch('/api/session/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: '', session_id: currentSessionId })
    });
    if (memoryBadgeText) memoryBadgeText.textContent = 'Memory: Fresh';
  });

  // Mock Data Modal
  viewDataBtn.addEventListener('click', () => {
    dataModal.classList.remove('hidden');
    renderActiveTab('crm-tab');
  });

  modalCloseBtn.addEventListener('click', () => {
    dataModal.classList.add('hidden');
  });

  dataModal.addEventListener('click', (e) => {
    if (e.target === dataModal) dataModal.classList.add('hidden');
  });

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderActiveTab(btn.getAttribute('data-tab'));
    });
  });

  // LLM Settings Modal
  if (llmSettingsBtn) {
    llmSettingsBtn.addEventListener('click', openLLMModal);
  }
  if (llmModalCloseBtn) {
    llmModalCloseBtn.addEventListener('click', () => llmModal.classList.add('hidden'));
  }
  if (llmModal) {
    llmModal.addEventListener('click', (e) => {
      if (e.target === llmModal) llmModal.classList.add('hidden');
    });
  }
  if (llmProviderSelect) {
    llmProviderSelect.addEventListener('change', handleProviderChange);
  }
  if (llmSaveBtn) {
    llmSaveBtn.addEventListener('click', handleSaveLLMConfig);
  }

  // Evals Modal
  if (runEvalsBtn) {
    runEvalsBtn.addEventListener('click', openEvalsModal);
  }
  if (evalsModalCloseBtn) {
    evalsModalCloseBtn.addEventListener('click', () => evalsModal.classList.add('hidden'));
  }
  if (evalsModal) {
    evalsModal.addEventListener('click', (e) => {
      if (e.target === evalsModal) evalsModal.classList.add('hidden');
    });
  }
  if (runEvalsActionBtn) {
    runEvalsActionBtn.addEventListener('click', executeEvalsBenchmark);
  }
}

/**
 * Handle user query submission
 */
async function handleChatSubmit(e) {
  e.preventDefault();
  const query = userInput.value.trim();
  if (!query) return;

  userInput.value = '';
  userInput.disabled = true;
  sendBtn.disabled = true;

  // Append User message to UI
  appendUserMessage(query);

  // Fresh visualizer reset on every user ask
  resetDiagram();
  const visualizerSection = document.getElementById('visualizer-section');
  if (visualizerSection) {
    visualizerSection.scrollTo({ top: 0, behavior: 'smooth' });
  }

  activateNode(nodes.user, '👤 Receiving user query...', 'Input Phase: User prompt is ingested by the agent runtime.');
  setFlowStatus('Processing', 'accent-amber');

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        message: query,
        session_id: currentSessionId
      })
    });

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const data = await response.json();

    // Update memory badge display
    updateMemoryBadge(data.session_context);

    // Run stepped visual playback of the architecture diagram
    await playArchitectureTrace(data);

    // Append Assistant response with internal reasoning trace and HITL buttons
    appendAssistantMessage(data);

  } catch (err) {
    console.warn('API call failed, running local educational fallback:', err);
    const fallbackData = simulateAgentLocally(query);
    await playArchitectureTrace(fallbackData);
    appendAssistantMessage(fallbackData);
  } finally {
    userInput.disabled = false;
    sendBtn.disabled = false;
    userInput.focus();
    setFlowStatus('Idle', 'accent-emerald');
  }
}

/**
 * Handle HITL Approve or Reject decision
 */
window.handleHITLDecision = async function(decision, btnElement) {
  const isApprove = decision === 'approve';
  const parentCard = btnElement ? btnElement.closest('.hitl-confirm-card') : null;

  if (parentCard) {
    const actionContainer = parentCard.querySelector('.hitl-actions');
    if (actionContainer) {
      actionContainer.innerHTML = isApprove
        ? `<span class="hitl-resolved-badge hitl-resolved-approved">✅ Action Authorized by Human Reviewer</span>`
        : `<span class="hitl-resolved-badge hitl-resolved-rejected">❌ Action Rejected & Aborted by Human Reviewer</span>`;
    }
  }

  // Append User confirmation to chat
  const confirmMsg = isApprove ? "Yes, proceed with execution" : "No, abort this action";
  appendUserMessage(confirmMsg);

  resetDiagram();
  const visualizerSection = document.getElementById('visualizer-section');
  if (visualizerSection) {
    visualizerSection.scrollTo({ top: 0, behavior: 'smooth' });
  }

  activateNode(nodes.user, '👤 Human Decision Ingested', `Reviewer response: "<strong>${escapeHtml(confirmMsg)}</strong>"`);
  setFlowStatus('Executing Decision', 'accent-amber');

  try {
    const res = await fetch('/api/chat/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        decision: decision,
        session_id: currentSessionId
      })
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    updateMemoryBadge(data.session_context);
    await playArchitectureTrace(data);
    appendAssistantMessage(data);

  } catch (err) {
    console.error('Failed to submit HITL decision:', err);
    appendAssistantMessage({
      user_query: confirmMsg,
      intent: "hitl_decision",
      tool_selected: null,
      tool_result: null,
      final_answer: `⚠️ Failed to communicate decision with server: ${err.message}`,
      steps: []
    });
  } finally {
    setFlowStatus('Idle', 'accent-emerald');
  }
};

/**
 * Update the header badge showing active entities stored in memory
 */
function updateMemoryBadge(context) {
  if (!memoryBadgeText) return;
  if (!context || Object.keys(context).length === 0) {
    memoryBadgeText.textContent = 'Memory: Active';
    return;
  }
  const parts = [];
  if (context.customer_name) parts.push(`🏢 ${context.customer_name}`);
  if (context.order_id) parts.push(`📦 ${context.order_id}`);
  if (context.ticket_id) parts.push(`🎫 ${context.ticket_id}`);
  memoryBadgeText.textContent = parts.length > 0 ? parts.join(' | ') : 'Memory: Active';
}

/**
 * Animate the diagram matching the agent architecture
 */
async function playArchitectureTrace(agentResponse) {
  const wait = ms => new Promise(r => setTimeout(r, ms));

  // Step 1: User Input
  activateNode(nodes.user, '1. User Input Received', `Query: "${escapeHtml(agentResponse.user_query)}"`);
  activateArrow(arrows.arrow0);
  await wait(300);

  // Step 2: Input Guardrail Check
  if (agentResponse.guardrail_blocked) {
    if (nodes.inputGuardrail) {
      nodes.inputGuardrail.classList.add('active-node', 'blocked');
    }
    inspectorContent.innerHTML = `<strong>🛡️ Input Guardrail Alert: Request Blocked</strong><br><span style="color: #e11d48; font-weight: 600;">Potential prompt injection or destructive command detected!</span><br>Pipeline terminated immediately to protect enterprise tools and databases.`;
    setFlowStatus('Blocked by Guardrail', 'accent-red');
    return;
  }

  // Passed Input Guardrail
  if (nodes.inputGuardrail) {
    nodes.inputGuardrail.classList.add('active-node', 'passed');
  }
  inspectorContent.innerHTML = `<strong>🛡️ Input Guardrail Passed</strong><br>Prompt verified safe against injection attacks, SQL threats, and malicious syntax.`;
  activateArrow(arrows.arrow1);
  await wait(350);

  // Step 2b: Session Memory Context Resolution
  if (nodes.memory) {
    const memStep = (agentResponse.steps || []).find(s => s.phase === 'session_memory');
    const wasResolved = memStep && memStep.title && memStep.title.includes('Context Resolved');
    nodes.memory.classList.add('active-node');
    const sub = document.getElementById('node-memory-sub');
    if (wasResolved) {
      nodes.memory.classList.add('tool-selected');
      if (sub && memStep.data && memStep.data.resolved_query) {
        sub.textContent = `Resolved: "${memStep.data.resolved_query.substring(0, 26)}..."`;
      }
    }
    
    const activeCtx = agentResponse.session_context;
    const ctxString = activeCtx && Object.keys(activeCtx).length > 0
      ? `<br><span style="font-size: 0.8rem; color: #7c3aed;"><strong>Active Session Entities:</strong> ${escapeHtml(JSON.stringify(activeCtx))}</span>`
      : `<br><span style="font-size: 0.8rem; color: #64748b;">(Fresh context buffer)</span>`;

    inspectorContent.innerHTML = `<strong>🧠 Session Memory Check</strong><br>` +
      (memStep ? escapeHtml(memStep.description) : 'Checking conversational history for pronoun references.') +
      ctxString;
  }
  activateArrow(arrows.arrowMem);
  await wait(350);

  // Step 3: AI Agent (Understand Intent)
  activateNode(nodes.agent1, '2. AI Agent: Understand Intent', 
    `Intent Detected: <strong>${escapeHtml(agentResponse.intent)}</strong>.<br>` +
    `The Agent reasons over the user prompt to determine if external systems are needed.`
  );
  activateArrow(arrows.arrow2);
  await wait(400);

  // Step 4: Tool Selector
  const toolName = agentResponse.tool_selected;
  const toolParams = agentResponse.tool_input ? JSON.stringify(agentResponse.tool_input) : '{}';
  
  activateNode(nodes.selector, '3. Tool Selector Routing', 
    toolName 
      ? `Selected Tool: <strong>${escapeHtml(toolName)}</strong><br>Arguments Extracted: <code>${escapeHtml(toolParams)}</code>`
      : `No tool needed. Direct conversation mode activated.`
  );
  activateArrow(arrows.arrowHitl);
  await wait(400);

  // Step 4b: HITL Governance Gate
  if (nodes.hitl) {
    if (agentResponse.requires_confirmation) {
      nodes.hitl.classList.add('active-node', 'gated');
      inspectorContent.innerHTML = `<strong>⚠️ HITL Governance Alert: High-Impact Write Action Gated</strong><br>` +
        `The Agent requested to execute write operation: <strong>${escapeHtml(agentResponse.pending_action?.tool || 'Write Tool')}</strong>.<br>` +
        `<span style="color: #b45309; font-weight: 600;">Execution suspended pending explicit human confirmation to safeguard enterprise records.</span>`;
      setFlowStatus('Awaiting Human Approval', 'accent-amber');
      return; // Stop animation here until human approves!
    } else {
      nodes.hitl.classList.add('active-node', 'approved');
      inspectorContent.innerHTML = `<strong>👤✋ HITL Approval Gate Passed</strong><br>` +
        (agentResponse.intent === 'hitl_approval' 
          ? `High-impact action confirmed and authorized by human.` 
          : `Read-only action verified safe for automated execution.`);
    }
  }
  activateArrow(arrows.branch);
  await wait(400);

  // Step 5: Specific Tool Execution
  if (toolName) {
    if (toolName === 'crm_tool') {
      activateToolNode(nodes.crm, '4. Executing CRM Tool (Tool RAG)', 'Querying live Customer Accounts & Contacts...');
    } else if (toolName === 'crm_kb_tool') {
      activateToolNode(nodes.crmKb, '4. Executing CRM KB Tool (Vector RAG)', 'Performing semantic similarity search over unstructured CRM policies & SLAs...');
    } else if (toolName === 'db_tool') {
      activateToolNode(nodes.db, '4. Executing DB Tool (Read)', 'Querying Database for Orders & Inventory...');
    } else if (toolName === 'cancel_order_tool') {
      activateToolNode(nodes.cancel, '4. Executing Cancel Order Tool (DB Write)', 'Authorized write committed: Order status updated to Cancelled.');
    } else if (toolName === 'itsm_tool') {
      activateToolNode(nodes.itsm, '4. Executing ITSM Tool (Read)', 'Querying Service Management Incidents & Tickets...');
    } else if (toolName === 'escalate_ticket_tool') {
      activateToolNode(nodes.escalate, '4. Executing Escalate Ticket Tool (ITSM Write)', 'Authorized write committed: Incident priority elevated and manager paged.');
    }
    await wait(550);

    // Step 5b: Tool Results back to Agent
    activateArrow(arrows.converge);
    inspectorContent.innerHTML = `<strong>4. Tool Results Gathered</strong><br><pre class="trace-step-json">${JSON.stringify(agentResponse.tool_result, null, 2)}</pre>`;
    await wait(500);
  }

  // Step 6: AI Agent Synthesis
  activateNode(nodes.agent2, '5. AI Agent: Synthesize Final Answer', 
    'Combining user query context with raw tool results to generate a concise, human-readable answer.'
  );
  activateArrow(arrows.arrow5);
  await wait(450);

  // Step 7: Output Guardrail Check
  if (nodes.outputGuardrail) {
    nodes.outputGuardrail.classList.add('active-node', 'passed');
  }
  inspectorContent.innerHTML = `<strong>🛡️ Output Guardrail Verified</strong><br>Checked final answer against sensitive data leaks, redacted PII (credit cards/SSNs), and validated response safety.`;
  activateArrow(arrows.arrow6);
  await wait(400);

  // Step 8: Final Answer
  activateNode(nodes.final, '6. Final Answer Presented', 'Delivering sanitized answer to user interface.');
  await wait(250);
}

/**
 * Visual Helpers
 */
function resetDiagram() {
  Object.values(nodes).forEach(node => {
    if (node) {
      node.classList.remove('active-node', 'tool-selected', 'passed', 'blocked', 'gated', 'approved');
    }
  });
  Object.values(arrows).forEach(arrow => {
    if (arrow) arrow.classList.remove('active-arrow');
  });
  const memSub = document.getElementById('node-memory-sub');
  if (memSub) memSub.textContent = 'Multi-Turn Entity Tracking';
}

function activateNode(node, title, inspectorHtml) {
  if (!node) return;
  node.classList.add('active-node');
  inspectorContent.innerHTML = `<strong>${title}</strong><br>${inspectorHtml}`;
  node.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function activateToolNode(node, title, desc) {
  if (!node) return;
  node.classList.add('active-node', 'tool-selected');
  inspectorContent.innerHTML = `<strong>${title}</strong><br>${desc}`;
  node.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function activateArrow(arrow) {
  if (arrow) arrow.classList.add('active-arrow');
}

function setFlowStatus(text, colorVar) {
  if (flowStatus) flowStatus.textContent = text;
}

/**
 * Message Rendering
 */
function appendUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'message-row user';
  row.innerHTML = `
    <div class="avatar">👤</div>
    <div class="message-content">
      <div class="bubble"><p>${escapeHtml(text)}</p></div>
    </div>
  `;
  chatMessages.appendChild(row);
  scrollToBottom();
}

function appendAssistantMessage(data) {
  const row = document.createElement('div');
  row.className = 'message-row assistant';

  const toolBadge = data.tool_selected 
    ? `<span class="trace-badge">Tool: ${data.tool_selected}</span>`
    : `<span class="trace-badge" style="background: rgba(148,163,184,0.15); color: #cbd5e1;">Direct AI</span>`;

  // Render markdown-like simple formatting for final answer
  const formattedAnswer = formatMarkdown(data.final_answer);

  // If requires confirmation, render HITL action confirmation card
  let hitlCardHtml = '';
  if (data.requires_confirmation && data.pending_action) {
    const action = data.pending_action;
    hitlCardHtml = `
      <div class="hitl-confirm-card">
        <div class="hitl-header">
          <span>✋ Human-in-the-Loop Authorization Required</span>
        </div>
        <div class="hitl-details">
          <strong>Proposed Write:</strong> ${escapeHtml(action.tool || 'Write Operation')}<br>
          <strong>Target Parameters:</strong> <code>${escapeHtml(JSON.stringify(action.params || {}))}</code><br>
          <strong>Impact Assessment:</strong> <span style="color: #b45309; font-weight: 700;">HIGH IMPACT (Data Mutation)</span>
        </div>
        <div class="hitl-actions">
          <button class="hitl-btn-approve" onclick="handleHITLDecision('approve', this)">
            <span>✅ Approve & Execute</span>
          </button>
          <button class="hitl-btn-reject" onclick="handleHITLDecision('reject', this)">
            <span>❌ Reject & Abort</span>
          </button>
        </div>
      </div>
    `;
  }

  // Steps breakdown
  const stepsHtml = (data.steps || []).map(s => `
    <div class="trace-step-item">
      <div class="trace-step-title">${escapeHtml(s.title)}</div>
      <div class="trace-step-desc">${escapeHtml(s.description)}</div>
      ${s.data && s.data.raw_result ? `<pre class="trace-step-json">${JSON.stringify(s.data.raw_result, null, 2)}</pre>` : ''}
    </div>
  `).join('');

  row.innerHTML = `
    <div class="avatar">🤖</div>
    <div class="message-content">
      <div class="bubble">
        ${formattedAnswer}
        ${hitlCardHtml}
      </div>
      
      <div class="trace-accordion">
        <details>
          <summary class="trace-summary">
            <span>⚙️ Internal Agent Execution Trace</span>
            ${toolBadge}
          </summary>
          <div class="trace-body">
            <div style="font-size: 0.76rem; color: #94a3b8; margin-bottom: 4px;">
              <strong>Architecture Path:</strong> User ➔ Intent [${escapeHtml(data.intent)}] ➔ Selector [${data.tool_selected || 'None'}] ➔ Governance ➔ Execution ➔ Synthesis
            </div>
            ${stepsHtml}
          </div>
        </details>
      </div>
    </div>
  `;

  chatMessages.appendChild(row);
  scrollToBottom();
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
  if (!text) return '';
  let html = text
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n• /g, '<br>• ')
    .replace(/\n/g, '<br>');
  return `<p>${html}</p>`;
}

/**
 * Fetch and View Mock Database
 */
async function fetchMockData() {
  try {
    const res = await fetch('/api/tools');
    if (res.ok) {
      cachedMockData = await res.json();
    }
  } catch (e) {
    console.log('Using default mock explorer data.');
  }
}

function renderActiveTab(tabId) {
  if (!cachedMockData) {
    modalCodeViewer.textContent = "Loading or server offline. Mock databases available in tools/ directory.";
    return;
  }

  if (tabId === 'crm-tab') {
    modalCodeViewer.textContent = JSON.stringify(cachedMockData.mock_data.crm_accounts || cachedMockData.mock_data.crm, null, 2);
  } else if (tabId === 'crm-kb-tab') {
    modalCodeViewer.textContent = JSON.stringify(cachedMockData.mock_data.crm_policies_vector_rag, null, 2);
  } else if (tabId === 'db-tab') {
    modalCodeViewer.textContent = JSON.stringify(cachedMockData.mock_data.db, null, 2);
  } else if (tabId === 'itsm-tab') {
    modalCodeViewer.textContent = JSON.stringify(cachedMockData.mock_data.itsm, null, 2);
  } else if (tabId === 'schemas-tab') {
    modalCodeViewer.textContent = JSON.stringify(cachedMockData.schemas, null, 2);
  }
}

/**
 * LLM Configuration Management
 */
async function fetchLLMStatus() {
  try {
    const res = await fetch('/api/llm/status');
    if (res.ok) {
      const status = await res.json();
      updateLLMUI(status);
    }
  } catch (e) {
    console.log('LLM status fetch fallback');
  }
}

function updateLLMUI(status) {
  if (llmBadgeText) {
    if (status.provider === 'gemini') {
      llmBadgeText.textContent = `🤖 LLM: Gemini (${status.model})`;
    } else if (status.provider === 'openai') {
      llmBadgeText.textContent = `🤖 LLM: OpenAI (${status.model})`;
    } else {
      llmBadgeText.textContent = '🤖 LLM: Standalone';
    }
  }
  if (llmStatusDetails) {
    llmStatusDetails.innerHTML = `
      Provider: <strong>${escapeHtml(status.provider)}</strong> | Model: <strong>${escapeHtml(status.model)}</strong><br>
      API Key Configured: <strong>${status.api_key_configured ? 'Yes (Active)' : 'No (Offline Fallback)'}</strong>
    `;
  }
  if (llmProviderSelect) {
    llmProviderSelect.value = status.provider;
  }
  if (llmModelName && status.model) {
    llmModelName.value = status.model;
  }
}

function openLLMModal() {
  llmModal.classList.remove('hidden');
  fetchLLMStatus();
}

function handleProviderChange() {
  const p = llmProviderSelect.value;
  if (p === 'gemini') {
    llmModelName.value = 'gemini-2.5-flash';
    llmApiKey.placeholder = 'Enter Google Gemini API Key (AIzaSy...)';
  } else if (p === 'openai') {
    llmModelName.value = 'gpt-4o-mini';
    llmApiKey.placeholder = 'Enter OpenAI API Key (sk-...)';
  } else {
    llmModelName.value = 'standalone-intent-classifier';
    llmApiKey.placeholder = 'No API key needed for built-in heuristic engine';
  }
}

async function handleSaveLLMConfig() {
  const provider = llmProviderSelect.value;
  const apiKey = llmApiKey.value.trim() || null;
  const model = llmModelName.value.trim() || null;

  llmSaveBtn.disabled = true;
  llmSaveBtn.textContent = 'Saving...';
  try {
    const res = await fetch('/api/llm/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: apiKey, model })
    });
    if (res.ok) {
      const status = await res.json();
      updateLLMUI(status);
      llmModal.classList.add('hidden');
      alert(`LLM provider updated to: ${status.provider} (${status.model})`);
    } else {
      throw new Error(`Server returned HTTP ${res.status}`);
    }
  } catch (e) {
    alert('Failed to update LLM configuration: ' + e.message);
  } finally {
    llmSaveBtn.disabled = false;
    llmSaveBtn.textContent = 'Save & Apply Configuration';
  }
}

/**
 * Evals Benchmarking Modal & Execution
 */
function openEvalsModal() {
  evalsModal.classList.remove('hidden');
}

async function executeEvalsBenchmark() {
  runEvalsActionBtn.disabled = true;
  runEvalsActionBtn.textContent = '⏳ Running 12 Gold Tests...';
  evalTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">Executing automated benchmark suite across Tool Selection, Faithfulness, Guardrails, and Memory...</td></tr>`;

  try {
    const res = await fetch('/api/evals/run', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const scorecard = await res.json();

    // Render Metrics
    const overallScore = scorecard.overall_accuracy_pct ?? 100;
    const passedCount = scorecard.passed ?? scorecard.total_tests;
    const totalCount = scorecard.total_tests ?? 12;
    const toolAcc = scorecard.category_breakdown?.tool_selection?.accuracy_pct ?? 100;
    const faithAcc = (scorecard.category_breakdown?.faithfulness?.accuracy_pct || scorecard.category_breakdown?.faithfulness_detection?.accuracy_pct) ?? 100;
    const guardAcc = scorecard.category_breakdown?.input_guardrail?.accuracy_pct ?? 100;
    const avgLatency = scorecard.avg_latency_ms ?? 0.58;

    document.getElementById('eval-score-val').textContent = `${Number(overallScore).toFixed(1)}%`;
    document.getElementById('eval-passed-count').textContent = `${passedCount} of ${totalCount} passed`;
    document.getElementById('eval-tool-val').textContent = `${Number(toolAcc).toFixed(1)}%`;
    document.getElementById('eval-faith-val').textContent = `${Number(faithAcc).toFixed(1)}%`;
    document.getElementById('eval-guard-val').textContent = `${Number(guardAcc).toFixed(1)}%`;
    document.getElementById('eval-latency-val').textContent = `${Number(avgLatency).toFixed(2)} ms`;

    // Render Table Rows
    const items = scorecard.detailed_results || [];
    evalTableBody.innerHTML = items.map(r => {
      const expTool = r.details?.expected_tool || (r.category === 'input_guardrail' ? 'None (Blocked)' : '(N/A)');
      const actTool = r.details?.selected_tool || r.details?.actual_tool || (r.details?.guardrail_blocked ? 'Blocked by Guardrail' : '(Passed)');
      const matchColor = r.passed ? '#059669' : '#e11d48';

      return `
        <tr>
          <td>
            <span class="${r.passed ? 'badge-pass' : 'badge-fail'}">
              ${r.passed ? '✓ PASS' : '✗ FAIL'}
            </span>
          </td>
          <td><code>${escapeHtml(r.category)}</code></td>
          <td><strong>${escapeHtml(r.description || r.test_id)}</strong></td>
          <td><span style="font-family: var(--font-mono); color: #475569;">${escapeHtml(expTool)}</span></td>
          <td><span style="font-family: var(--font-mono); color: ${matchColor}; font-weight: 600;">${escapeHtml(actTool)}</span></td>
          <td style="font-family: var(--font-mono); font-size: 0.76rem;">${r.latency_ms ? r.latency_ms.toFixed(2) : '0.00'}ms</td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    evalTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #e11d48; padding: 24px;">Failed to run evaluations: ${escapeHtml(err.message)}</td></tr>`;
  } finally {
    runEvalsActionBtn.disabled = false;
    runEvalsActionBtn.textContent = '🔄 Run Full Benchmark';
  }
}

/**
 * Standalone Client-side simulation fallback
 */
function simulateAgentLocally(query) {
  const q = query.toLowerCase();
  let intent = "general_conversation";
  let tool = null;
  let toolInput = {};
  let toolResult = null;
  let finalAnswer = "";

  if (q.includes("cancel") && (q.includes("order") || q.includes("ord-"))) {
    return {
      user_query: query,
      intent: "cancel_order_write",
      tool_selected: "cancel_order_tool",
      tool_input: { order_id: "ORD-9901", reason: "Customer requested cancellation" },
      tool_result: null,
      requires_confirmation: true,
      pending_action: {
        tool: "cancel_order_tool",
        params: { order_id: "ORD-9901", reason: "Customer cancellation request" },
        description: "Cancel order ORD-9901 in the database"
      },
      final_answer: `⚠️ **Action Requires Confirmation**:\nYou are requesting to cancel order **\`ORD-9901\`**.\nThis is a high-impact operation that updates production database state. Please confirm or cancel below.`,
      steps: [
        { phase: "intent_classification", title: "1. Understand Intent", description: "Identified high-impact write intent cancel_order_write." },
        { phase: "tool_selection", title: "2. Tool Selection", description: "Selected tool cancel_order_tool." },
        { phase: "hitl_gate", title: "3. HITL Governance Gate", description: "Action suspended pending human authorization." }
      ]
    };
  } else if (q.includes("crm") || q.includes("acme") || q.includes("stark") || q.includes("customer")) {
    intent = "lookup_customer_crm";
    tool = "crm_tool";
    toolInput = { query: "Acme Corporation" };
    toolResult = {
      status: "success",
      tool: "crm_tool",
      found: true,
      data: {
        id: "CUST-001",
        name: "Acme Corporation",
        contact_person: "Alice Johnson",
        email: "alice@acmecorp.com",
        phone: "+1-555-0192",
        tier: "Enterprise Platinum",
        sales_stage: "Closed Won",
        account_manager: "Sarah Davis"
      }
    };
    finalAnswer = `Here is the record for **Acme Corporation** from the CRM:\n\n• **Customer ID**: \`CUST-001\`\n• **Contact**: Alice Johnson (alice@acmecorp.com)\n• **Tier**: Enterprise Platinum\n• **Sales Stage**: Closed Won\n• **Account Manager**: Sarah Davis`;
  } else {
    finalAnswer = `Hello! I am your AI Agent demonstrating Tool Calling with Human-in-the-Loop governance and Multi-turn memory.\nTry asking about:\n• 📋 CRM Customer data (e.g. Acme Corp, Stark Industries)\n• ⚠️ Cancel Order ORD-9901 (triggers HITL approval)\n• 🚨 Escalate Ticket INC-1042 (triggers HITL approval)\n• 🎫 ITSM tickets or incidents (e.g. INC-1042, VPN)`;
  }

  return {
    user_query: query,
    intent: intent,
    tool_selected: tool,
    tool_input: toolInput,
    tool_result: toolResult,
    final_answer: finalAnswer,
    steps: [
      { step_id: "1", title: "1. User Input Received", description: `Query: "${query}"` },
      { step_id: "2", title: "2. Understand Intent", description: `Intent: ${intent}` },
      { step_id: "3", title: "3. Tool Selector", description: tool ? `Selected: ${tool}` : "Direct answer" },
      { step_id: "4", title: "4. Tool Execution", description: tool ? `Executed ${tool}` : "Skipped", data: { raw_result: toolResult } },
      { step_id: "5", title: "5. AI Agent Synthesis", description: "Formulated final response." }
    ]
  };
}
