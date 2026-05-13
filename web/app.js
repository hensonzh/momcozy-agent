const messages = document.querySelector("#messages");
const form = document.querySelector("#composer");
const input = document.querySelector("#message");
const send = document.querySelector("#send");
const reset = document.querySelector("#reset");
const attachImage = document.querySelector("#attach-image");
const imageInput = document.querySelector("#image-input");
const imagePreviewStrip = document.querySelector("#image-preview-strip");
const conversationLabel = document.querySelector("#conversation");
const skillsLabel = document.querySelector("#skills");

const THINKING_EVENT_NAME = "momcozy.agent.thinking";
const TEXT_IDLE_THINKING_DELAY_MS = 450;
const MAX_IMAGE_ATTACHMENTS = 4;
const MAX_IMAGE_BYTES = 6 * 1024 * 1024;
const CLIENT_USER_ID_KEY = "momcozy_user_id";
const IMAGE_VIEWER_MIN_ZOOM = 1;
const IMAGE_VIEWER_MAX_ZOOM = 3;
const IMAGE_VIEWER_ZOOM_STEP = 0.25;
const IBCLC_CONSULT_COMPLETED_KEY = "momcozy_ibclc_consult_completed";
const MOMCOZY_LOGO_SRC = "/momcozy_logo.png";
const DOWNLOAD_ICON_SVG = `
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 3v11" />
    <path d="m7 10 5 5 5-5" />
    <path d="M5 21h14" />
  </svg>
`;

let conversationId = localStorage.getItem("momcozy_conversation_id") || "";
let clientUserId = getOrCreateClientUserId();
let runCount = Number(localStorage.getItem("momcozy_run_count") || "0");
let pendingImages = [];
let imageViewer = null;

function getOrCreateClientUserId() {
  const existing = localStorage.getItem(CLIENT_USER_ID_KEY);
  if (existing) return existing;
  const generated = `user_${crypto.randomUUID()}`;
  localStorage.setItem(CLIENT_USER_ID_KEY, generated);
  return generated;
}

function addMessage(role, text, options = {}) {
  const row = addMessageRow(role);
  const node = document.createElement("div");
  node.className = `message ${role}`;
  if (role === "user" && options.images?.length) {
    appendMessageImages(node, options.images);
  }
  if (role === "assistant") {
    setAssistantMarkdown(node, text);
  } else if (text) {
    const textNode = document.createElement("div");
    textNode.textContent = text;
    node.appendChild(textNode);
  }
  row.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function appendMessageImages(node, images) {
  const strip = document.createElement("div");
  strip.className = "message-images";
  for (const image of images) {
    const img = document.createElement("img");
    img.className = "message-image";
    img.src = image.image_url;
    img.alt = image.name || "Attached image";
    enableImageViewer(img);
    strip.appendChild(img);
  }
  node.appendChild(strip);
}

function setAssistantMarkdown(node, text) {
  node._rawMarkdown = text || "";
  renderAssistantMarkdown(node);
}

function appendAssistantMarkdown(node, delta) {
  node._rawMarkdown = `${node._rawMarkdown || ""}${delta || ""}`;
  renderAssistantMarkdown(node);
}

function getAssistantMarkdown(node) {
  return node?._rawMarkdown || node?.textContent || "";
}

function renderAssistantMarkdown(node) {
  const markdown = node._rawMarkdown || "";
  if (!window.marked || !window.DOMPurify) {
    node.classList.remove("has-markdown-image");
    node.textContent = markdown;
    return;
  }
  const rawHtml = window.marked.parse(markdown, {
    async: false,
    breaks: true,
    gfm: true,
  });
  node.innerHTML = window.DOMPurify.sanitize(rawHtml, {
    USE_PROFILES: { html: true },
  });
  const markdownImages = node.querySelectorAll("img");
  node.classList.toggle("has-markdown-image", markdownImages.length > 0);
  markdownImages.forEach((img) => {
    img.decoding = "async";
    enableImageViewer(img);
    img.addEventListener("load", () => {
      messages.scrollTop = messages.scrollHeight;
    }, { once: true });
  });
}

function enableImageViewer(img) {
  if (!img || img.dataset.viewerEnabled === "true") return;
  img.dataset.viewerEnabled = "true";
  img.tabIndex = 0;
  img.setAttribute("role", "button");
  img.setAttribute("aria-label", img.alt ? `查看图片：${img.alt}` : "查看图片");
  img.addEventListener("click", () => openImageViewer(img.src, img.alt || "Image"));
  img.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openImageViewer(img.src, img.alt || "Image");
    }
  });
}

function createImageViewer() {
  if (imageViewer) return imageViewer;
  const overlay = document.createElement("div");
  overlay.className = "image-viewer";
  overlay.hidden = true;
  overlay.innerHTML = `
    <div class="image-viewer-toolbar" role="toolbar" aria-label="图片查看工具">
      <button class="image-viewer-button" type="button" data-action="zoom-out" aria-label="缩小">-</button>
      <button class="image-viewer-button" type="button" data-action="reset" aria-label="重置缩放">1x</button>
      <button class="image-viewer-button" type="button" data-action="zoom-in" aria-label="放大">+</button>
      <button class="image-viewer-button" type="button" data-action="close" aria-label="关闭">Close</button>
    </div>
    <div class="image-viewer-stage">
      <img class="image-viewer-img" alt="" />
    </div>
  `;
  const img = overlay.querySelector(".image-viewer-img");
  const stage = overlay.querySelector(".image-viewer-stage");
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeImageViewer();
  });
  overlay.querySelector('[data-action="close"]').addEventListener("click", closeImageViewer);
  overlay.querySelector('[data-action="zoom-in"]').addEventListener("click", () => setImageViewerZoom(imageViewer.zoom + IMAGE_VIEWER_ZOOM_STEP));
  overlay.querySelector('[data-action="zoom-out"]').addEventListener("click", () => setImageViewerZoom(imageViewer.zoom - IMAGE_VIEWER_ZOOM_STEP));
  overlay.querySelector('[data-action="reset"]').addEventListener("click", () => setImageViewerZoom(1));
  stage.addEventListener("wheel", (event) => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    const direction = event.deltaY < 0 ? 1 : -1;
    setImageViewerZoom(imageViewer.zoom + direction * IMAGE_VIEWER_ZOOM_STEP);
  }, { passive: false });
  document.body.appendChild(overlay);
  imageViewer = { overlay, img, stage, zoom: 1 };
  return imageViewer;
}

function openImageViewer(src, alt) {
  const viewer = createImageViewer();
  viewer.img.src = src;
  viewer.img.alt = alt || "Image";
  viewer.overlay.hidden = false;
  document.body.classList.add("image-viewer-open");
  setImageViewerZoom(1);
  viewer.overlay.querySelector('[data-action="close"]').focus();
}

function closeImageViewer() {
  if (!imageViewer) return;
  imageViewer.overlay.hidden = true;
  imageViewer.img.removeAttribute("src");
  document.body.classList.remove("image-viewer-open");
}

function setImageViewerZoom(value) {
  if (!imageViewer) return;
  const zoom = Math.min(IMAGE_VIEWER_MAX_ZOOM, Math.max(IMAGE_VIEWER_MIN_ZOOM, value));
  imageViewer.zoom = zoom;
  imageViewer.img.style.width = `${zoom * 100}%`;
  imageViewer.overlay.querySelector('[data-action="reset"]').textContent = `${Math.round(zoom * 100)}%`;
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && imageViewer && !imageViewer.overlay.hidden) {
    closeImageViewer();
  }
});

function addMessageRow(role) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;
  messages.appendChild(row);
  return row;
}

function addToolNote(toolResults) {
  if (!toolResults || toolResults.length === 0) return;
  const names = [...new Set(toolResults.map((tool) => tool.name).filter(Boolean))].join(", ");
  if (!names) return;
  const node = document.createElement("div");
  node.className = "tool-note";
  node.textContent = `Tools used: ${names}`;
  messages.appendChild(node);
}

