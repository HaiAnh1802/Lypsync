// ===== STATE =====
let selectedVideo = null;
let selectedVoiceRef = null;  // File audio mẫu giọng cho Voice Clone
let currentJobId = null;
let pollInterval = null;
let currentEngine = 'edge';       // TTS engine: 'edge' | 'gemini' | 'gtts' | 'voice_clone'
let currentLsEngine = 'wav2lip'; // Lip sync engine: 'wav2lip' | 'videoretalking'

// ===== SYSTEM STATUS CHECK =====
async function checkSystemStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const badge = document.getElementById('system-status');
    const text = document.getElementById('status-text');

    badge.className = 'status-badge';
    if (data.ready) {
      badge.classList.add('status-ready');
      text.textContent = '✅ Sẵn sàng';
    } else if (!data.ffmpeg) {
      badge.classList.add('status-error');
      text.textContent = '❌ Thiếu FFmpeg';
    } else if (!data.wav2lip) {
      badge.classList.add('status-error');
      text.textContent = '❌ Thiếu Wav2Lip';
    }

    // Update VRT badge
    const vrtBadge = document.getElementById('vrt-status-badge');
    if (vrtBadge) {
      if (data.videoretalking) {
        vrtBadge.textContent = 'Chất lượng cao';
        vrtBadge.className = 'engine-badge quality';
      } else {
        vrtBadge.textContent = 'Cần setup';
        vrtBadge.className = 'engine-badge warn';
      }
    }

    // Update Voice Clone badge
    const vcBadge = document.getElementById('vc-status-badge');
    if (vcBadge) {
      if (data.voice_clone) {
        vcBadge.textContent = 'Sẵn sàng';
        vcBadge.className = 'engine-badge free';
      } else {
        vcBadge.textContent = 'Cần setup';
        vcBadge.className = 'engine-badge warn';
      }
    }

    // Update voice clone status message
    checkVoiceCloneStatus(data.voice_clone);

  } catch {
    const badge = document.getElementById('system-status');
    badge.className = 'status-badge status-error';
    document.getElementById('status-text').textContent = '❌ Server chưa chạy';
  }
}

// ===== LIP SYNC ENGINE SELECTOR =====
function selectLsEngine(engine) {
  currentLsEngine = engine;
  document.querySelectorAll('.ls-engine-selector .engine-btn').forEach(btn => btn.classList.remove('active'));
  const btn = document.getElementById(`ls-engine-btn-${engine}`);
  if (btn) btn.classList.add('active');

  const note = document.getElementById('ls-engine-note');
  if (engine === 'videoretalking') {
    note.textContent = '✨ VideoReTalking – Chất lượng cao hơn, xử lý toàn bộ vùng mặt (cần setup models ~2GB)';
  } else {
    note.textContent = '⚡ Wav2Lip – Nhanh, ổn định, phù hợp cho mọi video';
  }
}

// ===== VIDEO UPLOAD =====
const videoInput = document.getElementById('video-input');
const dropZone = document.getElementById('video-drop-zone');

videoInput.addEventListener('change', e => handleVideoFile(e.target.files[0]));

// Drag & Drop
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('video/')) handleVideoFile(file);
});

function handleVideoFile(file) {
  if (!file) return;
  selectedVideo = file;

  const url = URL.createObjectURL(file);
  const preview = document.getElementById('video-preview');
  preview.src = url;

  preview.onloadedmetadata = () => {
    const duration = preview.duration.toFixed(1);
    const size = (file.size / 1024 / 1024).toFixed(1);
    document.getElementById('video-meta').textContent =
      `📹 ${file.name}  •  ${duration}s  •  ${size}MB`;
  };

  document.getElementById('video-drop-zone').classList.add('hidden');
  document.getElementById('video-preview-wrapper').classList.remove('hidden');
}

// ===== TEXT INPUT =====
const textInput = document.getElementById('text-input');
textInput.addEventListener('input', updateTextMeta);

function updateTextMeta() {
  const text = textInput.value;
  const chars = text.length;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const estimated = Math.round(words / 2.67);

  document.getElementById('char-count').textContent = `${chars} ký tự`;
  document.getElementById('duration-estimate').textContent = `~${estimated}s video`;
}

