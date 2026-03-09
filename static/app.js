const allowedExts = new Set(["jpg", "jpeg", "png", "bmp", "tif", "tiff", "webp", "gif"]);

const refs = {
  filePicker: document.getElementById("filePicker"),
  folderPicker: document.getElementById("folderPicker"),
  clearFiles: document.getElementById("clearFiles"),
  fileSummary: document.getElementById("fileSummary"),
  fileList: document.getElementById("fileList"),

  perSrc: document.getElementById("perSrc"),
  outputFormat: document.getElementById("outputFormat"),

  optMeta: document.getElementById("optMeta"),
  optCrop: document.getElementById("optCrop"),
  cropMax: document.getElementById("cropMax"),

  optResize: document.getElementById("optResize"),
  resizeRange: document.getElementById("resizeRange"),
  resizeLabel: document.getElementById("resizeLabel"),

  optRotate: document.getElementById("optRotate"),
  rotateRange: document.getElementById("rotateRange"),
  rotateLabel: document.getElementById("rotateLabel"),

  optNoise: document.getElementById("optNoise"),
  noiseStrength: document.getElementById("noiseStrength"),
  noiseLabel: document.getElementById("noiseLabel"),

  optColor: document.getElementById("optColor"),
  brightRange: document.getElementById("brightRange"),
  brightLabel: document.getElementById("brightLabel"),
  satRange: document.getElementById("satRange"),
  satLabel: document.getElementById("satLabel"),

  optBorder: document.getElementById("optBorder"),
  optBorderRandom: document.getElementById("optBorderRandom"),
  borderThickness: document.getElementById("borderThickness"),
  borderOpacity: document.getElementById("borderOpacity"),
  borderOpacityLabel: document.getElementById("borderOpacityLabel"),
  borderColor: document.getElementById("borderColor"),
  borderColorPicker: document.getElementById("borderColorPicker"),

  runBtn: document.getElementById("runBtn"),
  progressFill: document.getElementById("progressFill"),
  progressText: document.getElementById("progressText"),
  statusBadge: document.getElementById("statusBadge"),
  downloadBtn: document.getElementById("downloadBtn"),
  logBox: document.getElementById("logBox")
};

let selectedFiles = [];
const selectedKeys = new Set();
let running = false;

function makeFileKey(file) {
  return [
    file.name,
    file.size,
    file.lastModified,
    file.webkitRelativePath || "",
  ].join("::");
}