function addStatusNode() {
  const row = addMessageRow("status");
  const node = document.createElement("div");
  node.className = "status-note";
  node.innerHTML = `
    <span class="status-dot" aria-hidden="true"></span>
    <span class="status-text">Starting agent run...</span>
    <span class="status-tools"></span>
  `;
  row.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function addWorkPanel(startedAt = Date.now()) {
  const row = addMessageRow("work");
  const node = document.createElement("div");
  node.className = "work-panel";
  node._startedAt = startedAt;
  node._finished = false;
  node.innerHTML = `
    <button class="work-header" type="button" aria-expanded="true">
      <span class="work-caret" aria-hidden="true"></span>
      <span class="work-title">Working for 0s</span>
    </button>
    <div class="work-body">
      <ol class="work-list"></ol>
    </div>
  `;
  const header = node.querySelector(".work-header");
  header?.addEventListener("click", () => {
    const collapsed = node.classList.toggle("collapsed");
    header.setAttribute("aria-expanded", String(!collapsed));
  });
  node._timer = window.setInterval(() => updateWorkDuration(node), 1000);
  updateWorkDuration(node);
  row.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function createWorkRun() {
  return {
    startedAt: Date.now(),
    panel: null,
    finished: false,
    hasOutput: false,
    hasAction: false,
    thinkingVisible: false,
    thinkingNode: null,
    textIdleTimer: null,
  };
}

function ensureWorkPanel(run) {
  if (!run) return null;
  if (!run.panel) {
    run.panel = addWorkPanel(run.startedAt);
  }
  return run.panel;
}

function updateWorkDuration(workPanel, final = false) {
  const title = workPanel?.querySelector(".work-title");
  if (!title) return;
  const elapsed = Date.now() - (workPanel._startedAt || Date.now());
  title.textContent = `${final ? "Worked" : "Working"} for ${formatDuration(elapsed)}`;
}

function formatDuration(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (!minutes) return `${seconds}s`;
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

function showThinking(run, options = {}) {
  if (!run || run.finished || run.thinkingVisible) return;
  const panel = options.afterOutput ? null : run.hasAction ? ensureWorkPanel(run) : run.panel;
  const row = document.createElement("div");
  row.className = "message-row thinking";
  const node = document.createElement("div");
  node.className = "thinking-note";
  node.innerHTML = `
    <span class="thinking-marker" aria-hidden="true"></span>
    <span class="thinking-title">${options.title || "Thinking"}</span>
  `;
  row.appendChild(node);
  const panelRow = panel?.closest(".message-row");
  if (panelRow) {
    panelRow.insertAdjacentElement("afterend", row);
  } else {
    messages.appendChild(row);
  }
  run.thinkingNode = node;
  run.thinkingVisible = true;
  messages.scrollTop = messages.scrollHeight;
}

function completeThinking(run) {
  if (!run) return;
  removeMessageElement(run.thinkingNode);
  run.thinkingNode = null;
  run.thinkingVisible = false;
}

function clearTextIdleTimer(run) {
  if (!run?.textIdleTimer) return;
  window.clearTimeout(run.textIdleTimer);
  run.textIdleTimer = null;
}

function scheduleTextIdleThinking(run) {
  if (!run || run.finished) return;
  clearTextIdleTimer(run);
  run.textIdleTimer = window.setTimeout(() => {
    run.textIdleTimer = null;
    if (!run.finished) {
      showThinking(run, { afterOutput: true, title: "Preparing next step" });
    }
  }, TEXT_IDLE_THINKING_DELAY_MS);
}

function finishWorkPanel(run, options = {}) {
  if (!run || run.finished) return;
  run.finished = true;
  clearTextIdleTimer(run);
  completeThinking(run);
  const workPanel = options.failed ? ensureWorkPanel(run) : run.panel;
  if (!workPanel || workPanel._finished) return;
  if (!options.failed && !run.hasAction) {
    if (workPanel._timer) {
      window.clearInterval(workPanel._timer);
      workPanel._timer = null;
    }
    removeMessageElement(workPanel);
    run.panel = null;
    return;
  }
  workPanel._finished = true;
  if (workPanel._timer) {
    window.clearInterval(workPanel._timer);
    workPanel._timer = null;
  }
  updateWorkDuration(workPanel, true);
  if (options.failed) {
    upsertWorkItem(workPanel, {
      key: "run-error",
      status: "failed",
      title: "执行中断",
      detail: options.message || "请求处理失败，请稍后重试。",
    });
  } else {
    settleRunningWorkItems(workPanel);
    workPanel.classList.add("collapsed");
    workPanel.querySelector(".work-header")?.setAttribute("aria-expanded", "false");
  }
}

function addWorkToolStart(run, event) {
  if (!run || !event?.tool_call_id) return;
  run.hasAction = true;
  clearTextIdleTimer(run);
  completeThinking(run);
  const workPanel = ensureWorkPanel(run);
  const toolName = event.tool_call_name || "tool";
  const copy = toolStartCopy(toolName);
  upsertWorkItem(workPanel, {
    key: workItemKeyForToolCall(event),
    aliases: workItemKeysForToolCall(event),
    toolName,
    status: "running",
    title: copy.title,
  });
}

function addWorkToolArgs(run, event, toolName) {
  if (!run || !event?.tool_call_id) return;
  run.hasAction = true;
  clearTextIdleTimer(run);
  completeThinking(run);
  const workPanel = ensureWorkPanel(run);
  const copy = toolArgsCopy(toolName || "tool");
  upsertWorkItem(workPanel, {
    key: workItemKeyForToolCall(event),
    aliases: workItemKeysForToolCall(event),
    toolName,
    status: "running",
    title: copy.title,
    detail: copy.detail,
    mergeRunning: true,
  });
}

function addWorkToolEnd(run, event, toolName) {
  if (!run || !event?.tool_call_id) return;
  run.hasAction = true;
  clearTextIdleTimer(run);
  completeThinking(run);
  const workPanel = ensureWorkPanel(run);
  const copy = toolEndCopy(toolName || "tool");
  upsertWorkItem(workPanel, {
    key: workItemKeyForToolCall(event),
    aliases: workItemKeysForToolCall(event),
    toolName,
    status: "running",
    title: copy.title,
    detail: copy.detail,
    mergeRunning: true,
  });
}

function addWorkToolResult(run, event, result, toolName) {
  if (!run || !event?.tool_call_id) return;
  run.hasAction = true;
  clearTextIdleTimer(run);
  completeThinking(run);
  const workPanel = ensureWorkPanel(run);
  const copy = toolResultCopy(toolName || result?.tool_name || "tool", result || {});
  upsertWorkItem(workPanel, {
    key: workItemKeyForToolCall(event),
    aliases: workItemKeysForToolCall(event),
    toolName,
    status: result?.ok === false ? "failed" : "completed",
    title: copy.title,
    detail: copy.detail,
    mergeRunning: true,
  });
}

function addWorkNarration(run, markdown) {
  const text = String(markdown || "").trim();
  if (!run || !text) return null;
  run.hasAction = true;
  const workPanel = ensureWorkPanel(run);
  const list = workPanel?.querySelector(".work-list");
  if (!list) return null;

  const item = document.createElement("li");
  item.className = "work-item work-narration";

  const content = document.createElement("div");
  content.className = "work-narration-content";
  setAssistantMarkdown(content, text);
  item.appendChild(content);

  list.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

function workItemKeyForToolCall(event) {
  return workItemKeysForToolCall(event)[0] || "tool:unknown";
}

function workItemKeysForToolCall(event) {
  const keys = [];
  if (event?.response_id && event.output_index !== undefined && event.output_index !== null) {
    keys.push(`tool:${event.response_id}:${event.output_index}`);
  }
  if (event?.tool_call_id) keys.push(`tool:${event.tool_call_id}`);
  if (event?.item_id) keys.push(`tool:${event.item_id}`);
  return [...new Set(keys)];
}

function upsertWorkItem(workPanel, itemData) {
  const list = workPanel?.querySelector(".work-list");
  if (!list) return null;

  const key = itemData.key || `item:${Date.now()}:${Math.random()}`;
  const aliases = new Set([key, ...(itemData.aliases || [])].filter(Boolean));
  const escapedKey = cssEscape(key);
  let existingItem = null;
  if (itemData.mergeRunning) {
    existingItem = list.querySelector(`.work-item.running[data-work-key="${escapedKey}"]`);
  }
  if (!existingItem) {
    existingItem = list.querySelector(`.work-item[data-work-key="${escapedKey}"]`);
  }
  if (!existingItem && aliases.size) {
    existingItem = findWorkItemByAliases(list, aliases, itemData.mergeRunning ? "running" : "");
  }
  if (!existingItem && itemData.mergeRunning && itemData.toolName) {
    existingItem = findRunningWorkItemByToolName(list, itemData.toolName);
  }
  const item = existingItem || document.createElement("li");

  if (!existingItem) {
    const marker = document.createElement("span");
    marker.className = "work-marker";
    marker.setAttribute("aria-hidden", "true");
    item.appendChild(marker);
  }
  item.className = `work-item ${itemData.status || "running"}`;
  item.dataset.workKey = key;
  item.dataset.workAliases = mergeWorkAliases(item.dataset.workAliases, aliases);
  if (itemData.toolName) item.dataset.toolName = itemData.toolName;

  let body = item.querySelector(".work-item-body");
  if (!body) {
    body = document.createElement("div");
    body.className = "work-item-body";
    item.appendChild(body);
  }
  body.innerHTML = "";

  const title = document.createElement("div");
  title.className = "work-item-title";
  title.textContent = itemData.title || "Working";
  body.appendChild(title);

  if (itemData.detail) {
    const detail = document.createElement("div");
    detail.className = "work-detail";
    detail.textContent = itemData.detail;
    body.appendChild(detail);
  }

  if (!existingItem) {
    list.appendChild(item);
  }

  messages.scrollTop = messages.scrollHeight;
  return item;
}

function findWorkItemByAliases(list, aliases, requiredStatus = "") {
  for (const item of list.querySelectorAll(".work-item")) {
    if (requiredStatus && !item.classList.contains(requiredStatus)) continue;
    const itemAliases = parseWorkAliases(item.dataset.workAliases);
    if ([...aliases].some((alias) => itemAliases.has(alias))) {
      return item;
    }
  }
  return null;
}

function findRunningWorkItemByToolName(list, toolName) {
  for (const item of list.querySelectorAll(".work-item.running")) {
    if (item.dataset.toolName === toolName) return item;
  }
  return null;
}

function mergeWorkAliases(currentValue, aliases) {
  const merged = parseWorkAliases(currentValue);
  for (const alias of aliases) {
    merged.add(alias);
  }
  return [...merged].join(" ");
}

function parseWorkAliases(value) {
  return new Set(String(value || "").split(/\s+/).filter(Boolean));
}

function settleRunningWorkItems(workPanel) {
  for (const item of workPanel?.querySelectorAll(".work-item.running") || []) {
    item.classList.remove("running");
    item.classList.add("completed");
  }
}

function addStructuredArtifact(kind, label) {
  const row = addMessageRow("artifact");
  const node = document.createElement("section");
  node.className = `structured-artifact structured-artifact-${kind}`;

  if (label) {
    const header = document.createElement("div");
    header.className = "artifact-header";

    const artifactLabel = document.createElement("div");
    artifactLabel.className = "artifact-label";
    artifactLabel.textContent = label;
    header.appendChild(artifactLabel);
    node.appendChild(header);
  }

  const body = document.createElement("div");
  body.className = "artifact-body";
  node.appendChild(body);

  row.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return body;
}

function addFormCard(formSpec) {
  const body = addStructuredArtifact("form", "信息采集表");
  const node = document.createElement("form");
  node.className = "agent-form";
  node.dataset.formId = formSpec.id || "form";

  const title = document.createElement("h2");
  title.textContent = formSpec.title || "Confirm details";
  node.appendChild(title);

  if (formSpec.description) {
    const description = document.createElement("p");
    description.textContent = formSpec.description;
    node.appendChild(description);
  }

  for (const field of formSpec.fields || []) {
    node.appendChild(createFormField(field));
  }

  const actions = document.createElement("div");
  actions.className = "agent-form-actions";
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = formSpec.submit_label || "Confirm";
  actions.appendChild(submit);
  node.appendChild(actions);

  node.addEventListener("submit", (event) => {
    event.preventDefault();
    const validationMessage = validateFormSelection(node, formSpec);
    if (validationMessage) {
      addMessage("error", validationMessage);
      return;
    }
    const values = collectFormValues(node, formSpec);
    node.classList.add("submitted");
    for (const element of node.elements) {
      element.disabled = true;
    }
    const summary = buildFormConfirmationMessage(formSpec, values);
    sendUserText(summary, { displayText: `已提交：${formSpec.title || "表单"}` });
  });

  body.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function addSupportTicketDraft(ticketPayload) {
  const ticket = ticketPayload.ticket || {};
  const body = addStructuredArtifact("support-ticket", "");
  const node = document.createElement("form");
  node.className = "agent-form support-ticket-form";
  node.dataset.ticketDraftId = ticket.draft_id || "";

  const title = document.createElement("h2");
  title.textContent = "售后工单";
  node.appendChild(title);

  const fields = supportTicketFields(ticket);
  for (const field of fields) {
    node.appendChild(createFormField(field));
  }

  const actions = document.createElement("div");
  actions.className = "agent-form-actions";
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = ticketPayload.submit_label || "确认并提交";
  actions.appendChild(submit);
  node.appendChild(actions);

  node.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = normalizeSupportTicketValues(collectFormValues(node, { fields }));
    submit.disabled = true;
    submit.textContent = "发送中...";
    try {
      const result = await submitSupportTicket(values);
      node.classList.add("submitted");
      for (const element of node.elements) {
        element.disabled = true;
      }
      markSupportTicketSubmitted(node, submit, result);
      await sendUserText(buildSupportTicketSubmittedMessage(values, result), { displayText: "已提交售后工单" });
    } catch (error) {
      addMessage("error", error.message || "工单提交失败，请稍后重试。");
      submit.disabled = false;
      submit.textContent = ticketPayload.submit_label || "确认并提交";
    }
  });

  body.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function supportTicketFields(ticket) {
  return [
    {
      id: "issue_type",
      label: "问题类型",
      type: "select",
      required: true,
      default_value: supportTicketIssueLabel(ticket.issue_type),
      options: ["设备故障", "缺少配件", "疑似质量问题", "保修", "退换货/退款", "订单/物流", "使用帮助", "安全问题", "其他"],
    },
    {
      id: "issue_summary",
      label: "问题描述",
      type: "textarea",
      required: true,
      default_value: ticket.issue_summary || "",
      placeholder: "简单描述你遇到的问题",
    },
    {
      id: "product_model",
      label: "产品型号",
      type: "text",
      required: false,
      default_value: ticket.product_model || "",
      placeholder: "例如：M5、S12 Pro，或暂不确定",
    },
    {
      id: "urgency",
      label: "紧急程度",
      type: "select",
      required: true,
      default_value: supportTicketUrgencyLabel(ticket.urgency),
      options: ["普通", "较急", "安全相关"],
    },
  ];
}

function supportTicketIssueLabel(value) {
  const labels = {
    malfunction: "设备故障",
    missing_parts: "缺少配件",
    defect: "疑似质量问题",
    warranty: "保修",
    return_or_refund: "退换货/退款",
    order_or_shipping: "订单/物流",
    usage_help: "使用帮助",
    safety_concern: "安全问题",
    other: "其他",
  };
  return labels[value] || "其他";
}

function supportTicketUrgencyLabel(value) {
  const labels = {
    normal: "普通",
    high: "较急",
    safety: "安全相关",
  };
  return labels[value] || "普通";
}

function normalizeSupportTicketValues(values) {
  return {
    ...values,
    troubleshooting_done: String(values.troubleshooting_done || "")
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean),
  };
}

async function submitSupportTicket(ticket) {
  const timezone = clientTimezone();
  const messageSentAt = clientMessageSentAt();
  const response = await fetch("/api/support-ticket-submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ticket,
      thread_id: conversationId,
      user_id: clientUserId,
      locale: clientLocale(),
      timezone,
      message_sent_at: messageSentAt,
      idempotency_key: crypto.randomUUID(),
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed with ${response.status}`);
  }
  return data;
}

function markSupportTicketSubmitted(form, submit, result) {
  submit.textContent = "已提交";
  messages.scrollTop = messages.scrollHeight;
}

function buildSupportTicketSubmittedMessage(ticket, result) {
  const submittedTicket = result.ticket || ticket || {};
  const lines = [
    "客服工单已模拟提交成功。请基于以下提交信息，给用户一段简短的情绪支持。",
    result.ticket_id ? `工单编号：${result.ticket_id}` : "",
    submittedTicket.issue_type ? `问题类型：${submittedTicket.issue_type}` : "",
    submittedTicket.issue_summary ? `问题描述：${submittedTicket.issue_summary}` : "",
    submittedTicket.product_model ? `产品型号：${submittedTicket.product_model}` : "",
    submittedTicket.urgency ? `紧急程度：${submittedTicket.urgency}` : "",
    "回复要求：不要重复工单字段，不要继续排查；根据用户的主要售后情绪做 1-3 句贴合场景的承接，并告诉用户人工客服会在 24 小时内联系你解决问题。",
  ];
  return lines.filter(Boolean).join("\n");
}

function addIbclcConsultCard(card) {
  const body = addStructuredArtifact("ibclc", "");
  const node = document.createElement("article");
  node.className = "ibclc-card";
  const consultId = `ibclc_${crypto.randomUUID()}`;
  node.dataset.consultId = consultId;

  const consultant = card.consultant || {};
  const chat = card.chat || {};

  const heading = document.createElement("div");
  heading.className = "ibclc-card-heading";
  const title = document.createElement("h2");
  title.textContent = "IBCLC咨询";
  heading.appendChild(title);
  node.appendChild(heading);

  const consultantBlock = document.createElement("section");
  consultantBlock.className = "ibclc-consultant";
  const avatar = document.createElement("div");
  avatar.className = "ibclc-avatar";
  avatar.textContent = initialsForName(consultant.name || "IBCLC");
  consultantBlock.appendChild(avatar);

  const details = document.createElement("div");
  const name = document.createElement("strong");
  name.textContent = consultant.name || "IBCLC 顾问";
  details.appendChild(name);
  if (consultant.bio) {
    const bio = document.createElement("p");
    bio.textContent = consultant.bio;
    details.appendChild(bio);
  }
  consultantBlock.appendChild(details);
  node.appendChild(consultantBlock);

  const button = document.createElement("a");
  button.className = "ibclc-chat-button";
  button.href = ibclcChatUrl(chat.url || "/ibclc-chat.html", consultId);
  button.target = "_blank";
  button.rel = "noopener";
  button.textContent = "在线咨询";
  node.appendChild(button);
  applyIbclcConsultCompletionToCard(node, readStoredIbclcConsultCompletion());

  body.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function ibclcChatUrl(url, consultId) {
  const threadId = conversationId || localStorage.getItem("momcozy_conversation_id") || "";
  try {
    const nextUrl = new URL(url, window.location.origin);
    if (threadId) nextUrl.searchParams.set("thread_id", threadId);
    if (consultId) nextUrl.searchParams.set("consult_id", consultId);
    return nextUrl.origin === window.location.origin
      ? `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`
      : nextUrl.toString();
  } catch (_) {
    return url;
  }
}

function readStoredIbclcConsultCompletion() {
  return parseJson(localStorage.getItem(IBCLC_CONSULT_COMPLETED_KEY));
}

function handleIbclcConsultCompleted(payload) {
  if (!payload || payload.type !== "momcozy.ibclc_consult_completed") return;
  const eventThreadId = payload.conversation_id || payload.thread_id || payload.threadId || "";
  if (eventThreadId && conversationId && eventThreadId !== conversationId) return;
  if (eventThreadId && !conversationId) {
    conversationId = eventThreadId;
    localStorage.setItem("momcozy_conversation_id", conversationId);
  }
  updateMeta({
    conversation_id: eventThreadId || conversationId,
    loaded_skill_ids: payload.session_state?.loaded_skill_ids || [],
  });
  for (const card of document.querySelectorAll(".ibclc-card")) {
    applyIbclcConsultCompletionToCard(card, payload);
  }
}

function applyIbclcConsultCompletionToCard(card, payload) {
  const eventThreadId = payload?.conversation_id || payload?.thread_id || payload?.threadId || "";
  if (eventThreadId && conversationId && eventThreadId !== conversationId) return;
  const eventConsultId = payload?.consult_id || payload?.consultId || "";
  if (!eventConsultId || eventConsultId !== card?.dataset?.consultId) return;
  const button = card?.querySelector(".ibclc-chat-button");
  if (!button || payload?.type !== "momcozy.ibclc_consult_completed") return;
  card.classList.add("consult-completed");
  button.textContent = "咨询结束";
  button.classList.add("is-completed");
  button.setAttribute("aria-disabled", "true");
  button.removeAttribute("href");
  button.removeAttribute("target");
  button.removeAttribute("rel");
}

function initialsForName(name) {
  const text = String(name || "").trim();
  if (!text) return "IB";
  const asciiParts = text.match(/[A-Za-z]+/g);
  if (asciiParts?.length) {
    return asciiParts.slice(0, 2).map((part) => part[0].toUpperCase()).join("");
  }
  return text.slice(0, 2);
}

function addCard(card) {
  const body = addStructuredArtifact("card", "生成卡片");
  const node = document.createElement("article");
  node.className = `agent-card ${card.card_type ? `agent-card-${card.card_type}` : ""}`.trim();
  node.dataset.cardType = card.card_type || "";
  node.dataset.schemaVersion = card.schema_version || "";

  const cardJson = card.card_json || {};
  if (card.card_type === "birth_plan_card" && card.schema_version === "1.0") {
    renderBirthPlanCardV1(node, cardJson);
  } else if (card.card_type === "hospital_bag_card" && card.schema_version === "1.0") {
    renderHospitalBagCardV1(node, cardJson);
  } else {
    renderUnsupportedCard(node, card);
  }

  body.appendChild(node);
  attachCardDownload(body, node, cardDownloadFilename(card));
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function attachCardDownload(body, cardNode, filename) {
  const artifact = body?.closest(".structured-artifact");
  const header = artifact?.querySelector(".artifact-header");
  if (!header || !cardNode) return;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "artifact-download";
  button.title = "下载卡片 PNG";
  button.setAttribute("aria-label", "下载卡片 PNG");
  button.innerHTML = DOWNLOAD_ICON_SVG;
  button.addEventListener("click", async () => {
    await downloadCardAsPng(button, cardNode, filename);
  });
  header.appendChild(button);
}

async function downloadCardAsPng(button, cardNode, filename) {
  if (!window.htmlToImage?.toPng) {
    addMessage("error", "图片导出组件未加载，请检查网络后重试。");
    return;
  }

  button.disabled = true;
  button.classList.add("is-loading");
  try {
    await document.fonts?.ready;
    const dataUrl = await window.htmlToImage.toPng(cardNode, {
      backgroundColor: "#ffffff",
      cacheBust: true,
      pixelRatio: Math.min(Math.max(window.devicePixelRatio || 2, 2), 3),
    });
    const blob = await dataUrlToBlob(dataUrl);
    const shared = await shareImageOnMobile(blob, filename);
    if (!shared) {
      triggerImageDownload(dataUrl, filename);
    }
  } catch (error) {
    addMessage("error", error?.message || "卡片下载失败，请稍后重试。");
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
  }
}

function cardDownloadFilename(card) {
  const type = card?.card_type || "card";
  const date = new Date().toISOString().slice(0, 10);
  return `comate-${type}-${date}.png`.replace(/[^a-z0-9._-]+/gi, "-");
}

async function dataUrlToBlob(dataUrl) {
  const response = await fetch(dataUrl);
  return response.blob();
}

async function shareImageOnMobile(blob, filename) {
  const canShareFiles = navigator.share && navigator.canShare && typeof File !== "undefined";
  const mobileViewport = window.matchMedia?.("(max-width: 700px)")?.matches;
  if (!canShareFiles || !mobileViewport) return false;

  const file = new File([blob], filename, { type: "image/png" });
  if (!navigator.canShare({ files: [file] })) return false;

  try {
    await navigator.share({
      files: [file],
      title: "CoMate card",
    });
    return true;
  } catch (error) {
    return error?.name === "AbortError";
  }
}

function triggerImageDownload(dataUrl, filename) {
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function renderBirthPlanCardV1(node, cardJson) {
  const card = normalizeBirthPlanCard(cardJson);
  addCardHeader(node, card.title || "Birth Plan Card", birthPlanSubtitle(card) || card.subtitle || "");
  addBirthPlanPriorityBlock(node, card.top_priorities);
  addBirthPlanPreferenceGroups(node, [
    ["Communication", card.communication],
    ["Pain Relief", card.pain_relief],
    ["Baby After Birth", card.baby_after_birth],
    ["If Plans Change", card.if_plans_change],
  ]);
  addListSection(node, "Medical notes", card.medical_notes);
  addListSection(node, "Questions before admission", limitList(card.questions_for_hospital, 3));
  addDisclaimer(node, card.disclaimer);
}

function renderHospitalBagCardV1(node, cardJson) {
  addCardHeader(node, cardJson.title || "Hospital Bag Card", hospitalBagSubtitle(cardJson) || cardJson.subtitle || "");
  addPackingGroups(node, compactPackingGroups(cardJson.packing_groups));
  addListSection(node, "Confirm With Hospital", limitList(cardJson.hospital_context?.items_to_confirm_with_hospital, 3));
  addListSection(node, "Timeline", limitList(cardJson.timeline, 2));
  addDisclaimer(node, cardJson.disclaimer);
}

function hospitalBagSubtitle(cardJson) {
  const owner = cardJson.owner || {};
  const hospital = cardJson.hospital_context || {};
  const values = [owner.due_date_or_week, owner.birth_path, owner.packing_style, hospital.expected_stay]
    .filter((value) => hasDisplayValue(value) && !isConfirmPlaceholder(value))
    .map(formatPlainValue);
  return values.join(" | ");
}

function normalizeBirthPlanCard(cardJson) {
  const owner = cardJson.owner || {};
  const overview = cardJson.overview || {};
  const birthPreferences = cardJson.birth_preferences || {};
  return {
    title: cardJson.title || "Birth Plan Card",
    subtitle: cardJson.subtitle || "Labor room communication priority card",
    overview: {
      due_date_or_week: overview.due_date_or_week || owner.due_date_or_week,
      birth_path: overview.birth_path || birthPreferences.birth_path,
      support_people: overview.support_people || owner.support_people,
    },
    top_priorities: compactBirthPlanList(cardJson.top_priorities || cardJson.if_plans_change?.what_matters_most, 3),
    communication: compactBirthPlanList(cardJson.communication || cardJson.communication_preferences, 3),
    pain_relief: compactBirthPlanList(cardJson.pain_relief || cardJson.pain_relief_preferences, 3),
    baby_after_birth: compactBirthPlanList(cardJson.baby_after_birth || cardJson.baby_after_birth_preferences, 3),
    if_plans_change: compactBirthPlanList(cardJson.if_plans_change, 3),
    questions_for_hospital: compactBirthPlanList(cardJson.questions_for_hospital, 3),
    medical_notes: compactBirthPlanList(cardJson.medical_notes, 3),
    disclaimer:
      cardJson.disclaimer ||
      "This card is for communication only. Please follow your clinician and hospital guidance, especially if plans change for safety reasons.",
  };
}

function birthPlanSubtitle(card) {
  const overview = card.overview || {};
  const values = [overview.due_date_or_week, overview.birth_path, overview.support_people]
    .filter((value) => hasDisplayValue(value) && !isConfirmPlaceholder(value))
    .map(formatPlainValue);
  return values.join(" | ");
}

function compactBirthPlanList(values, maxItems) {
  return normalizeList(flattenDisplayValues(values))
    .filter((value) => !isConfirmPlaceholder(value))
    .slice(0, maxItems);
}

function flattenDisplayValues(value) {
  if (Array.isArray(value)) {
    return value.flatMap(flattenDisplayValues);
  }
  if (value && typeof value === "object") {
    return Object.values(value).flatMap(flattenDisplayValues);
  }
  return hasDisplayValue(value) ? [formatPlainValue(value)] : [];
}

function addBirthPlanPriorityBlock(node, priorities) {
  const items = compactBirthPlanList(priorities, 3);
  if (!items.length) return;

  const section = document.createElement("section");
  section.className = "birth-plan-priority";
  const heading = document.createElement("h3");
  heading.textContent = "What matters most";
  section.appendChild(heading);

  const list = document.createElement("ul");
  list.className = "agent-card-list";
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  }
  section.appendChild(list);
  node.appendChild(section);
}

function addBirthPlanPreferenceGroups(node, groups) {
  const visibleGroups = groups
    .map(([title, values]) => [title, compactBirthPlanList(values, 3)])
    .filter(([, values]) => values.length);
  if (!visibleGroups.length) return;

  const section = createCardSection("Care team preferences");
  section.classList.add("birth-plan-preferences");
  const grid = document.createElement("div");
  grid.className = "birth-plan-group-grid";
  for (const [title, values] of visibleGroups) {
    const group = document.createElement("div");
    group.className = "birth-plan-group";
    const heading = document.createElement("h4");
    heading.textContent = title;
    group.appendChild(heading);

    const list = document.createElement("ul");
    list.className = "agent-card-list";
    for (const value of values) {
      const item = document.createElement("li");
      item.textContent = value;
      list.appendChild(item);
    }
    group.appendChild(list);
    grid.appendChild(group);
  }
  section.appendChild(grid);
  node.appendChild(section);
}

function compactPackingGroups(groups) {
  if (!Array.isArray(groups)) return [];
  return groups
    .filter((group) => group && typeof group === "object")
    .slice(0, 3)
    .map((group) => ({
      ...group,
      items: compactPackingItems(group.items),
    }))
    .filter((group) => group.items.length);
}

function compactPackingItems(items) {
  if (!Array.isArray(items)) return [];
  if (items.length <= 4) return items;

  const pumpIndex = items.findIndex(isBreastPumpItem);
  if (pumpIndex === -1 || pumpIndex < 4) return items.slice(0, 4);

  const visibleItems = items.slice(0, 4);
  visibleItems[3] = items[pumpIndex];
  return visibleItems;
}

function isBreastPumpItem(item) {
  const text = JSON.stringify(item || {}).toLowerCase();
  return text.includes("吸奶") || text.includes("breast pump") || text.includes("pump");
}

function renderUnsupportedCard(node, card) {
  addCardHeader(node, card.card_type || "Unsupported card", card.schema_version ? `Schema ${card.schema_version}` : "");
  const pre = document.createElement("pre");
  pre.className = "agent-card-json";
  pre.textContent = JSON.stringify(card.card_json || {}, null, 2);
  node.appendChild(pre);
}

function addCardHeader(node, titleText, subtitleText) {
  const header = document.createElement("header");
  header.className = "agent-card-header";

  const text = document.createElement("div");
  text.className = "agent-card-header-text";

  const title = document.createElement("h2");
  title.textContent = titleText;
  text.appendChild(title);
  if (subtitleText) {
    const subtitle = document.createElement("p");
    subtitle.textContent = subtitleText;
    text.appendChild(subtitle);
  }

  const logo = document.createElement("img");
  logo.className = "agent-card-logo";
  logo.src = MOMCOZY_LOGO_SRC;
  logo.alt = "Momcozy";

  header.append(text, logo);
  node.appendChild(header);
}

function addKeyValueSection(node, title, data, options = {}) {
  if (!data || typeof data !== "object") return;
  const entries = Object.entries(data).filter(([key, value]) => {
    if (options.skipKeys?.includes(key)) return false;
    return hasDisplayValue(value);
  });
  if (!entries.length) return;

  const section = createCardSection(title);
  const grid = document.createElement("dl");
  grid.className = "agent-card-kv";
  for (const [key, value] of entries) {
    const dt = document.createElement("dt");
    dt.textContent = formatLabel(key);
    const dd = document.createElement("dd");
    appendValue(dd, value);
    grid.append(dt, dd);
  }
  section.appendChild(grid);
  node.appendChild(section);
}

function addListSection(node, title, values, options = {}) {
  const items = normalizeList(values);
  if (!items.length) return;
  const section = createCardSection(title, options.muted ? "muted" : "");
  const list = document.createElement("ul");
  list.className = "agent-card-list";
  for (const item of items) {
    const li = document.createElement("li");
    appendValue(li, item);
    list.appendChild(li);
  }
  section.appendChild(list);
  node.appendChild(section);
}

function addPackingGroups(node, groups) {
  if (!Array.isArray(groups) || !groups.length) return;
  const section = createCardSection("Packing List");
  for (const group of groups) {
    if (!group || typeof group !== "object") continue;
    const groupNode = document.createElement("div");
    groupNode.className = "packing-group";
    const title = document.createElement("h4");
    title.textContent = group.title || formatLabel(group.group_id || "Group");
    groupNode.appendChild(title);

    const list = document.createElement("ul");
    list.className = "agent-card-list";
    for (const item of group.items || []) {
      const li = document.createElement("li");
      li.className = "packing-item";
      const label = document.createElement("span");
      label.textContent = item?.label || String(item || "");
      li.appendChild(label);
      if (item?.priority) {
        const badge = document.createElement("span");
        badge.className = `priority priority-${String(item.priority).replaceAll("_", "-")}`;
        badge.textContent = priorityLabel(item.priority);
        li.appendChild(badge);
      }
      if (item?.note) {
        const note = document.createElement("small");
        note.textContent = item.note;
        li.appendChild(note);
      }
      list.appendChild(li);
    }
    groupNode.appendChild(list);
    section.appendChild(groupNode);
  }
  node.appendChild(section);
}

function addDisclaimer(node, text) {
  if (!text) return;
  const disclaimer = document.createElement("p");
  disclaimer.className = "agent-card-disclaimer";
  disclaimer.textContent = text;
  node.appendChild(disclaimer);
}

function createCardSection(title, extraClass = "") {
  const section = document.createElement("section");
  section.className = `agent-card-section ${extraClass}`.trim();
  section.dataset.section = slugifyClassName(title);
  const heading = document.createElement("h3");
  heading.textContent = title;
  section.appendChild(heading);
  return section;
}

function priorityLabel(priority) {
  const labels = {
    must: "Essential",
    recommended: "Helpful",
    nice_to_have: "Optional",
    confirm_first: "Confirm",
  };
  return labels[String(priority || "")] || formatLabel(priority);
}

function slugifyClassName(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function createFormField(field) {
  if (isMultiSelectField(field)) {
    return createCheckboxGroup(field);
  }

  const wrapper = document.createElement("label");
  wrapper.className = "agent-form-field";

  wrapper.appendChild(createFieldLabel("span", field));

  let control;
  if (field.type === "select") {
    control = document.createElement("select");
    for (const option of field.options || []) {
      const optionNode = document.createElement("option");
      optionNode.value = option;
      optionNode.textContent = option;
      control.appendChild(optionNode);
    }
  } else if (field.type === "textarea") {
    control = document.createElement("textarea");
    control.rows = 3;
  } else {
    control = document.createElement("input");
    control.type = field.type === "date" ? "date" : "text";
  }

  control.name = field.id;
  control.required = Boolean(field.required);
  if (field.placeholder) control.placeholder = field.placeholder;
  if (field.default_value) control.value = field.default_value;
  wrapper.appendChild(control);

  if (field.help_text) {
    const help = document.createElement("small");
    help.textContent = field.help_text;
    wrapper.appendChild(help);
  }

  return wrapper;
}

function createCheckboxGroup(field) {
  const wrapper = document.createElement("fieldset");
  wrapper.className = "agent-form-field agent-form-checkbox-group";

  wrapper.appendChild(createFieldLabel("legend", field));

  const options = document.createElement("div");
  options.className = "agent-form-options";
  const defaultValues = defaultMultiSelectValues(field.default_value);
  for (const option of field.options || []) {
    const optionLabel = document.createElement("label");
    optionLabel.className = "agent-form-option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = field.id;
    input.value = option;
    input.checked = defaultValues.includes(option);
    input.addEventListener("change", () => wrapper.classList.remove("invalid"));
    optionLabel.appendChild(input);
    const text = document.createElement("span");
    text.textContent = option;
    optionLabel.appendChild(text);
    options.appendChild(optionLabel);
  }
  wrapper.appendChild(options);

  if (field.help_text) {
    const help = document.createElement("small");
    help.textContent = field.help_text;
    wrapper.appendChild(help);
  }

  return wrapper;
}

function createFieldLabel(tagName, field) {
  const label = document.createElement(tagName);
  label.className = "agent-form-label";
  if (field.required) {
    const marker = document.createElement("span");
    marker.className = "agent-form-required-marker";
    marker.textContent = "*";
    marker.setAttribute("aria-hidden", "true");
    label.appendChild(marker);
  }
  label.appendChild(document.createTextNode(field.label || ""));
  return label;
}

function isMultiSelectField(field) {
  return ["multi_select", "checkbox_group"].includes(field?.type);
}

function defaultMultiSelectValues(value) {
  if (Array.isArray(value)) return value.map(String);
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function collectFormValues(node, formSpec) {
  const data = new FormData(node);
  const values = {};
  for (const field of formSpec.fields || []) {
    values[field.id] = isMultiSelectField(field) ? data.getAll(field.id) : data.get(field.id) || "";
  }
  return values;
}

function validateFormSelection(node, formSpec) {
  for (const field of formSpec.fields || []) {
    if (!field.required || !isMultiSelectField(field)) continue;
    if (new FormData(node).getAll(field.id).length) continue;
    const group = node.querySelector(`[name="${cssEscape(field.id)}"]`)?.closest(".agent-form-checkbox-group");
    if (group) group.classList.add("invalid");
    return `请选择：${field.label}`;
  }
  return "";
}

function buildFormConfirmationMessage(formSpec, values) {
  return [
    `我已确认 ${formSpec.title || "表单"} 信息，请基于这些信息生成对应卡片。`,
    `form_id: ${formSpec.id || "form"}`,
    "confirmed_form_data:",
    JSON.stringify(values, null, 2),
  ].join("\n");
}

function hasDisplayValue(value) {
  if (value === null || value === undefined || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}

function isConfirmPlaceholder(value) {
  return String(value || "").trim().toLowerCase() === "to confirm";
}

function normalizeList(values) {
  if (!Array.isArray(values)) return [];
  return values.filter(hasDisplayValue);
}

function limitList(values, maxItems) {
  return normalizeList(values).slice(0, maxItems);
}

function appendValue(node, value) {
  if (Array.isArray(value)) {
    node.textContent = value.length ? value.join(", ") : "";
    return;
  }
  if (value && typeof value === "object") {
    node.textContent = Object.entries(value)
      .filter(([, nestedValue]) => hasDisplayValue(nestedValue))
      .map(([key, nestedValue]) => `${formatLabel(key)}: ${formatPlainValue(nestedValue)}`)
      .join("; ");
    return;
  }
  node.textContent = formatPlainValue(value);
  if (value === "To confirm") node.classList.add("to-confirm");
}

function formatPlainValue(value) {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value ?? "");
}

function formatLabel(key) {
  return String(key)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function setBusy(isBusy) {
  send.disabled = isBusy;
  input.disabled = isBusy;
  if (attachImage) attachImage.disabled = isBusy;
  if (imageInput) imageInput.disabled = isBusy;
}

function removeMessageElement(node) {
  const row = node?.closest(".message-row");
  if (row) {
    row.remove();
  } else if (node) {
    node.remove();
  }
}

function updateMeta(data = {}) {
  const threadId = data.conversation_id || data.thread_id || data.threadId;
  if (threadId) {
    conversationId = threadId;
    localStorage.setItem("momcozy_conversation_id", conversationId);
  }
  if (conversationLabel) {
    conversationLabel.textContent = conversationId ? `Conversation: ${conversationId.slice(0, 8)}` : "No conversation yet";
  }
  const skills = data.loaded_skill_ids || [];
  if (skillsLabel) {
    skillsLabel.textContent = skills.length ? `Loaded skills: ${skills.join(", ")}` : "No loaded skills";
  }
}

async function addPendingImageFiles(files) {
  if (!files.length) return;
  const remainingSlots = MAX_IMAGE_ATTACHMENTS - pendingImages.length;
  if (remainingSlots <= 0) {
    addMessage("error", `最多一次发送 ${MAX_IMAGE_ATTACHMENTS} 张图片。`);
    return;
  }

  const acceptedFiles = files.slice(0, remainingSlots);
  if (files.length > remainingSlots) {
    addMessage("error", `最多一次发送 ${MAX_IMAGE_ATTACHMENTS} 张图片，已忽略多余图片。`);
  }

  for (const file of acceptedFiles) {
    if (!file.type.startsWith("image/")) {
      addMessage("error", `无法添加 ${file.name || "该文件"}：只支持图片。`);
      continue;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      addMessage("error", `无法添加 ${file.name || "该图片"}：图片不能超过 6MB。`);
      continue;
    }
    pendingImages.push(await imageFileToAttachment(file));
  }
  renderPendingImages();
}

function imageFileToAttachment(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      resolve({
        id: crypto.randomUUID(),
        name: file.name,
        mime_type: file.type,
        size: file.size,
        image_url: String(reader.result || ""),
        detail: "auto",
      });
    };
    reader.onerror = () => reject(reader.error || new Error("Image read failed."));
    reader.readAsDataURL(file);
  });
}

function renderPendingImages() {
  if (!imagePreviewStrip) return;
  imagePreviewStrip.innerHTML = "";
  imagePreviewStrip.hidden = pendingImages.length === 0;
  for (const image of pendingImages) {
    const item = document.createElement("div");
    item.className = "image-preview";

    const img = document.createElement("img");
    img.src = image.image_url;
    img.alt = image.name || "Selected image";
    item.appendChild(img);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "image-remove";
    remove.setAttribute("aria-label", "Remove image");
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      pendingImages = pendingImages.filter((pendingImage) => pendingImage.id !== image.id);
      renderPendingImages();
      input.focus();
    });
    item.appendChild(remove);

    imagePreviewStrip.appendChild(item);
  }
}

function clearPendingImages() {
  pendingImages = [];
  renderPendingImages();
  if (imageInput) imageInput.value = "";
}

function clientLocale() {
  return navigator.language || "en-US";
}

function clientTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Los_Angeles";
}

function clientMessageSentAt(date = new Date()) {
  const pad = (value, length = 2) => String(Math.trunc(Math.abs(value))).padStart(length, "0");
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const offsetHours = Math.floor(Math.abs(offsetMinutes) / 60);
  const offsetRemainder = Math.abs(offsetMinutes) % 60;
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    "T",
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`,
    ".",
    pad(date.getMilliseconds(), 3),
    `${sign}${pad(offsetHours)}:${pad(offsetRemainder)}`,
  ].join("");
}

function buildAgUiPayload(text, images = []) {
  const threadId = conversationId || `thread_${crypto.randomUUID()}`;
  conversationId = threadId;
  localStorage.setItem("momcozy_conversation_id", conversationId);
  runCount += 1;
  localStorage.setItem("momcozy_run_count", String(runCount));
  const locale = clientLocale();
  const timezone = clientTimezone();
  const messageSentAt = clientMessageSentAt();
  const content = images.length
    ? [
        ...(text ? [{ type: "text", text }] : []),
        ...images.map((image) => ({
          type: "image",
          image_url: image.image_url,
          mime_type: image.mime_type,
          name: image.name,
          size: image.size,
          detail: image.detail || "auto",
        })),
      ]
    : text;

  return {
    threadId,
    userId: clientUserId,
    runId: `run_${Date.now()}_${runCount}`,
    state: {
      user_id: clientUserId,
      locale,
      timezone,
      message_sent_at: messageSentAt,
      user_profile: {
        user_id: clientUserId,
        language: locale,
      },
    },
    messages: [
      {
        id: `msg_${Date.now()}`,
        role: "user",
        content,
      },
    ],
    tools: [],
    context: [],
    forwardedProps: {
      user_id: clientUserId,
      locale,
      timezone,
      message_sent_at: messageSentAt,
    },
  };
}

async function streamChat(text, workRun, images = []) {
  const response = await fetch("/api/ag-ui", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(buildAgUiPayload(text, images)),
  });

  if (!response.ok || !response.body) {
    let message = `Request failed with ${response.status}`;
    try {
      const data = await response.json();
      message = data.error || message;
    } catch (_) {
      // Keep the status-based message when the body is not JSON.
    }
    throw new Error(message);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalData = {};
  let activeToolName = "";
  const toolNamesByKey = new Map();
  const usedTools = new Set();
  let lastStatus = "";
  let assistantNode = null;
  let formShown = false;
  let cardShown = false;
  let statusNode = null;

  function ensureStatusNode() {
    if (!statusNode) {
      statusNode = addStatusNode();
    }
    return statusNode;
  }

  function ensureAssistantNode() {
    if (!assistantNode) {
      assistantNode = addMessage("assistant", "");
    }
    return assistantNode;
  }

  function moveProvisionalTextToWorkPanel() {
    if (!assistantNode) return;
    const markdown = getAssistantMarkdown(assistantNode);
    removeMessageElement(assistantNode);
    assistantNode = null;
    addWorkNarration(workRun, markdown);
  }

  function rememberToolName(event, toolName) {
    if (!toolName) return;
    for (const key of workItemKeysForToolCall(event)) {
      toolNamesByKey.set(key, toolName);
    }
  }

  function toolNameForEvent(event, fallback = "tool") {
    return toolNamesByKey.get(workItemKeyForToolCall(event)) || activeToolName || fallback;
  }

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const event = parseSseEvent(rawEvent);
      if (!event) continue;

      if (event.type === "RUN_STARTED") {
        updateMeta(event);
      } else if (event.type === "ACTIVITY_SNAPSHOT") {
        updateMeta(event.content?.metadata || {});
      } else if (event.type === "CUSTOM" && event.name === THINKING_EVENT_NAME) {
        if (["started", "running"].includes(event.value?.status)) {
          clearTextIdleTimer(workRun);
          showThinking(workRun, {
            afterOutput: Boolean(event.value?.metadata?.after_output_text),
            title: event.value?.metadata?.after_output_text ? "Preparing next step" : "Thinking",
          });
        }
      } else if (event.type === "CUSTOM" && event.name === "momcozy.agent.status") {
        updateMeta(event.value?.metadata || {});
      } else if (event.type === "STEP_STARTED") {
        updateMeta(event.metadata || {});
      } else if (event.type === "STEP_FINISHED") {
        updateMeta(event.metadata || {});
      } else if (event.type === "TOOL_CALL_START") {
        activeToolName = event.tool_call_name || "";
        if (activeToolName) usedTools.add(activeToolName);
        rememberToolName(event, activeToolName);
        moveProvisionalTextToWorkPanel();
        addWorkToolStart(workRun, event);
      } else if (event.type === "TOOL_CALL_ARGS") {
        const toolName = toolNameForEvent(event);
        if (toolName) usedTools.add(toolName);
        moveProvisionalTextToWorkPanel();
        addWorkToolArgs(workRun, event, toolName);
      } else if (event.type === "TOOL_CALL_END") {
        const toolName = toolNameForEvent(event);
        if (toolName) usedTools.add(toolName);
        moveProvisionalTextToWorkPanel();
        addWorkToolEnd(workRun, event, toolName);
      } else if (event.type === "TOOL_CALL_RESULT") {
        const result = parseJson(event.content) || {};
        const toolName = result.tool_name || toolNameForEvent(event);
        usedTools.add(toolName);
        rememberToolName(event, toolName);
        moveProvisionalTextToWorkPanel();
        updateMeta({ loaded_skill_ids: result.skill_id ? [result.skill_id] : undefined });
        addWorkToolResult(workRun, event, result, toolName);
        if (toolName === "ui_form_create" && result.form) {
          addFormCard(result.form);
          formShown = true;
          assistantNode = null;
        } else if (toolName === "ui_card_create" && result.card) {
          addCard(result.card);
          cardShown = true;
          assistantNode = null;
        } else if (toolName === "ibclc_consult_card_create" && result.card) {
          addIbclcConsultCard(result.card);
          cardShown = true;
          assistantNode = null;
        } else if (toolName === "support_ticket_draft_create" && result.ticket) {
          addSupportTicketDraft(result);
          formShown = true;
          assistantNode = null;
        }
      } else if (event.type === "TEXT_MESSAGE_CONTENT") {
        workRun.hasOutput = true;
        clearTextIdleTimer(workRun);
        completeThinking(workRun);
        appendAssistantMarkdown(ensureAssistantNode(), event.delta || "");
        scheduleTextIdleThinking(workRun);
        messages.scrollTop = messages.scrollHeight;
      } else if (event.type === "TEXT_MESSAGE_END") {
        clearTextIdleTimer(workRun);
        if (statusNode) lastStatus = updateStatus(statusNode, "Answer ready.", { lastStatus, usedTools, done: true });
      } else if (event.type === "RUN_FINISHED") {
        finalData = event;
        clearTextIdleTimer(workRun);
        completeThinking(workRun);
        if (statusNode) lastStatus = updateStatus(statusNode, "Run finished.", { lastStatus, usedTools, done: true });
        if (!formShown && !cardShown && (!assistantNode || !getAssistantMarkdown(assistantNode).trim())) {
          setAssistantMarkdown(ensureAssistantNode(), "(No text response)");
        }
      } else if (event.type === "RUN_ERROR") {
        clearTextIdleTimer(workRun);
        completeThinking(workRun);
        throw new Error(event.message || "Run failed");
      }
    }

    if (done) break;
  }

  return finalData;
}

async function sendUserText(text, options = {}) {
  const images = options.images || [];
  if (!text.trim() && images.length === 0) return;

  addMessage("user", options.displayText || text, { images });
  const workRun = createWorkRun();
  setBusy(true);

  try {
    await streamChat(text, workRun, images);
    finishWorkPanel(workRun);
  } catch (error) {
    finishWorkPanel(workRun, { failed: true, message: error.message });
    addMessage("error", error.message);
  } finally {
    setBusy(false);
    input.focus();
  }
}

function parseSseEvent(rawEvent) {
  const dataLines = rawEvent
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart());
  if (!dataLines.length) return null;
  return JSON.parse(dataLines.join("\n"));
}