// ===== GENERATE =====
async function startGenerate() {
  if (!selectedVideo) {
    alert('Vui lòng upload video gốc!');
    return;
  }
  const text = textInput.value.trim();
  if (!text) {
    alert('Vui lòng nhập text!');
    return;
  }

  document.getElementById('generate-btn').disabled = true;
  document.getElementById('progress-section').classList.remove('hidden');
  document.getElementById('result-section').classList.add('hidden');
  document.getElementById('error-section').classList.add('hidden');
  setProgress(5, 'Đang upload video...');

  try {
    const formData = new FormData();
    formData.append('video', selectedVideo);
    formData.append('text', text);
    formData.append('tts_engine', currentEngine);
    formData.append('lipsync_engine', currentLsEngine);

    if (currentEngine === 'gemini') {
      const lsApiKey = document.getElementById('ls-api-key').value.trim();
      const lsVoice  = document.getElementById('ls-voice').value;
      formData.append('gemini_api_key', lsApiKey);
      formData.append('gemini_voice',   lsVoice);
    } else if (currentEngine === 'edge') {
      const edgeVoice = document.getElementById('edge-voice').value;
      formData.append('edge_voice', edgeVoice);
    } else if (currentEngine === 'voice_clone') {
      if (!selectedVoiceRef) {
        showError('Vui lòng upload file audio mẫu giọng trước!');
        document.getElementById('generate-btn').disabled = false;
        return;
      }
      formData.append('voice_file', selectedVoiceRef);
    }

    const res = await fetch('/api/generate', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload thất bại');
    }
    const { job_id } = await res.json();
    currentJobId = job_id;
    pollInterval = setInterval(pollJobStatus, 2000);

  } catch (err) {
    showError(err.message);
  }
}

// ===== POLL JOB STATUS =====
async function pollJobStatus() {
  if (!currentJobId) return;

  try {
    const res = await fetch(`/api/job/${currentJobId}`);
    const job = await res.json();

    setProgress(job.progress, job.step);
    updateStepIndicators(job.progress);

    if (job.status === 'done') {
      clearInterval(pollInterval);
      showResult(currentJobId, job.duration);
    } else if (job.status === 'error') {
      clearInterval(pollInterval);
      showError(job.error || 'Đã xảy ra lỗi');
    }
  } catch (err) {
    // Server tạm thời không phản hồi, tiếp tục poll
  }
}

// ===== PROGRESS UI =====
function setProgress(percent, step) {
  document.getElementById('progress-bar').style.width = percent + '%';
  document.getElementById('progress-percent').textContent = percent + '%';
  document.getElementById('current-step').textContent = step || '';
}

function updateStepIndicators(progress) {
  const ttsDone = progress >= 35;
  const loopDone = progress >= 50;
  const lipsyncDone = progress >= 100;

  setStepStatus('step-tts', progress >= 15, ttsDone);
  setStepStatus('step-loop', ttsDone, loopDone);
  setStepStatus('step-lipsync', loopDone, lipsyncDone);
}

function setStepStatus(id, active, done) {
  const el = document.getElementById(id);
  const icon = el.querySelector('.step-icon');
  el.className = 'step-status';
  if (done) {
    el.classList.add('done');
    icon.textContent = '✅';
  } else if (active) {
    el.classList.add('active');
    icon.textContent = '⚙️';
  } else {
    icon.textContent = '⏳';
  }
}

// ===== RESULT =====
function showResult(jobId, duration) {
  document.getElementById('progress-section').classList.add('hidden');
  document.getElementById('result-section').classList.remove('hidden');
  document.getElementById('generate-btn').disabled = false;

  const videoUrl = `/api/download/${jobId}`;
  const resultVideo = document.getElementById('result-video');
  resultVideo.src = videoUrl;
  resultVideo.load();
}

async function downloadResult() {
  if (!currentJobId) return;
  const a = document.createElement('a');
  a.href = `/api/download/${currentJobId}`;
  a.download = 'lipsync_output.mp4';
  a.click();
}

// ===== ERROR =====
function showError(message) {
  document.getElementById('progress-section').classList.add('hidden');
  document.getElementById('error-section').classList.remove('hidden');
  document.getElementById('error-message').textContent = message;
  document.getElementById('generate-btn').disabled = false;
}

