import { useState, useCallback, useEffect, useRef } from "react";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, ImageOff, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { reviewApi } from "@/lib/api";
import { useUpload } from "@/contexts/UploadContext";

interface ReviewImage {
  id: string;
  url: string;
  crowdType: string;
  promptName: string;
}

// 19种人群类型
const crowdTypes = [
  "全部",
  "幼女", "少女", "熟女", "奶奶",
  "幼男", "少男", "大叔",
  "情侣", "闺蜜", "兄弟", "异性伙伴",
  "母子(少年)", "母子(幼年)", "母女(少年)", "母女(幼年)",
  "父子(少年)", "父子(幼年)", "父女(少年)", "父女(幼年)",
];


export default function ReviewClassify() {
  const { batchId } = useUpload();

  const [pendingImages, setPendingImages] = useState<ReviewImage[]>([]);
  const [loading, setLoading] = useState(false);

  const [approvedImages, setApprovedImages] = useState<ReviewImage[]>([]);
  const [needEditImages, setNeedEditImages] = useState<ReviewImage[]>([]);
  const [rejectedImages, setRejectedImages] = useState<ReviewImage[]>([]);

  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedCrowdType, setSelectedCrowdType] = useState("全部");
  const thumbnailContainerRef = useRef<HTMLDivElement>(null);

  // 从 API 加载待审核图片
  useEffect(() => {
    if (!batchId) {
      setPendingImages([]);
      return;
    }

    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const result = await reviewApi.list({
          batch_id: batchId,
          review_status: "pending_review",
          page_size: 200,
        });
        if (!cancelled && result) {
          setPendingImages(
            result.items.map((item) => ({
              id: item.id,
              url: reviewApi.imageUrl(item.id),
              crowdType: item.crowd_name,
              promptName: item.style_name,
            })),
          );
        }
      } catch {
        if (!cancelled) toast.error("加载图片失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [batchId]);

  // 根据人群类型筛选待审核图片
  const filteredImages = selectedCrowdType === "全部"
    ? pendingImages
    : pendingImages.filter(img => img.crowdType === selectedCrowdType);

  // 当筛选条件改变或图片列表变化时，确保索引有效
  useEffect(() => {
    if (currentIndex >= filteredImages.length) {
      setCurrentIndex(Math.max(0, filteredImages.length - 1));
    }
  }, [selectedCrowdType, filteredImages.length, currentIndex]);

  const prevImage = filteredImages[currentIndex - 1];
  const currentImage = filteredImages[currentIndex];
  const nextImage = filteredImages[currentIndex + 1];

  // 移除图片并移入对应库
  const removeAndClassify = useCallback(async (targetLibrary: "approved" | "needEdit" | "rejected") => {
    if (!currentImage) return;

    const statusMap = {
      approved: "selected" as const,
      needEdit: "pending_modification" as const,
      rejected: "not_selected" as const,
    };

    // 乐观更新
    setPendingImages((prev) => prev.filter(img => img.id !== currentImage.id));

    if (targetLibrary === "approved") {
      setApprovedImages((prev) => [...prev, currentImage]);
      toast.success("已移入选用库");
    } else if (targetLibrary === "needEdit") {
      setNeedEditImages((prev) => [...prev, currentImage]);
      toast.success("已移入待修改库");
    } else {
      setRejectedImages((prev) => [...prev, currentImage]);
      toast.success("已移入回收库");
    }

    if (currentIndex >= filteredImages.length - 1 && currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }

    if (batchId) {
      try {
        await reviewApi.mark(currentImage.id, statusMap[targetLibrary]);
      } catch {
        toast.error("标记失败，请重试");
        // 回滚
        setPendingImages((prev) => [...prev, currentImage]);
        if (targetLibrary === "approved") {
          setApprovedImages((prev) => prev.filter(img => img.id !== currentImage.id));
        } else if (targetLibrary === "needEdit") {
          setNeedEditImages((prev) => prev.filter(img => img.id !== currentImage.id));
        } else {
          setRejectedImages((prev) => prev.filter(img => img.id !== currentImage.id));
        }
      }
    }
  }, [currentImage, currentIndex, filteredImages.length, batchId]);

  const handleApprove = useCallback(() => removeAndClassify("approved"), [removeAndClassify]);
  const handleNeedEdit = useCallback(() => removeAndClassify("needEdit"), [removeAndClassify]);
  const handleReject = useCallback(() => removeAndClassify("rejected"), [removeAndClassify]);

  const handlePrev = useCallback(() => {
    if (currentIndex > 0) setCurrentIndex((prev) => prev - 1);
  }, [currentIndex]);

  const handleNext = useCallback(() => {
    if (currentIndex < filteredImages.length - 1) setCurrentIndex((prev) => prev + 1);
  }, [currentIndex, filteredImages.length]);

  const handleSelectAll = useCallback(async () => {
    if (filteredImages.length === 0) return;

    const filteredIds = filteredImages.map(img => img.id);
    const snapshot = [...filteredImages];

    setApprovedImages((prev) => [...prev, ...snapshot]);
    setPendingImages((prev) => prev.filter(img => !filteredIds.includes(img.id)));
    setCurrentIndex(0);
    toast.success(`已将 ${snapshot.length} 张图片移入选用库`);

    if (batchId) {
      try {
        await reviewApi.batchMark(filteredIds, "selected");
      } catch {
        toast.error("批量标记失败");
        setPendingImages((prev) => [...prev, ...snapshot]);
        setApprovedImages((prev) => prev.filter(img => !filteredIds.includes(img.id)));
      }
    }
  }, [filteredImages, batchId]);

  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      switch (e.key) {
        case "ArrowLeft": handlePrev(); break;
        case "ArrowRight": handleNext(); break;
        case "1": handleApprove(); break;
        case "2": handleNeedEdit(); break;
        case "3": handleReject(); break;
        case " ": e.preventDefault(); handleNext(); break;
        case "a": case "A": handleSelectAll(); break;
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handlePrev, handleNext, handleApprove, handleNeedEdit, handleReject, handleSelectAll]);

  // 滚动缩略图到可视区域
  useEffect(() => {
    if (thumbnailContainerRef.current && filteredImages.length > 0) {
      const selectedThumb = thumbnailContainerRef.current.children[currentIndex] as HTMLElement;
      selectedThumb?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }, [currentIndex, filteredImages.length]);

  // 加载状态
  if (loading) {
    return (
      <MainLayout title="审核分类">
        <div className="flex flex-col items-center justify-center h-[calc(100vh-120px)] gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-muted-foreground">加载图片中...</p>
        </div>
      </MainLayout>
    );
  }

  // 空状态显示
  if (filteredImages.length === 0) {
    return (
      <MainLayout title="审核分类">
        <div className="flex flex-col h-[calc(100vh-120px)]">
          <div className="flex-1 flex flex-col items-center justify-center gap-4">
            <ImageOff className="w-16 h-16 text-muted-foreground" />
            <p className="text-lg text-muted-foreground">
              {selectedCrowdType === "全部"
                ? "所有图片已审核完成"
                : `"${selectedCrowdType}" 类型的图片已全部审核完成`}
            </p>
            <p className="text-sm text-muted-foreground">
              已选用 {approvedImages.length} 张 | 待修改 {needEditImages.length} 张 | 已回收 {rejectedImages.length} 张
            </p>
            {selectedCrowdType !== "全部" && (
              <Button variant="outline" onClick={() => setSelectedCrowdType("全部")}>
                查看全部类型
              </Button>
            )}
          </div>
          <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-background">
            <div className="flex items-center gap-4">
              <Select value={selectedCrowdType} onValueChange={setSelectedCrowdType}>
                <SelectTrigger className="w-[140px]"><SelectValue placeholder="人群类型" /></SelectTrigger>
                <SelectContent>
                  {crowdTypes.map((type) => (
                    <SelectItem key={type} value={type}>{type}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout title="审核分类">
      <div className="flex flex-col h-[calc(100vh-120px)]">
        {/* 主要区域：三张大图 */}
        <div className="flex-1 flex items-center justify-center gap-4 px-4 relative">
          <Button
            variant="ghost" size="icon"
            className="absolute left-0 z-10 h-12 w-12 rounded-full bg-white/80 shadow-md hover:bg-white"
            onClick={handlePrev} disabled={currentIndex === 0}
          >
            <ChevronLeft className="w-6 h-6" />
          </Button>

          <div className="flex items-center justify-center gap-4 max-w-[1200px] w-full">
            {/* 左侧图片 */}
            <div className="flex-1 max-w-[320px]">
              {prevImage ? (
                <div className="relative">
                  <div className="absolute -top-2 left-2 text-xs text-muted-foreground z-10">
                    IMG_{String(currentIndex).padStart(4, '0')}
                  </div>
                  <div className="aspect-[9/16] rounded-lg overflow-hidden bg-muted border border-border">
                    <img src={prevImage.url} alt="" className="w-full h-full object-cover opacity-70" />
                  </div>
                </div>
              ) : (
                <div className="aspect-[9/16] rounded-lg bg-muted border border-border" />
              )}
            </div>

            {/* 中间图片 */}
            <div className="flex-1 max-w-[320px]">
              {currentImage ? (
                <div className="relative">
                  <div className="absolute -top-2 left-2 text-xs text-muted-foreground z-10">
                    IMG_{String(currentIndex + 1).padStart(4, '0')}
                  </div>
                  <div className={cn("aspect-[9/16] rounded-lg overflow-hidden bg-muted border-2 border-primary shadow-lg")}>
                    <img src={currentImage.url} alt="" className="w-full h-full object-cover" />
                  </div>
                </div>
              ) : (
                <div className="aspect-[9/16] rounded-lg bg-muted border border-border" />
              )}
            </div>

            {/* 右侧图片 */}
            <div className="flex-1 max-w-[320px]">
              {nextImage ? (
                <div className="relative">
                  <div className="absolute -top-2 left-2 text-xs text-muted-foreground z-10">
                    IMG_{String(currentIndex + 2).padStart(4, '0')}
                  </div>
                  <div className="aspect-[9/16] rounded-lg overflow-hidden bg-muted border border-border">
                    <img src={nextImage.url} alt="" className="w-full h-full object-cover opacity-70" />
                  </div>
                </div>
              ) : (
                <div className="aspect-[9/16] rounded-lg bg-muted border border-border" />
              )}
            </div>
          </div>

          <Button
            variant="ghost" size="icon"
            className="absolute right-0 z-10 h-12 w-12 rounded-full bg-white/80 shadow-md hover:bg-white"
            onClick={handleNext} disabled={currentIndex >= filteredImages.length - 1}
          >
            <ChevronRight className="w-6 h-6" />
          </Button>
        </div>

        {/* 底部缩略图列表 */}
        <div className="py-3 px-4">
          <ScrollArea className="w-full">
            <div ref={thumbnailContainerRef} className="flex gap-2 pb-2">
              {filteredImages.map((img, idx) => (
                <div
                  key={img.id}
                  className={cn(
                    "w-14 h-14 rounded-md overflow-hidden cursor-pointer shrink-0 border-2 transition-all",
                    idx === currentIndex
                      ? "border-primary ring-2 ring-primary/30"
                      : "border-transparent hover:border-muted-foreground/30",
                  )}
                  onClick={() => setCurrentIndex(idx)}
                >
                  <img src={img.url} alt="" className="w-full h-full object-cover" />
                </div>
              ))}
            </div>
            <ScrollBar orientation="horizontal" />
          </ScrollArea>
        </div>

        {/* 底部操作栏 */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-background">
          <div className="flex items-center gap-4">
            <Select value={selectedCrowdType} onValueChange={setSelectedCrowdType}>
              <SelectTrigger className="w-[140px]"><SelectValue placeholder="人群类型" /></SelectTrigger>
              <SelectContent>
                {crowdTypes.map((type) => (
                  <SelectItem key={type} value={type}>{type}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-sm text-muted-foreground">
              1=选用 2=待修改 3=不选 Space=下一张 ←→=切换
            </span>
          </div>

          <div className="flex items-center gap-4">
            <Button className="bg-primary hover:bg-primary/90 min-w-[100px]" onClick={handleApprove} disabled={!currentImage}>
              选用(1)
            </Button>
            <Button variant="outline" className="min-w-[100px]" onClick={handleNeedEdit} disabled={!currentImage}>
              待修改(2)
            </Button>
            <Button variant="outline" className="min-w-[100px]" onClick={handleReject} disabled={!currentImage}>
              不选(3)
            </Button>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              待审核 {filteredImages.length} 张
            </span>
            <Button variant="outline" onClick={handleSelectAll} disabled={filteredImages.length === 0}>
              全选当前页(A)
            </Button>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