function isImageFile(file) {
  const name = (file.name || "").toLowerCase();
  const ext = name.split(".").pop();
  return allowedExts.has(ext);
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function appendFiles(list) {
  let added = 0;
  for (const file of list) {
    if (!isImageFile(file)) {
      continue;
    }
    const key = makeFileKey(file);
    if (selectedKeys.has(key)) {
      continue;
    }
    selectedKeys.add(key);
    selectedFiles.push(file);
    added += 1;
  }

  if (added === 0 && list.length > 0) {
    window.alert("지원 이미지 파일만 추가됩니다. (jpg, png, webp 등)");
  }

  renderFileState();
}

function clearFiles() {
  selectedFiles = [];
  selectedKeys.clear();
  refs.filePicker.value = "";
  refs.folderPicker.value = "";
  renderFileState();
}

function renderFileState() {
  const total = selectedFiles.length;
  const perSrc = Math.max(1, parseInt(refs.perSrc.value || "1", 10) || 1);
  const expected = total * perSrc;

  if (!total) {
    refs.fileSummary.textContent = "아직 선택된 이미지가 없습니다.";
    refs.fileList.innerHTML = "";
    return;
  }

  refs.fileSummary.textContent = `선택된 이미지: ${total}장 · 예상 결과: ${expected}장`;

  const previewNames = selectedFiles.slice(0, 180).map((file) => {
    const rel = file.webkitRelativePath || file.name;
    return `<div>${escapeHtml(rel)}</div>`;
  });

  if (selectedFiles.length > 180) {
    previewNames.push(`<div>...외 ${selectedFiles.length - 180}개</div>`);
  }

  refs.fileList.innerHTML = previewNames.join("");
}

function setStatus(kind, text) {
  refs.statusBadge.className = `status ${kind}`;
  refs.statusBadge.textContent = text;
}

function setProgress(done, total) {
  const safeTotal = total > 0 ? total : 0;
  const pct = safeTotal > 0 ? Math.min(100, (done / safeTotal) * 100) : 0;
  refs.progressFill.style.width = `${pct}%`;
  refs.progressText.textContent = `${done} / ${safeTotal}`;
}

function appendLogs(lines) {
  if (!refs.logBox || !lines || !lines.length) {
    return;
  }
  const appendText = lines.join("\n") + "\n";
  refs.logBox.textContent += appendText;
  refs.logBox.scrollTop = refs.logBox.scrollHeight;
}

function syncResizeLabel() {
  const r = parseInt(refs.resizeRange.value, 10);
  refs.resizeLabel.textContent = `${100 - r}% ~ ${100 + r}%`;
}

function syncRotateLabel() {
  const r = parseFloat(refs.rotateRange.value);
  refs.rotateLabel.textContent = `-${r.toFixed(1)}° ~ +${r.toFixed(1)}°`;
}

function syncNoiseLabel() {
  refs.noiseLabel.textContent = `${parseInt(refs.noiseStrength.value, 10)}%`;
}

function syncBrightLabel() {
  refs.brightLabel.textContent = `±${parseInt(refs.brightRange.value, 10)}%`;
}

function syncSatLabel() {
  refs.satLabel.textContent = `±${parseInt(refs.satRange.value, 10)}%`;
}

function syncBorderOpacityLabel() {
  refs.borderOpacityLabel.textContent = `${parseInt(refs.borderOpacity.value, 10)}%`;
}

function syncEnabledState() {
  refs.cropMax.disabled = !refs.optCrop.checked;
  refs.resizeRange.disabled = !refs.optResize.checked;
  refs.rotateRange.disabled = !refs.optRotate.checked;
  refs.noiseStrength.disabled = !refs.optNoise.checked;

  const colorDisabled = !refs.optColor.checked;
  refs.brightRange.disabled = colorDisabled;
  refs.satRange.disabled = colorDisabled;

  const borderDisabled = !refs.optBorder.checked;
  refs.optBorderRandom.disabled = borderDisabled;
  refs.borderThickness.disabled = borderDisabled;
  refs.borderOpacity.disabled = borderDisabled;
  refs.borderColor.disabled = borderDisabled;
  refs.borderColorPicker.disabled = borderDisabled;
}

function normalizeHexColor(value) {
  const raw = (value || "").trim();
  const short = /^#([0-9a-fA-F]{3})$/;
  const full = /^#([0-9a-fA-F]{6})$/;

  if (full.test(raw)) {
    return raw.toUpperCase();
  }

  if (short.test(raw)) {
    const token = raw.slice(1);
    return `#${token[0]}${token[0]}${token[1]}${token[1]}${token[2]}${token[2]}`.toUpperCase();
  }

  return "#000000";
}

async function startRun() {
  if (running) {
    return;
  }

  if (selectedFiles.length === 0) {
    window.alert("먼저 파일 또는 폴더에서 이미지들을 선택해 주세요.");
    return;
  }

  const perSrc = parseInt(refs.perSrc.value || "1", 10);
  if (!Number.isFinite(perSrc) || perSrc <= 0) {
    window.alert("원본 1장당 생성 개수를 1 이상으로 입력해 주세요.");
    return;
  }

  running = true;
  refs.runBtn.disabled = true;
  refs.downloadBtn.classList.add("hidden");
  refs.downloadBtn.removeAttribute("href");
  if (refs.logBox) {
    refs.logBox.textContent = "";
  }
  setProgress(0, selectedFiles.length * perSrc);
  setStatus("running", "작업 시작 중");

  try {
    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append("images", file, file.webkitRelativePath || file.name);
    });

    formData.append("per_src", String(perSrc));
    formData.append("output_format", refs.outputFormat.value);

    formData.append("use_meta", String(refs.optMeta.checked));
    formData.append("use_crop", String(refs.optCrop.checked));
    formData.append("crop_max", refs.cropMax.value);

    formData.append("use_resize", String(refs.optResize.checked));
    formData.append("resize_r", refs.resizeRange.value);

    formData.append("use_rotate", String(refs.optRotate.checked));
    formData.append("rotate_r", refs.rotateRange.value);

    formData.append("use_noise", String(refs.optNoise.checked));
    formData.append("max_noise_pct", refs.noiseStrength.value);

    formData.append("use_color", String(refs.optColor.checked));
    formData.append("bright_r", refs.brightRange.value);
    formData.append("sat_r", refs.satRange.value);

    formData.append("use_border", String(refs.optBorder.checked));
    formData.append("use_border_random", String(refs.optBorderRandom.checked));
    formData.append("border_thickness", refs.borderThickness.value);
    formData.append("border_opacity", refs.borderOpacity.value);
    formData.append("border_color", normalizeHexColor(refs.borderColor.value));

    const createResp = await fetch("/api/jobs", {
      method: "POST",
      body: formData,
    });

    const createData = await createResp.json();
    if (!createResp.ok) {
      throw new Error(createData.error || "작업 생성에 실패했습니다.");
    }

    await pollJob(createData.job_id);
  } catch (error) {
    appendLogs([`오류: ${error.message}`]);
    setStatus("failed", "실패");
  } finally {
    running = false;
    refs.runBtn.disabled = false;
  }
}