function updateStatus(node, text, options = {}) {
  if (!node || !text) return options.lastStatus || "";
  if (text === options.lastStatus && !options.done) return options.lastStatus;

  const statusText = node.querySelector(".status-text");
  const statusTools = node.querySelector(".status-tools");
  const normalizedText = labelForStatus(text);
  if (statusText) statusText.textContent = normalizedText;
  if (statusTools) {
    const tools = [...(options.usedTools || [])].map(labelForTool);
    statusTools.textContent = tools.length ? `Tools: ${tools.join(", ")}` : "";
  }
  node.classList.toggle("done", Boolean(options.done));
  messages.scrollTop = messages.scrollHeight;
  return text;
}

function labelForStatus(text) {
  const labels = {
    "Agent loop started.": "Starting...",
    "Evaluating user intent and safety context.": "Checking intent and safety...",
    "Requesting model response.": "Thinking...",
    "Requesting model response with tool outputs.": "Preparing the answer...",
    "Selecting an application tool.": "Choosing a tool...",
    "Executing an application tool.": "Checking context...",
    "Answer ready.": "Answer ready.",
    "Run finished.": "Done.",
  };
  return labels[text] || text;
}

function labelForStep(stepName, state) {
  if (stepName === "routing") {
    return state === "started" ? "Checking intent and safety..." : "Intent check complete.";
  }
  return state === "started" ? `Starting ${stepName}...` : `Finished ${stepName}.`;
}

