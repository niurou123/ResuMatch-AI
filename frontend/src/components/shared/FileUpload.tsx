import { useCallback, useState } from 'react';
import { Upload } from 'lucide-react';
import { SUPPORTED_FORMATS_LABEL } from '@/lib/constants';

interface FileUploadProps {
  onUpload: (file: File) => void;
  uploading: boolean;
}

export function FileUpload({ onUpload, uploading }: FileUploadProps) {
  const [dragover, setDragover] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragover(false);
      const file = e.dataTransfer.files[0];
      if (file) onUpload(file);
    },
    [onUpload],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onUpload(file);
      // 重置 value，允许重复选择同一文件
      e.target.value = '';
    },
    [onUpload],
  );

  return (
    <div
      className={`file-upload-zone relative ${dragover ? 'dragover' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
      onDragLeave={() => setDragover(false)}
      onDrop={handleDrop}
    >
      {/* 文件输入：铺满整个区域，天然可点击。opacity:0 + 绝对定位覆盖，
          点击任意位置都直接命中 input（原生浏览器行为，最可靠） */}
      <input
        type="file"
        accept=".pdf,.docx,.md,.txt"
        onChange={handleChange}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        title="点击上传简历"
      />
      {uploading ? (
        <div className="flex flex-col items-center gap-3 pointer-events-none">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-text-2 text-sm">正在解析简历...</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 pointer-events-none">
          <Upload className="w-8 h-8 text-text-3" />
          <div>
            <p className="text-text font-medium text-sm">
              点击上传或拖拽文件到此处
            </p>
            <p className="text-text-3 text-xs mt-1">
              支持 {SUPPORTED_FORMATS_LABEL} 格式
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