async function pollJob(jobId) {
  let logIndex = 0;

  while (true) {
    const statusResp = await fetch(`/api/jobs/${jobId}?from=${logIndex}`);
    const statusData = await statusResp.json();

    if (!statusResp.ok) {
      throw new Error(statusData.error || "진행 상태를 불러오지 못했습니다.");
    }

    appendLogs(statusData.logs || []);
    logIndex = statusData.log_index || logIndex;

    setProgress(statusData.done || 0, statusData.total || 0);

    if (statusData.status === "completed") {
      setStatus("completed", "완료");
      refs.downloadBtn.href = `/api/jobs/${jobId}/download`;
      refs.downloadBtn.classList.remove("hidden");
      return;
    }

    if (statusData.status === "failed") {
      setStatus("failed", "실패");
      throw new Error(statusData.error || "작업이 실패했습니다.");
    }

    if (statusData.status === "running" || statusData.status === "queued") {
      setStatus("running", "작업 중");
    }

    await new Promise((resolve) => setTimeout(resolve, 650));
  }
}



function bindEvents() {
  refs.filePicker.addEventListener("change", (event) => {
    appendFiles(Array.from(event.target.files || []));
    refs.filePicker.value = "";
  });

  refs.folderPicker.addEventListener("change", (event) => {
    appendFiles(Array.from(event.target.files || []));
    refs.folderPicker.value = "";
  });

  refs.clearFiles.addEventListener("click", clearFiles);
  refs.perSrc.addEventListener("input", renderFileState);

  refs.resizeRange.addEventListener("input", syncResizeLabel);
  refs.rotateRange.addEventListener("input", syncRotateLabel);
  refs.noiseStrength.addEventListener("input", syncNoiseLabel);
  refs.brightRange.addEventListener("input", syncBrightLabel);
  refs.satRange.addEventListener("input", syncSatLabel);
  refs.borderOpacity.addEventListener("input", syncBorderOpacityLabel);

  [
    refs.optCrop,
    refs.optResize,
    refs.optRotate,
    refs.optNoise,
    refs.optColor,
    refs.optBorder,
  ].forEach((target) => target.addEventListener("change", syncEnabledState));

  refs.borderColorPicker.addEventListener("input", () => {
    refs.borderColor.value = refs.borderColorPicker.value.toUpperCase();
  });

  refs.borderColor.addEventListener("change", () => {
    const normalized = normalizeHexColor(refs.borderColor.value);
    refs.borderColor.value = normalized;
    refs.borderColorPicker.value = normalized;
  });

  refs.runBtn.addEventListener("click", startRun);
}

function init() {
  bindEvents();
  syncResizeLabel();
  syncRotateLabel();
  syncNoiseLabel();
  syncBrightLabel();
  syncSatLabel();
  syncBorderOpacityLabel();
  syncEnabledState();
  renderFileState();
  setStatus("idle", "대기 중");
  setProgress(0, 0);

}

init();