// ===== RESET =====
function resetApp() {
  selectedVideo = null;
  selectedVoiceRef = null;
  currentJobId = null;
  clearInterval(pollInterval);

  document.getElementById('video-input').value = '';
  document.getElementById('video-preview').src = '';
  document.getElementById('video-drop-zone').classList.remove('hidden');
  document.getElementById('video-preview-wrapper').classList.add('hidden');
  document.getElementById('text-input').value = '';
  document.getElementById('char-count').textContent = '0 ký tự';
  document.getElementById('duration-estimate').textContent = '~0s video';
  document.getElementById('progress-section').classList.add('hidden');
  document.getElementById('result-section').classList.add('hidden');
  document.getElementById('error-section').classList.add('hidden');
  document.getElementById('generate-btn').disabled = false;
  setProgress(0, '');
  resetVoiceRef();
}

// ===== INIT =====
checkSystemStatus();
setInterval(checkSystemStatus, 30000);
selectEngine('edge'); // Mặc định Edge TTS

// ===== VOICE CLONE STATUS =====
function checkVoiceCloneStatus(available) {
  // Lip Sync tab badge
  const msg = document.getElementById('vc-status-msg');
  if (msg) {
    msg.textContent = available
      ? '✅ F5-TTS sẵn sàng – Upload file audio mẫu 3–30 giây để clone giọng'
      : '❌ F5-TTS chưa cài – Hãy chạy setup_voiceclone.bat trước';
    msg.className = available ? 'ls-tts-mode-label ls-tts-edge' : 'ls-tts-mode-label';
  }
  // TTS tab badge (if function exists)
  if (typeof updateTtsVcBadge === 'function') updateTtsVcBadge(available);
}

// ===== VOICE REF FILE HANDLING =====
const voiceRefInput = document.getElementById('voice-ref-input');
if (voiceRefInput) {
  voiceRefInput.addEventListener('change', e => handleVoiceRefFile(e.target.files[0]));
}

const vcDropZone = document.getElementById('vc-drop-zone');
if (vcDropZone) {
  vcDropZone.addEventListener('dragover', e => { e.preventDefault(); vcDropZone.classList.add('drag-over'); });
  vcDropZone.addEventListener('dragleave', () => vcDropZone.classList.remove('drag-over'));
  vcDropZone.addEventListener('drop', e => {
    e.preventDefault();
    vcDropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('audio/')) handleVoiceRefFile(file);
  });
}

function handleVoiceRefFile(file) {
  if (!file) return;
  selectedVoiceRef = file;

  const url = URL.createObjectURL(file);
  const audio = document.getElementById('vc-preview-audio');
  audio.src = url;

  const sizeMB = (file.size / 1024 / 1024).toFixed(1);
  document.getElementById('vc-file-name').textContent =
    `🎙️ ${file.name}  •  ${sizeMB}MB`;

  document.getElementById('vc-drop-zone').classList.add('hidden');
  document.getElementById('vc-preview-wrapper').classList.remove('hidden');
}

function resetVoiceRef() {
  selectedVoiceRef = null;
  const input = document.getElementById('voice-ref-input');
  if (input) input.value = '';
  const audio = document.getElementById('vc-preview-audio');
  if (audio) { audio.pause(); audio.src = ''; }
  const dropZone = document.getElementById('vc-drop-zone');
  if (dropZone) dropZone.classList.remove('hidden');
  const wrapper = document.getElementById('vc-preview-wrapper');
  if (wrapper) wrapper.classList.add('hidden');
}

// ===== TAB SWITCHER =====
function switchTab(tab) {
  // Update buttons
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`tab-btn-${tab}`).classList.add('active');

  // Update content
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  document.getElementById(`tab-${tab}`).classList.remove('hidden');
}

// ===== TTS TAB =====

// Char counter
const ttsTextInput = document.getElementById('tts-text');
if (ttsTextInput) {
  ttsTextInput.addEventListener('input', () => {
    const text = ttsTextInput.value;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    const est = Math.round(words / 2.67);
    document.getElementById('tts-char-count').textContent = `${text.length} ký tự`;
    document.getElementById('tts-duration-est').textContent = `~${est}s`;
  });
}