function labelForTool(toolName) {
  const labels = {
    risk_evaluate: "safety check",
    profile_get: "profile lookup",
    memory_search: "memory search",
    ui_form_create: "form",
    ui_card_create: "card",
    ibclc_consult_card_create: "IBCLC consult card",
    device_manual_search: "device manual",
    load_skill: "skill loading",
    read_skill_file: "skill file reading",
    search_skill_assets: "skill asset search",
    run_approved_skill_script: "approved script",
    support_ticket_draft_create: "support ticket draft",
    reminder_list: "reminder lookup",
    reminder_create: "reminder creation",
    reminder_update: "reminder update",
    reminder_delete: "reminder deletion",
    knowledge_search: "knowledge search",
  };
  return labels[toolName] || toolName.replaceAll("_", " ");
}

function toolStartCopy(toolName) {
  const copies = {
    load_skill: {
      title: "Loading service workflow",
    },
    read_skill_file: {
      title: "Reading service reference",
    },
    ui_form_create: {
      title: "Preparing form",
    },
    ui_card_create: {
      title: "Creating card",
    },
    ibclc_consult_card_create: {
      title: "Preparing IBCLC consult",
    },
    device_manual_search: {
      title: "Checking device manual",
    },
    support_ticket_draft_create: {
      title: "Preparing support ticket",
    },
    profile_get: {
      title: "Checking profile context",
    },
  };
  return copies[toolName] || {
    title: `Using ${labelForTool(toolName)}`,
  };
}

