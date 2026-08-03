import { useRef, useState } from 'react';
import { Mic } from 'lucide-react';

interface VoiceInputButtonProps {
  onTranscript: (text: string) => void;  // 最终识别结果回调
  disabled?: boolean;
}

/**
 * 语音输入按钮 — 使用浏览器原生 Web Speech API
 * 支持中文识别（lang=zh-CN），Chrome/Edge 原生支持，零依赖
 *
 * 修复重复 bug：关闭 interimResults（中间结果），只在语音停顿后
 * 一次性回调最终识别文本，避免中间结果被反复追加导致大量重复。
 */
export function VoiceInputButton({ onTranscript, disabled }: VoiceInputButtonProps) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  // 延迟初始化 SpeechRecognition（SSR/类型安全）
  const getRecognition = () => {
    if (recognitionRef.current) return recognitionRef.current;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return null;
    const rec = new SR();
    rec.lang = 'zh-CN';
    rec.continuous = true;
    rec.interimResults = false;  // 关键：关闭中间结果，只在最终结果时回调，避免重复
    recognitionRef.current = rec;
    return rec;
  };

  const toggle = () => {
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const rec = getRecognition();
    if (!rec) {
      // 浏览器不支持时提示（Chrome/Edge 需开启麦克风权限）
      window.alert('当前浏览器不支持语音识别，请使用 Chrome 或 Edge，并允许麦克风权限');
      return;
    }
    setListening(true);

    let finalText = '';
    rec.onresult = (e: any) => {
      // 只取 isFinal 的结果（interimResults=false 时基本都是 final）
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalText += res[0].transcript;
      }
      if (finalText.trim()) {
        onTranscript(finalText);
        finalText = '';
      }
    };
    rec.onerror = () => { setListening(false); };
    rec.onend = () => { setListening(false); };
    rec.start();
  };

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled}
      className={`px-3 py-2 rounded-btn text-sm flex items-center gap-1.5 transition-colors ${
        listening
          ? 'bg-danger/20 text-danger border border-danger/40'
          : 'border border-border text-text-2 hover:text-text hover:border-primary/40'
      }`}
      title={listening ? '停止录音' : '语音输入问题'}
    >
      <Mic className="w-4 h-4" />
      {listening ? '聆听中...' : '语音'}
    </button>
  );
}

// 浏览器不支持时的全局提示（挂到 window 供引用）
export function isSpeechSupported(): boolean {
  return !!(window as any).SpeechRecognition || !!(window as any).webkitSpeechRecognition;
}