// Show/hide TTS tab API key
function toggleKeyVisibility() {
  const input = document.getElementById('tts-api-key');
  input.type = input.type === 'password' ? 'text' : 'password';
}

// Show/hide LipSync tab API key
function toggleLsKeyVisibility() {
  const input = document.getElementById('ls-api-key');
  input.type = input.type === 'password' ? 'text' : 'password';
}

// Xoa preview khi doi giong
function clearLsVoicePreview() {
  document.getElementById('ls-voice-preview-player').classList.add('hidden');
  document.getElementById('ls-preview-label').classList.add('hidden');
  const audio = document.getElementById('ls-preview-audio');
  audio.pause();
  audio.src = '';
}

// Nghe thu giong trong LipSync tab
async function previewLsVoice() {
  const apiKey = document.getElementById('ls-api-key').value.trim();
  const voice  = document.getElementById('ls-voice').value;

  if (!apiKey) { alert('Vui long nhap Gemini API key truoc!'); return; }
  if (!voice)  { alert('Vui long chon mot giong Gemini!'); return; }

  const btn = document.getElementById('ls-preview-btn');
  btn.disabled = true;
  btn.classList.add('loading');
  btn.textContent = '⏳ Đang tải...';

  document.getElementById('ls-voice-preview-player').classList.add('hidden');

  const sampleText = `Xin chào! Tôi là giọng đọc ${voice}. Rất vui được phục vụ bạn hôm nay.`;

  try {
    const formData = new FormData();
    formData.append('text', sampleText);
    formData.append('api_key', apiKey);
    formData.append('voice', voice);

    const res = await fetch('/api/tts', { method: 'POST', body: formData });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Loi'); }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);

    const audio = document.getElementById('ls-preview-audio');
    audio.src = url;

    const label = document.getElementById('ls-preview-label');
    label.textContent = `▶ ${voice}`;
    label.classList.remove('hidden');

    document.getElementById('ls-voice-preview-player').classList.remove('hidden');
    audio.play();

  } catch (err) {
    alert('Preview loi: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
    btn.textContent = '🔊 Nghe thử giọng';
  }
}

// Lưu LS API key vào localStorage (chia sẻ với TTS tab)
function saveLsApiKey() {
  const val = document.getElementById('ls-api-key').value.trim();
  if (val) localStorage.setItem('gemini_api_key', val);
  else localStorage.removeItem('gemini_api_key');
  // Sync sang TTS tab
  const ttsInput = document.getElementById('tts-api-key');
  if (ttsInput) ttsInput.value = val;
}

// ===== TTS ENGINE SELECTOR =====
function selectEngine(engine) {
  currentEngine = engine;

  // Update button styles
  ['edge', 'gemini', 'gtts', 'voice_clone'].forEach(e => {
    const btn = document.getElementById(`engine-btn-${e}`);
    if (btn) btn.classList.toggle('active', e === engine);
  });

  // Show/hide panels
  ['edge', 'gemini', 'gtts', 'voice_clone'].forEach(e => {
    const panel = document.getElementById(`panel-${e}`);
    if (panel) panel.classList.toggle('hidden', e !== engine);
  });
}

// Cap nhat indicator TTS mode
function updateLsTtsMode() {
  if (currentEngine === 'gemini') {
    const key   = (document.getElementById('ls-api-key')?.value || '').trim();
    const voice = document.getElementById('ls-voice')?.value || 'Kore';
    const label = document.getElementById('ls-tts-mode');
    if (!label) return;
    if (key) {
      label.textContent = `✅ Sẽ dùng Gemini TTS – giọng ${voice}`;
      label.className = 'ls-tts-mode-label ls-tts-gemini';
    } else {
      label.textContent = `⚠️ Nhập API key để dùng Gemini TTS`;
      label.className = 'ls-tts-mode-label';
    }
  }
}

// Lưu API key vào localStorage khi người dùng nhập
const apiKeyInput = document.getElementById('tts-api-key');
if (apiKeyInput) {
  // Load key đã lưu khi mở trang
  const savedKey = localStorage.getItem('gemini_api_key');
  if (savedKey) {
    apiKeyInput.value = savedKey;
    // Sync sang LipSync tab
    const lsKeyInput = document.getElementById('ls-api-key');
    if (lsKeyInput) {
      lsKeyInput.value = savedKey;
      updateLsTtsMode();  // Cap nhat indicator
    }
  }

  // Tự động lưu khi nhập
  apiKeyInput.addEventListener('input', () => {
    const val = apiKeyInput.value.trim();
    if (val) {
      localStorage.setItem('gemini_api_key', val);
    } else {
      localStorage.removeItem('gemini_api_key');
    }
  });
}

// Xoá preview khi đổi giọng
function clearVoicePreview() {
  document.getElementById('voice-preview-player').classList.add('hidden');
  document.getElementById('preview-voice-name').classList.add('hidden');
  const audio = document.getElementById('preview-audio');
  audio.pause();
  audio.src = '';
}

// Nghe thử giọng với đoạn mẫu ngắn
async function previewVoice() {
  const apiKey = document.getElementById('tts-api-key').value.trim();
  const voice  = document.getElementById('tts-voice').value;

  if (!apiKey) {
    alert('Vui lòng nhập Gemini API key trước!');
    return;
  }

  const btn = document.getElementById('preview-voice-btn');
  btn.disabled = true;
  btn.classList.add('loading');
  btn.textContent = '⏳ Đang tải...';

  // Ẩn player cũ
  document.getElementById('voice-preview-player').classList.add('hidden');

  // Câu mẫu ngắn ~5 giây
  const sampleText = `Xin chào! Tôi là giọng đọc ${voice}. Rất vui được phục vụ bạn hôm nay.`;

  try {
    const formData = new FormData();
    formData.append('text', sampleText);
    formData.append('api_key', apiKey);
    formData.append('voice', voice);

    const res = await fetch('/api/tts', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi tạo preview');
    }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);

    const audio = document.getElementById('preview-audio');
    audio.src = url;

    // Hiện label tên giọng
    const label = document.getElementById('preview-voice-name');
    label.textContent = `▶ ${voice}`;
    label.classList.remove('hidden');

    // Hiện player và tự phát
    document.getElementById('voice-preview-player').classList.remove('hidden');
    audio.play();

  } catch (err) {
    alert('Preview lỗi: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
    btn.textContent = '🔊 Nghe thử giọng';
  }
}

// Generate TTS
let ttsAudioBlob = null;
let ttsVoiceName = 'Kore';

async function generateTTS() {
  const text    = document.getElementById('tts-text').value.trim();
  const apiKey  = document.getElementById('tts-api-key').value.trim();
  const voice   = document.getElementById('tts-voice').value;

  if (!text)   { alert('Vui lòng nhập nội dung cần đọc!'); return; }
  if (!apiKey) { alert('Vui lòng nhập Gemini API key!'); return; }

  const btn = document.getElementById('tts-btn');
  const btnText = btn.querySelector('.btn-text');
  btn.disabled = true;
  btnText.textContent = 'Đang tạo giọng...';

  document.getElementById('tts-result').classList.add('hidden');
  document.getElementById('tts-error').classList.add('hidden');

  try {
    const formData = new FormData();
    formData.append('text', text);
    formData.append('api_key', apiKey);
    formData.append('voice', voice);

    const res = await fetch('/api/tts', { method: 'POST', body: formData });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi không xác định');
    }

    // Nhận file WAV dưới dạng blob
    ttsAudioBlob = await res.blob();
    ttsVoiceName = voice;

    const audioUrl = URL.createObjectURL(ttsAudioBlob);
    document.getElementById('tts-audio').src = audioUrl;
    document.getElementById('tts-result-voice').textContent = voice;
    document.getElementById('tts-result').classList.remove('hidden');

  } catch (err) {
    document.getElementById('tts-error-msg').textContent = err.message;
    document.getElementById('tts-error').classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btnText.textContent = 'Tạo giọng đọc';
  }
}