function toolArgsCopy(toolName) {
  const copies = {
    load_skill: {
      title: "Service workflow selected",
      detail: "The required workflow is ready to load.",
    },
    read_skill_file: {
      title: "Reference selected",
      detail: "The approved reference is ready to read.",
    },
    ui_form_create: {
      title: "Form requirements ready",
      detail: "The form fields are ready to generate.",
    },
    ui_card_create: {
      title: "Card requirements ready",
      detail: "The card inputs are ready to generate.",
    },
    ibclc_consult_card_create: {
      title: "IBCLC consult details ready",
      detail: "The consult card is ready to generate.",
    },
    device_manual_search: {
      title: "Device question ready",
      detail: "The manual and FAQ lookup is ready to run.",
    },
    support_ticket_draft_create: {
      title: "Support ticket details ready",
      detail: "The issue details are ready for confirmation.",
    },
  };
  return copies[toolName] || {
    title: `${labelForTool(toolName)} parameters ready`,
  };
}

function toolEndCopy(toolName) {
  const copies = {
    load_skill: {
      title: "Loading service workflow",
    },
    read_skill_file: {
      title: "Reading service reference",
    },
    ui_form_create: {
      title: "Generating form",
    },
    ui_card_create: {
      title: "Generating card",
    },
    ibclc_consult_card_create: {
      title: "Generating IBCLC consult card",
    },
    device_manual_search: {
      title: "Searching device manual",
    },
    support_ticket_draft_create: {
      title: "Preparing support ticket",
    },
  };
  return copies[toolName] || {
    title: `Running ${labelForTool(toolName)}`,
  };
}

