import React, { createContext, useContext, useState, useCallback } from "react";

const BATCH_ID_KEY = "batch_photo_batchId";

export interface UploadedFile {
  id: string;
  name: string;
  path?: string;
  size: number;
  preview: string; // blob URL or remote URL
  naturalWidth?: number;
  naturalHeight?: number;
}

interface UploadContextType {
  /** 当前活跃批次 ID（后端返回） */
  batchId: string | null;
  setBatchId: React.Dispatch<React.SetStateAction<string | null>>;
  uploadedFiles: UploadedFile[];
  setUploadedFiles: React.Dispatch<React.SetStateAction<UploadedFile[]>>;
  addFiles: (files: UploadedFile[]) => void;
  removeFile: (id: string) => void;
  clearFiles: () => void;
}

const UploadContext = createContext<UploadContextType | undefined>(undefined);

export function UploadProvider({ children }: { children: React.ReactNode }) {
  const [batchId, setBatchIdRaw] = useState<string | null>(
    () => localStorage.getItem(BATCH_ID_KEY)
  );
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);

  // batchId 变化时同步到 localStorage
  const setBatchId: React.Dispatch<React.SetStateAction<string | null>> = useCallback(
    (action) => {
      setBatchIdRaw((prev) => {
        const next = typeof action === "function" ? action(prev) : action;
        if (next) {
          localStorage.setItem(BATCH_ID_KEY, next);
        } else {
          localStorage.removeItem(BATCH_ID_KEY);
        }
        return next;
      });
    },
    [],
  );

  const addFiles = useCallback((files: UploadedFile[]) => {
    setUploadedFiles((prev) => [...prev, ...files]);
  }, []);

  const removeFile = useCallback((id: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearFiles = useCallback(() => {
    setUploadedFiles([]);
    setBatchId(null);
  }, []);

  return (
    <UploadContext.Provider
      value={{ batchId, setBatchId, uploadedFiles, setUploadedFiles, addFiles, removeFile, clearFiles }}
    >
      {children}
    </UploadContext.Provider>
  );
}

export function useUpload() {
  const context = useContext(UploadContext);
  if (!context) {
    throw new Error("useUpload must be used within an UploadProvider");
  }
  return context;
}
