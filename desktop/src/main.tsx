import { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import appIcon from "../src-tauri/icons/icon.svg";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  ClipboardPaste,
  FileAudio,
  FileCheck2,
  FolderOpen,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import "./styles.css";

window.addEventListener("error", (event) => {
  const root = document.getElementById("root");
  if (!root || root.dataset.rendered === "true") return;
  root.innerHTML = `<div class="fatal-error"><strong>QM Unlock 加载失败</strong><span>${String(event.error?.message || event.message || "未知前端错误")}</span><small>请从终端运行 npm run tauri dev 查看详细日志</small></div>`;
});
window.addEventListener("unhandledrejection", (event) => {
  const root = document.getElementById("root");
  if (!root || root.dataset.rendered === "true") return;
  root.innerHTML = `<div class="fatal-error"><strong>QM Unlock 加载失败</strong><span>${String(event.reason?.message || event.reason || "未知异步错误")}</span><small>请从终端运行 npm run tauri dev 查看详细日志</small></div>`;
});

type CredentialStatus = {
  available: boolean;
  platform: string;
  account_hint?: string;
  message: string;
};

type FileInfo = {
  path: string;
  supported: boolean;
  format?: string;
  songMid?: string;
  resourceFilename?: string;
  error?: string;
};

type Job = {
  input: string;
  output?: string;
  ok: boolean;
  format?: string;
  error?: string;
};

type OutputMode = "original" | "mp3";
type KeyMode = "automatic" | "manual";

type ProgressEvent = {
  phase: "scan" | "parse" | "ekey" | "decrypt" | "transcode" | "complete";
  input: string;
  current: number;
  total: number;
  percent: number;
  message: string;
};

type ScanResult = {
  files: string[];
  infos: FileInfo[];
};

function basename(path: string) {
  return path.split(/[\\/]/).pop() ?? path;
}

function extension(path: string) {
  return path.split(".").pop()?.toLowerCase() ?? "";
}

function uniquePaths(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}

export default function App() {
  const [paths, setPaths] = useState<string[]>([]);
  const [fileInfo, setFileInfo] = useState<Record<string, FileInfo>>({});
  const [outputDir, setOutputDir] = useState("");
  const [mode, setMode] = useState<OutputMode>("original");
  const [keyMode, setKeyMode] = useState<KeyMode>("automatic");
  const [manualKey, setManualKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [credentials, setCredentials] = useState<CredentialStatus>();
  const [running, setRunning] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [notice, setNotice] = useState<string>();
  const [progress, setProgress] = useState<ProgressEvent>();
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    const root = document.getElementById("root");
    if (root) root.dataset.rendered = "true";
  }, []);

  const refreshCredentials = useCallback(async () => {
    try {
      setCredentials(await invoke<CredentialStatus>("check_credentials"));
    } catch {
      setCredentials({
        available: false,
        platform: "unknown",
        message: "当前窗口无法读取 QQ 音乐登录状态",
      });
    }
  }, []);

  useEffect(() => {
    void refreshCredentials();
  }, [refreshCredentials]);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    void listen<ProgressEvent>("decrypt-progress", (event) => {
      setProgress(event.payload);
    }).then((stop) => {
      unlisten = stop;
    });
    return () => unlisten?.();
  }, []);

  const scanIncoming = useCallback(async (incoming: string[]) => {
    const candidates = uniquePaths(incoming);
    if (!candidates.length) return;
    setNotice(undefined);
    setProgress({
      phase: "scan",
      input: "",
      current: 0,
      total: 1,
      percent: 0,
      message: "正在扫描拖入的文件和文件夹",
    });
    try {
      const result = await invoke<ScanResult>("scan_paths", { paths: candidates });
      if (!result.files.length) {
        setNotice("没有找到 .mgg 或 .mflac 文件");
        return;
      }
      setPaths((old) => uniquePaths([...old, ...result.files]));
      setFileInfo((old) => ({
        ...old,
        ...Object.fromEntries(result.infos.map((info) => [info.path, info])),
      }));
      setJobs([]);
    } catch (error) {
      setNotice(`扫描失败：${String(error)}`);
    }
  }, []);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    void getCurrentWebview().onDragDropEvent((event) => {
      if (event.payload.type === "enter" || event.payload.type === "over") {
        setDragActive(true);
      } else if (event.payload.type === "leave") {
        setDragActive(false);
      } else if (event.payload.type === "drop") {
        setDragActive(false);
        void scanIncoming(event.payload.paths);
      }
    }).then((stop) => {
      unlisten = stop;
    }).catch(() => {
      // Browser fallback below still handles HTML5 file drops in dev tools.
    });
    return () => unlisten?.();
  }, [scanIncoming]);

  const chooseFiles = async () => {
    const picked = await open({
      multiple: true,
      filters: [{ name: "QQ 音乐加密文件", extensions: ["mgg", "mflac"] }],
    });
    if (Array.isArray(picked)) void scanIncoming(picked);
    else if (typeof picked === "string") void scanIncoming([picked]);
  };

  const chooseFolder = async () => {
    const picked = await open({ directory: true, multiple: false });
    if (typeof picked === "string") void scanIncoming([picked]);
  };

  const chooseOutput = async () => {
    const picked = await open({ directory: true, multiple: false });
    if (typeof picked === "string") setOutputDir(picked);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const dropped = Array.from(event.dataTransfer.files)
      .map((file) => (file as File & { path?: string }).path)
      .filter((path): path is string => Boolean(path));
    const supported = dropped.filter((path) => ["mgg", "mflac"].includes(extension(path)) || !extension(path));
    if (!supported.length) {
      setNotice("请选择 .mgg 或 .mflac 文件，也可以直接拖入包含它们的文件夹");
      return;
    }
    void scanIncoming(supported);
  };

  const removePath = (path: string) => {
    setPaths((old) => old.filter((item) => item !== path));
    setFileInfo((old) => {
      const next = { ...old };
      delete next[path];
      return next;
    });
  };

  const start = async () => {
    if (!paths.length || running) return;
    if (keyMode === "manual" && !manualKey.trim()) {
      setNotice("请粘贴 ekey 后再开始，或切换为自动获取");
      return;
    }
    if (keyMode === "automatic" && !credentials?.available) {
      setNotice("未检测到 QQ 音乐登录信息，请先登录 QQ 音乐，或切换为手动 ekey");
      return;
    }
    setNotice(undefined);
    setRunning(true);
    setJobs([]);
    setProgress(undefined);
    try {
      const result = await invoke<Job[]>("decrypt_paths", {
        paths,
        outputDir: outputDir || null,
        options: {
          output_mode: mode,
          manual_ekey: keyMode === "manual" ? manualKey.trim() : null,
        },
      });
      setJobs(result);
    } catch (error) {
      setJobs([{ input: "任务", ok: false, error: String(error) }]);
    } finally {
      setRunning(false);
      void refreshCredentials();
    }
  };

  const clearAll = () => {
    setPaths([]);
    setFileInfo({});
    setJobs([]);
    setNotice(undefined);
    setProgress(undefined);
  };

  const successCount = jobs.filter((job) => job.ok).length;
  const invalidCount = paths.filter((path) => fileInfo[path] && !fileInfo[path].supported).length;
  const keyReady = keyMode === "manual" ? manualKey.trim().length > 0 : Boolean(credentials?.available);
  const canStart = paths.length > 0 && keyReady && !running;
  const currentStep = running ? 3 : jobs.length ? 4 : paths.length && keyReady ? 3 : paths.length ? 2 : 1;
  const inputSummary = useMemo(() => {
    if (!paths.length) return "等待添加 .mgg 或 .mflac";
    const folders = paths.filter((path) => !extension(path));
    return folders.length ? `${paths.length} 个输入项，包含文件夹` : `${paths.length} 个加密文件`;
  }, [paths]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark"><img src={appIcon} alt="" /></div>
          <div><strong>QM Unlock</strong><span>QQ 音乐 musicex 解密工具</span></div>
        </div>
        <div className="topbar-meta">
          <span className="platform-tag"><CircleDot size={10} fill="currentColor" />{credentials?.platform || "本机"}</span>
          <button className="icon-button" title="刷新登录状态" aria-label="刷新登录状态" onClick={() => void refreshCredentials()}><RefreshCw size={17} /></button>
          <button className="icon-button" title="设置" aria-label="设置"><Settings2 size={17} /></button>
        </div>
      </header>

      <div className="layout">
        <aside className="flow-rail">
          <div className="rail-title">处理流程</div>
          <nav className="steps" aria-label="解密流程">
            <Step number="01" title="选择文件" caption="读取 musicex footer" state={currentStep > 1 ? "done" : "active"} />
            <Step number="02" title="获取 ekey" caption="自动凭据或手动粘贴" state={currentStep > 2 ? "done" : currentStep === 2 ? "active" : "idle"} />
            <Step number="03" title="解密与转码" caption="输出原格式或 MP3" state={currentStep > 3 ? "done" : currentStep === 3 ? "active" : "idle"} />
          </nav>

          <div className={`credential-card ${credentials?.available ? "is-ready" : ""}`}>
            <div className="credential-icon"><ShieldCheck size={18} /></div>
            <div className="credential-copy">
              <span className="eyebrow">授权状态</span>
              <strong>{credentials?.available ? "QQ 音乐已登录" : "等待授权"}</strong>
              <small>{credentials?.available ? `${credentials.account_hint || "当前用户"} · 可自动获取 ekey` : credentials?.message || "正在检查本机登录信息"}</small>
            </div>
          </div>

          <div className="rail-note">
            <KeyRound size={15} />
            <span>ekey 只在当前任务中使用，不写入磁盘。</span>
          </div>
        </aside>

        <section className="workspace">
          <div className="page-heading">
            <div>
              <span className="section-kicker">本地音乐工作台 / {credentials?.platform || "跨平台"}</span>
              <h1>解密 QQ 音乐加密文件</h1>
              <p>从下载的 `.mgg` / `.mflac` 中恢复音频，再按需要转换为 MP3。</p>
            </div>
            <div className="heading-status"><span className={`status-dot ${running ? "busy" : jobs.length ? "complete" : ""}`} />{running ? "处理中" : jobs.length ? "任务已完成" : "准备就绪"}</div>
          </div>

          <section className="section-panel source-panel">
            <div className="panel-heading">
              <div className="panel-title"><span className="step-number">01</span><div><h2>选择加密文件</h2><p>{inputSummary}</p></div></div>
              {paths.length > 0 && <button className="quiet-button" onClick={clearAll}><Trash2 size={15} />清空</button>}
            </div>
            <div className={`dropzone ${paths.length ? "has-items" : ""} ${dragActive ? "drag-active" : ""}`} onDragOver={(event) => event.preventDefault()} onDrop={handleDrop}>
              <div className="drop-icon"><Upload size={21} /></div>
              <strong>{dragActive ? "松开以添加文件" : paths.length ? "继续添加文件" : "拖入 .mgg / .mflac 文件或文件夹"}</strong>
              <span>{dragActive ? "将自动扫描文件夹并解析 musicex footer" : "支持批量选择，文件夹会递归扫描"}</span>
              <div className="drop-actions">
                <button className="outline-button" onClick={() => void chooseFiles()}><Plus size={16} />选择文件</button>
                <button className="outline-button" onClick={() => void chooseFolder()}><FolderOpen size={16} />选择文件夹</button>
              </div>
            </div>

            {paths.length > 0 && <div className="file-list">
              <div className="list-header"><span>输入队列</span><span>{paths.length} 项</span></div>
              {paths.map((path) => {
                const info = fileInfo[path];
                const isFolder = !extension(path);
                const active = running && progress?.input === path;
                return <div className="file-row" key={path}>
                  <div className="file-type-icon"><FileAudio size={17} /></div>
                  <div className="file-main"><strong title={path}>{basename(path)}</strong><span title={path}>{isFolder ? "文件夹 · 将递归扫描 .mgg / .mflac" : path}</span></div>
                  <div className={`file-state ${active ? "active" : info?.supported === false ? "bad" : info?.supported ? "good" : "pending"}`}>
                    {active ? <><LoaderCircle size={14} className="spin" />{progress?.phase === "parse" ? "解析中" : progress?.phase === "ekey" ? "获取 ekey" : progress?.phase === "transcode" ? "转码中" : "解密中"}</> : info?.supported === false ? <><AlertCircle size={14} />不可用</> : info?.supported ? <><FileCheck2 size={14} />已识别</> : isFolder ? <><FolderOpen size={14} />待扫描</> : <><LoaderCircle size={14} className="spin" />检查中</>}
                  </div>
                  <button className="row-remove" title="移除" aria-label={`移除 ${basename(path)}`} onClick={() => removePath(path)}><X size={16} /></button>
                </div>;
              })}
            </div>}
          </section>

          <div className="settings-grid">
            <section className="section-panel key-panel">
              <div className="panel-heading compact"><div className="panel-title"><span className="step-number">02</span><div><h2>获取 ekey</h2><p>用于还原 QMC2 音频密钥</p></div></div></div>
              <div className="mode-switch" role="tablist" aria-label="ekey 来源">
                <button className={keyMode === "automatic" ? "active" : ""} onClick={() => setKeyMode("automatic")}><RefreshCw size={15} />自动获取</button>
                <button className={keyMode === "manual" ? "active" : ""} onClick={() => setKeyMode("manual")}><ClipboardPaste size={15} />手动 ekey</button>
              </div>
              {keyMode === "automatic" ? <div className={`auth-state ${credentials?.available ? "ready" : "waiting"}`}>
                <div className="auth-state-icon">{credentials?.available ? <Check size={17} /> : <AlertCircle size={17} />}</div>
                <div><strong>{credentials?.available ? "将使用当前 QQ 音乐账号" : "未检测到 QQ 音乐登录"}</strong><span>{credentials?.available ? "每个文件会按 footer 信息请求对应 ekey" : "请登录 QQ 音乐，或使用手动 ekey"}</span></div>
                <button className="mini-button" onClick={() => void refreshCredentials()} title="重新检查"><RefreshCw size={15} /></button>
              </div> : <div className="manual-key-box">
                <div className="key-field"><KeyRound size={16} /><input value={manualKey} onChange={(event) => setManualKey(event.target.value)} type={showKey ? "text" : "password"} spellCheck={false} placeholder="粘贴 base64 ekey" /><button className="key-toggle" onClick={() => setShowKey((value) => !value)}>{showKey ? "隐藏" : "显示"}</button></div>
                <span>不会上传或保存，任务结束后仍保留在当前窗口。</span>
              </div>}
            </section>

            <section className="section-panel output-panel">
              <div className="panel-heading compact"><div className="panel-title"><span className="step-number">03</span><div><h2>输出设置</h2><p>选择解密后的文件格式和位置</p></div></div></div>
              <div className="output-mode" role="tablist" aria-label="输出格式">
                <button className={mode === "original" ? "active" : ""} onClick={() => setMode("original")}><FileAudio size={16} /><span><strong>原始格式</strong><small>OGG / FLAC / MP3</small></span></button>
                <button className={mode === "mp3" ? "active" : ""} onClick={() => setMode("mp3")}><CircleDot size={16} /><span><strong>转换为 MP3</strong><small>内置 FFmpeg + LAME</small></span></button>
              </div>
              <button className="output-path" onClick={() => void chooseOutput()} title={outputDir || "默认写回源文件目录"}><FolderOpen size={16} /><span><small>输出目录</small><strong>{outputDir || "与源文件相同"}</strong></span><ChevronRight size={15} /></button>
            </section>
          </div>

          {notice && <div className="notice-bar"><AlertCircle size={17} /><span>{notice}</span><button onClick={() => setNotice(undefined)} title="关闭提示" aria-label="关闭提示"><X size={15} /></button></div>}

          <div className="action-bar">
            <div><span className="action-count">{paths.length}</span><span>个输入项{invalidCount > 0 ? ` · ${invalidCount} 个需检查` : ""}</span></div>
            <button className="primary-button" disabled={!canStart} onClick={() => void start()}>{running ? <><LoaderCircle size={18} className="spin" />正在解密</> : <><LockKeyhole size={17} />开始解密</>}</button>
          </div>

          {progress && <div className={`progress-panel ${progress.phase === "complete" ? "complete" : ""}`}>
            <div className="progress-copy"><strong>{progress.message}</strong><span>{progress.input ? basename(progress.input) : ""}</span></div>
            <div className="progress-track"><div className="progress-fill" style={{ width: `${progress.percent}%` }} /></div>
            <div className="progress-meta"><span>{progress.phase === "scan" ? "扫描" : progress.phase === "parse" ? "解析" : progress.phase === "ekey" ? "获取 ekey" : progress.phase === "transcode" ? "转码" : progress.phase === "complete" ? "完成" : "解密"}</span><strong>{progress.percent}%</strong></div>
          </div>}

          {jobs.length > 0 && <section className="section-panel results-panel">
            <div className="results-heading"><div><span className="section-kicker">任务报告</span><h2>处理结果</h2></div><div className="result-summary"><strong>{successCount}</strong><span>/ {jobs.length} 成功</span></div></div>
            <div className="result-list">{jobs.map((job, index) => <div className={`result-row ${job.ok ? "success" : "failure"}`} key={`${job.input}-${index}`}>
              <div className="result-icon">{job.ok ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}</div>
              <div className="result-main"><strong>{basename(job.input)}</strong><span>{job.ok ? `${job.format?.toUpperCase() || "音频"} → ${job.output ? basename(job.output) : "完成"}` : job.error || "处理失败"}</span></div>
              <span className="result-status">{job.ok ? "完成" : "失败"}</span>
            </div>)}</div>
          </section>}
        </section>
      </div>
    </main>
  );
}

function Step({ number, title, caption, state }: { number: string; title: string; caption: string; state: "idle" | "active" | "done" }) {
  return <div className={`step ${state}`}><div className="step-marker">{state === "done" ? <Check size={14} /> : number}</div><div><strong>{title}</strong><span>{caption}</span></div></div>;
}

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("QM Unlock 找不到应用挂载节点");
}
createRoot(rootElement).render(<App />);