function toolResultCopy(toolName, result) {
  const errorMessage = result?.error?.message || "The tool did not complete successfully.";
  if (result?.ok === false) {
    return { title: "Tool failed", detail: errorMessage };
  }
  if (toolName === "load_skill") {
    return { title: "Service workflow loaded" };
  }
  if (toolName === "read_skill_file") {
    return { title: "Reference loaded" };
  }
  if (toolName === "ui_form_create") {
    return { title: "Form ready" };
  }
  if (toolName === "ui_card_create") {
    return { title: "Card ready" };
  }
  if (toolName === "ibclc_consult_card_create") {
    return { title: "IBCLC consult ready" };
  }
  if (toolName === "device_manual_search") {
    if (result?.status === "manual_already_loaded" || result?.status === "manual_already_loaded_with_faq") {
      return { title: "Device guide reused" };
    }
    return { title: "Device manual checked" };
  }
  if (toolName === "support_ticket_draft_create") {
    return { title: "Support ticket ready" };
  }
  return { title: "Tool completed" };
}

function cssEscape(value) {
  if (window.CSS?.escape) return window.CSS.escape(String(value));
  return String(value).replace(/["\\]/g, "\\$&");
}

function parseJson(value) {
  if (!value || typeof value !== "string") return null;
  try {
    return JSON.parse(value);
  } catch (_) {
    return null;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  const images = pendingImages.slice();
  if (!text && images.length === 0) return;

  input.value = "";
  clearPendingImages();
  await sendUserText(text, { images });
});

reset.addEventListener("click", () => {
  conversationId = "";
  localStorage.removeItem("momcozy_conversation_id");
  localStorage.removeItem(IBCLC_CONSULT_COMPLETED_KEY);
  messages.innerHTML = "";
  clearPendingImages();
  updateMeta();
  input.focus();
});

attachImage?.addEventListener("click", () => {
  imageInput?.click();
});

imageInput?.addEventListener("change", async () => {
  try {
    await addPendingImageFiles(Array.from(imageInput.files || []));
  } catch (error) {
    addMessage("error", error.message || "图片读取失败。");
  } finally {
    if (imageInput) imageInput.value = "";
    input.focus();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

window.addEventListener("storage", (event) => {
  if (event.key === IBCLC_CONSULT_COMPLETED_KEY) {
    handleIbclcConsultCompleted(parseJson(event.newValue));
  }
});

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin) return;
  handleIbclcConsultCompleted(event.data);
});

window.addEventListener("focus", () => {
  handleIbclcConsultCompleted(readStoredIbclcConsultCompletion());
});

window.addEventListener("pageshow", () => {
  handleIbclcConsultCompleted(readStoredIbclcConsultCompletion());
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    handleIbclcConsultCompleted(readStoredIbclcConsultCompletion());
  }
});

updateMeta();
addMessage(
  "assistant",
  "你好，我是 CoMate，懂妈妈的孕育与哺乳伙伴。\n\n我可以陪你做产前准备，比如分娩计划、待产包和入院准备；也可以支持产后泌乳指导、吸奶/亲喂计划、奶量管理、IBCLC 在线咨询，以及 Momcozy 设备使用指导。"
);