// Download TTS audio
function downloadTTS() {
  if (!ttsAudioBlob) return;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(ttsAudioBlob);
  a.download = `gemini_tts_${ttsVoiceName}.wav`;
  a.click();
}

// Reset TTS tab
function resetTTS() {
  document.getElementById('tts-text').value = '';
  document.getElementById('tts-char-count').textContent = '0 ký tự';
  document.getElementById('tts-duration-est').textContent = '~0s';
  document.getElementById('tts-audio').src = '';
  document.getElementById('tts-result').classList.add('hidden');
  document.getElementById('tts-error').classList.add('hidden');
  ttsAudioBlob = null;
}

// ===== TTS MODE SELECTOR =====
let currentTtsMode = 'gemini'; // 'gemini' | 'voice_clone'

function selectTtsMode(mode) {
  currentTtsMode = mode;

  // Update buttons
  ['gemini', 'voice_clone'].forEach(m => {
    const btn = document.getElementById(`tts-mode-btn-${m}`);
    if (btn) btn.classList.toggle('active', m === mode);
  });

  // Show/hide panels
  ['gemini', 'voice_clone'].forEach(m => {
    const panel = document.getElementById(`tts-panel-${m}`);
    if (panel) panel.classList.toggle('hidden', m !== mode);
  });

  // Reset result area when switching
  document.getElementById('tts-result').classList.add('hidden');
  document.getElementById('tts-error').classList.add('hidden');
}

