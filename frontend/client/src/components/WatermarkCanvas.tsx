import { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Undo2, Eraser, Paintbrush } from "lucide-react";

interface WatermarkCanvasProps {
  imageSrc: string;
  width: number;
  height: number;
  initialMaskData?: string; // base64 of previous mask
  onMaskChange?: (maskData: string, hasMask: boolean) => void;
}

export interface WatermarkCanvasRef {
  getMaskData: () => string;
  hasMask: () => boolean;
  clearMask: () => void;
}

const WatermarkCanvas = forwardRef<WatermarkCanvasRef, WatermarkCanvasProps>(
  ({ imageSrc, width, height, initialMaskData, onMaskChange }, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const maskCanvasRef = useRef<HTMLCanvasElement>(null);
    const [isDrawing, setIsDrawing] = useState(false);
    const [brushSize, setBrushSize] = useState(30);
    const [history, setHistory] = useState<ImageData[]>([]);
    const [tool, setTool] = useState<"brush" | "eraser">("brush");
    const lastPosRef = useRef<{ x: number; y: number } | null>(null);

    // 初始化画布
    useEffect(() => {
      const canvas = canvasRef.current;
      const maskCanvas = maskCanvasRef.current;
      if (!canvas || !maskCanvas) return;

      const ctx = canvas.getContext("2d");
      const maskCtx = maskCanvas.getContext("2d");
      if (!ctx || !maskCtx) return;

      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        // 绘制底图
        ctx.clearRect(0, 0, width, height);
        ctx.drawImage(img, 0, 0, width, height);

        // 初始化遮罩层
        maskCtx.clearRect(0, 0, width, height);

        // 如果有之前的遮罩数据，恢复它
        if (initialMaskData) {
          const maskImg = new Image();
          maskImg.onload = () => {
            maskCtx.drawImage(maskImg, 0, 0, width, height);
            // 将遮罩叠加到主画布
            ctx.globalAlpha = 0.4;
            ctx.drawImage(maskCanvas, 0, 0);
            ctx.globalAlpha = 1.0;
          };
          maskImg.src = initialMaskData;
        }

        // 保存初始状态到历史
        const initialState = maskCtx.getImageData(0, 0, width, height);
        setHistory([initialState]);
      };
      img.src = imageSrc;
    }, [imageSrc, width, height, initialMaskData]);

    // 重绘画布（底图 + 遮罩）
    const redrawCanvas = useCallback(() => {
      const canvas = canvasRef.current;
      const maskCanvas = maskCanvasRef.current;
      if (!canvas || !maskCanvas) return;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        ctx.clearRect(0, 0, width, height);
        ctx.drawImage(img, 0, 0, width, height);
        // 叠加遮罩
        ctx.globalAlpha = 0.4;
        ctx.drawImage(maskCanvas, 0, 0);
        ctx.globalAlpha = 1.0;
      };
      img.src = imageSrc;
    }, [imageSrc, width, height]);

    // 获取画布坐标
    const getCanvasPos = useCallback(
      (e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        if (!canvas) return { x: 0, y: 0 };
        const rect = canvas.getBoundingClientRect();
        const scaleX = width / rect.width;
        const scaleY = height / rect.height;
        return {
          x: (e.clientX - rect.left) * scaleX,
          y: (e.clientY - rect.top) * scaleY,
        };
      },
      [width, height]
    );

    // 绘制笔刷
    const drawBrush = useCallback(
      (x: number, y: number) => {
        const maskCanvas = maskCanvasRef.current;
        if (!maskCanvas) return;
        const maskCtx = maskCanvas.getContext("2d");
        if (!maskCtx) return;

        if (tool === "brush") {
          maskCtx.globalCompositeOperation = "source-over";
          maskCtx.fillStyle = "rgba(255, 60, 60, 0.8)";
          maskCtx.beginPath();
          maskCtx.arc(x, y, brushSize / 2, 0, Math.PI * 2);
          maskCtx.fill();
        } else {
          maskCtx.globalCompositeOperation = "destination-out";
          maskCtx.beginPath();
          maskCtx.arc(x, y, brushSize / 2, 0, Math.PI * 2);
          maskCtx.fill();
          maskCtx.globalCompositeOperation = "source-over";
        }
      },
      [brushSize, tool]
    );

    // 绘制线段（两点之间插值）
    const drawLine = useCallback(
      (x1: number, y1: number, x2: number, y2: number) => {
        const dist = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
        const steps = Math.max(Math.ceil(dist / (brushSize / 4)), 1);
        for (let i = 0; i <= steps; i++) {
          const t = i / steps;
          const x = x1 + (x2 - x1) * t;
          const y = y1 + (y2 - y1) * t;
          drawBrush(x, y);
        }
      },
      [drawBrush, brushSize]
    );

    const handleMouseDown = useCallback(
      (e: React.MouseEvent<HTMLCanvasElement>) => {
        const pos = getCanvasPos(e);
        setIsDrawing(true);
        lastPosRef.current = pos;

        // 保存当前状态到历史
        const maskCanvas = maskCanvasRef.current;
        if (maskCanvas) {
          const maskCtx = maskCanvas.getContext("2d");
          if (maskCtx) {
            const currentState = maskCtx.getImageData(0, 0, width, height);
            setHistory((prev) => [...prev, currentState]);
          }
        }

        drawBrush(pos.x, pos.y);
        redrawCanvas();
      },
      [getCanvasPos, drawBrush, redrawCanvas, width, height]
    );

    const handleMouseMove = useCallback(
      (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!isDrawing) return;
        const pos = getCanvasPos(e);
        if (lastPosRef.current) {
          drawLine(lastPosRef.current.x, lastPosRef.current.y, pos.x, pos.y);
        }
        lastPosRef.current = pos;
        redrawCanvas();
      },
      [isDrawing, getCanvasPos, drawLine, redrawCanvas]
    );

    const handleMouseUp = useCallback(() => {
      setIsDrawing(false);
      lastPosRef.current = null;

      // 通知父组件遮罩变化
      const maskCanvas = maskCanvasRef.current;
      if (maskCanvas && onMaskChange) {
        const maskCtx = maskCanvas.getContext("2d");
        if (maskCtx) {
          const imageData = maskCtx.getImageData(0, 0, width, height);
          const hasPixels = imageData.data.some((v, i) => i % 4 === 3 && v > 0);
          onMaskChange(maskCanvas.toDataURL(), hasPixels);
        }
      }
    }, [onMaskChange, width, height]);

    // 撤销
    const handleUndo = useCallback(() => {
      if (history.length <= 1) return;
      const newHistory = [...history];
      newHistory.pop();
      const prevState = newHistory[newHistory.length - 1];
      setHistory(newHistory);

      const maskCanvas = maskCanvasRef.current;
      if (maskCanvas) {
        const maskCtx = maskCanvas.getContext("2d");
        if (maskCtx) {
          maskCtx.putImageData(prevState, 0, 0);
          redrawCanvas();

          if (onMaskChange) {
            const hasPixels = prevState.data.some((v, i) => i % 4 === 3 && v > 0);
            onMaskChange(maskCanvas.toDataURL(), hasPixels);
          }
        }
      }
    }, [history, redrawCanvas, onMaskChange]);

    // 清除遮罩
    const handleClear = useCallback(() => {
      const maskCanvas = maskCanvasRef.current;
      if (!maskCanvas) return;
      const maskCtx = maskCanvas.getContext("2d");
      if (!maskCtx) return;

      // 保存当前状态
      const currentState = maskCtx.getImageData(0, 0, width, height);
      setHistory((prev) => [...prev, currentState]);

      maskCtx.clearRect(0, 0, width, height);
      redrawCanvas();

      if (onMaskChange) {
        onMaskChange(maskCanvas.toDataURL(), false);
      }
    }, [width, height, redrawCanvas, onMaskChange]);

    // 暴露方法给父组件
    useImperativeHandle(ref, () => ({
      getMaskData: () => {
        const maskCanvas = maskCanvasRef.current;
        return maskCanvas ? maskCanvas.toDataURL() : "";
      },
      hasMask: () => {
        const maskCanvas = maskCanvasRef.current;
        if (!maskCanvas) return false;
        const maskCtx = maskCanvas.getContext("2d");
        if (!maskCtx) return false;
        const imageData = maskCtx.getImageData(0, 0, width, height);
        return imageData.data.some((v, i) => i % 4 === 3 && v > 0);
      },
      clearMask: handleClear,
    }));

    return (
      <div className="flex flex-col gap-3">
        {/* 工具栏 */}
        <div className="flex flex-wrap items-center gap-3 px-2">
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant={tool === "brush" ? "default" : "outline"}
              onClick={() => setTool("brush")}
              className="h-8"
            >
              <Paintbrush className="w-4 h-4 mr-1" />
              画笔
            </Button>
            <Button
              size="sm"
              variant={tool === "eraser" ? "default" : "outline"}
              onClick={() => setTool("eraser")}
              className="h-8"
            >
              <Eraser className="w-4 h-4 mr-1" />
              橡皮
            </Button>
          </div>

          <div className="flex items-center gap-2 min-w-[180px] flex-1 sm:max-w-[240px]">
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              笔刷: {brushSize}px
            </span>
            <Slider
              value={[brushSize]}
              onValueChange={(v) => setBrushSize(v[0])}
              min={5}
              max={80}
              step={1}
              className="flex-1"
            />
          </div>

          <div className="flex items-center gap-1 sm:ml-auto">
            <Button
              size="sm"
              variant="outline"
              onClick={handleUndo}
              disabled={history.length <= 1}
              className="h-8"
            >
              <Undo2 className="w-4 h-4 mr-1" />
              撤销
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={handleClear}
              className="h-8"
            >
              清除标记
            </Button>
          </div>
        </div>

        {/* 画布区域 */}
        <div className="relative flex items-center justify-center bg-muted/30 rounded-lg overflow-hidden">
          <canvas
            ref={canvasRef}
            width={width}
            height={height}
            className="max-w-full max-h-[65vh] cursor-crosshair"
            style={{ objectFit: "contain" }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          />
          {/* 隐藏的遮罩画布 */}
          <canvas
            ref={maskCanvasRef}
            width={width}
            height={height}
            className="hidden"
          />
        </div>

        <p className="text-xs text-muted-foreground text-center">
          使用红色画笔在水印位置涂抹标记，标记完成后关闭预览继续下一张
        </p>
      </div>
    );
  }
);

WatermarkCanvas.displayName = "WatermarkCanvas";

export default WatermarkCanvas;
