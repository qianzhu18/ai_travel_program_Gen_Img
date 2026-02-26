import { useState, useCallback, useRef, useEffect } from "react";
import { useLocation } from "wouter";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "sonner";
import { X, Upload, Link as LinkIcon, Image, CheckCircle, AlertCircle, FolderOpen } from "lucide-react";
import { useUpload, UploadedFile } from "@/contexts/UploadContext";
import { uploadApi } from "@/lib/api";

interface UploadFile {
  id: string;
  name: string;
  path?: string;
  size: number;
  status: "uploading" | "success" | "error";
  progress: number;
  preview?: string;
  errorMsg?: string;
}

export default function MaterialUpload() {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [urlInput, setUrlInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [, setLocation] = useLocation();
  const { batchId, setBatchId, setUploadedFiles } = useUpload();

  // 当文件状态变化时，同步成功的文件到全局Context
  useEffect(() => {
    const successFiles: UploadedFile[] = files
      .filter((f) => f.status === "success" && f.preview)
      .map((f) => ({
        id: f.id,
        name: f.name,
        path: f.path,
        size: f.size,
        preview: f.preview!,
      }));
    setUploadedFiles(successFiles);
  }, [files, setUploadedFiles]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  /**
   * 核心上传：通过 uploadApi.batch() 发送到后端
   */
  const processFiles = useCallback(async (fileList: FileList, basePath?: string) => {
    const imageFiles = Array.from(fileList).filter((file) => file.type.startsWith("image/"));

    if (imageFiles.length === 0) {
      toast.error("请选择图片文件");
      return;
    }
    if (imageFiles.length > 100) {
      toast.error("单次最多上传 100 张图片");
      return;
    }

    // UI 占位条目
    const pendingFiles: UploadFile[] = imageFiles.map((file) => ({
      id: Math.random().toString(36).substr(2, 9),
      name: file.name,
      path: basePath || (file as any).webkitRelativePath || undefined,
      size: file.size,
      status: "uploading" as const,
      progress: 0,
      preview: URL.createObjectURL(file),
    }));

    setFiles((prev) => [...prev, ...pendingFiles]);
    setIsUploading(true);

    const pendingIds = new Set(pendingFiles.map((f) => f.id));
    const batchName = basePath || `上传_${new Date().toLocaleString("zh-CN")}`;

    try {
      // 上传开始 → 30%
      setFiles((prev) =>
        prev.map((f) => (pendingIds.has(f.id) ? { ...f, progress: 30 } : f))
      );

      // unwrap 已处理 code !== 0 的情况，返回 BatchUploadResult | undefined
      const data = await uploadApi.batch(imageFiles, batchName);

      // 响应到达 → 80%
      setFiles((prev) =>
        prev.map((f) => (pendingIds.has(f.id) ? { ...f, progress: 80 } : f))
      );

      if (data) {
        setBatchId(data.batch_id);

        const failedNames = new Set(
          (data.failed_files || []).map((f) => f.name)
        );
        const failedReasons = new Map(
          (data.failed_files || []).map((f) => [f.name, f.reason])
        );

        setFiles((prev) =>
          prev.map((f) => {
            if (!pendingIds.has(f.id)) return f;
            if (failedNames.has(f.name)) {
              return { ...f, progress: 100, status: "error", errorMsg: failedReasons.get(f.name) };
            }
            return { ...f, progress: 100, status: "success" };
          })
        );

        const msg = data.failed_count > 0
          ? `成功 ${data.uploaded_count} 张，失败 ${data.failed_count} 张`
          : `已上传 ${data.uploaded_count} 张图片`;
        toast.success(msg, { description: `批次: ${data.batch_name}` });
      } else {
        // unwrap 返回 undefined 表示后端 code !== 0，toast 已由 unwrap 触发
        setFiles((prev) =>
          prev.map((f) =>
            pendingIds.has(f.id) ? { ...f, progress: 100, status: "error", errorMsg: "上传失败" } : f
          )
        );
      }
    } catch (err: any) {
      // 网络错误等，拦截器已 toast
      const errMsg = err?.response?.data?.detail || err?.message || "网络错误";
      setFiles((prev) =>
        prev.map((f) =>
          pendingIds.has(f.id) ? { ...f, progress: 100, status: "error", errorMsg: errMsg } : f
        )
      );
    } finally {
      setIsUploading(false);
    }
  }, [setBatchId]);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files) {
        processFiles(e.dataTransfer.files);
      }
    },
    [processFiles]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        processFiles(e.target.files);
      }
    },
    [processFiles]
  );

  const handleFolderSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        const firstFile = e.target.files[0] as any;
        const folderPath = firstFile.webkitRelativePath?.split('/')[0] || '文件夹';
        processFiles(e.target.files, folderPath);
      }
    },
    [processFiles]
  );

  /**
   * URL 导入：调用 uploadApi.fromUrl()
   */
  const handleUrlImport = useCallback(async () => {
    if (!urlInput.trim()) {
      toast.error("请输入图片URL");
      return;
    }

    const newFile: UploadFile = {
      id: Math.random().toString(36).substr(2, 9),
      name: urlInput.split("/").pop()?.split("?")[0] || "url-image",
      size: 0,
      status: "uploading",
      progress: 0,
      preview: urlInput,
    };

    setFiles((prev) => [...prev, newFile]);
    const currentUrl = urlInput;
    setUrlInput("");

    try {
      const data = await uploadApi.fromUrl(currentUrl, batchId || undefined);

      if (data) {
        if (data.batch_id && !batchId) {
          setBatchId(data.batch_id);
        }
        setFiles((prev) =>
          prev.map((f) =>
            f.id === newFile.id
              ? { ...f, progress: 100, status: "success", name: data.filename || f.name }
              : f
          )
        );
        toast.success("URL导入成功");
      } else {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === newFile.id
              ? { ...f, progress: 100, status: "error", errorMsg: "导入失败" }
              : f
          )
        );
      }
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || err?.message || "网络错误";
      setFiles((prev) =>
        prev.map((f) =>
          f.id === newFile.id
            ? { ...f, progress: 100, status: "error", errorMsg: errMsg }
            : f
        )
      );
    }
  }, [urlInput, batchId, setBatchId]);

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setFiles([]);
    setBatchId(null);
    toast.info("已清空所有文件");
  }, [setBatchId]);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "未知大小";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const successCount = files.filter((f) => f.status === "success").length;
  const uploadingCount = files.filter((f) => f.status === "uploading").length;
  const errorCount = files.filter((f) => f.status === "error").length;

  return (
    <MainLayout
      title="素材上传"
      actions={
        files.length > 0 && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              已上传 {successCount}/{files.length} 张
              {errorCount > 0 && <span className="text-destructive ml-1">({errorCount} 失败)</span>}
            </span>
            {batchId && (
              <span className="text-xs text-muted-foreground">
                批次: {batchId.slice(0, 8)}...
              </span>
            )}
            <Button variant="outline" size="sm" onClick={clearAll}>
              清空全部
            </Button>
            <Button
              size="sm"
              disabled={uploadingCount > 0 || successCount === 0}
              onClick={() => {
                toast.success("开始预处理", { description: "正在跳转到预处理页面..." });
                setLocation("/preprocess");
              }}
            >
              开始预处理
            </Button>
          </div>
        )
      }
    >
      <div className="flex flex-col gap-6">
        {/* 上传区域 */}
        <Card className="border-2 border-dashed border-border hover:border-primary/50 transition-colors">
          <CardContent className="p-0">
            <div
              className={`relative flex flex-col items-center justify-center py-16 px-8 transition-colors ${
                isDragging ? "bg-primary/5" : ""
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Upload className="w-8 h-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                拖拽图片到此处上传
              </h3>
              <p className="text-sm text-muted-foreground mb-4">
                支持 JPG、PNG、WEBP 格式，单次最多上传 100 张，单张最大 10MB
              </p>
              <div className="flex items-center gap-4">
                <label>
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    className="hidden"
                    onChange={handleFileSelect}
                    disabled={isUploading}
                  />
                  <Button variant="default" asChild disabled={isUploading}>
                    <span>
                      <Image className="w-4 h-4 mr-2" />
                      选择文件
                    </span>
                  </Button>
                </label>

                <label>
                  <input
                    ref={folderInputRef}
                    type="file"
                    multiple
                    accept="image/*"
                    className="hidden"
                    onChange={handleFolderSelect}
                    disabled={isUploading}
                    {...({ webkitdirectory: "", directory: "" } as any)}
                  />
                  <Button variant="outline" asChild disabled={isUploading}>
                    <span>
                      <FolderOpen className="w-4 h-4 mr-2" />
                      选择文件夹
                    </span>
                  </Button>
                </label>
              </div>

              {/* URL导入 */}
              <div className="flex items-center gap-2 mt-6 w-full max-w-md">
                <div className="flex-1 flex items-center gap-2 px-3 py-2 bg-muted rounded-lg">
                  <LinkIcon className="w-4 h-4 text-muted-foreground shrink-0" />
                  <Input
                    type="url"
                    placeholder="或粘贴图片URL导入..."
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    className="border-0 bg-transparent p-0 h-auto focus-visible:ring-0"
                    onKeyDown={(e) => e.key === "Enter" && handleUrlImport()}
                    disabled={isUploading}
                  />
                </div>
                <Button variant="outline" size="sm" onClick={handleUrlImport} disabled={isUploading}>
                  导入
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 文件列表 */}
        {files.length > 0 && (
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-foreground">
                  上传列表 ({files.length} 张)
                </h3>
                <div className="flex items-center gap-4 text-sm">
                  <span className="flex items-center gap-1 text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    成功 {successCount}
                  </span>
                  {errorCount > 0 && (
                    <span className="flex items-center gap-1 text-destructive">
                      <AlertCircle className="w-4 h-4" />
                      失败 {errorCount}
                    </span>
                  )}
                  {uploadingCount > 0 && (
                    <span className="flex items-center gap-1 text-primary">
                      <span className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                      上传中 {uploadingCount}
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
                {files.map((file) => (
                  <div
                    key={file.id}
                    className="relative group aspect-[3/4] rounded-lg overflow-hidden bg-muted border border-border"
                  >
                    {file.preview && (
                      <img
                        src={file.preview}
                        alt={file.name}
                        className="w-full h-full object-cover"
                      />
                    )}

                    {file.status === "uploading" && (
                      <div className="absolute inset-0 bg-black/50 flex flex-col items-center justify-center">
                        <div className="w-3/4">
                          <Progress value={file.progress} className="h-1.5" />
                        </div>
                        <span className="text-white text-xs mt-2">
                          {Math.round(file.progress)}%
                        </span>
                      </div>
                    )}

                    {file.status === "success" && (
                      <div className="absolute top-2 right-2">
                        <CheckCircle className="w-5 h-5 text-green-500 drop-shadow-md" />
                      </div>
                    )}

                    {file.status === "error" && (
                      <div className="absolute top-2 right-2">
                        <AlertCircle className="w-5 h-5 text-red-500 drop-shadow-md" />
                      </div>
                    )}

                    <button
                      onClick={() => removeFile(file.id)}
                      className="absolute top-2 left-2 w-6 h-6 rounded-full bg-black/50 text-white opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center hover:bg-black/70"
                      aria-label={`删除 ${file.name}`}
                    >
                      <X className="w-4 h-4" />
                    </button>

                    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <p className="text-white text-xs truncate">{file.name}</p>
                      {file.path && (
                        <p className="text-white/50 text-xs truncate">{file.path}</p>
                      )}
                      <p className="text-white/70 text-xs">
                        {formatFileSize(file.size)}
                      </p>
                      {file.errorMsg && (
                        <p className="text-red-300 text-xs truncate">{file.errorMsg}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {files.length === 0 && (
          <div className="text-center py-12">
            <p className="text-muted-foreground">
              上传底图后，可进行水印去除和尺寸标准化处理
            </p>
          </div>
        )}
      </div>
    </MainLayout>
  );
}