// ===== TTS VOICE CLONE FILE HANDLING =====
let selectedTtsVoiceRef = null;

const ttsVcInput = document.getElementById('tts-voice-ref-input');
if (ttsVcInput) {
  ttsVcInput.addEventListener('change', e => handleTtsVoiceRefFile(e.target.files[0]));
}

const ttsVcDropZone = document.getElementById('tts-vc-drop-zone');
if (ttsVcDropZone) {
  ttsVcDropZone.addEventListener('dragover', e => { e.preventDefault(); ttsVcDropZone.classList.add('drag-over'); });
  ttsVcDropZone.addEventListener('dragleave', () => ttsVcDropZone.classList.remove('drag-over'));
  ttsVcDropZone.addEventListener('drop', e => {
    e.preventDefault();
    ttsVcDropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('audio/')) handleTtsVoiceRefFile(file);
  });
}

function handleTtsVoiceRefFile(file) {
  if (!file) return;
  selectedTtsVoiceRef = file;

  const url = URL.createObjectURL(file);
  const audio = document.getElementById('tts-vc-preview-audio');
  audio.src = url;

  const sizeMB = (file.size / 1024 / 1024).toFixed(1);
  document.getElementById('tts-vc-file-name').textContent = `🎙️ ${file.name}  •  ${sizeMB}MB`;

  document.getElementById('tts-vc-drop-zone').classList.add('hidden');
  document.getElementById('tts-vc-preview-wrapper').classList.remove('hidden');
}

function resetTtsVoiceRef() {
  selectedTtsVoiceRef = null;
  const input = document.getElementById('tts-voice-ref-input');
  if (input) input.value = '';
  const audio = document.getElementById('tts-vc-preview-audio');
  if (audio) { audio.pause(); audio.src = ''; }
  document.getElementById('tts-vc-drop-zone').classList.remove('hidden');
  document.getElementById('tts-vc-preview-wrapper').classList.add('hidden');
}

// Char counter for Voice Clone text
const ttsVcTextInput = document.getElementById('tts-vc-text');
if (ttsVcTextInput) {
  ttsVcTextInput.addEventListener('input', () => {
    const text = ttsVcTextInput.value;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    const est = Math.round(words / 2.67);
    document.getElementById('tts-vc-char-count').textContent = `${text.length} ký tự`;
    document.getElementById('tts-vc-duration-est').textContent = `~${est}s`;
  });
}

// Update VC badge in TTS tab from system status
function updateTtsVcBadge(available) {
  const badge = document.getElementById('tts-vc-badge');
  const statusMsg = document.getElementById('tts-vc-status');
  if (badge) {
    badge.textContent = available ? 'Sẵn sàng' : 'Cần setup';
    badge.className = available ? 'engine-badge free' : 'engine-badge warn';
  }
  if (statusMsg) {
    statusMsg.textContent = available
      ? '✅ F5-TTS sẵn sàng – Upload file audio mẫu 3–30 giây để clone giọng'
      : '❌ F5-TTS chưa cài – Hãy chạy setup_voiceclone.bat trước';
    statusMsg.className = available ? 'ls-tts-mode-label ls-tts-edge' : 'ls-tts-mode-label';
  }
}

// Hook into existing checkSystemStatus
const _origCheckStatus = checkSystemStatus;
// Patch: update TTS VC badge after status fetch
// (already handled by checkVoiceCloneStatus which calls updateTtsVcBadge)

// ===== TTS VOICE CLONE GENERATE (Job-based, chống timeout) =====
let ttsVcPollInterval = null;
let ttsVcJobId = null;

async function generateTtsVoiceClone() {
  const text = document.getElementById('tts-vc-text').value.trim();
  if (!text) { alert('Vui lòng nhập nội dung cần đọc!'); return; }
  if (!selectedTtsVoiceRef) { alert('Vui lòng upload file audio mẫu giọng trước!'); return; }

  const btn = document.getElementById('tts-vc-btn');
  const btnText = btn.querySelector('.btn-text');
  btn.disabled = true;
  btnText.textContent = 'Đang gửi...';

  document.getElementById('tts-result').classList.add('hidden');
  document.getElementById('tts-error').classList.add('hidden');

  // Hiện progress bar tạm dùng ls-tts-mode-label
  const statusEl = document.getElementById('tts-vc-status');

  try {
    const formData = new FormData();
    formData.append('text', text);
    formData.append('voice_file', selectedTtsVoiceRef);

    const res = await fetch('/api/tts-voice-clone', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi gửi yêu cầu');
    }

    const { job_id } = await res.json();
    ttsVcJobId = job_id;

    btnText.textContent = 'Đang clone giọng...';
    if (statusEl) {
      statusEl.textContent = '⏳ Đang clone giọng – lần đầu có thể mất 1-2 phút để tải model...';
      statusEl.className = 'ls-tts-mode-label';
    }

    // Poll status
    ttsVcPollInterval = setInterval(pollTtsVcJob, 2500);

  } catch (err) {
    document.getElementById('tts-error-msg').textContent = err.message;
    document.getElementById('tts-error').classList.remove('hidden');
    btn.disabled = false;
    btnText.textContent = 'Clone & Tạo giọng đọc';
  }
}

async function pollTtsVcJob() {
  if (!ttsVcJobId) return;
  const btn = document.getElementById('tts-vc-btn');
  const btnText = btn ? btn.querySelector('.btn-text') : null;
  const statusEl = document.getElementById('tts-vc-status');

  try {
    const res = await fetch(`/api/job/${ttsVcJobId}`);
    const job = await res.json();

    // Cập nhật status message
    if (statusEl && job.step) {
      statusEl.textContent = job.step;
    }

    if (job.status === 'done') {
      clearInterval(ttsVcPollInterval);
      ttsVcPollInterval = null;

      // Fetch audio blob từ endpoint riêng
      const audioRes = await fetch(`/api/download-audio/${ttsVcJobId}`);
      if (!audioRes.ok) throw new Error('Không thể tải audio kết quả');

      ttsAudioBlob = await audioRes.blob();
      ttsVoiceName = 'VoiceClone';

      const audioUrl = URL.createObjectURL(ttsAudioBlob);
      document.getElementById('tts-audio').src = audioUrl;
      document.getElementById('tts-result-voice').textContent = '🎤 Voice Clone';
      document.getElementById('tts-result').classList.remove('hidden');

      if (statusEl) {
        statusEl.textContent = '✅ F5-TTS sẵn sàng – Upload file audio mẫu 3–30 giây để clone giọng';
        statusEl.className = 'ls-tts-mode-label ls-tts-edge';
      }
      if (btn) { btn.disabled = false; if (btnText) btnText.textContent = 'Clone & Tạo giọng đọc'; }

    } else if (job.status === 'error') {
      clearInterval(ttsVcPollInterval);
      ttsVcPollInterval = null;

      document.getElementById('tts-error-msg').textContent = job.error || 'Đã xảy ra lỗi khi clone giọng';
      document.getElementById('tts-error').classList.remove('hidden');

      if (statusEl) {
        statusEl.textContent = '❌ F5-TTS chưa cài – Hãy chạy setup_voiceclone.bat trước';
        statusEl.className = 'ls-tts-mode-label';
      }
      if (btn) { btn.disabled = false; if (btnText) btnText.textContent = 'Clone & Tạo giọng đọc'; }
    }
  } catch (err) {
    // Server tạm không phản hồi, tiếp tục poll
  }
}


